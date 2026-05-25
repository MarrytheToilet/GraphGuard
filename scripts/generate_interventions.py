#!/usr/bin/env python3
"""Generate intervention candidates for documents that already have a base extraction.

Example:
  python scripts/generate_interventions.py --limit 5
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.db.database import open_db                    # noqa: E402
from graphguard.db import repositories as repo                # noqa: E402
from graphguard.interventions.candidates import generate_for_document  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docred-config", default="configs/docred.yaml")
    ap.add_argument("--db", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--split", default=None)
    ap.add_argument("--remove-sentences", action="store_true", default=True)
    ap.add_argument("--no-mask-sentences", action="store_true",
                    help="Disable sentence-mask interventions (only remove).")
    ap.add_argument("--schema-variants", nargs="+", default=("with_other", "coarse", "ambiguous"))
    ap.add_argument("--prompt-clauses-to-drop", nargs="+",
                    default=("C1_evidence_only", "C2_infer_implicit",
                             "C3_use_schema", "C4_allow_other",
                             "C5_cite_evidence", "C6_return_confidence"))
    ap.add_argument("--max-drop-relations", type=int, default=3,
                    help="Per-document top relations to turn into schema drop-specific variants.")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(level=args.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = yaml.safe_load(Path(args.docred_config).read_text(encoding="utf-8"))
    db_path = args.db or cfg["storage"]["db_path"]
    split = args.split or cfg["dataset"].get("default_split", "validation")
    base_prompt_id = cfg["extraction"]["default_prompt_id"]
    base_schema_id = cfg["extraction"]["default_schema_id"]

    conn = open_db(db_path)
    docs = repo.list_documents(conn, split=split, limit=args.limit)
    total = 0
    for d in docs:
        items = generate_for_document(
            conn, d["document_id"],
            base_prompt_id=base_prompt_id, base_schema_id=base_schema_id,
            prompt_clauses_to_drop=args.prompt_clauses_to_drop,
            schema_variants=args.schema_variants,
            max_drop_specific=args.max_drop_relations,
            mask_sentences=not args.no_mask_sentences,
            remove_sentences=args.remove_sentences,
        )
        total += len(items)
        print(f"  {d['document_id']}: +{len(items)} candidates")
    print(f"[done] documents={len(docs)} candidates_total={total} db={db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
