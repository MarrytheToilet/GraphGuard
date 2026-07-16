#!/usr/bin/env python3
"""GraphGuard on a real toolchain: LangChain LLMGraphTransformer.
(PVLDB revision, R1 / Rev6-W1.)

Runs the perturbation axes that the toolchain itself exposes, on the first
N DocRED validation documents (texts come from the lineage DB, no raw
corpus needed):

  base            — allowed_relationships in canonical order, temperature 0
  resample        — identical request repeated at temperature 0.2 (K6)
  schema_reorder  — allowed_relationships list reversed (K1, order axis)
  schema_rename   — relation labels replaced by synonyms; canonicalized
                    back before scoring (K1, rename axis)
  prompt_para     — paraphrased system prompt via the transformer's
                    `prompt` argument (K1b)
  evidence_reorder— document sentences reordered (K2)

Every (doc, condition) result is checkpointed to a JSONL cache, so the run
is resumable and the analysis can be replayed offline. The analysis
computes canonicalized edge drift vs. base per condition and violation
rates at the catalogue tolerances, for comparison with the custom-pipeline
contract results.

Usage:
  set -a && . ./.env && set +a
  python scripts/run_langchain_toolchain.py --limit 100 --workers 8
  python scripts/run_langchain_toolchain.py --analyze-only
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import statistics
import sys
import threading
import warnings
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# httpx chokes on `[::1]` / `<local>` entries in no_proxy (WSL default).
os.environ["no_proxy"] = os.environ["NO_PROXY"] = "localhost,127.0.0.1"
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB = ROOT / "data/processed/runs/docred__deepseek-v4-flash__300d/docred__deepseek-v4-flash__300d.db"
CACHE = ROOT / "data/processed/langchain_toolchain_cache.jsonl"
OUT = ROOT / "reports/cross_run/langchain_toolchain.json"

# Catalogue tolerances (per-pair drift tau) for the axes the toolchain exposes.
CONTRACT_TAU = {
    "schema_reorder": 0.15,   # K1
    "schema_rename": 0.15,    # K1
    "prompt_para": 0.20,      # K1b
    "evidence_reorder": 0.20, # K2
    "resample": 0.15,         # K6
}
ALPHA = 0.20  # violation budget

# Synonym map for the rename axis; scoring inverts it before comparison.
RENAME = {
    "country": "sovereign_state",
    "located_in": "situated_in",
    "headquarters_location": "hq_place",
    "place_of_birth": "birthplace",
    "place_of_death": "deathplace",
    "employer": "works_for",
    "part_of": "component_of",
    "member_of": "affiliated_with",
    "publication_date": "released_on",
    "performer": "performed_by",
    "author": "written_by",
    "director": "directed_by",
}
RENAME_INV = {v: k for k, v in RENAME.items()}

CONDITIONS = ["base", "resample", "schema_reorder", "schema_rename",
              "prompt_para", "evidence_reorder"]

PARA_SYSTEM = (
    "You are an information-extraction assistant building a knowledge graph. "
    "Read the passage and identify the entities it mentions together with the "
    "relationships that hold between them, using only the permitted relationship "
    "types. Be faithful to the text: never invent facts that the passage does "
    "not support, and keep entity names exactly as written. Output must follow "
    "the requested structured format."
)


def relation_labels() -> list[str]:
    con = sqlite3.connect(DB)
    row = con.execute("SELECT relation_types_json FROM schemas WHERE schema_id='docred_full'").fetchone()
    return [r["label"] for r in json.loads(row[0])]


def load_docs(limit: int) -> list[tuple[str, str, list[str]]]:
    con = sqlite3.connect(DB)
    docs = []
    for doc_id, raw in con.execute(
            "SELECT document_id, raw_text FROM documents ORDER BY document_id LIMIT ?", (limit,)):
        sents = [t for (t,) in con.execute(
            "SELECT text FROM sentences WHERE document_id=? ORDER BY sentence_index", (doc_id,))]
        docs.append((doc_id, raw, sents))
    return docs


# ------------------------------------------------------------------ extract

_LOCK = threading.Lock()


def make_transformer(condition: str, labels: list[str], ignore_tools: bool):
    from langchain_openai import ChatOpenAI
    from langchain_experimental.graph_transformers import LLMGraphTransformer

    temp = 0.2 if condition == "resample" else 0.0
    llm = ChatOpenAI(model=os.environ["OPENAI_MODEL"],
                     base_url=os.environ["OPENAI_BASE_URL"],
                     api_key=os.environ["OPENAI_API_KEY"],
                     temperature=temp, timeout=120, max_retries=3)
    rels = list(labels)
    if condition == "schema_reorder":
        rels = rels[::-1]
    elif condition == "schema_rename":
        rels = [RENAME.get(r, r) for r in rels]
    kwargs = dict(llm=llm, allowed_relationships=rels,
                  ignore_tool_usage=ignore_tools)
    if condition == "prompt_para":
        from langchain_core.prompts import ChatPromptTemplate
        kwargs["prompt"] = ChatPromptTemplate.from_messages(
            [("system", PARA_SYSTEM), ("human", "{input}")])
    return LLMGraphTransformer(**kwargs)


def doc_text(condition: str, doc_id: str, raw: str, sents: list[str]) -> str:
    if condition == "evidence_reorder" and len(sents) > 2:
        order = list(range(len(sents)))
        random.Random(hash(doc_id) & 0xFFFF).shuffle(order)
        return " ".join(sents[i] for i in order)
    return raw


def extract_one(condition, doc_id, raw, sents, labels, ignore_tools):
    from langchain_core.documents import Document
    t = make_transformer(condition, labels, ignore_tools)
    gd = t.convert_to_graph_documents(
        [Document(page_content=doc_text(condition, doc_id, raw, sents))])[0]
    edges = [[r.source.id, r.type, r.target.id] for r in gd.relationships]
    return {"doc": doc_id, "condition": condition, "edges": edges}


def run_extraction(limit: int, workers: int, ignore_tools: bool) -> None:
    labels = relation_labels()
    docs = load_docs(limit)
    done = set()
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            try:
                r = json.loads(line)
                done.add((r["doc"], r["condition"]))
            except Exception:
                pass
    todo = [(c, d, raw, sents) for c in CONDITIONS for d, raw, sents in docs
            if (d, c) not in done]
    print(f"[extract] {len(todo)} calls to make ({len(done)} cached), workers={workers}")
    if not todo:
        return
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    n_ok = n_err = 0
    with CACHE.open("a", encoding="utf-8") as fh, \
         ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(extract_one, c, d, raw, sents, labels, ignore_tools): (d, c)
                for c, d, raw, sents in todo}
        for fut in as_completed(futs):
            d, c = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:  # noqa: BLE001
                rec = {"doc": d, "condition": c, "edges": None,
                       "error": f"{type(e).__name__}: {e}"[:300]}
                n_err += 1
            else:
                n_ok += 1
            with _LOCK:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
            if (n_ok + n_err) % 50 == 0:
                print(f"[extract] {n_ok+n_err}/{len(todo)} done ({n_err} errors)", flush=True)
    print(f"[extract] finished: ok={n_ok} err={n_err}")


# ------------------------------------------------------------------ analyze

def canon_edges(edges, condition) -> set:
    out = set()
    for s, r, o in edges or []:
        r = str(r).lower().strip().replace(" ", "_")
        r = RENAME_INV.get(r, r)
        out.add((str(s).lower().strip(), r, str(o).lower().strip()))
    return out


def analyze() -> None:
    recs = defaultdict(dict)  # doc -> condition -> edges
    errors = defaultdict(int)
    for line in CACHE.read_text().splitlines():
        r = json.loads(line)
        if r.get("edges") is None:
            errors[r["condition"]] += 1
            continue
        recs[r["doc"]][r["condition"]] = r["edges"]

    summary = {}
    for cond in CONDITIONS[1:]:
        drifts = []
        for doc, by_cond in recs.items():
            if "base" not in by_cond or cond not in by_cond:
                continue
            b = canon_edges(by_cond["base"], "base")
            c = canon_edges(by_cond[cond], cond)
            if not b and not c:
                continue
            inter, union = len(b & c), len(b | c)
            drifts.append(1.0 - (inter / union if union else 1.0))
        if not drifts:
            continue
        tau = CONTRACT_TAU[cond]
        viol = sum(1 for d in drifts if d > tau) / len(drifts)
        summary[cond] = {
            "n": len(drifts), "errors": errors.get(cond, 0),
            "mean_drift": round(statistics.mean(drifts), 4),
            "median_drift": round(statistics.median(drifts), 4),
            "tau": tau, "violation_rate": round(viol, 4),
            "verdict": "VIOLATED" if viol > ALPHA else "SATISFIED",
        }

    out = {"toolchain": "langchain.LLMGraphTransformer",
           "model": os.environ.get("OPENAI_MODEL", "?"),
           "n_docs": len(recs), "summary": summary}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"[analyze] {len(recs)} docs -> {OUT}")
    for cond, s in summary.items():
        print(f"  {cond:<17} n={s['n']:<4} drift={s['mean_drift']:.3f} "
              f"viol@tau={s['tau']:.2f}: {s['violation_rate']:.3f} -> {s['verdict']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--ignore-tool-usage", action="store_true",
                    help="Use JSON-prompt mode for models without function calling.")
    args = ap.parse_args()
    if not args.analyze_only:
        for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
            if not os.environ.get(var):
                raise SystemExit(f"{var} not set; source .env first")
        run_extraction(args.limit, args.workers, args.ignore_tool_usage)
    analyze()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
