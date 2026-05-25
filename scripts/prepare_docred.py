#!/usr/bin/env python3
"""Download DocRED via HuggingFace and import into SQLite.

Example:
  python scripts/prepare_docred.py --config configs/docred.yaml --split validation --limit 50
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.data.load_docred import import_docred_into_db  # noqa: E402
from graphguard.data.load_scierc import import_scierc_into_db  # noqa: E402
from graphguard.data.load_cdr import import_cdr_into_db        # noqa: E402
from graphguard.db.database import open_db                     # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/docred.yaml")
    ap.add_argument("--split", default=None, help="Override split (validation/train/test)")
    ap.add_argument("--splits", default=None,
                    help="Comma-separated splits to import, e.g. validation,train.")
    ap.add_argument("--all-splits", action="store_true",
                    help="Import all splits listed in dataset.splits.")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--db", default=None, help="Override storage.db_path")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(level=args.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db_path = args.db or cfg["storage"]["db_path"]
    if args.splits:
        splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    elif args.all_splits:
        splits = list(cfg["dataset"].get("splits") or [cfg["dataset"].get("default_split", "validation")])
    else:
        splits = [args.split or cfg["dataset"].get("default_split", "validation")]
    hf_name = cfg["dataset"]["hf_name"]
    hf_config = cfg["dataset"].get("hf_config")
    cache_dir = cfg["dataset"].get("cache_dir")
    local_files = cfg["dataset"].get("local_files")
    dataset_name = cfg["dataset"].get("name", "docred")
    doc_id_prefix = cfg["dataset"].get("doc_id_prefix")

    conn = open_db(db_path)
    loader_name = cfg["dataset"].get("loader", "docred")
    total_docs = total_sentences = total_entities = 0
    for split in splits:
        if loader_name == "scierc":
            local_dir = "data/raw/scierc/processed_data/json"
            if local_files:
                first = next(iter(local_files.values()))
                local_dir = str(Path(first).parent)
            stats_dict = import_scierc_into_db(
                conn, split=split, local_dir=local_dir, limit=args.limit,
                dataset_name=dataset_name, doc_id_prefix=doc_id_prefix,
            )
            class _S: pass
            stats = _S(); stats.documents = stats_dict["documents"]
            stats.sentences = stats_dict["sentences"]; stats.entities = stats_dict["entities"]
        elif loader_name == "cdr":
            local_dir = cfg["dataset"].get("local_dir",
                "data/raw/cdr/CDR_Data/CDR.Corpus.v010516")
            stats = import_cdr_into_db(
                conn, split=split, local_dir=local_dir, limit=args.limit,
                dataset_name=dataset_name, doc_id_prefix=doc_id_prefix,
            )
        else:
            stats = import_docred_into_db(
                conn, split=split, hf_name=hf_name, hf_config=hf_config,
                cache_dir=cache_dir, limit=args.limit,
                local_files=local_files, dataset_name=dataset_name,
                doc_id_prefix=doc_id_prefix,
            )
        total_docs += stats.documents
        total_sentences += stats.sentences
        total_entities += stats.entities
        print(f"[split] {split}: docs={stats.documents} sentences={stats.sentences} entities={stats.entities}")
    print(f"[done] db={db_path} splits={','.join(splits)} docs={total_docs} "
          f"sentences={total_sentences} entities={total_entities}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
