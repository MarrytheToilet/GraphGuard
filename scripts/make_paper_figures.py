"""Regenerate all paper figures with publication-ready styling.

Reads from existing report artefacts (no extraction re-run) and writes
PNGs into paper/figures/ with friendly labels, larger fonts, and
consistent palette.  Replaces the ad-hoc generators that leaked variable
names (run IDs, family slugs, P-codes) into the camera-ready figures.

Inputs (relative to repo root):
  reports/cross_run/cross_run_summary.json      (per-run violation rates)
  reports/cross_run/amp_ci.json                 (Amp CIs per run, per query)
  reports/cross_run/k5_cross_model.json         (cross-model recall stability)
  reports/runs/<run>/eval/contracts.json        (per-contract sweep)
  reports/runs/<run>/eval/e8_amplification.json (within-run Amp)
  data/processed/runs/<run>/reports/e3_report.json  (schema flip rates)
  data/processed/runs/<run>/reports/e5_faithfulness.json
  data/processed/runs/<run>/reports/e6_query_stability.json

Outputs (paper/figures/):
  fig_crossrun_violations.png   contract violation rates run x contract
  fig_amp_crossrun.png          Amp(Q) cross-run consistency
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
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
    "Q1_single_edge": "Q1 single-edge",
    "Q2_two_hop":     "Q2 2-hop",
    "Q3_join":        "Q3 join",
    "Q4_top_degree":  "Q4 top-degree",
    "Q5_short_paths": "Q5 shortest path",
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
        "axes.titleweight": "bold",
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
    fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white")
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
        choices=["all", "replacement", "phase_w"],
        help="Which figure pack to (re)build (default: all).")
    args = parser.parse_args()

    if args.target in ("all", "replacement"):
        replacement_crossrun_violations()
        replacement_amp_crossrun()
        replacement_strict_vs_soft()
    if args.target in ("all", "phase_w"):
        make_noise_floor_figure()
        make_calibration_figure()
        make_2d_sensitivity_figure()
        make_auroc_figure()


# ===========================================================================
# Replacement figures for paper tables
# (merged from former scripts/make_replacement_figures.py; uses graphguard.viz.style)
# ===========================================================================

from graphguard.viz import style as _S  # noqa: E402


def replacement_crossrun_violations() -> None:
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
        # Read directly from the cross-run summary so Fig.~\ref{fig:crossrun_violations}
        # stays numerically identical to Table~\ref{tab:contractnum} and the prose in
        # Sec. RQ2.  Earlier versions of this function recomputed K4/K6 from
        # per-run artifacts under slightly different thresholding conventions,
        # which produced (0.93, 0.91) for DocRED--DSV4 while the table/text used
        # (0.89, 0.92).  We keep a single source of truth.
        return float(by_name[run_name]["contracts"][db_key]["violation_rate"])

    mat = np.zeros((len(db_keys), len(order)))   # transposed: rows=contracts
    for j_, (_, name) in enumerate(order):
        for i_, k in enumerate(db_keys):
            mat[i_, j_] = paper_violation_rate(name, k)

    # Short, horizontal-friendly run labels.
    short_runs = ["DR\nDSV4", "RDR\nDSV4", "SE\nDSV4", "CDR\nDSV4",
                  "DR\nGLM5", "DR\nKimi", "DR\nQwen3"]

    fig, ax = plt.subplots(figsize=(3.5, 2.0))
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
                    color=_S.BLACK if v < 0.55 else _S.WHITE,
                    fontweight="bold")
    cbar = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cbar.set_label("violation rate", fontsize=7)
    cbar.ax.tick_params(labelsize=6.5)
    ax.set_title("Cross-run contract violation rates",
                 fontsize=9, fontweight="bold")
    _S.save_fig(fig, OUT / "fig_crossrun_violations.png")


def replacement_amp_crossrun() -> None:
    _S.apply_rc(font_size=8)
    rows = [  # (corpus, model, Amp_Q1, Amp_Q3, CI_lo, CI_hi)
        ("DocRED",    "DSV4",  0.89, 1.32, 1.25, 1.40),
        ("DocRED",    "GLM-5", 0.76, 1.37, 1.24, 1.53),
        ("DocRED",    "Kimi",  0.78, 1.16, 1.10, 1.23),
        ("DocRED",    "Qwen3", 0.84, 1.13, 1.09, 1.17),
        ("Re-DocRED", "DSV4",  0.90, 1.34, 1.29, 1.40),
        ("SciERC",    "DSV4",  0.90, 0.68, 0.64, 0.72),
        ("BC5CDR",    "DSV4",  0.40, 0.02, 0.01, 0.04),
    ]
    corpora = [r[0] for r in rows]
    models = [r[1] for r in rows]
    q1 = [r[2] for r in rows]
    q3 = [r[3] for r in rows]
    err_lo = [r[3] - r[4] for r in rows]
    err_hi = [r[5] - r[3] for r in rows]
    x = np.arange(len(rows))
    w = 0.38

    fig, ax = plt.subplots(figsize=(3.5, 1.9))
    b1 = ax.bar(x - w/2, q1, w, color=_S.BLUE, edgecolor=_S.BLUE_DARK,
                linewidth=0.6, label=r"$Q_1$ (single-hop)")
    b2 = ax.bar(x + w/2, q3, w, color=_S.PINK, edgecolor=_S.PINK_DARK,
                linewidth=0.6,
                yerr=[err_lo, err_hi], capsize=2,
                error_kw=dict(ecolor=_S.PINK_DARK, lw=0.8),
                label=r"$Q_3$ (join, 95% CI)")
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
    y_top = 1.7
    ax.set_ylim(0, y_top)
    ax.set_ylabel(r"$\overline{\mathrm{Amp}}$", fontsize=9)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_title("Cross-run query amplification", fontsize=9, fontweight="bold")
    fig.legend([b1, b2],
               [r"$Q_1$ (single-hop)", r"$Q_3$ (join, 95% CI)"],
               loc="lower center", ncol=2, fontsize=7, frameon=False,
               bbox_to_anchor=(0.5, -0.14))
    _S.despine(ax)
    for rect, v in zip(b1, q1):
        ax.text(rect.get_x() + rect.get_width() / 2,
                rect.get_height() + 0.04, f"{v:.2f}",
                ha="center", va="bottom", fontsize=6, color=_S.BLACK)
    for rect, v, hi in zip(b2, q3, [r[5] for r in rows]):
        ax.text(rect.get_x() + rect.get_width() / 2,
                hi + 0.05, f"{v:.2f}",
                ha="center", va="bottom", fontsize=6, color=_S.BLACK)
    _S.save_fig(fig, OUT / "fig_amp_crossrun.png")


def replacement_strict_vs_soft() -> None:
    _S.apply_rc(font_size=8)
    rows = {
        "DocRED":    (0.69, 0.75, 0.76),
        "Re-DocRED": (0.71, 0.77, 0.78),
        "SciERC":    (0.72, 0.79, 0.83),
        "BC5CDR":    (0.18, 0.17, 0.27),
    }
    rows_h = {
        "DocRED":    (0.35, 0.42, 0.43),
        "Re-DocRED": (0.28, 0.35, 0.34),
        "SciERC":    (0.62, 0.62, 0.67),
        "BC5CDR":    (0.12, 0.12, 0.21),
    }
    labels = list(rows.keys())
    x = np.arange(len(labels))
    w = 0.25
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.7), sharey=True)

    def plot_one(ax, data, title):
        l1 = [data[l][0] for l in labels]
        l2 = [data[l][1] for l in labels]
        l3 = [data[l][2] for l in labels]
        ax.bar(x - w, l1, w, color=_S.BLUE,  edgecolor=_S.BLUE_DARK,  linewidth=0.5, label="L1")
        ax.bar(x,     l2, w, color=_S.PINK,  edgecolor=_S.PINK_DARK,  linewidth=0.5, label="L2")
        ax.bar(x + w, l3, w, color=_S.GREEN, edgecolor=_S.GREEN_DARK, linewidth=0.5, label="L3")
        short_lbl = {"DocRED":"DR","Re-DocRED":"RDR","SciERC":"SE","BC5CDR":"CDR"}
        xl = [short_lbl.get(l, l) for l in labels]
        ax.set_xticks(x); ax.set_xticklabels(xl, rotation=0, ha="center", fontsize=6.5)
        ax.set_title(title, fontsize=8.5, fontweight="bold")
        ax.tick_params(axis="y", labelsize=7)
        ax.set_ylim(0, 1.0)
        _S.despine(ax)

    plot_one(axes[0], rows,   r"Violation @ $\tau{=}0.5$")
    plot_one(axes[1], rows_h, "Harmful regression")
    axes[0].set_ylabel("rate", fontsize=8)
    axes[1].legend(loc="upper right", fontsize=6.5, ncol=1,
                   framealpha=0.9, handlelength=1.2)
    fig.suptitle("L1–L3 stability buckets", fontsize=9, y=1.02)
    _S.save_fig(fig, OUT / "fig_strict_vs_soft.png")




# ===========================================================================
# Phase-W artifacts  (merged from former scripts/make_phase_w_artifacts.py)
# Threshold calibration, noise-floor, 2-D sensitivity, AUROC/AUPRC, equiv-table.
# ===========================================================================
import sqlite3 as _sqlite3
import matplotlib.colors as mcolors
from sklearn.metrics import roc_curve, precision_recall_curve, auc, roc_auc_score

# Phase-W palette aliases
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
RUNS_DIR = ROOT / "data" / "processed" / "runs"
FIG_DIR  = ROOT / "paper" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

CORPORA = [
    ("docred__deepseek-v4-flash__300d", "DocRED"),
    ("redocred__deepseek-v4-flash__300d", "Re-DocRED"),
    ("scierc__deepseek-v4-flash__100d", "SciERC"),
    ("cdr__deepseek-v4-flash__300d", "BC5CDR"),
]

# ──────────────────────────────────────────────────────────────────────────────

def load_pairs(tag: str) -> list[dict]:
    path = REPORTS / f"e2e_kuzu_case_{tag}__N300.json"
    d = json.loads(path.read_text())
    return d["pair_records"]


def load_baselines(tag: str) -> dict:
    path = REPORTS / f"baselines_matched_{tag}.json"
    return json.loads(path.read_text())


def compute_calibration(pairs: list[dict], score_key: str = "graph_drift",
                        harm_eps: float = 0.05):
    """Sweep τ over score_key; return lists of (tau, coverage, harm_rate)."""
    scores = np.array([p[score_key] for p in pairs])
    labels = np.array([int(p["harmful"]) for p in pairs])
    taus = np.linspace(0.0, 1.0, 201)
    coverage, harm_rate = [], []
    for tau in taus:
        published = scores <= tau          # publish if drift <= tau
        n_pub = published.sum()
        n_harmful_pub = (published & (labels == 1)).sum()
        coverage.append(n_pub / max(len(pairs), 1))
        harm_rate.append(n_harmful_pub / max(n_pub, 1))
    return taus, np.array(coverage), np.array(harm_rate)


def noise_floor_from_db(tag: str) -> float:
    """Mean stochastic edge-overlap = 1 - D₀ from stability_reports."""
    db = RUNS_DIR / tag / f"{tag}.db"
    con = _sqlite3.connect(str(db))
    rows = con.execute(
        "SELECT avg_edge_overlap FROM stability_reports WHERE n_runs >= 2"
    ).fetchall()
    vals = [r[0] for r in rows if r[0] is not None]
    return 1.0 - float(np.mean(vals)) if vals else 0.0   # D0 drift


# ──────────────────────────────────────────────────────────────────────────────
# W2: Calibration figure – τ* at SLA ε
# ──────────────────────────────────────────────────────────────────────────────

def make_calibration_figure():
    _S.apply_rc(font_size=10)
    # Single-column display ~3.5" wide → 2x2 grid keeps each subplot ~1.75" wide.
    # Keep 1x4 layout per user request, but small canvas so native fonts render large.
    fig, axes = plt.subplots(1, 4, figsize=(7.6, 2.3), sharey=True)
    eps = 0.05  # SLA: ≤5% harmful publication rate

    blue_line = _BLUE
    red_line  = _PINK
    gray_fill = _BLUE_LIGHT
    green     = _GREEN

    for ax, (tag, name) in zip(axes, CORPORA):
        pairs = load_pairs(tag)
        taus, cov, harm = compute_calibration(pairs, score_key="graph_drift")

        # Largest τ such that publication harm rate still satisfies SLA.
        # Smaller τ trivially passes (publishes nothing) → not useful as
        # an operating point.
        feasible = np.where(harm <= eps)[0]
        if len(feasible):
            idx_star = feasible[-1]
            tau_star = taus[idx_star]
            cov_star = cov[idx_star]
        else:
            tau_star = cov_star = None

        ax.fill_between(taus, cov, alpha=0.25, color=gray_fill)
        ax.plot(taus, cov, color=blue_line, lw=1.6, label="Coverage")
        ax.plot(taus, harm, color=red_line, lw=1.6, ls="--", label="Pub. harm")
        ax.axhline(eps, color=red_line, lw=0.8, ls=":", alpha=0.7)
        if tau_star is not None:
            ax.axvline(tau_star, color=green, lw=1.4, ls="-.")
            ax.text(min(tau_star + 0.04, 0.80), 0.92,
                    rf"$\tau^*$={tau_star:.2f}",
                    fontsize=9, color=green, fontweight="bold")
        else:
            ax.text(0.5, 0.5, "infeasible\nunder graph-only gate",
                    ha="center", va="center", fontsize=9,
                    color=red_line, fontweight="bold",
                    transform=ax.transAxes)

        ax.set_xlim(0, 1)
        ax.set_ylim(-0.02, 1.08)
        ax.set_xlabel(r"$\tau$", fontsize=11)
        ax.set_title(name, fontsize=11, fontweight="bold")
        ax.tick_params(labelsize=9)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.grid(axis="y", ls=":", alpha=0.4)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        if ax is axes[0]:
            ax.set_ylabel("Rate", fontsize=11)

    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(plt.Line2D([0], [0], color=green, lw=1.4, ls="-."))
    labels.append(r"$\tau^*$ (operating point)")
    handles.append(plt.Line2D([0], [0], color=red_line, lw=0.8, ls=":"))
    labels.append(rf"SLA $\epsilon$={eps}")
    fig.legend(handles, labels, ncol=4, loc="upper center",
               bbox_to_anchor=(0.5, 0.04), fontsize=10,
               frameon=False, handlelength=2.0)

    fig.suptitle(
        rf"SLA-driven $\tau$ calibration (SLA $\epsilon$={eps})",
        fontsize=11, y=1.02
    )
    fig.tight_layout()
    out = FIG_DIR / "fig_calibration.png"
    fig.savefig(str(out), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[W2] saved {out}")


# ──────────────────────────────────────────────────────────────────────────────
# W1: Noise-floor + excess drift figure
# ──────────────────────────────────────────────────────────────────────────────

def make_noise_floor_figure():
    _S.apply_rc(font_size=10)
    FAMILY_LABELS = {
        "stochastic":   "Stoch.",
        "entity_alias": "Ent.alias",
        "prompt":       "Prompt",
        "evidence":     "Evid.",
        "schema":       "Schema",
    }
    ORDER = ["stochastic", "entity_alias", "prompt", "evidence", "schema"]
    # Use unified palette: gradient from light to dark within blue family.
    colors = {
        "stochastic":   _GRAY_LIGHT,
        "entity_alias": _BLUE_LIGHT,
        "prompt":       _BLUE,
        "evidence":     _PINK,
        "schema":       _PINK_LIGHT,
    }
    excess_color = _PINK
    base_color   = _BLUE_LIGHT
    floor_line   = _PINK

    fig, axes = plt.subplots(1, 4, figsize=(7.6, 2.6), sharey=True)

    for ax, (tag, name) in zip(axes, CORPORA):
        pairs = load_pairs(tag)
        D0 = noise_floor_from_db(tag)

        by_fam: dict[str, list] = {}
        for p in pairs:
            by_fam.setdefault(p["family"], []).append(p["graph_drift"])

        x = np.arange(len(ORDER))
        bar_w = 0.62
        for i, fam in enumerate(ORDER):
            drifts = by_fam.get(fam, [])
            if not drifts:
                continue
            mean_d = float(np.mean(drifts))
            base = min(D0, mean_d)
            excess = max(0.0, mean_d - D0)
            ax.bar(i, base, bar_w, color=base_color, edgecolor=_BLUE,
                   linewidth=0.5, zorder=3)
            ax.bar(i, excess, bar_w, bottom=base, color=excess_color,
                   edgecolor=_PINK, linewidth=0.5, zorder=3)
            ax.text(i, mean_d + 0.02, f"{mean_d:.2f}", ha="center",
                    va="bottom", fontsize=8, color=_BLACK)

        ax.axhline(D0, color=floor_line, lw=1.2, ls="--",
                   label=fr"$D_0$={D0:.2f}")
        ax.set_xticks(x)
        ax.set_xticklabels([FAMILY_LABELS[f] for f in ORDER],
                           fontsize=8.5, rotation=30, ha="right")
        ax.set_title(name, fontsize=11, fontweight="bold")
        ax.tick_params(axis="y", labelsize=9)
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", ls=":", alpha=0.4)
        ax.legend(fontsize=8.5, loc="upper left", framealpha=0.9,
                  handlelength=1.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        if ax is axes[0]:
            ax.set_ylabel("Mean graph drift", fontsize=10)

    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor=base_color,   edgecolor=_BLUE, label=r"Baseline $D_0$"),
        Patch(facecolor=excess_color, edgecolor=_PINK, label="Excess drift"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=2,
               fontsize=9.5, bbox_to_anchor=(0.5, -0.04), frameon=False)
    fig.suptitle(
        r"Perturbation drift vs. stochastic noise floor $D_0$",
        fontsize=11, y=1.02
    )
    fig.tight_layout()
    out = FIG_DIR / "fig_noise_floor.png"
    fig.savefig(str(out), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[W1] saved {out}")


# ──────────────────────────────────────────────────────────────────────────────
# W3: 2-D sensitivity heatmap τ_g × τ_q
# ──────────────────────────────────────────────────────────────────────────────

def make_2d_sensitivity_figure():
    _S.apply_rc(font_size=10)
    TAU_G = [0.20, 0.30, 0.40, 0.45, 0.50, 0.60]
    TAU_Q = [0.50, 0.60, 0.70, 0.80, 0.90]

    # Single-column 2x4 grid: keep canvas narrow so native fonts dominate.
    fig, axes = plt.subplots(2, 4, figsize=(7.6, 4.4))
    axes_harm = axes[0]
    axes_util = axes[1]

    # Clean monochrome ramps consistent with the rest of the paper:
    # harm uses a single warm hue (white -> dark pink), utility uses cool hue
    # (white -> dark blue). Both go from neutral background to saturated edge,
    # avoiding multi-hue gradients that read as muddy.
    cmap_harm = mcolors.LinearSegmentedColormap.from_list(
        "harm", ["#FFFFFF", _S.PINK, _S.PINK_DARK, "#8B2D44"])
    cmap_util = mcolors.LinearSegmentedColormap.from_list(
        "util", ["#FFFFFF", _S.BLUE, _S.BLUE_DARK, "#1F4F70"])

    for ax_h, ax_u, (tag, name) in zip(axes_harm, axes_util, CORPORA):
        pairs = load_pairs(tag)
        gd = np.array([p["graph_drift"] for p in pairs])
        aq = np.array([p["max_answer_drift"] for p in pairs])
        harm = np.array([int(p["harmful"]) for p in pairs])

        harm_grid = np.zeros((len(TAU_G), len(TAU_Q)))
        util_grid = np.zeros((len(TAU_G), len(TAU_Q)))

        for i, tg in enumerate(TAU_G):
            for j, tq in enumerate(TAU_Q):
                blocked = (gd > tg) | (aq > tq)
                published = ~blocked
                n_pub = published.sum()
                n_harmful_pub = (published & (harm == 1)).sum()
                harm_grid[i, j] = n_harmful_pub / max(n_pub, 1)
                benign = harm == 0
                n_benign_pub = (published & benign).sum()
                util_grid[i, j] = n_benign_pub / max(benign.sum(), 1)

        def _draw_heatmap(ax, grid, cmap, vmin=0, vmax=1):
            im = ax.imshow(grid, cmap=cmap, vmin=vmin, vmax=vmax,
                           aspect="auto", interpolation="nearest")
            ax.set_xticks(range(len(TAU_Q)))
            ax.set_xticklabels([f"{t:.1f}" for t in TAU_Q], fontsize=9)
            ax.set_yticks(range(len(TAU_G)))
            ax.set_yticklabels([f"{t:.1f}" for t in TAU_G], fontsize=9)
            for i in range(len(TAU_G)):
                for j in range(len(TAU_Q)):
                    v = grid[i, j]
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                            fontsize=7.0,
                            color="white" if v > 0.55 else _BLACK,
                            fontweight="bold")
            return im

        _draw_heatmap(ax_h, harm_grid, cmap_harm)
        _draw_heatmap(ax_u, util_grid, cmap_util)

        ax_h.set_title(name, fontsize=11, fontweight="bold")
        ax_u.set_xlabel(r"$\tau_q$", fontsize=10)
        if ax_h is axes_harm[0]:
            ax_h.set_ylabel(r"$\tau_g$" + "\n(Harm rate)", fontsize=10)
        if ax_u is axes_util[0]:
            ax_u.set_ylabel(r"$\tau_g$" + "\n(Utility)", fontsize=10)

    # Gold star at default operating point τ_g=0.45, τ_q=0.70 (matches Table 9).
    for ax_h, ax_u in zip(axes_harm, axes_util):
        # Find the closest grid cell to (0.45, 0.70).
        r = min(range(len(TAU_G)), key=lambda i: abs(TAU_G[i] - 0.45))
        c = min(range(len(TAU_Q)), key=lambda j: abs(TAU_Q[j] - 0.70))
        for ax in (ax_h, ax_u):
            ax.add_patch(plt.Rectangle((c - 0.45, r - 0.45), 0.9, 0.9,
                                       fill=False, edgecolor="#D4A017",
                                       linewidth=1.6, zorder=5))

    fig.suptitle(
        r"Gate sensitivity to $(\tau_g,\tau_q)$: harm (top), utility (bottom). "
        r"$\bigstar$ = paper's operating point",
        fontsize=10.5, y=1.01
    )
    fig.tight_layout(h_pad=0.6, w_pad=0.4)
    out = FIG_DIR / "fig_2d_sensitivity.png"
    fig.savefig(str(out), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[W3] saved {out}")


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
MONITOR_LS = {
    "graph_only_drift": "-",
    "contract_severity": "--",
    "answer_drift": "-.",
    "self_consistency": ":",
    "confidence_inv": (0, (3, 1)),
    "min_confidence_inv": (0, (5, 2)),
    "graphguard": "-",
}


def _pairs_to_monitor_scores(pairs: list[dict]) -> dict[str, np.ndarray]:
    """Extract per-pair scores for each monitor from Kuzu pair records."""
    gd = np.array([p["graph_drift"] for p in pairs])
    aq = np.array([p["max_answer_drift"] for p in pairs])
    # GraphGuard combined score = max(graph_drift, max_answer_drift)
    gg = np.maximum(gd, aq)
    # Confidence-inv not available in Kuzu pairs → load from baselines_matched
    return {
        "graph_only_drift": gd,
        "contract_severity": gd,   # proxy; contract_severity ~ graph_drift rank
        "graphguard": gg,
    }


def _scores_from_baselines(tag: str) -> dict[str, np.ndarray]:
    """
    Reconstruct continuous per-pair scores for baselines from fair_budget data.
    fair_budget_*.json contains per-pair graph_drift. baselines_matched gives
    only sweep points; we reconstruct AUROC directly from pair records + graph_drift.
    """
    try:
        bm = load_baselines(tag)
    except FileNotFoundError:
        return {}
    # baselines_matched only has 5-point sweeps; not enough for full ROC.
    # We'll return empty and rely on pair-level reconstruction.
    return {}


def make_auroc_figure():
    _S.apply_rc(font_size=10)
    # Single-column, 2 rows (ROC top, PR bottom) x 4 cols (corpora).
    fig, axes = plt.subplots(2, 4, figsize=(7.6, 4.4), sharex=True, sharey=True)
    axes_roc = axes[0]
    axes_pr = axes[1]

    roc_summary = {}

    for ax_r, ax_p, (tag, name) in zip(axes_roc, axes_pr, CORPORA):
        pairs = load_pairs(tag)
        labels = np.array([int(p["harmful"]) for p in pairs])

        if labels.sum() == 0 or labels.sum() == len(labels):
            ax_r.text(0.5, 0.5, "No var.", ha="center", transform=ax_r.transAxes, fontsize=9)
            ax_p.text(0.5, 0.5, "No var.", ha="center", transform=ax_p.transAxes, fontsize=9)
            continue

        scores_map = {
            "graph_only_drift": np.array([p["graph_drift"] for p in pairs]),
            "answer_drift": np.array([p["max_answer_drift"] for p in pairs]),
            "graphguard": np.maximum(
                [p["graph_drift"] for p in pairs],
                [p["max_answer_drift"] for p in pairs]
            ),
        }

        try:
            fb = json.loads((REPORTS / f"fair_budget_{tag}.json").read_text())
            if isinstance(fb, list) and fb and "confidence" in fb[0]:
                conf = np.array([r.get("confidence", 0.5) for r in fb])
                if len(conf) == len(labels):
                    scores_map["confidence_inv"] = 1.0 - conf
        except Exception:
            pass

        roc_summary[name] = {}
        roc_text_lines = []
        pr_text_lines = []
        for mkey, scores in scores_map.items():
            label = MONITOR_LABELS.get(mkey, mkey)
            color = MONITOR_COLORS.get(mkey, "#888888")
            ls = MONITOR_LS.get(mkey, "-")
            try:
                fpr, tpr, _ = roc_curve(labels, scores)
                auroc = auc(fpr, tpr)
                ax_r.plot(fpr, tpr, color=color, ls=ls, lw=1.4, label=label)

                prec, rec, _ = precision_recall_curve(labels, scores)
                auprc = auc(rec, prec)
                ax_p.plot(rec, prec, color=color, ls=ls, lw=1.4, label=label)

                roc_text_lines.append(f"{auroc:.2f}")
                pr_text_lines.append(f"{auprc:.2f}")
                roc_summary[name][label] = {"auroc": round(auroc, 3),
                                             "auprc": round(auprc, 3)}
            except Exception:
                pass

        if roc_text_lines:
            ax_r.text(0.97, 0.05, "\n".join(roc_text_lines),
                      transform=ax_r.transAxes, ha="right", va="bottom",
                      fontsize=7.5, family="monospace",
                      bbox=dict(boxstyle="round,pad=0.18", fc="white",
                                ec="#cccccc", alpha=0.85))
        if pr_text_lines:
            ax_p.text(0.97, 0.95, "\n".join(pr_text_lines),
                      transform=ax_p.transAxes, ha="right", va="top",
                      fontsize=7.5, family="monospace",
                      bbox=dict(boxstyle="round,pad=0.18", fc="white",
                                ec="#cccccc", alpha=0.85))

        ax_r.plot([0, 1], [0, 1], color=_GRAY, ls=":", lw=0.6, alpha=0.6)
        ax_r.set_xlim(0, 1); ax_r.set_ylim(0, 1.02)
        ax_p.set_xlim(0, 1); ax_p.set_ylim(0, 1.02)

        for ax in (ax_r, ax_p):
            ax.tick_params(labelsize=8.5)
            ax.set_xticks([0, 0.5, 1.0])
            ax.set_yticks([0, 0.5, 1.0])
            ax.grid(ls=":", alpha=0.4)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)

        ax_r.set_title(name, fontsize=10.5, fontweight="bold")

    axes_roc[0].set_ylabel("TPR", fontsize=10)
    axes_pr[0].set_ylabel("Precision", fontsize=10)
    for ax in axes_pr:
        ax.set_xlabel("FPR / Recall", fontsize=9.5)

    handles, labels_ = axes_roc[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels_, loc="lower center",
                   ncol=len(handles), fontsize=9, frameon=False,
                   bbox_to_anchor=(0.5, -0.04), handlelength=1.8,
                   columnspacing=1.2)

    fig.tight_layout(h_pad=0.3, w_pad=0.3, rect=(0, 0.04, 1, 1))
    out = FIG_DIR / "fig_auroc.png"
    fig.savefig(str(out), dpi=260, bbox_inches="tight")
    plt.close(fig)

    print(f"[W4] saved {out}")
    print("\nAUROC/AUPRC summary:")
    for corpus, ms in roc_summary.items():
        print(f"  {corpus}:")
        for m, vals in ms.items():
            print(f"    {m}: AUROC={vals['auroc']:.3f}  AUPRC={vals['auprc']:.3f}")


if __name__ == "__main__":
    main()
