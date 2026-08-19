#!/usr/bin/env python3
"""Check the private manuscript's final figures and result tables.

The public result verifier checks machine-readable evidence.  This companion
check closes the last mile: it verifies that every figure consumed by
``paper/main.tex`` is the canonical asset copy and that the numerical
tables in the paper (plus their response-letter counterparts) still match the
authoritative JSON artifacts.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.contracts import REGISTRY  # noqa: E402
from sync_paper_figures import ACTIVE_FIGURES, sha256_file  # noqa: E402


class ManuscriptMismatch(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ManuscriptMismatch(message)


def load_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def require_fragment(text: str, fragment: str, context: str) -> None:
    require(fragment in text, f"{context}: missing `{fragment}`")


def verify_inventory() -> None:
    main = (ROOT / "paper" / "main.tex").read_text(encoding="utf-8")
    figures = {
        Path(name).name
        for name in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", main)
    }
    require(
        figures == set(ACTIVE_FIGURES),
        f"main figure inventory mismatch: {sorted(figures)}",
    )

    tables = set(re.findall(r"\\input\{tables/([^}]+)\}", main))
    expected_tables = {
        "tab_contracts",
        "tab_runs",
        "tab_queries",
        "tab_contractnum",
        "tab_familydecomp",
        "tab_langchain",
        "tab_crossdoc",
    }
    require(
        tables == expected_tables,
        f"main table inventory mismatch: {sorted(tables)}",
    )

    for name in ACTIVE_FIGURES:
        canonical = ROOT / "assets" / "figures" / name
        manuscript = ROOT / "paper" / "figures" / name
        require(canonical.is_file(), f"missing canonical figure: {name}")
        require(manuscript.is_file(), f"missing manuscript figure: {name}")
        require(
            sha256_file(canonical) == sha256_file(manuscript),
            f"figure copies differ: {name}",
        )
    print("[PASS] manuscript inventory and 13 figure hashes")


def verify_contract_table() -> None:
    path = ROOT / "paper" / "tables" / "tab_contracts.tex"
    tex = compact(path.read_text(encoding="utf-8"))
    tex = tex[tex.find(r"\midrule"):]
    macros = {
        "K1": r"\KOne",
        "K1b": r"\KOneB",
        "K1c": r"\KOneC",
        "K2": r"\KTwo",
        "K3": r"\KThree",
        "K4": r"\KFour ",
        "K4b": r"\KFour$^{b}$",
        "K4c": r"\KFour$^{c}$",
        "K4d": r"\KFour$^{d}$",
        "K5": r"\KFive",
        "K6": r"\KSix",
    }
    for contract_id, macro in macros.items():
        contract = REGISTRY[contract_id]
        tolerance = (
            1.0 - contract.threshold
            if contract.direction == "min"
            else contract.threshold
        )
        start = tex.find(macro)
        require(start >= 0, f"contract table: missing {contract_id}")
        row_end = tex.find(r"\\", start)
        require(row_end >= 0, f"contract table: unterminated {contract_id}")
        row = tex[start:row_end]
        require_fragment(
            row,
            f"{tolerance:.2f}",
            f"contract table {contract_id} drift tolerance",
        )
    print("[PASS] declarative contract table")


def verify_runs_table() -> None:
    samples = load_json("reports/cross_run/sampled_document_ids.json")["runs"]
    tex = compact(
        (ROOT / "paper" / "tables" / "tab_runs.tex").read_text(encoding="utf-8")
    )
    expected = {
        "docred__deepseek-v4-flash__300d": ("DocRED", "DS-V4-Flash"),
        "redocred__deepseek-v4-flash__300d": ("Re-DocRED", "DS-V4-Flash"),
        "scierc__deepseek-v4-flash__100d": ("SciERC", "DS-V4-Flash"),
        "cdr__deepseek-v4-flash__300d": ("BC5CDR", "DS-V4-Flash"),
        "docred__glm-5__100d": ("DocRED", "GLM-5"),
        "docred__kimi-k2__100d": ("DocRED", "Kimi-K2"),
        "docred__qwen3-32b__100d": ("DocRED", "Qwen3-32B"),
    }
    for run, (corpus, extractor) in expected.items():
        n = samples[run]["n_selected"]
        # Bold markup is used only on the primary row, so compare tokens
        # independently rather than hard-coding presentation.
        require(corpus in tex and extractor in tex, f"runs table: missing {run}")
        require(
            re.search(rf"{re.escape(extractor)}[^\\\\]*& {n} ", tex) is not None,
            f"runs table: selected count mismatch for {run}",
        )
    print("[PASS] run table and sampled-document counts")


def verify_query_table() -> None:
    tex = compact(
        (ROOT / "paper" / "tables" / "tab_queries.tex").read_text(encoding="utf-8")
    )
    labels = {
        "Q_1": "Lookup",
        "Q_2": "Neighbor",
        "Q_3": "Join",
        "Q_4": "Two-hop",
        "Q_5": "Shortest path",
        "Q_6": "Aggregation",
        "Q_7": "RAG retrieval",
        "X_1": "Cross-document fanout",
        "X_2": "Cross-document shared tail",
    }
    for query_id, label in labels.items():
        require_fragment(tex, f"${query_id}$", f"query table {query_id}")
        require_fragment(tex, label, f"query table {query_id}")
    for contract_id, query_id in {
        "K4b": "Q5",
        "K4c": "Q6",
        "K4d": "Q7",
    }.items():
        require(
            REGISTRY[contract_id].query_id == query_id,
            f"{contract_id}: registry query mismatch",
        )
    print("[PASS] query table and registered query contracts")


def verify_cross_document_text() -> None:
    result = load_json("reports/cross_run/cross_document_cdr.json")
    summary = result["summary"]
    order = summary["comparisons"]["order"]
    seed = summary["comparisons"]["seed"]
    excess = summary["order_minus_seed"]["max_query_drift"]
    main = compact((ROOT / "paper" / "main.tex").read_text(encoding="utf-8"))
    response = compact(
        (ROOT / "paper" / "response.tex").read_text(encoding="utf-8")
    )

    main_table = compact(
        (ROOT / "paper" / "tables" / "tab_crossdoc.tex").read_text(
            encoding="utf-8"
        )
    )
    for tex, context in (
        (main_table, "main cross-document table"),
        (response, "response cross-document table"),
    ):
        require_fragment(
            tex,
            (
                "Provenance graph & "
                f"${order['provenance_graph_drift']['mean']:.3f}\\,["
                f"{order['provenance_graph_drift']['ci95'][0]:.3f},"
                f"{order['provenance_graph_drift']['ci95'][1]:.3f}]$ & "
                f"${seed['provenance_graph_drift']['mean']:.3f}\\,["
                f"{seed['provenance_graph_drift']['ci95'][0]:.3f},"
                f"{seed['provenance_graph_drift']['ci95'][1]:.3f}]$"
            ),
            context,
        )
        require_fragment(
            tex,
            (
                "Active query & "
                f"${order['max_query_drift']['mean']:.3f}\\,["
                f"{order['max_query_drift']['ci95'][0]:.3f},"
                f"{order['max_query_drift']['ci95'][1]:.3f}]$ & "
                f"${seed['max_query_drift']['mean']:.3f}\\,["
                f"{seed['max_query_drift']['ci95'][0]:.3f},"
                f"{seed['max_query_drift']['ci95'][1]:.3f}]$"
            ),
            context,
        )
        for fragment in (
            "prediction-independent, document-disjoint, gold-witness pairs",
            "oracle MeSH linking",
            "95\\% packet-bootstrap CI",
        ):
            require_fragment(tex, fragment, context)
    excess_value = f"${excess['mean']:.3f}$"
    excess_ci = (
        f"$[{excess['ci95'][0]:.3f},"
        f"{excess['ci95'][1]:.3f}]$"
    )
    for tex, context in (
        (main, "main cross-document excess"),
        (response, "response cross-document excess"),
    ):
        require_fragment(tex, excess_value, context)
        require_fragment(tex, "95\\% CI", context)
        require_fragment(tex, excess_ci, context)
    require_fragment(
        main,
        "All $1{,}000$ Kuzu answer sets match the deterministic executor",
        "main cross-document Kuzu parity",
    )
    for fragment in (
        "$100$ prediction-independent, document-disjoint, gold-witness-enriched BC5CDR pairs",
        "oracle MeSH linking",
        "$1{,}000$ Kuzu",
        "$[-0.023,0.101]$",
    ):
        require_fragment(response, fragment, "response cross-document evidence")
    print("[PASS] cross-document manuscript and response numbers")


def verify_contract_outcomes() -> None:
    contracts = load_json(
        "reports/runs/docred__deepseek-v4-flash__300d/eval/contracts.json"
    )["contracts"]
    rows = {row["contract_id"]: row for row in contracts}
    k5 = load_json("reports/cross_run/k5_cross_model.json")["pooled_primary"]
    tex = compact(
        (ROOT / "paper" / "tables" / "tab_contractnum.tex").read_text(
            encoding="utf-8"
        )
    )
    tex = tex[tex.find(r"\midrule"):]
    macros = {
        "K1": r"\KOne",
        "K1b": r"\KOneB",
        "K1c": r"\KOneC",
        "K2": r"\KTwo",
        "K3": r"\KThree",
        "K4": r"\KFour",
        "K5": r"\KFive",
        "K6": r"\KSix",
    }
    for contract_id, macro in macros.items():
        if contract_id == "K5":
            values = (
                k5["n"],
                k5["mean_abs_diff"],
                k5["frac_above_tau"],
                k5["severity_mean"],
            )
        else:
            row = rows[contract_id]
            metric = (
                1.0 - row["metric_mean"]
                if row["direction"] == "min"
                else row["metric_mean"]
            )
            values = (
                row["n_pairs"],
                metric,
                row["violation_rate"],
                row["severity_mean"],
            )
        start = tex.find(macro)
        require(start >= 0, f"contract outcome table: missing {contract_id}")
        row_end = tex.find(r"\\", start)
        row_text = tex[start:row_end]
        expected = (
            f"& {values[0]} & {values[1]:.2f} & "
            f"{values[2]:.2f} & {values[3]:.2f} &"
        )
        require_fragment(
            row_text,
            expected,
            f"contract outcome table {contract_id}",
        )
    print("[PASS] numerical contract-outcome table")


def family_expected_rows() -> dict[str, tuple[str, ...]]:
    summary = load_json(
        "reports/cross_run/"
        "family_decomp_docred__deepseek-v4-flash__300d.json"
    )["summary"]
    labels = {
        "stochastic": "Decoding resample",
        "entity_alias": "Entity alias",
        "evidence": "Evidence",
        "prompt": "Prompt",
        "schema-pres": "Schema (present.)",
        "schema-sem": "Schema (semantic)",
    }
    return {
        label: tuple(
            f"{row[key]:.2f}"
            for key in ("overlap", "pair_overlap", "type_agree", "disappear", "new")
        )
        for key, label in labels.items()
        for row in [summary[key]]
    }


def verify_family_table(path: Path) -> None:
    tex = compact(path.read_text(encoding="utf-8"))
    for label, values in family_expected_rows().items():
        expected = label + " & " + " & ".join(values)
        require_fragment(tex, expected, path.name)


def external_toolchain_expected_rows() -> dict[
    str,
    tuple[tuple[str, str], tuple[str, str]],
]:
    langchain = load_json(
        "reports/cross_run/langchain_toolchain.json"
    )["summary"]
    neo4j = load_json("reports/cross_run/neo4j_toolchain.json")["summary"]
    keys = {
        "Schema reorder": "schema_reorder",
        "Schema rename": "schema_rename",
        "Prompt paraphrase": "prompt_para",
        "Evidence reorder": "evidence_reorder",
        "Decoding resample": "resample",
    }
    return {
        label: (
            (
                f"{langchain[key]['mean_drift']:.2f}",
                f"{langchain[key]['violation_rate']:.2f}",
            ),
            (
                f"{neo4j[key]['mean_drift']:.2f}",
                f"{neo4j[key]['violation_rate']:.2f}",
            ),
        )
        for label, key in keys.items()
    }


def verify_external_toolchain_table(path: Path) -> None:
    tex = compact(path.read_text(encoding="utf-8"))
    for label, (langchain, neo4j) in external_toolchain_expected_rows().items():
        start = tex.find(label)
        require(start >= 0, f"{path.name}: missing {label}")
        row_end = tex.find(r"\\", start)
        row = tex[start:row_end]
        require_fragment(
            row,
            (
                f"& {langchain[0]}, {langchain[1]} "
                f"& {neo4j[0]}, {neo4j[1]}"
            ),
            path.name,
        )
    query_artifact = load_json(
        "reports/cross_run/external_toolchain_q1q4_kuzu.json"
    )
    cells = []
    for toolchain in ("langchain", "neo4j"):
        summary = query_artifact["toolchains"][toolchain]["summary"]
        drifts = [
            row["mean_pair_max_query_drift"] for row in summary.values()
        ]
        violations = [
            row["violation_rate"] for row in summary.values()
        ]
        cells.append(
            f"{min(drifts):.2f}--{max(drifts):.2f}, "
            f"{min(violations):.2f}--{max(violations):.2f}"
        )
    require_fragment(
        tex,
        (
            f"Kuzu Q1--Q4 (range) & {cells[0]} "
            f"& {cells[1]}"
        ),
        path.name,
    )


def verify_response_k5() -> None:
    tex = compact((ROOT / "paper" / "response.tex").read_text(encoding="utf-8"))
    pairs = load_json("reports/cross_run/k5_model_size.json")["pairs"]
    labels = {
        "Qwen3-8B vs Qwen3-14B": "Qwen 8B--14B",
        "Qwen3-8B vs Qwen3-32B": "Qwen 8B--32B",
        "Qwen3-14B vs Qwen3-32B": "Qwen 14B--32B",
    }
    for key, label in labels.items():
        row = pairs[key]
        expected = (
            f"{label} & {row['mean_graph_drift']:.2f} & "
            f"{row['mean_abs_diff']:.3f} & {row['frac_above_tau']:.2f} &"
        )
        require_fragment(tex, expected, f"response K5 row {key}")
    print("[PASS] response K5 size-ladder table")


def main() -> int:
    try:
        require((ROOT / "paper").is_dir(), "private paper directory is absent")
        verify_inventory()
        verify_contract_table()
        verify_runs_table()
        verify_query_table()
        verify_cross_document_text()
        verify_contract_outcomes()
        verify_family_table(ROOT / "paper" / "tables" / "tab_familydecomp.tex")
        verify_external_toolchain_table(
            ROOT / "paper" / "tables" / "tab_langchain.tex"
        )
        response = ROOT / "paper" / "response.tex"
        verify_family_table(response)
        verify_external_toolchain_table(response)
        verify_response_k5()
    except (
        FileNotFoundError,
        KeyError,
        TypeError,
        ManuscriptMismatch,
    ) as exc:
        print(f"[FAIL] {exc}")
        return 1
    print("[PASS] manuscript figures and tables match authoritative artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
