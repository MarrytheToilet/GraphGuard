#!/usr/bin/env python3
"""Reproduce the DocRED drift-versus-accuracy statistics in Sec. 6.2.

The 4,000-pair population follows run_e2e_qa.py exactly: seed 0, at most
4,000 successful counterfactual runs, and documents with a non-empty
gold-derived query workload. Its label is an absolute query-utility change,
not the directional regression label used by the release-gate experiment.
K1 uses every successful schema rename/reorder pair and the same relation
projection and threshold as the contract runtime.
"""
from __future__ import annotations

import argparse
import json
import random
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
from graphguard.qa import (
    build_queries,
    execute,
    f1,
    graph_jaccard,
    load_data,
)


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


def query_population(
    conn: sqlite3.Connection,
    *,
    max_runs: int,
    seed: int,
) -> dict:
    edges, gold, runs = load_data(conn)
    rng = random.Random(seed)
    if max_runs and len(runs) > max_runs:
        runs = rng.sample(runs, max_runs)

    rows = []
    for _, base_event, cf_event, doc, _, _ in runs:
        if (
            not cf_event
            or base_event not in edges
            or cf_event not in edges
        ):
            continue
        queries = build_queries(gold.get(doc, set()))
        if not queries:
            continue
        base_graph = edges[base_event]
        cf_graph = edges[cf_event]
        gold_graph = gold.get(doc, set())
        graph_drift = 1.0 - graph_jaccard(base_graph, cf_graph)
        recall_base, precision_base = extraction_quality(
            base_graph, gold_graph
        )
        recall_cf, precision_cf = extraction_quality(cf_graph, gold_graph)
        delta_f1 = [
            abs(
                f1(execute(base_graph, query), query[1]["gold"])
                - f1(execute(cf_graph, query), query[1]["gold"])
            )
            for query in queries
        ]
        rows.append({
            "graph_drift": graph_drift,
            "delta_recall": abs(recall_base - recall_cf),
            "delta_precision": abs(precision_base - precision_cf),
            "mean_delta_f1": mean(delta_f1),
        })

    drift = [row["graph_drift"] for row in rows]
    delta_recall = [row["delta_recall"] for row in rows]
    delta_precision = [row["delta_precision"] for row in rows]
    rho_recall = spearmanr(drift, delta_recall)
    rho_precision = spearmanr(drift, delta_precision)
    return {
        "selection": {
            "seed": seed,
            "max_runs_before_filtering": max_runs,
            "requires_nonempty_gold_query_workload": True,
        },
        "n_pairs": len(rows),
        "query_divergence_threshold_abs_mean_delta_f1": 0.05,
        "query_divergence_base_rate": (
            sum(row["mean_delta_f1"] > 0.05 for row in rows) / len(rows)
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
        SELECT cr.base_event_id, cr.cf_event_id, cr.document_id
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
    for base_event, cf_event, doc in pairs:
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
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--max-runs", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    result = {
        "run": DEFAULT_RUN,
        "query_population": query_population(
            conn,
            max_runs=args.max_runs,
            seed=args.seed,
        ),
        "k1_contrast": k1_contrast(conn),
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
