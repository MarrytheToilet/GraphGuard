#!/usr/bin/env python3
"""Fixed-budget query-aware detection by registered workload regime.

The local target averages Q1 lookup and Q2 neighbor changes; the multi-hop
target averages Q3 join and Q4 two-hop changes. The primary score averages
answer-set drift over the same query instances. Maximum drift remains a
sensitivity score. Every graph-only/query-aware comparison uses an identical
review count and a deterministic, label-blind tie break.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.deployment_evidence import (  # noqa: E402
    DEFAULT_INDEX,
    load_artifact_index,
    load_downstream_evidence,
)
from graphguard.sqlite_snapshot import sha256_file  # noqa: E402
from scripts.run_graph_vs_query_ablation import (  # noqa: E402
    BOOTSTRAP_DRAWS,
    FIXED_REVIEW_BUDGETS,
    confusion,
    document_cluster_bootstrap,
    flags_at_count,
    score_summary,
)

MAIN_RUNS = [
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
]
OUT_DIR = ROOT / "reports" / "cross_run"
CHANGE_THRESHOLD = 0.05
REGIMES = {"local": ("lookup", "neighbor"), "multihop": ("join", "twohop")}
REGISTERED_FAMILIES = {
    "lookup": "deployment.lookup",
    "neighbor": "deployment.neighbor",
    "join": "deployment.shared_tail_join",
    "twohop": "deployment.typed_two_hop",
}


def analyze_run(run: str) -> dict:
    artifact = load_downstream_evidence(ROOT, run)
    rows = []
    for pair in artifact["per_pair"]:
        row = {
            "run_id": pair["run_id"],
            "document_id": pair["document_id"],
            "graph_drift": pair["graph_drift"],
        }
        for regime, families in REGIMES.items():
            summaries = [
                pair["families"][REGISTERED_FAMILIES[family]]
                for family in families
            ]
            n_queries = sum(item["n_queries"] for item in summaries)
            has_answer = any(
                item.get("has_nonempty_answer", False) for item in summaries
            )
            if not n_queries or not has_answer:
                continue
            row[f"{regime}_mean_abs_delta_f1"] = sum(
                item.get("mean_delta_f1_abs", 0.0) * item["n_queries"]
                for item in summaries
            ) / n_queries
            row[f"{regime}_query_mean"] = sum(
                item.get("mean_answer_drift", 0.0) * item["n_queries"]
                for item in summaries
            ) / n_queries
            row[f"{regime}_query_max"] = max(
                item.get("max_answer_drift", 0.0) for item in summaries
            )
            row[f"{regime}_n_queries"] = n_queries
        rows.append(row)

    index = load_artifact_index(ROOT)
    out = {
        "artifact_type": "graphguard.query_regime_analysis",
        "artifact_version": 2,
        "run": run,
        "source": {
            "evidence_index": {
                "path": str(DEFAULT_INDEX),
                "sha256": sha256_file(ROOT / DEFAULT_INDEX),
            },
            "downstream_sha256": index["entries"][
                f"downstream:{run}"
            ]["raw_sha256"],
        },
        "n_pairs": len(rows),
        "label_definition": (
            "query-count-weighted mean absolute per-query gold-F1 change "
            "within the regime > threshold"
        ),
        "change_threshold_delta_f1": CHANGE_THRESHOLD,
        "active_pair_filter": (
            "registered regime has at least one query and at least one "
            "nonempty paired answer"
        ),
        "score_definitions": {
            "graph_only": "canonicalized typed-edge Jaccard drift",
            "query_mean": (
                "query-count-weighted mean answer-set Jaccard drift within "
                "the regime; primary score for the mean-change target"
            ),
            "query_max": (
                "maximum answer-set Jaccard drift within the regime; "
                "sensitivity score for any-query change"
            ),
        },
        "fixed_budget_ties": (
            "exact top-k selection; score ties broken by SHA-256(run_id) "
            "without target labels"
        ),
        "regimes": {},
    }

    for regime in REGIMES:
        eligible = [
            row for row in rows
            if f"{regime}_mean_abs_delta_f1" in row
        ]
        if len(eligible) < 50:
            continue
        labels = [
            row[f"{regime}_mean_abs_delta_f1"] > CHANGE_THRESHOLD
            for row in eligible
        ]
        graph_scores = [row["graph_drift"] for row in eligible]
        mean_scores = [row[f"{regime}_query_mean"] for row in eligible]
        max_scores = [row[f"{regime}_query_max"] for row in eligible]
        row_ids = [row["run_id"] for row in eligible]
        graph_summary = score_summary(labels, graph_scores)
        mean_summary = score_summary(labels, mean_scores)
        max_summary = score_summary(labels, max_scores)
        bootstrap_ci, valid_draws, bootstrap_seed = document_cluster_bootstrap(
            eligible, labels, graph_scores, mean_scores, f"{run}:{regime}"
        )
        result = {
            "n": len(eligible),
            "positive_base_rate": round(sum(labels) / len(labels), 4),
            "threshold_free": {
                "graph_only": graph_summary,
                "query_mean": mean_summary,
                "query_max": max_summary,
                "query_mean_minus_graph_auroc": {
                    "difference": round(
                        mean_summary["auroc"] - graph_summary["auroc"], 4
                    ),
                    "document_cluster_bootstrap_ci95": bootstrap_ci,
                    "requested_draws": BOOTSTRAP_DRAWS,
                    "valid_draws": valid_draws,
                    "rng": bootstrap_seed,
                },
            },
            "fixed_review_budgets": [],
        }
        for budget in FIXED_REVIEW_BUDGETS:
            n_review = round(budget * len(eligible))
            graph_flags, graph_boundary = flags_at_count(
                graph_scores, row_ids, n_review
            )
            mean_flags, mean_boundary = flags_at_count(
                mean_scores, row_ids, n_review
            )
            max_flags, max_boundary = flags_at_count(
                max_scores, row_ids, n_review
            )
            graph_result = confusion(graph_flags, labels)
            mean_result = confusion(mean_flags, labels)
            max_result = confusion(max_flags, labels)
            result["fixed_review_budgets"].append({
                "review_budget": budget,
                "n_review": n_review,
                "score_boundary": {
                    "graph_only": round(graph_boundary, 4),
                    "query_mean": round(mean_boundary, 4),
                    "query_max": round(max_boundary, 4),
                },
                "graph_only": graph_result,
                "query_mean": mean_result,
                "query_max": max_result,
                "query_mean_minus_graph_f1": round(
                    mean_result["f1"] - graph_result["f1"], 4
                ),
                "query_max_minus_graph_f1": round(
                    max_result["f1"] - graph_result["f1"], 4
                ),
            })
        out["regimes"][regime] = result

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"regimes_{run}.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"[done] {run}: {len(rows)} pairs -> {out_path}")
    for regime, result in out["regimes"].items():
        gains = ", ".join(
            f"{row['review_budget']:.0%}={row['query_mean_minus_graph_f1']:+.3f}"
            for row in result["fixed_review_budgets"]
        )
        print(
            f"  {regime:<9} n={result['n']:<6} "
            f"base={result['positive_base_rate']:.2f} gains: {gains}"
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="*", default=MAIN_RUNS)
    args = parser.parse_args()
    for run in args.runs:
        analyze_run(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
