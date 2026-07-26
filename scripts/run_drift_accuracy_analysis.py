#!/usr/bin/env python3
"""Reproduce the registered DocRED RQ8 drift/accuracy statistics.

The 4,000-pair query population is the label-blind continuity cohort in
``deployment_cohorts.json``. K1 remains a separate extraction-level
contrast over every successful schema rename/reorder pair in the source DB.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from scipy.stats import spearmanr

from graphguard.contracts.metrics import (
    _project,
    _to_triples,
    edge_jaccard,
)
from graphguard.deployment_evidence import (
    DEFAULT_INDEX,
    load_artifact_index,
    load_rq8_pairs,
)
from graphguard.sqlite_snapshot import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = "docred__deepseek-v4-flash__300d"
DEFAULT_DB = (
    f"data/processed/runs/{DEFAULT_RUN}/{DEFAULT_RUN}.db"
)
DEFAULT_OUT = (
    f"reports/cross_run/drift_accuracy_{DEFAULT_RUN}.json"
)


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.mean(values) if values else 0.0


def extraction_quality(
    predicted: set[tuple[str, str, str]],
    gold: set[tuple[str, str, str]],
) -> tuple[float, float]:
    true_positive = len(predicted & gold)
    recall = true_positive / len(gold) if gold else 0.0
    precision = true_positive / len(predicted) if predicted else 0.0
    return recall, precision


def load_edge_rows(
    conn: sqlite3.Connection,
) -> dict[str, list[sqlite3.Row]]:
    by_event: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in conn.execute("SELECT * FROM extracted_edges"):
        by_event[row["event_id"]].append(row)
    return by_event


def load_gold(
    conn: sqlite3.Connection,
) -> dict[str, set[tuple[str, str, str]]]:
    by_doc: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for doc, head, relation, tail in conn.execute(
        "SELECT document_id, head_name, relation_base, tail_name "
        "FROM gold_edges"
    ):
        if head and relation and tail:
            by_doc[doc].add((
                head.lower().strip(),
                relation,
                tail.lower().strip(),
            ))
    return by_doc


def query_population(rows: list[dict]) -> dict:
    drift = [row["graph_drift"] for row in rows]
    delta_recall = [row["delta_recall_abs"] for row in rows]
    delta_precision = [row["delta_precision_abs"] for row in rows]
    rho_recall = spearmanr(drift, delta_recall)
    rho_precision = spearmanr(drift, delta_precision)
    return {
        "selection": {
            "cohort": "rq8_docred_n4000",
            "source": str(DEFAULT_INDEX),
            "selection_is_label_blind": True,
        },
        "n_pairs": len(rows),
        "query_divergence_threshold_abs_mean_delta_f1": 0.05,
        "query_divergence_base_rate": (
            sum(
                row["mean_delta_f1_abs"] > 0.05
                for row in rows
            )
            / len(rows)
        ),
        "spearman": {
            "graph_drift_vs_abs_delta_recall": {
                "rho": float(rho_recall.statistic),
                "p_value": float(rho_recall.pvalue),
            },
            "graph_drift_vs_abs_delta_precision": {
                "rho": float(rho_precision.statistic),
                "p_value": float(rho_precision.pvalue),
            },
        },
    }


def k1_contrast(conn: sqlite3.Connection) -> dict:
    edge_rows = load_edge_rows(conn)
    gold = load_gold(conn)
    schema_json = conn.execute(
        "SELECT relation_types_json FROM schemas WHERE schema_id='docred_full'"
    ).fetchone()
    if schema_json is None:
        raise RuntimeError("base schema docred_full not found")
    base_relation_ids = {
        row["id"] for row in json.loads(schema_json[0])
    }

    pairs = conn.execute(
        """
        SELECT cr.run_id, cr.base_event_id, cr.cf_event_id, cr.document_id
        FROM counterfactual_runs cr
        JOIN intervention_candidates ic
          ON cr.intervention_id = ic.intervention_id
        WHERE cr.status='ok'
          AND cr.cf_event_id IS NOT NULL
          AND ic.cause_family='schema'
          AND ic.semantic_class='presentation'
          AND (
            ic.description LIKE '%rename%'
            OR ic.description LIKE '%reorder%'
          )
        """
    ).fetchall()

    rows = []
    for run_id, base_event, cf_event, doc in pairs:
        base_rows = edge_rows[base_event]
        cf_rows = edge_rows[cf_event]
        base_graph = set(_project(_to_triples(base_rows), base_relation_ids))
        cf_graph = set(_project(_to_triples(cf_rows), base_relation_ids))
        gold_graph = gold[doc]
        recall_base, precision_base = extraction_quality(
            base_graph, gold_graph
        )
        recall_cf, precision_cf = extraction_quality(cf_graph, gold_graph)
        overlap = edge_jaccard(
            base_rows,
            cf_rows,
            base_relation_ids=base_relation_ids,
        )
        rows.append({
            "run_id": run_id,
            "document_id": doc,
            "edge_overlap": overlap,
            "violated": overlap < 0.85,
            "abs_delta_recall": abs(recall_base - recall_cf),
            "abs_delta_precision": abs(precision_base - precision_cf),
        })

    def summarize(violated: bool) -> dict:
        selected = [row for row in rows if row["violated"] == violated]
        return {
            "n": len(selected),
            "mean_abs_delta_recall": mean(
                row["abs_delta_recall"] for row in selected
            ),
            "mean_abs_delta_precision": mean(
                row["abs_delta_precision"] for row in selected
            ),
        }

    return {
        "scope": "K1 schema rename/reorder",
        "overlap_threshold": 0.85,
        "relation_projection": "to docred_full base relation IDs",
        "n_pairs": len(rows),
        "violating": summarize(True),
        "satisfied": summarize(False),
        "per_pair": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    registered_rows = load_rq8_pairs(ROOT, DEFAULT_RUN)
    index = load_artifact_index(ROOT)
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        result = {
            "artifact_type": "graphguard.rq8_drift_accuracy",
            "artifact_version": 1,
            "run": DEFAULT_RUN,
            "sources": {
                "evidence_index": {
                    "path": str(DEFAULT_INDEX),
                    "sha256": sha256_file(ROOT / DEFAULT_INDEX),
                },
                "downstream_artifact": {
                    "sha256": index["entries"][
                        f"downstream:{DEFAULT_RUN}"
                    ]["raw_sha256"],
                },
                "source_database": {
                    "path": args.db,
                    "sha256": sha256_file(args.db),
                },
            },
            "query_population": query_population(registered_rows),
            "k1_contrast": k1_contrast(conn),
        }
    finally:
        conn.close()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
