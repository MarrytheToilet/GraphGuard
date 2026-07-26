"""Regenerate the seven paper figures owned by this script.

Reads from existing report artefacts (no extraction re-run) and writes
PNGs into assets/figures/ with friendly labels, larger fonts, and
consistent palette.  Replaces the ad-hoc generators that leaked variable
names (run IDs, family slugs, P-codes) into the camera-ready figures.

Inputs (relative to repo root):
  reports/cross_run/cross_run_summary.json      (per-run violation rates)
  reports/cross_run/amp_ci.json                 (canonical D1--D5 Amp CIs)
  reports/cross_run/strict_vs_soft_<run>.json    (stability buckets)
  reports/cross_run/reproducibility_manifest.json (cached D0 noise floors)
  reports/cross_run/deployment_evidence.json and its registered
      deterministic gzip transports                   (RQ8--RQ10 pairs)

Outputs (assets/figures/):
  fig_crossrun_violations.png   contract violation rates run x contract
  fig_amp_crossrun.png          diagnostic amplification consistency
  fig_strict_vs_soft.png        strict vs soft perturbation comparison
  fig_calibration.png           harmful-edge calibration
  fig_noise_floor.png           noise-floor across corpora
  fig_2d_sensitivity.png        2-D threshold sweep
  fig_auroc.png                 ROC / PR curves

Run from repo root:
  python scripts/make_paper_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from graphguard.deployment_evidence import load_kuzu_evidence

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ---------- palette --------------------------------------------------------

PINK       = "#F4A6B8"
PINK_DARK  = "#C8607C"
BLUE       = "#9DC8E0"
BLUE_DARK  = "#3A82B0"
GREEN      = "#9FD3AC"
GREEN_DARK = "#3D8A5A"
LAVENDER   = "#B8A7D9"
PEACH      = "#F4B98A"
YELLOW     = "#F4D86A"
GRAY       = "#7E848C"
GRAY_LIGHT = "#D6D9DD"
BLACK      = "#1F1F23"

PALETTE_FAMILIES = {
    "Schema variant":   PINK_DARK,
    "Prompt rewording": BLUE_DARK,
    "Evidence reorder": GREEN_DARK,
    "Entity alias":     LAVENDER,
    "Decoding seed":    PEACH,
}

# ---------- friendly label maps -------------------------------------------

RUN_LABEL = {
    "docred__deepseek-v4-flash__300d":   "DocRED\n(DeepSeek-V4-Flash · 300d)",
    "redocred__deepseek-v4-flash__300d": "Re-DocRED\n(DeepSeek-V4-Flash · 300d)",
    "cdr__deepseek-v4-flash__300d":      "BC5CDR\n(DeepSeek-V4-Flash · 300d)",
    "scierc__deepseek-v4-flash__100d":    "SciERC\n(DeepSeek-V4-Flash · 100d)",
    "docred__glm-5__100d":               "DocRED\n(GLM-5 · 100d)",
    "docred__kimi-k2__100d":             "DocRED\n(Kimi-K2 · 100d)",
    "docred__qwen3-32b__100d":           "DocRED\n(Qwen3-32B · 100d)",
}

# Order tuned so primary, cross-domain, then cross-model cluster predictably.
RUN_ORDER = [
    "docred__deepseek-v4-flash__300d", "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d", "cdr__deepseek-v4-flash__300d",
    "docred__glm-5__100d",
    "docred__kimi-k2__100d", "docred__qwen3-32b__100d",
]

QUERY_LABEL = {
    "diagnostic.edge_identity": "D1 edge identity",
    "diagnostic.two_hop_endpoints": "D2 2-hop endpoints",
    "diagnostic.fanout_join": "D3 fan-out join",
    "diagnostic.top_undirected_degree": "D4 top degree",
    "diagnostic.short_connectivity": "D5 short connectivity",
}

FAMILY_LABEL = {
    "schema":       "Schema variant",
    "prompt":       "Prompt rewording",
    "evidence":     "Evidence reorder",
    "entity_alias": "Entity alias",
    "stochastic":   "Decoding seed",
}

CONTRACT_ORDER = ["K1", "K1b", "K1c", "K2", "K3", "K4", "K5", "K6"]
CONTRACT_TITLE = {  # short label suitable for axis ticks
    "K1":  "K1",
    "K1b": "K1b",
    "K1c": "K1c",
    "K2":  "K2",
    "K3":  "K3",
    "K4":  "K4",
    "K5":  "K5",
    "K6":  "K6",
}

# Schema perturbation classes shown in fig_schema.
SCHEMA_CLASSES = [
    ("rename",       "Rename"),
    ("reorder",      "Reorder"),
    ("desc_added",   "Description added"),
    ("desc_removed", "Description removed"),
    ("with_other",   "OTHER class added"),
    ("hierarchical", "Hierarchical"),
    ("coarse",       "Coarse"),
    ("ambiguous",    "Ambiguous (mean)"),
    ("drop",         "Drop label (mean)"),
]

CANONICAL_RUN = "docred__deepseek-v4-flash__300d"

# ---------- shared style ---------------------------------------------------

def apply_style(base: int = 16) -> None:
    plt.rcParams.update({
        "axes.facecolor":   "white",
        "figure.facecolor": "white",
        "axes.edgecolor":   BLACK,
        "axes.labelcolor":  BLACK,
        "axes.titlecolor":  BLACK,
        "axes.titleweight": "normal",
        "xtick.color":      BLACK,
        "ytick.color":      BLACK,
        "text.color":       BLACK,
        "font.family":      ["DejaVu Sans"],
        "font.size":        base,
        "axes.titlesize":   base + 2,
        "axes.labelsize":   base,
        "xtick.labelsize":  base - 1,
        "ytick.labelsize":  base - 1,
        "legend.fontsize":  base - 1,
        "legend.frameon":   True,
        "legend.facecolor": "white",
        "legend.edgecolor": GRAY_LIGHT,
        "axes.spines.top":   False,
        "axes.spines.right": False,
    })


def save(fig, name: str) -> None:
    p = OUT / name
    fig.tight_layout()
    fig.savefig(p, dpi=200, bbox_inches="tight", pad_inches=0.025,
                facecolor="white")
    plt.close(fig)
    print(f"  wrote {p.relative_to(ROOT)}")


def load(rel: str):
    p = ROOT / rel
    with open(p) as f:
        return json.load(f)

# ---------- figures --------------------------------------------------------


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Regenerate the paper figures used in main.tex.")
    parser.add_argument(
        "target", nargs="?", default="all",
        choices=["all", "contracts", "evaluation"],
        help="Which figure pack to (re)build (default: all).")
    args = parser.parse_args()

    if args.target in ("all", "contracts"):
        make_crossrun_violations()
        make_amp_crossrun()
        make_strict_vs_soft()
    if args.target in ("all", "evaluation"):
        make_noise_floor_figure()
        make_calibration_figure()
        make_2d_sensitivity_figure()
        make_auroc_figure()


# ===========================================================================
# Replacement figures for paper tables
# Contract-result figures
# ===========================================================================

from graphguard.viz import style as _S  # noqa: E402


def make_crossrun_violations() -> None:
    _S.apply_rc(font_size=9)
    j = json.loads((ROOT / "reports/cross_run/cross_run_summary.json").read_text())
    order = [
        ("DocRED · DSV4-Flash",   "docred__deepseek-v4-flash__300d"),
        ("Re-DocRED · DSV4-Flash", "redocred__deepseek-v4-flash__300d"),
        ("SciERC · DSV4-Flash",   "scierc__deepseek-v4-flash__100d"),
        ("BC5CDR · DSV4-Flash",   "cdr__deepseek-v4-flash__300d"),
        ("DocRED · GLM-5",        "docred__glm-5__100d"),
        ("DocRED · Kimi-K2",      "docred__kimi-k2__100d"),
        ("DocRED · Qwen3-32B",    "docred__qwen3-32b__100d"),
    ]
    # After contract renumber, internal DB IDs already match the paper's IDs.
    key_map = [
        ("K1", "K1"), ("K1b", "K1b"), ("K1c", "K1c"),
        ("K2", "K2"), ("K3", "K3"),
        ("K4", "K4"),
        ("K6", "K6"),
    ]
    db_keys = [k for k, _ in key_map]
    disp = [d for _, d in key_map]
    by_name = {r["name"]: r for r in j["runs"]}

    def paper_violation_rate(run_name: str, db_key: str) -> float:
        # Read directly from the cross-run summary so the figure, result table,
        # and prose use the same catalogue thresholds and source of truth.
        return float(by_name[run_name]["contracts"][db_key]["violation_rate"])

    mat = np.zeros((len(db_keys), len(order)))   # transposed: rows=contracts
    for j_, (_, name) in enumerate(order):
        for i_, k in enumerate(db_keys):
            mat[i_, j_] = paper_violation_rate(name, k)

    # Short, horizontal-friendly run labels.
    short_runs = ["DR\nDSV4", "RDR\nDSV4", "SE\nDSV4", "CDR\nDSV4",
                  "DR\nGLM5", "DR\nKimi", "DR\nQwen3"]

    fig, ax = plt.subplots(figsize=(3.5, 1.64))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list(
        "ggblues", [_S.WHITE, _S.BLUE, _S.BLUE_DARK, "#1F4F70"])
    im = ax.imshow(mat, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(short_runs, fontsize=6.5)
    ax.set_yticks(range(len(disp)))
    ax.set_yticklabels(disp, fontsize=8)
    for i in range(mat.shape[0]):
        for jj in range(mat.shape[1]):
            v = mat[i, jj]
            ax.text(jj, i, f"{v:.2f}", ha="center", va="center",
                    fontsize=6.6,
                    color=_S.BLACK if v < 0.55 else _S.WHITE)
    cbar = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cbar.set_label("violation rate", fontsize=7)
    cbar.ax.tick_params(labelsize=6.5)
    ax.set_title("Cross-run contract violation rates", fontsize=9)
    _S.save_fig(fig, OUT / "fig_crossrun_violations.png")


def make_amp_crossrun() -> None:
    _S.apply_rc(font_size=8)
    specs = [
        ("docred__deepseek-v4-flash__300d", "DocRED", "DSV4"),
        ("docred__glm-5__100d", "DocRED", "GLM-5"),
        ("docred__kimi-k2__100d", "DocRED", "Kimi"),
        ("docred__qwen3-32b__100d", "DocRED", "Qwen3"),
        ("redocred__deepseek-v4-flash__300d", "Re-DocRED", "DSV4"),
        ("scierc__deepseek-v4-flash__100d", "SciERC", "DSV4"),
        ("cdr__deepseek-v4-flash__300d", "BC5CDR", "DSV4"),
    ]
    amp = load("reports/cross_run/amp_ci.json")["runs"]
    rows = []
    for run, corpus, model in specs:
        d1_row = amp[run]["diagnostic.edge_identity"]
        d3_row = amp[run]["diagnostic.fanout_join"]
        rows.append((
            corpus,
            model,
            d1_row["amp_mean"],
            d3_row["amp_mean"],
            d3_row["amp_ci_lo"],
            d3_row["amp_ci_hi"],
        ))
    corpora = [r[0] for r in rows]
    models = [r[1] for r in rows]
    d1 = [r[2] for r in rows]
    d3 = [r[3] for r in rows]
    err_lo = [r[3] - r[4] for r in rows]
    err_hi = [r[5] - r[3] for r in rows]
    x = np.arange(len(rows))
    w = 0.38

    fig, ax = plt.subplots(figsize=(3.5, 1.27))
    b1 = ax.bar(x - w/2, d1, w, color=_S.BLUE, edgecolor=_S.BLUE_DARK,
                linewidth=0.8, label=r"$D_1$ (edge identity)")
    b2 = ax.bar(x + w/2, d3, w, color=_S.PINK, edgecolor=_S.PINK_DARK,
                linewidth=0.8,
                yerr=[err_lo, err_hi], capsize=2,
                error_kw=dict(ecolor=_S.PINK_DARK, lw=0.8),
                label=r"$D_3$ (fan-out join, 95% CI)")
    ax.axhline(1.0, ls="--", lw=0.6, color=_S.GRAY, zorder=0)
    ax.set_xticks(x)
    short_corpora = {"DocRED": "DR", "Re-DocRED": "RDR", "SciERC": "SE", "BC5CDR": "CDR"}
    ax.set_xticklabels([f"{m}\n{short_corpora.get(c,c)}" for c, m in zip(corpora, models)],
                       rotation=0, ha="center", fontsize=6)
    boundaries = []
    for i in range(1, len(rows)):
        if corpora[i] != corpora[i - 1]:
            boundaries.append(i - 0.5)
    for bx in boundaries:
        ax.axvline(bx, color=_S.GRAY_LIGHT, lw=0.6, ls=":", zorder=0)
    y_top = 1.75
    ax.set_ylim(0, y_top)
    ax.set_ylabel(r"$\overline{\mathrm{Amp}}$", fontsize=9)
    ax.tick_params(axis="y", labelsize=7)
    fig.legend([b1, b2],
               [r"$D_1$ (edge identity)",
                r"$D_3$ (fan-out join, 95% CI)"],
               loc="lower center", ncol=2, fontsize=7, frameon=False,
               bbox_to_anchor=(0.5, -0.14))
    _S.despine(ax)
    for rect, v in zip(b1, d1):
        label_y = 1.04 if 0.87 <= v <= 1.0 else rect.get_height() + 0.04
        ax.text(rect.get_x() + rect.get_width() / 2,
                label_y, f"{v:.2f}",
                ha="center", va="bottom", fontsize=5.5, color=_S.BLACK)
    for rect, v, hi in zip(b2, d3, [r[5] for r in rows]):
        ax.text(rect.get_x() + rect.get_width() / 2,
                hi + 0.05, f"{v:.2f}",
                ha="center", va="bottom", fontsize=5.5, color=_S.BLACK)
    _S.save_fig(fig, OUT / "fig_amp_crossrun.png")


def make_strict_vs_soft() -> None:
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
    REP = ROOT / "reports" / "cross_run"
    runs = {"DocRED": "docred__deepseek-v4-flash__300d",
            "Re-DocRED": "redocred__deepseek-v4-flash__300d",
            "SciERC": "scierc__deepseek-v4-flash__100d",
            "BC5CDR": "cdr__deepseek-v4-flash__300d"}
    order = ["strict", "soft", "ablation"]  # L1 / L2 / L3
    rows, rows_h, ns = {}, {}, {}
    for name, run in runs.items():
        b = json.loads((REP / f"strict_vs_soft_{run}.json").read_text())["buckets"]
        rows[name]   = tuple(b[o]["violation_rate_tau0p5"] for o in order)
        rows_h[name] = tuple(
            b[o]["query_divergence_rate"] for o in order
        )
        ns[name]     = tuple(b[o]["n_pairs"] for o in order)

    def ci(p, n):
        return 1.96 * float(np.sqrt(p * (1 - p) / n)) if n else 0.0

    labels = list(rows.keys())
    x = np.arange(len(labels))
    w = 0.25
    fills = [_S.BLUE, _S.PINK, _S.GREEN]
    edges = [_S.BLUE_DARK, _S.PINK_DARK, _S.GREEN_DARK]
    fig, axes = plt.subplots(2, 1, figsize=(3.5, 2.12), sharex=True,
                             gridspec_kw={"hspace": 0.34})

    def plot_one(ax, data, title):
        for k in range(3):
            vals = [data[l][k] for l in labels]
            errs = [ci(data[l][k], ns[l][k]) for l in labels]
            xs = x + (k - 1) * w
            ax.bar(xs, vals, w, color=fills[k], edgecolor=edges[k],
                   linewidth=0.8, label=f"L{k+1}", yerr=errs,
                   error_kw=dict(ecolor=edges[k], elinewidth=0.8, capsize=1.2))
            label_lift = 0.012 * (k % 2)
            for xi, v, e in zip(xs, vals, errs):
                ax.text(xi, v + e + 0.014 + label_lift, f"{v:.2f}",
                        ha="center", va="bottom", fontsize=5.0,
                        color=_S.BLACK)
        ax.set_ylabel("Rate")
        ax.set_title(title, loc="left", pad=3)
        ax.set_ylim(0, 1.08)
        ax.set_yticks([0, 0.5, 1.0])
        _S.despine(ax)
        ax.spines["left"].set_linewidth(0.7)
        ax.spines["bottom"].set_linewidth(0.7)

    plot_one(axes[0], rows,   r"Violation rate ($\tau=0.5$)")
    plot_one(axes[1], rows_h, "Query divergence")
    short_lbl = {"DocRED":"DR","Re-DocRED":"RDR","SciERC":"SE","BC5CDR":"CDR"}
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([short_lbl.get(l, l) for l in labels])

    from matplotlib.patches import Patch
    fig.legend(
        [Patch(facecolor=fill, edgecolor=edge, linewidth=0.8)
         for fill, edge in zip(fills, edges)],
        ["L1", "L2", "L3"],
        loc="upper right", bbox_to_anchor=(0.99, 0.995), ncol=3,
        frameon=False, handlelength=1.0, columnspacing=0.8,
        handletextpad=0.35,
    )
    fig.subplots_adjust(left=0.14, right=0.995, bottom=0.13, top=0.91)
    out = OUT / "fig_strict_vs_soft.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.025,
                facecolor=_S.WHITE)
    plt.close(fig)
    print(f"  wrote {out}")




# ===========================================================================
# Evaluation artifacts
# Threshold calibration, noise-floor, 2-D sensitivity, AUROC/AUPRC, equiv-table.
# ===========================================================================
import matplotlib.colors as mcolors
from sklearn.metrics import roc_curve, precision_recall_curve, auc, roc_auc_score

# Shared evaluation palette
_BLUE        = _S.BLUE_DARK
_BLUE_LIGHT  = _S.BLUE
_PINK        = _S.PINK_DARK
_PINK_LIGHT  = _S.PINK
_GREEN       = _S.GREEN_DARK
_GREEN_LIGHT = _S.GREEN
_LAV         = "#9F86C0"
_PEACH       = "#E89B6A"
_GRAY        = _S.GRAY
_GRAY_LIGHT  = _S.GRAY_LIGHT
_BLACK       = _S.BLACK

REPORTS  = ROOT / "reports" / "cross_run"
FIG_DIR  = ROOT / "assets" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TAU_GRAPH_DEFAULT = 0.45
TAU_QUERY_DEFAULT = 0.70

CORPORA = [
    ("docred__deepseek-v4-flash__300d", "DocRED"),
    ("redocred__deepseek-v4-flash__300d", "Re-DocRED"),
    ("scierc__deepseek-v4-flash__100d", "SciERC"),
    ("cdr__deepseek-v4-flash__300d", "BC5CDR"),
]

# ──────────────────────────────────────────────────────────────────────────────

def load_pairs(tag: str) -> list[dict]:
    artifact = load_kuzu_evidence(ROOT, tag)
    return [
        {
            **record,
            "doc": record["document_id"],
            "family": record["cause_family"],
            "mean_df1": record["mean_delta_f1_abs"],
            "harmful": record["mean_delta_f1_signed"] > 0.05,
        }
        for record in artifact["per_pair"]
    ]


def compute_calibration(pairs: list[dict], score_key: str = "graph_drift",
                        harm_eps: float = 0.05):
    """Sweep τ over score_key; return lists of (tau, coverage, harm_rate)."""
    scores = np.array([p[score_key] for p in pairs])
    labels = np.array([int(p["harmful"]) for p in pairs])
    taus = np.linspace(0.0, 1.0, 201)
    coverage, harm_rate = [], []
    for tau in taus:
        published = scores < tau  # fixed gate blocks score >= threshold
        n_pub = published.sum()
        n_harmful_pub = (published & (labels == 1)).sum()
        coverage.append(n_pub / max(len(pairs), 1))
        harm_rate.append(n_harmful_pub / max(n_pub, 1))
    return taus, np.array(coverage), np.array(harm_rate)


def noise_floor_from_cache(corpus: str) -> float:
    """Return D0 drift from the canonical lineage summary.

    ``build_reproducibility_manifest.py`` derives the cached overlap from the
    four primary SQLite ``stability_reports`` tables.  Reading that frozen
    value here keeps the submitted figure reproducible without local DBs.
    """
    manifest = load("reports/cross_run/reproducibility_manifest.json")
    overlap = manifest["raw_stability"][corpus]["avg_edge_overlap"]
    return 1.0 - float(overlap)


# ──────────────────────────────────────────────────────────────────────────────
# W2: Calibration figure – τ* at SLA ε
# ──────────────────────────────────────────────────────────────────────────────

def make_calibration_figure():
    # Native single-column canvas (like fig_riskcoverage): fonts render ~1:1.
    _S.apply_rc(font_size=7)
    fig, axes = plt.subplots(1, 4, figsize=(3.5, 0.68), sharey=True,
                             gridspec_kw={"wspace": 0.20})
    eps = 0.05  # SLA: <=5% harmful publication rate

    blue_line = _BLUE
    red_line  = _PINK
    gray_fill = _BLUE_LIGHT
    green     = _GREEN

    for ax, (tag, name) in zip(axes, CORPORA):
        pairs = load_pairs(tag)
        taus, cov, harm = compute_calibration(pairs, score_key="graph_drift")

        feasible = np.where(harm <= eps)[0]
        if len(feasible):
            tau_star = taus[feasible[-1]]
        else:
            tau_star = None

        ax.fill_between(taus, cov, alpha=0.25, color=gray_fill)
        ax.plot(taus, cov, color=blue_line, lw=1.1, label="Coverage")
        ax.plot(taus, harm, color=red_line, lw=1.1, ls="--", label="Pub. harm")
        ax.axhline(eps, color=red_line, lw=0.7, ls=":", alpha=0.7)
        if tau_star is not None:
            ax.axvline(tau_star, color=green, lw=1.1, ls="-.")
            ax.text(min(tau_star + 0.06, 0.62), 0.9,
                    rf"$\tau^*$={tau_star:.2f}",
                    fontsize=6.5, color=green)
        else:
            ax.text(0.55, 0.45, "infeasible",
                    ha="center", va="center", fontsize=6.5,
                    color=red_line,
                    transform=ax.transAxes)

        ax.set_xlim(0, 1)
        ax.set_ylim(-0.02, 1.08)
        ax.set_title(name, fontsize=7)
        ax.tick_params(labelsize=6)
        ax.set_xticks([0, 0.5, 1.0])
        ax.set_xticklabels(["0", ".5", "1"])
        ax.grid(axis="y", ls=":", alpha=0.4)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        if ax is axes[0]:
            ax.set_ylabel("Rate", fontsize=6.5)

    axes[0].legend(loc="upper left", fontsize=5, frameon=False,
                   handlelength=1.2, borderaxespad=0.1, labelspacing=0.25,
                   handletextpad=0.4)
    axes[0].text(0.96, eps + 0.04, rf"$\epsilon$={eps}", fontsize=5,
                  color=red_line, ha="right", va="bottom",
                  transform=axes[0].get_yaxis_transform())
    fig.tight_layout()
    out = FIG_DIR / "fig_calibration.png"
    fig.savefig(str(out), dpi=400, bbox_inches="tight", pad_inches=0.025)
    plt.close(fig)
    print(f"[saved] {out}")


# ──────────────────────────────────────────────────────────────────────────────
# W1: Noise-floor + excess drift figure
# ──────────────────────────────────────────────────────────────────────────────

def make_noise_floor_figure():
    # Native single-column 1x4 row: same footprint as before, fonts ~1:1.
    _S.apply_rc(font_size=7)
    FAMILY_LABELS = {
        "stochastic":   "Stoch.",
        "entity_alias": "Alias",
        "prompt":       "Prompt",
        "evidence":     "Evid.",
        "schema":       "Schema",
    }
    ORDER = ["stochastic", "entity_alias", "prompt", "evidence", "schema"]
    excess_color = _PINK
    base_color   = _BLUE_LIGHT
    floor_line   = _PINK

    fig, axes = plt.subplots(1, 4, figsize=(3.5, 0.83), sharey=True,
                             gridspec_kw={"wspace": 0.20})

    for ax, (tag, name) in zip(axes, CORPORA):
        pairs = load_pairs(tag)
        D0 = noise_floor_from_cache(name)

        by_fam: dict[str, list] = {}
        for p in pairs:
            by_fam.setdefault(p["family"], []).append(p["graph_drift"])

        x = np.arange(len(ORDER))
        bar_w = 0.68
        for i, fam in enumerate(ORDER):
            drifts = by_fam.get(fam, [])
            if not drifts:
                continue
            mean_d = float(np.mean(drifts))
            base = min(D0, mean_d)
            excess = max(0.0, mean_d - D0)
            ax.bar(i, base, bar_w, color=base_color, edgecolor=_BLUE,
                   linewidth=0.8, zorder=3)
            ax.bar(i, excess, bar_w, bottom=base, color=excess_color,
                   edgecolor=_PINK, linewidth=0.8, zorder=3)
            ax.text(i, mean_d + 0.03, f"{mean_d:.2f}", rotation=90,
                    ha="center", va="bottom", fontsize=5.5, color=_BLACK)

        ax.axhline(D0, color=floor_line, lw=1.0, ls="--")
        ax.text(0.96, 0.96, rf"$D_0$={D0:.2f}", transform=ax.transAxes,
                ha="right", va="top", fontsize=5.5, color=floor_line)
        ax.set_xticks(x)
        ax.set_xticklabels([FAMILY_LABELS[f] for f in ORDER],
                           fontsize=5.2, rotation=35, ha="right")
        ax.set_title(name, fontsize=7, pad=3)
        ax.tick_params(axis="y", labelsize=6)
        ax.set_ylim(0, 1.12)
        ax.set_yticks([0, 0.5, 1.0])
        ax.grid(axis="y", ls=":", alpha=0.4)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].set_ylabel("Mean drift", fontsize=6.5)

    from matplotlib.patches import Patch
    axes[3].legend(handles=[
        Patch(facecolor=base_color,   edgecolor=_BLUE, label=r"base $D_0$"),
        Patch(facecolor=excess_color, edgecolor=_PINK, label="excess"),
    ], loc="upper right", bbox_to_anchor=(1.0, 0.84), fontsize=5,
       frameon=False, handlelength=1.0, borderaxespad=0.1,
       labelspacing=0.25, handletextpad=0.4)
    fig.tight_layout()
    out = FIG_DIR / "fig_noise_floor.png"
    fig.savefig(str(out), dpi=400, bbox_inches="tight", pad_inches=0.025)
    plt.close(fig)
    print(f"[saved] {out}")


# ──────────────────────────────────────────────────────────────────────────────
# W3: 2-D sensitivity heatmap τ_g × τ_q
# ──────────────────────────────────────────────────────────────────────────────

def make_2d_sensitivity_figure():
    # Native single-column canvas, corpora as rows and {harm, F1 fidelity} as
    # columns, so every annotated cell stays legible in print.
    _S.apply_rc(font_size=7)
    TAU_G = [0.20, 0.30, 0.45, 0.60]
    TAU_Q = [0.50, 0.70, 0.90]

    shown = CORPORA
    fig, axes = plt.subplots(
        len(shown), 2, figsize=(3.5, 3.25), squeeze=False
    )

    cmap_harm = mcolors.LinearSegmentedColormap.from_list(
        "harm", ["#FFFFFF", _S.PINK, _S.PINK_DARK, "#8B2D44"])
    cmap_util = mcolors.LinearSegmentedColormap.from_list(
        "util", ["#FFFFFF", _S.BLUE, _S.BLUE_DARK, "#1F4F70"])

    def _draw_heatmap(ax, grid, cmap, vmin=0, vmax=1):
        ax.imshow(grid, cmap=cmap, vmin=vmin, vmax=vmax,
                  aspect="auto", interpolation="nearest")
        ax.set_xticks(range(len(TAU_Q)))
        ax.set_xticklabels([f"{t:.1f}" for t in TAU_Q], fontsize=6.5)
        ax.set_yticks(range(len(TAU_G)))
        ax.set_yticklabels([f"{t:.2f}" for t in TAU_G], fontsize=6.5)
        for i in range(len(TAU_G)):
            for j in range(len(TAU_Q)):
                v = grid[i, j]
                thresh = vmin + 0.55 * (vmax - vmin)
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        fontsize=6.5,
                        color="white" if v > thresh else _BLACK)

    for row, (tag, name) in enumerate(shown):
        pairs = load_pairs(tag)
        gd = np.array([p["graph_drift"] for p in pairs])
        aq = np.array([p["max_answer_drift"] for p in pairs])
        harm = np.array([int(p["harmful"]) for p in pairs])

        harm_grid = np.zeros((len(TAU_G), len(TAU_Q)))
        util_grid = np.zeros((len(TAU_G), len(TAU_Q)))
        for i, tg in enumerate(TAU_G):
            for j, tq in enumerate(TAU_Q):
                blocked = (gd >= tg) | (aq >= tq)
                published = ~blocked
                n_pub = published.sum()
                harm_grid[i, j] = (published & (harm == 1)).sum() / max(n_pub, 1)
                # F1 fidelity: mean per-pair 1-|dF1| over published pairs
                df1 = np.array([abs(p["mean_df1"]) for p in pairs])
                util_grid[i, j] = ((1.0 - df1)[published].mean()
                                   if n_pub else 0.0)

        ax_h, ax_u = axes[row]
        _draw_heatmap(ax_h, harm_grid, cmap_harm)
        _draw_heatmap(ax_u, util_grid, cmap_util, vmin=0.90, vmax=1.0)
        ax_h.set_ylabel(name + "\n" + r"$\tau_g$", fontsize=7)
        if row == 0:
            ax_h.set_title("Published-harm rate", fontsize=8)
            ax_u.set_title(r"$F_1$ fidelity", fontsize=8)
        if row == len(shown) - 1:
            ax_h.set_xlabel(r"$\tau_q$", fontsize=7)
            ax_u.set_xlabel(r"$\tau_q$", fontsize=7)

        # Gold box at the operating point tau_g=0.45, tau_q=0.70.
        r = TAU_G.index(0.45)
        c = TAU_Q.index(0.70)
        for ax in (ax_h, ax_u):
            ax.add_patch(plt.Rectangle((c - 0.45, r - 0.45), 0.9, 0.9,
                                       fill=False, edgecolor="#D4A017",
                                       linewidth=1.4, zorder=5))

    fig.tight_layout(h_pad=0.6, w_pad=0.5)
    out = FIG_DIR / "fig_2d_sensitivity.png"
    fig.savefig(str(out), dpi=200, bbox_inches="tight", pad_inches=0.025)
    plt.close(fig)
    print(f"[saved] {out}")

# ──────────────────────────────────────────────────────────────────────────────
# W4: AUROC + AUPRC figure
# ──────────────────────────────────────────────────────────────────────────────

MONITOR_LABELS = {
    "graph_only_drift": "Graph drift",
    "contract_severity": "Contract severity",
    "answer_drift": "Answer-set drift",
    "self_consistency": "Self-consistency",
    "confidence_inv": "Confidence (inv.)",
    "min_confidence_inv": "Min-conf. (inv.)",
    "graphguard": "GraphGuard (gate)",
}
MONITOR_COLORS = {
    "graph_only_drift":   _BLUE,
    "contract_severity":  _BLUE_LIGHT,
    "answer_drift":       _PINK,
    "self_consistency":   _LAV,
    "confidence_inv":     _PEACH,
    "min_confidence_inv": _GRAY,
    "graphguard":         _GREEN,
}
def make_auroc_figure():
    # Native single-column 1x4 row, ROC only (PR curves ship in the artifact).
    _S.apply_rc(font_size=8)
    plt.rcParams.update({
        "axes.linewidth": 0.7,
        "axes.labelsize": 7.5,
        "axes.titlesize": 8,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "lines.linewidth": 1.1,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
    })
    fig, axes = plt.subplots(1, 4, figsize=(3.5, 1.22),
                             sharex=True, sharey=True,
                             gridspec_kw={"wspace": 0.16})

    roc_summary = {}
    legend_handles = []
    for ax_r, (tag, name) in zip(axes, CORPORA):
        pairs = load_pairs(tag)
        labels = np.array([int(p["harmful"]) for p in pairs])
        if labels.sum() == 0 or labels.sum() == len(labels):
            ax_r.text(0.5, 0.5, "No var.", ha="center",
                      transform=ax_r.transAxes, fontsize=6)
            continue

        scores_map = {
            "graph_only_drift": np.array([p["graph_drift"] for p in pairs]),
            "answer_drift": np.array([p["max_answer_drift"] for p in pairs]),
            "graphguard": np.maximum(
                np.array([p["graph_drift"] for p in pairs])
                / TAU_GRAPH_DEFAULT,
                np.array([p["max_answer_drift"] for p in pairs])
                / TAU_QUERY_DEFAULT,
            ),
        }
        roc_summary[name] = {}
        roc_text_lines = []
        for mkey, scores in scores_map.items():
            label = MONITOR_LABELS.get(mkey, mkey)
            color = MONITOR_COLORS.get(mkey, "#888888")
            ls = {
                "graph_only_drift": "-",
                "answer_drift": "-.",
                "graphguard": "--",
            }[mkey]
            fpr, tpr, _ = roc_curve(labels, scores)
            auroc = auc(fpr, tpr)
            line, = ax_r.plot(fpr, tpr, color=color, ls=ls, lw=1.05,
                              label=label)
            if len(legend_handles) < 3:
                legend_handles.append(line)
            roc_text_lines.append((auroc, color))
            roc_summary[name][label] = {"auroc": round(auroc, 3)}

        for j, (val, col) in enumerate(roc_text_lines):
            ax_r.text(0.97, 0.05 + (len(roc_text_lines) - 1 - j) * 0.14,
                      f"{val:.2f}", transform=ax_r.transAxes, ha="right",
                      va="bottom", fontsize=5.5,
                      family="monospace", color=col)
        ax_r.plot([0, 1], [0, 1], color=_GRAY, ls=":", lw=0.55)
        ax_r.set_xlim(0, 1)
        ax_r.set_ylim(0, 1.01)
        ax_r.set_xticks([0, 0.5, 1.0])
        ax_r.set_xticklabels(["0", ".5", "1"])
        ax_r.set_yticks([0, 0.5, 1.0])
        ax_r.set_yticklabels(["0", ".5", "1"])
        ax_r.set_aspect("equal", adjustable="box")
        ax_r.grid(True, color=_S.GRAY_LIGHT, ls=":", lw=0.5, alpha=0.9)
        _S.despine(ax_r)
        ax_r.spines["left"].set_linewidth(0.7)
        ax_r.spines["bottom"].set_linewidth(0.7)
        ax_r.set_title(name, pad=3)

    axes[0].set_ylabel("TPR")
    fig.supxlabel("False-positive rate (FPR)", y=0.01, fontsize=7.5)
    fig.legend(
        legend_handles,
        ["Graph drift", "Answer drift", "GraphGuard"],
        loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=3,
        frameon=False, handlelength=1.5, columnspacing=0.9,
        handletextpad=0.4,
    )
    fig.subplots_adjust(left=0.095, right=0.995, bottom=0.24, top=0.77)
    out = FIG_DIR / "fig_auroc.png"
    fig.savefig(str(out), dpi=300, bbox_inches="tight", pad_inches=0.025,
                facecolor=_S.WHITE)
    plt.close(fig)

    print(f"[saved] {out}")
    print("\nAUROC/AUPRC summary:")
    for corpus, ms in roc_summary.items():
        print(f"  {corpus}:")
        for m, vals in ms.items():
            print(f"    {m}: AUROC={vals['auroc']:.3f}")


if __name__ == "__main__":
    main()
