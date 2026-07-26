#!/usr/bin/env python3
"""Build the compact paper-facing summary of canonical D1--D5 results.

The full-run ``diagnostic_*.json`` artifacts already contain deterministic
per-pair diagnostics and document-cluster bootstrap confidence intervals.  This
script copies their summaries into ``amp_ci.json`` for figures and writes a
human-readable Markdown table.  It never reads the historical E6/E8 results.
"""
from __future__ import annotations

import json
from pathlib import Path


RUNS = (
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
    "docred__glm-5__100d",
    "docred__kimi-k2__100d",
    "docred__qwen3-32b__100d",
)
ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "cross_run"

DIAGNOSTIC_LABELS = {
    "diagnostic.edge_identity": "D1 edge identity",
    "diagnostic.two_hop_endpoints": "D2 two-hop endpoints",
    "diagnostic.fanout_join": "D3 fan-out join",
    "diagnostic.top_undirected_degree": "D4 top degree",
    "diagnostic.short_connectivity": "D5 short connectivity",
}


def compact_query_summary(summary: dict) -> dict:
    interval = summary["amplification_document_cluster_ci"]
    return {
        "n": summary["n"],
        "n_documents": summary["n_documents"],
        "amp_mean": summary["amplification_mean_per_pair"],
        "amp_ci_lo": interval["ci_low"],
        "amp_ci_hi": interval["ci_high"],
        "query_drift_mean": summary["query_drift_mean"],
        "graph_drift_mean": summary["graph_drift_mean"],
        "amp_ratio_of_means": summary[
            "amplification_ratio_of_means_damped"
        ],
        "by_semantic_class": summary["by_semantic_class"],
    }


def main() -> int:
    output = {
        "artifact_type": "graphguard.diagnostic_amplification_summary",
        "artifact_version": 2,
        "source_artifacts": {},
        "runs": {},
    }
    for run in RUNS:
        path = REPORTS / f"diagnostic_{run}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("artifact_version") != 2:
            raise ValueError(f"{path}: expected diagnostic artifact version 2")
        summaries = data["summary"]
        missing = set(DIAGNOSTIC_LABELS) - set(summaries)
        if missing:
            raise ValueError(f"{path}: missing diagnostics {sorted(missing)}")
        output["source_artifacts"][run] = {
            "path": str(path.relative_to(ROOT)),
            "artifact_type": data["artifact_type"],
            "artifact_version": data["artifact_version"],
            "source_database": data["source_database"],
        }
        output["runs"][run] = {
            query_id: compact_query_summary(summaries[query_id])
            for query_id in DIAGNOSTIC_LABELS
        }

    out_path = REPORTS / "amp_ci.json"
    out_path.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("wrote", out_path)

    lines = [
        "# Canonical diagnostic amplification",
        "",
        "Document-cluster bootstrap 95% CIs from the complete canonical pair "
        "populations (B=1000, seed=0; mean of per-pair ratios).",
        "",
        "| run | query | n | docs | Amp mean | 95% CI | Amp(ratio-of-means) |",
        "|---|---|---:|---:|---:|---|---:|",
    ]
    for run, queries in output["runs"].items():
        for query_id, summary in queries.items():
            lines.append(
                f"| {run} | {DIAGNOSTIC_LABELS[query_id]} | "
                f"{summary['n']} | {summary['n_documents']} | "
                f"{summary['amp_mean']:.3f} | "
                f"[{summary['amp_ci_lo']:.3f}, "
                f"{summary['amp_ci_hi']:.3f}] | "
                f"{summary['amp_ratio_of_means']:.3f} |"
            )
    md_path = REPORTS / "amp_ci.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
