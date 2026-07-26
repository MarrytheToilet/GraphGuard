#!/usr/bin/env python3
"""Paper figure for the extended-query + regime results (PVLDB revision).

Replaces the wide two-part table with a single-column, two-panel figure:
  (a) mean amplification per corpus for Q5 (shortest path, with 95% CI),
      Q6 (aggregation), Q7 (RAG retrieval), dashed line at Amp = 1;
  (b) gold-free detector F1 against workload-visible query change, graph-only vs
      query-aware, per corpus and regime (dumbbells).

Reads reports/cross_run/extqueries_<run>.json and regimes_<run>.json;
writes assets/figures/fig_extqueries.png.
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
        reg[label] = json.loads((REP / f"regimes_{run}.json").read_text())["regimes"]

    # Per-corpus no-amplification reference: the lookup query Q1, whose answer set
    # equals the edge set by construction. epsilon-damping places it below 1
    # (mean-of-ratios); its ratio-of-means value is exactly 1.
    amp = json.loads((REP / "amp_ci.json").read_text())
    q1_run = {"DocRED": "docred__deepseek-v4-flash__300d",
              "Re-DocRED": "redocred__deepseek-v4-flash__300d",
              "SciERC": "scierc__deepseek-v4-flash__100d",
              "BC5CDR": "cdr__deepseek-v4-flash__300d"}
    q1_ref = {l: amp[r]["Q1_single_edge"]["amp_mean"] for l, r in q1_run.items()}

    labels = [l for _, l in RUNS]
    x = np.arange(len(labels))

    _S.apply_rc(font_size=9)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(3.6, 2.50),
                                   gridspec_kw={"hspace": 0.5})

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
        ax1.hlines(q1_ref[l], x[i] - 1.6 * w, x[i] + 1.6 * w,
                   color=_S.GRAY, linestyle="--", linewidth=0.8, zorder=0)
    ax1.set_xticks(x); ax1.set_xticklabels(labels)
    ax1.set_ylabel(r"$\overline{\mathrm{Amp}}(Q)$")
    ax1.set_ylim(0, 1.92)
    handles, labs = ax1.get_legend_handles_labels()
    handles.append(Line2D([0], [0], color=_S.GRAY, linestyle="--", linewidth=0.8))
    labs.append(r"$Q_1$ ref.")
    ax1.legend(handles, labs, fontsize=6.5, ncol=4, frameon=False, loc="upper center",
               bbox_to_anchor=(0.5, 1.06), handlelength=1.0, columnspacing=0.8)
    ax1.set_title("(a) Extended-template amplification", fontsize=9)
    _S.despine(ax1)

    # ---- (b) regime dumbbells --------------------------------------------
    off = {"local": -0.16, "multihop": 0.16}
    color = {"local": _S.BLUE_DARK, "multihop": _S.PINK_DARK}
    fill = {"local": _S.BLUE, "multihop": _S.PINK}
    for regime in ("local", "multihop"):
        gx, gy, qy = [], [], []
        for i, l in enumerate(labels):
            s = reg[l][regime]
            gx.append(i + off[regime])
            gy.append(s["graph_only"]["f1"])
            qy.append(s["query_aware"]["f1"])
        for xi, g, q in zip(gx, gy, qy):
            ax2.plot([xi, xi], [g, q], color=color[regime], linewidth=1.1, zorder=1)
        ax2.scatter(gx, gy, s=18, facecolor="white", edgecolor=color[regime],
                    linewidth=1.2, zorder=2,
                    label=f"{'local' if regime=='local' else 'multi-hop'}: graph-only")
        ax2.scatter(gx, qy, s=22, facecolor=fill[regime], edgecolor=color[regime],
                    linewidth=1.2, zorder=3,
                    label=f"{'local' if regime=='local' else 'multi-hop'}: query-aware")
    ax2.set_xticks(x); ax2.set_xticklabels(labels)
    ax2.set_ylabel("detector F1")
    ax2.set_ylim(0.46, 1.02)
    ax2.legend(fontsize=6.5, ncol=2, frameon=False, loc="lower right",
               bbox_to_anchor=(1.0, 0.0), handletextpad=0.3, columnspacing=0.8)
    ax2.set_title(
        "(b) Workload-visible change: graph-only vs. query-aware",
        fontsize=9,
    )
    _S.despine(ax2)

    out = ROOT / "assets" / "figures" / "fig_extqueries.png"
    _S.save_fig(fig, out, pad=0.8)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
