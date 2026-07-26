import pytest

from graphguard.sqlite_snapshot import (
    require_stable_quiescent_snapshot,
)


def _fingerprint(
    *,
    main_sha="abc",
    main_size=10,
    wal_exists=False,
    wal_size=0,
    wal_mtime=None,
):
    return {
        "main": {
            "sha256": main_sha,
            "size_bytes": main_size,
            "mtime_ns": 1,
        },
        "wal": {
            "exists": wal_exists,
            "sha256": "wal-hash" if wal_size else None,
            "size_bytes": wal_size,
            "mtime_ns": wal_mtime,
        },
    }


def test_absent_to_zero_byte_wal_is_stable():
    require_stable_quiescent_snapshot(
        _fingerprint(),
        _fingerprint(wal_exists=True, wal_mtime=2),
    )


def test_zero_byte_wal_mtime_change_is_stable():
    require_stable_quiescent_snapshot(
        _fingerprint(wal_exists=True, wal_mtime=1),
        _fingerprint(wal_exists=True, wal_mtime=2),
    )


@pytest.mark.parametrize(
    "after",
    [
        _fingerprint(main_sha="changed"),
        _fingerprint(main_size=11),
    ],
)
def test_main_database_content_change_is_rejected(after):
    with pytest.raises(RuntimeError, match="main database changed"):
        require_stable_quiescent_snapshot(_fingerprint(), after)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (_fingerprint(wal_size=1), _fingerprint()),
        (_fingerprint(), _fingerprint(wal_size=1)),
    ],
)
def test_nonempty_wal_is_rejected(before, after):
    with pytest.raises(RuntimeError, match="non-empty WAL"):
        require_stable_quiescent_snapshot(before, after)
