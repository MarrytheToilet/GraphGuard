"""GraphGuard viz (uses shared graphguard.viz.style for palette).

Outputs go to reports/runs/<run>/figures/ with figNN_<topic>.png naming.
A copy is mirrored to /viz/ for backward compatibility.
"""
from __future__ import annotations
import argparse, json, sqlite3, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from graphguard.viz import (
    PALETTE, PINK, PINK_DARK, BLUE, BLUE_DARK, GREEN, LAVENDER, PEACH, GRAY,
    BLACK, WHITE, LINESTYLES, MARKERS, apply_rc, save_fig, despine,
    annotate_bars,
)


apply_rc(font_size=11)


def save_png(fig, base: Path) -> None:
    """Backward-compat wrapper. base is a path *without* extension."""
    save_fig(fig, base.with_suffix(".png"))


def _two_color(n):
    return [PINK if i % 2 == 0 else BLUE for i in range(n)]


def viz_risk_distribution(conn, out: Path) -> None:
    rows = conn.execute(
        "SELECT risk_score, prompt_sensitivity, schema_sensitivity, stochastic_variance "
        "FROM edge_reliability_scores WHERE risk_score IS NOT NULL"
    ).fetchall()
    if not rows:
        return
    titles = ["Risk score", "Prompt sensitivity", "Schema sensitivity", "Stochastic variance"]
    colors = [PINK, BLUE, PINK, BLUE]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, idx, t, c in zip(axes.flat, range(4), titles, colors):
        vals = [r[idx] for r in rows if r[idx] is not None]
        ax.hist(vals, bins=20, color=c, edgecolor=BLACK, linewidth=1.0)
        ax.set_title(t, color=BLACK)
        ax.set_xlabel("value"); ax.set_ylabel("count")
        ax.grid(True, alpha=0.25, color=BLACK)
    fig.suptitle(f"Reliability score distributions  (n={len(rows)} edges)", color=BLACK,
                 fontweight="bold", fontsize=13)
    save_png(fig, out)


def viz_e2_pr(report: Path, out: Path) -> None:
    if not report.exists(): return
    d = json.loads(report.read_text())
    metrics = d.get("metrics", {})
    if not metrics: return
    keys = list(metrics.keys())
    auc = [metrics[k].get("auc_pr", 0) for k in keys]
    p5  = [metrics[k].get("p@5pct", 0) for k in keys]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    y = np.arange(len(keys))
    h = 0.4
    ax.barh(y - h/2, auc, h, color=PINK, edgecolor=BLACK, label="AUC-PR")
    ax.barh(y + h/2, p5, h, color=BLUE, edgecolor=BLACK, label="P@5%")
    for i, (a, p) in enumerate(zip(auc, p5)):
        ax.text(a + 0.005, i - h/2, f"{a:.3f}", va="center", color=BLACK, fontsize=9)
        ax.text(p + 0.005, i + h/2, f"{p:.3f}", va="center", color=BLACK, fontsize=9)
    ax.set_yticks(y); ax.set_yticklabels(keys)
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("score (higher is better)")
    ax.set_title(f"E2 — error detection by signal  "
                 f"(n_edges={d.get('n_edges')}, n_wrong={d.get('n_wrong')})")
    ax.legend(facecolor=WHITE, edgecolor=BLACK)
    ax.grid(True, alpha=0.25, axis="x", color=BLACK)
    save_png(fig, out)


def viz_e3_schema(report: Path, out: Path) -> None:
    if not report.exists(): return
    d = json.loads(report.read_text())
    fr = d.get("flip_rates") or d.get("flip_rates_by_variant") or {}
    if not fr: return

    metric_keys = ["type_flip_rate", "disappearance_rate",
                   "percent_downgraded_to_other", "percent_correct_to_wrong"]
    metric_labels = ["type flip", "disappearance", "→ other", "correct→wrong"]

    items = []
    for v, m in fr.items():
        vals = [float(m.get(k, 0) or 0) for k in metric_keys]
        items.append((v, vals, sum(vals)))
    items.sort(key=lambda r: -r[2])
    top = items[:18]
    names = [r[0] for r in top]
    M = np.array([r[1] for r in top])

    # Soft blue→pink sequential colormap from project palette.
    from matplotlib.colors import LinearSegmentedColormap
    blue_cmap = LinearSegmentedColormap.from_list(
        "cl_blue_pink", [WHITE, BLUE, PINK, PINK_DARK], N=256)

    fig_h = max(5.0, 0.5 * len(top) + 2.0)
    fig, ax = plt.subplots(figsize=(11.5, fig_h))
    im = ax.imshow(M, aspect="auto", cmap=blue_cmap, vmin=0, vmax=1)
    ax.set_xticks(range(len(metric_keys)))
    ax.set_xticklabels(metric_labels, fontsize=14)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=12)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i,j]:.2f}", ha="center", va="center",
                    fontsize=14,
                    color=BLACK if M[i,j] < 0.55 else WHITE,
                    fontweight="bold")
    ax.set_title("E3 — schema-induced distortion (top variants)", fontsize=16)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("rate", fontsize=12)
    cb.ax.tick_params(labelsize=11)
    save_png(fig, out)

    # Aggregated by intervention family (drop:* / ambiguous:* / coarse / ...)
    fam = {}
    for v, vals, _ in items:
        prefix = v.split(":")[0] if ":" in v else v
        fam.setdefault(prefix, []).append(vals)
    if len(fam) < 2:
        return
    # Filter out noisy single-variant families; keep them in a "low-n" annotation only.
    MIN_N = 2
    high_n = {f: vs for f, vs in fam.items() if len(vs) >= MIN_N}
    low_n = {f: vs for f, vs in fam.items() if len(vs) < MIN_N}
    if not high_n:
        # fallback: keep top-3 by sample size so the figure still renders
        high_n = dict(sorted(fam.items(), key=lambda kv: -len(kv[1]))[:3])
        low_n = {f: vs for f, vs in fam.items() if f not in high_n}
    fams = sorted(high_n.keys(), key=lambda f: -len(high_n[f]))
    means = np.array([np.mean(high_n[f], axis=0) for f in fams])
    stds  = np.array([np.std(high_n[f], axis=0)  for f in fams])
    counts = [len(high_n[f]) for f in fams]

    # Soft blue → pink sequential palette so families read as ordinal by sample size.
    from matplotlib.colors import LinearSegmentedColormap
    fam_cmap = LinearSegmentedColormap.from_list(
        "cl_fam", [BLUE, BLUE_DARK, PINK, PINK_DARK], N=max(3, len(fams)))
    colors = [fam_cmap(i / max(1, len(fams)-1)) for i in range(len(fams))]

    fig_w = max(8.0, 1.6 * len(metric_keys) + 0.8 * len(fams))
    fig2, ax2 = plt.subplots(figsize=(fig_w, 4.8))
    x = np.arange(len(metric_keys))
    w = 0.78 / max(1, len(fams))
    for i, f in enumerate(fams):
        offs = x + (i - (len(fams)-1)/2) * w
        bars = ax2.bar(offs, means[i], w, color=colors[i], edgecolor=BLACK,
                       linewidth=0.9,
                       label=f"{f} (n={counts[i]})",
                       yerr=stds[i], capsize=3,
                       error_kw={"ecolor": BLACK, "elinewidth": 0.7, "alpha": 0.7})
        for b, val in zip(bars, means[i]):
            ax2.text(b.get_x()+b.get_width()/2, b.get_height()+0.015,
                     f"{val:.2f}", ha="center", va="bottom",
                     fontsize=9, color=BLACK)
    ax2.set_xticks(x); ax2.set_xticklabels(metric_labels, fontsize=11)
    ax2.set_ylim(0, min(1.0, max(0.3, float(means.max() + stds.max()) * 1.20)))
    ax2.set_ylabel("mean rate (± 1σ)", fontsize=11)
    ax2.set_title("E3 — distortion by intervention family", fontsize=13)
    ax2.legend(facecolor=WHITE, edgecolor=BLACK, loc="upper right",
               fontsize=10, framealpha=0.95)
    ax2.grid(True, alpha=0.25, axis="y", color=BLACK, linestyle=":")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    if low_n:
        note = "low-n omitted: " + ", ".join(f"{f}(n={len(v)})" for f, v in sorted(low_n.items()))
        ax2.text(0.01, -0.18, note, transform=ax2.transAxes,
                 fontsize=8, color=GRAY, ha="left")
    fig2.tight_layout()
    save_png(fig2, out.with_name(out.name + "_by_family"))


def viz_e4(report: Path, out: Path) -> None:
    if not report.exists(): return
    data = json.loads(report.read_text())
    rows = data if isinstance(data, list) else (
        data.get("points") or data.get("rows") or data.get("results") or [])
    if not rows: return
    by = {}
    for r in rows:
        by.setdefault(r["planner"], []).append((r["budget"],
                                                 r.get("cause_recall_at_k", r.get("recall_at_k", 0))))
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    for i, (p, pts) in enumerate(sorted(by.items())):
        pts.sort()
        xs, ys = zip(*pts)
        c = PALETTE[i % len(PALETTE)]
        ls = LINESTYLES[i % len(LINESTYLES)]
        mk = MARKERS[i % len(MARKERS)]
        ax.plot(xs, ys, marker=mk, linestyle=ls, linewidth=1.8, markersize=6,
                color=c, markeredgecolor=BLACK, markeredgewidth=0.8, label=p)
    ax.set_xlabel("Budget (cf calls per edge)")
    ax.set_ylabel("Cause recall@k")
    ax.set_ylim(-0.02, 1.05)
    ax.set_title("E4 — cost-quality curve by planner")
    ax.legend(facecolor=WHITE, edgecolor=BLACK, loc="lower right", framealpha=0.95)
    ax.grid(True, alpha=0.25, color=BLACK)
    save_png(fig, out)


def viz_causal_attribution(conn, out: Path) -> None:
    rows = conn.execute("""
        SELECT ic.target_type, eo.outcome_type, COUNT(*) AS n
        FROM edge_outcomes eo
        JOIN counterfactual_runs cr ON eo.run_id = cr.run_id
        JOIN intervention_candidates ic ON cr.intervention_id = ic.intervention_id
        WHERE eo.outcome_type IN ('DISAPPEARED','TYPE_FLIP')
        GROUP BY ic.target_type, eo.outcome_type
    """).fetchall()
    if not rows: return
    targets = sorted({r[0] for r in rows})
    outcomes = ["DISAPPEARED", "TYPE_FLIP"]
    M = np.zeros((len(targets), len(outcomes)))
    for t, o, n in rows:
        M[targets.index(t), outcomes.index(o)] = n
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(targets)); w = 0.4
    ax.bar(x - w/2, M[:, 0], w, color=PINK, edgecolor=BLACK, label="DISAPPEARED")
    ax.bar(x + w/2, M[:, 1], w, color=BLUE, edgecolor=BLACK, label="TYPE_FLIP")
    for i, t in enumerate(targets):
        for j, val in enumerate(M[i]):
            ax.text(i + (j - 0.5) * w, val + 0.5, f"{int(val)}",
                    ha="center", color=BLACK, fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(targets)
    ax.set_ylabel("# observed outcomes")
    ax.set_title("Causal attribution — variable type → edge change")
    ax.legend(facecolor=WHITE, edgecolor=BLACK)
    ax.grid(True, alpha=0.25, axis="y", color=BLACK)
    save_png(fig, out)


def viz_extracted_graph_static(conn, doc_id: str, out: Path) -> None:
    """Single-doc static KG with auto-fit bbox labels.

    Improvements (2026-05-13):
      * widen layout scale so star outer nodes don't crowd text
      * larger font on outer nodes
      * truncate node labels to 18 chars (was 22) so bbox fits comfortably
      * limit edges to 40 (was 60) when graph is dense, prioritising risky edges
    """
    import networkx as nx
    from matplotlib.patches import FancyArrowPatch

    base_event = conn.execute("""
        SELECT ev.event_id FROM extraction_events ev
        WHERE ev.document_id = ?
          AND ev.event_id IN (SELECT base_event_id FROM counterfactual_runs)
        ORDER BY ev.created_at DESC LIMIT 1
    """, (doc_id,)).fetchone()
    if base_event is None:
        base_event = conn.execute("""
            SELECT ev.event_id FROM extraction_events ev
            WHERE ev.document_id = ?
              AND ev.prompt_id = 'base_v1' AND ev.schema_id = 'docred_full'
            ORDER BY ev.created_at DESC LIMIT 1
        """, (doc_id,)).fetchone()
    if base_event is None:
        return
    rows = conn.execute("""
        SELECT ee.subject_name, ee.relation, ee.object_name,
               COALESCE(s.risk_score, 0) AS risk
        FROM extracted_edges ee
        LEFT JOIN edge_reliability_scores s ON s.edge_id = ee.edge_id
        WHERE ee.event_id = ?
        ORDER BY risk DESC
        LIMIT 80
    """, (base_event[0],)).fetchall()
    if not rows:
        return

    def short(name: str, n: int = 18) -> str:
        name = (name or "").strip()
        return name if len(name) <= n else name[: n - 1] + "…"

    G = nx.DiGraph()
    edge_records = []
    for s, r, o, risk in rows:
        ss, oo = short(s), short(o)
        if ss == oo:
            continue
        G.add_edge(ss, oo)
        edge_records.append((ss, oo, r, risk))
        if len(edge_records) >= 40:
            break

    n_nodes = G.number_of_nodes()
    if n_nodes == 0:
        return

    deg = dict(G.degree())
    hub = max(deg, key=deg.get)
    hub_share = deg[hub] / max(1, n_nodes - 1)
    star_like = hub_share >= 0.5  # was: only-hub-connected — too strict, missed obvious stars

    # WIDER scale — was 0.85; now 1.4 so outer ring is far enough that node
    # bboxes don't collide with each other or the centre hub label.
    scale = 1.6 if n_nodes >= 10 else (1.4 if n_nodes >= 6 else 1.1)

    if star_like:
        # Manual angular layout: hub at centre, outer nodes evenly spaced; nodes
        # with no edge to hub get pushed slightly inward to break ties.
        outer = [n for n in G.nodes() if n != hub]
        outer.sort(key=lambda n: (-int(G.has_edge(hub, n) or G.has_edge(n, hub)), n))
        pos = {hub: (0.0, 0.0)}
        n_outer = len(outer)
        # Use a slightly bigger ring for many-node stars.
        radius = scale * (1.0 + 0.04 * max(0, n_outer - 8))
        import math
        for i, n in enumerate(outer):
            theta = 2 * math.pi * i / max(1, n_outer) + math.pi / 6
            r = radius * (1.0 if (G.has_edge(hub, n) or G.has_edge(n, hub)) else 0.78)
            pos[n] = (r * math.cos(theta), r * math.sin(theta))
    else:
        try:
            pos = nx.kamada_kawai_layout(G, scale=scale)
        except Exception:
            pos = nx.spring_layout(G, seed=7,
                                   k=2.2 / max(1, n_nodes ** 0.5),
                                   iterations=500)

    # Bigger figure so labels can breathe.
    fig_w = max(11.0, min(18.0, 8.0 + n_nodes * 0.45))
    fig_h = fig_w * 0.74
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Larger node fonts.
    node_font = 13 if n_nodes <= 8 else (12 if n_nodes <= 14 else 11)
    node_text_artists = {}
    for n, (x, y) in pos.items():
        is_hub = star_like and n == hub
        t = ax.text(
            x, y, n,
            ha="center", va="center",
            fontsize=node_font + (2 if is_hub else 0),
            fontweight="bold", color=BLACK, zorder=4,
            bbox=dict(
                boxstyle="round,pad=0.7,rounding_size=0.5",
                facecolor=PINK if is_hub else BLUE,
                edgecolor=BLACK, linewidth=1.0,
            ),
        )
        node_text_artists[n] = t

    edge_label_font = 10 if n_nodes <= 8 else (9 if n_nodes <= 14 else 8)
    seen_pair = {}
    for s, o, rel, risk in edge_records:
        color = PINK_DARK if (risk or 0) >= 1.0 else BLUE_DARK
        key = (s, o)
        seen_pair[key] = seen_pair.get(key, 0) + 1
        rad = 0.20 * (seen_pair[key] - 1) if seen_pair[key] > 1 else 0.13
        patch = FancyArrowPatch(
            posA=pos[s], posB=pos[o],
            arrowstyle="-|>", mutation_scale=16,
            color=color, linewidth=1.7,
            connectionstyle=f"arc3,rad={rad}",
            patchA=node_text_artists[s].get_bbox_patch(),
            patchB=node_text_artists[o].get_bbox_patch(),
            shrinkA=2, shrinkB=2, zorder=2,
        )
        ax.add_patch(patch)

        mx, my = (pos[s][0] + pos[o][0]) / 2, (pos[s][1] + pos[o][1]) / 2
        dx, dy = pos[o][0] - pos[s][0], pos[o][1] - pos[s][1]
        norm = (dx * dx + dy * dy) ** 0.5 or 1.0
        off = 0.06 * (1 if seen_pair[key] % 2 else -1)
        lx = mx + (-dy / norm) * off
        ly = my + (dx / norm) * off
        ax.text(
            lx, ly, rel,
            ha="center", va="center",
            fontsize=edge_label_font, color=BLACK, zorder=3,
            bbox=dict(facecolor=WHITE, edgecolor=color,
                      boxstyle="round,pad=0.22", alpha=0.95, linewidth=0.7),
        )

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    pad_x = (max(xs) - min(xs) or 1.0) * 0.20
    pad_y = (max(ys) - min(ys) or 1.0) * 0.22
    ax.set_xlim(min(xs) - pad_x, max(xs) + pad_x)
    ax.set_ylim(min(ys) - pad_y, max(ys) + pad_y)
    ax.set_aspect("equal")

    title = doc_id if len(doc_id) < 70 else doc_id[:67] + "…"
    ax.set_title(
        f"Extracted KG  ·  {title}\n"
        f"pink hub = highest-degree entity   ·   pink edge = risk_score ≥ 1.0",
        fontsize=10,
    )
    ax.axis("off")
    save_png(fig, out)


def viz_e6(report: Path, out: Path) -> None:
    if not report.exists():
        return
    d = json.loads(report.read_text())
    s = d.get("summary", {})
    by_q = s.get("by_query", {}) or d.get("queries", {})
    by_qf = s.get("by_query_family", {})
    if not by_q:
        return
    qnames = list(by_q.keys())
    # parse families from by_query_family keys "Q|fam"
    fams = sorted({k.split("|", 1)[1] for k in by_qf.keys() if "|" in k})
    fig_w = max(8.5, 1.4 * max(1, len(fams)) + 0.9 * len(qnames))
    fig, ax = plt.subplots(figsize=(min(14, fig_w), 4.8))
    if fams:
        width = 0.78 / max(1, len(fams))
        x = np.arange(len(qnames))
        for i, fam in enumerate(fams):
            vals = [by_qf.get(f"{q}|{fam}", {}).get("mean_jaccard", 0) for q in qnames]
            ax.bar(x + i * width, vals, width,
                   color=PALETTE[i % len(PALETTE)],
                   edgecolor=BLACK, linewidth=0.5,
                   label=fam)
        ax.set_xticks(x + width * (len(fams) - 1) / 2)
        ax.set_xticklabels(qnames, rotation=15, ha="right")
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5),
                  fontsize=9, framealpha=0.95, borderaxespad=0.0)
    else:
        x = np.arange(len(qnames))
        ax.bar(x, [by_q[q].get("mean_jaccard", 0) for q in qnames],
               color=BLUE, edgecolor=BLACK, linewidth=0.5)
        ax.set_xticks(x); ax.set_xticklabels(qnames, rotation=15, ha="right")
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Mean answer Jaccard (cf vs base)")
    ax.set_title("E6 — graph-query stability under configuration drift")
    ax.grid(True, axis="y", alpha=0.25, color=GRAY, linestyle=":")
    despine(ax)
    save_png(fig, out)


def viz_e7(report: Path, out: Path) -> None:
    if not report.exists():
        return
    d = json.loads(report.read_text())
    rows = []
    for r in d.get("split_candidates", []):
        rows.append({"action": "split", "label": f"split: {r.get('relation','?')} → {r.get('top_flip_target','?')}", "score": r.get("share", 0)})
    for r in d.get("merge_candidates", []):
        rows.append({"action": "merge", "label": f"merge: {r.get('relation_a','?')} ↔ {r.get('relation_b','?')}",
                     "score": (r.get("share_a_to_b", 0) + r.get("share_b_to_a", 0)) / 2})
    for r in d.get("describe_candidates", []):
        rows.append({"action": "describe", "label": f"describe: {r.get('relation','?')}", "score": r.get("disappearance_share", 0)})
    rows = rows[:12]
    if not rows:
        return
    colors = [PALETTE[2] if r["action"] == "split" else (PALETTE[3] if r["action"] == "merge" else PALETTE[4]) for r in rows]
    fig, ax = plt.subplots(figsize=(7, max(3, 0.35 * len(rows) + 1)))
    y = np.arange(len(rows))
    ax.barh(y, [r["score"] for r in rows], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels([r["label"] for r in rows], fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Confusion / disappearance share")
    ax.set_title("E7 schema-redesign candidates")
    save_png(fig, out)


def viz_e5(report: Path, out: Path) -> None:
    if not report.exists():
        return
    d = json.loads(report.read_text())
    s = d.get("summary", {})
    docs = d.get("per_document", [])
    if not docs:
        return
    spear = np.array([float(r.get("spearman") or 0) for r in docs])
    lift  = np.array([float(r.get("effect_lift") or 0) for r in docs])

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6),
                             gridspec_kw={"width_ratios": [1.05, 1.0]})
    ax_h, ax_s = axes

    # ---- left: paired histograms ----
    bins = np.linspace(-1.0, 1.0, 21)
    ax_h.hist(spear, bins=bins, color=BLUE, edgecolor=BLACK, linewidth=0.5,
              alpha=0.85, label=f"Spearman  μ={spear.mean():+.2f}")
    ax_h.hist(lift,  bins=bins, color=PINK, edgecolor=BLACK, linewidth=0.5,
              alpha=0.75, label=f"Effect lift  μ={lift.mean():+.2f}")
    ax_h.axvline(0,            color=GRAY,      ls="-",  lw=0.8)
    ax_h.axvline(spear.mean(), color=BLUE_DARK, ls="--", lw=1.6)
    ax_h.axvline(lift.mean(),  color=PINK_DARK, ls="--", lw=1.6)
    ax_h.set_xlabel("Per-document score")
    ax_h.set_ylabel("# documents")
    ax_h.set_title(f"Distribution across {len(docs)} docs")
    ax_h.legend(loc="upper left", framealpha=0.95)
    ax_h.grid(True, axis="y", alpha=0.25, color=GRAY, linestyle=":")
    despine(ax_h)

    # ---- right: scatter Spearman vs Effect lift ----
    ax_s.axhline(0, color=GRAY, lw=0.6)
    ax_s.axvline(0, color=GRAY, lw=0.6)
    ax_s.scatter(spear, lift, s=28, color=PINK_DARK,
                 alpha=0.65, edgecolors=BLACK, linewidths=0.4)
    if len(spear) >= 2 and spear.std() > 1e-6 and lift.std() > 1e-6:
        rho = float(np.corrcoef(spear, lift)[0, 1])
        m, b = np.polyfit(spear, lift, 1)
        xs = np.linspace(spear.min(), spear.max(), 50)
        ax_s.plot(xs, m * xs + b, color=BLUE_DARK, lw=1.6, ls="--",
                  label=f"linear fit (r={rho:+.2f})")
        ax_s.legend(loc="upper left", framealpha=0.95)
    ax_s.set_xlim(-1.05, 1.05)
    ax_s.set_xlabel("Spearman correlation")
    ax_s.set_ylabel("Held-out effect lift")
    ax_s.set_title("Per-doc faithfulness")
    ax_s.grid(True, alpha=0.25, color=GRAY, linestyle=":")
    despine(ax_s)

    fig.suptitle(
        f"E5 — Held-out attribution faithfulness   ·   "
        f"Spearman μ={s.get('spearman_mean',0):+.2f}   ·   "
        f"Effect lift μ={s.get('effect_lift_mean',0):+.2f}",
        fontsize=13, fontweight="bold", y=1.02,
    )
    save_png(fig, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/processed/docred.db")
    ap.add_argument("--out", default=None,
                    help="(deprecated) ignored — figures always go to --figures-dir")
    ap.add_argument("--figures-dir", required=True,
                    help="canonical figures directory; figNN_*.png go here")
    ap.add_argument("--reports-dir", default="data/processed")
    ap.add_argument("--n-graphs", type=int, default=3)
    args = ap.parse_args()

    figdir = Path(args.figures_dir)
    figdir.mkdir(parents=True, exist_ok=True)
    fig_cases = figdir / "cases"; fig_cases.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    rd = Path(args.reports_dir)

    # (target_path_no_suffix, fn, json_or_None)
    plan = [
        (figdir / "fig09_risk_distribution",            viz_risk_distribution,  None),
        (figdir / "fig08_error_detection",              viz_e2_pr,              rd / "e2_report.json"),
        (figdir / "fig04_schema_distortion",            viz_e3_schema,          rd / "e3_report.json"),
        (figdir / "fig05_cost_quality",                 viz_e4,                 rd / "e4_report.json"),
        (figdir / "fig06_faithfulness",                 viz_e5,                 rd / "e5_faithfulness.json"),
        (figdir / "fig07_query_stability",              viz_e6,                 rd / "e6_query_stability.json"),
        (figdir / "fig10_schema_redesign",              viz_e7,                 rd / "e7_schema_redesign.json"),
        (figdir / "fig11_causal_attribution",           viz_causal_attribution, None),
    ]
    for newp, fn, j in plan:
        try:
            if j is None:
                fn(conn, newp)
            else:
                fn(j, newp)
            # E3 also writes a *_by_family.png variant — rename it for consistency
            bf = newp.with_name(newp.name + "_by_family.png")
            if bf.exists():
                bf.rename(figdir / "fig04b_schema_distortion_by_family.png")
        except Exception as e:
            print(f"  [warn] {fn.__name__} failed: {e}")

    docs = [r[0] for r in conn.execute("""
        SELECT ev.document_id FROM extraction_events ev
        JOIN extracted_edges ee ON ee.event_id = ev.event_id
        WHERE ev.event_id IN (SELECT base_event_id FROM counterfactual_runs)
        GROUP BY ev.document_id ORDER BY COUNT(*) DESC LIMIT ?
    """, (args.n_graphs,)).fetchall()]
    for d in docs:
        safe = d.replace("/", "_")[:60]
        viz_extracted_graph_static(conn, d, fig_cases / f"kg_{safe}")
    print(f"[done] figures={figdir}")


if __name__ == "__main__":
    main()
