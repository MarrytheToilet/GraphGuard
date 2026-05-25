"""Aggregate-report builder.

Reconstructed lightweight implementation: produces a JSON+Markdown summary of
the DB and a small set of case studies suitable for inspection or appendix
inclusion. Used by ``scripts/make_report.py`` and ``tests/test_phase_a.py``.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .. import queries as Q


# ---------- helpers ---------------------------------------------------------

_COUNT_TABLES = [
    "documents", "sentences", "entities",
    "schemas", "prompts", "extraction_events",
    "extracted_edges", "intervention_candidates",
    "counterfactual_runs", "edge_outcomes",
    "edge_reliability_scores", "edge_correctness", "gold_edges",
]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _safe_count(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    try:
        r = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        return int(r["n"] if isinstance(r, sqlite3.Row) else r[0])
    except sqlite3.Error:
        return 0


def _dataclass_to_dict(x: Any) -> Any:
    if hasattr(x, "to_dict") and callable(x.to_dict):
        return x.to_dict()
    if is_dataclass(x):
        return asdict(x)
    return x


def _json_default(o: Any) -> Any:
    if isinstance(o, sqlite3.Row):
        return {k: o[k] for k in o.keys()}
    if hasattr(o, "to_dict"):
        return o.to_dict()
    if is_dataclass(o):
        return asdict(o)
    if isinstance(o, set):
        return sorted(o)
    return str(o)


# ---------- public API ------------------------------------------------------

def summarize_db(conn: sqlite3.Connection) -> Dict[str, int]:
    """Return per-table row counts for the main extraction/contract tables."""
    return {t: _safe_count(conn, t) for t in _COUNT_TABLES}


def collect_case_studies(conn: sqlite3.Connection, k: int = 5,
                         *, top_k_causes: int = 3) -> List[Dict[str, Any]]:
    """Return at most ``k`` per-edge case studies.

    Each case is a dict with keys:
      - ``edge``: edge row as a dict
      - ``why_edge_top``: top causes from :func:`Q.why_edge`
      - ``why_type_top``: top causes from :func:`Q.why_type`
      - ``risk``: row from ``edge_reliability_scores`` if present
    """
    if not _table_exists(conn, "extracted_edges"):
        return []
    # Prefer ranking via the audit query (highest risk first); fall back to
    # any extracted edges if scoring tables are unavailable.
    edges: List[Any] = []
    try:
        edges = list(Q.rank_edges_for_audit(conn, k=k))
    except Exception:
        edges = []
    if not edges:
        rows = conn.execute(
            "SELECT * FROM extracted_edges LIMIT ?", (k,)
        ).fetchall()
        edges = [{kk: r[kk] for kk in r.keys()} for r in rows]

    out: List[Dict[str, Any]] = []
    for e in edges[:k]:
        edge_dict = _dataclass_to_dict(e)
        edge_id = (edge_dict.get("edge_id") if isinstance(edge_dict, dict)
                   else None)
        if edge_id is None:
            continue
        try:
            why_e = [c.to_dict() if hasattr(c, "to_dict") else c
                     for c in Q.why_edge(conn, edge_id, top_k=top_k_causes)]
        except Exception:
            why_e = []
        try:
            why_t = [c.to_dict() if hasattr(c, "to_dict") else c
                     for c in Q.why_type(conn, edge_id, top_k=top_k_causes)]
        except Exception:
            why_t = []
        risk_row = conn.execute(
            "SELECT * FROM edge_reliability_scores WHERE edge_id=?", (edge_id,)
        ).fetchone() if _table_exists(conn, "edge_reliability_scores") else None
        risk = ({k_: risk_row[k_] for k_ in risk_row.keys()}
                if risk_row is not None else None)
        out.append({
            "edge": edge_dict,
            "why_edge_top": why_e,
            "why_type_top": why_t,
            "risk": risk,
        })
    return out


def _load_optional_json(path: Optional[str]) -> Optional[Any]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def make_report(conn: sqlite3.Connection, out_dir: str, *,
                e0_path: Optional[str] = None,
                e1_path: Optional[str] = None,
                e2_path: Optional[str] = None,
                e3_path: Optional[str] = None,
                e4_path: Optional[str] = None,
                repair_path: Optional[str] = None,
                e5_audit_path: Optional[str] = None,
                k_cases: int = 5) -> Dict[str, Any]:
    """Assemble a JSON+Markdown report from per-experiment artifacts.

    Returns the summary dict and also writes ``summary.json`` / ``summary.md``
    into ``out_dir``.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    db_counts = summarize_db(conn)
    cases = collect_case_studies(conn, k=k_cases)

    artifacts: Dict[str, Any] = {}
    for name, path in (
        ("e0", e0_path), ("e1", e1_path), ("e2", e2_path),
        ("e3", e3_path), ("e4", e4_path),
        ("repair", repair_path), ("e5_audit", e5_audit_path),
    ):
        v = _load_optional_json(path)
        if v is not None:
            artifacts[name] = v

    summary: Dict[str, Any] = {
        "db_counts": db_counts,
        "case_studies": cases,
        "artifacts": artifacts,
    }

    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, default=_json_default),
        encoding="utf-8",
    )

    md_lines: List[str] = ["# Aggregate report", "", "## DB row counts", ""]
    for k_, v_ in db_counts.items():
        md_lines.append(f"- {k_}: {v_}")
    md_lines += ["", "## Loaded artifacts", ""]
    if artifacts:
        for k_ in artifacts:
            md_lines.append(f"- {k_}")
    else:
        md_lines.append("(none)")
    md_lines += ["", f"## Case studies ({len(cases)})", ""]
    for i, c in enumerate(cases, 1):
        eid = (c.get("edge") or {}).get("edge_id", "?")
        md_lines.append(f"### Case {i} — edge `{eid}`")
        md_lines.append("")
        md_lines.append(
            "```json\n"
            + json.dumps(c, indent=2, default=_json_default)
            + "\n```"
        )
        md_lines.append("")
    (out / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")

    return summary
