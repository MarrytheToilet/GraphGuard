"""Edge-matching validation (README §11.3).

Samples a random subset of ``edge_outcomes`` (with their base + cf edges and
cited evidence sentence text) and dumps them to a JSON file for manual
inspection. Also computes a deterministic 'auto-precision' upper-bound under
the assumption that subject_id/object_id matches imply correctness.

This defends against the reviewer attack: "your stability metrics depend on a
brittle string matcher". It lets us put a number on matching precision, and
flags candidates a human can adjudicate.

Usage:
    python scripts/run_matching_validation.py \
        --db data/processed/runs/<run>/<run>.db \
        --out reports/runs/<run>/matching_validation.json --n 200
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.db.database import open_db


def _outcome_rows(conn, n: int, seed: int):
    rows = list(conn.execute("""
        SELECT eo.outcome_id, eo.outcome_type,
               eo.original_edge_id, eo.matched_edge_id AS cf_edge_id,
               eb.subject_name AS b_subj, eb.relation AS b_rel, eb.object_name AS b_obj,
               eb.subject_entity_id AS b_sid, eb.object_entity_id AS b_oid,
               eb.evidence_sentence_ids_json AS b_ev,
               eb.document_id AS doc_id,
               ec.subject_name AS c_subj, ec.relation AS c_rel, ec.object_name AS c_obj,
               ec.subject_entity_id AS c_sid, ec.object_entity_id AS c_oid,
               ic.target_type, ic.target_id AS target_value, ic.operator
        FROM edge_outcomes eo
        JOIN extracted_edges eb ON eb.edge_id = eo.original_edge_id
        LEFT JOIN extracted_edges ec ON ec.edge_id = eo.matched_edge_id
        JOIN counterfactual_runs cr ON cr.run_id = eo.run_id
        JOIN intervention_candidates ic ON ic.intervention_id = cr.intervention_id
    """))
    rng = random.Random(seed)
    rng.shuffle(rows)
    return rows[:n]


def _evidence_text(conn, doc_id: str, json_ids: str | None) -> list[str]:
    try:
        ids = json.loads(json_ids) if json_ids else []
    except Exception:
        ids = []
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    return [
        r["text"] for r in conn.execute(
            f"SELECT text FROM sentences WHERE document_id = ? AND sentence_id IN ({placeholders})",
            (doc_id, *ids),
        )
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    conn = open_db(args.db)
    rows = _outcome_rows(conn, args.n, args.seed)

    samples = []
    auto = {"id_match_same_outcome": 0, "id_match_disagree": 0, "no_id_overlap": 0}
    for r in rows:
        ev = _evidence_text(conn, r["doc_id"], r["b_ev"])
        same_subj_id = r["b_sid"] is not None and r["b_sid"] == r["c_sid"]
        same_obj_id = r["b_oid"] is not None and r["b_oid"] == r["c_oid"]
        ot = r["outcome_type"]
        if r["c_sid"] is None and r["c_oid"] is None:
            auto["no_id_overlap"] += 1
        elif same_subj_id and same_obj_id:
            if ot in ("EXACT_SAME", "TYPE_FLIP"):
                auto["id_match_same_outcome"] += 1
            else:
                auto["id_match_disagree"] += 1
        else:
            auto["no_id_overlap"] += 1
        samples.append({
            "outcome_id": r["outcome_id"],
            "outcome_type": ot,
            "intervention": f'{r["target_type"]}:{r["target_value"]}:{r["operator"]}',
            "base":  {"subj": r["b_subj"], "rel": r["b_rel"], "obj": r["b_obj"],
                      "subj_id": r["b_sid"], "obj_id": r["b_oid"]},
            "cf":    {"subj": r["c_subj"], "rel": r["c_rel"], "obj": r["c_obj"],
                      "subj_id": r["c_sid"], "obj_id": r["c_oid"]} if r["c_subj"] else None,
            "evidence": ev,
            "reviewer_label": None,
            "reviewer_note": "",
        })

    n = max(1, len(samples))
    summary = {
        "n_sampled": len(samples),
        "auto_check": auto,
        "auto_precision_upper_bound":
            round((auto["id_match_same_outcome"] + auto["id_match_disagree"])
                  / n, 4),
    }
    out = {"summary": summary, "samples": samples}
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
