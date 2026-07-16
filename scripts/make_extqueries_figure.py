#!/usr/bin/env python3
"""Paper figure for the extended-query + regime results (PVLDB revision).

Replaces the wide two-part table with a single-column, two-panel figure:
  (a) mean amplification per corpus for Q5 (shortest path, with 95% CI),
      Q6 (aggregation), Q7 (RAG retrieval), dashed line at Amp = 1;
  (b) gold-free detector F1 against workload-visible harm, graph-only vs
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

    labels = [l for _, l in RUNS]
    x = np.arange(len(labels))

    _S.apply_rc(font_size=8)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(3.4, 3.4),
                                   gridspec_kw={"hspace": 0.52})

    # ---- (a) amplification ------------------------------------------------
    w = 0.26
    specs = [("Q_path", r"$Q_5$ path", _S.BLUE_DARK),
             ("Q_deg", r"$Q_6$ agg", _S.PINK_DARK),
             ("Q_rag", r"$Q_7$ RAG", _S.GREEN_DARK)]
    for i, (key, lab, color) in enumerate(specs):
        vals = [ext[l][key]["amp_mean"] for l in labels]
        bars = ax1.bar(x + (i - 1) * w, vals, width=w * 0.92, color=color, label=lab)
        if key == "Q_path":
            err = np.array([[ext[l][key]["amp_mean"] - ext[l][key]["amp_ci_lo"],
                             ext[l][key]["amp_ci_hi"] - ext[l][key]["amp_mean"]]
                            for l in labels]).T
            ax1.errorbar(x + (i - 1) * w, vals, yerr=err, fmt="none",
                         ecolor=_S.BLACK, elinewidth=0.7, capsize=1.5)
        _S.annotate_bars(ax1, bars, vals, fmt="{:.2f}", fontsize=5.5)
    ax1.axhline(1.0, color=_S.GRAY, linestyle="--", linewidth=0.8)
    ax1.set_xticks(x); ax1.set_xticklabels(labels)
    ax1.set_ylabel(r"$\overline{\mathrm{Amp}}(Q)$")
    ax1.set_ylim(0, 1.55)
    ax1.legend(fontsize=6, ncol=3, frameon=False, loc="upper left",
               handlelength=1.0, columnspacing=0.9)
    ax1.set_title("(a) Extended-template amplification", fontsize=8)
    _S.despine(ax1)

    # ---- (b) regime dumbbells --------------------------------------------
    off = {"local": -0.16, "multihop": 0.16}
    color = {"local": _S.BLUE_DARK, "multihop": _S.PINK_DARK}
    for regime in ("local", "multihop"):
        gx, gy, qy = [], [], []
        for i, l in enumerate(labels):
            s = reg[l][regime]
            gx.append(i + off[regime])
            gy.append(s["graph_only"]["f1"])
            qy.append(s["query_aware"]["f1"])
        for xi, g, q in zip(gx, gy, qy):
            ax2.plot([xi, xi], [g, q], color=color[regime], linewidth=1.1, zorder=1)
        ax2.scatter(gx, gy, s=14, facecolor="white", edgecolor=color[regime],
                    linewidth=1.1, zorder=2,
                    label=f"{'local' if regime=='local' else 'multi-hop'}: graph-only")
        ax2.scatter(gx, qy, s=16, color=color[regime], zorder=3,
                    label=f"{'local' if regime=='local' else 'multi-hop'}: query-aware")
    ax2.set_xticks(x); ax2.set_xticklabels(labels)
    ax2.set_ylabel("detector F1")
    ax2.set_ylim(0.5, 1.02)
    ax2.legend(fontsize=5.6, ncol=2, frameon=False, loc="lower left",
               handletextpad=0.3, columnspacing=0.8)
    ax2.set_title("(b) Workload-visible harm: graph-only vs. query-aware", fontsize=8)
    _S.despine(ax2)

    out = ROOT / "assets" / "figures" / "fig_extqueries.png"
    _S.save_fig(fig, out)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
