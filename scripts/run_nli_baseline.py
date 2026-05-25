"""C1 — NLI baseline for triple verification.

Treat each extracted edge (s, r, o) as a hypothesis to be entailed by the source sentence(s).
Use a pretrained NLI model (DeBERTa-v3 base MNLI, ~440MB) to score entailment vs contradiction.
The signal `nli_entail - nli_contradict` is then evaluated as an error-detection signal
analogous to E2 (paired against the same labels: correct vs wrong vs unmatched).

This is a *zero-cost* (no LLM call) baseline competitive with logprob/SelfCheck approaches.

usage:
  python scripts/run_nli_baseline.py
"""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path

import numpy as np

REL_VERBALIZER = {
    "P131": "is located in",
    "P17": "is in country",
    "P27": "is a citizen of",
    "P19": "was born in",
    "P20": "died in",
    "P108": "is employed by",
    "P159": "is headquartered in",
    "P50": "is the author of",
    "P57": "is the director of",
    "P175": "is performed by",
    "P361": "is part of",
    "P150": "contains",
    "P800": "is known for",
    "P136": "has genre",
    "P364": "has original language",
    "P1412": "speaks",
    "P937": "worked in",
    "P176": "is manufactured by",
    "P127": "is owned by",
}


def verbalize(s: str, rel: str, o: str) -> str:
    v = REL_VERBALIZER.get(rel, rel.replace("_", " "))
    return f"{s} {v} {o}."


def load_edges(conn: sqlite3.Connection):
    return conn.execute("""
        SELECT ee.edge_id, ee.subject_name, ee.relation, ee.object_name,
               ev.document_id, ev.input_sentence_ids_json, ee.event_id
        FROM extracted_edges ee
        JOIN extraction_events ev ON ev.event_id = ee.event_id
        WHERE ev.event_id IN (SELECT base_event_id FROM counterfactual_runs)
           OR ev.event_id NOT IN (SELECT run_id FROM counterfactual_runs)
    """).fetchall()


def get_premise(conn: sqlite3.Connection, doc_id: str, sentence_ids_json: str) -> str:
    try:
        ids = json.loads(sentence_ids_json) if sentence_ids_json else []
    except Exception:
        ids = []
    if ids:
        rows = conn.execute(
            f"SELECT text FROM sentences WHERE document_id=? AND sentence_id IN ({','.join('?'*len(ids))}) ORDER BY sentence_index",
            [doc_id, *ids],
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT text FROM sentences WHERE document_id=? ORDER BY sentence_index", (doc_id,)
        ).fetchall()
    return " ".join(r[0] for r in rows)[:1800]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/processed/docred.db")
    ap.add_argument("--model", default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
    ap.add_argument("--out", default="data/processed/nli_baseline.json")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    print(f"[load] {args.model}")
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(args.model)
    device = args.device if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    label_map = model.config.id2label
    ent_idx = next(i for i, n in label_map.items() if "entail" in n.lower())
    con_idx = next(i for i, n in label_map.items() if "contra" in n.lower())

    conn = sqlite3.connect(args.db)
    edges = load_edges(conn)
    if args.limit: edges = edges[: args.limit]
    print(f"[scoring] {len(edges)} edges")

    results = []
    for i in range(0, len(edges), args.batch):
        chunk = edges[i:i + args.batch]
        premises = [get_premise(conn, e[4], e[5]) for e in chunk]
        hypotheses = [verbalize(e[1], e[2], e[3]) for e in chunk]
        with torch.no_grad():
            enc = tok(premises, hypotheses, padding=True, truncation=True,
                      return_tensors="pt", max_length=512).to(device)
            logits = model(**enc).logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
        for e, p in zip(chunk, probs):
            results.append({
                "edge_id": e[0], "subject": e[1], "relation": e[2], "object": e[3],
                "document_id": e[4],
                "p_entail": float(p[ent_idx]),
                "p_contra": float(p[con_idx]),
                "score": float(p[ent_idx] - p[con_idx]),  # higher = more reliable
            })
        if (i // args.batch) % 10 == 0:
            print(f"  {i + len(chunk)}/{len(edges)}")

    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"[done] wrote {args.out}")

    # Quick AUC-PR vs E2 labels (if available)
    rows = conn.execute(
        "SELECT edge_id, label FROM edge_correctness"
    ).fetchall()
    if rows:
        lbl = {r[0]: r[1] for r in rows}
        score_lbl = [(r["score"], lbl.get(r["edge_id"])) for r in results
                     if r["edge_id"] in lbl]
        if score_lbl:
            scores = np.array([-s for s, _ in score_lbl])  # invert: high score = error
            y = np.array([1 if l in ("wrong", "unmatched") else 0 for _, l in score_lbl])
            from sklearn.metrics import average_precision_score, roc_auc_score
            print(f"\n[NLI baseline as error detector]  n={len(score_lbl)}")
            print(f"  AUC-PR (¬entail predicts error) = {average_precision_score(y, scores):.4f}")
            print(f"  ROC-AUC                          = {roc_auc_score(y, scores):.4f}")


if __name__ == "__main__":
    main()
