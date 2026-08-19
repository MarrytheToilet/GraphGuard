import json
import tempfile
from pathlib import Path

import pytest

from graphguard.cross_document import (
    CrossDocumentKuzuGraph,
    build_cross_document_cohort,
    execute_cross_document_query,
    load_cdr_inputs,
    localize_edges,
    normalize_joint_response,
    render_joint_prompt,
    sha256_file,
    summarize_records,
)
from scripts.package_cross_document_checkpoint import package


ROOT = Path(__file__).resolve().parents[1]
RAW = (
    ROOT
    / "data/raw/cdr/CDR_Data/CDR.Corpus.v010516/"
    "CDR_DevelopmentSet.PubTator.txt"
)
RUN = "cdr__deepseek-v4-flash__300d"
DB = ROOT / "data/processed/runs" / RUN / f"{RUN}.db"
SAMPLES = ROOT / "reports/cross_run/sampled_document_ids.json"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _package_fixture(directory: Path, *, stale_sha: bool = False):
    source = directory / "data/private.jsonl"
    output = directory / "reports/cache.jsonl"
    result = directory / "reports/result.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for packet_index in range(100):
        packet_id = f"packet-{packet_index:03d}"
        for condition in (
            "joint_ab_seed7",
            "joint_ba_seed7",
            "joint_ab_seed13",
        ):
            records.append(
                {
                    "packet_id": packet_id,
                    "condition": condition,
                    "status": "ok",
                    "prompt_tokens": 1,
                    "completion_tokens": 2,
                    "raw_response_text": "{}",
                    "edges": [],
                }
            )
    source.write_text(
        "".join(json.dumps(row) + "\n" for row in records),
        encoding="utf-8",
    )
    cohort = {
        "path": "reports/cross_run/cross_document_cdr_cohort.json",
        "sha256": "cohort-sha",
        "packets_sha256": "packets-sha",
    }
    manifest_path = source.with_suffix(source.suffix + ".manifest.json")
    _write_json(
        manifest_path,
        {
            "artifact_type": (
                "graphguard.cross_document_cdr_checkpoint_manifest"
            ),
            "artifact_version": 1,
            "design_id": "test-design",
            "cohort": cohort,
        },
    )
    _write_json(
        result,
        {
            "artifact_type": "graphguard.cross_document_cdr_results",
            "artifact_version": 1,
            "design_id": "test-design",
            "cohort": cohort,
            "checkpoint_manifest": {
                "path": str(manifest_path.relative_to(ROOT)),
                "sha256": (
                    "stale" if stale_sha else sha256_file(manifest_path)
                ),
            },
        },
    )
    return source, output, result


def _registered_inputs():
    return load_cdr_inputs(
        raw_path=RAW,
        db_path=DB,
        samples_path=SAMPLES,
        run_id=RUN,
    )


def test_queries_require_different_source_documents():
    edges = {
        ("C", "CID", "D1", "doc-a"),
        ("C", "CID", "D2", "doc-b"),
        ("C1", "CID", "D", "doc-a"),
        ("C2", "CID", "D", "doc-b"),
        ("X", "CID", "Y1", "doc-a"),
        ("X", "CID", "Y2", "doc-a"),
    }

    assert execute_cross_document_query(edges, "crossdoc_fanout") == {
        ("C", "D1", "D2")
    }
    assert execute_cross_document_query(edges, "crossdoc_shared_tail") == {
        ("C1", "C2", "D")
    }
    localized = localize_edges(edges)
    assert not execute_cross_document_query(localized, "crossdoc_fanout")
    assert not execute_cross_document_query(
        localized, "crossdoc_shared_tail"
    )


def test_kuzu_matches_provenance_executor():
    edges = {
        "packet": {
            ("C", "CID", "D1", "doc-a"),
            ("C", "CID", "D2", "doc-b"),
            ("C1", "CID", "D", "doc-a"),
            ("C2", "CID", "D", "doc-b"),
        }
    }
    with CrossDocumentKuzuGraph(edges) as graph:
        for family in ("crossdoc_fanout", "crossdoc_shared_tail"):
            assert graph.execute("packet", family) == (
                execute_cross_document_query(edges["packet"], family)
            )


def test_registered_mesh_mapping_and_cohort_are_deterministic():
    inputs = _registered_inputs()
    assert inputs.mapping_audit["n_documents"] == 300
    assert inputs.mapping_audit["n_local_entities"] == 2009
    assert inputs.mapping_audit["n_unique_mesh_ids"] == 952
    assert inputs.mapping_audit["n_repeated_mesh_ids"] == 362
    assert inputs.mapping_audit["n_documents_with_repeated_mesh"] == 299
    assert inputs.mapping_audit["unmapped_gold_rows"] == 0
    assert inputs.mapping_audit["base_edge_mapping_rate"] > 0.98

    first = build_cross_document_cohort(inputs, n_packets=100)
    second = build_cross_document_cohort(inputs, n_packets=100)
    assert first == second
    documents = [doc for packet in first for doc in packet["documents"]]
    assert len(documents) == len(set(documents)) == 200
    assert all(packet["active_queries"] for packet in first)


def test_joint_prompt_swap_changes_only_document_block_order():
    inputs = _registered_inputs()
    packet = build_cross_document_cohort(inputs, n_packets=1)[0]
    prompt_ab = render_joint_prompt(inputs, packet, order="ab")
    prompt_ba = render_joint_prompt(inputs, packet, order="ba")

    assert prompt_ab != prompt_ba
    for document_id in packet["documents"]:
        assert prompt_ab.count(f"### Document {document_id}") == 1
        assert prompt_ba.count(f"### Document {document_id}") == 1
    registry_ab = prompt_ab.split("## Documents", 1)[0]
    registry_ba = prompt_ba.split("## Documents", 1)[0]
    assert registry_ab == registry_ba


def test_joint_normalizer_rejects_wrong_provenance_and_direction():
    inputs = _registered_inputs()
    packet = build_cross_document_cohort(inputs, n_packets=1)[0]
    document_id = packet["documents"][0]
    entities = inputs.documents[document_id]["entities"]
    chemical = next(
        entity for entity in entities if entity["entity_type"] == "Chemical"
    )
    disease = next(
        entity for entity in entities if entity["entity_type"] == "Disease"
    )
    parsed = {
        "edges": [
            {
                "subject_mesh_id": chemical["mesh_id"],
                "relation": "CID",
                "object_mesh_id": disease["mesh_id"],
                "source_document_id": document_id,
                "evidence_sentence_ids": [1],
            },
            {
                "subject_mesh_id": disease["mesh_id"],
                "relation": "CID",
                "object_mesh_id": chemical["mesh_id"],
                "source_document_id": document_id,
                "evidence_sentence_ids": [1],
            },
            {
                "subject_mesh_id": chemical["mesh_id"],
                "relation": "CID",
                "object_mesh_id": disease["mesh_id"],
                "source_document_id": "not-in-packet",
                "evidence_sentence_ids": [1],
            },
        ]
    }

    edges, audit = normalize_joint_response(parsed, inputs, packet)
    assert edges == {
        (
            chemical["mesh_id"],
            "CID",
            disease["mesh_id"],
            document_id,
        )
    }
    assert audit["invalid_cid_direction"] == 1
    assert audit["invalid_provenance"] == 1


def test_published_cache_and_result_are_self_consistent():
    cache = ROOT / "reports/cross_run/cross_document_cdr_cache.jsonl"
    manifest = cache.with_suffix(cache.suffix + ".manifest.json")
    audit_path = cache.with_suffix(cache.suffix + ".audit.json")
    result_path = ROOT / "reports/cross_run/cross_document_cdr.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in cache.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(records) == 302
    assert len({(row["packet_id"], row["condition"]) for row in records}) == 300
    assert sum(row["status"] == "parse_error" for row in records) == 2
    assert all("raw_response_text" not in row for row in records)
    assert audit["published_cache"]["sha256"] == sha256_file(cache)
    assert audit["published_cache"]["manifest_sha256"] == sha256_file(manifest)
    assert audit["result_artifact"]["sha256"] == sha256_file(result_path)
    assert audit["endpoint_attempts"]["total_tokens"] == 1_475_253
    assert result["negative_control"]["document_local_cross_document_answers"] == 0
    assert result["kuzu_parity"] == {
        "kuzu_version": "0.11.3",
        "answer_sets_checked": 1000,
        "mismatches": [],
        "status": "pass",
    }
    assert summarize_records(result["per_packet"]) == result["summary"]


def test_packager_rebinds_private_result_and_is_idempotent():
    with tempfile.TemporaryDirectory(
        prefix=".crossdoc-package-test-",
        dir=ROOT,
    ) as temporary:
        source, output, result = _package_fixture(Path(temporary))
        first = package(source, output, result)
        output_manifest = output.with_suffix(output.suffix + ".manifest.json")
        rebound = json.loads(result.read_text(encoding="utf-8"))
        assert rebound["checkpoint_manifest"] == {
            "path": str(output_manifest.relative_to(ROOT)),
            "sha256": sha256_file(output_manifest),
        }
        assert first["published_cache"]["sha256"] == sha256_file(output)
        assert first["result_artifact"]["sha256"] == sha256_file(result)
        assert all(
            "raw_response_text" not in json.loads(line)
            for line in output.read_text(encoding="utf-8").splitlines()
        )

        hashes = {
            path: sha256_file(path)
            for path in (
                output,
                output_manifest,
                result,
                output.with_suffix(output.suffix + ".audit.json"),
            )
        }
        package(source, output, result)
        assert hashes == {path: sha256_file(path) for path in hashes}


def test_packager_rejects_stale_manifest_before_target_writes():
    with tempfile.TemporaryDirectory(
        prefix=".crossdoc-package-test-",
        dir=ROOT,
    ) as temporary:
        source, output, result = _package_fixture(
            Path(temporary),
            stale_sha=True,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output_manifest = output.with_suffix(output.suffix + ".manifest.json")
        audit = output.with_suffix(output.suffix + ".audit.json")
        output.write_bytes(b"old-cache")
        output_manifest.write_bytes(b"old-manifest")
        audit.write_bytes(b"old-audit")
        before = {
            path: path.read_bytes()
            for path in (output, output_manifest, result, audit)
        }

        with pytest.raises(ValueError, match="manifest SHA-256 mismatch"):
            package(source, output, result)
        assert before == {path: path.read_bytes() for path in before}
