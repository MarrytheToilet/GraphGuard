#!/usr/bin/env python3
"""Perturbation magnitude vs. graph drift (PVLDB revision, R2 / Rev5-W3).

For every ok counterfactual pair in a run's lineage DB, recover a quantitative
perturbation magnitude from the lineage itself and relate it to graph drift:

  schema   — structural diff between base and cf relation_types_json:
             semantic-touch count (relations removed/added by description),
             relabel count (same description, new label/id), description-edit
             count, and an order-only flag.
  prompt   — clause-level token edit ratio between base and cf prompt
             (clauses added/removed/replaced, tokens changed / base tokens).
  evidence — diff of input_sentence_ids_json between the paired events:
             fraction of sentences removed, or normalized Kendall-tau
             reorder distance for order-only changes.
  alias    — aliased entities / document entities.
  stochastic — magnitude 0 by construction (noise-floor reference).

Outputs reports/cross_run/magnitude_<run>.json with per-pair rows and a
per-family summary (magnitude buckets, mean drift, Spearman rho).

Usage:
  python scripts/run_magnitude_analysis.py                  # all four main runs
  python scripts/run_magnitude_analysis.py --runs docred__deepseek-v4-flash__300d
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Canonicalized drift identical to the contract checker: entity-alias
# canonicalization + rename back-projection + coarse-bucket-aware matching.
from graphguard.contracts.metrics import edge_jaccard  # noqa: E402

MAIN_RUNS = [
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
]

OUT_DIR = ROOT / "reports" / "cross_run"


# ------------------------------------------------------------------ helpers

def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    u = len(a | b)
    return len(a & b) / u if u else 1.0


def tokens(s: str) -> list[str]:
    return s.split()


def kendall_tau_dist(base_order: list, cf_order: list) -> float:
    """Normalized Kendall-tau distance over the common elements (0..1)."""
    common = [x for x in base_order if x in set(cf_order)]
    if len(common) < 2:
        return 0.0
    pos = {x: i for i, x in enumerate(cf_order)}
    seq = [pos[x] for x in common]
    n = len(seq)
    inv = sum(1 for i in range(n) for j in range(i + 1, n) if seq[i] > seq[j])
    return inv / (n * (n - 1) / 2)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else None


# ------------------------------------------------------- magnitude features

def schema_features(base_rels: list[dict], cf_rels: list[dict]) -> dict:
    """Structural diff keyed by relation description (stable across renames)."""
    def by_desc(rels):
        d = {}
        for r in rels:
            d.setdefault((r.get("description") or r.get("label") or r.get("id")), []).append(r)
        return d
    b_ids = [r.get("id") for r in base_rels]
    c_ids = [r.get("id") for r in cf_rels]
    bd, cd = by_desc(base_rels), by_desc(cf_rels)
    removed = sum(len(v) for k, v in bd.items() if k not in cd)
    added = sum(len(v) for k, v in cd.items() if k not in bd)
    relabel = 0
    desc_changed = 0
    for k in set(bd) & set(cd):
        for rb, rc in zip(bd[k], cd[k]):
            if rb.get("label") != rc.get("label") or rb.get("id") != rc.get("id"):
                relabel += 1
    # description edits among same-id relations
    b_by_id = {r.get("id"): r for r in base_rels}
    for r in cf_rels:
        rb = b_by_id.get(r.get("id"))
        if rb and rb.get("label") == r.get("label") and (rb.get("description") or "") != (r.get("description") or ""):
            desc_changed += 1
    common_ids = [i for i in b_ids if i in set(c_ids)]
    reordered = common_ids != [i for i in c_ids if i in set(b_ids)]
    n_base = max(1, len(base_rels))
    semantic_touch = removed + added
    presentation_touch = relabel + desc_changed
    return {
        "n_base": len(base_rels), "n_cf": len(cf_rels),
        "removed": removed, "added": added, "relabel": relabel,
        "desc_changed": desc_changed, "reordered": bool(reordered),
        "semantic_frac": semantic_touch / n_base,
        "presentation_frac": presentation_touch / n_base,
    }


def schema_variant(desc: str) -> tuple[str, int | None]:
    """Parse the intervention description into (variant kind, k)."""
    d = desc or ""
    if "drop relation" in d:
        return "drop", 1
    if "ambiguous:" in d:
        k = d.split("ambiguous:")[1].split("'")[0].count(",") + 1
        return "ambiguous", k
    if "'coarse'" in d:
        return "coarse", None
    if "'with_other'" in d:
        return "with_other", None
    if "Presentation schema variant" in d:
        name = d.split("'")[1] if "'" in d else "unknown"
        return f"pres_{name}", 0
    return "other", None


def schema_level(variant: str, k, f: dict) -> str:
    """Magnitude level label combining variant kind and structural touch count."""
    if variant == "drop":
        return "sem-drop-1"
    if variant == "ambiguous":
        return f"sem-ambig-{k}"
    if variant == "coarse":
        return "sem-coarse"
    if variant == "with_other":
        return "sem-add-other"
    if variant.startswith("pres_"):
        return variant.replace("pres_", "pres-")
    # fallback to structural diff
    st = f["removed"] + f["added"]
    return f"sem-{st}" if st else "pres-none"


def prompt_edit_ratio(con, base_pid: str, cf_pid: str) -> dict:
    """Clause-level edit between two prompt variants.

    Variant clause texts are not persisted in the lineage DB; they are produced
    deterministically by graphguard.interventions.prompt (drop removes one base
    clause; role_swap inserts C0_role; tone appends C9_tone). We therefore
    reconstruct the changed text from the base clause table plus the
    ROLE_VARIANTS / TONE_VARIANTS constants used at extraction time.
    """
    from graphguard.interventions.prompt import ROLE_VARIANTS, TONE_VARIANTS
    cur = con.cursor()
    base_clauses = {cid: txt for cid, txt in cur.execute(
        "SELECT clause_id, clause_text FROM prompt_clauses WHERE prompt_id=?", (base_pid,))}
    ids = {}
    for pid in (base_pid, cf_pid):
        row = cur.execute("SELECT clause_ids_json FROM prompts WHERE prompt_id=?", (pid,)).fetchone()
        ids[pid] = json.loads(row[0]) if row and row[0] else []
    base_ids, cf_ids = ids[base_pid], ids[cf_pid]
    removed = [c for c in base_ids if c not in set(cf_ids)]
    added = [c for c in cf_ids if c not in set(base_ids)]
    base_tokens = sum(len(tokens(t)) for t in base_clauses.values()) or 1
    changed = sum(len(tokens(base_clauses.get(c, ""))) for c in removed)
    for c in added:
        if c == "C0_role":
            variant = cf_pid.rsplit("role_", 1)[-1]
            changed += len(tokens(ROLE_VARIANTS.get(variant, next(iter(ROLE_VARIANTS.values())))))
        elif c == "C9_tone":
            variant = cf_pid.rsplit("tone_", 1)[-1]
            changed += len(tokens(TONE_VARIANTS.get(variant, next(iter(TONE_VARIANTS.values())))))
        else:
            changed += len(tokens(base_clauses.get(c, "")))
    return {
        "clauses_base": len(base_ids), "clauses_cf": len(cf_ids),
        "clauses_changed": len(removed) + len(added),
        "token_edit_ratio": changed / base_tokens,
    }


def evidence_features(base_sids: list, cf_sids: list) -> dict:
    bs, cs = list(base_sids or []), list(cf_sids or [])
    if not bs:
        return {"frac_removed": 0.0, "reorder_tau": 0.0}
    removed = [x for x in bs if x not in set(cs)]
    return {
        "n_base": len(bs), "n_removed": len(removed),
        "frac_removed": len(removed) / len(bs),
        "reorder_tau": kendall_tau_dist(bs, cs),
    }


# ------------------------------------------------------------------- runner

def analyze_run(run: str) -> dict | None:
    db = ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
    if not db.exists():
        print(f"[skip] {run}: no db")
        return None
    con = sqlite3.connect(db)
    cur = con.cursor()

    edges = defaultdict(list)
    for eid, sid, sn, r, oid, on in cur.execute(
        "SELECT event_id, subject_entity_id, subject_name, relation, "
        "object_entity_id, object_name FROM extracted_edges"):
        edges[eid].append({
            "subject_entity_id": sid, "subject_name": sn, "relation": r,
            "object_entity_id": oid, "object_name": on,
        })

    events = {eid: (pid, sid, json.loads(sj) if sj else [])
              for eid, pid, sid, sj in cur.execute(
                  "SELECT event_id, prompt_id, schema_id, input_sentence_ids_json FROM extraction_events")}
    schemas = {sid: json.loads(rj) for sid, rj in cur.execute(
        "SELECT schema_id, relation_types_json FROM schemas")}
    iv = {ivid: (fam, op, desc, sc) for ivid, fam, op, desc, sc in cur.execute(
        "SELECT intervention_id, cause_family, operator, description, semantic_class "
        "FROM intervention_candidates")}
    n_entities = dict(cur.execute(
        "SELECT document_id, COUNT(*) FROM entities GROUP BY document_id"))

    prompt_cache: dict[tuple, dict] = {}
    rows = []
    for run_id, base_ev, cf_ev, ivid, doc in cur.execute(
        "SELECT run_id, base_event_id, cf_event_id, intervention_id, document_id "
        "FROM counterfactual_runs WHERE status='ok' AND cf_event_id IS NOT NULL AND cf_event_id<>''"):
        if base_ev not in events or cf_ev not in events:
            continue
        fam, op, desc, sem_class = iv.get(ivid, ("unknown", "unknown", "", "unknown"))
        b_pid, b_sid, b_sents = events[base_ev]
        c_pid, c_sid, c_sents = events[cf_ev]
        base_rel_ids = {r.get("id") for r in schemas.get(b_sid, [])} or None
        drift = 1.0 - edge_jaccard(edges.get(base_ev, []), edges.get(cf_ev, []),
                                   base_relation_ids=base_rel_ids)

        row = {"run_id": run_id, "doc": doc, "family": fam, "operator": op,
               "semantic_class": sem_class, "drift": drift}
        if fam == "schema" and b_sid in schemas and c_sid in schemas:
            f = schema_features(schemas[b_sid], schemas[c_sid])
            variant, k = schema_variant(desc)
            row.update(f)
            row["variant"] = variant
            row["level"] = schema_level(variant, k, f)
            sem_k = {"drop": 1, "with_other": 1}.get(variant, k if variant == "ambiguous" else None)
            if variant == "coarse":
                sem_k = f["removed"] + f["added"]
            row["magnitude"] = (sem_k / max(1, f["n_base"])) if sem_k is not None \
                else f["presentation_frac"]
        elif fam == "prompt":
            key = (b_pid, c_pid)
            if key not in prompt_cache:
                prompt_cache[key] = prompt_edit_ratio(con, b_pid, c_pid)
            row.update(prompt_cache[key])
            row["level"] = f"clauses-{row['clauses_changed']}"
            row["magnitude"] = row["token_edit_ratio"]
        elif fam == "evidence":
            f = evidence_features(b_sents, c_sents)
            row.update(f)
            if f["frac_removed"] > 0:
                row["level"] = "remove"
                row["magnitude"] = f["frac_removed"]
            else:
                row["level"] = "reorder"
                row["magnitude"] = f["reorder_tau"]
        elif fam == "entity_alias":
            ne = n_entities.get(doc, 0) or 1
            row["level"] = "alias-1"
            row["magnitude"] = 1.0 / ne
        elif fam == "stochastic":
            row["level"] = "noop"
            row["magnitude"] = 0.0
        else:
            row["level"] = op
            row["magnitude"] = None
        rows.append(row)

    # ------------------------------------------------------------ summarize
    summary: dict = {}
    for fam in sorted({r["family"] for r in rows}):
        fr = [r for r in rows if r["family"] == fam]
        by_level = defaultdict(list)
        for r in fr:
            by_level[r["level"]].append(r["drift"])
        mags = [r["magnitude"] for r in fr if r.get("magnitude") is not None]
        drifts = [r["drift"] for r in fr if r.get("magnitude") is not None]
        summary[fam] = {
            "n": len(fr),
            "mean_drift": statistics.mean([r["drift"] for r in fr]) if fr else None,
            "levels": {lvl: {"n": len(v), "mean_drift": statistics.mean(v),
                             "median_drift": statistics.median(v)}
                       for lvl, v in sorted(by_level.items())},
            "spearman_mag_drift": spearman(mags, drifts),
        }
        if fam == "schema":
            sem = [r for r in fr if str(r.get("level", "")).startswith("sem-")
                   and r.get("magnitude") is not None]
            summary[fam]["spearman_semantic_only"] = spearman(
                [r["magnitude"] for r in sem], [r["drift"] for r in sem])
            summary[fam]["n_semantic"] = len(sem)

    out = {"run": run, "n_pairs": len(rows), "summary": summary, "pairs": rows}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"magnitude_{run}.json"
    out_path.write_text(json.dumps(out, indent=1))
    print(f"[done] {run}: {len(rows)} pairs -> {out_path}")
    for fam, s in summary.items():
        rho = s["spearman_mag_drift"]
        rho_s = f"{rho:.3f}" if rho is not None else "n/a"
        print(f"  {fam:<14} n={s['n']:<6} mean_drift={s['mean_drift']:.3f} rho(mag,drift)={rho_s}")
        for lvl, v in s["levels"].items():
            print(f"    {lvl:<18} n={v['n']:<5} drift={v['mean_drift']:.3f}")
    return out


def make_figure(runs: list[str]) -> None:
    """Presentation-family drift plateaus across the four main corpora."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from graphguard.viz import style as _S

    data = {}
    for run in runs:
        p = OUT_DIR / f"magnitude_{run}.json"
        if p.exists():
            data[run.split("__")[0]] = json.loads(p.read_text())
    if not data:
        return

    # Mean graph drift per presentation family, corpora on the x-axis (matching
    # the house layout). Confidence intervals cluster-bootstrap source
    # documents because one document contributes multiple perturbation pairs.

    def fam_stat(d, key):
        pairs = d.get("pairs", [])
        if key == "noop":
            selected = [p for p in pairs if p.get("level") == "noop"]
        elif key == "presentation":
            selected = [
                p for p in pairs
                if str(p.get("level", "")).startswith("pres-")
            ]
        elif key == "prompt":
            selected = [p for p in pairs if p.get("family") == "prompt"]
        else:  # evidence
            selected = [p for p in pairs if p.get("family") == "evidence"]
        if not selected:
            return 0.0, 0.0
        vals = [p["drift"] for p in selected]
        m = sum(vals) / len(vals)
        by_doc = defaultdict(list)
        for pair in selected:
            by_doc[pair["doc"]].append(pair["drift"])
        docs = sorted(by_doc)
        rng = np.random.default_rng(0)
        boot = []
        for _ in range(1000):
            sampled_docs = rng.choice(docs, size=len(docs), replace=True)
            sample = [
                value
                for doc in sampled_docs
                for value in by_doc[doc]
            ]
            boot.append(float(np.mean(sample)))
        lo, hi = np.quantile(boot, [0.025, 0.975])
        return m, (m - float(lo), float(hi) - m)

    _S.apply_rc(font_size=8)
    plt.rcParams.update({
        "axes.linewidth": 0.7,
        "axes.labelsize": 7.5,
        "axes.titlesize": 8,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
    })
    fig, ax = plt.subplots(figsize=(3.5, 1.22))

    fams = [("noop", "Resample"), ("presentation", "Schema"),
            ("prompt", "Prompt"), ("evidence", "Evidence")]
    fam_fill = [_S.BLUE, _S.PINK, _S.GREEN, _S.GRAY_LIGHT]
    fam_edge = [_S.BLUE_DARK, _S.PINK_DARK, _S.GREEN_DARK, _S.GRAY]
    short = {"docred": "DR", "redocred": "RDR", "scierc": "SE", "cdr": "CDR"}
    corpora = list(data.keys())
    x = np.arange(len(corpora))
    nb = len(fams)
    w = 0.76 / nb
    for j, (key, lab) in enumerate(fams):
        stats = [fam_stat(data[c], key) for c in corpora]
        vals = [s[0] for s in stats]
        errs = np.array([
            [s[1][0] for s in stats],
            [s[1][1] for s in stats],
        ])
        xs = x + (j - (nb - 1) / 2) * w
        bars = ax.bar(xs, vals, width=w * 0.9, color=fam_fill[j],
                      edgecolor=fam_edge[j], linewidth=0.8, label=lab,
                      yerr=errs,
                      error_kw=dict(ecolor=fam_edge[j], elinewidth=0.8,
                                    capsize=1.2))
        # Alternate the label height within each group so near-equal values do
        # not run together after the figure is scaled to one-column width.
        label_lift = 0.012 * (j % 2)
        for bar, v, e in zip(bars, vals, errs[1]):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    v + e + 0.012 + label_lift, f"{v:.2f}",
                    ha="center", va="bottom", fontsize=4.5, color=_S.BLACK)
    ax.set_xticks(x)
    ax.set_xticklabels([short.get(c, c) for c in corpora])
    ax.set_ylabel("Mean graph drift")
    ax.set_ylim(0, 0.84)
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8])
    ax.legend(ncol=4, frameon=False, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), handlelength=1.0,
              columnspacing=0.9, handletextpad=0.35)
    _S.despine(ax)
    ax.spines["left"].set_linewidth(0.7)
    ax.spines["bottom"].set_linewidth(0.7)

    out = ROOT / "assets" / "figures" / "fig_magnitude.png"
    fig.subplots_adjust(left=0.14, right=0.995, bottom=0.22, top=0.83)
    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.025,
                facecolor=_S.WHITE)
    plt.close(fig)
    print(f"[fig] {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=MAIN_RUNS)
    ap.add_argument("--no-fig", action="store_true")
    ap.add_argument("--fig-only", action="store_true",
                    help="Skip analysis; rebuild the figure from cached JSONs.")
    args = ap.parse_args()
    if not args.fig_only:
        for run in args.runs:
            analyze_run(run)
    if not args.no_fig:
        make_figure(args.runs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
