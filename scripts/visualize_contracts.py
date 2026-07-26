"""Visualize drift contracts and canonical diagnostic amplification.

Output naming (under reports/runs/<run>/figures/):
    fig01_contracts_violations.png
    fig02_contracts_threshold_sensitivity.png
    fig03_amplification_by_query.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from graphguard.viz import (
    PALETTE, PINK, PINK_DARK, BLUE, BLUE_DARK, GREEN, LAVENDER, GRAY,
    BLACK, WHITE, apply_rc, save_fig, despine, color_for_verdict,
    annotate_bars,
)
import matplotlib.pyplot as plt


apply_rc(font_size=11)


# ------------------------------------------------------------------ contracts


def viz_contracts(contracts_json: Path, fig_dir: Path) -> None:
    data = json.loads(contracts_json.read_text())
    items = data["contracts"]

    # Keep inconclusive contracts out of the plots, but do not lose them in text reports.
    plotted = [c for c in items if c.get("n_pairs", 0) > 0]
    if not plotted:
        print("  contracts: nothing to plot (all inconclusive)")
        return

    # Sort by violation rate so the headline pattern is obvious.
    plotted = sorted(
        plotted,
        key=lambda c: (c["violation_rate"], c.get("metric_mean", 0.0)),
        reverse=True,
    )

    ids = [c["contract_id"] for c in plotted]
    names = [c.get("name", "") for c in plotted]
    viols = np.array([c["violation_rate"] for c in plotted], dtype=float)
    means = np.array([c["metric_mean"] for c in plotted], dtype=float)
    verdicts = [c["verdict"] for c in plotted]
    n_pairs = [c["n_pairs"] for c in plotted]
    colors = [color_for_verdict(v) for v in verdicts]

    # ------------------------------------------------------------------
    # 1. Contract violation rate: horizontal bars
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9.8, max(4.2, 0.55 * len(plotted) + 1.6)))

    y = np.arange(len(plotted))
    bars = ax.barh(
        y,
        viols,
        color=colors,
        edgecolor=BLACK,
        linewidth=0.6,
        height=0.62,
    )

    # Y labels: ID + short name.
    def short_name(s: str, max_len: int = 38) -> str:
        s = s.replace(" invariance", "").replace(" robustness", "")
        return s if len(s) <= max_len else s[: max_len - 1] + "…"

    ylabels = [f"{cid}  {short_name(name)}" for cid, name in zip(ids, names)]
    ax.set_yticks(y)
    ax.set_yticklabels(ylabels, fontsize=9)
    ax.invert_yaxis()

    ax.set_xlim(0, 1.08)
    ax.set_xlabel("Violation rate")
    ax.set_title("Drift-contract violations")

    # Tolerance guide lines.
    ax.axvline(
        0.05,
        color=GRAY,
        ls="--",
        lw=0.9,
        alpha=0.85,
        label="5% invariance tolerance",
    )
    ax.axvline(
        0.20,
        color=GRAY,
        ls=":",
        lw=0.9,
        alpha=0.85,
        label="20% bounded-drift tolerance",
    )

    # Bar-end labels: violation rate.
    for yi, val in zip(y, viols):
        ax.text(
            min(val + 0.018, 1.04),
            yi,
            f"{val:.2f}",
            va="center",
            ha="left",
            fontsize=9,
            color=BLACK,
        )

    # Right-side compact metadata column.
    # Put n and mean metric outside bar area, aligned by row.
    for yi, n, mu, verdict in zip(y, n_pairs, means, verdicts):
        ax.text(
            1.075,
            yi,
            f"n={n:,}   μ={mu:.2f}",
            va="center",
            ha="left",
            fontsize=8.5,
            color=GRAY,
            transform=ax.get_yaxis_transform(),
        )

    # Compact legend: verdict colors + tolerance lines.
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D

    legend_handles = [
        Patch(facecolor=color_for_verdict("VIOLATED"), edgecolor=BLACK, label="VIOLATED"),
        Patch(facecolor=color_for_verdict("SATISFIED"), edgecolor=BLACK, label="SATISFIED"),
        Patch(facecolor=color_for_verdict("INCONCLUSIVE"), edgecolor=BLACK, label="INCONCLUSIVE"),
        Line2D([0], [0], color=GRAY, ls="--", lw=0.9, label="5% inv. tol."),
        Line2D([0], [0], color=GRAY, ls=":", lw=0.9, label="20% bd. tol."),
    ]

    ax.legend(
        handles=legend_handles,
        loc="lower right",
        ncol=2,
        fontsize=9,
        framealpha=0.95,
        borderaxespad=0.6,
    )

    ax.grid(True, axis="x", alpha=0.22, color=GRAY, linestyle=":")
    despine(ax)

    # Tight margins; reserve a slim right column for n / μ metadata.
    fig.subplots_adjust(left=0.28, right=0.84, bottom=0.10, top=0.92)
    save_fig(fig, fig_dir / "fig01_contracts_violations.png")

    # ------------------------------------------------------------------
    # 2. Threshold sensitivity
    # ------------------------------------------------------------------
    fig2, ax2 = plt.subplots(figsize=(8.8, 5.2))

    marker_cycle = ["o", "s", "^", "D", "v", "P", "X", "*"]

    for i, c in enumerate(plotted):
        sens = c.get("threshold_sensitivity", {})
        if not sens:
            continue

        # Robust parsing because JSON keys may be "0.5" but sometimes generated as floats.
        ts = sorted(float(t) for t in sens.keys())
        vs = [sens[str(t)] if str(t) in sens else sens.get(f"{t:.1f}", np.nan) for t in ts]

        ax2.plot(
            ts,
            vs,
            color=PALETTE[i % len(PALETTE)],
            marker=marker_cycle[i % len(marker_cycle)],
            linewidth=2.0,
            markersize=6.5,
            markeredgecolor=BLACK,
            markeredgewidth=0.55,
            label=c["contract_id"],
        )

    ax2.set_xlabel("Threshold τ")
    ax2.set_ylabel("Violation rate at τ")
    ax2.set_ylim(-0.03, 1.05)

    if all_ts := [float(t) for c in plotted for t in c.get("threshold_sensitivity", {}).keys()]:
        ax2.set_xlim(min(all_ts) - 0.02, max(all_ts) + 0.02)

    ax2.set_title("Threshold sensitivity of drift-contract violations")
    ax2.grid(True, axis="y", alpha=0.25, color=GRAY, linestyle=":")
    despine(ax2)

    # Inline legend in the empty middle-right region.
    ax2.legend(
        title="Contract",
        loc="center right",
        ncol=2,
        fontsize=9,
        title_fontsize=9,
        framealpha=0.95,
        borderaxespad=0.6,
    )

    fig2.subplots_adjust(left=0.10, right=0.96, bottom=0.12, top=0.92)
    save_fig(fig2, fig_dir / "fig02_contracts_threshold_sensitivity.png")


# ----------------------------------------------- canonical D1--D5 diagnostics


def viz_amplification(diagnostic_json: Path, fig_dir: Path) -> None:
    data = json.loads(diagnostic_json.read_text())
    by_q = data["summary"]
    queries = [
        "diagnostic.edge_identity",
        "diagnostic.two_hop_endpoints",
        "diagnostic.fanout_join",
        "diagnostic.top_undirected_degree",
        "diagnostic.short_connectivity",
    ]
    queries = [query_id for query_id in queries if query_id in by_q]
    amps = [by_q[q]["amplification_mean_per_pair"] for q in queries]
    qds  = [by_q[q]["query_drift_mean"] for q in queries]
    gds  = [by_q[q]["graph_drift_mean"] for q in queries]
    ns   = [by_q[q]["n"]                for q in queries]

    short = {
        "diagnostic.edge_identity": "D1\nedge identity",
        "diagnostic.two_hop_endpoints": "D2\ntwo-hop endpoints",
        "diagnostic.fanout_join": "D3\nfan-out join",
        "diagnostic.top_undirected_degree": "D4\ntop degree",
        "diagnostic.short_connectivity": "D5\nshort connectivity",
    }
    labels = [short.get(q, q) for q in queries]
    is_d3 = [q == "diagnostic.fanout_join" for q in queries]

    fig, ax = plt.subplots(figsize=(10, 5.0))
    x = np.arange(len(queries))
    w = 0.36

    # Amp bars: highlight D3 in dark pink, others in soft pink.
    amp_colors = [PINK_DARK if d3 else PINK for d3 in is_d3]
    bars1 = ax.bar(x - w / 2, amps, w, color=amp_colors,
                   edgecolor=BLACK, linewidth=0.6,
                   label="Amp(D) = QueryDrift / (GraphDrift + ε)")
    bars2 = ax.bar(x + w / 2, qds, w, color=BLUE,
                   edgecolor=BLACK, linewidth=0.6,
                   label="QueryDrift (mean)")

    ax.axhline(1.0, color=GRAY, ls="--", lw=0.9)
    ax.text(len(queries) - 0.6, 1.03, "Amp = 1 (no amplification)",
            color=GRAY, fontsize=9, ha="right")

    if gds:
        gd_mean = float(np.mean(gds))
        ax.axhline(gd_mean, color=BLUE_DARK, ls=":", lw=1.4,
                   label=f"GraphDrift baseline (mean = {gd_mean:.2f})")

    annotate_bars(ax, bars1, amps, fmt="{:.2f}", dy=0.02)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Mean drift / amplification")

    title = "Drift amplification by query type"
    d1 = by_q.get("diagnostic.edge_identity")
    d3 = by_q.get("diagnostic.fanout_join")
    if d1 and d3 and d1["amplification_mean_per_pair"]:
        ratio = (
            d3["amplification_mean_per_pair"]
            / d1["amplification_mean_per_pair"]
        )
        title += f"   ·   Amp(D3) / Amp(D1) = {ratio:.2f}×"
    ax.set_title(title)
    ax.set_ylim(0, max(max(amps), max(qds), 1.0) * 1.22)
    ax.legend(loc="upper right", framealpha=0.95)
    despine(ax)
    save_fig(fig, fig_dir / "fig03_amplification_by_query.png")


# ------------------------------------------------------------------- driver


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True,
                    help="reports/runs/<run> directory")
    args = ap.parse_args()
    rd = Path(args.run_dir)
    figdir = rd / "figures"
    figdir.mkdir(parents=True, exist_ok=True)

    cj = rd / "eval" / "contracts.json"
    if cj.exists():
        viz_contracts(cj, figdir)
    diagnostic = (
        ROOT / "reports" / "cross_run"
        / f"diagnostic_{rd.name}.json"
    )
    if diagnostic.exists():
        viz_amplification(diagnostic, figdir)


if __name__ == "__main__":
    main()
