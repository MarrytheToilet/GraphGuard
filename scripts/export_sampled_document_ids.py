#!/usr/bin/env python3
"""Export the exact document samples used by the seven paper runs.

The selection rule matches ``repositories.list_documents``: filter by the
configured split set, sort by ``document_id``, then take the profile limit.
The output also records sampled documents without a successful extraction
event, so a requested run size is not confused with its materialized count.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "cross_run" / "sampled_document_ids.json"

RUNS = {
    "docred__deepseek-v4-flash__300d": {
        "dataset": "DocRED",
        "profile": "main300",
        "splits": ["validation"],
        "limit": 300,
    },
    "redocred__deepseek-v4-flash__300d": {
        "dataset": "Re-DocRED",
        "profile": "main300",
        "splits": ["validation"],
        "limit": 300,
    },
    "scierc__deepseek-v4-flash__100d": {
        "dataset": "SciERC",
        "profile": "main100",
        "splits": ["dev", "test", "train"],
        "limit": 100,
    },
    "cdr__deepseek-v4-flash__300d": {
        "dataset": "BC5CDR",
        "profile": "main300",
        "splits": ["validation"],
        "limit": 300,
    },
    "docred__glm-5__100d": {
        "dataset": "DocRED",
        "profile": "cross-model-100",
        "splits": ["validation"],
        "limit": 100,
    },
    "docred__kimi-k2__100d": {
        "dataset": "DocRED",
        "profile": "cross-model-100",
        "splits": ["validation"],
        "limit": 100,
    },
    "docred__qwen3-32b__100d": {
        "dataset": "DocRED",
        "profile": "cross-model-100",
        "splits": ["validation"],
        "limit": 100,
    },
}


def select_documents(
    conn: sqlite3.Connection,
    splits: list[str],
    limit: int,
) -> list[str]:
    placeholders = ",".join("?" for _ in splits)
    return [
        row[0]
        for row in conn.execute(
            f"SELECT document_id FROM documents "
            f"WHERE split IN ({placeholders}) "
            f"ORDER BY document_id LIMIT ?",
            (*splits, limit),
        )
    ]


def main() -> int:
    output = {
        "schema_version": 1,
        "selection_rule": (
            "filter configured splits; ORDER BY document_id; "
            "LIMIT profile document count"
        ),
        "runs": {},
    }
    for run, spec in RUNS.items():
        db = (
            ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
        )
        if not db.is_file():
            raise FileNotFoundError(db)
        with sqlite3.connect(db) as conn:
            selected = select_documents(
                conn,
                spec["splits"],
                spec["limit"],
            )
            materialized = {
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT document_id FROM extraction_events"
                )
            }
        missing = sorted(set(selected) - materialized)
        output["runs"][run] = {
            **spec,
            "n_selected": len(selected),
            "n_with_extraction_event": (
                len(set(selected) & materialized)
            ),
            "documents_without_extraction_event": missing,
            "document_ids": selected,
        }

    OUTPUT.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
