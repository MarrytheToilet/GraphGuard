#!/usr/bin/env python3
"""Create the deterministic, hash-indexed RQ8--RQ10 evidence package."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path

from graphguard.formal_artifacts import (
    DEFAULT_INDEX,
    FORMAL_INDEX_TYPE,
    FORMAL_INDEX_VERSION,
    expected_artifact_specs,
)


ROOT = Path(__file__).resolve().parents[1]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _gzip_deterministic(raw: bytes) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        compresslevel=9,
        fileobj=output,
        mtime=0,
    ) as compressed:
        compressed.write(raw)
    return output.getvalue()


def _write_atomic(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(handle, "wb") as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def package(repo_root: Path, index_path: Path) -> dict:
    entries = {}
    for key, spec in expected_artifact_specs().items():
        logical_path = repo_root / spec.logical_path
        raw = logical_path.read_bytes()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"{logical_path} is not a JSON object")
        if value.get("artifact_type") != spec.artifact_type:
            raise ValueError(f"{logical_path}: artifact type mismatch")
        if value.get("artifact_version") != spec.artifact_version:
            raise ValueError(f"{logical_path}: artifact version mismatch")
        if (
            spec.source_run is not None
            and value.get("source_run") != spec.source_run
        ):
            raise ValueError(f"{logical_path}: source run mismatch")

        if spec.compression == "gzip":
            transport = _gzip_deterministic(raw)
            transport_path = repo_root / spec.transport_path
            _write_atomic(transport_path, transport)
        else:
            transport = raw
        entries[key] = {
            "role": spec.role,
            "source_run": spec.source_run,
            "logical_path": spec.logical_path,
            "transport_path": spec.transport_path,
            "compression": spec.compression,
            "artifact_type": spec.artifact_type,
            "artifact_version": spec.artifact_version,
            "raw_size_bytes": len(raw),
            "raw_sha256": _sha256(raw),
            "transport_size_bytes": len(transport),
            "transport_sha256": _sha256(transport),
        }

    script_path = Path(__file__).resolve()
    index = {
        "artifact_type": FORMAL_INDEX_TYPE,
        "artifact_version": FORMAL_INDEX_VERSION,
        "description": (
            "Frozen derived evidence for auditing RQ8--RQ10 without the "
            "source lineage databases."
        ),
        "implementation": {
            "path": str(script_path.relative_to(repo_root)),
            "sha256": _sha256(script_path.read_bytes()),
            "compression": "gzip level 9 with empty filename and mtime=0",
        },
        "entries": entries,
    }
    encoded = (
        json.dumps(index, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _write_atomic(index_path, encoded)
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    index_path = args.index
    if not index_path.is_absolute():
        index_path = repo_root / index_path
    index = package(repo_root, index_path)
    transport_bytes = sum(
        entry["transport_size_bytes"]
        for entry in index["entries"].values()
        if entry["compression"] == "gzip"
    )
    print(
        f"wrote {index_path} and 12 gzip artifacts "
        f"({transport_bytes} bytes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
