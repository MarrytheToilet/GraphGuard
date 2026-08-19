#!/usr/bin/env python3
"""Run the registered BC5CDR joint-context cross-document experiment.

The experiment is isolated from the seven historical lineage databases.  Its
cohort is selected from loader-visible BC5CDR gold edges before model outputs
are read, and every query answer requires relation supports from two different
source documents.

Examples
--------
Build and validate the output-independent 100-packet cohort::

    python scripts/run_cross_document_experiment.py --build-cohort

Run or resume the 300 registered joint endpoints, then analyze them::

    python scripts/run_cross_document_experiment.py --all --workers 8

Rebuild the report and Kuzu parity evidence without API calls::

    python scripts/run_cross_document_experiment.py --analyze-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

from graphguard.cross_document import (  # noqa: E402
    CONDITIONS,
    DESIGN_ID,
    QUERY_FAMILIES,
    CrossDocumentKuzuGraph,
    build_cross_document_cohort,
    canonical_digest,
    execute_cross_document_query,
    graph_drifts,
    graph_quality,
    load_cdr_inputs,
    localize_edges,
    macro_query_metrics,
    normalize_joint_response,
    packet_edges,
    query_drift,
    render_joint_prompt,
    sha256_file,
    summarize_records,
)
from graphguard.llm.json_repair import parse_json_lenient  # noqa: E402
from graphguard.llm.openai_client import OpenAICompatClient  # noqa: E402


RUN_ID = "cdr__deepseek-v4-flash__300d"
RAW_PATH = (
    ROOT
    / "data/raw/cdr/CDR_Data/CDR.Corpus.v010516/"
    "CDR_DevelopmentSet.PubTator.txt"
)
DB_PATH = ROOT / "data/processed/runs" / RUN_ID / f"{RUN_ID}.db"
SAMPLES_PATH = ROOT / "reports/cross_run/sampled_document_ids.json"
DEFAULT_COHORT = ROOT / "reports/cross_run/cross_document_cdr_cohort.json"
DEFAULT_CHECKPOINT = (
    ROOT / "data/processed/cross_document/cross_document_cdr.jsonl"
)
DEFAULT_REPORT = ROOT / "reports/cross_run/cross_document_cdr.json"
BASE_SEED = 7
RESAMPLE_SEED = 13
TEMPERATURE = 0.0
MAX_TOKENS = 8192
EXPECTED_MODEL = "deepseek-v4-flash"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _endpoint_fingerprint() -> str:
    return hashlib.sha256(
        os.environ.get("OPENAI_BASE_URL", "").encode("utf-8")
    ).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _recorded_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _source_hashes() -> dict[str, str]:
    return {
        str(RAW_PATH.relative_to(ROOT)): sha256_file(RAW_PATH),
        str(DB_PATH.relative_to(ROOT)): sha256_file(DB_PATH),
        str(SAMPLES_PATH.relative_to(ROOT)): sha256_file(SAMPLES_PATH),
    }


def _code_hashes() -> dict[str, str]:
    paths = (
        Path(__file__).resolve(),
        ROOT / "graphguard/cross_document.py",
        ROOT / "graphguard/llm/openai_client.py",
    )
    return {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in paths
    }


def build_cohort(path: Path, *, n_packets: int) -> tuple[dict, object]:
    inputs = load_cdr_inputs(
        raw_path=RAW_PATH,
        db_path=DB_PATH,
        samples_path=SAMPLES_PATH,
        run_id=RUN_ID,
    )
    packets = build_cross_document_cohort(inputs, n_packets=n_packets)
    artifact = {
        "artifact_type": "graphguard.cross_document_cdr_cohort",
        "artifact_version": 1,
        "design_id": DESIGN_ID,
        "source_run": RUN_ID,
        "selection": {
            "rule": (
                "loader-visible gold cross-document witness; SHA-256 rank; "
                "greedy document-disjoint selection"
            ),
            "prediction_independent": True,
            "n_packets": len(packets),
            "n_unique_documents": len(
                {doc for packet in packets for doc in packet["documents"]}
            ),
            "packets_sha256": canonical_digest(packets),
        },
        "mapping_audit": inputs.mapping_audit,
        "source_sha256": _source_hashes(),
        "conditions": {
            "joint_ab_seed7": {
                "document_order": "AB",
                "seed": BASE_SEED,
            },
            "joint_ba_seed7": {
                "document_order": "BA",
                "seed": BASE_SEED,
            },
            "joint_ab_seed13": {
                "document_order": "AB",
                "seed": RESAMPLE_SEED,
            },
        },
        "query_families": {
            "crossdoc_fanout": (
                "same chemical, different disease answers, relation supports "
                "from different source documents"
            ),
            "crossdoc_shared_tail": (
                "different chemicals, same disease answer, relation supports "
                "from different source documents"
            ),
        },
        "packets": packets,
    }
    _write_json(path, artifact)
    return artifact, inputs


def load_cohort(path: Path) -> tuple[dict, object]:
    cohort = json.loads(path.read_text(encoding="utf-8"))
    if cohort.get("artifact_type") != "graphguard.cross_document_cdr_cohort":
        raise ValueError(f"not a cross-document cohort: {path}")
    if cohort.get("artifact_version") != 1:
        raise ValueError("cross-document cohort version mismatch")
    if cohort.get("source_sha256") != _source_hashes():
        raise ValueError("cross-document cohort source hashes no longer match")
    if cohort["selection"]["packets_sha256"] != canonical_digest(
        cohort["packets"]
    ):
        raise ValueError("cross-document cohort packet digest mismatch")
    inputs = load_cdr_inputs(
        raw_path=RAW_PATH,
        db_path=DB_PATH,
        samples_path=SAMPLES_PATH,
        run_id=RUN_ID,
    )
    if inputs.mapping_audit != cohort["mapping_audit"]:
        raise ValueError("cross-document MeSH mapping audit changed")
    rebuilt = build_cross_document_cohort(
        inputs,
        n_packets=cohort["selection"]["n_packets"],
    )
    if canonical_digest(rebuilt) != cohort["selection"]["packets_sha256"]:
        raise ValueError("cross-document cohort is not reproducible")
    return cohort, inputs


def _condition_spec(condition: str) -> tuple[str, int]:
    if condition == "joint_ab_seed7":
        return "ab", BASE_SEED
    if condition == "joint_ba_seed7":
        return "ba", BASE_SEED
    if condition == "joint_ab_seed13":
        return "ab", RESAMPLE_SEED
    raise KeyError(condition)


def _record_key(packet_id: str, condition: str) -> str:
    return f"{packet_id}\x1f{condition}"


class JsonlCheckpoint:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.records: dict[str, dict] = {}
        if self.path.exists():
            for line_number, line in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid checkpoint JSON at {path}:{line_number}"
                    ) from exc
                self.records[_record_key(
                    record["packet_id"], record["condition"]
                )] = record

    def get(self, packet_id: str, condition: str) -> dict | None:
        return self.records.get(_record_key(packet_id, condition))

    def append(self, record: dict) -> None:
        encoded = json.dumps(record, ensure_ascii=False, sort_keys=True)
        key = _record_key(record["packet_id"], record["condition"])
        with self.lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self.records[key] = record


def _checkpoint_manifest(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".manifest.json")


def _expected_run_manifest(cohort_path: Path, cohort: dict) -> dict:
    return {
        "artifact_type": "graphguard.cross_document_cdr_checkpoint_manifest",
        "artifact_version": 1,
        "design_id": DESIGN_ID,
        "cohort": {
            "path": _recorded_path(cohort_path),
            "sha256": sha256_file(cohort_path),
            "packets_sha256": cohort["selection"]["packets_sha256"],
        },
        "model_id": os.environ.get("OPENAI_MODEL"),
        "endpoint_sha256": _endpoint_fingerprint(),
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "conditions": cohort["conditions"],
        "source_sha256": _source_hashes(),
        "code_sha256": _code_hashes(),
    }


def _validate_or_create_run_manifest(
    checkpoint_path: Path,
    cohort_path: Path,
    cohort: dict,
) -> None:
    path = _checkpoint_manifest(checkpoint_path)
    expected = _expected_run_manifest(cohort_path, cohort)
    if path.exists():
        actual = json.loads(path.read_text(encoding="utf-8"))
        if actual != expected:
            raise ValueError(
                f"checkpoint manifest differs from current inputs/code: {path}"
            )
    else:
        _write_json(path, expected)


def _call_joint(
    client: OpenAICompatClient,
    *,
    prompt: str,
    inputs,
    packet: dict,
    condition: str,
    seed: int,
) -> dict:
    try:
        response = client.complete_json(
            prompt,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            seed=seed,
        )
    except Exception as exc:
        return {
            "status": "api_error",
            "error": f"{exc.__class__.__name__}: {exc}",
            "edges": [],
            "normalization_audit": {},
            "raw_response_text": "",
            "finish_reason": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "latency_ms": None,
        }
    finish_reason = (
        response.raw.get("finish_reason") if response.raw else None
    )
    try:
        parsed = parse_json_lenient(response.text)
    except Exception as exc:
        return {
            "status": "parse_error",
            "error": f"{exc.__class__.__name__}: {exc}",
            "edges": [],
            "normalization_audit": {},
            "raw_response_text": response.text,
            "finish_reason": finish_reason,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "latency_ms": response.latency_ms,
        }
    edges, audit = normalize_joint_response(parsed, inputs, packet)
    status = "ok" if finish_reason in {None, "stop"} else "truncated"
    return {
        "status": status,
        "error": "" if status == "ok" else f"finish_reason={finish_reason}",
        "edges": [list(edge) for edge in sorted(edges)] if status == "ok" else [],
        "normalization_audit": audit,
        "raw_response_text": response.text,
        "finish_reason": finish_reason,
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "latency_ms": response.latency_ms,
    }


def _process_packet(
    packet: dict,
    *,
    inputs,
    checkpoint: JsonlCheckpoint,
    retry_failures: bool,
) -> dict:
    client = OpenAICompatClient(timeout=300.0, json_mode=True)
    condition_order = sorted(
        CONDITIONS,
        key=lambda condition: canonical_digest(
            [DESIGN_ID, packet["packet_id"], condition, "call-order"]
        ),
    )
    new_calls = 0
    statuses = {}
    for condition in condition_order:
        order, seed = _condition_spec(condition)
        prompt = render_joint_prompt(inputs, packet, order=order)
        prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        existing = checkpoint.get(packet["packet_id"], condition)
        if existing is not None:
            expected = {
                "packet_id": packet["packet_id"],
                "documents": packet["documents"],
                "condition": condition,
                "prompt_sha256": prompt_sha,
                "seed": seed,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "model_id": os.environ.get("OPENAI_MODEL"),
                "endpoint_sha256": _endpoint_fingerprint(),
            }
            actual = {key: existing.get(key) for key in expected}
            if actual != expected:
                raise ValueError(
                    f"checkpoint fingerprint mismatch for "
                    f"{packet['packet_id']}/{condition}"
                )
        if existing is None or (
            retry_failures and existing.get("status") != "ok"
        ):
            result = _call_joint(
                client,
                prompt=prompt,
                inputs=inputs,
                packet=packet,
                condition=condition,
                seed=seed,
            )
            record = {
                "packet_id": packet["packet_id"],
                "documents": packet["documents"],
                "condition": condition,
                "prompt_sha256": prompt_sha,
                "seed": seed,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "model_id": os.environ.get("OPENAI_MODEL"),
                "endpoint_sha256": _endpoint_fingerprint(),
                "recorded_at": _utc_now(),
                **result,
            }
            checkpoint.append(record)
            existing = record
            new_calls += 1
        statuses[condition] = existing["status"]
    return {
        "packet_id": packet["packet_id"],
        "new_calls": new_calls,
        "statuses": statuses,
    }


def run_extraction(
    cohort_path: Path,
    checkpoint_path: Path,
    *,
    workers: int,
    retry_failures: bool,
) -> None:
    cohort, inputs = load_cohort(cohort_path)
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available")
    if not os.environ.get("OPENAI_BASE_URL"):
        raise RuntimeError("OPENAI_BASE_URL is not available")
    if os.environ.get("OPENAI_MODEL") != EXPECTED_MODEL:
        raise RuntimeError(
            f"registered experiment requires OPENAI_MODEL={EXPECTED_MODEL}"
        )
    _validate_or_create_run_manifest(checkpoint_path, cohort_path, cohort)
    checkpoint = JsonlCheckpoint(checkpoint_path)

    completed = 0
    total_new_calls = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [
            executor.submit(
                _process_packet,
                packet,
                inputs=inputs,
                checkpoint=checkpoint,
                retry_failures=retry_failures,
            )
            for packet in cohort["packets"]
        ]
        for future in as_completed(futures):
            result = future.result()
            completed += 1
            total_new_calls += result["new_calls"]
            print(
                f"[progress] {completed}/{len(futures)} "
                f"{result['packet_id']} new_calls={result['new_calls']} "
                f"statuses={result['statuses']}",
                flush=True,
            )
    print(
        f"[extraction complete] packets={completed} "
        f"new_calls={total_new_calls} checkpoint={checkpoint_path}",
        flush=True,
    )


def _record_edges(record: dict) -> set[tuple[str, str, str, str]]:
    return {tuple(edge) for edge in record.get("edges", [])}


def _kuzu_parity(
    edge_sets: dict[str, dict[str, set[tuple[str, str, str, str]]]],
) -> dict:
    checked = 0
    mismatches = []
    for condition, edges_by_packet in edge_sets.items():
        with CrossDocumentKuzuGraph(edges_by_packet) as graph:
            for packet_id, edges in sorted(edges_by_packet.items()):
                for family in QUERY_FAMILIES:
                    expected = execute_cross_document_query(edges, family)
                    actual = graph.execute(packet_id, family)
                    checked += 1
                    if actual != expected:
                        mismatches.append(
                            {
                                "condition": condition,
                                "packet_id": packet_id,
                                "family": family,
                                "expected": sorted(expected),
                                "actual": sorted(actual),
                            }
                        )
    return {
        "kuzu_version": __import__("kuzu").__version__,
        "answer_sets_checked": checked,
        "mismatches": mismatches,
        "status": "pass" if not mismatches else "fail",
    }


def analyze(
    cohort_path: Path,
    checkpoint_path: Path,
    output_path: Path,
) -> dict:
    cohort, inputs = load_cohort(cohort_path)
    _validate_or_create_run_manifest(checkpoint_path, cohort_path, cohort)
    checkpoint = JsonlCheckpoint(checkpoint_path)
    expected_keys = {
        _record_key(packet["packet_id"], condition)
        for packet in cohort["packets"]
        for condition in CONDITIONS
    }
    missing = sorted(expected_keys - set(checkpoint.records))
    if missing:
        raise ValueError(
            f"cross-document checkpoint is incomplete: {len(missing)} records missing"
        )
    failed = [
        record
        for key, record in checkpoint.records.items()
        if key in expected_keys and record.get("status") != "ok"
    ]
    if failed:
        counts: dict[str, int] = {}
        for record in failed:
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        raise ValueError(f"cross-document checkpoint has failed endpoints: {counts}")

    edge_sets: dict[
        str, dict[str, set[tuple[str, str, str, str]]]
    ] = {condition: {} for condition in CONDITIONS}
    edge_sets["cached_union"] = {}
    edge_sets["document_local_negative"] = {}
    per_packet = []
    for packet in cohort["packets"]:
        packet_id = packet["packet_id"]
        gold_edges = packet_edges(inputs, packet, source="gold")
        cached_edges = packet_edges(inputs, packet, source="cached_base")
        conditions = {
            condition: _record_edges(checkpoint.get(packet_id, condition))
            for condition in CONDITIONS
        }
        edge_sets["cached_union"][packet_id] = cached_edges
        edge_sets["document_local_negative"][packet_id] = localize_edges(
            cached_edges
        )
        for condition, edges in conditions.items():
            edge_sets[condition][packet_id] = edges

        condition_records = {
            "cached_union": {
                "n_edges": len(cached_edges),
                "graph_quality": graph_quality(cached_edges, gold_edges),
                "query_quality": macro_query_metrics(cached_edges, gold_edges),
            }
        }
        for condition, edges in conditions.items():
            condition_records[condition] = {
                "n_edges": len(edges),
                "graph_quality": graph_quality(edges, gold_edges),
                "query_quality": macro_query_metrics(edges, gold_edges),
            }
        comparisons = {}
        for label, changed_condition in (
            ("order", "joint_ba_seed7"),
            ("seed", "joint_ab_seed13"),
        ):
            semantic_drift, provenance_drift = graph_drifts(
                conditions["joint_ab_seed7"],
                conditions[changed_condition],
            )
            qdrift = query_drift(
                conditions["joint_ab_seed7"],
                conditions[changed_condition],
                gold_edges,
            )
            comparisons[label] = {
                "condition": changed_condition,
                "semantic_graph_drift": semantic_drift,
                "provenance_graph_drift": provenance_drift,
                "max_query_drift": qdrift["max_active_drift"],
                "mean_query_drift": qdrift["mean_active_drift"],
                "per_family": qdrift["per_family"],
            }
        per_packet.append(
            {
                "packet_id": packet_id,
                "documents": packet["documents"],
                "active_queries": packet["active_queries"],
                "n_gold_edges": len(gold_edges),
                "conditions": condition_records,
                "comparisons": comparisons,
            }
        )

    negative_nonempty = {
        packet_id: {
            family: sorted(execute_cross_document_query(edges, family))
            for family in QUERY_FAMILIES
            if execute_cross_document_query(edges, family)
        }
        for packet_id, edges in edge_sets["document_local_negative"].items()
    }
    negative_nonempty = {
        packet_id: answers
        for packet_id, answers in negative_nonempty.items()
        if answers
    }
    if negative_nonempty:
        raise ValueError(
            "document-local negative control produced cross-document answers"
        )

    parity = _kuzu_parity(edge_sets)
    if parity["status"] != "pass":
        raise ValueError(
            f"Kuzu parity failed for {len(parity['mismatches'])} answer sets"
        )

    used_records = [
        checkpoint.records[key] for key in sorted(expected_keys)
    ]
    call_audit = {
        "planned_endpoints": len(expected_keys),
        "successful_endpoints": len(used_records),
        "finish_reasons": {},
        "prompt_tokens": sum(
            int(record.get("prompt_tokens") or 0) for record in used_records
        ),
        "completion_tokens": sum(
            int(record.get("completion_tokens") or 0) for record in used_records
        ),
        "latency_ms": sum(
            int(record.get("latency_ms") or 0) for record in used_records
        ),
        "normalization": {},
    }
    for record in used_records:
        reason = str(record.get("finish_reason"))
        call_audit["finish_reasons"][reason] = (
            call_audit["finish_reasons"].get(reason, 0) + 1
        )
        for key, value in record.get("normalization_audit", {}).items():
            call_audit["normalization"][key] = (
                call_audit["normalization"].get(key, 0) + int(value)
            )

    artifact = {
        "artifact_type": "graphguard.cross_document_cdr_results",
        "artifact_version": 1,
        "design_id": DESIGN_ID,
        "scope": (
            "two-document joint-context extraction with oracle MeSH linking; "
            "not open-domain coreference or cross-document-only relation gold"
        ),
        "cohort": {
            "path": _recorded_path(cohort_path),
            "sha256": sha256_file(cohort_path),
            "packets_sha256": cohort["selection"]["packets_sha256"],
        },
        "checkpoint_manifest": {
            "path": _recorded_path(_checkpoint_manifest(checkpoint_path)),
            "sha256": sha256_file(_checkpoint_manifest(checkpoint_path)),
        },
        "source_sha256": _source_hashes(),
        "code_sha256": _code_hashes(),
        "call_audit": call_audit,
        "negative_control": {
            "document_local_cross_document_answers": 0,
            "status": "pass",
        },
        "kuzu_parity": parity,
        "summary": summarize_records(per_packet),
        "per_packet": per_packet,
    }
    _write_json(output_path, artifact)
    print(
        f"[analysis complete] packets={len(per_packet)} "
        f"answer_sets={parity['answer_sets_checked']} output={output_path}",
        flush=True,
    )
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--build-cohort", action="store_true")
    modes.add_argument("--extract", action="store_true")
    modes.add_argument("--analyze-only", action="store_true")
    modes.add_argument("--all", action="store_true")
    parser.add_argument("--packets", type=int, default=100)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.packets <= 0:
        raise ValueError("--packets must be positive")
    if args.build_cohort or args.all:
        cohort, _inputs = build_cohort(args.cohort, n_packets=args.packets)
        print(
            f"[cohort] packets={cohort['selection']['n_packets']} "
            f"documents={cohort['selection']['n_unique_documents']} "
            f"digest={cohort['selection']['packets_sha256']} "
            f"path={args.cohort}",
            flush=True,
        )
    if args.extract or args.analyze_only:
        cohort, _inputs = load_cohort(args.cohort)
        if cohort["selection"]["n_packets"] != args.packets:
            raise ValueError(
                f"cohort has {cohort['selection']['n_packets']} packets, "
                f"but --packets={args.packets}"
            )
    if args.extract or args.all:
        run_extraction(
            args.cohort,
            args.checkpoint,
            workers=args.workers,
            retry_failures=args.retry_failures,
        )
    if args.analyze_only or args.all:
        analyze(args.cohort, args.checkpoint, args.output)


if __name__ == "__main__":
    main()
