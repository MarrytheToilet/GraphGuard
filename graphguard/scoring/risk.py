"""Aggregate edge_outcomes into per-edge reliability scores.

Per README §8:
  Stability(e)        = 1 - mean_i Change(e, i)
  TextResp(e)         = mean_i Change(e, i) over text interventions
  PromptSensitivity   = mean_i Change(e, i) over prompt interventions
  SchemaSensitivity   = mean_i Change(e, i) over schema interventions
  StochasticVariance  = mean_i Change(e, i) over no-op repeats
  AdjustedEffect(e,i) = max(0, ChangeRate(e,i) - NaturalChange(e))   (§8.5)
  Risk(e)             = 1.0*(1-Stability) + 0.8*PromptSensAdj + 0.8*SchemaSensAdj
                       + 0.5*StochVar - 0.7*TextRespAdj
where Change(e, i) = 1 if outcome_type in {DISAPPEARED, TYPE_FLIP, OBJECT_FLIP, SUBJECT_FLIP, AMBIGUOUS}.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

CHANGE_OUTCOMES = {"DISAPPEARED", "TYPE_FLIP", "OBJECT_FLIP", "SUBJECT_FLIP", "AMBIGUOUS"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_div(num: float, den: int) -> float:
    return num / den if den else 0.0


def _natural_change_for_doc(conn: sqlite3.Connection, document_id: str) -> float:
    """Look up NaturalChange(document) computed by E0 stability runner; default 0."""
    r = conn.execute(
        "SELECT natural_change FROM document_natural_change WHERE document_id = ?",
        (document_id,),
    ).fetchone()
    if r and r[0] is not None:
        return float(r[0])
    # Fall back to per-document stability_reports if natural_change wasn't persisted.
    r = conn.execute(
        "SELECT 1.0 - avg_edge_overlap AS nc FROM stability_reports WHERE document_id = ?",
        (document_id,),
    ).fetchone()
    if r and r[0] is not None:
        return max(0.0, float(r[0]))
    return 0.0


def compute_for_edge(conn: sqlite3.Connection, edge_id: str) -> dict:
    rows = list(conn.execute("""
        SELECT eo.outcome_type, ic.target_type, ee.document_id
        FROM edge_outcomes eo
        JOIN counterfactual_runs cfr ON cfr.run_id = eo.run_id
        JOIN intervention_candidates ic ON ic.intervention_id = cfr.intervention_id
        JOIN extracted_edges ee ON ee.edge_id = eo.original_edge_id
        WHERE eo.original_edge_id = ?
    """, (edge_id,)))

    by_type: dict[str, list[int]] = {"sentence": [], "prompt_clause": [], "schema": []}
    all_changes: list[int] = []
    document_id: str | None = None
    for r in rows:
        document_id = r["document_id"]
        ch = 1 if r["outcome_type"] in CHANGE_OUTCOMES else 0
        all_changes.append(ch)
        by_type.setdefault(r["target_type"], []).append(ch)

    stability = 1.0 - _safe_div(sum(all_changes), len(all_changes))
    text_change = _safe_div(sum(by_type["sentence"]), len(by_type["sentence"]))
    prompt_sens = _safe_div(sum(by_type["prompt_clause"]), len(by_type["prompt_clause"]))
    schema_sens = _safe_div(sum(by_type["schema"]), len(by_type["schema"]))

    # Preserve any pre-existing stochastic_variance written by the E0 stability runner.
    prev = conn.execute(
        "SELECT stochastic_variance FROM edge_reliability_scores WHERE edge_id = ?",
        (edge_id,),
    ).fetchone()
    stochastic_var = float(prev["stochastic_variance"]) if prev and prev["stochastic_variance"] is not None else 0.0

    # README §8.5: AdjustedEffect subtracts natural variance so we don't attribute
    # stochastic noise to interventions. Natural variance is per-document.
    natural = _natural_change_for_doc(conn, document_id) if document_id else 0.0
    text_change_adj = max(0.0, text_change - natural)
    prompt_sens_adj = max(0.0, prompt_sens - natural)
    schema_sens_adj = max(0.0, schema_sens - natural)

    risk = (1.0 * (1.0 - stability)
            + 0.8 * prompt_sens_adj
            + 0.8 * schema_sens_adj
            + 0.5 * stochastic_var
            - 0.7 * text_change_adj)

    return {
        "edge_id": edge_id,
        "stability_score": stability,
        "text_responsibility": text_change_adj,
        "prompt_sensitivity": prompt_sens_adj,
        "schema_sensitivity": schema_sens_adj,
        "stochastic_variance": stochastic_var,
        "risk_score": risk,
        "computed_at": _now(),
        "_n_observations": len(all_changes),
        "_natural_change": natural,
        "_text_change_raw": text_change,
        "_prompt_sens_raw": prompt_sens,
        "_schema_sens_raw": schema_sens,
    }


def compute_all(conn: sqlite3.Connection) -> int:
    edge_ids = [r[0] for r in conn.execute(
        "SELECT DISTINCT original_edge_id FROM edge_outcomes")]
    n = 0
    for eid in edge_ids:
        s = compute_for_edge(conn, eid)
        conn.execute(
            "INSERT OR REPLACE INTO edge_reliability_scores("
            "edge_id, stability_score, text_responsibility, prompt_sensitivity, "
            "schema_sensitivity, stochastic_variance, risk_score, computed_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (s["edge_id"], s["stability_score"], s["text_responsibility"],
             s["prompt_sensitivity"], s["schema_sensitivity"],
             s["stochastic_variance"], s["risk_score"], s["computed_at"]),
        )
        n += 1
    conn.commit()
    return n

