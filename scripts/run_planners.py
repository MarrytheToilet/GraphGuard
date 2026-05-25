#!/usr/bin/env python3
"""Run counterfactuals via a chosen planner under a budget.

Wraps `planning.runner` after filtering candidates with the planner's
selection. Compatible with all planners in `planning.planners`.

Example:
  python scripts/run_planners.py --planner graphguard --budget 4 --limit 1
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

from graphguard.db.database import open_db
from graphguard.db import repositories as repo
from graphguard.extraction.prompts import get_prompt_def, get_schema_def, load_yaml
from graphguard.interventions.candidates import list_for_document
from graphguard.llm.cache import CachedLLMClient
from graphguard.llm.openai_client import OpenAICompatClient
from graphguard.planning.planners import get_planner, PLANNERS
from graphguard.planning.runner import run_for_document


def _candidate_to_obj(row):
    from graphguard.interventions.candidates import InterventionCandidate
    return InterventionCandidate(
        intervention_id=row["intervention_id"],
        document_id=row["document_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        operator=row["operator"],
        description=row["description"],
        estimated_cost=row["estimated_cost"] or 1.0,
        group_id=row["group_id"],
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--planner", required=True, choices=list(PLANNERS))
    ap.add_argument("--budget", type=int, default=4)
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--docred-config", default="configs/docred.yaml")
    ap.add_argument("--prompts-config", default="configs/prompts.yaml")
    ap.add_argument("--schemas-config", default="configs/schemas.yaml")
    ap.add_argument("--models-config", default="configs/models.yaml")
    ap.add_argument("--db", default=None)
    ap.add_argument("--workers", type=int, default=1,
                    help="Parallel document workers. Each worker uses its own SQLite connection.")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(level=args.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    docred_cfg = yaml.safe_load(Path(args.docred_config).read_text(encoding="utf-8"))
    prompts_cfg = load_yaml(args.prompts_config)
    schemas_cfg = load_yaml(args.schemas_config)
    models_cfg = load_yaml(args.models_config)
    db_path = args.db or docred_cfg["storage"]["db_path"]
    split = docred_cfg["dataset"].get("default_split", "validation")
    prompt_id = docred_cfg["extraction"]["default_prompt_id"]
    schema_id = docred_cfg["extraction"]["default_schema_id"]
    prompt_def = get_prompt_def(prompts_cfg, prompt_id)
    schema_def = get_schema_def(schemas_cfg, schema_id)
    model_def = next(m for m in models_cfg["models"] if m["id"] == models_cfg["default"])
    conn = open_db(db_path)

    try:
        planner = get_planner(args.planner, seed=args.seed)
    except TypeError:
        planner = get_planner(args.planner)

    docs = repo.list_documents(conn, split=split, limit=args.limit)
    jobs = []
    for d in docs:
        cands_rows = list_for_document(conn, d["document_id"])
        if not cands_rows:
            tqdm.write(f"  {d['document_id']}: no candidates; run generate_interventions first")
            continue
        cands = [_candidate_to_obj(r) for r in cands_rows]
        chosen = planner.choose(cands, args.budget, conn=conn)
        chosen_ids = {c.intervention_id for c in chosen}
        chosen_rows = [dict(r) for r in cands_rows if r["intervention_id"] in chosen_ids]
        tqdm.write(f"  {d['document_id']}: planner={planner.name} chose {len(chosen_rows)}/{len(cands)}")
        jobs.append((dict(d), chosen_rows))

    def process_job(job) -> dict:
        d, chosen_rows = job
        worker_conn = open_db(db_path)
        llm_raw = OpenAICompatClient(timeout=float(model_def.get("timeout_s", 120)),
                                     json_mode=bool(model_def.get("json_mode", True)))
        llm = CachedLLMClient(llm_raw, worker_conn)
        try:
            s = run_for_document(
                worker_conn, llm,
                document_row=d, interventions=chosen_rows,
                base_prompt_def=prompt_def, base_schema_def=schema_def,
                temperature=float(model_def.get("temperature", 0.0)),
                seed=model_def.get("seed"),
                max_tokens=int(model_def.get("max_tokens", 2048)),
                budget_calls=args.budget,
            )
            s["cache_hits"] = llm.hits
            s["cache_misses"] = llm.misses
            return s
        finally:
            worker_conn.close()

    summary = {"runs": 0, "skipped": 0, "outcomes": 0}
    hits = misses = 0
    workers = max(1, args.workers)
    if workers == 1:
        iterator = (process_job(j) for j in jobs)
        for s in tqdm(iterator, total=len(jobs), desc=f"plan-{args.planner}"):
            hits += s.pop("cache_hits", 0); misses += s.pop("cache_misses", 0)
            for k, v in s.items():
                if isinstance(v, int):
                    summary[k] = summary.get(k, 0) + v
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(process_job, j) for j in jobs]
            for fut in tqdm(as_completed(futures), total=len(futures), desc=f"plan-{args.planner}[{workers}]"):
                s = fut.result()
                hits += s.pop("cache_hits", 0); misses += s.pop("cache_misses", 0)
                for k, v in s.items():
                    if isinstance(v, int):
                        summary[k] = summary.get(k, 0) + v
    print(f"[done] planner={planner.name} budget={args.budget} {summary} "
          f"cache_hits={hits} misses={misses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
