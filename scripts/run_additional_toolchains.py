#!/usr/bin/env python3
"""External-toolchain checks for GraphGuard.

This runner applies the same DocRED cohort, model endpoint, perturbation
definitions, canonicalization, contract tolerances, and paired-graph analysis
used by ``run_langchain_toolchain.py`` to two additional extraction components:

* LlamaIndex ``SchemaLLMPathExtractor``;
* Neo4j GraphRAG Python ``LLMEntityRelationExtractor``.

Each component is executed in its own pinned environment because their Python
dependencies are not mutually compatible.  Both checks stop at the native
in-memory typed graph, matching the boundary of the existing LangChain
``LLMGraphTransformer`` experiment; they do not test graph persistence.

Examples
--------
Smoke tests (one document, six conditions)::

  set -a && . ./.env && set +a
  /tmp/gg-toolchains-llama/bin/python scripts/run_additional_toolchains.py \
      --toolchain llamaindex --limit 1 --workers 1 \
      --cache /tmp/llamaindex-smoke.jsonl \
      --output /tmp/llamaindex-smoke.json
  /tmp/gg-toolchains-neo4j/bin/python scripts/run_additional_toolchains.py \
      --toolchain neo4j --limit 1 --workers 1 \
      --cache /tmp/neo4j-smoke.jsonl \
      --output /tmp/neo4j-smoke.json

Full resumable runs and publication::

  /tmp/gg-toolchains-llama/bin/python scripts/run_additional_toolchains.py \
      --toolchain llamaindex --limit 100 --workers 1 --publish
  /tmp/gg-toolchains-neo4j/bin/python scripts/run_additional_toolchains.py \
      --toolchain neo4j --limit 100 --workers 1 --publish
  python scripts/run_additional_toolchains.py --combine-only

``--publish`` writes a canonical, one-record-per-document-condition checkpoint
under ``reports/cross_run`` and binds it to a metadata file and a recomputed
summary.  ``--analyze-only`` needs only the Python standard library.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import shutil
import sqlite3
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_langchain_toolchain as langchain_protocol  # noqa: E402

DB = langchain_protocol.DB
CONDITIONS = list(langchain_protocol.CONDITIONS)
CONTRACT_TAU = dict(langchain_protocol.CONTRACT_TAU)
ALPHA = langchain_protocol.ALPHA
RENAME = dict(langchain_protocol.RENAME)
RENAME_INV = dict(langchain_protocol.RENAME_INV)
EVIDENCE_SEED_RULE = langchain_protocol.EVIDENCE_SEED_RULE

LOCAL_CACHE = {
    "llamaindex": ROOT / "data/processed/llamaindex_toolchain_cache.jsonl",
    "neo4j": ROOT / "data/processed/neo4j_toolchain_cache.jsonl",
}
PUBLISHED_CACHE = {
    "llamaindex": ROOT / "reports/cross_run/llamaindex_toolchain_cache.jsonl",
    "neo4j": ROOT / "reports/cross_run/neo4j_toolchain_cache.jsonl",
}
CHECKPOINT_METADATA = {
    "llamaindex": ROOT
    / "reports/cross_run/llamaindex_toolchain_checkpoint.json",
    "neo4j": ROOT / "reports/cross_run/neo4j_toolchain_checkpoint.json",
}
OUTPUT = {
    "llamaindex": ROOT / "reports/cross_run/llamaindex_toolchain.json",
    "neo4j": ROOT / "reports/cross_run/neo4j_toolchain.json",
}
COMBINED_OUTPUT = ROOT / "reports/cross_run/additional_toolchains.json"

DEPENDENCY_PACKAGES = {
    "llamaindex": (
        "llama-index-core",
        "llama-index-llms-openai-like",
        "llama-index-llms-openai",
        "openai",
        "numpy",
    ),
    "neo4j": ("neo4j-graphrag", "openai", "numpy", "pydantic"),
}
TOOLCHAIN_NAME = {
    "llamaindex": "llamaindex.SchemaLLMPathExtractor",
    "neo4j": "neo4j_graphrag.LLMEntityRelationExtractor",
}
LLAMA_MODES = ("native", "json_object")
EXTRACTION_MODE = {
    "llamaindex": (
        "SchemaLLMPathExtractor; one TextNode per document; strict schema; "
        "prompt-based Pydantic parsing; no embeddings or persistence"
    ),
    "neo4j": (
        "LLMEntityRelationExtractor; one TextChunk per document; V1 JSON "
        "prompt; provider JSON-object mode; thinking disabled; lexical graph "
        "disabled; no persistence"
    ),
}
THINKING_CONTROL = {
    "llamaindex": "provider default",
    "neo4j": "disabled via extra_body.enable_thinking=false",
}
MAX_TRIPLETS = 100
MAX_TOKENS = 4096
ERROR_CLASSIFICATION = {
    "llamaindex": (
        "capture native response; revalidate with the extractor's own "
        "Pydantic schema; distinguish parse failure, validation/pruning "
        "empty, and nonempty output; no application-level retry"
    ),
    "neo4j": (
        "native OnError.RAISE; distinguish parse failure, empty, and "
        "nonempty output; no application-level retry"
    ),
}

LLAMAINDEX_PARAPHRASE = (
    "Read the text below and extract every supported knowledge-graph path "
    "that is stated by the text. Follow the supplied structured output schema "
    "and return no more than {max_triplets_per_chunk} paths. Do not invent "
    "facts or add explanations.\n"
    "-------\n{text}\n-------\n"
)

NEO4J_PARAPHRASE = """
Convert the input passage into the typed graph described by the supplied
schema. Identify the entities and every supported relationship between them.

Return only one JSON object in this exact shape:
{{"nodes": [{{"id": "0", "label": "ENTITY",
"properties": {{"name": "John"}}}}],
"relationships": [{{"type": "KNOWS", "start_node_id": "0",
"end_node_id": "1", "properties": {{}}}}]}}

Use only node and relationship types from this schema:
{schema}
Reuse a node ID whenever the same entity participates in several relations.
Do not add prose, Markdown fences, or unsupported facts.

Examples:
{examples}

Input text:
{text}
"""

_WRITE_LOCK = threading.Lock()


class LlamaIndexNativeParseError(RuntimeError):
    """A parse failure hidden by SchemaLLMPathExtractor 0.14.23."""

    def __init__(
        self,
        message: str,
        observation: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.observation = observation


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric_metadata(value: Any) -> Any:
    """Retain numeric usage counters while dropping textual metadata."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        kept = {
            str(key): numeric_metadata(item)
            for key, item in value.items()
        }
        return {
            key: item
            for key, item in kept.items()
            if item is not None and item != {}
        }
    return None


def relative_or_absolute(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def dependency_versions(toolchain: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in DEPENDENCY_PACKAGES[toolchain]:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed (analysis-only)"
    return versions


def extraction_mode(toolchain: str, llama_mode: str = "native") -> str:
    base = EXTRACTION_MODE[toolchain]
    if toolchain != "llamaindex":
        return base
    if llama_mode == "native":
        return f"{base}; provider response format unconstrained"
    if llama_mode == "json_object":
        return f"{base}; provider JSON-object response constraint"
    raise ValueError(f"unsupported LlamaIndex mode: {llama_mode}")


def effective_labels(condition: str, labels: list[str]) -> list[str]:
    result = list(labels)
    if condition == "schema_reorder":
        result.reverse()
    elif condition == "schema_rename":
        result = [RENAME.get(label, label) for label in result]
    return result


def prompt_identity(toolchain: str, condition: str) -> str:
    if condition != "prompt_para":
        return "native-default"
    prompt = (
        LLAMAINDEX_PARAPHRASE
        if toolchain == "llamaindex"
        else NEO4J_PARAPHRASE
    )
    return f"paraphrase:{sha256_bytes(prompt.encode('utf-8'))}"


def cohort_fingerprint(
    toolchain: str,
    labels: list[str],
    source_database_sha256: str,
    versions: dict[str, str],
    outer_workers: int,
    llama_mode: str = "native",
) -> str:
    payload = {
        "toolchain": TOOLCHAIN_NAME[toolchain],
        "model": os.environ.get("OPENAI_MODEL", ""),
        "labels": labels,
        "source_database_sha256": source_database_sha256,
        "evidence_seed_rule": EVIDENCE_SEED_RULE,
        "dependency_versions": versions,
        "extraction_mode": extraction_mode(toolchain, llama_mode),
        "max_tokens": MAX_TOKENS,
        "outer_workers": outer_workers,
        "error_classification": ERROR_CLASSIFICATION[toolchain],
        "thinking_control": THINKING_CONTROL[toolchain],
    }
    return sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )


def config_fingerprint(
    toolchain: str,
    condition: str,
    labels: list[str],
    versions: dict[str, str],
    outer_workers: int,
    llama_mode: str = "native",
) -> str:
    payload = {
        "toolchain": TOOLCHAIN_NAME[toolchain],
        "condition": condition,
        "model": os.environ.get("OPENAI_MODEL", ""),
        "temperature": 0.2 if condition == "resample" else 0.0,
        "labels": effective_labels(condition, labels),
        "prompt": prompt_identity(toolchain, condition),
        "evidence_seed_rule": EVIDENCE_SEED_RULE,
        "dependency_versions": versions,
        "extraction_mode": extraction_mode(toolchain, llama_mode),
        "max_tokens": MAX_TOKENS,
        "outer_workers": outer_workers,
        "error_classification": ERROR_CLASSIFICATION[toolchain],
        "thinking_control": THINKING_CONTROL[toolchain],
    }
    return sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )


def normalize_relation(value: Any, condition: str) -> str:
    relation = str(value).lower().strip().replace(" ", "_")
    if condition == "schema_rename":
        relation = RENAME_INV.get(relation, relation)
    return relation


def normalize_entity(value: Any) -> str:
    return str(value).lower().strip()


def declared_edges(
    raw_edges: list[list[str]],
    condition: str,
    declared_labels: list[str],
) -> tuple[list[list[str]], int]:
    """Apply one shared declared-label normalization to every toolchain."""
    allowed = {
        str(label).lower().strip().replace(" ", "_")
        for label in declared_labels
    }
    kept: set[tuple[str, str, str]] = set()
    off_schema = 0
    for source, relation, target in raw_edges:
        canonical_relation = normalize_relation(relation, condition)
        if canonical_relation not in allowed:
            off_schema += 1
            continue
        kept.add(
            (
                normalize_entity(source),
                canonical_relation,
                normalize_entity(target),
            )
        )
    return [list(edge) for edge in sorted(kept)], off_schema


def _dynamic_literal(values: list[str]) -> Any:
    """Construct ``Literal[v1, ...]`` from a runtime relation catalogue."""
    return Literal.__getitem__(tuple(values))


def extract_llamaindex(
    condition: str,
    text: str,
    labels: list[str],
    llama_mode: str,
) -> tuple[list[list[str]], list[dict[str, Any]], dict[str, Any]]:
    from llama_index.core.graph_stores.types import KG_NODES_KEY, KG_RELATIONS_KEY
    from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
    from llama_index.core.output_parsers.pydantic import PydanticOutputParser
    from llama_index.core.output_parsers.utils import extract_json_str
    from llama_index.core.schema import TextNode
    from llama_index.llms.openai_like import OpenAILike
    from pydantic import PrivateAttr

    class ObservedOpenAILike(OpenAILike):
        """Capture response metadata without changing the native call."""

        _observed_response: dict[str, Any] = PrivateAttr(default_factory=dict)

        async def achat(self, messages: Any, **kwargs: Any) -> Any:
            response = await super().achat(messages, **kwargs)
            content = response.message.content or ""
            raw = response.raw
            choices = getattr(raw, "choices", None) or []
            first_choice = choices[0] if choices else None
            raw_message = getattr(first_choice, "message", None)
            message_extra = getattr(raw_message, "model_extra", None) or {}
            reasoning = (
                getattr(raw_message, "reasoning_content", None)
                or message_extra.get("reasoning_content")
                or ""
            )
            usage = getattr(raw, "usage", None)
            raw_usage_dict = (
                usage.model_dump(mode="json")
                if hasattr(usage, "model_dump")
                else {}
            )
            usage_dict = numeric_metadata(raw_usage_dict) or {}
            response_id = str(getattr(raw, "id", "") or "")
            raw_content = getattr(raw_message, "content", None)
            tool_calls = getattr(raw_message, "tool_calls", None) or []
            refusal = getattr(raw_message, "refusal", None)
            self._observed_response = {
                "response_sha256": sha256_bytes(content.encode("utf-8")),
                "response_characters": len(content),
                "raw_content_is_none": raw_content is None,
                "reasoning_sha256": sha256_bytes(
                    str(reasoning).encode("utf-8")
                ),
                "reasoning_characters": len(str(reasoning)),
                "response_id_sha256": sha256_bytes(
                    response_id.encode("utf-8")
                ),
                "finish_reason": getattr(first_choice, "finish_reason", None),
                "usage": usage_dict,
                "message_extra_keys": sorted(message_extra),
                "tool_call_count": len(tool_calls),
                "refusal_present": refusal is not None,
                "request_kwarg_keys": sorted(kwargs),
                "request_tool_choice": kwargs.get("tool_choice"),
                "requested_max_tokens": self.max_tokens,
                "requested_response_format": (
                    self.additional_kwargs.get("response_format")
                    if self.additional_kwargs
                    else None
                ),
                "requested_thinking_control": (
                    {
                        key: self.additional_kwargs[key]
                        for key in ("enable_thinking", "thinking")
                        if key in self.additional_kwargs
                    }
                    if self.additional_kwargs
                    else {}
                ),
                "_content": content,
            }
            return response

    rels = [label.upper() for label in effective_labels(condition, labels)]
    entity_type = Literal["ENTITY"]
    relation_type = _dynamic_literal(rels)
    validation = [("ENTITY", relation, "ENTITY") for relation in rels]
    temperature = 0.2 if condition == "resample" else 0.0
    llm_kwargs = {
        "model": os.environ["OPENAI_MODEL"],
        "api_base": os.environ["OPENAI_BASE_URL"],
        "api_key": os.environ["OPENAI_API_KEY"],
        "temperature": temperature,
        "max_tokens": MAX_TOKENS,
        "timeout": 120.0,
        "max_retries": 3,
        "reuse_client": False,
        "context_window": 128000,
        "is_chat_model": True,
        "is_function_calling_model": False,
        "should_use_structured_outputs": False,
    }
    if llama_mode == "json_object":
        llm_kwargs["additional_kwargs"] = {
            "response_format": {"type": "json_object"}
        }
    elif llama_mode != "native":
        raise ValueError(f"unsupported LlamaIndex mode: {llama_mode}")
    llm = ObservedOpenAILike(
        **llm_kwargs,
    )
    extractor = SchemaLLMPathExtractor(
        llm=llm,
        extract_prompt=(
            LLAMAINDEX_PARAPHRASE if condition == "prompt_para" else None
        ),
        possible_entities=entity_type,
        possible_relations=relation_type,
        kg_validation_schema=validation,
        strict=True,
        max_triplets_per_chunk=MAX_TRIPLETS,
        num_workers=1,
        allow_additional_properties=False,
    )
    output_node = extractor([TextNode(text=text)], show_progress=False)[0]
    observation = dict(llm._observed_response)
    response_content = str(observation.pop("_content", ""))
    try:
        unvalidated = json.loads(extract_json_str(response_content))
        parsed = PydanticOutputParser(
            output_cls=extractor.kg_schema_cls
        ).parse(response_content)
    except Exception as error:  # the native component hides these as []
        response_sha = observation.get("response_sha256", "unavailable")
        observation["parse_error_cause"] = type(error).__name__
        if isinstance(error, json.JSONDecodeError):
            observation["parse_error_location"] = {
                "line": error.lineno,
                "column": error.colno,
                "position": error.pos,
            }
        elif hasattr(error, "error_count"):
            try:
                observation["parse_error_count"] = int(error.error_count())
            except Exception:  # noqa: BLE001
                pass
        raise LlamaIndexNativeParseError(
            f"native structured-output parse failed; "
            f"cause={type(error).__name__}; "
            f"response_sha256={response_sha}",
            observation,
        ) from error

    unvalidated_triplets = (
        unvalidated.get("triplets")
        if isinstance(unvalidated, dict)
        else None
    )
    unvalidated_triplet_count = (
        len(unvalidated_triplets)
        if isinstance(unvalidated_triplets, list)
        else None
    )
    parsed_triplets = list(getattr(parsed, "triplets", []) or [])
    native_nodes = output_node.metadata.get(KG_NODES_KEY, [])
    native_relations = output_node.metadata.get(KG_RELATIONS_KEY, [])
    id_to_name = {node.id: node.name for node in native_nodes}
    raw_edges = [
        [
            id_to_name.get(relation.source_id, relation.source_id),
            relation.label,
            id_to_name.get(relation.target_id, relation.target_id),
        ]
        for relation in native_relations
    ]
    serialized_nodes = [
        {
            "id": node.id,
            "name": node.name,
            "label": node.label,
        }
        for node in native_nodes
    ]
    if raw_edges:
        native_status = "nonempty"
    elif unvalidated_triplet_count == 0:
        native_status = "model_empty"
    elif not parsed_triplets:
        native_status = "schema_validation_empty"
    else:
        native_status = "strict_pruning_empty"
    observation.update(
        {
            "native_output_status": native_status,
            "unvalidated_triplet_count": unvalidated_triplet_count,
            "parsed_triplet_count": len(parsed_triplets),
        }
    )
    return raw_edges, serialized_nodes, observation


def _native_node_name(node: Any) -> str:
    properties = getattr(node, "properties", {}) or {}
    for key in ("name", "title", "id"):
        value = properties.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return str(getattr(node, "id", ""))


def neo4j_edges_from_graph(graph: Any) -> tuple[list[list[str]], list[dict[str, Any]]]:
    native_nodes = list(getattr(graph, "nodes", []) or [])
    id_to_name = {
        str(getattr(node, "id", "")): _native_node_name(node)
        for node in native_nodes
    }
    raw_edges = []
    for relation in list(getattr(graph, "relationships", []) or []):
        source_id = str(getattr(relation, "start_node_id", ""))
        target_id = str(getattr(relation, "end_node_id", ""))
        raw_edges.append(
            [
                id_to_name.get(source_id, source_id),
                str(getattr(relation, "type", "")),
                id_to_name.get(target_id, target_id),
            ]
        )
    serialized_nodes = [
        (
            node.model_dump(mode="json")
            if hasattr(node, "model_dump")
            else {
                "id": str(getattr(node, "id", "")),
                "label": str(getattr(node, "label", "")),
                "properties": getattr(node, "properties", {}) or {},
            }
        )
        for node in native_nodes
    ]
    return raw_edges, serialized_nodes


def extract_neo4j(
    condition: str,
    text: str,
    labels: list[str],
    stable_uid: str,
) -> tuple[list[list[str]], list[dict[str, Any]], dict[str, Any]]:
    import httpx

    from neo4j_graphrag.experimental.components.entity_relation_extractor import (
        LLMEntityRelationExtractor,
        OnError,
    )
    from neo4j_graphrag.experimental.components.schema import (
        GraphSchema,
        NodeType,
        Pattern,
        RelationshipType,
    )
    from neo4j_graphrag.experimental.components.types import TextChunk, TextChunks
    from neo4j_graphrag.llm import OpenAILLM

    rels = [label.upper() for label in effective_labels(condition, labels)]
    schema = GraphSchema(
        node_types=(NodeType(label="ENTITY"),),
        relationship_types=tuple(
            RelationshipType(label=relation) for relation in rels
        ),
        patterns=tuple(
            Pattern(
                source="ENTITY",
                relationship=relation,
                target="ENTITY",
            )
            for relation in rels
        ),
        additional_node_types=False,
        additional_relationship_types=False,
        additional_patterns=False,
    )
    temperature = 0.2 if condition == "resample" else 0.0
    llm = OpenAILLM(
        model_name=os.environ["OPENAI_MODEL"],
        model_params={
            "temperature": temperature,
            "max_tokens": MAX_TOKENS,
            "response_format": {"type": "json_object"},
            "extra_body": {"enable_thinking": False},
        },
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
        timeout=120.0,
        max_retries=3,
        # OpenAI 1.x/httpx can fail its TLS handshake through the inherited
        # WSL proxy even though the configured provider is directly reachable.
        # The LangChain/LlamaIndex clients already reach the same endpoint
        # directly; use an explicit async client to keep that network path.
        http_client=httpx.AsyncClient(trust_env=False, timeout=120.0),
    )
    extractor_kwargs = {
        "llm": llm,
        "create_lexical_graph": False,
        "on_error": OnError.RAISE,
        "max_concurrency": 1,
        "use_structured_output": False,
    }
    if condition == "prompt_para":
        extractor_kwargs["prompt_template"] = NEO4J_PARAPHRASE
    extractor = LLMEntityRelationExtractor(**extractor_kwargs)

    async def run_and_close() -> Any:
        try:
            return await extractor.run(
                chunks=TextChunks(
                    chunks=[TextChunk(text=text, index=0, uid=stable_uid)]
                ),
                schema=schema,
            )
        finally:
            await llm.aclose()

    graph = asyncio.run(
        run_and_close()
    )
    raw_edges, serialized_nodes = neo4j_edges_from_graph(graph)
    return raw_edges, serialized_nodes, {
        "native_output_status": "nonempty" if raw_edges else "model_empty",
    }


def extract_one(
    toolchain: str,
    condition: str,
    doc_id: str,
    raw: str,
    sentences: list[str],
    labels: list[str],
    cohort: str,
    versions: dict[str, str],
    outer_workers: int,
    llama_mode: str = "native",
) -> dict[str, Any]:
    text = langchain_protocol.doc_text(
        condition,
        doc_id,
        raw,
        sentences,
    )
    fingerprint = config_fingerprint(
        toolchain,
        condition,
        labels,
        versions,
        outer_workers,
        llama_mode,
    )
    stable_uid = sha256_bytes(
        f"{cohort}\0{doc_id}\0{condition}".encode("utf-8")
    )[:32]
    if toolchain == "llamaindex":
        raw_edges, native_nodes, native_diagnostics = extract_llamaindex(
            condition,
            text,
            labels,
            llama_mode,
        )
    elif toolchain == "neo4j":
        raw_edges, native_nodes, native_diagnostics = extract_neo4j(
            condition,
            text,
            labels,
            stable_uid,
        )
    else:
        raise ValueError(f"unsupported toolchain: {toolchain}")
    edges, off_schema = declared_edges(raw_edges, condition, labels)
    record = {
        "schema_version": 1,
        "toolchain": TOOLCHAIN_NAME[toolchain],
        "cohort_fingerprint": cohort,
        "config_fingerprint": fingerprint,
        "doc": doc_id,
        "condition": condition,
        "model": os.environ["OPENAI_MODEL"],
        "temperature": 0.2 if condition == "resample" else 0.0,
        "max_tokens": MAX_TOKENS,
        "outer_workers": outer_workers,
        "llama_mode": llama_mode if toolchain == "llamaindex" else None,
        "input_sha256": sha256_bytes(text.encode("utf-8")),
        "evidence_seed_rule": EVIDENCE_SEED_RULE,
        "evidence_seed": (
            langchain_protocol.stable_evidence_seed(doc_id)
            if condition == "evidence_reorder"
            else None
        ),
        "stable_native_uid": stable_uid,
        "dependency_versions": versions,
        "extraction_mode": extraction_mode(toolchain, llama_mode),
        "error_classification": ERROR_CLASSIFICATION[toolchain],
        "thinking_control": THINKING_CONTROL[toolchain],
        "native_diagnostics": native_diagnostics,
        "native_nodes": native_nodes,
        "raw_edges": raw_edges,
        "edges": edges,
        "raw_edge_count": len(raw_edges),
        "declared_edge_count": len(edges),
        "off_schema_relation_count": off_schema,
        "declared_label_filter": (
            "lowercase/underscore relation normalization; invert declared "
            "rename; retain only the common 26-relation DocRED catalogue"
        ),
    }
    return record


def failed_record(
    toolchain: str,
    condition: str,
    doc_id: str,
    raw: str,
    sentences: list[str],
    labels: list[str],
    cohort: str,
    versions: dict[str, str],
    outer_workers: int,
    llama_mode: str,
    error: Exception,
) -> dict[str, Any]:
    text = langchain_protocol.doc_text(
        condition,
        doc_id,
        raw,
        sentences,
    )
    parse_error = (
        isinstance(error, LlamaIndexNativeParseError)
        or "valid JSON" in str(error)
        or "improper format" in str(error)
    )
    diagnostics = {
        "native_output_status": (
            "parse_error" if parse_error else "runtime_error"
        )
    }
    if isinstance(error, LlamaIndexNativeParseError):
        diagnostics.update(error.observation)
    return {
        "schema_version": 1,
        "toolchain": TOOLCHAIN_NAME[toolchain],
        "cohort_fingerprint": cohort,
        "config_fingerprint": config_fingerprint(
            toolchain,
            condition,
            labels,
            versions,
            outer_workers,
            llama_mode,
        ),
        "doc": doc_id,
        "condition": condition,
        "model": os.environ["OPENAI_MODEL"],
        "temperature": 0.2 if condition == "resample" else 0.0,
        "max_tokens": MAX_TOKENS,
        "outer_workers": outer_workers,
        "llama_mode": llama_mode if toolchain == "llamaindex" else None,
        "input_sha256": sha256_bytes(text.encode("utf-8")),
        "evidence_seed_rule": EVIDENCE_SEED_RULE,
        "evidence_seed": (
            langchain_protocol.stable_evidence_seed(doc_id)
            if condition == "evidence_reorder"
            else None
        ),
        "dependency_versions": versions,
        "extraction_mode": extraction_mode(toolchain, llama_mode),
        "error_classification": ERROR_CLASSIFICATION[toolchain],
        "thinking_control": THINKING_CONTROL[toolchain],
        "native_diagnostics": diagnostics,
        "native_nodes": None,
        "raw_edges": None,
        "edges": None,
        "error": type(error).__name__,
    }


def record_key(record: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(record.get("cohort_fingerprint", "")),
        str(record.get("doc", "")),
        str(record.get("condition", "")),
        str(record.get("config_fingerprint", "")),
        str(record.get("input_sha256", "")),
    )


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"invalid JSONL at {path}:{line_number}"
            ) from error
    return records


def latest_records(
    records: list[dict[str, Any]],
    cohort: str | None = None,
) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for record in records:
        if cohort is not None and record.get("cohort_fingerprint") != cohort:
            continue
        latest[record_key(record)] = record
    return sorted(
        latest.values(),
        key=lambda record: (
            CONDITIONS.index(record["condition"]),
            record["doc"],
        ),
    )


def completed_keys(records: list[dict[str, Any]]) -> set[tuple[str, str, str, str, str]]:
    """Return attempted endpoints, including errors, to avoid selective retry."""
    return {
        record_key(record)
        for record in latest_records(records)
    }


def load_doc_by_id(doc_id: str) -> tuple[str, str, list[str]]:
    connection = sqlite3.connect(DB)
    try:
        row = connection.execute(
            "SELECT document_id, raw_text FROM documents "
            "WHERE document_id=?",
            (doc_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"document not found: {doc_id}")
        sentences = [
            text
            for (text,) in connection.execute(
                "SELECT text FROM sentences WHERE document_id=? "
                "ORDER BY sentence_index",
                (doc_id,),
            )
        ]
    finally:
        connection.close()
    return str(row[0]), str(row[1]), sentences


def run_extraction(
    toolchain: str,
    limit: int,
    workers: int,
    cache_path: Path,
    llama_mode: str = "native",
    doc_id: str | None = None,
) -> str:
    required_env = ("OPENAI_MODEL", "OPENAI_BASE_URL", "OPENAI_API_KEY")
    missing = [name for name in required_env if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "missing required environment variables: " + ", ".join(missing)
        )
    labels = langchain_protocol.relation_labels()
    docs = (
        [load_doc_by_id(doc_id)]
        if doc_id is not None
        else langchain_protocol.load_docs(limit)
    )
    versions = dependency_versions(toolchain)
    source_sha = sha256_file(DB)
    cohort = cohort_fingerprint(
        toolchain,
        labels,
        source_sha,
        versions,
        workers,
        llama_mode,
    )
    existing = load_records(cache_path)
    done = completed_keys(existing)
    todo: list[tuple[str, str, str, list[str]]] = []
    for condition in CONDITIONS:
        for doc_id, raw, sentences in docs:
            text = langchain_protocol.doc_text(
                condition,
                doc_id,
                raw,
                sentences,
            )
            key = (
                cohort,
                doc_id,
                condition,
                config_fingerprint(
                    toolchain,
                    condition,
                    labels,
                    versions,
                    workers,
                    llama_mode,
                ),
                sha256_bytes(text.encode("utf-8")),
            )
            if key not in done:
                todo.append((condition, doc_id, raw, sentences))
    print(
        f"[extract:{toolchain}] {len(todo)} calls "
        f"({len(done)} exact attempts cached), workers={workers}",
        flush=True,
    )
    if not todo:
        return cohort
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ok = errors = 0
    with cache_path.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(
        max_workers=workers
    ) as executor:
        futures = {
            executor.submit(
                extract_one,
                toolchain,
                condition,
                doc_id,
                raw,
                sentences,
                labels,
                cohort,
                versions,
                workers,
                llama_mode,
            ): (condition, doc_id, raw, sentences)
            for condition, doc_id, raw, sentences in todo
        }
        for future in as_completed(futures):
            condition, doc_id, raw, sentences = futures[future]
            try:
                record = future.result()
            except Exception as error:  # noqa: BLE001
                record = failed_record(
                    toolchain,
                    condition,
                    doc_id,
                    raw,
                    sentences,
                    labels,
                    cohort,
                    versions,
                    workers,
                    llama_mode,
                    error,
                )
                errors += 1
            else:
                ok += 1
            with _WRITE_LOCK:
                handle.write(
                    json.dumps(record, ensure_ascii=False, sort_keys=True)
                    + "\n"
                )
                handle.flush()
            if (ok + errors) % 25 == 0:
                print(
                    f"[extract:{toolchain}] {ok + errors}/{len(todo)} "
                    f"done ({errors} errors)",
                    flush=True,
                )
    print(
        f"[extract:{toolchain}] finished: ok={ok} errors={errors}",
        flush=True,
    )
    return cohort


def calibration_docs(
    offset: int = 100,
    limit: int = 10,
) -> list[tuple[str, str, list[str]]]:
    docs = langchain_protocol.load_docs(offset + limit)[offset:]
    if len(docs) != limit:
        raise RuntimeError(
            f"calibration requires {limit} documents at offset {offset}; "
            f"found {len(docs)}"
        )
    return docs


def binomial_upper_tail(successes: int, trials: int) -> float:
    if trials == 0:
        return 1.0
    numerator = sum(
        math.comb(trials, value)
        for value in range(successes, trials + 1)
    )
    return numerator / (2**trials)


def llama_calibration_summary(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    latest = latest_records(records)
    by_mode_cell: dict[
        str,
        dict[tuple[str, str], dict[str, Any]],
    ] = {mode: {} for mode in LLAMA_MODES}
    for record in latest:
        mode = str(record.get("llama_mode"))
        if mode not in by_mode_cell:
            continue
        by_mode_cell[mode][
            (str(record["doc"]), str(record["condition"]))
        ] = record

    thresholds = {
        "endpoint_parse_success_min": 54,
        "base_parse_success_min": 9,
        "each_condition_parse_success_min": 8,
        "each_axis_parse_pair_min": 8,
        "total_parse_pairs_min": 45,
        "each_axis_drift_evaluable_pair_min": 7,
        "total_drift_evaluable_pairs_min": 40,
        "json_object_success_improvement_min": 6,
        "mcnemar_one_sided_p_max_exclusive": 0.05,
    }
    modes: dict[str, Any] = {}
    for mode in LLAMA_MODES:
        cells = by_mode_cell[mode]
        condition_success = {
            condition: sum(
                record.get("edges") is not None
                for (doc, cell_condition), record in cells.items()
                if cell_condition == condition
            )
            for condition in CONDITIONS
        }
        parse_pairs: dict[str, int] = {}
        drift_evaluable_pairs: dict[str, int] = {}
        docs = sorted({doc for doc, _condition in cells})
        for condition in CONDITIONS[1:]:
            parse_count = evaluable_count = 0
            for doc in docs:
                base = cells.get((doc, "base"))
                changed = cells.get((doc, condition))
                if (
                    base is None
                    or changed is None
                    or base.get("edges") is None
                    or changed.get("edges") is None
                ):
                    continue
                parse_count += 1
                if edge_set(base) or edge_set(changed):
                    evaluable_count += 1
            parse_pairs[condition] = parse_count
            drift_evaluable_pairs[condition] = evaluable_count
        endpoint_success = sum(
            record.get("edges") is not None for record in cells.values()
        )
        qualified = (
            len(cells) == 60
            and endpoint_success >= thresholds["endpoint_parse_success_min"]
            and condition_success["base"]
            >= thresholds["base_parse_success_min"]
            and all(
                value
                >= thresholds["each_condition_parse_success_min"]
                for value in condition_success.values()
            )
            and all(
                value >= thresholds["each_axis_parse_pair_min"]
                for value in parse_pairs.values()
            )
            and sum(parse_pairs.values())
            >= thresholds["total_parse_pairs_min"]
            and all(
                value
                >= thresholds["each_axis_drift_evaluable_pair_min"]
                for value in drift_evaluable_pairs.values()
            )
            and sum(drift_evaluable_pairs.values())
            >= thresholds["total_drift_evaluable_pairs_min"]
        )
        modes[mode] = {
            "attempted": len(cells),
            "parse_success": endpoint_success,
            "condition_parse_success": condition_success,
            "parse_pairs": parse_pairs,
            "parse_pairs_total": sum(parse_pairs.values()),
            "drift_evaluable_pairs": drift_evaluable_pairs,
            "drift_evaluable_pairs_total": sum(
                drift_evaluable_pairs.values()
            ),
            "qualified": qualified,
        }

    native_cells = by_mode_cell["native"]
    json_cells = by_mode_cell["json_object"]
    common_cells = sorted(set(native_cells) & set(json_cells))
    json_only = sum(
        native_cells[cell].get("edges") is None
        and json_cells[cell].get("edges") is not None
        for cell in common_cells
    )
    native_only = sum(
        native_cells[cell].get("edges") is not None
        and json_cells[cell].get("edges") is None
        for cell in common_cells
    )
    discordant = json_only + native_only
    mcnemar_p = binomial_upper_tail(json_only, discordant)
    improvement = (
        modes["json_object"]["parse_success"]
        - modes["native"]["parse_success"]
    )
    if modes["native"]["qualified"]:
        selected_mode = "native"
        selection_reason = "native mode passed every frozen threshold"
    elif (
        modes["json_object"]["qualified"]
        and improvement
        >= thresholds["json_object_success_improvement_min"]
        and mcnemar_p
        < thresholds["mcnemar_one_sided_p_max_exclusive"]
    ):
        selected_mode = "json_object"
        selection_reason = (
            "native failed; JSON-object passed and met the frozen paired "
            "improvement rule"
        )
    else:
        selected_mode = None
        selection_reason = (
            "no mode satisfied the frozen qualification and selection rules"
        )
    return {
        "schema_version": 1,
        "artifact_type": "graphguard.llamaindex_mode_calibration",
        "selection_inputs_exclude_drift_values": True,
        "document_window": {
            "offset": 100,
            "limit": 10,
            "outside_formal_first_100": True,
        },
        "thresholds": thresholds,
        "modes": modes,
        "paired_mode_comparison": {
            "common_cells": len(common_cells),
            "json_object_only_success": json_only,
            "native_only_success": native_only,
            "one_sided_exact_mcnemar_p": round(mcnemar_p, 8),
            "json_object_success_improvement": improvement,
        },
        "selected_mode": selected_mode,
        "selection_reason": selection_reason,
    }


def run_llama_calibration(
    cache_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    required_env = ("OPENAI_MODEL", "OPENAI_BASE_URL", "OPENAI_API_KEY")
    missing = [name for name in required_env if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "missing required environment variables: " + ", ".join(missing)
        )
    labels = langchain_protocol.relation_labels()
    docs = calibration_docs()
    versions = dependency_versions("llamaindex")
    source_sha = sha256_file(DB)
    cohorts = {
        mode: cohort_fingerprint(
            "llamaindex",
            labels,
            source_sha,
            versions,
            1,
            mode,
        )
        for mode in LLAMA_MODES
    }
    existing = load_records(cache_path)
    done = completed_keys(existing)
    schedule = []
    for condition in CONDITIONS:
        for doc_id, raw, sentences in docs:
            modes = list(LLAMA_MODES)
            order_hash = sha256_bytes(
                f"{doc_id}\0{condition}\0mode-order".encode("utf-8")
            )
            if int(order_hash[-1], 16) % 2:
                modes.reverse()
            for mode in modes:
                text = langchain_protocol.doc_text(
                    condition,
                    doc_id,
                    raw,
                    sentences,
                )
                key = (
                    cohorts[mode],
                    doc_id,
                    condition,
                    config_fingerprint(
                        "llamaindex",
                        condition,
                        labels,
                        versions,
                        1,
                        mode,
                    ),
                    sha256_bytes(text.encode("utf-8")),
                )
                if key not in done:
                    schedule.append(
                        (mode, condition, doc_id, raw, sentences)
                    )
    print(
        f"[calibrate:llamaindex] {len(schedule)} calls "
        f"({len(done)} exact attempts cached), workers=1",
        flush=True,
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("a", encoding="utf-8") as handle:
        for index, (mode, condition, doc_id, raw, sentences) in enumerate(
            schedule,
            start=1,
        ):
            try:
                record = extract_one(
                    "llamaindex",
                    condition,
                    doc_id,
                    raw,
                    sentences,
                    labels,
                    cohorts[mode],
                    versions,
                    1,
                    mode,
                )
            except Exception as error:  # noqa: BLE001
                record = failed_record(
                    "llamaindex",
                    condition,
                    doc_id,
                    raw,
                    sentences,
                    labels,
                    cohorts[mode],
                    versions,
                    1,
                    mode,
                    error,
                )
            record["calibration_only"] = True
            record["calibration_doc_offset"] = 100
            record["calibration_doc_limit"] = 10
            handle.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            )
            handle.flush()
            if index % 10 == 0:
                print(
                    f"[calibrate:llamaindex] "
                    f"{index}/{len(schedule)} new calls done",
                    flush=True,
                )
    summary = llama_calibration_summary(load_records(cache_path))
    summary["provenance"] = {
        "runner": "scripts/run_additional_toolchains.py",
        "runner_sha256": sha256_file(Path(__file__)),
        "cache_path": relative_or_absolute(cache_path),
        "cache_sha256": sha256_file(cache_path),
        "model": os.environ["OPENAI_MODEL"],
        "dependency_versions": versions,
        "cohort_fingerprints": cohorts,
        "mode_order_rule": (
            "sha256(doc_id NUL condition NUL 'mode-order') final hex parity"
        ),
        "application_level_retry": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"[calibrate:llamaindex] selected={summary['selected_mode']} "
        f"-> {output_path}",
        flush=True,
    )
    return summary


def edge_set(record: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (str(source), str(relation), str(target))
        for source, relation, target in record.get("edges") or []
    }


def analyze_records(
    records: list[dict[str, Any]],
    toolchain: str,
    cohort: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = latest_records(records, cohort)
    if not selected:
        raise RuntimeError("no records selected for analysis")
    cohorts = {record.get("cohort_fingerprint") for record in selected}
    if cohort is None and len(cohorts) != 1:
        raise RuntimeError(
            "checkpoint contains multiple cohorts; pass --cohort explicitly"
        )
    selected_cohort = str(next(iter(cohorts)))
    models = {record.get("model") for record in selected}
    versions = {
        json.dumps(record.get("dependency_versions"), sort_keys=True)
        for record in selected
    }
    modes = {record.get("extraction_mode") for record in selected}
    worker_counts = {record.get("outer_workers") for record in selected}
    error_policies = {
        record.get("error_classification") for record in selected
    }
    thinking_controls = {
        record.get("thinking_control") for record in selected
    }
    if (
        len(models) != 1
        or len(versions) != 1
        or len(modes) != 1
        or len(worker_counts) != 1
        or len(error_policies) != 1
        or len(thinking_controls) != 1
    ):
        raise RuntimeError("selected checkpoint mixes extraction environments")

    by_doc: dict[str, dict[str, dict[str, Any]]] = {}
    errors: dict[str, int] = {condition: 0 for condition in CONDITIONS}
    attempted: dict[str, int] = {condition: 0 for condition in CONDITIONS}
    raw_edges: dict[str, int] = {condition: 0 for condition in CONDITIONS}
    off_schema: dict[str, int] = {condition: 0 for condition in CONDITIONS}
    native_statuses: dict[str, int] = {}
    for record in selected:
        condition = record["condition"]
        attempted[condition] += 1
        status = str(
            (record.get("native_diagnostics") or {}).get(
                "native_output_status",
                "unclassified",
            )
        )
        native_statuses[status] = native_statuses.get(status, 0) + 1
        if record.get("edges") is None:
            errors[condition] += 1
            continue
        raw_edges[condition] += int(record.get("raw_edge_count", 0))
        off_schema[condition] += int(
            record.get("off_schema_relation_count", 0)
        )
        by_doc.setdefault(record["doc"], {})[condition] = record

    summary: dict[str, Any] = {}
    for condition in CONDITIONS[1:]:
        drifts = []
        empty_empty = 0
        for conditions in by_doc.values():
            if "base" not in conditions or condition not in conditions:
                continue
            base_edges = edge_set(conditions["base"])
            changed_edges = edge_set(conditions[condition])
            if not base_edges and not changed_edges:
                empty_empty += 1
                continue
            union = base_edges | changed_edges
            drift = 1.0 - len(base_edges & changed_edges) / len(union)
            drifts.append(drift)
        if not drifts:
            summary[condition] = {
                "n": 0,
                "attempted": attempted[condition],
                "errors": errors[condition],
                "empty_empty_excluded": empty_empty,
                "mean_drift": None,
                "median_drift": None,
                "tau": CONTRACT_TAU[condition],
                "violation_rate": None,
                "verdict": "NO_VALID_PAIRS",
                "raw_edges": raw_edges[condition],
                "off_schema_relations": off_schema[condition],
                "off_schema_rate": (
                    round(off_schema[condition] / raw_edges[condition], 6)
                    if raw_edges[condition]
                    else 0.0
                ),
            }
            continue
        tau = CONTRACT_TAU[condition]
        violation_rate = sum(drift > tau for drift in drifts) / len(drifts)
        summary[condition] = {
            "n": len(drifts),
            "attempted": attempted[condition],
            "errors": errors[condition],
            "empty_empty_excluded": empty_empty,
            "mean_drift": round(statistics.mean(drifts), 4),
            "median_drift": round(statistics.median(drifts), 4),
            "tau": tau,
            "violation_rate": round(violation_rate, 4),
            "verdict": (
                "VIOLATED" if violation_rate > ALPHA else "SATISFIED"
            ),
            "raw_edges": raw_edges[condition],
            "off_schema_relations": off_schema[condition],
            "off_schema_rate": round(
                off_schema[condition] / raw_edges[condition],
                6,
            )
            if raw_edges[condition]
            else 0.0,
        }
    selection = {
        "cohort_fingerprint": selected_cohort,
        "selected_records": len(selected),
        "attempted_documents": len(by_doc)
        + len(
            {
                record["doc"]
                for record in selected
                if record.get("edges") is None
                and record["doc"] not in by_doc
            }
        ),
        "documents_with_any_success": len(by_doc),
        "model": next(iter(models)),
        "dependency_versions": json.loads(next(iter(versions))),
        "extraction_mode": next(iter(modes)),
        "outer_workers": next(iter(worker_counts)),
        "error_classification": next(iter(error_policies)),
        "thinking_control": next(iter(thinking_controls)),
        "native_output_statuses": native_statuses,
        "condition_attempts": attempted,
        "condition_errors": errors,
    }
    return summary, selection


def write_analysis(
    toolchain: str,
    cache_path: Path,
    output_path: Path,
    cohort: str | None = None,
    checkpoint_metadata_path: Path | None = None,
) -> dict[str, Any]:
    records = load_records(cache_path)
    summary, selection = analyze_records(records, toolchain, cohort)
    source_database = {
        "path": relative_or_absolute(DB),
        "bytes": DB.stat().st_size,
        "sha256": sha256_file(DB),
    }
    checkpoint = {
        "path": relative_or_absolute(cache_path),
        "bytes": cache_path.stat().st_size,
        "sha256": sha256_file(cache_path),
        "records": len(latest_records(records, selection["cohort_fingerprint"])),
    }
    result = {
        "schema_version": 1,
        "artifact_type": "graphguard.additional_toolchain_summary",
        "toolchain": TOOLCHAIN_NAME[toolchain],
        "component_level_only": True,
        "model": selection["model"],
        "attempted_documents": selection["attempted_documents"],
        "provenance": {
            "producer": {
                "script": "scripts/run_additional_toolchains.py",
                "runner_sha256": sha256_file(Path(__file__)),
                "analysis_command": (
                    "python scripts/run_additional_toolchains.py "
                    f"--toolchain {toolchain} --analyze-only"
                ),
                "evidence_seed_rule": EVIDENCE_SEED_RULE,
            },
            "source_database": source_database,
            "checkpoint": checkpoint,
            "checkpoint_metadata": (
                {
                    "path": relative_or_absolute(checkpoint_metadata_path),
                    "sha256": sha256_file(checkpoint_metadata_path),
                }
                if checkpoint_metadata_path
                and checkpoint_metadata_path.is_file()
                else None
            ),
            "selection": selection,
            "declared_label_filter": (
                "applied identically to all conditions; off-schema counts "
                "remain visible in each summary row"
            ),
        },
        "summary": summary,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"[analyze:{toolchain}] {selection['attempted_documents']} docs "
        f"-> {output_path}",
        flush=True,
    )
    for condition, row in summary.items():
        drift = (
            "---"
            if row["mean_drift"] is None
            else f"{row['mean_drift']:.3f}"
        )
        violation = (
            "---"
            if row["violation_rate"] is None
            else f"{row['violation_rate']:.3f}"
        )
        print(
            f"  {condition:<17} n={row['n']:<4} "
            f"err={row['errors']:<3} empty={row['empty_empty_excluded']:<3} "
            f"drift={drift} viol={violation} "
            f"off_schema={row['off_schema_rate']:.3f}",
            flush=True,
        )
    return result


def publish_checkpoint(
    toolchain: str,
    local_cache: Path,
    cohort: str,
) -> tuple[Path, Path]:
    records = latest_records(load_records(local_cache), cohort)
    expected = {
        (doc_id, condition)
        for doc_id, _raw, _sentences in langchain_protocol.load_docs(100)
        for condition in CONDITIONS
    }
    observed = {(record["doc"], record["condition"]) for record in records}
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing or extra or len(records) != len(expected):
        raise RuntimeError(
            "cannot publish non-canonical checkpoint; "
            f"records={len(records)} expected={len(expected)} "
            f"missing={len(missing)} extra={len(extra)}"
        )
    published = PUBLISHED_CACHE[toolchain]
    published.parent.mkdir(parents=True, exist_ok=True)
    temporary = published.with_suffix(published.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            )
    temporary.replace(published)
    metadata = {
        "schema_version": 1,
        "artifact_type": "graphguard.additional_toolchain_checkpoint",
        "toolchain": TOOLCHAIN_NAME[toolchain],
        "producer": {
            "runner": "scripts/run_additional_toolchains.py",
            "runner_sha256": sha256_file(Path(__file__)),
        },
        "checkpoint": {
            "path": relative_or_absolute(published),
            "bytes": published.stat().st_size,
            "sha256": sha256_file(published),
            "records": len(records),
        },
        "source_database": {
            "path": relative_or_absolute(DB),
            "bytes": DB.stat().st_size,
            "sha256": sha256_file(DB),
        },
        "extraction_environment": {
            "cohort_fingerprint": cohort,
            "model": records[0]["model"],
            "dependency_versions": records[0]["dependency_versions"],
            "extraction_mode": records[0]["extraction_mode"],
            "outer_workers": records[0]["outer_workers"],
            "max_tokens": records[0]["max_tokens"],
            "error_classification": records[0]["error_classification"],
            "thinking_control": records[0]["thinking_control"],
            "evidence_seed_rule": EVIDENCE_SEED_RULE,
            "per_record_fingerprints": True,
            "per_record_input_hashes": True,
        },
    }
    metadata_path = CHECKPOINT_METADATA[toolchain]
    metadata_path.write_text(
        json.dumps(metadata, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"[publish:{toolchain}] {len(records)} records -> {published}",
        flush=True,
    )
    return published, metadata_path


def combine_outputs() -> dict[str, Any]:
    summaries = {}
    for toolchain, path in OUTPUT.items():
        if not path.is_file():
            raise RuntimeError(f"missing published summary: {path}")
        summaries[toolchain] = json.loads(path.read_text(encoding="utf-8"))
    combined = {
        "schema_version": 1,
        "artifact_type": "graphguard.additional_toolchains",
        "scope": (
            "response-only component-level text-to-in-memory-typed-graph "
            "checks; no graph persistence"
        ),
        "toolchains": summaries,
    }
    COMBINED_OUTPUT.write_text(
        json.dumps(combined, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[combine] -> {COMBINED_OUTPUT}", flush=True)
    return combined


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--toolchain",
        choices=sorted(TOOLCHAIN_NAME),
        help="external extraction component to run",
    )
    parser.add_argument(
        "--llama-mode",
        choices=LLAMA_MODES,
        default="native",
        help="global LlamaIndex provider-output mode",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--doc-id",
        help="run all six conditions for exactly one document",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--cache",
        type=Path,
        help=(
            "checkpoint path; analyze-only defaults to the published "
            "checkpoint, extraction defaults to the local cache"
        ),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cohort")
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument(
        "--publish-existing",
        action="store_true",
        help="publish a complete existing cache without model calls",
    )
    parser.add_argument("--combine-only", action="store_true")
    parser.add_argument("--calibrate-llama", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.calibrate_llama:
        if args.toolchain or args.publish or args.analyze_only:
            raise SystemExit(
                "--calibrate-llama is standalone; do not combine it with "
                "--toolchain, --publish, or --analyze-only"
            )
        run_llama_calibration(
            args.cache
            or Path("/tmp/graphguard-llamaindex-calibration.jsonl"),
            args.output
            or Path("/tmp/graphguard-llamaindex-calibration.json"),
        )
        return
    if args.combine_only:
        combine_outputs()
        return
    if not args.toolchain:
        raise SystemExit("--toolchain is required unless --combine-only is used")
    toolchain = args.toolchain
    if toolchain != "llamaindex" and args.llama_mode != "native":
        raise SystemExit("--llama-mode applies only to LlamaIndex")
    if args.cache is not None:
        cache = args.cache
    elif args.analyze_only:
        cache = PUBLISHED_CACHE[toolchain]
    else:
        cache = LOCAL_CACHE[toolchain]
    output = args.output or OUTPUT[toolchain]
    if args.publish_existing:
        if args.cache is None or args.publish or args.analyze_only:
            raise SystemExit(
                "--publish-existing requires --cache and is incompatible "
                "with --publish/--analyze-only"
            )
        records = load_records(cache)
        cohorts = {
            str(record.get("cohort_fingerprint"))
            for record in records
        }
        cohort = args.cohort
        if cohort is None:
            if len(cohorts) != 1:
                raise RuntimeError(
                    "--publish-existing needs --cohort when the cache "
                    "contains multiple cohorts"
                )
            cohort = next(iter(cohorts))
        published, metadata = publish_checkpoint(
            toolchain,
            cache,
            cohort,
        )
        write_analysis(
            toolchain,
            published,
            OUTPUT[toolchain],
            cohort,
            metadata,
        )
        return
    if args.analyze_only:
        default_published = cache.resolve() == PUBLISHED_CACHE[
            toolchain
        ].resolve()
        write_analysis(
            toolchain,
            cache,
            output,
            args.cohort,
            CHECKPOINT_METADATA[toolchain] if default_published else None,
        )
        return
    cohort = run_extraction(
        toolchain,
        args.limit,
        args.workers,
        cache,
        args.llama_mode,
        args.doc_id,
    )
    if args.publish:
        if (
            args.limit != 100
            or args.cache is not None
            or args.workers != 1
            or args.doc_id is not None
        ):
            raise RuntimeError(
                "--publish requires the default cache, --limit 100, "
                "--workers 1, and no --doc-id"
            )
        published, metadata = publish_checkpoint(toolchain, cache, cohort)
        write_analysis(
            toolchain,
            published,
            OUTPUT[toolchain],
            cohort,
            metadata,
        )
    else:
        write_analysis(toolchain, cache, output, cohort)


if __name__ == "__main__":
    main()
