"""Comprehensive correctness audit for the contracts pipeline.

Constructs synthetic in-memory data so we can verify every step:
- relation back-projection (rename, identity, unknown, coarse)
- edge_jaccard / relation_distribution_l1 / type_flip_rate on hand-crafted pairs
- _query_q3 with back-projection
- cf_event_id backfill on a synthetic DB with intentional cross-pair traps
- _iter_pairs prefers cf_event_id over the (correct) fallback over the (legacy) heuristic
- contract Registry metric_fn signatures all accept base_relation_ids
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from graphguard.contracts import metrics as M
from graphguard.contracts.runner import (
    _iter_pairs, _query_q3, _project_triples, _base_relation_ids_for,
    _BASE_REL_CACHE,
)
from graphguard.contracts.registry import REGISTRY
from graphguard.matching.relation_normalizer import project_to_base
from graphguard.db.database import open_db


# helper to build edge dicts matching what the runner sees
def E(s, r, o):
    return {"subject_name": s, "object_name": o, "relation": r,
            "subject_entity_id": s, "object_entity_id": o}


DOCRED_IDS = {"P17","P19","P20","P26","P27","P40","P50","P54","P57","P69",
              "P108","P131","P150","P159","P161","P175","P194","P361","P463",
              "P495","P527","P569","P570","P577","P580","P582","P1336"}


def must(cond, msg):
    if not cond:
        print(f"  FAIL: {msg}")
        return False
    print(f"  ok:   {msg}")
    return True


def t1_identical():
    print("\n[T1] identical edges -> jaccard=1")
    a = [E("X","P19","Y")]
    b = [E("X","P19","Y")]
    ok = True
    ok &= must(M.edge_jaccard(a, b) == 1.0, "no projection")
    ok &= must(M.edge_jaccard(a, b, base_relation_ids=DOCRED_IDS) == 1.0, "with projection")
    return ok


def t2_rename_equivalent():
    print("\n[T2] rename only (token-equivalent) -> jaccard=1")
    base = [E("X","P19","Y"), E("X","P159","Z")]
    cf   = [E("X","place_of_birth","Y"), E("X","headquarters_location","Z")]
    # without projection: would fail
    no_proj = M.edge_jaccard(base, cf)
    with_proj = M.edge_jaccard(base, cf, base_relation_ids=DOCRED_IDS)
    print(f"   no_proj={no_proj}  with_proj={with_proj}")
    ok = True
    ok &= must(no_proj == 0.0, "without projection, tokens differ")
    ok &= must(with_proj == 1.0, "with projection, jaccard=1.0")
    # type_flip should also be 0
    flip = M.type_flip_rate(base, cf, base_relation_ids=DOCRED_IDS)
    ok &= must(flip == 0.0, f"type_flip_rate=0 (got {flip})")
    return ok


def t3_rename_with_real_change():
    print("\n[T3] rename + one real relation flip -> partial violation")
    # base: P19, P159
    # cf:   place_of_birth (=P19, matches), place_of_death (=P20, real change for same s/o)
    base = [E("X","P19","Y"), E("X","P159","Z")]
    cf   = [E("X","place_of_birth","Y"), E("X","place_of_death","Z")]
    j = M.edge_jaccard(base, cf, base_relation_ids=DOCRED_IDS)
    flip = M.type_flip_rate(base, cf, base_relation_ids=DOCRED_IDS)
    print(f"   jaccard={j} flip={flip}")
    ok = True
    # 1 of 2 base triples matches; 1 cf triple is new; union=3, inter=1
    ok &= must(abs(j - 1/3) < 1e-9, f"jaccard=1/3 (got {j})")
    # both s/o pairs overlap; one has relation flipped (X,Z): P159 vs P20
    ok &= must(abs(flip - 0.5) < 1e-9, f"flip=0.5 (got {flip})")
    return ok


def t4_reorder_storage():
    print("\n[T4] same triples, different storage order -> jaccard=1")
    base = [E("X","P19","Y"), E("X","P159","Z"), E("A","P17","B")]
    cf   = list(reversed(base))
    ok = must(M.edge_jaccard(base, cf, base_relation_ids=DOCRED_IDS) == 1.0,
              "shuffled list still matches as set")
    return ok


def t5_coarse_bucket():
    print("\n[T5] declared coarse bucket matches a base relation member")
    # P17 in base, 'loc_admin' (a coarse bucket id) in cf. project_to_base
    # returns None -> caller keeps 'loc_admin' -> mismatch.
    from graphguard.interventions.schema import COARSE_GROUPS
    bucket = next(iter(COARSE_GROUPS))
    member = COARSE_GROUPS[bucket][0]
    print(f"   bucket={bucket!r}  member={member!r}")
    base = [E("X", member, "Y")]
    cf   = [E("X", bucket, "Y")]
    proj = project_to_base(bucket, base_relation_ids=DOCRED_IDS)
    print(f"   project_to_base({bucket!r}) -> {proj!r}")
    j = M.edge_jaccard(base, cf, base_relation_ids=DOCRED_IDS)
    print(f"   jaccard={j} (expected=1 via declared bucket rule)")
    return must(j == 1.0, "declared coarse relation is canonicalized")


def t6_entity_alias():
    print("\n[T6] distinct explicit identifiers override surface aliases")
    base = [E("United States", "P17", "Y")]
    cf   = [E("the U.S.",     "P17", "Y")]
    j = M.edge_jaccard(base, cf, base_relation_ids=DOCRED_IDS)
    print(f"   jaccard={j} (identifier-first match)")
    return must(j == 0.0, "different explicit identifiers remain distinct")


def t7_cf_event_backfill():
    print("\n[T7] cf_event_id backfill on synthetic DB")
    # Build a tiny DB with two interventions on same doc near in time so the
    # legacy time-window heuristic would mis-pair them. Then run migration and
    # check the backfill picks the right cf event.
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    try:
        conn = open_db(path)
        c = conn
        # FK parents
        for sid in ("docred_full","docred_full_rename","docred_full_reorder"):
            c.execute("INSERT INTO schemas(schema_id, name) VALUES(?,?)",(sid,sid))
        c.execute("INSERT INTO prompts(prompt_id, name) VALUES('base_v1','b')")
        # documents
        c.execute("INSERT INTO documents(document_id, dataset, title) VALUES('doc1','test','t')")
        # base event
        c.execute(
            "INSERT INTO extraction_events(event_id, document_id, prompt_id, schema_id, model_id, temperature, seed, latency_ms) "
            "VALUES('ev-base','doc1','base_v1','docred_full','m1',0.0,0,1)")
        # two cf events with different configs, close in time
        c.execute(
            "INSERT INTO extraction_events(event_id, document_id, prompt_id, schema_id, model_id, temperature, seed, latency_ms, created_at) "
            "VALUES('ev-rename','doc1','base_v1','docred_full_rename','m1',0.0,0,1,'2025-01-01 00:00:01')")
        c.execute(
            "INSERT INTO extraction_events(event_id, document_id, prompt_id, schema_id, model_id, temperature, seed, latency_ms, created_at) "
            "VALUES('ev-reorder','doc1','base_v1','docred_full_reorder','m1',0.0,0,1,'2025-01-01 00:00:02')")
        # two cfrs created earlier than both events (so legacy 'next event' heuristic would mis-pair)
        c.execute(
            "INSERT INTO counterfactual_runs(run_id, intervention_id, base_event_id, document_id, prompt_id, schema_id, model_id, temperature, seed, status, latency_ms, created_at) "
            "VALUES('cfr-1','iv-rename','ev-base','doc1','base_v1','docred_full_rename','m1',0.0,0,'ok',1,'2025-01-01 00:00:00')")
        c.execute(
            "INSERT INTO counterfactual_runs(run_id, intervention_id, base_event_id, document_id, prompt_id, schema_id, model_id, temperature, seed, status, latency_ms, created_at) "
            "VALUES('cfr-2','iv-reorder','ev-base','doc1','base_v1','docred_full_reorder','m1',0.0,0,'ok',1,'2025-01-01 00:00:00')")
        conn.commit()
        # close + reopen to re-run migration (idempotent)
        conn.close()
        conn = open_db(path)
        rows = list(conn.execute("SELECT run_id, schema_id, cf_event_id FROM counterfactual_runs ORDER BY run_id"))
        for r in rows: print(f"   {dict(r)}")
        ok = True
        ok &= must(rows[0]["cf_event_id"] == "ev-rename",
                   f"cfr-1 (rename) paired with ev-rename (got {rows[0]['cf_event_id']})")
        ok &= must(rows[1]["cf_event_id"] == "ev-reorder",
                   f"cfr-2 (reorder) paired with ev-reorder (got {rows[1]['cf_event_id']})")
        conn.close()
        return ok
    finally:
        os.unlink(path)


def t8_iter_pairs():
    print("\n[T8] _iter_pairs prefers cf_event_id; falls back correctly when NULL")
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    try:
        conn = open_db(path)
        for sid in ("docred_full","docred_full_rename"):
            conn.execute("INSERT INTO schemas(schema_id, name) VALUES(?,?)",(sid,sid))
        conn.execute("INSERT INTO prompts(prompt_id, name) VALUES('base_v1','b')")
        conn.execute("INSERT INTO documents(document_id, dataset, title) VALUES('d','t','y')")
        conn.execute("INSERT INTO extraction_events(event_id, document_id, prompt_id, schema_id, model_id, temperature, seed, latency_ms) VALUES('eb','d','base_v1','docred_full','m',0.0,0,1)")
        conn.execute("INSERT INTO extraction_events(event_id, document_id, prompt_id, schema_id, model_id, temperature, seed, latency_ms) VALUES('ec','d','base_v1','docred_full_rename','m',0.0,0,1)")
        # cfr with cf_event_id directly set
        conn.execute("INSERT INTO counterfactual_runs(run_id, intervention_id, base_event_id, cf_event_id, document_id, prompt_id, schema_id, model_id, temperature, seed, status, latency_ms) VALUES('cf','iv','eb','ec','d','base_v1','docred_full_rename','m',0.0,0,'ok',1)")
        conn.commit()
        pairs = list(_iter_pairs(conn))
        print(f"   pairs: {pairs}")
        ok = must(len(pairs) == 1 and pairs[0][1] == "eb" and pairs[0][2] == "ec",
                  "single pair (eb,ec) yielded")
        # Now NULL out cf_event_id, ensure fallback works
        conn.execute("UPDATE counterfactual_runs SET cf_event_id=NULL")
        pairs2 = list(_iter_pairs(conn))
        ok &= must(len(pairs2) == 1 and pairs2[0][2] == "ec",
                   "fallback finds ec via configuration tuple")
        conn.close()
        return ok
    finally:
        os.unlink(path)


def t9_metric_signature():
    print("\n[T9] every registered contract's metric_fn accepts base_relation_ids")
    ok = True
    for cid, c in REGISTRY.items():
        if c.query_scoped:
            continue
        try:
            kwargs = {"base_relation_ids": DOCRED_IDS}
            if c.needs_gold:
                kwargs["gold_edges"] = []
            v = c.metric_fn([], [], **kwargs)
            ok &= must(True, f"{cid}: ok (returned {v})")
        except TypeError as e:
            ok &= must(False, f"{cid}: {e}")
    return ok


def t10_query_q3_rename():
    print("\n[T10] _query_q3 with back-projection -> rename equivalent yields same answer set")
    # Subject 'X' has two distinct relations -> Q3 multi-hop seed.
    base = [E("X","P19","Y"), E("X","P17","Greece")]
    cf   = [E("X","place_of_birth","Y"), E("X","located_in_country","Greece")]
    a = _query_q3(base, base_relation_ids=DOCRED_IDS)
    b = _query_q3(cf,   base_relation_ids=DOCRED_IDS)
    print(f"   base answers: {a}")
    print(f"   cf   answers: {b}")
    ok = must(a == b, "answer sets equal after projection")
    return ok


def t11_bucket_aware_match_K1c():
    print("\n[T11] K1c bucket-aware match: cf relation == coarse bucket should match a base P-id in that bucket on same s/o")
    # COARSE_GROUPS maps bucket name -> list of base P-ids. Pick one.
    from graphguard.interventions.schema import COARSE_GROUPS
    bucket, members = next(iter(COARSE_GROUPS.items()))
    bid = members[0]
    base = [E("X", bid, "Y")]
    cf   = [E("X", bucket, "Y")]
    j = M.edge_jaccard(base, cf, base_relation_ids=DOCRED_IDS)
    print(f"   bucket={bucket!r}  base_rel={bid!r}  jaccard={j}")
    return must(j == 1.0, f"bucket name on cf side should match base member ({bid}) -> jaccard=1.0")


def t12_alias_canon():
    print("\n[T12] entity_alias canonicalization at audit time: 'United States' == 'the U.S.'")
    base = [{"subject_name": "United States", "relation": "P17",
             "object_name": "X", "subject_entity_id": "Q30",
             "object_entity_id": "QX"}]
    cf = [{"subject_name": "the U.S.", "relation": "P17",
           "object_name": "X", "subject_entity_id": None,
           "object_entity_id": "QX"}]
    j = M.edge_jaccard(base, cf, base_relation_ids=DOCRED_IDS)
    print(f"   jaccard={j}")
    return must(j == 1.0, "alias-equivalent entity names should produce jaccard=1.0")


def main():
    fns = [t1_identical, t2_rename_equivalent, t3_rename_with_real_change,
           t4_reorder_storage, t5_coarse_bucket, t6_entity_alias,
           t7_cf_event_backfill, t8_iter_pairs, t9_metric_signature,
           t10_query_q3_rename, t11_bucket_aware_match_K1c, t12_alias_canon]
    results = []
    for fn in fns:
        try:
            results.append((fn.__name__, fn()))
        except Exception as e:
            import traceback; traceback.print_exc()
            results.append((fn.__name__, False))
    print("\n=== summary ===")
    for n, r in results:
        print(f"  {'PASS' if r else 'FAIL'}  {n}")
    sys.exit(0 if all(r for _, r in results) else 1)


if __name__ == "__main__":
    main()
