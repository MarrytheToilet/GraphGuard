#!/usr/bin/env python3
"""Single-column figure replacing the Kuzu release-gate table.

Two stacked panels over the four corpora: (a) published-harm rate and
(b) retained utility, for publish-all / graph-only / GraphGuard at the
paper's operating point (tau_g=0.45, tau_q=0.70), with bootstrap 95% CIs.
Values mirror the validated release-gate evaluation shipped in
reports/cross_run/e2e_kuzu_case_<run>__N300.json (see
make_kuzu_gate_artifacts.py); per-policy operating details (publish/block
rates, harm recall/precision, false-block rates) remain in the artifact.

Writes assets/figures/fig_gate.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from graphguard.viz import style as _S

CORPORA = ["DocRED", "Re-DocRED", "SciERC", "BC5CDR"]
POLICIES = ["Publish-all", "Graph-only", "GraphGuard"]

# (harm_rate, lo, hi), (retained_utility, lo, hi) per corpus per policy.
HARM = {
    "Publish-all": [(0.24, 0.19, 0.29), (0.18, 0.14, 0.23), (0.31, 0.25, 0.36), (0.19, 0.15, 0.24)],
    "Graph-only":  [(0.16, 0.10, 0.23), (0.13, 0.07, 0.19), (0.16, 0.07, 0.25), (0.12, 0.08, 0.16)],
    "GraphGuard":  [(0.03, 0.00, 0.07), (0.00, 0.00, 0.00), (0.00, 0.00, 0.00), (0.04, 0.02, 0.07)],
}
UTIL = {
    "Publish-all": [(0.92, 0.90, 0.93), (0.96, 0.95, 0.96), (0.86, 0.84, 0.88), (0.84, 0.80, 0.87)],
    "Graph-only":  [(0.95, 0.93, 0.97), (0.96, 0.96, 0.97), (0.91, 0.87, 0.95), (0.91, 0.88, 0.94)],
    "GraphGuard":  [(0.99, 0.99, 1.00), (1.00, 1.00, 1.00), (0.99, 0.98, 1.00), (0.97, 0.96, 0.98)],
}
COLORS = {"Publish-all": _S.GRAY, "Graph-only": _S.BLUE_DARK, "GraphGuard": _S.PINK_DARK}


def panel(ax, data, ylabel, ylim, annotate=True):
    x = np.arange(len(CORPORA))
    w = 0.26
    for i, pol in enumerate(POLICIES):
        vals = [v[0] for v in data[pol]]
        err = np.array([[v[0] - v[1], v[2] - v[0]] for v in data[pol]]).T
        bars = ax.bar(x + (i - 1) * w, vals, width=w * 0.9,
                      color=COLORS[pol], label=pol)
        ax.errorbar(x + (i - 1) * w, vals, yerr=err, fmt="none",
                    ecolor=_S.BLACK, elinewidth=0.7, capsize=1.5)
        if annotate:
            _S.annotate_bars(ax, bars, vals, fmt="{:.2f}", fontsize=5.3)
    ax.set_xticks(x)
    ax.set_xticklabels(CORPORA)
    ax.set_ylabel(ylabel)
    ax.set_ylim(*ylim)
    _S.despine(ax)


def main() -> int:
    _S.apply_rc(font_size=8)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(3.4, 3.3),
                                   gridspec_kw={"hspace": 0.42})
    panel(ax1, HARM, "published-harm rate", (0, 0.42))
    ax1.legend(fontsize=6, ncol=3, frameon=False, loc="upper right",
               handlelength=1.0, columnspacing=0.8)
    ax1.set_title("(a) Harm among published graphs", fontsize=8)
    panel(ax2, UTIL, "retained utility", (0.75, 1.06), annotate=False)
    ax2.axhline(1.0, color=_S.GRAY, linestyle=":", linewidth=0.7)
    ax2.set_title("(b) Retained utility", fontsize=8)

    out = ROOT / "assets" / "figures" / "fig_gate.png"
    _S.save_fig(fig, out)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
