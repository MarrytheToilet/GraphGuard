"""Load DocRED via HuggingFace `datasets` and normalize it for our SQLite store.

DocRED structure per example:
  - title:      str
  - sents:      list[list[str]]           # list of sentences, each as token list
  - vertexSet:  list[list[mention_dict]]  # entity clusters; mentions have name/sent_id/...
  - labels:     list[{head, tail, relation_id, relation_text, evidence}]  (only labelled splits)

We do not import labels into Milestone 1 storage: the read-out is left to evaluation code.
"""
from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

from datasets import load_dataset

from ..db import repositories as repo

log = logging.getLogger(__name__)


@dataclass
class LoadStats:
    documents: int = 0
    sentences: int = 0
    entities: int = 0


def _doc_id(split: str, idx: int, title: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:40]
    return f"docred-{split}-{idx:06d}-{safe}"


def _join_sentence(tokens: list[str]) -> str:
    """Detokenize a DocRED sentence into a readable string (heuristic)."""
    out: list[str] = []
    for i, tok in enumerate(tokens):
        if i == 0:
            out.append(tok)
            continue
        if tok in {",", ".", ";", ":", "!", "?", ")", "]", "'s", "n't", "'re", "'ve", "'ll", "'d", "'m"}:
            out.append(tok)
        elif out[-1] in {"(", "[", "``", "$"}:
            out.append(tok)
        else:
            out.append(" " + tok)
    return "".join(out).strip()


def _build_entities(document_id: str, vertex_set: list[list[dict]]) -> list[repo.Entity]:
    entities: list[repo.Entity] = []
    for cluster_idx, cluster in enumerate(vertex_set):
        names: list[str] = []
        types: list[str] = []
        for m in cluster:
            n = m.get("name")
            t = m.get("type")
            if n and n not in names:
                names.append(n)
            if t and t not in types:
                types.append(t)
        if not names:
            continue
        entities.append(repo.Entity(
            entity_id=f"{document_id}::e{cluster_idx}",
            document_id=document_id,
            canonical_name=names[0],
            aliases=names,
            entity_type=types[0] if types else None,
        ))
    return entities


def _build_gold_edges(document_id: str, labels: Optional[dict],
                      entities: list[repo.Entity]) -> list[repo.GoldEdge]:
    if not labels:
        return []
    heads = labels.get("head") or []
    tails = labels.get("tail") or []
    rels = labels.get("relation_id") or []
    rel_text = labels.get("relation_text") or [None] * len(heads)
    evid = labels.get("evidence") or [[] for _ in heads]
    rows: list[repo.GoldEdge] = []
    for i, (h, t, r) in enumerate(zip(heads, tails, rels)):
        if h is None or t is None:
            continue
        try:
            head_ent = entities[int(h)] if int(h) < len(entities) else None
            tail_ent = entities[int(t)] if int(t) < len(entities) else None
        except (TypeError, ValueError):
            head_ent = tail_ent = None
        head_name = head_ent.canonical_name if head_ent else f"#{h}"
        tail_name = tail_ent.canonical_name if tail_ent else f"#{t}"
        rows.append(repo.GoldEdge(
            gold_edge_id=f"{document_id}::g{i}",
            document_id=document_id,
            head_entity_id=head_ent.entity_id if head_ent else None,
            tail_entity_id=tail_ent.entity_id if tail_ent else None,
            head_name=head_name,
            tail_name=tail_name,
            relation_base=str(r),
            evidence_sentence_ids=[int(x) for x in (evid[i] or [])],
            source="docred",
        ))
    return rows


def _build_sentences(document_id: str, sents: list[list[str]]) -> list[repo.Sentence]:
    rows: list[repo.Sentence] = []
    for idx, tokens in enumerate(sents):
        rows.append(repo.Sentence(
            sentence_id=f"{document_id}::s{idx}",
            document_id=document_id,
            sentence_index=idx,
            text=_join_sentence(tokens),
        ))
    return rows


# DocRED on HF Hub used to ship a loading script (`docred.py`); HF datasets 4.x
# rejects script-based datasets. We therefore prefer the auto-generated parquet
# branch HF maintains under `refs/convert/parquet`. Mapping below resolves a
# requested split to the parquet sub-directory used on that branch.
_PARQUET_SPLIT_DIR = {
    "validation": "default/validation",
    "test":       "default/test",
    "train":            "default/train_annotated",
    "train_annotated":  "default/train_annotated",
    "train_distant":    "default/train_distant",
}


def _cache_paths(cache_dir: Optional[str], dataset_name: str, split: str) -> tuple[Optional[Path], Optional[str]]:
    if not cache_dir:
        return None, None
    root = Path(cache_dir)
    safe_name = dataset_name.replace("/", "__")
    mirror = root / "datasets" / safe_name / f"{split}.jsonl"
    hf_cache = str(root / "hf_datasets")
    return mirror, hf_cache


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    return obj


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_jsonable(row), ensure_ascii=False) + "\n")
    tmp.replace(path)


def _load_parquet_branch(hf_name: str, split: str, hf_cache_dir: Optional[str]):
    """Load a split via the HF auto-converted parquet branch."""
    sub = _PARQUET_SPLIT_DIR.get(split, f"default/{split}")
    data_files = f"hf://datasets/{hf_name}@~parquet/{sub}/*.parquet"
    log.info("Loading parquet: %s", data_files)
    kwargs = {"data_files": data_files, "split": "train"}
    if hf_cache_dir:
        kwargs["cache_dir"] = hf_cache_dir
    return load_dataset("parquet", **kwargs)


def _normalize_redocred_labels(labels_list: list[dict]) -> dict:
    """Convert Re-DocRED list-of-dicts to columnar dict (HF parquet shape)."""
    out = {"head": [], "tail": [], "relation_id": [], "relation_text": [], "evidence": []}
    for lab in labels_list or []:
        out["head"].append(lab.get("h"))
        out["tail"].append(lab.get("t"))
        out["relation_id"].append(lab.get("r"))
        out["relation_text"].append(lab.get("r"))
        out["evidence"].append(lab.get("evidence") or [])
    return out


def _iter_local_json_array(path: Path):
    """Yield Re-DocRED-style records from a JSON array file."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    for ex in data:
        if isinstance(ex.get("labels"), list):
            ex = dict(ex)
            ex["labels"] = _normalize_redocred_labels(ex["labels"])
        yield ex


def iter_docred(split: str = "validation",
                hf_name: str = "docred",
                hf_config: Optional[str] = None,
                cache_dir: Optional[str] = None,
                limit: Optional[int] = None,
                local_files: Optional[dict] = None) -> Iterator[dict]:
    """Yield raw DocRED-format examples.

    If ``local_files`` is supplied (split -> path), reads from disk in
    Re-DocRED list-of-dicts format and normalizes labels to HF columnar shape.
    Otherwise falls back to the HF datasets API / parquet branch.
    """
    if local_files and split in local_files:
        path = Path(local_files[split])
        log.info("Loading local JSON: %s", path)
        for i, ex in enumerate(_iter_local_json_array(path)):
            if limit is not None and i >= limit:
                break
            yield i, ex
        return

    log.info("Loading HF dataset %s split=%s config=%s", hf_name, split, hf_config)
    mirror_path, hf_cache_dir = _cache_paths(cache_dir, hf_name if "/" in hf_name else f"thunlp/{hf_name}", split)
    if mirror_path and mirror_path.exists():
        log.info("Loading local dataset mirror: %s", mirror_path)
        for i, ex in enumerate(_iter_jsonl(mirror_path)):
            if limit is not None and i >= limit:
                break
            yield i, ex
        return

    kwargs: dict = {"split": split}
    if hf_config:
        kwargs["name"] = hf_config
    if hf_cache_dir:
        kwargs["cache_dir"] = hf_cache_dir
    try:
        ds = load_dataset(hf_name, **kwargs)
    except Exception as e:
        log.warning("Standard load failed (%s); falling back to parquet branch", e)
        # Resolve canonical name (HF redirects bare 'docred' -> 'thunlp/docred')
        canonical = hf_name if "/" in hf_name else f"thunlp/{hf_name}"
        ds = _load_parquet_branch(canonical, split, hf_cache_dir)

    if mirror_path:
        materialized = [_jsonable(ex) for ex in ds]
        _write_jsonl(mirror_path, materialized)
        ds_iter = materialized
        log.info("Wrote local dataset mirror: %s (%d rows)", mirror_path, len(materialized))
    else:
        ds_iter = ds

    for i, ex in enumerate(ds_iter):
        if limit is not None and i >= limit:
            break
        yield i, ex


def import_docred_into_db(conn,
                          split: str = "validation",
                          hf_name: str = "docred",
                          hf_config: Optional[str] = None,
                          cache_dir: Optional[str] = None,
                          limit: Optional[int] = None,
                          local_files: Optional[dict] = None,
                          dataset_name: str = "docred",
                          doc_id_prefix: Optional[str] = None) -> LoadStats:
    stats = LoadStats()
    prefix = doc_id_prefix or dataset_name
    for idx, ex in iter_docred(split=split, hf_name=hf_name, hf_config=hf_config,
                               cache_dir=cache_dir, limit=limit, local_files=local_files):
        title = ex.get("title") or f"doc_{idx}"
        sents = ex.get("sents") or []
        vertex_set = ex.get("vertexSet") or []
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:40]
        document_id = f"{prefix}-{split}-{idx:06d}-{safe}"
        sentence_rows = _build_sentences(document_id, sents)
        entity_rows = _build_entities(document_id, vertex_set)
        raw_text = "\n".join(s.text for s in sentence_rows)

        repo.upsert_document(conn, repo.Document(
            document_id=document_id, dataset=dataset_name, title=title,
            raw_text=raw_text, split=split,
        ))
        if sentence_rows:
            repo.upsert_sentences(conn, sentence_rows)
        if entity_rows:
            repo.upsert_entities(conn, entity_rows)
        gold_rows = _build_gold_edges(document_id, ex.get("labels"), entity_rows)
        if gold_rows:
            repo.upsert_gold_edges(conn, gold_rows)
        conn.commit()

        stats.documents += 1
        stats.sentences += len(sentence_rows)
        stats.entities += len(entity_rows)
    return stats
