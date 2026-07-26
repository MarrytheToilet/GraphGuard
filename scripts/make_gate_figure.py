#!/usr/bin/env python3
"""Single-column figure replacing the Kuzu release-gate table.

Two stacked panels over the four corpora: (a) published-harm rate and
(b) F1 fidelity, for publish-all / graph-only / GraphGuard at the
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
from make_kuzu_gate_artifacts import (
    DATASETS,
    TAU_GRAPH_DEFAULT,
    TAU_QUERY_DEFAULT,
    gate_metrics,
    load_pairs,
    policy_graph_only,
    policy_graphguard,
    policy_publish_all,
)

CORPORA = [name for name, _ in DATASETS]
POLICIES = ["Publish-all", "Graph-only", "GraphGuard"]

FILLS  = {"Publish-all": _S.GRAY_LIGHT, "Graph-only": _S.BLUE, "GraphGuard": _S.PINK}
EDGES  = {"Publish-all": _S.GRAY, "Graph-only": _S.BLUE_DARK, "GraphGuard": _S.PINK_DARK}


def load_panel_data():
    """Recompute the plotted values from the shipped N=300 pair records."""
    harm = {policy: [] for policy in POLICIES}
    fidelity = {policy: [] for policy in POLICIES}
    for _, run in DATASETS:
        pairs = load_pairs(run)
        masks = {
            "Publish-all": policy_publish_all(pairs),
            "Graph-only": policy_graph_only(pairs, TAU_GRAPH_DEFAULT),
            "GraphGuard": policy_graphguard(
                pairs, TAU_GRAPH_DEFAULT, TAU_QUERY_DEFAULT
            ),
        }
        for policy, mask in masks.items():
            metrics = gate_metrics(pairs, mask)
            harm[policy].append((
                metrics["published_harmful_rate"],
                *metrics["pub_harm_ci"],
            ))
            fidelity[policy].append((
                metrics["f1_fidelity"],
                *metrics["f1_fidelity_ci"],
            ))
    return harm, fidelity


def panel(ax, data, ylabel, ylim, annotate=True):
    x = np.arange(len(CORPORA))
    w = 0.26
    for i, pol in enumerate(POLICIES):
        vals = [v[0] for v in data[pol]]
        err = np.array([[v[0] - v[1], v[2] - v[0]] for v in data[pol]]).T
        bars = ax.bar(x + (i - 1) * w, vals, width=w * 0.9, color=FILLS[pol],
                      edgecolor=EDGES[pol], linewidth=0.8, label=pol)
        ax.errorbar(x + (i - 1) * w, vals, yerr=err, fmt="none",
                    ecolor=EDGES[pol], elinewidth=0.8, capsize=1.5)
        if annotate:
            # place value labels just above the CI whisker top to avoid overlap
            label_lift = 0.018 if i == 1 else 0.0
            for xi, v, hi in zip(x + (i - 1) * w, vals,
                                 (d[2] for d in data[pol])):
                ax.text(xi, hi + 0.012 + label_lift, f"{v:.2f}",
                        ha="center", va="bottom", fontsize=5.2,
                        color=_S.BLACK)
    ax.set_xticks(x)
    ax.set_xticklabels(CORPORA)
    ax.set_ylabel(ylabel)
    ax.set_ylim(*ylim)
    _S.despine(ax)


def main() -> int:
    harm, fidelity = load_panel_data()
    _S.apply_rc(font_size=9)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(3.6, 2.05),
                                   gridspec_kw={"hspace": 0.85})
    panel(ax1, harm, "pub. harm rate", (0, 0.72))
    ax1.legend(fontsize=6.5, ncol=3, frameon=False, loc="upper center",
               bbox_to_anchor=(0.5, 1.02), handlelength=1.0, columnspacing=1.0)
    ax1.set_title("(a) Harm among published graphs", fontsize=8, pad=4)
    panel(ax2, fidelity, r"$F_1$ fidelity", (0.75, 1.09))
    ax2.axhline(1.0, color=_S.GRAY, linestyle=":", linewidth=0.7)
    ax2.set_title(r"(b) $F_1$ fidelity", fontsize=8, pad=4)

    out = ROOT / "assets" / "figures" / "fig_gate.png"
    _S.save_fig(fig, out)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
