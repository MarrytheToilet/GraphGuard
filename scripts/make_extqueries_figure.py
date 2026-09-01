#!/usr/bin/env python3
"""Paper figure for the extended-query + regime results (PVLDB revision).

Builds the single-column, two-panel Figure 9:
  (a) mean amplification per corpus for Q5 (shortest path, with 95% CI),
      Q6 (aggregation), Q7 (RAG retrieval), dashed line at Amp = 1;
  (b) query-mean minus graph-only detection F1 under strictly matched review
      budgets, for local and multi-hop registered workloads.

Reads reports/cross_run/extqueries_<run>.json and the registered regime
artifacts; writes a vector PDF and matching PNG preview in assets/figures/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
import numpy as np

from graphguard.viz import style as _S

RUNS = [
    ("docred__deepseek-v4-flash__300d", "DocRED"),
    ("redocred__deepseek-v4-flash__300d", "Re-DocRED"),
    ("scierc__deepseek-v4-flash__100d", "SciERC"),
    ("cdr__deepseek-v4-flash__300d", "BC5CDR"),
]
REP = ROOT / "reports" / "cross_run"


def main() -> int:
    ext, reg = {}, {}
    for run, label in RUNS:
        ext[label] = json.loads((REP / f"extqueries_{run}.json").read_text())["summary"]
        reg[label] = json.loads(
            (REP / f"regimes_{run}.json").read_text()
        )["regimes"]

    # Per-corpus no-amplification reference: diagnostic D1, whose answer set
    # equals the edge set by construction. Epsilon-damping places it below 1
    # (mean-of-ratios); its ratio-of-means value is exactly 1.
    amp = json.loads((REP / "amp_ci.json").read_text())["runs"]
    d1_run = {"DocRED": "docred__deepseek-v4-flash__300d",
              "Re-DocRED": "redocred__deepseek-v4-flash__300d",
              "SciERC": "scierc__deepseek-v4-flash__100d",
              "BC5CDR": "cdr__deepseek-v4-flash__300d"}
    d1_ref = {
        label: amp[run]["diagnostic.edge_identity"]["amp_mean"]
        for label, run in d1_run.items()
    }

    labels = [l for _, l in RUNS]
    x = np.arange(len(labels))

    _S.apply_rc(font_size=9)
    fig = plt.figure(figsize=(3.6, 2.50))
    grid = fig.add_gridspec(
        2, 2, height_ratios=(1.08, 0.92), hspace=0.78, wspace=0.10
    )
    ax1 = fig.add_subplot(grid[0, :])
    ax_local = fig.add_subplot(grid[1, 0])
    ax_multihop = fig.add_subplot(grid[1, 1])

    # ---- (a) amplification ------------------------------------------------
    w = 0.26
    specs = [("Q_path", r"$Q_5$ path", _S.BLUE, _S.BLUE_DARK),
             ("Q_deg", r"$Q_6$ agg", _S.PINK, _S.PINK_DARK),
             ("Q_rag", r"$Q_7$ RAG", _S.GREEN, _S.GREEN_DARK)]
    for i, (key, lab, fill, color) in enumerate(specs):
        vals = [ext[l][key]["amp_mean"] for l in labels]
        bars = ax1.bar(x + (i - 1) * w, vals, width=w * 0.92, color=fill,
                       edgecolor=color, linewidth=0.8, label=lab)
        if key == "Q_path":
            err = np.array([[ext[l][key]["amp_mean"] - ext[l][key]["amp_ci_lo"],
                             ext[l][key]["amp_ci_hi"] - ext[l][key]["amp_mean"]]
                            for l in labels]).T
            ax1.errorbar(x + (i - 1) * w, vals, yerr=err, fmt="none",
                         ecolor=_S.BLACK, elinewidth=0.8, capsize=1.5)
            for bar, val, err_hi in zip(bars, vals, err[1]):
                ax1.text(bar.get_x() + bar.get_width() / 2,
                         val + err_hi + 0.035, f"{val:.2f}",
                         ha="center", va="bottom", fontsize=5.5,
                         color=_S.BLACK)
        else:
            _S.annotate_bars(ax1, bars, vals, fmt="{:.2f}", fontsize=5.5)
    for i, l in enumerate(labels):
        ax1.hlines(d1_ref[l], x[i] - 1.6 * w, x[i] + 1.6 * w,
                   color=_S.GRAY, linestyle="--", linewidth=0.8, zorder=0)
    ax1.set_xticks(x); ax1.set_xticklabels(labels)
    ax1.set_ylabel(r"$\overline{\mathrm{Amp}}(Q)$")
    ax1.set_ylim(0, 1.92)
    handles, labs = ax1.get_legend_handles_labels()
    handles.append(Line2D([0], [0], color=_S.GRAY, linestyle="--", linewidth=0.8))
    labs.append(r"$D_1$ ref.")
    ax1.legend(handles, labs, fontsize=6.5, ncol=4, frameon=False,
               loc="upper left", bbox_to_anchor=(0.01, 1.04),
               labelspacing=0.1, borderpad=0, borderaxespad=0,
               handlelength=0.9, columnspacing=0.6, handletextpad=0.25)
    ax1.set_title("(a) Query-topology amplification", fontsize=8)
    _S.despine(ax1)

    # ---- (b) strictly matched review budgets -----------------------------
    budgets = [0.30, 0.50, 0.70, 0.90]
    cmap = LinearSegmentedColormap.from_list(
        "query_gain", ["#F7FBFF", _S.BLUE, _S.BLUE_DARK]
    )
    for axis, regime, title in (
        (ax_local, "local", "local"),
        (ax_multihop, "multihop", "multi-hop"),
    ):
        values = np.array([
            [
                next(
                    row["query_mean_minus_graph_f1"]
                    for row in reg[label][regime]["fixed_review_budgets"]
                    if row["review_budget"] == budget
                )
                for budget in budgets
            ]
            for label in labels
        ])
        x_edges = np.arange(values.shape[1] + 1) - 0.5
        y_edges = np.arange(values.shape[0] + 1) - 0.5
        axis.pcolormesh(
            x_edges,
            y_edges,
            values,
            cmap=cmap,
            vmin=0.0,
            vmax=0.25,
            shading="flat",
            edgecolors="none",
            antialiased=False,
        )
        axis.set_xlim(-0.5, values.shape[1] - 0.5)
        axis.set_ylim(values.shape[0] - 0.5, -0.5)
        axis.set_xticks(range(len(budgets)))
        axis.set_xticklabels([f"{budget:.0%}" for budget in budgets], fontsize=5.5)
        axis.set_yticks(range(len(labels)))
        axis.set_yticklabels(labels if regime == "local" else [], fontsize=5.5)
        axis.set_title(title, fontsize=6.5, pad=1.5)
        axis.tick_params(length=0, pad=1.2)
        for row_index in range(values.shape[0]):
            for column_index in range(values.shape[1]):
                value = values[row_index, column_index]
                label = "0" if abs(value) < 0.0005 else f"+{value:.2f}"
                axis.text(
                    column_index,
                    row_index,
                    label,
                    ha="center",
                    va="center",
                    fontsize=5.2,
                    color="white" if value >= 0.14 else _S.BLACK,
                )
        for spine in axis.spines.values():
            spine.set_linewidth(0.45)
            spine.set_color(_S.GRAY)
    fig.text(
        0.55,
        0.425,
        "(b) Query-aware F1 gain at matched budgets",
        ha="center",
        va="bottom",
        fontsize=8,
    )
    fig.text(0.55, 0.025, "review budget", ha="center", fontsize=6.0)

    out = ROOT / "assets" / "figures" / "fig_extqueries.pdf"
    _S.save_fig(fig, out, pad=0.8)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
