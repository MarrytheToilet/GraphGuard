#!/usr/bin/env python3
"""Run counterfactual extractions for documents that have base extractions.

Example:
  python scripts/run_counterfactuals.py --limit 2 --budget-calls 8
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from graphguard.db.database import open_db                  # noqa: E402
from graphguard.db import repositories as repo              # noqa: E402
from graphguard.extraction.prompts import (                 # noqa: E402
    get_prompt_def, get_schema_def, load_yaml,
)
from graphguard.interventions.candidates import list_for_document  # noqa: E402
from graphguard.llm.cache import CachedLLMClient            # noqa: E402
from graphguard.llm.openai_client import OpenAICompatClient # noqa: E402
from graphguard.planning.runner import run_for_document     # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docred-config", default="configs/docred.yaml")
    ap.add_argument("--prompts-config", default="configs/prompts.yaml")
    ap.add_argument("--schemas-config", default="configs/schemas.yaml")
    ap.add_argument("--models-config",  default="configs/models.yaml")
    ap.add_argument("--db", default=None)
    ap.add_argument("--split", default=None)
    ap.add_argument("--limit", type=int, default=2, help="Number of documents to process")
    ap.add_argument("--budget-calls", type=int, default=None,
                    help="Per-document max LLM calls (counterfactual runs). Cache hits don't count toward this.")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(level=args.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    docred_cfg = yaml.safe_load(Path(args.docred_config).read_text(encoding="utf-8"))
    prompts_cfg = load_yaml(args.prompts_config)
    schemas_cfg = load_yaml(args.schemas_config)
    models_cfg  = load_yaml(args.models_config)

    db_path = args.db or docred_cfg["storage"]["db_path"]
    split = args.split or docred_cfg["dataset"].get("default_split", "validation")
    base_prompt_def = get_prompt_def(prompts_cfg, docred_cfg["extraction"]["default_prompt_id"])
    base_schema_def = get_schema_def(schemas_cfg, docred_cfg["extraction"]["default_schema_id"])

    model_def = next(m for m in models_cfg["models"] if m["id"] == models_cfg["default"])
    raw = OpenAICompatClient(
        timeout=float(model_def.get("timeout_s", 120)),
        json_mode=bool(model_def.get("json_mode", True)),
    )
    temperature = float(model_def.get("temperature", 0.0))
    seed = model_def.get("seed")
    max_tokens = int(model_def.get("max_tokens", 2048))

    conn = open_db(db_path)
    llm = CachedLLMClient(raw, conn)

    docs = repo.list_documents(conn, split=split, limit=args.limit)
    summary = {"runs": 0, "skipped": 0, "outcomes": 0}
    for d in tqdm(docs, desc="docs"):
        ivs = list_for_document(conn, d["document_id"])
        if not ivs:
            tqdm.write(f"  {d['document_id']}: no candidates (run generate_interventions.py first)")
            continue
        result = run_for_document(
            conn, llm,
            document_row=d, base_prompt_def=base_prompt_def, base_schema_def=base_schema_def,
            interventions=ivs,
            temperature=temperature, seed=seed, max_tokens=max_tokens,
            budget_calls=args.budget_calls,
        )
        for k in summary:
            summary[k] += result[k]
        tqdm.write(f"  {d['document_id']}: runs={result['runs']} skipped={result['skipped']} "
                   f"outcomes={result['outcomes']}")

    print(f"[done] {summary} cache_hits={llm.hits} cache_misses={llm.misses} db={db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
