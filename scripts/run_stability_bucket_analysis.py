#!/usr/bin/env python3
"""Rebuild the L1/L2/L3 stability-bucket artifacts used by Figure 6.

The buckets follow the paper:
  L1 (strict): controlled decoding resampling and order-only changes;
  L2 (soft): presentation-equivalent prompt, schema, alias, and evidence edits;
  L3 (ablation): semantics-bounded edits.

The historical JSON field ``violation_rate_tau0p5`` is retained for backward
compatibility; it means max workload answer-set drift > 0.5. The query-change
label is mean absolute per-query gold F1 change > 0.05, not directional harm.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path

from graphguard import qa


ROOT = Path(__file__).resolve().parents[1]
RUNS = [
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
]

DATASET_LABELS = {
    "docred__deepseek-v4-flash__300d": "DocRED",
    "redocred__deepseek-v4-flash__300d": "Re-DocRED",
    "scierc__deepseek-v4-flash__100d": "SciERC",
    "cdr__deepseek-v4-flash__300d": "BC5CDR",
}


def bucket_for(semantic_class: str, description: str) -> str:
    description = description.lower()
    if semantic_class == "stochastic" or "reorder" in description:
        return "strict"
    return "soft" if semantic_class == "presentation" else "ablation"


def analyze(run: str) -> dict:
    db = ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
    if not db.is_file():
        raise FileNotFoundError(db)
    with sqlite3.connect(db) as conn:
        edges, gold, runs = qa.load_data(conn)
        metadata = {
            intervention_id: (semantic_class, description)
            for intervention_id, semantic_class, description
            in conn.execute(
                "SELECT intervention_id, semantic_class, description "
                "FROM intervention_candidates"
            )
        }

    rows: dict[str, list[dict[str, float]]] = defaultdict(list)
    for _, base_event, cf_event, document, _, intervention_id in runs:
        if (
            not cf_event
            or base_event not in edges
            or cf_event not in edges
        ):
            continue
        queries = qa.build_queries(gold.get(document, set()))
        if not queries:
            continue

        base_graph = edges[base_event]
        cf_graph = edges[cf_event]
        graph_drift = 1.0 - qa.graph_jaccard(base_graph, cf_graph)
        answer_drifts = []
        f1_changes = []
        for query in queries:
            base_answers = qa.execute(base_graph, query)
            cf_answers = qa.execute(cf_graph, query)
            answer_drifts.append(
                1.0 - qa.jaccard(base_answers, cf_answers)
            )
            gold_answers = query[1]["gold"]
            f1_changes.append(abs(
                qa.f1(base_answers, gold_answers)
                - qa.f1(cf_answers, gold_answers)
            ))

        semantic_class, description = metadata[intervention_id]
        rows[bucket_for(semantic_class, description)].append({
            "graph_drift": graph_drift,
            "query_drift": max(answer_drifts),
            "mean_abs_delta_f1": statistics.mean(f1_changes),
        })

    result = {
        "run": run,
        "n_pairs": sum(len(values) for values in rows.values()),
        "label_definition": (
            "mean absolute per-query gold F1 change > 0.05"
        ),
        "violation_definition": "max answer-set drift > 0.5",
        "bucket_definition": {
            "strict": "decoding resample and order-only",
            "soft": "presentation-equivalent",
            "ablation": "semantics-bounded",
        },
        "buckets": {},
    }
    for bucket in ("strict", "ablation", "soft"):
        values = rows[bucket]
        result["buckets"][bucket] = {
            "n_pairs": len(values),
            "query_divergence_rate": (
                sum(row["mean_abs_delta_f1"] > 0.05 for row in values)
                / len(values)
            ),
            "violation_rate_tau0p5": (
                sum(row["query_drift"] > 0.5 for row in values)
                / len(values)
            ),
            "mean_graph_drift": statistics.mean(
                row["graph_drift"] for row in values
            ),
            "mean_query_drift": statistics.mean(
                row["query_drift"] for row in values
            ),
            "mean_u": statistics.mean(
                row["mean_abs_delta_f1"] for row in values
            ),
        }
    return result


def write_table(results: list[dict]) -> None:
    lines = [
        r"\begin{table}[t]",
        r"\caption{Stability buckets by assumption strength. "
        r"Viol.\ is max answer-set drift $>0.5$; Abs.\ query div.\ is "
        r"mean absolute per-query gold-$F_1$ change $>0.05$.}",
        r"\label{tab:strictvssoft}",
        r"\centering\footnotesize",
        r"\begin{tabular}{llrrr}",
        r"\toprule",
        r"Dataset & Bucket & $n$ & Viol. & Abs.\ query div. \\",
        r"\midrule",
    ]
    for result_index, result in enumerate(results):
        run = result["run"]
        for bucket in ("strict", "soft", "ablation"):
            values = result["buckets"][bucket]
            lines.append(
                f"{DATASET_LABELS[run]} & {bucket.title()} & "
                f"{values['n_pairs']} & "
                f"{values['violation_rate_tau0p5']:.2f} & "
                f"{values['query_divergence_rate']:.2f} \\\\"
            )
        if result_index + 1 < len(results):
            lines.append(r"\midrule")
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    output = ROOT / "paper" / "tables" / "tab_strict_vs_soft.tex"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="*", default=RUNS)
    args = parser.parse_args()
    results = []
    for run in args.runs:
        result = analyze(run)
        results.append(result)
        output = (
            ROOT / "reports" / "cross_run" / f"strict_vs_soft_{run}.json"
        )
        output.write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {output}: {result['n_pairs']} pairs")
    if set(args.runs) == set(RUNS):
        results.sort(key=lambda result: RUNS.index(result["run"]))
        write_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
