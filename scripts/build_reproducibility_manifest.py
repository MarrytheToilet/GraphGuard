#!/usr/bin/env python3
"""Rebuild the run-level provenance used by the paper.

This is the sole producer of
``reports/cross_run/reproducibility_manifest.json``.  It records exact
lineage-database identities, aggregate event/edge/view/token counts, and the
four primary runs' repeated-extraction baselines.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "cross_run" / "reproducibility_manifest.json"

RUNS = {
    "DocRED": ("docred__deepseek-v4-flash__300d", True),
    "Re-DocRED": ("redocred__deepseek-v4-flash__300d", True),
    "SciERC": ("scierc__deepseek-v4-flash__100d", True),
    "BC5CDR": ("cdr__deepseek-v4-flash__300d", True),
    "DocRED / GLM-5": ("docred__glm-5__100d", False),
    "DocRED / Kimi-K2": ("docred__kimi-k2__100d", False),
    "DocRED / Qwen3-32B": ("docred__qwen3-32b__100d", False),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    totals = {
        "extraction_events": 0,
        "primary_events": 0,
        "cross_model_events": 0,
        "extracted_edges": 0,
        "counterfactual_views": 0,
        "tokens": 0,
    }
    sources = {}
    raw_stability = {}

    for label, (run, primary) in RUNS.items():
        relative = Path("data") / "processed" / "runs" / run / f"{run}.db"
        db = ROOT / relative
        if not db.is_file():
            raise FileNotFoundError(db)

        with sqlite3.connect(db) as conn:
            events = conn.execute(
                "SELECT COUNT(*) FROM extraction_events"
            ).fetchone()[0]
            edges = conn.execute(
                "SELECT COUNT(*) FROM extracted_edges"
            ).fetchone()[0]
            views = conn.execute(
                "SELECT COUNT(*) FROM counterfactual_runs "
                "WHERE status='ok' AND COALESCE(cf_event_id, '')<>''"
            ).fetchone()[0]
            tokens = conn.execute(
                "SELECT COALESCE(SUM(token_input), 0) "
                "+ COALESCE(SUM(token_output), 0) FROM extraction_events"
            ).fetchone()[0]

            if primary:
                raw = conn.execute(
                    "SELECT COUNT(*), AVG(avg_edge_overlap), "
                    "AVG(type_agreement), AVG(disappearance_rate), "
                    "AVG(type_flip_rate), AVG(new_edge_rate) "
                    "FROM stability_reports WHERE n_runs >= 2"
                ).fetchone()
                raw_stability[label] = {
                    "n_documents": raw[0],
                    "avg_edge_overlap": raw[1],
                    "type_agreement": raw[2],
                    "disappearance_rate": raw[3],
                    "type_flip_rate": raw[4],
                    "new_edge_rate": raw[5],
                }

        totals["extraction_events"] += events
        totals["extracted_edges"] += edges
        totals["counterfactual_views"] += views
        totals["tokens"] += tokens
        if primary:
            totals["primary_events"] += events
        else:
            totals["cross_model_events"] += events

        sources[run] = {
            "label": label,
            "role": "primary" if primary else "cross-model",
            "path": relative.as_posix(),
            "bytes": db.stat().st_size,
            "sha256": sha256_file(db),
            "counts": {
                "extraction_events": events,
                "extracted_edges": edges,
                "counterfactual_views": views,
                "tokens": tokens,
            },
        }

    script = Path(__file__).resolve()
    output = {
        "schema_version": 2,
        "scope": (
            "four primary DeepSeek-V4-Flash runs plus three DocRED "
            "cross-model runs"
        ),
        "producer": {
            "script": script.relative_to(ROOT).as_posix(),
            "command": "python scripts/build_reproducibility_manifest.py",
            "script_sha256": sha256_file(script),
        },
        "source_databases": sources,
        "lineage_totals": totals,
        "raw_stability": raw_stability,
    }
    OUTPUT.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
