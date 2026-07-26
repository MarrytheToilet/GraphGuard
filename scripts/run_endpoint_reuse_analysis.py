#!/usr/bin/env python3
"""Measure endpoint-union savings on the materialized contract workload.

The no-reuse baseline materializes both endpoints independently for every
contract-pair evaluation.  The endpoint-union plan materializes each extraction
event once and lets all graph/query contracts consume the cached view.

The analysis is offline: it reads the lineage databases and issues no LLM calls.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.contracts import REGISTRY
from graphguard.contracts.runner import (
    _base_relation_ids_for,
    _edges,
    _iter_pairs,
    _query_similarity,
)


DEFAULT_RUNS = {
    "docred__deepseek-v4-flash__300d":
        "data/processed/runs/docred__deepseek-v4-flash__300d/"
        "docred__deepseek-v4-flash__300d.db",
    "redocred__deepseek-v4-flash__300d":
        "data/processed/runs/redocred__deepseek-v4-flash__300d/"
        "redocred__deepseek-v4-flash__300d.db",
    "scierc__deepseek-v4-flash__100d":
        "data/processed/runs/scierc__deepseek-v4-flash__100d/"
        "scierc__deepseek-v4-flash__100d.db",
    "cdr__deepseek-v4-flash__300d":
        "data/processed/runs/cdr__deepseek-v4-flash__300d/"
        "cdr__deepseek-v4-flash__300d.db",
}


def _parse_run(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--run must have the form NAME=DB_PATH")
    name, path = value.split("=", 1)
    if not name or not path:
        raise argparse.ArgumentTypeError("--run must have the form NAME=DB_PATH")
    return name, Path(path)


def _open_read_only(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(resolved)
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _reported_contract_counts(run_name: str, reports_root: Path) -> dict[str, int]:
    path = reports_root / run_name / "eval" / "contracts.json"
    if not path.exists():
        return {}
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        row["contract_id"]: int(row["n_pairs"])
        for row in report["contracts"]
    }


def analyze_run(
    run_name: str,
    db_path: Path,
    *,
    reports_root: Path,
) -> dict:
    resolved_db = db_path.resolve()
    try:
        reported_db = str(resolved_db.relative_to(ROOT))
    except ValueError:
        reported_db = str(resolved_db)
    conn = _open_read_only(db_path)
    try:
        pairs = list(_iter_pairs(conn))
        token_volume = {
            row["event_id"]: int(row["token_input"] or 0)
            + int(row["token_output"] or 0)
            for row in conn.execute(
                "SELECT event_id, token_input, token_output FROM extraction_events"
            )
        }

        @lru_cache(maxsize=None)
        def edges(event_id: str):
            return tuple(_edges(conn, event_id))

        requests: list[tuple[str, str, str]] = []
        per_contract: Counter[str] = Counter()
        for (
            _intervention_id,
            base_event,
            cf_event,
            family,
            semantic_class,
            operator,
            _document_id,
            description,
        ) in pairs:
            for contract in REGISTRY.values():
                if not contract.applies(
                    family, semantic_class, operator, description=description
                ):
                    continue
                if contract.query_scoped:
                    similarity = _query_similarity(
                        edges(base_event),
                        edges(cf_event),
                        base_relation_ids=_base_relation_ids_for(conn, base_event),
                        query_id=contract.query_id or "D3",
                    )
                    if similarity is None:
                        continue
                requests.append((contract.id, base_event, cf_event))
                per_contract[contract.id] += 1

        reported = _reported_contract_counts(run_name, reports_root)
        if reported:
            observed = {
                contract_id: per_contract.get(contract_id, 0)
                for contract_id in reported
            }
            if observed != reported:
                raise RuntimeError(
                    f"{run_name}: pair counts disagree with contracts.json: "
                    f"observed={observed}, reported={reported}"
                )

        endpoint_requests = [
            endpoint
            for _contract_id, base_event, cf_event in requests
            for endpoint in (base_event, cf_event)
        ]
        unique_endpoints = set(endpoint_requests)
        cf_requests = [cf_event for _, _, cf_event in requests]
        unique_cf_endpoints = set(cf_requests)

        missing = sorted(unique_endpoints - token_volume.keys())
        if missing:
            raise RuntimeError(
                f"{run_name}: {len(missing)} endpoints lack extraction token records"
            )

        naive_tokens = sum(token_volume[event] for event in endpoint_requests)
        union_tokens = sum(token_volume[event] for event in unique_endpoints)
        cf_naive_tokens = sum(token_volume[event] for event in cf_requests)
        cf_union_tokens = sum(token_volume[event] for event in unique_cf_endpoints)

        pair_evaluations = len(requests)
        naive_calls = len(endpoint_requests)
        union_calls = len(unique_endpoints)
        return {
            "run": run_name,
            "db": reported_db,
            "pair_evaluations": pair_evaluations,
            "per_contract_pair_evaluations": dict(sorted(per_contract.items())),
            "contract_counts_match_report": bool(reported),
            "full_endpoint_union": {
                "naive_endpoint_materializations": naive_calls,
                "unique_endpoint_materializations": union_calls,
                "call_savings_factor": naive_calls / union_calls,
                "naive_token_volume": naive_tokens,
                "union_token_volume": union_tokens,
                "token_savings_factor": naive_tokens / union_tokens,
            },
            "counterfactual_only": {
                "naive_counterfactual_materializations": len(cf_requests),
                "unique_counterfactual_materializations": len(unique_cf_endpoints),
                "call_savings_factor": len(cf_requests) / len(unique_cf_endpoints),
                "naive_token_volume": cf_naive_tokens,
                "union_token_volume": cf_union_tokens,
                "token_savings_factor": cf_naive_tokens / cf_union_tokens,
            },
        }
    finally:
        conn.close()


def _range(rows: list[dict], section: str, field: str) -> dict[str, float]:
    values = [float(row[section][field]) for row in rows]
    return {"min": min(values), "max": max(values)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        action="append",
        type=_parse_run,
        default=None,
        help="run and lineage DB as NAME=DB_PATH; repeat for multiple runs",
    )
    parser.add_argument("--reports-root", default="reports/runs")
    parser.add_argument(
        "--out", default="reports/cross_run/endpoint_reuse.json"
    )
    args = parser.parse_args()

    runs = dict(args.run) if args.run else {
        name: Path(path) for name, path in DEFAULT_RUNS.items()
    }
    reports_root = Path(args.reports_root)
    rows = [
        analyze_run(name, path, reports_root=reports_root)
        for name, path in runs.items()
    ]
    report = {
        "definition": {
            "baseline": (
                "materialize both endpoints independently for every "
                "contract-pair evaluation"
            ),
            "optimized": (
                "materialize the union of unique extraction-event endpoints once"
            ),
            "token_volume": "token_input + token_output",
            "llm_calls": 0,
        },
        "runs": rows,
        "summary": {
            "n_runs": len(rows),
            "full_call_savings_factor": _range(
                rows, "full_endpoint_union", "call_savings_factor"
            ),
            "full_token_savings_factor": _range(
                rows, "full_endpoint_union", "token_savings_factor"
            ),
            "counterfactual_call_savings_factor": _range(
                rows, "counterfactual_only", "call_savings_factor"
            ),
            "counterfactual_token_savings_factor": _range(
                rows, "counterfactual_only", "token_savings_factor"
            ),
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[endpoint-reuse] runs={len(rows)} out={out}")
    for row in rows:
        full = row["full_endpoint_union"]
        cf = row["counterfactual_only"]
        print(
            f"  {row['run']}: full={full['call_savings_factor']:.3f}x calls, "
            f"{full['token_savings_factor']:.3f}x tokens; "
            f"cf-only={cf['call_savings_factor']:.3f}x calls, "
            f"{cf['token_savings_factor']:.3f}x tokens"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
