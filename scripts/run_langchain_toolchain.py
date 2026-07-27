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
                    `prompt` argument (K2)
  evidence_reorder— document sentences reordered (K3)

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
import hashlib
import importlib.metadata
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
LOCAL_CACHE = ROOT / "data/processed/langchain_toolchain_cache.jsonl"
PUBLISHED_CACHE = ROOT / "reports/cross_run/langchain_toolchain_cache.jsonl"
CHECKPOINT_METADATA = (
    ROOT / "reports/cross_run/langchain_toolchain_checkpoint.json"
)
OUT = ROOT / "reports/cross_run/langchain_toolchain.json"
EVIDENCE_SEED_RULE = "sha256(doc_id UTF-8), first 8 bytes, unsigned big-endian"
DEPENDENCY_PACKAGES = (
    "langchain-openai",
    "langchain-experimental",
    "langchain-core",
)

# Catalogue tolerances (per-pair drift tau) for the axes the toolchain exposes.
CONTRACT_TAU = {
    "schema_reorder": 0.15,   # K1
    "schema_rename": 0.15,    # K1
    "prompt_para": 0.20,      # K2
    "evidence_reorder": 0.20, # K3
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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def langchain_dependency_versions() -> dict[str, str]:
    versions = {}
    for package in DEPENDENCY_PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed (analysis-only)"
    return versions


def stable_evidence_seed(doc_id: str) -> int:
    digest = hashlib.sha256(doc_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def config_fingerprint(
    condition: str,
    labels: list[str],
    ignore_tools: bool,
    extraction_dependency_versions: dict[str, str] | None = None,
) -> str:
    dependencies = (
        extraction_dependency_versions
        if extraction_dependency_versions is not None
        else langchain_dependency_versions()
    )
    payload = {
        "condition": condition,
        "model": os.environ.get("OPENAI_MODEL", ""),
        "temperature": 0.2 if condition == "resample" else 0.0,
        "allowed_relationships": labels,
        "ignore_tool_usage": ignore_tools,
        "evidence_seed_rule": EVIDENCE_SEED_RULE,
        "extraction_dependency_versions": dependencies,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(encoded)


def cohort_fingerprint(
    labels: list[str],
    ignore_tools: bool,
    source_database_sha256: str,
    extraction_dependency_versions: dict[str, str] | None = None,
) -> str:
    """Identify one mutually compatible extraction cohort."""
    dependencies = (
        extraction_dependency_versions
        if extraction_dependency_versions is not None
        else langchain_dependency_versions()
    )
    payload = {
        "model": os.environ.get("OPENAI_MODEL", ""),
        "allowed_relationships": labels,
        "ignore_tool_usage": ignore_tools,
        "evidence_seed_rule": EVIDENCE_SEED_RULE,
        "source_database_sha256": source_database_sha256,
        "extraction_dependency_versions": dependencies,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(encoded)


def para_system(rels: list[str]) -> str:
    """Paraphrased system prompt (K2 axis). Keeps the output contract of the
    transformer's default unstructured prompt (JSON list with head / head_type /
    relation / tail / tail_type) and the permitted relation list, so only the
    instruction wording changes."""
    return (
        "You are an information-extraction assistant that turns text passages "
        "into knowledge-graph triples. Read the passage and identify the "
        "entities it mentions and the relationships between them. The only "
        "relationship types you may use are: " + ", ".join(rels) + ". "
        "Respond with JSON only: a list of objects, each having exactly the "
        'keys "head", "head_type", "relation", "tail", and "tail_type". Use '
        "the most complete name for every entity and keep entity references "
        "consistent across triples. Extract every relationship the passage "
        "supports, invent nothing, and include no prose or explanations "
        "outside the JSON list."
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
            [("system", para_system(rels)),
             ("human", "Extract the entities and relationships from this text.\nText: {input}")])
    return LLMGraphTransformer(**kwargs)


def doc_text(condition: str, doc_id: str, raw: str, sents: list[str]) -> str:
    if condition == "evidence_reorder" and len(sents) > 2:
        order = list(range(len(sents)))
        random.Random(stable_evidence_seed(doc_id)).shuffle(order)
        return " ".join(sents[i] for i in order)
    return raw


def record_metadata(
    condition: str,
    doc_id: str,
    text: str,
    labels: list[str],
    ignore_tools: bool,
    cohort: str,
    extraction_dependency_versions: dict[str, str],
) -> dict:
    metadata = {
        "config_fingerprint": config_fingerprint(
            condition,
            labels,
            ignore_tools,
            extraction_dependency_versions,
        ),
        "cohort_fingerprint": cohort,
        "input_sha256": sha256_bytes(text.encode("utf-8")),
        "extraction_dependency_versions": extraction_dependency_versions,
        "model": os.environ["OPENAI_MODEL"],
        "evidence_seed_rule": EVIDENCE_SEED_RULE,
        "ignore_tool_usage": ignore_tools,
    }
    if condition == "evidence_reorder":
        metadata["evidence_seed"] = stable_evidence_seed(doc_id)
    return metadata


def extract_one(
    condition,
    doc_id,
    raw,
    sents,
    labels,
    ignore_tools,
    cohort,
    extraction_dependency_versions,
):
    from langchain_core.documents import Document
    t = make_transformer(condition, labels, ignore_tools)
    text = doc_text(condition, doc_id, raw, sents)
    gd = t.convert_to_graph_documents(
        [Document(page_content=text)])[0]
    edges = [[r.source.id, r.type, r.target.id] for r in gd.relationships]
    record = {
        "doc": doc_id,
        "condition": condition,
        **record_metadata(
            condition,
            doc_id,
            text,
            labels,
            ignore_tools,
            cohort,
            extraction_dependency_versions,
        ),
        "edges": edges,
    }
    return record


def run_extraction(
    limit: int,
    workers: int,
    ignore_tools: bool,
    cache_path: Path = LOCAL_CACHE,
) -> str:
    labels = relation_labels()
    docs = load_docs(limit)
    extraction_dependencies = langchain_dependency_versions()
    cohort = cohort_fingerprint(
        labels,
        ignore_tools,
        sha256_file(DB),
        extraction_dependencies,
    )
    cached_records = []
    if cache_path.exists():
        for line in cache_path.read_text().splitlines():
            try:
                cached_records.append(json.loads(line))
            except Exception:
                pass
    done = successful_record_keys(cached_records)
    todo = []
    for condition in CONDITIONS:
        for doc_id, raw, sents in docs:
            text = doc_text(condition, doc_id, raw, sents)
            metadata = record_metadata(
                condition,
                doc_id,
                text,
                labels,
                ignore_tools,
                cohort,
                extraction_dependencies,
            )
            key = (
                cohort,
                doc_id,
                condition,
                metadata["config_fingerprint"],
                metadata["input_sha256"],
            )
            if key not in done:
                todo.append((condition, doc_id, raw, sents))
    print(f"[extract] {len(todo)} calls to make ({len(done)} cached), workers={workers}")
    if not todo:
        return cohort
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    n_ok = n_err = 0
    with cache_path.open("a", encoding="utf-8") as fh, \
         ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(
                extract_one,
                c,
                d,
                raw,
                sents,
                labels,
                ignore_tools,
                cohort,
                extraction_dependencies,
            ): (d, c, raw, sents)
            for c, d, raw, sents in todo
        }
        for fut in as_completed(futs):
            d, c, raw, sents = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:  # noqa: BLE001
                text = doc_text(c, d, raw, sents)
                rec = {
                    "doc": d,
                    "condition": c,
                    **record_metadata(
                        c,
                        d,
                        text,
                        labels,
                        ignore_tools,
                        cohort,
                        extraction_dependencies,
                    ),
                    "edges": None,
                    "error": f"{type(e).__name__}: {e}"[:300],
                }
                n_err += 1
            else:
                n_ok += 1
            with _LOCK:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
            if (n_ok + n_err) % 50 == 0:
                print(f"[extract] {n_ok+n_err}/{len(todo)} done ({n_err} errors)", flush=True)
    print(f"[extract] finished: ok={n_ok} err={n_err}")
    return cohort


# ------------------------------------------------------------------ analyze

def canon_edges(edges, condition) -> set:
    out = set()
    for s, r, o in edges or []:
        r = str(r).lower().strip().replace(" ", "_")
        r = RENAME_INV.get(r, r)
        out.add((str(s).lower().strip(), r, str(o).lower().strip()))
    return out


def successful_record_keys(records: list[dict]) -> set[tuple]:
    """Return reusable successes, scoped to an exact extraction cohort."""
    completion_state = {}
    for record in records:
        fingerprint = record.get("config_fingerprint")
        cohort = record.get("cohort_fingerprint")
        input_sha256 = record.get("input_sha256")
        if fingerprint and cohort and input_sha256:
            key = (
                cohort,
                record["doc"],
                record["condition"],
                fingerprint,
                input_sha256,
            )
            # A later failure invalidates an earlier success for the same
            # exact cohort/input and remains retryable.
            completion_state[key] = record.get("edges") is not None
    return {
        key for key, successful in completion_state.items() if successful
    }


def checkpoint_metadata(records: list[dict]) -> dict:
    fingerprinted = sum(
        1 for record in records if record.get("config_fingerprint")
    )
    records_without_fingerprints = len(records) - fingerprinted
    if not records:
        checkpoint_format = "empty"
    elif fingerprinted == 0:
        checkpoint_format = "published-checkpoint"
    elif records_without_fingerprints == 0:
        checkpoint_format = "fingerprinted-only"
    else:
        checkpoint_format = "mixed"
    return {
        "records": len(records),
        "fingerprinted_records": fingerprinted,
        "records_without_fingerprints": records_without_fingerprints,
        "format": checkpoint_format,
        "contains_fingerprinted_records": fingerprinted > 0,
        "fully_fingerprinted": (
            bool(records) and records_without_fingerprints == 0
        ),
    }


def select_analysis_records(
    records: list[dict],
    requested_cohort: str | None = None,
) -> tuple[dict, dict, dict]:
    """Select one coherent checkpoint cohort without mixing configurations."""
    fingerprinted_records = [
        record
        for record in records
        if record.get("config_fingerprint")
        and record.get("cohort_fingerprint")
        and record.get("input_sha256")
    ]
    recs = defaultdict(dict)
    errors = defaultdict(int)
    if not fingerprinted_records:
        for record in records:
            if record.get("edges") is None:
                errors[record["condition"]] += 1
                continue
            recs[record["doc"]][record["condition"]] = record["edges"]
        return recs, errors, {
            "mode": "published-checkpoint",
            "cohort_fingerprint": None,
            "selected_records": len(records),
        }

    available = {
        record["cohort_fingerprint"] for record in fingerprinted_records
    }
    if requested_cohort is not None and requested_cohort not in available:
        raise RuntimeError(
            f"requested LangChain cohort {requested_cohort} is absent "
            "from the selected LangChain checkpoint"
        )
    cohort = (
        requested_cohort
        or fingerprinted_records[-1]["cohort_fingerprint"]
    )

    # The checkpoint is append-only.  The last status for each document and
    # condition in the selected cohort is authoritative; a failure therefore
    # cannot silently fall back to an older success.
    latest = {}
    for record in fingerprinted_records:
        if record["cohort_fingerprint"] == cohort:
            latest[(record["doc"], record["condition"])] = record
    for record in latest.values():
        if record.get("edges") is None:
            errors[record["condition"]] += 1
            continue
        recs[record["doc"]][record["condition"]] = record["edges"]
    dependency_sets = {
        json.dumps(
            record.get("extraction_dependency_versions"),
            sort_keys=True,
        )
        for record in latest.values()
    }
    if len(dependency_sets) != 1:
        raise RuntimeError(
            f"LangChain cohort {cohort} mixes extraction environments"
        )
    extraction_dependencies = json.loads(dependency_sets.pop())
    models = {record.get("model") for record in latest.values()}
    if len(models) != 1 or None in models:
        raise RuntimeError(
            f"LangChain cohort {cohort} lacks one recorded model"
        )
    evidence_seed_rules = {
        record.get("evidence_seed_rule") for record in latest.values()
    }
    ignore_tool_modes = {
        record.get("ignore_tool_usage") for record in latest.values()
    }
    if (
        len(evidence_seed_rules) != 1
        or None in evidence_seed_rules
        or len(ignore_tool_modes) != 1
        or None in ignore_tool_modes
    ):
        raise RuntimeError(
            f"LangChain cohort {cohort} mixes extraction configuration"
        )
    return recs, errors, {
        "mode": "fingerprinted-cohort",
        "cohort_fingerprint": cohort,
        "selected_records": len(latest),
        "extraction_dependency_versions": extraction_dependencies,
        "model": models.pop(),
        "evidence_seed_rule": evidence_seed_rules.pop(),
        "ignore_tool_usage": ignore_tool_modes.pop(),
    }


def load_checkpoint_metadata(
    cache_path: Path,
    metadata_path: Path = CHECKPOINT_METADATA,
) -> dict:
    if not metadata_path.is_file():
        raise RuntimeError(
            "LangChain checkpoint metadata is required for "
            f"{cache_path}"
        )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    checkpoint = metadata["checkpoint"]
    records = sum(
        1 for line in cache_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if (
        checkpoint["bytes"] != cache_path.stat().st_size
        or checkpoint["sha256"] != sha256_file(cache_path)
        or checkpoint["records"] != records
    ):
        raise RuntimeError(
            "LangChain checkpoint does not match its metadata"
        )
    return metadata


def source_database_provenance(
    published_metadata: dict | None = None,
    database_path: Path | None = None,
    root: Path | None = None,
) -> dict:
    """Return stable source provenance and verify a local copy when present."""
    database_path = database_path or DB
    root = root or ROOT
    relative_path = database_path.relative_to(root).as_posix()

    if published_metadata is not None:
        source = published_metadata.get("source_database")
        required = {"path", "bytes", "sha256"}
        if not isinstance(source, dict) or not required.issubset(source):
            raise RuntimeError(
                "published LangChain checkpoint metadata lacks complete "
                "source-database provenance"
            )
        canonical = {key: source[key] for key in ("path", "bytes", "sha256")}
        if canonical["path"] != relative_path:
            raise RuntimeError(
                "published LangChain source-database path does not match "
                "the configured database"
            )
        if database_path.is_file():
            actual = {
                "path": relative_path,
                "bytes": database_path.stat().st_size,
                "sha256": sha256_file(database_path),
            }
            if actual != canonical:
                raise RuntimeError(
                    "local LangChain source database does not match "
                    "published checkpoint metadata"
                )
        return canonical

    source = {"path": relative_path}
    if database_path.is_file():
        source.update({
            "bytes": database_path.stat().st_size,
            "sha256": sha256_file(database_path),
        })
    else:
        source["available_during_analysis"] = False
    return source


def analyze(
    requested_cohort: str | None = None,
    cache_path: Path = PUBLISHED_CACHE,
    checkpoint_metadata_path: Path = CHECKPOINT_METADATA,
) -> None:
    records = [
        json.loads(line)
        for line in cache_path.read_text(encoding="utf-8").splitlines()
    ]
    recs, errors, selection = select_analysis_records(
        records,
        requested_cohort,
    )

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

    analysis_dependency_versions = langchain_dependency_versions()
    published_metadata = None
    if selection["mode"] == "published-checkpoint":
        published_metadata = load_checkpoint_metadata(
            cache_path,
            checkpoint_metadata_path,
        )
        model = published_metadata["extraction_environment"]["model"]
        model_source = "hash-bound checkpoint metadata"
        extraction_environment = {
            "recorded": False,
            "metadata_source": "hash-bound checkpoint metadata",
            "model": model,
            "ignore_tool_usage": published_metadata["extraction_environment"][
                "ignore_tool_usage"
            ],
            "evidence_seed_rule": None,
            "evidence_seed_recorded": False,
            "dependency_versions": None,
        }
    else:
        model = selection["model"]
        model_source = "fingerprinted checkpoint records"
        extraction_environment = {
            "recorded": True,
            "metadata_source": "fingerprinted checkpoint records",
            "model": model,
            "ignore_tool_usage": selection["ignore_tool_usage"],
            "evidence_seed_rule": selection["evidence_seed_rule"],
            "evidence_seed_recorded": True,
            "dependency_versions": selection[
                "extraction_dependency_versions"
            ],
        }

    source_database = source_database_provenance(published_metadata)
    checkpoint = checkpoint_metadata(records)
    out = {
        "schema_version": 2,
        "toolchain": "langchain.LLMGraphTransformer",
        "model": model,
        "n_docs": len(recs),
        "provenance": {
            "producer": {
                "script": "scripts/run_langchain_toolchain.py",
                "analysis_command": (
                    "python scripts/run_langchain_toolchain.py --analyze-only"
                ),
                "future_extraction_evidence_seed_rule": EVIDENCE_SEED_RULE,
            },
            "source_database": source_database,
            "checkpoint": {
                "path": cache_path.relative_to(ROOT).as_posix(),
                "bytes": cache_path.stat().st_size,
                "sha256": sha256_file(cache_path),
                **checkpoint,
            },
            "model_source": model_source,
            "checkpoint_metadata": (
                {
                    "path": checkpoint_metadata_path.relative_to(
                        ROOT
                    ).as_posix(),
                    "sha256": sha256_file(checkpoint_metadata_path),
                }
                if published_metadata is not None
                else None
            ),
            "selection": selection,
            "analysis_environment_dependency_versions": (
                analysis_dependency_versions
            ),
            "extraction_environment": extraction_environment,
        },
        "summary": summary,
    }
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
    ap.add_argument(
        "--cohort",
        help="Analyze one explicit fingerprinted cohort (default: latest).",
    )
    ap.add_argument(
        "--cache",
        type=Path,
        help=(
            "Checkpoint path. Defaults to the published cache for "
            "--analyze-only and the local append-only cache for extraction."
        ),
    )
    ap.add_argument("--ignore-tool-usage", action="store_true",
                    help="Use JSON-prompt mode for models without function calling.")
    args = ap.parse_args()
    cohort = args.cohort
    cache_path = args.cache or (
        PUBLISHED_CACHE if args.analyze_only else LOCAL_CACHE
    )
    if not args.analyze_only:
        for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
            if not os.environ.get(var):
                raise SystemExit(f"{var} not set; source .env first")
        cohort = run_extraction(
            args.limit,
            args.workers,
            args.ignore_tool_usage,
            cache_path,
        )
    analyze(cohort, cache_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
