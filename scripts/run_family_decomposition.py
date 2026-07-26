#!/usr/bin/env python3
"""Per-family drift decomposition (PVLDB revision, Rev8-E2.1 / E2.2).

Extends the repeated-extraction analysis (paper Table tab_e0: edge overlap,
type agreement, disappearing / new edge rates) to every perturbation family,
on every ok counterfactual pair of a run. Also records label-erased
(entity-pair) overlap and per-event graph size, which quantify how much of
the drift budget lives in the relation-label dimension --- the comparison
that explains BC5CDR's low violation rates (single CID relation type,
MeSH-clustered entities).

Writes reports/cross_run/family_decomp_<run>.json.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.contracts import metrics as M  # noqa: E402

MAIN_RUNS = [
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
]

OUT_DIR = ROOT / "reports" / "cross_run"


def family_key(fam: str, sem_class: str) -> str:
    """Split the schema family into presentation vs semantic sub-families."""
    if fam == "schema":
        return "schema-pres" if sem_class == "presentation" else "schema-sem"
    return fam


def pair_stats(bt: set, ct: set) -> dict:
    """E0-style decomposition on canonical triples."""
    inter = bt & ct
    union = bt | ct
    overlap = len(inter) / len(union) if union else 1.0
    b_pairs = {(s, o): r for s, r, o in bt}
    c_pairs = {(s, o): r for s, r, o in ct}
    common = set(b_pairs) & set(c_pairs)
    pair_union = set(b_pairs) | set(c_pairs)
    pair_overlap = len(common) / len(pair_union) if pair_union else 1.0
    type_agree = (sum(1 for so in common if b_pairs[so] == c_pairs[so]) / len(common)) if common else 1.0
    disappear = len(bt - ct) / len(bt) if bt else 0.0
    new = len(ct - bt) / len(bt) if bt else 0.0
    return {
        "overlap": overlap, "pair_overlap": pair_overlap,
        "type_agree": type_agree, "disappear": disappear, "new": new,
        "n_base": len(bt),
    }


def analyze_run(run: str) -> dict | None:
    db = ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
    if not db.exists():
        print(f"[skip] {run}: no db")
        return None
    con = sqlite3.connect(db)
    cur = con.cursor()

    raw_edges = defaultdict(list)
    for eid, sid, sn, r, oid, on in cur.execute(
        "SELECT event_id, subject_entity_id, subject_name, relation, "
        "object_entity_id, object_name FROM extracted_edges"):
        raw_edges[eid].append({
            "subject_entity_id": sid, "subject_name": sn, "relation": r,
            "object_entity_id": oid, "object_name": on,
        })
    ev_schema = dict(cur.execute("SELECT event_id, schema_id FROM extraction_events"))
    schemas = {sid: {r["id"] for r in json.loads(rj)} for sid, rj in cur.execute(
        "SELECT schema_id, relation_types_json FROM schemas")}
    iv = {ivid: (fam, sc) for ivid, fam, sc in cur.execute(
        "SELECT intervention_id, cause_family, semantic_class FROM intervention_candidates")}

    by_family = defaultdict(list)
    for run_id, base_ev, cf_ev, ivid in cur.execute(
        "SELECT run_id, base_event_id, cf_event_id, intervention_id "
        "FROM counterfactual_runs WHERE status='ok' AND cf_event_id IS NOT NULL AND cf_event_id<>''"):
        fam, sem_class = iv.get(ivid, ("unknown", "unknown"))
        base_rel_ids = schemas.get(ev_schema.get(base_ev)) or None
        bt, ct = M.paired_triples(
            raw_edges.get(base_ev, []), raw_edges.get(cf_ev, []),
            base_relation_ids=base_rel_ids,
        )
        bt, ct = set(bt), set(ct)
        if not bt and not ct:
            continue
        by_family[family_key(fam, sem_class)].append(pair_stats(bt, ct))

    keys = ["overlap", "pair_overlap", "type_agree", "disappear", "new", "n_base"]
    summary = {}
    for fam, rows in sorted(by_family.items()):
        summary[fam] = {"n": len(rows)}
        for k in keys:
            summary[fam][k] = statistics.mean(r[k] for r in rows)

    out = {"run": run, "summary": summary}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"family_decomp_{run}.json"
    out_path.write_text(json.dumps(out, indent=1))
    print(f"[done] {run} -> {out_path}")
    print(f"  {'family':<13} {'n':>6} {'overlap':>8} {'pairJ':>7} {'typeAgr':>8} {'disap':>6} {'new':>6} {'|G|':>6}")
    for fam, s in summary.items():
        print(f"  {fam:<13} {s['n']:>6} {s['overlap']:>8.3f} {s['pair_overlap']:>7.3f} "
              f"{s['type_agree']:>8.3f} {s['disappear']:>6.3f} {s['new']:>6.3f} {s['n_base']:>6.1f}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=MAIN_RUNS)
    args = ap.parse_args()
    for run in args.runs:
        analyze_run(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
