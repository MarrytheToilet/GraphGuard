"""BC5CDR loader that emits DocRED-shaped records.

PubTator source format (per-document blocks separated by blank lines):

    PMID|t|<title>
    PMID|a|<abstract>
    PMID\tstart\tend\ttext\ttype\tmesh_id          # entity mention
    ...
    PMID\tCID\tchem_mesh\tdisease_mesh             # relation
    <blank>

Each MeSH ID groups multiple character-span mentions into one vertex (cluster),
mirroring the DocRED `vertexSet` shape. Relations carry a single label "CID"
(Chemical-Induces-Disease). Sentences are split with a regex that respects
common biomedical abbreviations.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterator, Optional

log = logging.getLogger(__name__)


# Conservative sentence splitter for biomedical text.
# Splits on . ! ? followed by whitespace + capital letter, but not after common abbreviations.
_ABBREV = {"e.g", "i.e", "vs", "et", "al", "fig", "etc", "ref", "vol", "no", "approx",
           "Dr", "Mr", "Mrs", "Ms", "St", "U.S", "U.K", "Inc", "Ltd"}
_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def _sent_split(text: str) -> list[tuple[int, int, str]]:
    """Return list of (char_start, char_end, sent_text) for `text`."""
    if not text.strip():
        return []
    parts: list[tuple[int, int, str]] = []
    cursor = 0
    for chunk in _SPLIT_RE.split(text):
        if not chunk:
            continue
        # Find chunk in remaining text starting at cursor (handles whitespace).
        start = text.find(chunk, cursor)
        if start < 0:
            start = cursor
        end = start + len(chunk)
        # Re-merge if previous fragment ends with an abbreviation.
        if parts:
            prev_text = parts[-1][2].rstrip()
            last_token = re.split(r"\s+", prev_text)[-1].rstrip(".") if prev_text else ""
            if last_token in _ABBREV:
                ps, _, pt = parts[-1]
                merged = text[ps:end]
                parts[-1] = (ps, end, merged)
                cursor = end
                continue
        parts.append((start, end, chunk))
        cursor = end
    return parts


def _tokenize(sent: str) -> list[tuple[int, int, str]]:
    """Whitespace+punctuation tokenization. Returns (start, end, token) within `sent`."""
    toks = []
    for m in re.finditer(r"[A-Za-z0-9][A-Za-z0-9\-/]*|[^\sA-Za-z0-9]", sent):
        toks.append((m.start(), m.end(), m.group(0)))
    return toks


def _char_to_sent(char_pos: int, sent_spans: list[tuple[int, int, str]]) -> int:
    for sid, (s, e, _) in enumerate(sent_spans):
        if s <= char_pos < e:
            return sid
    return max(0, len(sent_spans) - 1)


def _char_span_to_token_span(char_start: int, char_end: int,
                              sent_spans: list[tuple[int, int, str]],
                              sent_tokens: list[list[tuple[int, int, str]]]
                              ) -> Optional[tuple[int, int, int]]:
    """Map global (char_start, char_end) -> (sent_id, tok_start, tok_end_exclusive)."""
    sid = _char_to_sent(char_start, sent_spans)
    s_off = sent_spans[sid][0]
    local_s = char_start - s_off
    local_e = char_end - s_off
    toks = sent_tokens[sid]
    if not toks:
        return None
    tok_start = None
    tok_end = None
    for ti, (ts, te, _) in enumerate(toks):
        if tok_start is None and te > local_s:
            tok_start = ti
        if ts < local_e:
            tok_end = ti + 1
        if ts >= local_e:
            break
    if tok_start is None or tok_end is None or tok_end <= tok_start:
        return None
    return sid, tok_start, tok_end


def _parse_pubtator(path: Path) -> Iterator[dict]:
    block: list[str] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                if block:
                    yield _parse_block(block)
                    block = []
            else:
                block.append(line.rstrip("\n"))
    if block:
        yield _parse_block(block)


def _parse_block(lines: list[str]) -> dict:
    pmid = ""
    title = ""
    abstract = ""
    mentions = []   # (start, end, text, type, mesh)
    relations = []  # (chem_mesh, disease_mesh)
    for ln in lines:
        if "|t|" in ln:
            pmid, _, title = ln.partition("|t|")
        elif "|a|" in ln:
            _, _, abstract = ln.partition("|a|")
        else:
            parts = ln.split("\t")
            if len(parts) == 6 and parts[1].isdigit():
                _, s, e, txt, typ, mesh = parts
                mentions.append((int(s), int(e), txt, typ, mesh))
            elif len(parts) == 4 and parts[1] == "CID":
                relations.append((parts[2], parts[3]))
    full = title + " " + abstract  # title and abstract are concatenated; offsets index this string
    return {"pmid": pmid, "title": title, "abstract": abstract, "text": full,
            "mentions": mentions, "relations": relations}


def iter_cdr(split: str = "validation",
             local_dir: str = "data/raw/cdr/CDR_Data/CDR.Corpus.v010516",
             limit: Optional[int] = None) -> Iterator[tuple[int, dict]]:
    """Yield (idx, docred-shaped example)."""
    fname = {"validation": "CDR_DevelopmentSet.PubTator.txt",
             "dev":        "CDR_DevelopmentSet.PubTator.txt",
             "train":      "CDR_TrainingSet.PubTator.txt",
             "test":       "CDR_TestSet.PubTator.txt"}.get(split)
    if fname is None:
        raise ValueError(f"unknown CDR split: {split}")
    path = Path(local_dir) / fname
    if not path.exists():
        raise FileNotFoundError(f"CDR split not found: {path}")
    log.info("Loading CDR: %s", path)

    for i, doc in enumerate(_parse_pubtator(path)):
        if limit is not None and i >= limit:
            break
        text = doc["text"]
        sent_spans = _sent_split(text)
        if not sent_spans:
            continue
        sentences_tokens = [_tokenize(s_text) for _, _, s_text in sent_spans]
        sentences_str = [[t for _, _, t in toks] for toks in sentences_tokens]

        # Group mentions by MeSH id.
        mesh_to_cluster: dict[str, int] = {}
        vertex_set: list[list[dict]] = []
        for s, e, txt, typ, mesh in doc["mentions"]:
            tspan = _char_span_to_token_span(s, e, sent_spans, sentences_tokens)
            if tspan is None:
                continue
            sid, ts, te = tspan
            mention = {"name": txt, "sent_id": sid, "type": typ, "pos": [ts, te]}
            # Some mentions have composite mesh like "D001234|D005678" — treat as multi-cluster.
            for mid in (mesh.split("|") if mesh else ["-1"]):
                if not mid or mid == "-1":
                    continue
                if mid not in mesh_to_cluster:
                    mesh_to_cluster[mid] = len(vertex_set)
                    vertex_set.append([])
                vertex_set[mesh_to_cluster[mid]].append(mention)

        # Drop empty clusters (shouldn't happen but be safe).
        kept = [(mid, idx) for mid, idx in mesh_to_cluster.items() if vertex_set[idx]]
        # Re-index vertex_set after potential drops.
        new_vs = [vertex_set[idx] for _, idx in kept]
        new_idx_map = {mid: ni for ni, (mid, _) in enumerate(kept)}

        # Build labels.
        heads, tails, rels, rel_text, evid = [], [], [], [], []
        for chem_mesh, dis_mesh in doc["relations"]:
            h = new_idx_map.get(chem_mesh)
            t = new_idx_map.get(dis_mesh)
            if h is None or t is None or h == t:
                continue
            heads.append(h)
            tails.append(t)
            rels.append("CID")
            rel_text.append("CID")
            # Evidence = sentence ids where either mention appears.
            sids = sorted({m["sent_id"] for m in new_vs[h] + new_vs[t]})
            evid.append(sids[:5])

        yield i, {
            "title": doc["pmid"] or f"cdr_{i}",
            "sents": sentences_str,
            "vertexSet": new_vs,
            "labels": {"head": heads, "tail": tails, "relation_id": rels,
                       "relation_text": rel_text, "evidence": evid},
        }


def import_cdr_into_db(conn,
                       split: str = "validation",
                       local_dir: str = "data/raw/cdr/CDR_Data/CDR.Corpus.v010516",
                       limit: Optional[int] = None,
                       dataset_name: str = "cdr",
                       doc_id_prefix: Optional[str] = None):
    """Mirror of import_scierc_into_db: feeds CDR records through DocRED writer."""
    from .load_docred import _build_sentences, _build_entities, _build_gold_edges
    from ..db import repositories as repo

    prefix = doc_id_prefix or dataset_name
    n_docs = n_sents = n_ents = 0
    for idx, ex in iter_cdr(split=split, local_dir=local_dir, limit=limit):
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
    log.info("CDR import done: %d docs / %d sents / %d entities", n_docs, n_sents, n_ents)

    class _S:
        pass
    s = _S()
    s.documents = n_docs
    s.sentences = n_sents
    s.entities = n_ents
    return s
