#!/usr/bin/env python3
"""Audit the non-identifier portion of the 200-sample matcher validation.

The shipped validation (run_matching_validation.py) auto-verifies the
identifier-exact matches (64% of samples on the primary run, 98.4%
agreement). This script audits the remaining, harder outcomes against the
full counterfactual edge set of each sample's run:

  * DISAPPEARED — the matcher asserts *no* counterfactual edge corresponds
    to the base edge. We re-scan every edge of the counterfactual event and
    flag any candidate on the same entity pair (identifier-exact, then
    case-insensitive surface, then containment, in the matcher's own
    order). A disappeared verdict passes iff no candidate exists.
  * SUBJECT_FLIP / OBJECT_FLIP / TYPE_FLIP / AMBIGUOUS matched without an
    identifier-exact pair — the match anchors on shared entities (and, for
    flips, the preserved relation). A flip match passes iff its anchor
    entities agree by identifier; anchors that agree only by surface or
    containment are listed for manual adjudication with evidence text.

Everything is recomputed from the run database; no LLM calls.

Usage:
    python scripts/run_matching_validation_hard.py \
        --run docred__deepseek-v4-flash__300d
Writes reports/runs/<run>/matching_validation_hard.json.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def surf_eq(a: str, b: str) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def surf_contain(a: str, b: str) -> bool:
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    return bool(a and b) and (a in b or b in a)


def pair_match_level(base, cand):
    """Return the strongest level at which cand's endpoints match base's."""
    if (base["subj_id"] and cand["subj_id"] and base["obj_id"] and cand["obj_id"]
            and base["subj_id"] == cand["subj_id"] and base["obj_id"] == cand["obj_id"]):
        return "id"
    if surf_eq(base["subj"], cand["subj"]) and surf_eq(base["obj"], cand["obj"]):
        return "surface"
    if surf_contain(base["subj"], cand["subj"]) and surf_contain(base["obj"], cand["obj"]):
        return "containment"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="docred__deepseek-v4-flash__300d")
    args = ap.parse_args()

    run_dir = ROOT / "data/processed/runs" / args.run
    db = sqlite3.connect(str(run_dir / f"{args.run}.db"))
    db.row_factory = sqlite3.Row
    val = json.loads((run_dir / "reports/matching_validation.json").read_text())

    def edge_row(edge_id):
        r = db.execute("SELECT * FROM extracted_edges WHERE edge_id=?", (edge_id,)).fetchone()
        return None if r is None else {
            "edge_id": r["edge_id"], "subj": r["subject_name"], "rel": r["relation"],
            "obj": r["object_name"], "subj_id": r["subject_entity_id"],
            "obj_id": r["object_entity_id"],
        }

    def cf_edges_for_outcome(outcome_id):
        r = db.execute("""
            SELECT cr.cf_event_id AS ev FROM edge_outcomes eo
            JOIN counterfactual_runs cr ON cr.run_id = eo.run_id
            WHERE eo.outcome_id=?""", (outcome_id,)).fetchone()
        if r is None or r["ev"] is None:
            return []
        rows = db.execute("SELECT * FROM extracted_edges WHERE event_id=?", (r["ev"],)).fetchall()
        return [{"edge_id": x["edge_id"], "subj": x["subject_name"], "rel": x["relation"],
                 "obj": x["object_name"], "subj_id": x["subject_entity_id"],
                 "obj_id": x["object_entity_id"]} for x in rows]

    report = {"run": args.run, "disappeared": {"n": 0, "pass": 0, "candidates": []},
              "flip_or_ambiguous": {"n": 0, "id_anchor": 0, "surface_anchor": 0,
                                    "containment_anchor": 0, "review": []},
              "id_exact": 0, "id_disagree": 0}

    for s in val["samples"]:
        base_row = db.execute(
            "SELECT original_edge_id, matched_edge_id FROM edge_outcomes WHERE outcome_id=?",
            (s["outcome_id"],)).fetchone()
        base = edge_row(base_row["original_edge_id"])
        cf = edge_row(base_row["matched_edge_id"]) if base_row["matched_edge_id"] else None

        if cf is not None and pair_match_level(base, cf) == "id":
            report["id_exact"] += 1
            continue

        if s["outcome_type"] == "DISAPPEARED" or cf is None:
            report["disappeared"]["n"] += 1
            cands = []
            for c in cf_edges_for_outcome(s["outcome_id"]):
                lvl = pair_match_level(base, c)
                if lvl:
                    cands.append({"level": lvl, **c})
            if not cands:
                report["disappeared"]["pass"] += 1
            else:
                report["disappeared"]["candidates"].append({
                    "outcome_id": s["outcome_id"], "base": s["base"],
                    "evidence": s.get("evidence", []), "missed": cands})
            continue

        # matched, but not identifier-exact on both endpoints
        report["flip_or_ambiguous"]["n"] += 1
        lvl = pair_match_level(base, cf)
        # flips share one endpoint by design; check the anchor endpoint(s)
        subj_anchor = ("id" if base["subj_id"] and base["subj_id"] == cf["subj_id"]
                       else "surface" if surf_eq(base["subj"], cf["subj"])
                       else "containment" if surf_contain(base["subj"], cf["subj"]) else None)
        obj_anchor = ("id" if base["obj_id"] and base["obj_id"] == cf["obj_id"]
                      else "surface" if surf_eq(base["obj"], cf["obj"])
                      else "containment" if surf_contain(base["obj"], cf["obj"]) else None)
        anchors = [a for a in (subj_anchor, obj_anchor) if a]
        if anchors and all(a == "id" for a in anchors) and len(anchors) == 2:
            report["flip_or_ambiguous"]["id_anchor"] += 1
        elif anchors and "containment" not in anchors:
            report["flip_or_ambiguous"]["surface_anchor"] += 1
            report["flip_or_ambiguous"]["review"].append({
                "outcome_id": s["outcome_id"], "type": s["outcome_type"],
                "base": s["base"], "cf": s["cf"], "evidence": s.get("evidence", []),
                "anchor": [subj_anchor, obj_anchor]})
        else:
            report["flip_or_ambiguous"]["containment_anchor"] += 1
            report["flip_or_ambiguous"]["review"].append({
                "outcome_id": s["outcome_id"], "type": s["outcome_type"],
                "base": s["base"], "cf": s["cf"], "evidence": s.get("evidence", []),
                "anchor": [subj_anchor, obj_anchor]})

    out = run_dir / "reports/matching_validation_hard.json"
    out.write_text(json.dumps(report, indent=2))
    d = report["disappeared"]; f = report["flip_or_ambiguous"]
    print(f"id-exact matched pairs: {report['id_exact']}")
    print(f"disappeared: {d['n']}  pass(no same-pair candidate): {d['pass']}  "
          f"flagged: {len(d['candidates'])}")
    print(f"flip/ambiguous non-ID: {f['n']}  id-anchor: {f['id_anchor']}  "
          f"surface: {f['surface_anchor']}  containment: {f['containment_anchor']}  "
          f"for review: {len(f['review'])}")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
