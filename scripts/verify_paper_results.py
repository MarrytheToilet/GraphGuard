#!/usr/bin/env python3
"""Verify the paper's headline results against the shipped artifacts.

The default check is API-free and uses only versioned JSON under reports/.
Pass --lineage to additionally recount events, edges, counterfactual views,
and tokens from the local per-run SQLite lineage databases.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RC = ROOT / "reports" / "cross_run"
RR = ROOT / "reports" / "runs"

RUNS = {
    "DocRED": "docred__deepseek-v4-flash__300d",
    "Re-DocRED": "redocred__deepseek-v4-flash__300d",
    "SciERC": "scierc__deepseek-v4-flash__100d",
    "BC5CDR": "cdr__deepseek-v4-flash__300d",
}

LINEAGE_RUNS = {
    **RUNS,
    "DocRED / GLM-5": "docred__glm-5__100d",
    "DocRED / Kimi-K2": "docred__kimi-k2__100d",
    "DocRED / Qwen3-32B": "docred__qwen3-32b__100d",
}

EXPECTED_LINEAGE = {
    "DocRED": (7113, 71926, 6419, 36608230),
    "Re-DocRED": (7314, 80463, 6614, 39482498),
    "SciERC": (7004, 55697, 6336, 34511282),
    "BC5CDR": (7051, 22167, 6351, 14148369),
    "DocRED / GLM-5": (530, 4148, 431, 4619807),
    "DocRED / Kimi-K2": (2040, 13478, 1820, 3768445),
    "DocRED / Qwen3-32B": (1991, 16131, 1776, 4507748),
}


class VerificationError(AssertionError):
    """Raised when an artifact does not support a reported result."""


def load(path: Path) -> Any:
    if not path.is_file():
        raise VerificationError(f"missing artifact: {path.relative_to(ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(
            f"invalid JSON: {path.relative_to(ROOT)}: {exc}"
        ) from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def close(actual: float, expected: float, tol: float = 0.005) -> None:
    if not math.isclose(actual, expected, abs_tol=tol):
        raise VerificationError(
            f"expected {expected:.4f} ± {tol:.4f}, got {actual:.6f}"
        )


def rank_auc(labels: list[int], scores: list[float]) -> float:
    """Mann–Whitney AUROC with average ranks for tied scores."""
    require(len(labels) == len(scores) and labels, "invalid AUROC inputs")
    ordered = sorted(zip(scores, labels), key=lambda item: item[0])
    rank_sum_pos = 0.0
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        average_rank = ((i + 1) + j) / 2.0
        rank_sum_pos += average_rank * sum(label for _, label in ordered[i:j])
        i = j
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    require(n_pos > 0 and n_neg > 0, "AUROC requires both classes")
    return (
        rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    ) / (n_pos * n_neg)


def pr_auc(labels: list[int], scores: list[float]) -> float:
    """Trapezoidal area under the precision--recall curve."""
    require(len(labels) == len(scores) and labels, "invalid AUPRC inputs")
    n_pos = sum(labels)
    require(n_pos > 0, "AUPRC requires at least one positive")
    points = [(sum(labels) / len(labels), 1.0)]
    for threshold in sorted(set(scores)):
        selected = [
            label for label, score in zip(labels, scores)
            if score >= threshold
        ]
        true_positive = sum(selected)
        points.append((
            true_positive / len(selected),
            true_positive / n_pos,
        ))
    points.append((1.0, 0.0))
    points.sort(key=lambda point: point[1], reverse=True)
    return sum(
        (left[1] - right[1]) * (left[0] + right[0]) / 2.0
        for left, right in zip(points, points[1:])
    )


def verify_artifact_inventory() -> None:
    required = [
        RC / "amp_ci.json",
        RC / "budget_planner.json",
        RC / "cross_run_summary.json",
        RC / f"drift_accuracy_{RUNS['DocRED']}.json",
        RC / "endpoint_reuse.json",
        RC / "gate_split.json",
        RC / "k5_cross_model.json",
        RC / "k5_model_size.json",
        RC / "k5_model_size_expressible.json",
        RC / "langchain_toolchain.json",
        RC / "reproducibility_manifest.json",
        RC / "sampled_document_ids.json",
    ]
    for run in RUNS.values():
        required.extend([
            RC / f"e2e_kuzu_case_{run}__N300.json",
            RC / f"extqueries_{run}.json",
            RC / f"family_decomp_{run}.json",
            RC / f"graph_vs_query_{run}.json",
            RC / f"magnitude_{run}.json",
            RC / f"regimes_{run}.json",
            RC / f"strict_vs_soft_{run}.json",
            RR / run / "eval" / "contracts.json",
        ])
    for path in required:
        load(path)
    print(f"[PASS] artifact inventory ({len(required)} JSON files)")


def verify_sampled_documents(*, lineage: bool) -> None:
    samples = load(RC / "sampled_document_ids.json")
    require(
        samples["selection_rule"].startswith("filter configured splits"),
        "sample selection rule mismatch",
    )
    expected = {
        "docred__deepseek-v4-flash__300d": (300, 299),
        "redocred__deepseek-v4-flash__300d": (300, 300),
        "scierc__deepseek-v4-flash__100d": (100, 100),
        "cdr__deepseek-v4-flash__300d": (300, 300),
        "docred__glm-5__100d": (100, 99),
        "docred__kimi-k2__100d": (100, 100),
        "docred__qwen3-32b__100d": (100, 99),
    }
    for run, (n_selected, n_materialized) in expected.items():
        row = samples["runs"][run]
        document_ids = row["document_ids"]
        require(
            row["n_selected"] == n_selected == len(document_ids),
            f"{run}: sampled-document count mismatch",
        )
        require(
            document_ids == sorted(set(document_ids)),
            f"{run}: document IDs are not unique and sorted",
        )
        require(
            row["n_with_extraction_event"] == n_materialized,
            f"{run}: materialized-document count mismatch",
        )
        if lineage:
            db = (
                ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
            )
            with sqlite3.connect(db) as conn:
                placeholders = ",".join("?" for _ in row["splits"])
                actual = [
                    item[0]
                    for item in conn.execute(
                        f"SELECT document_id FROM documents "
                        f"WHERE split IN ({placeholders}) "
                        f"ORDER BY document_id LIMIT ?",
                        (*row["splits"], row["limit"]),
                    )
                ]
            require(
                document_ids == actual,
                f"{run}: sampled IDs do not match lineage DB",
            )
    print("[PASS] exact sampled-document identifiers")


def verify_reproducibility_manifest() -> None:
    manifest = load(RC / "reproducibility_manifest.json")
    totals = manifest["lineage_totals"]
    require(totals["extraction_events"] == 33043, "event total mismatch")
    require(totals["primary_events"] == 28482, "primary event total mismatch")
    require(totals["cross_model_events"] == 4561, "cross-model total mismatch")
    require(totals["tokens"] == 137646379, "token total mismatch")

    raw = manifest["raw_stability"]
    close(raw["DocRED"]["avg_edge_overlap"], 0.57)
    close(raw["Re-DocRED"]["avg_edge_overlap"], 0.57)
    close(raw["DocRED"]["type_agreement"], 0.79)
    close(raw["Re-DocRED"]["type_agreement"], 0.78)
    print("[PASS] run totals and raw repeated-extraction baseline")


def verify_contract_catalogue() -> None:
    from graphguard.contracts import REGISTRY

    for contract_id, query_id in {
        "K4b": "Q5", "K4c": "Q6", "K4d": "Q7"
    }.items():
        require(contract_id in REGISTRY, f"{contract_id}: not registered")
        contract = REGISTRY[contract_id]
        require(
            contract.query_scoped
            and contract.query_id == query_id
            and contract.threshold == 0.70
            and contract.alpha == 0.20,
            f"{contract_id}: registry definition mismatch",
        )
    k5 = REGISTRY["K5"]
    require(
        k5.metric_fn.__name__ == "recall_difference"
        and k5.threshold == 0.20
        and k5.alpha == 0.20
        and k5.needs_gold,
        "K5: registry definition mismatch",
    )

    data = load(RR / RUNS["DocRED"] / "eval" / "contracts.json")
    by_id = {row["contract_id"]: row for row in data["contracts"]}
    expected = {
        "K1": (676, 0.66, 0.97, 0.52),
        "K1b": (337, 0.64, 0.93, 0.48),
        "K1c": (676, 0.64, 0.72, 0.26),
        "K2": (534, 0.62, 0.92, 0.46),
        "K3": (78, 0.41, 0.64, 0.44),
        "K4": (2301, 0.78, 0.92, 0.54),
        "K4b": (872, 0.74, 0.82, 0.60),
        "K4c": (2301, 0.31, 0.55, 0.27),
        "K4d": (2301, 0.63, 0.88, 0.39),
        "K6": (78, 0.51, 0.91, 0.41),
    }
    for contract_id, (
        n_pairs, mean_drift, violation_rate, severity
    ) in expected.items():
        row = by_id[contract_id]
        require(row["n_pairs"] == n_pairs, f"{contract_id}: n mismatch")
        close(1.0 - row["metric_mean"], mean_drift)
        close(row["violation_rate"], violation_rate)
        close(row["severity_mean"], severity)

    cross_model = load(RC / "k5_cross_model.json")
    primary = [
        row for name, row in cross_model["pairs"].items()
        if name.startswith("DeepSeek-V4-Flash")
    ]
    n_total = sum(row["n"] for row in primary)
    mean_abs = sum(row["n"] * row["mean_abs_diff"] for row in primary) / n_total
    violation = sum(
        row["n"] * row["frac_above_tau"] for row in primary
    ) / n_total
    require(n_total == 294, "K5: pooled pair count mismatch")
    close(mean_abs, 0.10)
    close(violation, 0.13)
    pooled = cross_model["pooled_primary"]
    require(pooled["n"] == 294, "K5: pooled artifact n mismatch")
    close(pooled["severity_mean"], 0.22)
    print("[PASS] contract catalogue (Table 4)")


def verify_revision_analyses() -> None:
    ladder = load(RC / "k5_model_size.json")
    recalls = ladder["mean_recall"]
    for model, expected in {
        "Qwen3-8B": 0.107,
        "Qwen3-14B": 0.122,
        "Qwen3-32B": 0.140,
        "DeepSeek-V4-Flash": 0.206,
    }.items():
        close(recalls[model], expected)

    expressible = load(RC / "k5_model_size_expressible.json")
    close(expressible["mean_recall_expressible"]["Qwen3-8B"], 0.134)
    close(expressible["mean_recall_expressible"]["Qwen3-32B"], 0.174)
    close(expressible["mean_recall_expressible"]["DeepSeek-V4-Flash"], 0.260)

    semantic_rhos = []
    presentation_rhos = []
    for run in RUNS.values():
        summary = load(RC / f"magnitude_{run}.json")["summary"]
        semantic_rhos.append(summary["schema"]["spearman_semantic_only"])
        presentation_rhos.extend([
            abs(summary["prompt"]["spearman_mag_drift"]),
            abs(summary["evidence"]["spearman_mag_drift"]),
        ])
    require(
        min(semantic_rhos) >= 0.13 and max(semantic_rhos) <= 0.40,
        f"semantic magnitude correlations out of range: {semantic_rhos}",
    )
    require(
        max(presentation_rhos) < 0.13,
        f"presentation magnitude correlation exceeds rounded 0.13: "
        f"{presentation_rhos}",
    )

    toolchain = load(RC / "langchain_toolchain.json")
    rates = [
        row["violation_rate"] for row in toolchain["summary"].values()
    ]
    require(min(rates) >= 0.91, "LangChain violation range mismatch")

    for run in RUNS.values():
        buckets = load(RC / f"strict_vs_soft_{run}.json")
        require(
            buckets["n_pairs"]
            == sum(
                row["n_pairs"] for row in buckets["buckets"].values()
            ),
            f"{run}: stability-bucket pair count mismatch",
        )
    docred_l1 = load(
        RC / f"strict_vs_soft_{RUNS['DocRED']}.json"
    )["buckets"]["strict"]
    close(docred_l1["violation_rate_tau0p5"], 0.69, tol=0.01)
    close(docred_l1["query_divergence_rate"], 0.35, tol=0.01)
    print(
        "[PASS] revision analyses "
        "(magnitude, stability buckets, K5 ladder, LangChain)"
    )


def verify_query_results() -> None:
    amp = load(RC / "amp_ci.json")
    docred_join = amp[RUNS["DocRED"]]["Q3_join"]
    close(docred_join["amp_mean"], 1.32)
    close(docred_join["amp_ci_lo"], 1.14)
    close(docred_join["amp_ci_hi"], 1.59)
    require(
        docred_join["n_documents"] == 18,
        "DocRED join CI is not document-clustered as expected",
    )

    ext = {
        name: load(RC / f"extqueries_{run}.json")["summary"]
        for name, run in RUNS.items()
    }
    aggregation = [rows["Q_deg"]["amp_mean"] for rows in ext.values()]
    rag = [rows["Q_rag"]["amp_mean"] for rows in ext.values()]
    require(
        0.21 <= min(aggregation) <= 0.23
        and 0.56 <= max(aggregation) <= 0.58,
        f"aggregation amplification mismatch: {aggregation}",
    )
    require(
        0.47 <= min(rag) <= 0.49 and 0.91 <= max(rag) <= 0.93,
        f"RAG amplification mismatch: {rag}",
    )
    close(ext["BC5CDR"]["Q_path"]["amp_mean"], 1.27, tol=0.02)

    pooled_deltas = []
    for run in RUNS.values():
        monitors = load(
            RC / f"graph_vs_query_{run}.json"
        )["monitors_at_matched_alarm"]
        close(
            monitors["query_aware"]["alarm_rate"],
            monitors["graph_only"]["alarm_rate"],
            tol=1e-12,
        )
        pooled_deltas.append(
            monitors["query_aware"]["f1"] - monitors["graph_only"]["f1"]
        )
    require(
        0.005 <= min(pooled_deltas) and max(pooled_deltas) <= 0.115,
        f"pooled query-aware F1 deltas mismatch: {pooled_deltas}",
    )

    regime_deltas = []
    unequal_alarm_regimes = 0
    for run in RUNS.values():
        regimes = load(RC / f"regimes_{run}.json")["regimes"]
        for row in regimes.values():
            regime_deltas.append(row["delta_f1"])
            if abs(
                row["graph_only"]["alarm_rate"]
                - row["query_aware"]["alarm_rate"]
            ) > 0.05:
                unequal_alarm_regimes += 1
    require(
        0.095 <= min(regime_deltas) and max(regime_deltas) <= 0.215,
        f"regime F1 deltas mismatch: {regime_deltas}",
    )
    require(
        unequal_alarm_regimes > 0,
        "regime artifacts unexpectedly look strictly alarm-matched",
    )
    print("[PASS] query amplification and graph-vs-query comparisons")


def verify_drift_accuracy() -> None:
    data = load(RC / f"drift_accuracy_{RUNS['DocRED']}.json")
    population = data["query_population"]
    require(population["n_pairs"] == 4000, "query-divergence n mismatch")
    close(population["query_divergence_base_rate"], 0.394)
    recall = population["spearman"][
        "graph_drift_vs_abs_delta_recall"
    ]
    precision = population["spearman"][
        "graph_drift_vs_abs_delta_precision"
    ]
    close(recall["rho"], 0.205)
    close(precision["rho"], 0.115)
    require(
        recall["p_value"] < 1e-3 and precision["p_value"] < 1e-3,
        "drift/accuracy correlations are not significant",
    )

    k1 = data["k1_contrast"]
    require(k1["n_pairs"] == 676, "K1 accuracy contrast n mismatch")
    require(
        k1["violating"]["n"] == 657
        and k1["satisfied"]["n"] == 19,
        "K1 accuracy contrast split mismatch",
    )
    close(k1["violating"]["mean_abs_delta_recall"], 0.070)
    close(k1["violating"]["mean_abs_delta_precision"], 0.117)
    close(k1["satisfied"]["mean_abs_delta_recall"], 0.033)
    close(k1["satisfied"]["mean_abs_delta_precision"], 0.032)
    print("[PASS] query divergence and K1 accuracy contrast")


def verify_harm_detection_and_gate() -> None:
    graph_aurocs = []
    answer_aurocs = []
    graph_auprcs = []
    answer_auprcs = []
    full_harm = []
    graph_only_harm = []
    gated_harm = []
    gated_f1_fidelity = []
    random_harm = []
    graph_only_coverage_at_05 = []
    graph_only_coverage_at_15 = []
    for run in RUNS.values():
        pairs = load(RC / f"e2e_kuzu_case_{run}__N300.json")["pair_records"]
        labels = [int(row["harmful"]) for row in pairs]
        graph = [float(row["graph_drift"]) for row in pairs]
        answer = [float(row["max_answer_drift"]) for row in pairs]
        graph_aurocs.append(rank_auc(labels, graph))
        answer_aurocs.append(rank_auc(labels, answer))
        graph_auprcs.append(pr_auc(labels, graph))
        answer_auprcs.append(pr_auc(labels, answer))
        full_harm.append(sum(labels) / len(labels))

        graph_published = [
            row for row in pairs
            if float(row["graph_drift"]) < 0.45
        ]
        graph_only_harm.append(
            sum(bool(row["harmful"]) for row in graph_published)
            / len(graph_published)
        )
        published = [
            row for row in pairs
            if not (
                float(row["graph_drift"]) >= 0.45
                or float(row["max_answer_drift"]) >= 0.70
            )
        ]
        gated_harm.append(
            sum(bool(row["harmful"]) for row in published) / len(published)
        )
        gated_f1_fidelity.append(
            sum(1.0 - abs(float(row["mean_df1"])) for row in published)
            / len(published)
        )
        rng = random.Random(0)
        blocked = set(rng.sample(
            range(len(pairs)), len(pairs) - len(published)
        ))
        random_published = [
            row for index, row in enumerate(pairs)
            if index not in blocked
        ]
        random_harm.append(
            sum(bool(row["harmful"]) for row in random_published)
            / len(random_published)
        )

        for target, accumulator in (
            (0.05, graph_only_coverage_at_05),
            (0.15, graph_only_coverage_at_15),
        ):
            feasible_coverage = []
            for step in range(201):
                threshold = step / 200
                selected = [
                    row for row in pairs
                    if float(row["graph_drift"]) <= threshold
                ]
                if not selected:
                    continue
                harm_rate = (
                    sum(bool(row["harmful"]) for row in selected)
                    / len(selected)
                )
                if harm_rate <= target:
                    feasible_coverage.append(len(selected) / len(pairs))
            accumulator.append(
                max(feasible_coverage) if feasible_coverage else 0.0
            )

    require(
        0.55 <= min(graph_aurocs) and max(graph_aurocs) <= 0.90,
        f"graph AUROC mismatch: {graph_aurocs}",
    )
    require(
        0.61 <= min(answer_aurocs) and max(answer_aurocs) <= 0.91,
        f"answer AUROC mismatch: {answer_aurocs}",
    )
    require(
        0.27 <= min(graph_auprcs) and max(graph_auprcs) <= 0.70,
        f"graph AUPRC mismatch: {graph_auprcs}",
    )
    require(
        0.62 <= min(answer_auprcs) and max(answer_auprcs) <= 0.70,
        f"answer AUPRC mismatch: {answer_auprcs}",
    )
    require(
        0.19 <= min(full_harm) and max(full_harm) <= 0.31,
        f"publish-all harm mismatch: {full_harm}",
    )
    require(
        0.035 <= min(graph_only_harm) and max(graph_only_harm) <= 0.24,
        f"graph-only gate mismatch: {graph_only_harm}",
    )
    require(
        max(gated_harm) <= 0.131 and min(gated_f1_fidelity) >= 0.97,
        "full-data gate mismatch: "
        f"harm={gated_harm}, F1 fidelity={gated_f1_fidelity}",
    )
    require(
        0.09 <= min(random_harm) and max(random_harm) <= 0.34,
        f"matched-random gate mismatch: {random_harm}",
    )
    require(
        0.035 <= min(graph_only_coverage_at_05)
        and max(graph_only_coverage_at_05) <= 0.61,
        "5% graph-only calibration mismatch: "
        f"{graph_only_coverage_at_05}",
    )
    require(
        0.065 <= min(graph_only_coverage_at_15)
        and max(graph_only_coverage_at_15) <= 0.93,
        "15% graph-only calibration mismatch: "
        f"{graph_only_coverage_at_15}",
    )

    split = load(RC / "gate_split.json")["corpora"]
    paper_point = [
        row["deploy_graphguard_paper_point"] for row in split.values()
    ]
    require(
        max(row["pub_harm_rate"] for row in paper_point) <= 0.06,
        "held-out paper-point harm exceeds reported 0–6%",
    )
    require(
        min(row["f1_fidelity"] for row in paper_point) >= 0.96,
        "held-out F1 fidelity is below 0.96",
    )
    deploy_reselected = [
        row["deploy_graphguard"] for row in split.values()
    ]
    require(
        max(row["pub_harm_rate"] for row in deploy_reselected) >= 0.10,
        "calibration re-selection no longer exposes the reported miss",
    )
    held_out_publish_all = [
        row["deploy_publish_all"]["pub_harm_rate"]
        for row in split.values()
    ]
    require(
        min(held_out_publish_all) >= 0.21
        and max(held_out_publish_all) <= 0.31,
        "held-out publish-all harm is outside reported 21–31%",
    )

    planner = load(RC / "budget_planner.json")
    budget_index = planner["budgets"].index(0.4)
    budget_index_60 = planner["budgets"].index(0.6)
    recall_at_40 = [
        row["greedy"][budget_index] for row in planner["datasets"].values()
    ]
    recall_at_60 = [
        row["greedy"][budget_index_60]
        for row in planner["datasets"].values()
    ]
    require(
        0.39 <= min(recall_at_40) and max(recall_at_40) <= 0.56,
        f"40% budget recall mismatch: {recall_at_40}",
    )
    require(
        0.59 <= min(recall_at_60) and max(recall_at_60) <= 0.80,
        f"60% budget recall mismatch: {recall_at_60}",
    )
    print("[PASS] harmful-regression AUROC, release gate, and budget planner")


def verify_lineage() -> None:
    manifest = load(RC / "reproducibility_manifest.json")
    totals = [0, 0, 0, 0]
    for label, run in LINEAGE_RUNS.items():
        db_path = ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
        if not db_path.is_file():
            raise VerificationError(
                f"--lineage requested but DB is missing: "
                f"{db_path.relative_to(ROOT)}"
            )
        with sqlite3.connect(db_path) as conn:
            actual = (
                conn.execute("SELECT COUNT(*) FROM extraction_events").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM extracted_edges").fetchone()[0],
                conn.execute(
                    "SELECT COUNT(*) FROM counterfactual_runs "
                    "WHERE status='ok' AND COALESCE(cf_event_id, '')<>''"
                ).fetchone()[0],
                conn.execute(
                    "SELECT COALESCE(SUM(token_input), 0) "
                    "+ COALESCE(SUM(token_output), 0) FROM extraction_events"
                ).fetchone()[0],
            )
        require(
            actual == EXPECTED_LINEAGE[label],
            f"{label}: expected {EXPECTED_LINEAGE[label]}, got {actual}",
        )
        totals = [left + right for left, right in zip(totals, actual)]
        if label in RUNS:
            with sqlite3.connect(db_path) as conn:
                raw = conn.execute(
                    "SELECT COUNT(*), AVG(avg_edge_overlap), "
                    "AVG(type_agreement), AVG(disappearance_rate), "
                    "AVG(type_flip_rate), AVG(new_edge_rate) "
                    "FROM stability_reports"
                ).fetchone()
            cached = manifest["raw_stability"][label]
            require(raw[0] == cached["n_documents"], f"{label}: E0 n mismatch")
            for index, key in enumerate((
                "avg_edge_overlap",
                "type_agreement",
                "disappearance_rate",
                "type_flip_rate",
                "new_edge_rate",
            ), start=1):
                close(raw[index], cached[key], tol=1e-12)
    require(
        tuple(totals) == (33043, 264010, 29747, 137646379),
        f"lineage totals mismatch: {tuple(totals)}",
    )
    primary_events = sum(EXPECTED_LINEAGE[name][0] for name in RUNS)
    require(primary_events == 28482, "primary event total mismatch")
    print(
        "[PASS] lineage recount "
        "(33,043 events; 28,482 primary; 4,561 cross-model; "
        "137,646,379 tokens)"
    )


def verify_endpoint_reuse(*, lineage: bool) -> None:
    cached = load(RC / "endpoint_reuse.json")
    rows = cached["runs"]
    require(len(rows) == len(RUNS), "endpoint-reuse run count mismatch")
    require(
        {row["run"] for row in rows} == set(RUNS.values()),
        "endpoint-reuse run set mismatch",
    )
    require(
        all(row["contract_counts_match_report"] for row in rows),
        "endpoint-reuse pair counts do not match contract reports",
    )

    full_calls = [
        row["full_endpoint_union"]["call_savings_factor"] for row in rows
    ]
    full_tokens = [
        row["full_endpoint_union"]["token_savings_factor"] for row in rows
    ]
    cf_calls = [
        row["counterfactual_only"]["call_savings_factor"] for row in rows
    ]
    cf_tokens = [
        row["counterfactual_only"]["token_savings_factor"] for row in rows
    ]
    require(
        7.30 <= min(full_calls) and max(full_calls) <= 8.06,
        f"endpoint call-savings mismatch: {full_calls}",
    )
    require(
        7.32 <= min(full_tokens) and max(full_tokens) <= 7.91,
        f"endpoint token-savings mismatch: {full_tokens}",
    )
    require(
        3.95 <= min(cf_calls) and max(cf_calls) <= 4.46,
        f"counterfactual call-savings mismatch: {cf_calls}",
    )
    require(
        3.97 <= min(cf_tokens) and max(cf_tokens) <= 4.51,
        f"counterfactual token-savings mismatch: {cf_tokens}",
    )

    if lineage:
        from run_endpoint_reuse_analysis import analyze_run

        cached_by_run = {row["run"]: row for row in rows}
        for run in RUNS.values():
            db_path = (
                ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
            )
            observed = analyze_run(run, db_path, reports_root=RR)
            expected = cached_by_run[run]
            require(
                observed == expected,
                f"{run}: endpoint-reuse lineage recomputation mismatch",
            )
    print(
        "[PASS] endpoint-union savings "
        "(7.3–8.1x calls; 7.3–7.9x tokens; "
        "counterfactual-only 4.0–4.5x)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lineage",
        action="store_true",
        help="also verify the local SQLite lineage databases",
    )
    args = parser.parse_args()

    try:
        verify_artifact_inventory()
        verify_sampled_documents(lineage=args.lineage)
        verify_reproducibility_manifest()
        verify_contract_catalogue()
        verify_endpoint_reuse(lineage=args.lineage)
        verify_revision_analyses()
        verify_query_results()
        verify_drift_accuracy()
        verify_harm_detection_and_gate()
        if args.lineage:
            verify_lineage()
    except (KeyError, TypeError, ZeroDivisionError, VerificationError) as exc:
        print(f"[FAIL] {exc}")
        return 1

    scope = "cached artifacts + lineage DBs" if args.lineage else "cached artifacts"
    print(f"[PASS] paper result verification complete ({scope})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
