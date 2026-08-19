#!/usr/bin/env python3
"""Publish a sanitized replay cache for the BC5CDR cross-document run.

The private append-only checkpoint contains prompts and raw provider text.  The
published cache retains endpoint fingerprints, normalized MeSH/provenance
edges, token counts, statuses, and retry history, but removes both text fields.
The cached-result verifier needs no corpus or LLM call.  Full ``--analyze-only``
reconstruction additionally reads the registered BC5CDR source and lineage DB
to rebuild the cohort and historical per-document baseline.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT / "data/processed/cross_document/cross_document_cdr.jsonl"
)
DEFAULT_OUTPUT = ROOT / "reports/cross_run/cross_document_cdr_cache.jsonl"
DEFAULT_RESULT = ROOT / "reports/cross_run/cross_document_cdr.json"
REMOVED_FIELDS = {"raw_response_text"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _replace_atomically(files: list[tuple[Path, bytes]]) -> None:
    """Replace each file atomically, committing the audit marker last."""
    staged: list[tuple[Path, Path]] = []
    try:
        for target, payload in files:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                staged.append((target, Path(handle.name)))
        for target, temporary in staged:
            os.replace(temporary, target)
    finally:
        for _target, temporary in staged:
            temporary.unlink(missing_ok=True)


def package(source: Path, output: Path, result: Path | None = None) -> dict:
    source_manifest = source.with_suffix(source.suffix + ".manifest.json")
    output_manifest = output.with_suffix(output.suffix + ".manifest.json")
    audit_path = output.with_suffix(output.suffix + ".audit.json")
    if not source.is_file():
        raise FileNotFoundError(source)
    if not source_manifest.is_file():
        raise FileNotFoundError(source_manifest)
    if result is not None and not result.is_file():
        raise FileNotFoundError(result)

    source_manifest_bytes = source_manifest.read_bytes()
    source_manifest_sha256 = _sha256_bytes(source_manifest_bytes)
    manifest = json.loads(source_manifest_bytes)
    if (
        manifest.get("artifact_type")
        != "graphguard.cross_document_cdr_checkpoint_manifest"
        or manifest.get("artifact_version") != 1
        or not manifest.get("design_id")
        or not isinstance(manifest.get("cohort"), dict)
    ):
        raise ValueError("invalid source checkpoint manifest")

    records = [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError(f"checkpoint is empty: {source}")
    sanitized = []
    for record in records:
        item = {
            key: value
            for key, value in record.items()
            if key not in REMOVED_FIELDS
        }
        raw = str(record.get("raw_response_text", ""))
        item["raw_response_sha256"] = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()
        item["raw_response_bytes"] = len(raw.encode("utf-8"))
        sanitized.append(item)

    cache_bytes = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in sanitized
    ).encode("utf-8")

    result_bytes = None
    if result is not None:
        result_bytes = result.read_bytes()
        report = json.loads(result_bytes)
        if (
            report.get("artifact_type")
            != "graphguard.cross_document_cdr_results"
            or report.get("artifact_version") != 1
            or report.get("design_id") != manifest["design_id"]
            or report.get("cohort") != manifest["cohort"]
        ):
            raise ValueError("result artifact identity does not match manifest")
        source_manifest_name = str(source_manifest.relative_to(ROOT))
        output_manifest_name = str(output_manifest.relative_to(ROOT))
        checkpoint_manifest = report.get("checkpoint_manifest", {})
        if checkpoint_manifest.get("path") not in {
            source_manifest_name,
            output_manifest_name,
        }:
            raise ValueError(
                "result artifact references an unexpected checkpoint manifest"
            )
        if checkpoint_manifest.get("sha256") != source_manifest_sha256:
            raise ValueError(
                "result artifact checkpoint-manifest SHA-256 mismatch"
            )
        if checkpoint_manifest["path"] == source_manifest_name:
            checkpoint_manifest["path"] = output_manifest_name
            result_bytes = _json_bytes(report)

    keys = [
        (record["packet_id"], record["condition"])
        for record in sanitized
    ]
    key_counts = collections.Counter(keys)
    status_counts = collections.Counter(
        record["status"] for record in sanitized
    )
    retry_keys = sorted(
        [list(key) for key, count in key_counts.items() if count > 1]
    )
    latest = {}
    for record in sanitized:
        latest[(record["packet_id"], record["condition"])] = record
    if len(latest) != 300 or any(
        record["status"] != "ok" for record in latest.values()
    ):
        raise ValueError("published checkpoint must end with 300 successful keys")
    audit = {
        "artifact_type": "graphguard.cross_document_cdr_cache_audit",
        "artifact_version": 1,
        "source_checkpoint": {
            "sha256": sha256_file(source),
            "rows": len(records),
        },
        "published_cache": {
            "path": str(output.relative_to(ROOT)),
            "sha256": _sha256_bytes(cache_bytes),
            "manifest_sha256": source_manifest_sha256,
            "removed_fields": sorted(REMOVED_FIELDS),
        },
        "endpoint_attempts": {
            "records": len(sanitized),
            "unique_registered_keys": len(key_counts),
            "status_counts": dict(sorted(status_counts.items())),
            "retry_keys": retry_keys,
            "keys_with_retry": len(retry_keys),
            "prompt_tokens": sum(
                int(record.get("prompt_tokens") or 0) for record in sanitized
            ),
            "completion_tokens": sum(
                int(record.get("completion_tokens") or 0)
                for record in sanitized
            ),
        },
        "final_registered_endpoints": {
            "records": len(latest),
            "status_counts": dict(
                sorted(
                    collections.Counter(
                        record["status"] for record in latest.values()
                    ).items()
                )
            ),
        },
        "scope_note": (
            "Endpoint attempts are checkpoint records. Transparent HTTP "
            "retries inside the provider client are not individually logged."
        ),
        "producer": {
            "script": str(Path(__file__).resolve().relative_to(ROOT)),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
    }
    if result is not None:
        assert result_bytes is not None
        audit["result_artifact"] = {
            "path": str(result.relative_to(ROOT)),
            "sha256": _sha256_bytes(result_bytes),
        }
    audit["endpoint_attempts"]["total_tokens"] = (
        audit["endpoint_attempts"]["prompt_tokens"]
        + audit["endpoint_attempts"]["completion_tokens"]
    )
    files = [
        (output, cache_bytes),
        (output_manifest, source_manifest_bytes),
    ]
    if result is not None:
        assert result_bytes is not None
        files.append((result, result_bytes))
    files.append((audit_path, _json_bytes(audit)))
    _replace_atomically(files)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = package(args.source, args.output, args.result)
    attempts = audit["endpoint_attempts"]
    print(
        f"[packaged] rows={attempts['records']} "
        f"keys={attempts['unique_registered_keys']} "
        f"retries={attempts['keys_with_retry']} "
        f"tokens={attempts['total_tokens']} output={args.output}"
    )


if __name__ == "__main__":
    main()
