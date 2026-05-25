#!/usr/bin/env python3
"""CLI for the §9 reliability query interface.

Examples:
  python scripts/query.py why_edge --edge-id <eid> --top 5
  python scripts/query.py why_type --edge-id <eid> --top 5
  python scripts/query.py fragile --threshold 0.5 --limit 20
  python scripts/query.py schema_sensitive --threshold 0.5
  python scripts/query.py prompt_induced --threshold 0.5
  python scripts/query.py audit --k 20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.db.database import open_db
from graphguard import queries as Q


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("op", choices=["why_edge", "why_type", "fragile",
                                   "schema_sensitive", "prompt_induced", "audit"])
    ap.add_argument("--db", default=None)
    ap.add_argument("--docred-config", default="configs/docred.yaml")
    ap.add_argument("--edge-id")
    ap.add_argument("--document-id")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None, help="Optional JSON output path")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.docred_config).read_text(encoding="utf-8"))
    db_path = args.db or cfg["storage"]["db_path"]
    conn = open_db(db_path)

    if args.op in ("why_edge", "why_type"):
        if not args.edge_id:
            ap.error("--edge-id required for why_edge / why_type")
        fn = Q.why_edge if args.op == "why_edge" else Q.why_type
        causes = fn(conn, args.edge_id, top_k=args.top)
        out = [c.to_dict() for c in causes]
        for c in causes:
            print(f"  effect={c.effect:.2f} {c.variable_type:<14} {c.variable_id:<32} "
                  f"op={c.operator:<8} :: {c.interpretation}")
    elif args.op == "fragile":
        edges = Q.find_fragile_edges(conn, document_id=args.document_id,
                                     threshold=args.threshold, limit=args.limit)
        out = [e.to_dict() for e in edges]
        for e in edges:
            print(f"  stab={e.stability_score:.2f} risk={e.risk_score:.2f} "
                  f"  ({e.subject_name}) -[{e.relation}]-> ({e.object_name})  "
                  f"  {e.edge_id}")
    elif args.op == "schema_sensitive":
        edges = Q.find_schema_sensitive_edges(conn, threshold=args.threshold, limit=args.limit)
        out = [e.to_dict() for e in edges]
        for e in edges:
            print(f"  schema_s={e.schema_sensitivity:.2f} risk={e.risk_score:.2f} "
                  f"  ({e.subject_name}) -[{e.relation}]-> ({e.object_name})")
    elif args.op == "prompt_induced":
        edges = Q.find_prompt_induced_edges(conn, threshold=args.threshold, limit=args.limit)
        out = [e.to_dict() for e in edges]
        for e in edges:
            print(f"  prompt_s={e.prompt_sensitivity:.2f} risk={e.risk_score:.2f} "
                  f"  ({e.subject_name}) -[{e.relation}]-> ({e.object_name})")
    elif args.op == "audit":
        edges = Q.rank_edges_for_audit(conn, k=args.k)
        out = [e.to_dict() for e in edges]
        for e in edges:
            print(f"  risk={(e.risk_score or 0):+.2f} stab={(e.stability_score or 0):.2f} "
                  f"  ({e.subject_name}) -[{e.relation}]-> ({e.object_name})")
    else:
        ap.error("unknown op")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[done] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
