#!/usr/bin/env python3
"""Verify the paper's headline results against the shipped artifacts.

The default check is API-free and uses only canonical JSON under reports/.
Pass --lineage to additionally recount events, edges, counterfactual views,
and tokens from the local per-run SQLite lineage databases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from graphguard.deployment_evidence import (
    PRIMARY_RUNS,
    load_kuzu_evidence,
    validate_evidence_package,
)

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


def _fixed_effect_slope(
    panels: list[list[tuple[float, float]]],
) -> float:
    numerator = 0.0
    denominator = 0.0
    for panel in panels:
        x_mean = statistics.mean(x for x, _ in panel)
        y_mean = statistics.mean(y for _, y in panel)
        numerator += sum(
            (x - x_mean) * (y - y_mean) for x, y in panel
        )
        denominator += sum((x - x_mean) ** 2 for x, _ in panel)
    require(
        denominator > 0,
        "dose-response slope has no within-document variation",
    )
    return numerator / denominator


def _recompute_dose_response(
    pairs: list[dict],
    *,
    family: str,
    seed: int,
    draws: int,
) -> tuple[int, float, list[float]]:
    by_document: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in pairs:
        if row["family"] == family:
            by_document[row["document_id"]].append(
                (float(row["actual_magnitude"]), float(row["drift"]))
            )
    complete = {
        document_id: sorted(panel)
        for document_id, panel in by_document.items()
        if len(panel) == 4
    }
    docs = sorted(complete)
    require(docs, f"{family}: no complete four-level dose panels")
    point = 0.10 * _fixed_effect_slope([complete[doc] for doc in docs])
    rng = random.Random(seed)
    boot = []
    for _ in range(draws):
        sample = [complete[docs[rng.randrange(len(docs))]] for _ in docs]
        boot.append(0.10 * _fixed_effect_slope(sample))
    boot.sort()
    ci = [
        boot[math.floor(0.025 * (len(boot) - 1))],
        boot[math.ceil(0.975 * (len(boot) - 1))],
    ]
    return len(docs), point, ci


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        RC / "cross_document_cdr.json",
        RC / "cross_document_cdr_cache.jsonl.audit.json",
        RC / "cross_document_cdr_cache.jsonl.manifest.json",
        RC / "cross_document_cdr_cohort.json",
        RC / "cross_run_summary.json",
        RC / f"drift_accuracy_{RUNS['DocRED']}.json",
        RC / "endpoint_reuse.json",
        RC / "external_toolchain_q1q4_kuzu.json",
        RC / "deployment_evidence.json",
        RC / "gate_split.json",
        RC / "k5_cross_model.json",
        RC / "k5_model_size.json",
        RC / "k5_model_size_expressible.json",
        RC / "langchain_toolchain.json",
        RC / "neo4j_toolchain.json",
        RC / "reproducibility_manifest.json",
        RC / "sampled_document_ids.json",
    ]
    required.extend(
        RC / f"diagnostic_{run}.json"
        for run in LINEAGE_RUNS.values()
    )
    for run in RUNS.values():
        required.extend([
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
    package = validate_evidence_package(ROOT)
    require(
        set(package) == set(PRIMARY_RUNS),
        "deployment evidence run inventory mismatch",
    )
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
    require(
        manifest["schema_version"] == 2,
        "reproducibility manifest schema mismatch",
    )
    producer = manifest["producer"]
    producer_path = ROOT / producer["script"]
    require(
        producer["command"]
        == "python scripts/build_reproducibility_manifest.py"
        and producer_path.is_file()
        and producer["script_sha256"] == sha256_file(producer_path),
        "reproducibility manifest producer mismatch",
    )
    require(
        set(manifest["source_databases"]) == set(LINEAGE_RUNS.values()),
        "reproducibility manifest source-run inventory mismatch",
    )
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
        "K4": (2301, 0.76, 0.91, 0.53),
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

    magnitude_expected = {
        "DocRED": {
            "base_valid": 99,
            "pairs": 1179,
            "reference": 0.460,
            "schema_delta": 0.012,
            "prompt_delta": 0.028,
            "evidence_delta": 0.278,
            "schema_positive": False,
            "slopes": {
                "schema": (96, 0.00293, False),
                "prompt": (95, 0.00478, False),
                "evidence": (97, 0.04199, True),
            },
        },
        "Re-DocRED": {
            "base_valid": 98,
            "pairs": 1173,
            "reference": 0.492,
            "schema_delta": 0.111,
            "prompt_delta": 0.015,
            "evidence_delta": 0.282,
            "schema_positive": True,
            "slopes": {
                "schema": (97, 0.01695, True),
                "prompt": (96, 0.00012, False),
                "evidence": (98, 0.04333, True),
            },
        },
        "SciERC": {
            "base_valid": 98,
            "pairs": 1165,
            "reference": 0.472,
            "schema_delta": 0.077,
            "prompt_delta": 0.017,
            "evidence_delta": 0.352,
            "schema_positive": True,
            "slopes": {
                "schema": (95, 0.01298, True),
                "prompt": (92, 0.00188, False),
                "evidence": (97, 0.05534, True),
            },
        },
        "BC5CDR": {
            "base_valid": 100,
            "pairs": 1200,
            "reference": 0.127,
            "schema_delta": 0.046,
            "prompt_delta": 0.005,
            "evidence_delta": 0.374,
            "schema_positive": False,
            "slopes": {
                "schema": (100, 0.00642, False),
                "prompt": (100, -0.00038, False),
                "evidence": (100, 0.05547, True),
            },
        },
    }
    for run_index, (corpus, run) in enumerate(RUNS.items()):
        magnitude = load(RC / f"magnitude_{run}.json")
        expected = magnitude_expected[corpus]
        require(
            magnitude["experiment_id"] == "controlled-magnitude"
            and magnitude["n_documents"] == 100,
            f"{corpus}: controlled magnitude metadata mismatch",
        )
        require(
            magnitude["base"]["valid"] == expected["base_valid"]
            and magnitude["n_valid_pairs"] == expected["pairs"],
            f"{corpus}: magnitude pair inventory mismatch",
        )
        close(
            magnitude["resample_reference"]["mean_drift"],
            expected["reference"],
        )
        for family_index, (family, key) in enumerate(
            (
                ("schema", "schema_delta"),
                ("prompt", "prompt_delta"),
                ("evidence", "evidence_delta"),
            )
        ):
            result = magnitude["families"][family]["paired_high_minus_low"]
            close(result["mean"], expected[key])
            lo, hi = result["ci95"]
            if family == "evidence":
                require(
                    lo > 0,
                    f"{corpus}: evidence magnitude CI is not positive",
                )
            elif family == "prompt":
                require(
                    lo <= 0 <= hi,
                    f"{corpus}: prompt magnitude CI does not include zero",
                )
            else:
                require(
                    (lo > 0) == expected["schema_positive"],
                    f"{corpus}: schema magnitude CI verdict mismatch",
                )
            levels = magnitude["families"][family]["levels"]
            require(
                set(levels) == {"0.10", "0.25", "0.50", "0.75"}
                and min(cell["valid"] for cell in levels.values()) >= 95,
                f"{corpus}: magnitude level inventory mismatch",
            )
            slope = magnitude["families"][family]["dose_response_slope"]
            expected_n, expected_slope, expected_positive = expected["slopes"][
                family
            ]
            expected_seed = 40000 + 1000 * run_index + family_index
            require(
                slope["estimator"] == "pooled document-fixed-effects OLS"
                and slope["x"] == "actual_magnitude"
                and slope["complete_documents"] == expected_n
                and slope["observations"] == 4 * expected_n
                and slope["bootstrap"]
                == {
                    "unit": "document",
                    "draws": 2000,
                    "seed": expected_seed,
                },
                f"{corpus}/{family}: dose-response metadata mismatch",
            )
            n, point, slope_ci = _recompute_dose_response(
                magnitude["pairs"],
                family=family,
                seed=expected_seed,
                draws=2000,
            )
            require(
                n == expected_n
                and math.isclose(
                    slope["slope_per_0_10"], point, abs_tol=1e-12
                )
                and all(
                    math.isclose(actual, rebuilt, abs_tol=1e-12)
                    for actual, rebuilt in zip(slope["ci95"], slope_ci)
                ),
                f"{corpus}/{family}: dose-response recomputation mismatch",
            )
            close(slope["slope_per_0_10"], expected_slope, tol=0.0005)
            slope_lo, slope_hi = slope["ci95"]
            require(
                slope_lo > 0
                if expected_positive
                else slope_lo <= 0 <= slope_hi,
                f"{corpus}/{family}: dose-response CI verdict mismatch",
            )

    toolchain = load(RC / "langchain_toolchain.json")
    producer = toolchain["provenance"]["producer"]
    require(
        toolchain["schema_version"] == 2
        and producer[
            "future_extraction_evidence_seed_rule"
        ].startswith("sha256(doc_id")
        and toolchain["provenance"]["extraction_environment"] == {
            "recorded": False,
            "metadata_source": "hash-bound checkpoint metadata",
            "model": "deepseek-v4-flash",
            "ignore_tool_usage": True,
            "evidence_seed_rule": None,
            "evidence_seed_recorded": False,
            "dependency_versions": None,
        },
        "LangChain provenance metadata mismatch",
    )
    checkpoint = toolchain["provenance"]["checkpoint"]
    checkpoint_path = ROOT / checkpoint["path"]
    require(
        checkpoint_path.is_file(),
        f"published LangChain checkpoint missing: {checkpoint_path}",
    )
    checkpoint_records = [
        json.loads(line)
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
    ]
    require(
        checkpoint["bytes"] == checkpoint_path.stat().st_size
        and checkpoint["sha256"] == sha256_file(checkpoint_path)
        and checkpoint["records"] == len(checkpoint_records)
        and checkpoint["format"] == "published-checkpoint"
        and not checkpoint["contains_fingerprinted_records"]
        and not checkpoint["fully_fingerprinted"],
        "LangChain checkpoint provenance mismatch",
    )
    metadata_ref = toolchain["provenance"]["checkpoint_metadata"]
    metadata_path = ROOT / metadata_ref["path"]
    require(
        metadata_path.is_file()
        and metadata_ref["sha256"] == sha256_file(metadata_path),
        "LangChain checkpoint metadata provenance mismatch",
    )
    checkpoint_metadata = load(metadata_path)
    source_database = toolchain["provenance"]["source_database"]
    require(
        checkpoint_metadata["schema_version"] == 2
        and checkpoint_metadata["checkpoint"]["path"] == checkpoint["path"]
        and checkpoint_metadata["checkpoint"]["bytes"] == checkpoint["bytes"]
        and checkpoint_metadata["checkpoint"]["sha256"]
        == checkpoint["sha256"]
        and checkpoint_metadata["checkpoint"]["records"]
        == checkpoint["records"]
        and checkpoint_metadata["extraction_environment"]["model"]
        == toolchain["model"],
        "LangChain metadata does not bind the published checkpoint",
    )
    require(
        checkpoint_metadata["source_database"] == source_database
        and source_database == {
            "path": (
                "data/processed/runs/docred__deepseek-v4-flash__300d/"
                "docred__deepseek-v4-flash__300d.db"
            ),
            "bytes": 212393984,
            "sha256": (
                "54950e36efe566d3b73558f1c64336cb76913948bf4da1515ea7d4"
                "e0e03f9418"
            ),
        },
        "LangChain source-database provenance mismatch",
    )
    require(
        toolchain["provenance"][
            "analysis_environment_dependency_versions"
        ] == {
            "langchain-openai": "1.3.5",
            "langchain-experimental": "0.4.2",
            "langchain-core": "1.4.9",
        },
        "LangChain analysis dependency versions mismatch",
    )

    rename_inv = {
        "sovereign_state": "country",
        "situated_in": "located_in",
        "hq_place": "headquarters_location",
        "birthplace": "place_of_birth",
        "deathplace": "place_of_death",
        "works_for": "employer",
        "component_of": "part_of",
        "affiliated_with": "member_of",
        "released_on": "publication_date",
        "performed_by": "performer",
        "written_by": "author",
        "directed_by": "director",
    }

    def canonical_edges(edges: list) -> set:
        canonical = set()
        for subject, relation, obj in edges or []:
            relation = str(relation).lower().strip().replace(" ", "_")
            canonical.add((
                str(subject).lower().strip(),
                rename_inv.get(relation, relation),
                str(obj).lower().strip(),
            ))
        return canonical

    cached = defaultdict(dict)
    cached_errors = defaultdict(int)
    for record in checkpoint_records:
        if record.get("edges") is None:
            cached_errors[record["condition"]] += 1
        else:
            cached[record["doc"]][record["condition"]] = record["edges"]
    require(
        len(cached) == toolchain["n_docs"] == 100,
        "LangChain checkpoint document count mismatch",
    )
    for condition, reported in toolchain["summary"].items():
        drifts = []
        for by_condition in cached.values():
            if "base" not in by_condition or condition not in by_condition:
                continue
            base = canonical_edges(by_condition["base"])
            counterfactual = canonical_edges(by_condition[condition])
            if not base and not counterfactual:
                continue
            union = base | counterfactual
            drifts.append(
                1.0 - (len(base & counterfactual) / len(union))
            )
        violation_rate = (
            sum(drift > reported["tau"] for drift in drifts) / len(drifts)
        )
        require(
            reported["n"] == len(drifts)
            and reported["errors"] == cached_errors[condition],
            f"LangChain checkpoint population mismatch for {condition}",
        )
        close(
            reported["mean_drift"],
            round(statistics.mean(drifts), 4),
        )
        close(
            reported["median_drift"],
            round(statistics.median(drifts), 4),
        )
        close(
            reported["violation_rate"],
            round(violation_rate, 4),
        )
    rates = [
        row["violation_rate"] for row in toolchain["summary"].values()
    ]
    require(min(rates) >= 0.91, "LangChain violation range mismatch")

    neo4j = load(RC / "neo4j_toolchain.json")
    require(
        neo4j["schema_version"] == 1
        and neo4j["artifact_type"]
        == "graphguard.additional_toolchain_summary"
        and neo4j["toolchain"]
        == "neo4j_graphrag.LLMEntityRelationExtractor"
        and neo4j["component_level_only"] is True
        and neo4j["model"] == "deepseek-v4-flash"
        and neo4j["attempted_documents"] == 100,
        "Neo4j GraphRAG summary metadata mismatch",
    )
    neo4j_checkpoint = neo4j["provenance"]["checkpoint"]
    neo4j_checkpoint_path = ROOT / neo4j_checkpoint["path"]
    require(
        neo4j_checkpoint_path.is_file(),
        f"published Neo4j checkpoint missing: {neo4j_checkpoint_path}",
    )
    neo4j_records = [
        json.loads(line)
        for line in neo4j_checkpoint_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    require(
        neo4j_checkpoint["bytes"] == neo4j_checkpoint_path.stat().st_size
        and neo4j_checkpoint["sha256"]
        == sha256_file(neo4j_checkpoint_path)
        and neo4j_checkpoint["records"] == len(neo4j_records) == 600,
        "Neo4j checkpoint provenance mismatch",
    )
    neo4j_metadata_ref = neo4j["provenance"]["checkpoint_metadata"]
    neo4j_metadata_path = ROOT / neo4j_metadata_ref["path"]
    require(
        neo4j_metadata_path.is_file()
        and neo4j_metadata_ref["sha256"]
        == sha256_file(neo4j_metadata_path),
        "Neo4j checkpoint metadata provenance mismatch",
    )
    neo4j_metadata = load(neo4j_metadata_path)
    neo4j_source = neo4j["provenance"]["source_database"]
    require(
        neo4j_metadata["checkpoint"] == neo4j_checkpoint
        and neo4j_metadata["source_database"] == neo4j_source
        and neo4j_source == source_database
        and neo4j_metadata["extraction_environment"]["thinking_control"]
        == "disabled via extra_body.enable_thinking=false"
        and neo4j_metadata["extraction_environment"][
            "dependency_versions"
        ]
        == {
            "neo4j-graphrag": "1.18.0",
            "numpy": "2.2.6",
            "openai": "1.109.1",
            "pydantic": "2.13.4",
        },
        "Neo4j checkpoint metadata does not bind the reported run",
    )
    expected_conditions = {
        "base",
        "resample",
        "schema_reorder",
        "schema_rename",
        "prompt_para",
        "evidence_reorder",
    }
    neo4j_endpoints = {
        (record["doc"], record["condition"])
        for record in neo4j_records
    }
    require(
        len({record["doc"] for record in neo4j_records}) == 100
        and {record["condition"] for record in neo4j_records}
        == expected_conditions
        and len(neo4j_endpoints) == 600
        and all(
            record["toolchain"]
            == "neo4j_graphrag.LLMEntityRelationExtractor"
            and record["thinking_control"]
            == "disabled via extra_body.enable_thinking=false"
            for record in neo4j_records
        ),
        "Neo4j checkpoint endpoint inventory mismatch",
    )
    neo4j_cached = defaultdict(dict)
    neo4j_errors = defaultdict(int)
    for record in neo4j_records:
        if record.get("edges") is None:
            neo4j_errors[record["condition"]] += 1
        else:
            neo4j_cached[record["doc"]][record["condition"]] = record[
                "edges"
            ]
    for condition, reported in neo4j["summary"].items():
        drifts = []
        for by_condition in neo4j_cached.values():
            if "base" not in by_condition or condition not in by_condition:
                continue
            base = canonical_edges(by_condition["base"])
            counterfactual = canonical_edges(by_condition[condition])
            if not base and not counterfactual:
                continue
            union = base | counterfactual
            drifts.append(
                1.0 - (len(base & counterfactual) / len(union))
            )
        violation_rate = (
            sum(drift > reported["tau"] for drift in drifts) / len(drifts)
        )
        require(
            reported["n"] == len(drifts) == 99
            and reported["attempted"] == 100
            and reported["errors"] == neo4j_errors[condition] == 1
            and reported["empty_empty_excluded"] == 0,
            f"Neo4j checkpoint population mismatch for {condition}",
        )
        close(reported["mean_drift"], round(statistics.mean(drifts), 4))
        close(reported["median_drift"], round(statistics.median(drifts), 4))
        close(reported["violation_rate"], round(violation_rate, 4))
    neo4j_rates = [
        row["violation_rate"] for row in neo4j["summary"].values()
    ]
    require(
        min(neo4j_rates) >= 0.78 and max(neo4j_rates) <= 0.95,
        "Neo4j GraphRAG violation range mismatch",
    )

    for run in RUNS.values():
        family = load(RC / f"family_decomp_{run}.json")
        require(
            all(
                0.0 <= row["type_agree"] <= 1.0
                for row in family["summary"].values()
            ),
            f"{run}: invalid relation-set agreement",
        )
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
    docred_family = load(
        RC / f"family_decomp_{RUNS['DocRED']}.json"
    )["summary"]
    close(docred_family["stochastic"]["type_agree"], 0.80, tol=0.01)
    close(docred_family["prompt"]["type_agree"], 0.76, tol=0.01)
    close(docred_family["schema-sem"]["type_agree"], 0.50, tol=0.01)
    print(
        "[PASS] additional analyses "
        "(magnitude, family decomposition, stability buckets, "
        "K5 ladder, LangChain, Neo4j GraphRAG)"
    )


def verify_external_toolchain_queries() -> None:
    artifact = load(RC / "external_toolchain_q1q4_kuzu.json")
    require(
        artifact["artifact_type"]
        == "graphguard.external_toolchain_q1q4_kuzu"
        and artifact["artifact_version"] == 1
        and artifact["kuzu_version"] == "0.11.3",
        "external Q1-Q4 artifact metadata mismatch",
    )
    require(
        artifact["source_database"]["bytes"] == 212393984
        and artifact["source_database"]["sha256"]
        == (
            "54950e36efe566d3b73558f1c64336cb76913948bf4da1515ea7d4"
            "e0e03f9418"
        ),
        "external Q1-Q4 source database mismatch",
    )
    protocol = artifact["protocol"]
    require(
        "independently" in protocol["query_workload"]
        and "exact match" in protocol["entity_linking"]
        and "containment" not in protocol["entity_linking"]
        and protocol["empty_answers"]["both_empty_query_drift"] == 0.0
        and protocol["empty_answers"]["one_empty_query_drift"] == 1.0
        and not protocol["empty_answers"][
            "pairs_filtered_for_empty_answers"
        ]
        and protocol["contract_violation"] == {
            "metric": "pair maximum query drift",
            "comparator": ">",
            "tau": 0.30,
            "alpha": 0.20,
        },
        "external Q1-Q4 protocol mismatch",
    )

    catalogs = artifact["query_catalogs"]
    require(
        catalogs["n_documents"] == 100
        and catalogs["n_queries"] == 1926
        and catalogs["family_counts"] == {
            "deployment.lookup": 906,
            "deployment.neighbor": 249,
            "deployment.shared_tail_join": 416,
            "deployment.typed_two_hop": 355,
        },
        "external Q1-Q4 catalog inventory mismatch",
    )
    parity = artifact["parity"]
    require(
        parity["status"] == "pass"
        and parity["n_endpoints_materialized"] == 1189
        and parity["n_query_instances"] == 22848
        and parity["n_answer_sets"] == 22848
        and parity["n_mismatches"] == 0
        and parity["mismatches"] == [],
        "external Q1-Q4 Kuzu parity mismatch",
    )

    producer = artifact["producer"]
    require(
        producer["command"].startswith(
            "python scripts/run_external_toolchain_queries.py"
        ),
        "external Q1-Q4 producer command mismatch",
    )
    for relative, expected_hash in producer[
        "implementation_sha256"
    ].items():
        path = ROOT / relative
        require(
            path.is_file() and sha256_file(path) == expected_hash,
            f"external Q1-Q4 implementation hash mismatch: {relative}",
        )

    expected = {
        "langchain": {
            "mapping": {
                "exact": 12325,
                "ambiguous": 151,
                "unlinked": 3416,
            },
            "successful_endpoints": 595,
            "answer_sets": 11436,
            "mean_range": (0.627, 0.708),
            "violation_range": (0.676, 0.759),
            "active_range": (0.247, 0.282),
        },
        "neo4j": {
            "mapping": {
                "exact": 10567,
                "ambiguous": 218,
                "unlinked": 2089,
            },
            "successful_endpoints": 594,
            "answer_sets": 11412,
            "mean_range": (0.488, 0.683),
            "violation_range": (0.524, 0.729),
            "active_range": (0.191, 0.215),
        },
    }
    for toolchain, expected_toolchain in expected.items():
        result = artifact["toolchains"][toolchain]
        checkpoint = result["source_checkpoint"]
        checkpoint_path = ROOT / checkpoint["path"]
        require(
            checkpoint_path.is_file()
            and checkpoint["bytes"] == checkpoint_path.stat().st_size
            and checkpoint["sha256"] == sha256_file(checkpoint_path)
            and checkpoint["records"] == 600,
            f"{toolchain}: external Q1-Q4 checkpoint mismatch",
        )
        mapping = result["mapping"]
        require(
            mapping["entity_resolution"]
            == expected_toolchain["mapping"]
            and mapping["off_schema_relations"] == 0
            and mapping["n_endpoints"] == 600
            and mapping["n_successful_endpoints"]
            == expected_toolchain["successful_endpoints"],
            f"{toolchain}: external Q1-Q4 identifier mapping mismatch",
        )
        execution = result["execution"]
        require(
            execution["n_endpoints_materialized"]
            == expected_toolchain["successful_endpoints"]
            and execution["n_query_instances"]
            == expected_toolchain["answer_sets"]
            and execution["n_answer_sets"]
            == expected_toolchain["answer_sets"]
            and execution["n_mismatches"] == 0,
            f"{toolchain}: external Q1-Q4 execution inventory mismatch",
        )

        per_pair = result["per_pair"]
        require(
            len(per_pair) == 495,
            f"{toolchain}: external Q1-Q4 pair count mismatch",
        )
        summary = result["summary"]
        mean_values = []
        violation_values = []
        active_values = []
        for axis, reported in summary.items():
            records = [
                record for record in per_pair
                if record["axis"] == axis
            ]
            require(
                len(records) == reported["n_pairs"] == 99
                and reported["n_documents"] == 99
                and reported["n_query_evaluations"] == 1902,
                f"{toolchain}/{axis}: Q1-Q4 population mismatch",
            )
            state_counts = {
                state: sum(
                    record["answer_state_counts"][state]
                    for record in records
                )
                for state in (
                    "both_empty",
                    "base_only",
                    "cf_only",
                    "both_nonempty",
                )
            }
            require(
                state_counts == reported["answer_state_counts"]
                and sum(state_counts.values()) == 1902,
                f"{toolchain}/{axis}: answer-state mismatch",
            )
            mean_drift = statistics.mean(
                record["max_query_drift"] for record in records
            )
            violation = sum(
                record["max_query_drift"] > 0.30 for record in records
            ) / len(records)
            active = (
                1.0 - state_counts["both_empty"] / 1902
            )
            close(
                reported["mean_pair_max_query_drift"],
                mean_drift,
                tol=1e-12,
            )
            close(
                reported["violation_rate"],
                violation,
                tol=1e-12,
            )
            close(
                reported["active_query_rate"],
                active,
                tol=1e-12,
            )
            mean_values.append(mean_drift)
            violation_values.append(violation)
            active_values.append(active)

        for values, bounds, label in (
            (
                mean_values,
                expected_toolchain["mean_range"],
                "mean max drift",
            ),
            (
                violation_values,
                expected_toolchain["violation_range"],
                "violation",
            ),
            (
                active_values,
                expected_toolchain["active_range"],
                "active-query",
            ),
        ):
            require(
                bounds[0] <= min(values)
                and max(values) <= bounds[1],
                f"{toolchain}: external Q1-Q4 {label} range mismatch",
            )
    print(
        "[PASS] external-toolchain actual-Kuzu Q1-Q4 "
        "(1,189 endpoints; 22,848 answer sets; 0 mismatches)"
    )


def verify_cross_document_experiment() -> None:
    """Check the public cache, retry history, and paper-facing summary."""
    from graphguard.cross_document import summarize_records

    cohort_path = RC / "cross_document_cdr_cohort.json"
    cache_path = RC / "cross_document_cdr_cache.jsonl"
    manifest_path = cache_path.with_suffix(cache_path.suffix + ".manifest.json")
    audit_path = cache_path.with_suffix(cache_path.suffix + ".audit.json")
    result_path = RC / "cross_document_cdr.json"
    cohort = load(cohort_path)
    manifest = load(manifest_path)
    audit = load(audit_path)
    result = load(result_path)

    source_hashes = {
        (
            "data/raw/cdr/CDR_Data/CDR.Corpus.v010516/"
            "CDR_DevelopmentSet.PubTator.txt"
        ): "9e18d8e700168887a7919e62f67ac2ce2357e3f409a48ee992906abdd80fe3e5",
        (
            "data/processed/runs/cdr__deepseek-v4-flash__300d/"
            "cdr__deepseek-v4-flash__300d.db"
        ): "1793ee64aa8d40ac9deeff4dfa08207a9e31107bcd16ea692c9ba27d8e814a44",
        "reports/cross_run/sampled_document_ids.json": (
            "7b07cb539a58987750688887fb3dd33914672c4446b7548cb55767f2122b015d"
        ),
    }
    selection = cohort["selection"]
    require(
        cohort["artifact_type"] == "graphguard.cross_document_cdr_cohort"
        and cohort["artifact_version"] == 1
        and selection["prediction_independent"] is True
        and selection["n_packets"] == 100
        and selection["n_unique_documents"] == 200
        and selection["packets_sha256"]
        == "2bbfdcba928ebfe92a005acf3b1c8777cec0080d37132db877a7ee1fdcde3146",
        "cross-document cohort identity mismatch",
    )
    documents = [
        document
        for packet in cohort["packets"]
        for document in packet["documents"]
    ]
    active = Counter(
        family
        for packet in cohort["packets"]
        for family in packet["active_queries"]
    )
    require(
        len(cohort["packets"]) == 100
        and len(documents) == len(set(documents)) == 200
        and active == {
            "crossdoc_fanout": 41,
            "crossdoc_shared_tail": 59,
        },
        "cross-document packet inventory mismatch",
    )
    require(
        cohort["source_sha256"] == source_hashes
        and manifest["source_sha256"] == source_hashes,
        "cross-document source fingerprints mismatch",
    )
    mapping = cohort["mapping_audit"]
    require(
        mapping["n_documents"] == 300
        and mapping["n_local_entities"] == 2009
        and mapping["n_unique_mesh_ids"] == 952
        and mapping["n_repeated_mesh_ids"] == 362
        and mapping["n_documents_with_repeated_mesh"] == 299
        and mapping["unmapped_gold_rows"] == 0
        and mapping["base_edge_rows"] == 983
        and mapping["mapped_base_edge_rows"] == 967,
        "cross-document MeSH reconstruction audit mismatch",
    )

    require(cache_path.is_file(), "missing cross-document public cache")
    records = [
        json.loads(line)
        for line in cache_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    keys = [(row["packet_id"], row["condition"]) for row in records]
    key_counts = Counter(keys)
    status_counts = Counter(row["status"] for row in records)
    latest = {}
    for row in records:
        latest[(row["packet_id"], row["condition"])] = row
    require(
        len(records) == 302
        and len(key_counts) == 300
        and status_counts == {"ok": 300, "parse_error": 2}
        and sum(count > 1 for count in key_counts.values()) == 2
        and len(latest) == 300
        and all(row["status"] == "ok" for row in latest.values()),
        "cross-document cache chronology mismatch",
    )
    require(
        all("raw_response_text" not in row for row in records),
        "cross-document public cache contains raw provider text",
    )
    attempts = audit["endpoint_attempts"]
    require(
        audit["artifact_type"]
        == "graphguard.cross_document_cdr_cache_audit"
        and audit["artifact_version"] == 1
        and audit["published_cache"]["sha256"] == sha256_file(cache_path)
        and audit["published_cache"]["manifest_sha256"]
        == sha256_file(manifest_path)
        and audit["result_artifact"] == {
            "path": "reports/cross_run/cross_document_cdr.json",
            "sha256": sha256_file(result_path),
        }
        and attempts["records"] == 302
        and attempts["unique_registered_keys"] == 300
        and attempts["status_counts"] == {"ok": 300, "parse_error": 2}
        and attempts["keys_with_retry"] == 2
        and attempts["prompt_tokens"] == 441925
        and attempts["completion_tokens"] == 1033328
        and attempts["total_tokens"] == 1475253,
        "cross-document public-cache audit mismatch",
    )

    require(
        result["artifact_type"] == "graphguard.cross_document_cdr_results"
        and result["artifact_version"] == 1
        and result["cohort"]["sha256"] == sha256_file(cohort_path)
        and result["checkpoint_manifest"]["sha256"]
        == sha256_file(manifest_path)
        and result["call_audit"]["planned_endpoints"] == 300
        and result["call_audit"]["successful_endpoints"] == 300
        and result["call_audit"]["finish_reasons"] == {"stop": 300}
        and result["call_audit"]["normalization"] == {
            "accepted_edges": 2355,
            "invalid_cid_direction": 1,
            "invalid_evidence": 0,
            "invalid_provenance": 0,
            "invalid_relation": 0,
            "invalid_shape": 0,
            "raw_edges": 2360,
            "undeclared_entity": 4,
        }
        and result["negative_control"] == {
            "document_local_cross_document_answers": 0,
            "status": "pass",
        }
        and result["kuzu_parity"] == {
            "kuzu_version": "0.11.3",
            "answer_sets_checked": 1000,
            "mismatches": [],
            "status": "pass",
        },
        "cross-document result audit mismatch",
    )
    require(
        summarize_records(result["per_packet"]) == result["summary"],
        "cross-document packet-level summary mismatch",
    )
    summary = result["summary"]
    close(
        summary["comparisons"]["order"]["provenance_graph_drift"]["mean"],
        0.320,
        0.001,
    )
    close(
        summary["comparisons"]["order"]["max_query_drift"]["mean"],
        0.187,
        0.001,
    )
    close(
        summary["comparisons"]["seed"]["provenance_graph_drift"]["mean"],
        0.280,
        0.001,
    )
    close(
        summary["comparisons"]["seed"]["max_query_drift"]["mean"],
        0.150,
        0.001,
    )
    close(
        summary["query_quality"]["cached_union"]["mean_macro_query_f1"],
        0.600,
        0.001,
    )
    close(
        summary["query_quality"]["joint_ab_seed7"]["mean_macro_query_f1"],
        0.657,
        0.001,
    )
    print(
        "[PASS] BC5CDR cross-document stress test "
        "(100 packets; 302 recorded attempts; 1,000 Kuzu answers)"
    )


def verify_query_results() -> None:
    amp = load(RC / "amp_ci.json")
    require(
        amp["artifact_version"] == 2,
        "canonical diagnostic summary version mismatch",
    )
    diagnostic_runs = amp["runs"]
    for run in LINEAGE_RUNS.values():
        source = load(RC / f"diagnostic_{run}.json")
        require(
            source["artifact_version"] == 2,
            f"{run}: diagnostic artifact version mismatch",
        )
        require(
            amp["source_artifacts"][run]["source_database"]
            == source["source_database"],
            f"{run}: compact diagnostic provenance mismatch",
        )
        for query_id, full in source["summary"].items():
            compact = diagnostic_runs[run][query_id]
            interval = full["amplification_document_cluster_ci"]
            require(
                compact["n"] == full["n"]
                and compact["n_documents"] == full["n_documents"]
                and compact["amp_mean"]
                == full["amplification_mean_per_pair"]
                and compact["amp_ci_lo"] == interval["ci_low"]
                and compact["amp_ci_hi"] == interval["ci_high"]
                and compact["query_drift_mean"]
                == full["query_drift_mean"]
                and compact["graph_drift_mean"]
                == full["graph_drift_mean"],
                f"{run}/{query_id}: compact diagnostic summary mismatch",
            )
    docred = diagnostic_runs[RUNS["DocRED"]]
    docred_d3 = docred["diagnostic.fanout_join"]
    close(docred_d3["amp_mean"], 1.15)
    close(docred_d3["amp_ci_lo"], 1.12)
    close(docred_d3["amp_ci_hi"], 1.17)
    require(
        docred_d3["n"] == 6419
        and docred_d3["n_documents"] == 299,
        "DocRED diagnostic D3 CI is not document-clustered as expected",
    )
    require(
        docred_d3["amp_mean"]
        == max(row["amp_mean"] for row in docred.values()),
        "canonical D3 is not the strongest primary-run diagnostic",
    )
    close(
        diagnostic_runs[RUNS["Re-DocRED"]][
            "diagnostic.fanout_join"
        ]["amp_mean"],
        1.15,
    )
    close(
        diagnostic_runs[RUNS["SciERC"]][
            "diagnostic.fanout_join"
        ]["amp_mean"],
        0.82,
    )
    close(
        diagnostic_runs[RUNS["BC5CDR"]][
            "diagnostic.fanout_join"
        ]["amp_mean"],
        0.12,
    )
    for semantic_class, expected in {
        "stochastic": 1.11,
        "presentation": 1.13,
        "semantic": 1.15,
    }.items():
        close(
            docred_d3["by_semantic_class"][semantic_class][
                "amplification_mean_per_pair"
            ],
            expected,
        )
    primary_contracts = load(
        RR / RUNS["DocRED"] / "eval" / "contracts.json"
    )
    k4 = next(
        row for row in primary_contracts["contracts"]
        if row["contract_id"] == "K4"
    )
    close(
        docred_d3["by_semantic_class"]["presentation"][
            "query_drift_mean"
        ],
        1.0 - k4["metric_mean"],
        tol=1e-12,
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
    docred_contracts = {
        row["contract_id"]: row
        for row in load(
            RR / RUNS["DocRED"] / "eval" / "contracts.json"
        )["contracts"]
    }
    for contract_id, query_key in {
        "K4b": "Q_path",
        "K4c": "Q_deg",
        "K4d": "Q_rag",
    }.items():
        close(
            ext["DocRED"][query_key]["viol_rate_drift_gt_0.30"],
            docred_contracts[contract_id]["violation_rate"],
            tol=1e-12,
        )

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
        regimes = load(
            RC / f"regimes_{run}.json"
        )["regimes"]
        for row in regimes.values():
            regime_deltas.append(row["delta_f1"])
            if abs(
                row["graph_only"]["alarm_rate"]
                - row["query_aware"]["alarm_rate"]
            ) > 0.05:
                unequal_alarm_regimes += 1
    require(
        0.095 <= min(regime_deltas) and max(regime_deltas) <= 0.205,
        f"regime F1 deltas mismatch: {regime_deltas}",
    )
    require(
        unequal_alarm_regimes > 0,
        "regime artifacts unexpectedly look strictly alarm-matched",
    )
    print("[PASS] query amplification and graph-vs-query comparisons")


def verify_drift_accuracy() -> None:
    data = load(
        RC / f"drift_accuracy_{RUNS['DocRED']}.json"
    )
    population = data["query_population"]
    require(population["n_pairs"] == 4000, "query-divergence n mismatch")
    close(population["query_divergence_base_rate"], 0.436)
    recall = population["spearman"][
        "graph_drift_vs_abs_delta_recall"
    ]
    precision = population["spearman"][
        "graph_drift_vs_abs_delta_precision"
    ]
    close(recall["rho"], 0.219)
    close(precision["rho"], 0.135)
    require(
        recall["p_value"] < 1e-3 and precision["p_value"] < 1e-3,
        "drift/accuracy correlations are not significant",
    )

    k1 = data["k1_contrast"]
    require(k1["n_pairs"] == 676, "K1 accuracy contrast n mismatch")
    require(
        k1["violating"]["n"] == 656
        and k1["satisfied"]["n"] == 20,
        "K1 accuracy contrast split mismatch",
    )
    close(k1["violating"]["mean_abs_delta_recall"], 0.070)
    close(k1["violating"]["mean_abs_delta_precision"], 0.117)
    close(k1["satisfied"]["mean_abs_delta_recall"], 0.031)
    close(k1["satisfied"]["mean_abs_delta_precision"], 0.032)
    print("[PASS] query divergence and K1 accuracy contrast")


def verify_harm_detection_and_gate() -> None:
    graph_aurocs = []
    answer_aurocs = []
    gate_aurocs = []
    graph_auprcs = []
    answer_auprcs = []
    full_harm = []
    full_improvement = []
    graph_only_harm = []
    gated_harm = []
    gated_f1_fidelity = []
    gated_coverage = []
    random_harm = []
    graph_only_coverage_at_05 = []
    graph_only_coverage_at_15 = []
    joint_coverage_at_15 = []

    def strict_threshold_coverage(scores, labels, target):
        ordered = sorted(zip(scores, labels), key=lambda item: item[0])
        best = 0.0
        n_published = 0
        n_harmful = 0
        index = 0
        while index < len(ordered):
            score = ordered[index][0]
            while (
                index < len(ordered)
                and abs(ordered[index][0] - score) <= 1e-12
            ):
                n_published += 1
                n_harmful += ordered[index][1]
                index += 1
            if n_harmful / n_published <= target:
                best = n_published / len(ordered)
        return best

    for run in RUNS.values():
        pairs = load_kuzu_evidence(ROOT, run)["per_pair"]
        labels = [
            int(float(row["mean_delta_f1_signed"]) > 0.05)
            for row in pairs
        ]
        graph = [float(row["graph_drift"]) for row in pairs]
        answer = [float(row["max_answer_drift"]) for row in pairs]
        gate_margin = [
            max(graph_score / 0.45, answer_score / 0.70)
            for graph_score, answer_score in zip(graph, answer)
        ]
        graph_aurocs.append(rank_auc(labels, graph))
        answer_aurocs.append(rank_auc(labels, answer))
        gate_aurocs.append(rank_auc(labels, gate_margin))
        graph_auprcs.append(pr_auc(labels, graph))
        answer_auprcs.append(pr_auc(labels, answer))
        full_harm.append(sum(labels) / len(labels))
        full_improvement.append(
            sum(
                float(row["mean_delta_f1_signed"]) < -0.05
                for row in pairs
            )
            / len(pairs)
        )

        graph_published = [
            row for row in pairs
            if float(row["graph_drift"]) < 0.45
        ]
        graph_only_harm.append(
            sum(
                float(row["mean_delta_f1_signed"]) > 0.05
                for row in graph_published
            )
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
            sum(
                float(row["mean_delta_f1_signed"]) > 0.05
                for row in published
            )
            / len(published)
        )
        gated_f1_fidelity.append(
            sum(
                1.0 - float(row["mean_delta_f1_abs"])
                for row in published
            )
            / len(published)
        )
        gated_coverage.append(len(published) / len(pairs))
        rng = random.Random(0)
        blocked = set(rng.sample(
            range(len(pairs)), len(pairs) - len(published)
        ))
        random_published = [
            row for index, row in enumerate(pairs)
            if index not in blocked
        ]
        random_harm.append(
            sum(
                float(row["mean_delta_f1_signed"]) > 0.05
                for row in random_published
            )
            / len(random_published)
        )

        graph_only_coverage_at_05.append(
            strict_threshold_coverage(graph, labels, 0.05)
        )
        graph_only_coverage_at_15.append(
            strict_threshold_coverage(graph, labels, 0.15)
        )
        joint_coverage_at_15.append(
            strict_threshold_coverage(gate_margin, labels, 0.15)
        )

    require(
        0.57 <= min(graph_aurocs) and max(graph_aurocs) <= 0.90,
        f"graph AUROC mismatch: {graph_aurocs}",
    )
    require(
        0.61 <= min(answer_aurocs) and max(answer_aurocs) <= 0.91,
        f"answer AUROC mismatch: {answer_aurocs}",
    )
    require(
        0.32 <= min(graph_auprcs) and max(graph_auprcs) <= 0.70,
        f"graph AUPRC mismatch: {graph_auprcs}",
    )
    require(
        0.67 <= min(answer_auprcs) and max(answer_auprcs) <= 0.73,
        f"answer AUPRC mismatch: {answer_auprcs}",
    )
    require(
        0.19 <= min(full_harm) and max(full_harm) <= 0.305,
        f"publish-all harm mismatch: {full_harm}",
    )
    require(
        0.10 <= min(full_improvement) and max(full_improvement) <= 0.25,
        f"publish-all improvement mismatch: {full_improvement}",
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
        0.18 <= min(random_harm) and max(random_harm) <= 0.305,
        f"matched-random gate mismatch: {random_harm}",
    )
    require(
        0.075 <= min(gated_coverage) and max(gated_coverage) <= 0.59,
        f"GraphGuard coverage mismatch: {gated_coverage}",
    )
    require(
        0.60 <= min(gate_aurocs) and max(gate_aurocs) <= 0.89,
        f"normalized gate AUROC mismatch: {gate_aurocs}",
    )
    require(
        0.03 <= min(graph_only_coverage_at_05)
        and max(graph_only_coverage_at_05) <= 0.61,
        "5% graph-only calibration mismatch: "
        f"{graph_only_coverage_at_05}",
    )
    require(
        0.075 <= min(graph_only_coverage_at_15)
        and max(graph_only_coverage_at_15) <= 0.93,
        "15% graph-only calibration mismatch: "
        f"{graph_only_coverage_at_15}",
    )
    require(
        0.15 <= min(joint_coverage_at_15)
        and max(joint_coverage_at_15) <= 0.93,
        f"15% joint threshold coverage mismatch: {joint_coverage_at_15}",
    )

    split = load(RC / "gate_split.json")["corpora"]
    paper_point = [
        row["deploy_graphguard_paper_point"] for row in split.values()
    ]
    require(
        max(row["pub_harm_rate"] for row in paper_point) <= 0.08,
        "held-out paper-point harm exceeds reported 0–8%",
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
        and max(held_out_publish_all) <= 0.30,
        "held-out publish-all harm is outside reported 21–29%",
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
        0.38 <= min(recall_at_40) and max(recall_at_40) <= 0.53,
        f"40% budget recall mismatch: {recall_at_40}",
    )
    require(
        0.58 <= min(recall_at_60) and max(recall_at_60) <= 0.78,
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
        diagnostic = load(RC / f"diagnostic_{run}.json")
        source = manifest["source_databases"][run]
        require(
            source["path"] == db_path.relative_to(ROOT).as_posix()
            and source["bytes"] == db_path.stat().st_size
            and source["sha256"] == sha256_file(db_path),
            f"{label}: reproducibility-manifest database identity mismatch",
        )
        require(
            diagnostic["source_database"]["sha256"]
            == source["sha256"],
            f"{label}: diagnostic source database SHA-256 mismatch",
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
        verify_external_toolchain_queries()
        verify_cross_document_experiment()
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
