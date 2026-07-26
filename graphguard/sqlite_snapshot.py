"""Fingerprint and stability checks for read-only SQLite run databases."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def database_fingerprint(db_path: str | Path) -> dict:
    """Fingerprint the main DB and WAL bytes that define a SQLite snapshot."""
    db_path = Path(db_path)
    wal_path = Path(f"{db_path}-wal")
    wal_exists = wal_path.exists()
    wal_size = wal_path.stat().st_size if wal_exists else 0
    return {
        "main": {
            "sha256": sha256_file(db_path),
            "size_bytes": db_path.stat().st_size,
            "mtime_ns": db_path.stat().st_mtime_ns,
        },
        "wal": {
            "exists": wal_exists,
            "sha256": sha256_file(wal_path) if wal_size else None,
            "size_bytes": wal_size,
            "mtime_ns": wal_path.stat().st_mtime_ns if wal_exists else None,
        },
    }


def require_quiescent_snapshot(fingerprint: dict) -> None:
    """Reject a source whose logical state includes uncheckpointed WAL data."""
    if fingerprint["wal"]["size_bytes"]:
        raise RuntimeError(
            "source SQLite database has a non-empty WAL; checkpoint it or "
            "make an immutable snapshot before formal analysis"
        )


def require_stable_quiescent_snapshot(
    before: dict,
    after: dict,
) -> None:
    """Require stable main DB bytes and no WAL frames at either checkpoint.

    SQLite may create a zero-byte WAL during a read-only open.  Its existence
    and mtime are coordination metadata, not logical database content.
    """
    require_quiescent_snapshot(before)
    require_quiescent_snapshot(after)
    before_identity = (
        before["main"]["sha256"],
        before["main"]["size_bytes"],
    )
    after_identity = (
        after["main"]["sha256"],
        after["main"]["size_bytes"],
    )
    if before_identity != after_identity:
        raise RuntimeError(
            "source SQLite main database changed during analysis"
        )


def runtime_versions() -> dict:
    import sys

    return {
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
    }
