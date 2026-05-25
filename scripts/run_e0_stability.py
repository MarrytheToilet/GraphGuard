#!/usr/bin/env python3
"""E0 stability driver: repeat extraction n times per document and persist
per-document stability metrics + per-edge stochastic_variance.

Writes a JSON report mirroring the legacy layout consumed by
`make_paper_figures.py` and the per-run report builder.

Example:
  python scripts/run_e0_stability.py \
      --docred-config configs/docred.yaml \
      --prompts-config configs/prompts.yaml \
      --schemas-config configs/schemas.yaml \
      --models-config  configs/models.yaml \
      --limit 50 --runs 5 --temperature 0.3 \
      --db data/processed/runs/<run>/<run>.db \
      --report data/processed/runs/<run>/reports/e0_report.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
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

from graphguard.db.database import open_db                      # noqa: E402
from graphguard.db import repositories as repo                  # noqa: E402
from graphguard.experiments.e0_stability import (               # noqa: E402
    compute_metrics, run_stability_for_document, update_stochastic_variance,
)
from graphguard.extraction.prompts import (                     # noqa: E402
    get_prompt_def, get_schema_def, load_yaml,
)
from graphguard.llm.cache import CachedLLMClient                # noqa: E402
from graphguard.llm.openai_client import OpenAICompatClient      # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docred-config", default="configs/docred.yaml")
    ap.add_argument("--prompts-config", default="configs/prompts.yaml")
    ap.add_argument("--schemas-config", default="configs/schemas.yaml")
    ap.add_argument("--models-config", default="configs/models.yaml")
    ap.add_argument("--prompt-id", default=None)
    ap.add_argument("--schema-id", default=None)
    ap.add_argument("--split", default=None)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--runs", type=int, default=5,
                    help="Number of repeat extractions per document.")
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--db", default=None)
    ap.add_argument("--report", required=True,
                    help="Output JSON report path.")
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
    max_tokens = int(model_def.get("max_tokens", 2048))

    conn = open_db(db_path)
    docs = repo.list_documents(conn, split=split, limit=args.limit)
    if not docs:
        print(f"[warn] no documents in db for split={split}")
        return 1

    raw = OpenAICompatClient(
        timeout=float(model_def.get("timeout_s", 120)),
        json_mode=bool(model_def.get("json_mode", True)),
    )
    llm = CachedLLMClient(raw, conn)

    base_relation_ids = {r.get("id") or r.get("relation_id") for r in schema_def.get("relations", [])} \
        if isinstance(schema_def.get("relations"), list) else set()

    report_docs: list[dict] = []
    n_updated_edges = 0

    for drow in tqdm(docs, desc=f"e0[runs={args.runs}]"):
        d = dict(drow)
        event_ids = run_stability_for_document(
            conn, llm,
            document_row=d,
            prompt_def=prompt_def, schema_def=schema_def,
            n_runs=args.runs, temperature=args.temperature,
            max_tokens=max_tokens,
        )
        if len(event_ids) < 2:
            tqdm.write(f"  {d['document_id']}: only {len(event_ids)} runs — skip metrics")
            continue
        result = compute_metrics(conn, d["document_id"], event_ids)
        repo.upsert_stability_report(
            conn, d["document_id"],
            n_runs=result.n_runs,
            avg_edge_overlap=result.avg_edge_overlap,
            type_agreement=result.type_agreement,
            disappearance_rate=result.disappearance_rate,
            type_flip_rate=result.type_flip_rate,
            new_edge_rate=result.new_edge_rate,
        )
        base = event_ids[0]
        n_updated_edges += update_stochastic_variance(
            conn, base, event_ids[1:], base_relation_ids
        )
        report_docs.append({
            "document_id": d["document_id"],
            "event_ids": event_ids,
            "metrics": {
                "avg_edge_overlap": round(result.avg_edge_overlap, 4),
                "type_agreement": round(result.type_agreement, 4),
                "disappearance_rate": round(result.disappearance_rate, 4),
                "type_flip_rate": round(result.type_flip_rate, 4),
                "new_edge_rate": round(result.new_edge_rate, 4),
            },
        })
        tqdm.write(
            f"  {d['document_id']}: overlap={result.avg_edge_overlap:.3f} "
            f"flip={result.type_flip_rate:.3f}"
        )

    def _mean(key: str) -> float:
        xs = [d["metrics"][key] for d in report_docs]
        return sum(xs) / len(xs) if xs else 0.0

    summary = {
        "n_documents": len(report_docs),
        "n_runs_per_doc": args.runs,
        "temperature": args.temperature,
        "avg_edge_overlap": round(_mean("avg_edge_overlap"), 4),
        "type_agreement": round(_mean("type_agreement"), 4),
        "disappearance_rate": round(_mean("disappearance_rate"), 4),
        "type_flip_rate": round(_mean("type_flip_rate"), 4),
        "new_edge_rate": round(_mean("new_edge_rate"), 4),
        "edges_with_variance_updated": n_updated_edges,
    }

    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"docs": report_docs, "summary": summary}, indent=2))
    print(f"[done] e0 docs={len(report_docs)} updated_edges={n_updated_edges} "
          f"avg_overlap={summary['avg_edge_overlap']:.3f} report={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
