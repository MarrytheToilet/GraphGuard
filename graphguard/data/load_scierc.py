"""SciERC loader that emits DocRED-shaped records.

SciERC source format (one JSON object per line in processed_data/json/{train,dev,test}.json):
  - doc_key:   str (paper abstract identifier)
  - sentences: list[list[str]]  (tokens per sentence)
  - ner:       list[ list[ [global_start, global_end, type] ] ]  (per sentence; spans use
               GLOBAL token indices across the whole abstract; end is INCLUSIVE)
  - relations: list[ list[ [h_start, h_end, t_start, t_end, rel_type] ] ]
  - clusters:  list[ list[ [global_start, global_end] ] ]  (coreference clusters)

We map each abstract to a DocRED example so it flows through our existing
`import_docred_into_db` machinery without further changes.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator, Optional

log = logging.getLogger(__name__)


def _sent_offsets(sentences: list[list[str]]) -> list[int]:
    offs, n = [0], 0
    for s in sentences:
        n += len(s)
        offs.append(n)
    return offs


def _locate_span(global_start: int, global_end: int, offsets: list[int]) -> tuple[int, int, int]:
    """Return (sent_id, local_start, local_end_inclusive)."""
    for sid in range(len(offsets) - 1):
        if offsets[sid] <= global_start < offsets[sid + 1]:
            return sid, global_start - offsets[sid], global_end - offsets[sid]
    return len(offsets) - 2, global_start - offsets[-2], global_end - offsets[-2]


def _span_text(sentences: list[list[str]], offsets: list[int],
               g_start: int, g_end: int) -> str:
    sid, ls, le = _locate_span(g_start, g_end, offsets)
    sent = sentences[sid]
    le = min(le, len(sent) - 1)
    return " ".join(sent[ls:le + 1])


def _normalize_clusters(ner_per_sent: list[list[list]],
                        clusters: list[list[list[int]]],
                        sentences: list[list[str]]) -> tuple[list[dict], dict[tuple[int, int], int]]:
    """Return (vertexSet, span->cluster_index map).

    Each vertex cluster is the union of: (a) a coref cluster, plus
    (b) any NER mention whose span falls inside one of those coref spans.
    Singleton NER mentions become their own cluster.
    """
    offsets = _sent_offsets(sentences)
    span_to_cluster: dict[tuple[int, int], int] = {}
    vertex_set: list[dict] = []

    # Collect every NER mention with type (global-indexed).
    ner_mentions: list[tuple[int, int, str]] = []
    for sent_ner in ner_per_sent:
        for m in sent_ner:
            if len(m) >= 3:
                ner_mentions.append((int(m[0]), int(m[1]), str(m[2])))

    span_to_type: dict[tuple[int, int], str] = {(s, e): t for s, e, t in ner_mentions}

    # Step 1: coref clusters → vertex clusters
    for cluster in clusters:
        mentions = []
        types_in_cluster: list[str] = []
        for span in cluster:
            s, e = int(span[0]), int(span[1])
            sid, ls, le = _locate_span(s, e, offsets)
            name = _span_text(sentences, offsets, s, e)
            t = span_to_type.get((s, e))
            mentions.append({"name": name, "sent_id": sid, "type": t or "Entity",
                             "pos": [ls, le + 1]})
            if t:
                types_in_cluster.append(t)
            span_to_cluster[(s, e)] = len(vertex_set)
        if mentions:
            vertex_set.append({"_mentions": mentions, "_types": types_in_cluster})

    # Step 2: singleton NER mentions not yet assigned
    for s, e, t in ner_mentions:
        if (s, e) in span_to_cluster:
            continue
        sid, ls, le = _locate_span(s, e, offsets)
        name = _span_text(sentences, offsets, s, e)
        span_to_cluster[(s, e)] = len(vertex_set)
        vertex_set.append({"_mentions": [{"name": name, "sent_id": sid, "type": t,
                                           "pos": [ls, le + 1]}],
                           "_types": [t]})

    # Convert to DocRED vertexSet shape (list of mention lists) but keep type metadata.
    docred_vs: list[list[dict]] = []
    for v in vertex_set:
        cluster_mentions = []
        # pick a stable type: most common non-Generic, else first
        type_counts: dict[str, int] = {}
        for t in v["_types"]:
            type_counts[t] = type_counts.get(t, 0) + 1
        non_generic = [t for t in type_counts if t != "Generic"]
        chosen = max(non_generic, key=lambda x: type_counts[x]) if non_generic else (
            max(type_counts, key=lambda x: type_counts[x]) if type_counts else "Entity"
        )
        for m in v["_mentions"]:
            cluster_mentions.append({"name": m["name"], "sent_id": m["sent_id"],
                                     "type": chosen, "pos": m["pos"]})
        docred_vs.append(cluster_mentions)

    return docred_vs, span_to_cluster


def _build_labels(relations_per_sent: list[list[list]],
                  span_to_cluster: dict[tuple[int, int], int]) -> dict:
    heads, tails, rels, rel_text, evid = [], [], [], [], []
    for sid, sent_rels in enumerate(relations_per_sent):
        for r in sent_rels:
            if len(r) < 5:
                continue
            hs, he, ts, te = int(r[0]), int(r[1]), int(r[2]), int(r[3])
            rel_type = str(r[4])
            h_idx = span_to_cluster.get((hs, he))
            t_idx = span_to_cluster.get((ts, te))
            if h_idx is None or t_idx is None or h_idx == t_idx:
                continue
            heads.append(h_idx)
            tails.append(t_idx)
            rels.append(rel_type)
            rel_text.append(rel_type)
            evid.append([sid])
    return {"head": heads, "tail": tails, "relation_id": rels,
            "relation_text": rel_text, "evidence": evid}


def iter_scierc(split: str = "dev",
                local_dir: str = "data/raw/scierc/processed_data/json",
                limit: Optional[int] = None) -> Iterator[tuple[int, dict]]:
    """Yield (idx, docred-shaped example) records."""
    fname = {"validation": "dev.json", "dev": "dev.json",
             "train": "train.json", "test": "test.json"}.get(split, f"{split}.json")
    path = Path(local_dir) / fname
    if not path.exists():
        raise FileNotFoundError(f"SciERC split not found: {path}")
    log.info("Loading SciERC: %s", path)
    with path.open() as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            if limit is not None and i >= limit:
                break
            ex = json.loads(line)
            sentences = ex.get("sentences") or []
            ner = ex.get("ner") or [[] for _ in sentences]
            relations = ex.get("relations") or [[] for _ in sentences]
            clusters = ex.get("clusters") or []
            vs, span_map = _normalize_clusters(ner, clusters, sentences)
            labels = _build_labels(relations, span_map)
            yield i, {
                "title": ex.get("doc_key") or f"scierc_{i}",
                "sents": sentences,
                "vertexSet": vs,
                "labels": labels,
            }


def import_scierc_into_db(conn,
                           split: str = "dev",
                           local_dir: str = "data/raw/scierc/processed_data/json",
                           limit: Optional[int] = None,
                           dataset_name: str = "scierc",
                           doc_id_prefix: Optional[str] = None):
    """Mirror of import_docred_into_db: feeds SciERC records through DocRED writer."""
    from .load_docred import _build_sentences, _build_entities, _build_gold_edges
    from ..db import repositories as repo

    prefix = doc_id_prefix or dataset_name
    n_docs = n_sents = n_ents = 0
    for idx, ex in iter_scierc(split=split, local_dir=local_dir, limit=limit):
        title = ex["title"]
        sents = ex["sents"]
        vertex_set = ex["vertexSet"]
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
        gold_rows = _build_gold_edges(document_id, ex["labels"], entity_rows)
        if gold_rows:
            repo.upsert_gold_edges(conn, gold_rows)
        conn.commit()
        n_docs += 1
        n_sents += len(sentence_rows)
        n_ents += len(entity_rows)
    log.info("SciERC import done: %d docs / %d sents / %d entities", n_docs, n_sents, n_ents)
    return {"documents": n_docs, "sentences": n_sents, "entities": n_ents}
