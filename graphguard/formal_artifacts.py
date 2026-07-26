"""Verified access to the frozen RQ8--RQ10 evidence package.

The public package stores large JSON artifacts as deterministic gzip streams.
Their embedded provenance continues to refer to the uncompressed JSON bytes,
so both transport and logical hashes are checked before an artifact is used.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from graphguard.deployment_cohorts import canonical_digest


FORMAL_INDEX_TYPE = "graphguard.formal_artifact_index"
FORMAL_INDEX_VERSION = 1
DEFAULT_INDEX = Path("reports/cross_run/formal_artifacts_v1.json")
PRIMARY_RUNS = (
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
)


@dataclass(frozen=True)
class ArtifactSpec:
    role: str
    source_run: str | None
    logical_path: str
    compression: str | None
    artifact_type: str
    artifact_version: int

    @property
    def key(self) -> str:
        return (
            self.role
            if self.source_run is None
            else f"{self.role}:{self.source_run}"
        )

    @property
    def transport_path(self) -> str:
        if self.compression == "gzip":
            return self.logical_path + ".gz"
        return self.logical_path


def expected_artifact_specs() -> dict[str, ArtifactSpec]:
    specs = [
        ArtifactSpec(
            role="cohort_manifest",
            source_run=None,
            logical_path="reports/cross_run/deployment_cohorts_v1.json",
            compression=None,
            artifact_type="graphguard.deployment_q1q4_cohorts",
            artifact_version=1,
        )
    ]
    for run in PRIMARY_RUNS:
        specs.extend(
            (
                ArtifactSpec(
                    role="deployment",
                    source_run=run,
                    logical_path=(
                        "reports/cross_run/deployment_q1q4_v1_"
                        f"{run}.json"
                    ),
                    compression="gzip",
                    artifact_type=(
                        "graphguard.deployment_q1q4_amplification"
                    ),
                    artifact_version=1,
                ),
                ArtifactSpec(
                    role="downstream",
                    source_run=run,
                    logical_path=(
                        "reports/cross_run/deployment_downstream_v1_"
                        f"{run}.json"
                    ),
                    compression="gzip",
                    artifact_type="graphguard.deployment_q1q4_downstream",
                    artifact_version=1,
                ),
                ArtifactSpec(
                    role="kuzu",
                    source_run=run,
                    logical_path=(
                        "reports/cross_run/deployment_kuzu_cohort_v1_"
                        f"{run}.json"
                    ),
                    compression="gzip",
                    artifact_type=(
                        "graphguard.deployment_q1q4_kuzu_cohort"
                    ),
                    artifact_version=1,
                ),
                ArtifactSpec(
                    role="parity",
                    source_run=run,
                    logical_path=(
                        "reports/cross_run/deployment_q1q4_v1_"
                        f"{run}__kuzu_parity.json"
                    ),
                    compression=None,
                    artifact_type=(
                        "graphguard.deployment_q1q4_kuzu_parity"
                    ),
                    artifact_version=1,
                ),
            )
        )
    return {spec.key: spec for spec in specs}


def _repo_path(repo_root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ValueError(f"artifact path must be relative: {relative_path}")
    root = repo_root.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"artifact path escapes repository: {relative_path}")
    return resolved


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _object_without_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _parse_json_object(raw: bytes, label: str) -> dict:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON in {label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _require_size_and_sha(
    value: bytes,
    *,
    expected_size: int,
    expected_sha256: str,
    label: str,
) -> None:
    if len(value) != expected_size:
        raise ValueError(
            f"{label} size mismatch: {len(value)} != {expected_size}"
        )
    actual = _sha256(value)
    if actual != expected_sha256:
        raise ValueError(
            f"{label} SHA mismatch: {actual} != {expected_sha256}"
        )


def _decompress_bounded(
    compressed: bytes,
    *,
    expected_size: int,
    label: str,
) -> bytes:
    try:
        with gzip.GzipFile(fileobj=__import__("io").BytesIO(compressed)) as gz:
            raw = gz.read(expected_size + 1)
            trailing = gz.read(1)
    except (OSError, EOFError) as exc:
        raise ValueError(f"invalid gzip stream for {label}") from exc
    if len(raw) > expected_size or trailing:
        raise ValueError(f"decompressed {label} exceeds registered size")
    return raw


def load_artifact_index(
    repo_root: str | Path,
    index_path: str | Path = DEFAULT_INDEX,
) -> dict:
    repo_root = Path(repo_root)
    path = Path(index_path)
    if not path.is_absolute():
        path = _repo_path(repo_root, str(path))
    raw = path.read_bytes()
    index = _parse_json_object(raw, str(path))
    if index.get("artifact_type") != FORMAL_INDEX_TYPE:
        raise ValueError("formal artifact index type mismatch")
    if index.get("artifact_version") != FORMAL_INDEX_VERSION:
        raise ValueError("formal artifact index version mismatch")
    implementation = index.get("implementation")
    if not isinstance(implementation, dict):
        raise ValueError("formal artifact index implementation is missing")
    implementation_path = implementation.get("path")
    implementation_sha = implementation.get("sha256")
    if (
        implementation_path != "scripts/package_formal_artifacts.py"
        or not isinstance(implementation_sha, str)
        or len(implementation_sha) != 64
    ):
        raise ValueError("formal artifact index implementation mismatch")
    packager = _repo_path(repo_root, implementation_path)
    if _sha256(packager.read_bytes()) != implementation_sha:
        raise ValueError("formal artifact packager SHA mismatch")
    entries = index.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("formal artifact index entries must be an object")
    specs = expected_artifact_specs()
    if set(entries) != set(specs):
        missing = sorted(set(specs) - set(entries))
        extra = sorted(set(entries) - set(specs))
        raise ValueError(
            f"formal artifact index entry mismatch; "
            f"missing={missing}, extra={extra}"
        )
    for key, spec in specs.items():
        entry = entries[key]
        expected = {
            "role": spec.role,
            "source_run": spec.source_run,
            "logical_path": spec.logical_path,
            "transport_path": spec.transport_path,
            "compression": spec.compression,
            "artifact_type": spec.artifact_type,
            "artifact_version": spec.artifact_version,
        }
        for field, value in expected.items():
            if entry.get(field) != value:
                raise ValueError(f"{key}: index {field} mismatch")
        for field in (
            "raw_size_bytes",
            "transport_size_bytes",
        ):
            if not isinstance(entry.get(field), int) or entry[field] <= 0:
                raise ValueError(f"{key}: invalid {field}")
        for field in ("raw_sha256", "transport_sha256"):
            value = entry.get(field)
            if not isinstance(value, str) or len(value) != 64:
                raise ValueError(f"{key}: invalid {field}")
    return index


def _read_registered_bytes(
    repo_root: Path,
    entry: Mapping,
    *,
    label: str,
) -> bytes:
    logical_path = _repo_path(repo_root, entry["logical_path"])
    transport_path = _repo_path(repo_root, entry["transport_path"])
    compression = entry["compression"]

    logical_raw = logical_path.read_bytes() if logical_path.exists() else None
    if logical_raw is not None:
        _require_size_and_sha(
            logical_raw,
            expected_size=entry["raw_size_bytes"],
            expected_sha256=entry["raw_sha256"],
            label=f"{label} logical artifact",
        )

    if not transport_path.exists():
        raise FileNotFoundError(
            f"registered transport artifact is missing: {transport_path}"
        )
    transport = transport_path.read_bytes()
    _require_size_and_sha(
        transport,
        expected_size=entry["transport_size_bytes"],
        expected_sha256=entry["transport_sha256"],
        label=f"{label} transport artifact",
    )
    if compression == "gzip":
        raw = _decompress_bounded(
            transport,
            expected_size=entry["raw_size_bytes"],
            label=label,
        )
    elif compression is None:
        raw = transport
    else:
        raise ValueError(f"{label}: unsupported compression {compression}")
    _require_size_and_sha(
        raw,
        expected_size=entry["raw_size_bytes"],
        expected_sha256=entry["raw_sha256"],
        label=f"{label} uncompressed artifact",
    )
    if logical_raw is not None and logical_raw != raw:
        raise ValueError(f"{label}: logical and transport bytes differ")
    return raw


def load_registered_artifact(
    repo_root: str | Path,
    role: str,
    source_run: str | None = None,
    *,
    index: dict | None = None,
) -> dict:
    repo_root = Path(repo_root)
    if index is None:
        index = load_artifact_index(repo_root)
    key = role if source_run is None else f"{role}:{source_run}"
    if key not in index["entries"]:
        raise KeyError(f"unregistered formal artifact: {key}")
    entry = index["entries"][key]
    artifact = _parse_json_object(
        _read_registered_bytes(repo_root, entry, label=key),
        key,
    )
    if artifact.get("artifact_type") != entry["artifact_type"]:
        raise ValueError(f"{key}: artifact type mismatch")
    if artifact.get("artifact_version") != entry["artifact_version"]:
        raise ValueError(f"{key}: artifact version mismatch")
    if source_run is not None and artifact.get("source_run") != source_run:
        raise ValueError(f"{key}: source run mismatch")
    return artifact


def _require_reference_sha(
    reference: Mapping,
    expected_sha256: str,
    label: str,
) -> None:
    if reference.get("sha256") != expected_sha256:
        raise ValueError(f"{label} reference SHA mismatch")


def _validate_selection(selection: Mapping, label: str) -> list[str]:
    selected = selection.get("selected_run_ids")
    retained = selection.get("retained_run_ids")
    replacements = selection.get("replacement_run_ids")
    excluded = selection.get("excluded")
    if not all(
        isinstance(value, list)
        for value in (selected, retained, replacements, excluded)
    ):
        raise ValueError(f"{label}: selection lists are incomplete")
    target = selection.get("target_size")
    if not isinstance(target, int) or target <= 0:
        raise ValueError(f"{label}: target size is invalid")
    if len(selected) != target or len(selected) != len(set(selected)):
        raise ValueError(f"{label}: selected IDs are not unique and complete")
    if selected != retained + replacements:
        raise ValueError(f"{label}: selected ID order mismatch")
    expected_counts = {
        "n_legacy": target,
        "n_retained": len(retained),
        "n_excluded": len(excluded),
        "n_replacements": len(replacements),
    }
    for field, expected in expected_counts.items():
        if selection.get(field) != expected:
            raise ValueError(f"{label}: {field} mismatch")
    if len(excluded) != len(replacements):
        raise ValueError(f"{label}: exclusions/replacements are unbalanced")
    if canonical_digest(selected) != selection.get(
        "selected_run_ids_sha256"
    ):
        raise ValueError(f"{label}: selected ID digest mismatch")
    return list(selected)


def _manifest_selection(manifest: Mapping, source_run: str) -> dict:
    try:
        entry = manifest["cohorts"]["rq10_n300"][source_run]
        selection = entry["selection"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"manifest lacks RQ10 selection for {source_run}"
        ) from exc
    _validate_selection(selection, f"{source_run} RQ10")
    return entry


def load_formal_downstream(
    repo_root: str | Path,
    source_run: str,
) -> dict:
    """Load a full formal downstream population and validate its hash chain."""
    repo_root = Path(repo_root)
    index = load_artifact_index(repo_root)
    deployment = load_registered_artifact(
        repo_root, "deployment", source_run, index=index
    )
    downstream = load_registered_artifact(
        repo_root, "downstream", source_run, index=index
    )
    parity = load_registered_artifact(
        repo_root, "parity", source_run, index=index
    )
    deployment_sha = index["entries"][
        f"deployment:{source_run}"
    ]["raw_sha256"]
    parity_sha = index["entries"][f"parity:{source_run}"]["raw_sha256"]
    _require_reference_sha(
        downstream["deployment_artifact"],
        deployment_sha,
        f"{source_run} downstream->deployment",
    )
    parity_ref = downstream["execution_evidence"]["kuzu_parity"]
    _require_reference_sha(
        parity_ref,
        parity_sha,
        f"{source_run} downstream->parity",
    )
    _require_reference_sha(
        parity["deployment_artifact"],
        deployment_sha,
        f"{source_run} parity->deployment",
    )
    if parity.get("status") != "pass" or parity.get("n_mismatches") != 0:
        raise ValueError(f"{source_run}: Kuzu parity did not pass")
    database_hashes = {
        deployment["source_database"]["sha256"],
        downstream["source_database"]["sha256"],
        parity["source_database"]["sha256"],
    }
    if len(database_hashes) != 1:
        raise ValueError(f"{source_run}: source database SHA chain mismatch")
    pairs = downstream.get("per_pair")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError(f"{source_run}: downstream population is empty")
    run_ids = [pair.get("run_id") for pair in pairs]
    if len(run_ids) != len(set(run_ids)) or None in run_ids:
        raise ValueError(f"{source_run}: downstream run IDs are invalid")
    return downstream


def load_rq8_pairs(
    repo_root: str | Path,
    source_run: str = "docred__deepseek-v4-flash__300d",
) -> list[dict]:
    """Return the exact manifest-registered RQ8 population in fixed order."""
    repo_root = Path(repo_root)
    index = load_artifact_index(repo_root)
    manifest = load_registered_artifact(
        repo_root, "cohort_manifest", index=index
    )
    downstream = load_formal_downstream(repo_root, source_run)
    try:
        manifest_entry = manifest["cohorts"]["rq8_docred_n4000"]
        selection = manifest_entry["selection"]
    except (KeyError, TypeError) as exc:
        raise ValueError("manifest lacks the RQ8 continuity cohort") from exc
    if manifest_entry["source"].get("source_run") != source_run:
        raise ValueError("RQ8 manifest source run mismatch")
    deployment_sha = index["entries"][
        f"deployment:{source_run}"
    ]["raw_sha256"]
    downstream_sha = index["entries"][
        f"downstream:{source_run}"
    ]["raw_sha256"]
    _require_reference_sha(
        manifest_entry["source"]["deployment_artifact"],
        deployment_sha,
        "RQ8 manifest->deployment",
    )
    _require_reference_sha(
        manifest_entry["source"]["downstream_artifact"],
        downstream_sha,
        "RQ8 manifest->downstream",
    )
    if (
        manifest_entry["source"]["source_database"]["sha256"]
        != downstream["source_database"]["sha256"]
    ):
        raise ValueError("RQ8 manifest source database SHA mismatch")
    selected = _validate_selection(selection, "RQ8")
    by_id = {pair["run_id"]: pair for pair in downstream["per_pair"]}
    missing = [run_id for run_id in selected if run_id not in by_id]
    if missing:
        raise ValueError(f"RQ8 formal pairs are missing: {missing[:3]}")
    return [by_id[run_id] for run_id in selected]


def load_formal_kuzu(
    repo_root: str | Path,
    source_run: str,
) -> dict:
    """Load actual-Kuzu N=300 evidence and validate the selected population."""
    repo_root = Path(repo_root)
    index = load_artifact_index(repo_root)
    manifest = load_registered_artifact(
        repo_root, "cohort_manifest", index=index
    )
    downstream = load_formal_downstream(repo_root, source_run)
    kuzu = load_registered_artifact(
        repo_root, "kuzu", source_run, index=index
    )
    manifest_entry = _manifest_selection(manifest, source_run)
    selected = manifest_entry["selection"]["selected_run_ids"]
    selected_digest = manifest_entry["selection"][
        "selected_run_ids_sha256"
    ]
    deployment_sha = index["entries"][
        f"deployment:{source_run}"
    ]["raw_sha256"]
    downstream_sha = index["entries"][
        f"downstream:{source_run}"
    ]["raw_sha256"]
    manifest_sha = index["entries"]["cohort_manifest"]["raw_sha256"]

    _require_reference_sha(
        manifest_entry["source"]["deployment_artifact"],
        deployment_sha,
        f"{source_run} manifest->deployment",
    )
    _require_reference_sha(
        manifest_entry["source"]["downstream_artifact"],
        downstream_sha,
        f"{source_run} manifest->downstream",
    )
    _require_reference_sha(
        kuzu["sources"]["deployment_artifact"],
        deployment_sha,
        f"{source_run} Kuzu->deployment",
    )
    _require_reference_sha(
        kuzu["sources"]["downstream_artifact"],
        downstream_sha,
        f"{source_run} Kuzu->downstream",
    )
    if kuzu["cohort"]["manifest"]["sha256"] != manifest_sha:
        raise ValueError(f"{source_run}: Kuzu manifest SHA mismatch")
    if kuzu.get("status") != "pass" or kuzu.get("complete") is not True:
        raise ValueError(f"{source_run}: Kuzu artifact is incomplete")
    if kuzu.get("runtime", {}).get("kuzu") != "0.11.3":
        raise ValueError(f"{source_run}: unexpected Kuzu version")
    if kuzu["cohort"].get("registered_target_size") != len(selected):
        raise ValueError(f"{source_run}: Kuzu target size mismatch")
    if kuzu["cohort"].get(
        "registered_selected_run_ids_sha256"
    ) != selected_digest:
        raise ValueError(f"{source_run}: Kuzu cohort digest mismatch")
    if kuzu["cohort"].get("executed_run_ids") != selected:
        raise ValueError(f"{source_run}: Kuzu execution order mismatch")
    pairs = kuzu.get("per_pair")
    if [pair.get("run_id") for pair in pairs] != selected:
        raise ValueError(f"{source_run}: Kuzu pair order mismatch")

    execution = kuzu.get("execution", {})
    n_pairs = len(selected)
    n_queries = sum(pair["n_queries"] for pair in pairs)
    expected_execution = {
        "n_pairs_expected": n_pairs,
        "n_pairs_completed": n_pairs,
        "n_graphs_materialized": 2 * n_pairs,
        "n_query_instances_checked": n_queries,
        "n_answer_sets_checked": 2 * n_queries,
        "n_mismatches": 0,
    }
    if execution != expected_execution:
        raise ValueError(f"{source_run}: Kuzu execution totals mismatch")

    downstream_by_id = {
        pair["run_id"]: pair for pair in downstream["per_pair"]
    }
    for pair in pairs:
        expected = downstream_by_id.get(pair["run_id"])
        if expected is None:
            raise ValueError(
                f"{source_run}: missing downstream pair {pair['run_id']}"
            )
        for field, value in expected.items():
            if pair.get(field) != value:
                raise ValueError(
                    f"{source_run}/{pair['run_id']}: "
                    f"Kuzu aggregate mismatch for {field}"
                )
    return kuzu


def validate_formal_package(repo_root: str | Path) -> dict:
    """Validate every frozen artifact, including full deployment JSON."""
    repo_root = Path(repo_root)
    index = load_artifact_index(repo_root)
    manifest = load_registered_artifact(
        repo_root, "cohort_manifest", index=index
    )
    summary = {}
    for run in PRIMARY_RUNS:
        deployment = load_registered_artifact(
            repo_root, "deployment", run, index=index
        )
        downstream = load_registered_artifact(
            repo_root, "downstream", run, index=index
        )
        parity = load_registered_artifact(
            repo_root, "parity", run, index=index
        )
        kuzu = load_formal_kuzu(repo_root, run)
        manifest_entry = _manifest_selection(manifest, run)
        database_hashes = {
            deployment["source_database"]["sha256"],
            downstream["source_database"]["sha256"],
            parity["source_database"]["sha256"],
            kuzu["sources"]["database"]["sha256"],
            manifest_entry["source"]["source_database"]["sha256"],
        }
        if len(database_hashes) != 1:
            raise ValueError(f"{run}: source database SHA chain mismatch")
        summary[run] = {
            "deployment_pairs": len(deployment["per_pair"]),
            "kuzu_pairs": len(kuzu["per_pair"]),
            "kuzu_queries": kuzu["execution"][
                "n_query_instances_checked"
            ],
        }
    return summary
