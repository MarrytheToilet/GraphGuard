#!/usr/bin/env python3
"""Run and analyze the controlled perturbation-magnitude experiment.

The experiment is deliberately isolated from the primary lineage databases.
For every registered document it makes one contemporaneous unmodified base
call, then compares that graph with four nested masking levels on each of:

* schema relation descriptions (excluding ``OTHER``);
* prompt task instructions (C1--C6);
* evidence sentence text.

An unmodified alternate-seed call provides a same-input resampling reference.
The three magnitude curves use the actual fraction of eligible whitespace-token
occurrences replaced by ``[MASK]``.  They measure controlled information
attenuation, not relation-count edits, natural paraphrases, or arbitrary
production configuration changes.

Examples
--------
Validate the registered inputs without making API calls::

    python scripts/run_magnitude_analysis.py --dry-run --docs 2

Run a two-document-per-corpus smoke test in an isolated checkpoint::

    python scripts/run_magnitude_analysis.py --run-controlled --docs 2 \
      --checkpoint /tmp/graphguard-magnitude-smoke.jsonl \
      --out-dir /tmp/graphguard-magnitude-smoke \
      --figure /tmp/graphguard-magnitude-smoke.png

Resume or run the registered 100-document cohorts::

    python scripts/run_magnitude_analysis.py --run-controlled

Rebuild reports and the figure from the checkpoint without API calls::

    python scripts/run_magnitude_analysis.py --analyze-only
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import random
import sqlite3
import statistics
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

from graphguard.contracts.metrics import edge_jaccard  # noqa: E402
from graphguard.experiments.controlled_magnitude import (  # noqa: E402
    NOMINAL_LEVELS,
    MaskedVariant,
    edge_dicts,
    evidence_variants,
    prompt_variants,
    schema_variants,
)
from graphguard.extraction.normalize import normalize_edges  # noqa: E402
from graphguard.extraction.prompts import (  # noqa: E402
    get_prompt_def,
    get_schema_def,
    load_yaml,
    render_prompt,
)
from graphguard.llm.json_repair import parse_json_lenient  # noqa: E402
from graphguard.llm.openai_client import OpenAICompatClient  # noqa: E402


EXPERIMENT_ID = "controlled-magnitude"
DESIGN_SEED = "graphguard-controlled-magnitude-20260727"
BASE_SEED = 7
RESAMPLE_SEED = 13
TEMPERATURE = 0.0
MAX_TOKENS = 8192
BOOTSTRAP_DRAWS = 2000

RUN_SPECS: dict[str, dict[str, str]] = {
    "docred__deepseek-v4-flash__300d": {
        "corpus": "docred",
        "label": "DocRED",
        "schema_id": "docred_full",
    },
    "redocred__deepseek-v4-flash__300d": {
        "corpus": "redocred",
        "label": "Re-DocRED",
        "schema_id": "docred_full",
    },
    "scierc__deepseek-v4-flash__100d": {
        "corpus": "scierc",
        "label": "SciERC",
        "schema_id": "scierc_full",
    },
    "cdr__deepseek-v4-flash__300d": {
        "corpus": "cdr",
        "label": "BC5CDR",
        "schema_id": "cdr_full",
    },
}
MAIN_RUNS = list(RUN_SPECS)

SAMPLES_PATH = ROOT / "reports" / "cross_run" / "sampled_document_ids.json"
PROMPTS_PATH = ROOT / "configs" / "prompts.yaml"
SCHEMAS_PATH = ROOT / "configs" / "schemas.yaml"
DEFAULT_CHECKPOINT = (
    ROOT / "data" / "processed" / "magnitude" / "controlled_magnitude.jsonl"
)
DEFAULT_OUT_DIR = ROOT / "reports" / "cross_run"
DEFAULT_FIGURE = ROOT / "assets" / "figures" / "fig_magnitude.png"

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _endpoint_fingerprint() -> str:
    """Hash endpoint metadata without publishing the endpoint itself."""
    return _sha256_text(os.environ.get("OPENAI_BASE_URL", ""))


def _record_key(corpus: str, document_id: str, condition_id: str) -> str:
    return "\x1f".join((corpus, document_id, condition_id))


class JsonlCheckpoint:
    """Thread-safe append-only checkpoint with fingerprint validation."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.records: dict[str, dict] = {}
        if self.path.exists():
            for lineno, line in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid checkpoint JSON at {self.path}:{lineno}"
                    ) from exc
                key = _record_key(
                    record["corpus"],
                    record["document_id"],
                    record["condition_id"],
                )
                self.records[key] = record

    def get(self, corpus: str, document_id: str, condition_id: str) -> dict | None:
        with self.lock:
            row = self.records.get(_record_key(corpus, document_id, condition_id))
            return copy.deepcopy(row) if row is not None else None

    def append(self, record: dict) -> None:
        key = _record_key(
            record["corpus"], record["document_id"], record["condition_id"]
        )
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self.lock:
            existing = self.records.get(key)
            if (
                existing is not None
                and existing.get("input_sha256") != record.get("input_sha256")
            ):
                raise ValueError(
                    f"checkpoint fingerprint mismatch for "
                    f"{record['corpus']}/{record['document_id']}/"
                    f"{record['condition_id']}"
                )
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
            self.records[key] = copy.deepcopy(record)


def _validate_checkpoint_manifest(checkpoint_path: Path, manifest: dict) -> Path:
    """Fail closed before any checkpoint record can be reused."""
    checkpoint_path = Path(checkpoint_path)
    manifest_path = checkpoint_path.with_suffix(".manifest.json")
    checkpoint_nonempty = (
        checkpoint_path.exists() and checkpoint_path.stat().st_size > 0
    )
    if checkpoint_nonempty and not manifest_path.exists():
        raise ValueError(
            f"non-empty checkpoint has no manifest: {checkpoint_path}"
        )
    if not manifest_path.exists():
        return manifest_path

    existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    immutable_keys = (
        "experiment_id",
        "design_seed",
        "nominal_levels",
        "base_seed",
        "resample_seed",
        "temperature",
        "max_tokens",
        "model_id",
        "endpoint_sha256",
        "document_ids",
        "source_db_sha256",
        "input_sha256",
        "code_sha256",
    )
    mismatches = [
        key
        for key in immutable_keys
        if existing_manifest.get(key) != manifest.get(key)
    ]
    if mismatches:
        raise ValueError(
            f"checkpoint manifest mismatch in immutable fields: {mismatches}"
        )
    return manifest_path


def _assert_record_fingerprint(record: dict, expected: dict) -> None:
    """Reject a resumed endpoint if any registered condition field differs."""
    mismatches = [
        key for key, value in expected.items() if record.get(key) != value
    ]
    if mismatches:
        raise ValueError(
            f"checkpoint record fingerprint mismatch for "
            f"{record.get('corpus')}/{record.get('document_id')}/"
            f"{record.get('condition_id')}: {mismatches}"
        )


def _source_db(run: str) -> Path:
    return ROOT / "data" / "processed" / "runs" / run / f"{run}.db"


def _registered_ids(run: str, limit: int) -> list[str]:
    samples = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    ids = list(samples["runs"][run]["document_ids"])
    if len(ids) < limit:
        raise ValueError(f"{run}: requested {limit} docs but only {len(ids)} registered")
    return ids[:limit]


def _load_documents(run: str, limit: int) -> list[dict]:
    db = _source_db(run)
    if not db.exists():
        raise FileNotFoundError(db)
    requested = _registered_ids(run, limit)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out: list[dict] = []
    try:
        for document_id in requested:
            document = conn.execute(
                "SELECT * FROM documents WHERE document_id=?", (document_id,)
            ).fetchone()
            if document is None:
                raise ValueError(f"{run}: registered document missing: {document_id}")
            sentences = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM sentences WHERE document_id=? "
                    "ORDER BY sentence_index",
                    (document_id,),
                )
            ]
            entities = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM entities WHERE document_id=? ORDER BY entity_id",
                    (document_id,),
                )
            ]
            if not sentences:
                raise ValueError(f"{run}/{document_id}: no evidence sentences")
            if not entities:
                raise ValueError(f"{run}/{document_id}: no candidate entities")
            out.append(
                {
                    "run": run,
                    "corpus": RUN_SPECS[run]["corpus"],
                    "document": dict(document),
                    "sentences": sentences,
                    "entities": entities,
                }
            )
    finally:
        conn.close()
    return out


def _minimal_edges(edges: Iterable[dict]) -> list[dict]:
    fields = (
        "subject_entity_id",
        "subject_name",
        "relation",
        "object_entity_id",
        "object_name",
        "evidence_sentence_ids",
        "confidence",
    )
    return [{field: edge.get(field) for field in fields} for edge in edges]


def _validate_parsed(parsed: Any) -> tuple[bool, str]:
    if not isinstance(parsed, dict):
        return False, "top-level JSON is not an object"
    if "edges" not in parsed:
        return False, "missing edges field"
    if not isinstance(parsed["edges"], list):
        return False, "edges field is not a list"
    return True, ""


def _call_and_normalize(
    *,
    client: OpenAICompatClient,
    prompt_text: str,
    document: dict,
    sentences: Sequence[dict],
    entities: Sequence[dict],
    schema_def: dict,
    seed: int,
    condition_id: str,
) -> dict:
    responses: list[dict] = []
    try:
        first = client.complete_json(
            prompt_text,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            seed=seed,
        )
        responses.append(
            {
                "text": first.text,
                "model": first.model,
                "prompt_tokens": first.prompt_tokens,
                "completion_tokens": first.completion_tokens,
                "latency_ms": first.latency_ms,
            }
        )
    except Exception as exc:
        return {
            "status": "api_error",
            "error": f"{exc.__class__.__name__}: {exc}",
            "responses": responses,
            "edges": [],
            "explicit_empty_graph": False,
            "normalization_empty_graph": False,
        }

    try:
        parsed = parse_json_lenient(responses[0]["text"])
        valid, validation_error = _validate_parsed(parsed)
    except Exception as exc:
        parsed = None
        valid = False
        validation_error = f"{exc.__class__.__name__}: {exc}"
    if not valid or parsed is None:
        return {
            "status": "parse_error",
            "error": validation_error or "invalid extraction JSON",
            "responses": responses,
            "edges": [],
            "explicit_empty_graph": False,
            "normalization_empty_graph": False,
        }

    event_id = (
        f"controlled::{document['document_id']}::{condition_id}::"
        f"{_sha256_text(prompt_text)[:12]}"
    )
    normalized = normalize_edges(
        parsed,
        event_id=event_id,
        document_id=document["document_id"],
        sentences=list(sentences),
        entities=list(entities),
        schema_def=schema_def,
    )
    edges = _minimal_edges(edge_dicts(normalized))
    raw_edge_count = len(parsed["edges"])
    return {
        "status": "ok",
        "error": "",
        "responses": responses,
        "raw_edge_count": raw_edge_count,
        "edges": edges,
        "explicit_empty_graph": raw_edge_count == 0,
        "normalization_empty_graph": raw_edge_count > 0 and len(edges) == 0,
    }


def _condition_record(
    *,
    run: str,
    corpus: str,
    document_id: str,
    condition_id: str,
    family: str,
    prompt_text: str,
    seed: int,
    result: dict,
    nominal_magnitude: float | None,
    actual_magnitude: float | None,
    changed: int | None,
    eligible: int | None,
    changed_digest: str | None,
    call_order: int,
) -> dict:
    responses = result.get("responses", [])
    last = responses[-1] if responses else {}
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "design_seed": DESIGN_SEED,
        "run": run,
        "corpus": corpus,
        "document_id": document_id,
        "condition_id": condition_id,
        "family": family,
        "nominal_magnitude": nominal_magnitude,
        "actual_magnitude": actual_magnitude,
        "changed": changed,
        "eligible": eligible,
        "changed_digest": changed_digest,
        "input_sha256": _sha256_text(prompt_text),
        "call_order": call_order,
        "model_id": last.get("model") or os.environ.get("OPENAI_MODEL"),
        "endpoint_sha256": _endpoint_fingerprint(),
        "temperature": TEMPERATURE,
        "seed": seed,
        "max_tokens": MAX_TOKENS,
        "status": result["status"],
        "error": result.get("error", ""),
        "parse_attempts": len(responses),
        "prompt_tokens": last.get("prompt_tokens"),
        "completion_tokens": last.get("completion_tokens"),
        "latency_ms": sum(
            int(response.get("latency_ms") or 0) for response in responses
        ),
        "raw_edge_count": result.get("raw_edge_count"),
        "edges": result.get("edges", []),
        "explicit_empty_graph": bool(result.get("explicit_empty_graph", False)),
        "normalization_empty_graph": bool(
            result.get("normalization_empty_graph", False)
        ),
        "responses": responses,
        "created_at": _utc_now(),
    }


def _expected_record_fingerprint(
    *,
    run: str,
    corpus: str,
    document_id: str,
    condition_id: str,
    family: str,
    prompt_text: str,
    seed: int,
    nominal_magnitude: float | None,
    actual_magnitude: float | None,
    changed: int | None,
    eligible: int | None,
    changed_digest: str | None,
) -> dict:
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "design_seed": DESIGN_SEED,
        "run": run,
        "corpus": corpus,
        "document_id": document_id,
        "condition_id": condition_id,
        "family": family,
        "nominal_magnitude": nominal_magnitude,
        "actual_magnitude": actual_magnitude,
        "changed": changed,
        "eligible": eligible,
        "changed_digest": changed_digest,
        "input_sha256": _sha256_text(prompt_text),
        "model_id": os.environ.get("OPENAI_MODEL"),
        "endpoint_sha256": _endpoint_fingerprint(),
        "temperature": TEMPERATURE,
        "seed": seed,
        "max_tokens": MAX_TOKENS,
    }


def _variant_conditions(
    job: dict,
    prompt_def: dict,
    schema_def: dict,
) -> list[dict]:
    corpus = job["corpus"]
    document_id = job["document"]["document_id"]
    sentences = job["sentences"]
    schema_levels = schema_variants(
        schema_def,
        corpus=corpus,
        document_id=document_id,
        design_seed=DESIGN_SEED,
    )
    prompt_levels = prompt_variants(
        prompt_def,
        corpus=corpus,
        document_id=document_id,
        design_seed=DESIGN_SEED,
    )
    evidence_levels = evidence_variants(
        sentences,
        corpus=corpus,
        document_id=document_id,
        design_seed=DESIGN_SEED,
    )

    conditions: list[dict] = []
    for family, variants in (
        ("schema", schema_levels),
        ("prompt", prompt_levels),
        ("evidence", evidence_levels),
    ):
        for variant in variants:
            plan = variant.plan
            condition = {
                "condition_id": f"{family}:q{plan.nominal_magnitude:.2f}",
                "family": family,
                "nominal_magnitude": plan.nominal_magnitude,
                "actual_magnitude": plan.actual_magnitude,
                "changed": plan.changed,
                "eligible": plan.eligible,
                "changed_digest": plan.changed_digest,
                "prompt_def": variant.payload if family == "prompt" else prompt_def,
                "schema_def": variant.payload if family == "schema" else schema_def,
                "sentences": variant.payload if family == "evidence" else sentences,
                "seed": BASE_SEED,
            }
            conditions.append(condition)

    conditions.append(
        {
            "condition_id": "resample:alternate-seed",
            "family": "resample",
            "nominal_magnitude": None,
            "actual_magnitude": 0.0,
            "changed": 0,
            "eligible": None,
            "changed_digest": None,
            "prompt_def": prompt_def,
            "schema_def": schema_def,
            "sentences": sentences,
            "seed": RESAMPLE_SEED,
        }
    )

    # Randomize endpoint order deterministically while keeping the shared base
    # first. This avoids always running one family earlier in the time window.
    def condition_order(condition: dict) -> str:
        return _sha256_text(
            "\x1f".join(
                (
                    DESIGN_SEED,
                    corpus,
                    document_id,
                    condition["condition_id"],
                    "call-order",
                )
            )
        )

    conditions.sort(key=condition_order)

    base_hash = _sha256_text(
        render_prompt(
            prompt_def,
            schema_def,
            sentences,
            job["entities"],
        )
    )
    seen_hashes: set[str] = set()
    for condition in conditions:
        prompt_text = render_prompt(
            condition["prompt_def"],
            condition["schema_def"],
            condition["sentences"],
            job["entities"],
        )
        condition["prompt_text"] = prompt_text
        input_hash = _sha256_text(prompt_text)
        if condition["family"] != "resample" and input_hash == base_hash:
            raise ValueError(
                f"{corpus}/{document_id}/{condition['condition_id']}: "
                "nonzero condition rendered as a no-op"
            )
        if condition["family"] != "resample":
            if input_hash in seen_hashes:
                raise ValueError(
                    f"{corpus}/{document_id}: duplicate variant input hash"
                )
            seen_hashes.add(input_hash)
        elif input_hash != base_hash:
            raise ValueError(
                f"{corpus}/{document_id}: resample input differs from base"
            )
    return conditions


def _process_document(
    job: dict,
    *,
    prompt_def: dict,
    schema_def: dict,
    checkpoint: JsonlCheckpoint,
    retry_failures: bool,
) -> dict:
    run = job["run"]
    corpus = job["corpus"]
    document = job["document"]
    document_id = document["document_id"]
    entities = job["entities"]
    sentences = job["sentences"]
    client = OpenAICompatClient(timeout=300.0, json_mode=True)

    base_prompt = render_prompt(prompt_def, schema_def, sentences, entities)
    base_expected = _expected_record_fingerprint(
        run=run,
        corpus=corpus,
        document_id=document_id,
        condition_id="base",
        family="base",
        prompt_text=base_prompt,
        seed=BASE_SEED,
        nominal_magnitude=0.0,
        actual_magnitude=0.0,
        changed=0,
        eligible=None,
        changed_digest=None,
    )
    base_existing = checkpoint.get(corpus, document_id, "base")
    if (
        base_existing is None
        or (retry_failures and base_existing.get("status") != "ok")
    ):
        base_result = _call_and_normalize(
            client=client,
            prompt_text=base_prompt,
            document=document,
            sentences=sentences,
            entities=entities,
            schema_def=schema_def,
            seed=BASE_SEED,
            condition_id="base",
        )
        base_record = _condition_record(
            run=run,
            corpus=corpus,
            document_id=document_id,
            condition_id="base",
            family="base",
            prompt_text=base_prompt,
            seed=BASE_SEED,
            result=base_result,
            nominal_magnitude=0.0,
            actual_magnitude=0.0,
            changed=0,
            eligible=None,
            changed_digest=None,
            call_order=0,
        )
        checkpoint.append(base_record)
    else:
        _assert_record_fingerprint(base_existing, base_expected)
        base_record = base_existing

    if base_record.get("status") != "ok":
        return {
            "corpus": corpus,
            "document_id": document_id,
            "status": "base_failed",
            "new_calls": int(base_existing is None),
        }

    base_edges = base_record.get("edges", [])
    base_relation_ids = {
        relation["id"] for relation in schema_def.get("relations", [])
    }
    new_calls = int(base_existing is None)
    failed = 0
    conditions = _variant_conditions(job, prompt_def, schema_def)
    for call_order, condition in enumerate(conditions, start=1):
        condition_id = condition["condition_id"]
        expected = _expected_record_fingerprint(
            run=run,
            corpus=corpus,
            document_id=document_id,
            condition_id=condition_id,
            family=condition["family"],
            prompt_text=condition["prompt_text"],
            seed=condition["seed"],
            nominal_magnitude=condition["nominal_magnitude"],
            actual_magnitude=condition["actual_magnitude"],
            changed=condition["changed"],
            eligible=condition["eligible"],
            changed_digest=condition["changed_digest"],
        )
        existing = checkpoint.get(corpus, document_id, condition_id)
        if existing is not None and not (
            retry_failures and existing.get("status") != "ok"
        ):
            _assert_record_fingerprint(existing, expected)
            continue
        result = _call_and_normalize(
            client=client,
            prompt_text=condition["prompt_text"],
            document=document,
            sentences=condition["sentences"],
            entities=entities,
            schema_def=condition["schema_def"],
            seed=condition["seed"],
            condition_id=condition_id,
        )
        record = _condition_record(
            run=run,
            corpus=corpus,
            document_id=document_id,
            condition_id=condition_id,
            family=condition["family"],
            prompt_text=condition["prompt_text"],
            seed=condition["seed"],
            result=result,
            nominal_magnitude=condition["nominal_magnitude"],
            actual_magnitude=condition["actual_magnitude"],
            changed=condition["changed"],
            eligible=condition["eligible"],
            changed_digest=condition["changed_digest"],
            call_order=call_order,
        )
        if record["status"] == "ok":
            record["drift"] = 1.0 - edge_jaccard(
                base_edges,
                record["edges"],
                base_relation_ids=base_relation_ids,
            )
        else:
            record["drift"] = None
            failed += 1
        checkpoint.append(record)
        new_calls += 1

    return {
        "corpus": corpus,
        "document_id": document_id,
        "status": "ok" if failed == 0 else "partial",
        "new_calls": new_calls,
        "failed": failed,
    }


def _preflight(
    runs: Sequence[str],
    docs: int,
    *,
    prompt_def: dict,
    schemas: dict[str, dict],
) -> tuple[list[dict], dict]:
    jobs: list[dict] = []
    source_hashes = {}
    for run in runs:
        if run not in RUN_SPECS:
            raise ValueError(f"unknown run: {run}")
        source_hashes[run] = _sha256_file(_source_db(run))
        loaded = _load_documents(run, docs)
        schema_def = schemas[RUN_SPECS[run]["schema_id"]]
        for job in loaded:
            conditions = _variant_conditions(job, prompt_def, schema_def)
            if len(conditions) != 13:
                raise AssertionError(
                    f"{run}/{job['document']['document_id']}: expected 13 endpoints"
                )
        jobs.extend(loaded)

    manifest = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "design": "nested token-level information attenuation",
        "design_seed": DESIGN_SEED,
        "nominal_levels": list(NOMINAL_LEVELS),
        "base_seed": BASE_SEED,
        "resample_seed": RESAMPLE_SEED,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "model_id": os.environ.get("OPENAI_MODEL"),
        "endpoint_sha256": _endpoint_fingerprint(),
        "runs": runs,
        "documents_per_run": docs,
        "document_ids": {
            run: [job["document"]["document_id"] for job in jobs if job["run"] == run]
            for run in runs
        },
        "source_db_sha256": source_hashes,
        "input_sha256": {
            str(PROMPTS_PATH.relative_to(ROOT)): _sha256_file(PROMPTS_PATH),
            str(SCHEMAS_PATH.relative_to(ROOT)): _sha256_file(SCHEMAS_PATH),
            str(SAMPLES_PATH.relative_to(ROOT)): _sha256_file(SAMPLES_PATH),
        },
        "code_sha256": {
            "scripts/run_magnitude_analysis.py": _sha256_file(Path(__file__)),
            "graphguard/experiments/controlled_magnitude.py": _sha256_file(
                ROOT / "graphguard" / "experiments" / "controlled_magnitude.py"
            ),
        },
        "families": {
            "schema": "non-OTHER relation-description token masking",
            "prompt": "C1-C6 instruction-token masking",
            "evidence": "sentence-text token masking",
            "resample": "same-input alternate-seed reference",
        },
        "pairing": "one contemporaneous base per document shared by all endpoints",
        "created_at": _utc_now(),
    }
    return jobs, manifest


def run_controlled(args: argparse.Namespace) -> dict:
    prompts = load_yaml(PROMPTS_PATH)
    schemas_yaml = load_yaml(SCHEMAS_PATH)
    prompt_def = get_prompt_def(prompts, "base_v1")
    schemas = {
        schema["id"]: schema for schema in schemas_yaml.get("schemas", [])
    }
    jobs, manifest = _preflight(
        args.runs, args.docs, prompt_def=prompt_def, schemas=schemas
    )
    print(
        f"[preflight] runs={len(args.runs)} docs={len(jobs)} "
        f"endpoints={len(jobs) * 14} model={manifest['model_id']}",
        flush=True,
    )
    if args.dry_run:
        return manifest

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available")
    if not os.environ.get("OPENAI_BASE_URL"):
        raise RuntimeError("OPENAI_BASE_URL is not available")
    if os.environ.get("OPENAI_MODEL") != "deepseek-v4-flash":
        raise RuntimeError(
            "controlled cohort is registered for OPENAI_MODEL=deepseek-v4-flash"
        )

    manifest_path = _validate_checkpoint_manifest(args.checkpoint, manifest)
    if not manifest_path.exists():
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    checkpoint = JsonlCheckpoint(args.checkpoint)

    completed = 0
    total_new_calls = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = []
        for job in jobs:
            schema_def = schemas[RUN_SPECS[job["run"]]["schema_id"]]
            futures.append(
                executor.submit(
                    _process_document,
                    job,
                    prompt_def=prompt_def,
                    schema_def=schema_def,
                    checkpoint=checkpoint,
                    retry_failures=args.retry_failures,
                )
            )
        for future in as_completed(futures):
            result = future.result()
            completed += 1
            total_new_calls += result.get("new_calls", 0)
            print(
                f"[progress] {completed}/{len(jobs)} "
                f"{result['corpus']}/{result['document_id']} "
                f"status={result['status']} new_calls={result.get('new_calls', 0)}",
                flush=True,
            )
    print(
        f"[run complete] documents={completed} new_calls={total_new_calls} "
        f"checkpoint={args.checkpoint}",
        flush=True,
    )
    return manifest


def _bootstrap_mean(
    values_by_doc: dict[str, float],
    *,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = 0,
) -> tuple[float | None, list[float | None]]:
    if not values_by_doc:
        return None, [None, None]
    docs = sorted(values_by_doc)
    values = [values_by_doc[doc] for doc in docs]
    mean = statistics.mean(values)
    if len(values) == 1:
        return mean, [mean, mean]
    rng = random.Random(seed)
    boot = []
    for _ in range(draws):
        sample = [values[rng.randrange(len(values))] for _ in values]
        boot.append(statistics.mean(sample))
    boot.sort()
    lo = boot[math.floor(0.025 * (len(boot) - 1))]
    hi = boot[math.ceil(0.975 * (len(boot) - 1))]
    return mean, [lo, hi]


def _within_document_slope(
    panels: Sequence[Sequence[tuple[float, float]]],
) -> float:
    """Return the pooled document-fixed-effects slope for complete panels."""
    numerator = 0.0
    denominator = 0.0
    for panel in panels:
        if len(panel) != len(NOMINAL_LEVELS):
            raise ValueError("dose-response panels must contain all four levels")
        x_mean = statistics.mean(x for x, _ in panel)
        y_mean = statistics.mean(y for _, y in panel)
        numerator += sum(
            (x - x_mean) * (y - y_mean) for x, y in panel
        )
        denominator += sum((x - x_mean) ** 2 for x, _ in panel)
    if denominator <= 0:
        raise ValueError("dose-response slope has no within-document variation")
    return numerator / denominator


def _complete_dose_panels(
    *,
    docs: Sequence[str],
    bases: dict[str, dict],
    rows_by_level: dict[float, dict[str, dict]],
) -> dict[str, list[tuple[float, float]]]:
    """Collect documents with a valid base and all four valid dose endpoints."""
    panels: dict[str, list[tuple[float, float]]] = {}
    for document_id in docs:
        if bases.get(document_id, {}).get("status") != "ok":
            continue
        panel: list[tuple[float, float]] = []
        for q in NOMINAL_LEVELS:
            row = rows_by_level[q].get(document_id)
            if (
                row is None
                or row.get("status") != "ok"
                or row.get("actual_magnitude") is None
            ):
                break
            panel.append(
                (float(row["actual_magnitude"]), float(row["drift"]))
            )
        if len(panel) == len(NOMINAL_LEVELS):
            panels[document_id] = panel
    return panels


def _dose_response_summary(
    panels_by_doc: dict[str, list[tuple[float, float]]],
    *,
    seed: int,
    draws: int = BOOTSTRAP_DRAWS,
) -> dict:
    """Summarize drift per +0.10 actual masking with a document bootstrap."""
    docs = sorted(panels_by_doc)
    if not docs:
        raise ValueError("dose-response summary has no complete documents")
    point = 0.10 * _within_document_slope(
        [panels_by_doc[document_id] for document_id in docs]
    )
    rng = random.Random(seed)
    boot = []
    for _ in range(draws):
        sample = [
            panels_by_doc[docs[rng.randrange(len(docs))]]
            for _ in docs
        ]
        boot.append(0.10 * _within_document_slope(sample))
    boot.sort()
    lo = boot[math.floor(0.025 * (len(boot) - 1))]
    hi = boot[math.ceil(0.975 * (len(boot) - 1))]
    return {
        "estimator": "pooled document-fixed-effects OLS",
        "x": "actual_magnitude",
        "unit": "graph drift per +0.10 actual masked-token fraction",
        "complete_documents": len(docs),
        "observations": len(docs) * len(NOMINAL_LEVELS),
        "slope_per_0_10": point,
        "ci95": [lo, hi],
        "bootstrap": {
            "unit": "document",
            "draws": draws,
            "seed": seed,
        },
        "missing_policy": (
            "valid base and all four valid dose endpoints; no failure imputation"
        ),
    }


def _load_checkpoint_records(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    records = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{lineno}") from exc
    latest: dict[str, dict] = {}
    for record in records:
        latest[
            _record_key(
                record["corpus"], record["document_id"], record["condition_id"]
            )
        ] = record
    return list(latest.values())


def _cell_summary(
    *,
    docs: Sequence[str],
    bases: dict[str, dict],
    rows: dict[str, dict],
    seed: int,
) -> dict:
    valid: dict[str, float] = {}
    actual = []
    parse_failures = api_failures = missing_records = unavailable_base = 0
    explicit_empty = normalization_empty = 0
    failure_as_harm: dict[str, float] = {}
    for document_id in docs:
        base = bases.get(document_id)
        row = rows.get(document_id)
        if base is None or base.get("status") != "ok":
            unavailable_base += 1
            continue
        if row is None:
            missing_records += 1
            failure_as_harm[document_id] = 1.0
            continue
        if row.get("status") == "parse_error":
            parse_failures += 1
            failure_as_harm[document_id] = 1.0
            continue
        if row.get("status") != "ok":
            api_failures += 1
            failure_as_harm[document_id] = 1.0
            continue
        drift = float(row["drift"])
        valid[document_id] = drift
        failure_as_harm[document_id] = drift
        if row.get("actual_magnitude") is not None:
            actual.append(float(row["actual_magnitude"]))
        if row.get("explicit_empty_graph"):
            explicit_empty += 1
        if row.get("normalization_empty_graph"):
            normalization_empty += 1
    mean, ci = _bootstrap_mean(valid, seed=seed)
    sensitivity_mean, _ = _bootstrap_mean(failure_as_harm, seed=seed + 991)
    return {
        "attempted": len(docs),
        "base_unavailable": unavailable_base,
        "valid": len(valid),
        "parse_failures": parse_failures,
        "api_failures": api_failures,
        "missing_records": missing_records,
        "explicit_empty_graphs": explicit_empty,
        "normalization_empty_graphs": normalization_empty,
        "mean_drift": mean,
        "median_drift": statistics.median(valid.values()) if valid else None,
        "ci95": ci,
        "actual_magnitude_mean": statistics.mean(actual) if actual else None,
        "actual_magnitude_min": min(actual) if actual else None,
        "actual_magnitude_max": max(actual) if actual else None,
        "failure_as_harm_mean_drift": sensitivity_mean,
        "values_by_document": valid,
    }


def analyze_checkpoint(
    checkpoint_path: Path,
    *,
    runs: Sequence[str],
    docs_per_run: int,
    out_dir: Path,
) -> dict[str, dict]:
    records = _load_checkpoint_records(checkpoint_path)
    by_key = {
        _record_key(row["corpus"], row["document_id"], row["condition_id"]): row
        for row in records
    }
    results: dict[str, dict] = {}
    out_dir.mkdir(parents=True, exist_ok=True)

    for run_index, run in enumerate(runs):
        spec = RUN_SPECS[run]
        corpus = spec["corpus"]
        docs = _registered_ids(run, docs_per_run)
        bases = {
            doc: by_key.get(_record_key(corpus, doc, "base"))
            for doc in docs
        }
        bases = {doc: row for doc, row in bases.items() if row is not None}
        families: dict[str, dict] = {}
        pair_rows: list[dict] = []
        for family_index, family in enumerate(("schema", "prompt", "evidence")):
            levels: dict[str, dict] = {}
            rows_by_level: dict[float, dict[str, dict]] = {}
            for level_index, q in enumerate(NOMINAL_LEVELS):
                condition_id = f"{family}:q{q:.2f}"
                rows = {
                    doc: by_key.get(_record_key(corpus, doc, condition_id))
                    for doc in docs
                }
                rows = {doc: row for doc, row in rows.items() if row is not None}
                rows_by_level[q] = rows
                summary = _cell_summary(
                    docs=docs,
                    bases=bases,
                    rows=rows,
                    seed=1000 * run_index + 100 * family_index + level_index,
                )
                values = summary.pop("values_by_document")
                levels[f"{q:.2f}"] = summary
                for doc, drift in values.items():
                    source = rows[doc]
                    pair_rows.append(
                        {
                            "document_id": doc,
                            "family": family,
                            "nominal_magnitude": q,
                            "actual_magnitude": source.get("actual_magnitude"),
                            "changed": source.get("changed"),
                            "eligible": source.get("eligible"),
                            "drift": drift,
                            "explicit_empty_graph": source.get(
                                "explicit_empty_graph"
                            ),
                            "normalization_empty_graph": source.get(
                                "normalization_empty_graph"
                            ),
                            "parse_attempts": source.get("parse_attempts"),
                            "input_sha256": source.get("input_sha256"),
                            "changed_digest": source.get("changed_digest"),
                        }
                    )

            low_rows = rows_by_level[NOMINAL_LEVELS[0]]
            high_rows = rows_by_level[NOMINAL_LEVELS[-1]]
            paired_delta = {}
            monotone = {}
            for doc in docs:
                low = low_rows.get(doc)
                high = high_rows.get(doc)
                if (
                    bases.get(doc, {}).get("status") == "ok"
                    and low is not None
                    and high is not None
                    and low.get("status") == "ok"
                    and high.get("status") == "ok"
                ):
                    paired_delta[doc] = float(high["drift"]) - float(low["drift"])
                doc_values = []
                for q in NOMINAL_LEVELS:
                    row = rows_by_level[q].get(doc)
                    if row is None or row.get("status") != "ok":
                        break
                    doc_values.append(float(row["drift"]))
                if len(doc_values) == len(NOMINAL_LEVELS):
                    monotone[doc] = all(
                        left <= right
                        for left, right in zip(doc_values, doc_values[1:])
                    )
            delta_mean, delta_ci = _bootstrap_mean(
                paired_delta,
                seed=20000 + 1000 * run_index + family_index,
            )
            slope_seed = 40000 + 1000 * run_index + family_index
            dose_response = _dose_response_summary(
                _complete_dose_panels(
                    docs=docs,
                    bases=bases,
                    rows_by_level=rows_by_level,
                ),
                seed=slope_seed,
            )
            families[family] = {
                "levels": levels,
                "paired_high_minus_low": {
                    "n": len(paired_delta),
                    "mean": delta_mean,
                    "ci95": delta_ci,
                },
                "dose_response_slope": dose_response,
                "monotone_document_fraction": (
                    sum(monotone.values()) / len(monotone) if monotone else None
                ),
                "monotone_document_n": len(monotone),
            }

        reference_rows = {
            doc: by_key.get(
                _record_key(corpus, doc, "resample:alternate-seed")
            )
            for doc in docs
        }
        reference_rows = {
            doc: row for doc, row in reference_rows.items() if row is not None
        }
        reference = _cell_summary(
            docs=docs,
            bases=bases,
            rows=reference_rows,
            seed=30000 + run_index,
        )
        reference.pop("values_by_document")
        base_status = {
            "attempted": len(docs),
            "valid": sum(row.get("status") == "ok" for row in bases.values()),
            "parse_failures": sum(
                row.get("status") == "parse_error" for row in bases.values()
            ),
            "api_failures": sum(
                row.get("status") == "api_error" for row in bases.values()
            ),
            "missing_records": len(docs) - len(bases),
            "explicit_empty_graphs": sum(
                row.get("status") == "ok" and row.get("explicit_empty_graph")
                for row in bases.values()
            ),
            "normalization_empty_graphs": sum(
                row.get("status") == "ok"
                and row.get("normalization_empty_graph")
                for row in bases.values()
            ),
        }
        result = {
            "schema_version": 2,
            "experiment_id": EXPERIMENT_ID,
            "run": run,
            "corpus": corpus,
            "corpus_label": spec["label"],
            "design": {
                "operator": "nested token-level information attenuation",
                "nominal_levels": list(NOMINAL_LEVELS),
                "pairing": "one contemporaneous base per document",
                "reference": "same-input alternate-seed resample",
                "claim_scope": (
                    "schema-description, prompt-instruction, and evidence-text "
                    "attenuation only"
                ),
            },
            "n_documents": len(docs),
            "base": base_status,
            "families": families,
            "resample_reference": reference,
            "n_valid_pairs": len(pair_rows),
            "pairs": pair_rows,
        }
        out_path = out_dir / f"magnitude_{run}.json"
        out_path.write_text(
            json.dumps(result, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[report] {out_path}", flush=True)
        results[run] = result
    return results


def make_figure(results: dict[str, dict], output: Path) -> None:
    """Render four corpus panels with three magnitude curves and one reference."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from graphguard.viz import style as S

    # Native single-column 1x4 canvas, matching the paper's AUROC small
    # multiples so typography and strokes render at their declared size.
    S.apply_rc(font_size=8)
    plt.rcParams.update(
        {
            "axes.linewidth": 0.7,
            "axes.labelsize": 7.5,
            "axes.titlesize": 8,
            "axes.titleweight": "normal",
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "legend.fontsize": 6.5,
            "legend.frameon": False,
            "lines.linewidth": 1.1,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
            "xtick.major.size": 2.5,
            "ytick.major.size": 2.5,
        }
    )
    fig, axes = plt.subplots(
        1,
        4,
        figsize=(3.5, 1.22),
        sharex=True,
        sharey=True,
        gridspec_kw={"wspace": 0.16},
    )
    series = [
        ("schema", "Schema", S.BLUE_DARK, "o", "-"),
        ("prompt", "Prompt", S.PINK_DARK, "s", "--"),
        ("evidence", "Evidence", S.GREEN_DARK, "^", "-."),
    ]
    ordered_runs = [run for run in MAIN_RUNS if run in results]
    for ax, run in zip(axes, ordered_runs):
        result = results[run]
        for series_index, (family, label, color, marker, linestyle) in enumerate(
            series
        ):
            levels = result["families"][family]["levels"]
            xs = np.array(
                [
                    levels[f"{q:.2f}"]["actual_magnitude_mean"]
                    for q in NOMINAL_LEVELS
                ],
                dtype=float,
            )
            means = np.array(
                [levels[f"{q:.2f}"]["mean_drift"] for q in NOMINAL_LEVELS],
                dtype=float,
            )
            lows = np.array(
                [levels[f"{q:.2f}"]["ci95"][0] for q in NOMINAL_LEVELS],
                dtype=float,
            )
            highs = np.array(
                [levels[f"{q:.2f}"]["ci95"][1] for q in NOMINAL_LEVELS],
                dtype=float,
            )
            ax.plot(
                xs,
                means,
                color=color,
                marker=marker,
                markersize=2.0,
                markerfacecolor="white",
                markeredgewidth=0.75,
                linestyle=linestyle,
                linewidth=1.05,
                label=label,
                zorder=3,
            )
            ax.fill_between(
                xs, lows, highs, color=color, alpha=0.12, linewidth=0
            )
            slope = result["families"][family]["dose_response_slope"][
                "slope_per_0_10"
            ]
            slope_label = f"{family[0].upper()} {slope:+.4f}"
            slope_label = slope_label.replace("+0.", "+.").replace("-0.", "-.")
            label_y = 0.95 - 0.13 * series_index
            if result["corpus_label"] == "SciERC" and family == "evidence":
                label_y = 0.40
            ax.text(
                0.04,
                label_y,
                slope_label,
                transform=ax.transAxes,
                color=color,
                fontsize=5.6,
                ha="left",
                va="top",
                zorder=5,
            )
        reference = result["resample_reference"]
        ref_mean = reference["mean_drift"]
        if ref_mean is not None:
            ax.axhline(
                ref_mean,
                color=S.GRAY,
                linestyle=":",
                linewidth=0.75,
                label="Alt. seed",
                zorder=2,
            )
            if reference["ci95"][0] is not None:
                ax.axhspan(
                    reference["ci95"][0],
                    reference["ci95"][1],
                    color=S.GRAY_LIGHT,
                    alpha=0.35,
                    linewidth=0,
                    zorder=1,
                )
        ax.set_title(result["corpus_label"], pad=3)
        ax.set_xlim(0.075, 0.81)
        ax.set_ylim(0, 1.0)
        # Keep all four observations but label only three anchors.  At native
        # single-column width, adjacent 0.10/0.25 labels collide.
        ax.set_xticks([0.10, 0.50, 0.75])
        ax.set_xticklabels([".1", ".5", ".75"])
        ax.set_yticks([0, 0.5, 1.0])
        ax.set_yticklabels(["0", ".5", "1"])
        ax.grid(
            axis="y",
            color=S.GRAY_LIGHT,
            linestyle=":",
            linewidth=0.5,
            alpha=0.9,
        )
        S.despine(ax)
        ax.spines["left"].set_linewidth(0.7)
        ax.spines["bottom"].set_linewidth(0.7)

    axes[0].set_ylabel("Mean drift")
    fig.supxlabel("Actual masked-token fraction", y=0.01, fontsize=7.5)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        ncol=4,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        handlelength=1.4,
        columnspacing=0.65,
        handletextpad=0.35,
    )
    fig.subplots_adjust(
        left=0.105,
        right=0.995,
        bottom=0.24,
        top=0.75,
        wspace=0.16,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output,
        dpi=300,
        bbox_inches="tight",
        pad_inches=0.025,
        facecolor=S.WHITE,
    )
    plt.close(fig)
    print(f"[figure] {output}", flush=True)


def _load_results(runs: Sequence[str], out_dir: Path) -> dict[str, dict]:
    results = {}
    for run in runs:
        path = out_dir / f"magnitude_{run}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        results[run] = json.loads(path.read_text(encoding="utf-8"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", default=MAIN_RUNS)
    parser.add_argument("--docs", type=int, default=100)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    parser.add_argument("--run-controlled", action="store_true")
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--fig-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--no-fig", action="store_true")
    args = parser.parse_args()

    if args.fig_only:
        results = _load_results(args.runs, args.out_dir)
        make_figure(results, args.figure)
        return 0

    if args.run_controlled or args.dry_run:
        run_controlled(args)
    elif not args.analyze_only:
        parser.error("choose --run-controlled, --analyze-only, --fig-only, or --dry-run")

    if args.dry_run:
        return 0
    results = analyze_checkpoint(
        args.checkpoint,
        runs=args.runs,
        docs_per_run=args.docs,
        out_dir=args.out_dir,
    )
    if not args.no_fig:
        make_figure(results, args.figure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
