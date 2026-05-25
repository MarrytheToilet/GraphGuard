#!/usr/bin/env python3
"""Run base LLM extraction over documents stored in SQLite.

Reads OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL from env (or .env via dotenv).

Example:
  python scripts/run_extract.py \
      --docred-config configs/docred.yaml \
      --prompts-config configs/prompts.yaml \
      --schemas-config configs/schemas.yaml \
      --models-config  configs/models.yaml \
      --split validation --limit 5
"""
from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
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

from graphguard.db.database import open_db          # noqa: E402
from graphguard.db import repositories as repo      # noqa: E402
from graphguard.extraction.extractor import extract_document  # noqa: E402
from graphguard.extraction.prompts import (         # noqa: E402
    get_prompt_def, get_schema_def, load_yaml,
)
from graphguard.llm.cache import CachedLLMClient            # noqa: E402
from graphguard.llm.openai_client import OpenAICompatClient   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docred-config", default="configs/docred.yaml")
    ap.add_argument("--prompts-config", default="configs/prompts.yaml")
    ap.add_argument("--schemas-config", default="configs/schemas.yaml")
    ap.add_argument("--models-config", default="configs/models.yaml")
    ap.add_argument("--prompt-id", default=None)
    ap.add_argument("--schema-id", default=None)
    ap.add_argument("--split", default=None)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--skip-extracted", action="store_true",
                    help="Skip docs that already have an event for (prompt,schema,model).")
    ap.add_argument("--workers", type=int, default=1,
                    help="Parallel document workers. Each worker uses its own SQLite connection.")
    ap.add_argument("--db", default=None)
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(level=args.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    docred_cfg = yaml.safe_load(Path(args.docred_config).read_text(encoding="utf-8"))
    prompts_cfg = load_yaml(args.prompts_config)
    schemas_cfg = load_yaml(args.schemas_config)
    models_cfg = load_yaml(args.models_config)

    db_path = args.db or docred_cfg["storage"]["db_path"]
    split = args.split or docred_cfg["dataset"].get("default_split", "validation")
    prompt_id = args.prompt_id or docred_cfg["extraction"]["default_prompt_id"]
    schema_id = args.schema_id or docred_cfg["extraction"]["default_schema_id"]

    prompt_def = get_prompt_def(prompts_cfg, prompt_id)
    schema_def = get_schema_def(schemas_cfg, schema_id)

    model_def = next(m for m in models_cfg["models"] if m["id"] == models_cfg["default"])
    temperature = float(model_def.get("temperature", 0.0))
    max_tokens = int(model_def.get("max_tokens", 2048))
    seed = model_def.get("seed")

    conn = open_db(db_path)
    docs = repo.list_documents(conn, split=split, limit=args.limit)
    if not docs:
        print(f"[warn] no documents in db for split={split}; run prepare_docred.py first")
        return 1

    def process_doc(drow) -> tuple[str, str, int, int, int]:
        worker_conn = open_db(db_path)
        worker_raw = OpenAICompatClient(
            timeout=float(model_def.get("timeout_s", 120)),
            json_mode=bool(model_def.get("json_mode", True)),
        )
        worker_llm = CachedLLMClient(worker_raw, worker_conn)
        d = dict(drow)
        if args.skip_extracted and repo.count_events_for_doc(
                worker_conn, d["document_id"], prompt_id, schema_id, worker_llm.model_id) > 0:
            return d["document_id"], "skipped", 0, worker_llm.hits, worker_llm.misses
        try:
            event_id, n_edges = extract_document(
                worker_conn, worker_llm,
                document_row=d, prompt_def=prompt_def, schema_def=schema_def,
                temperature=temperature, seed=seed, max_tokens=max_tokens,
            )
            return d["document_id"], event_id, n_edges, worker_llm.hits, worker_llm.misses
        except Exception as e:
            logging.exception("extraction failed for %s: %s", d["document_id"], e)
            return d["document_id"], "failed", 0, worker_llm.hits, worker_llm.misses
        finally:
            worker_conn.close()

    total_edges = hits = misses = 0
    workers = max(1, args.workers)
    if workers == 1:
        for d in tqdm(docs, desc="extract"):
            doc_id, event_id, n_edges, h, m = process_doc(d)
            total_edges += n_edges; hits += h; misses += m
            tqdm.write(f"  {doc_id}: event={event_id} edges={n_edges}")
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(process_doc, d) for d in docs]
            for fut in tqdm(as_completed(futures), total=len(futures), desc=f"extract[{workers}]"):
                doc_id, event_id, n_edges, h, m = fut.result()
                total_edges += n_edges; hits += h; misses += m
                tqdm.write(f"  {doc_id}: event={event_id} edges={n_edges}")

    print(f"[done] processed={len(docs)} edges_total={total_edges} "
          f"cache_hits={hits} cache_misses={misses} db={db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
