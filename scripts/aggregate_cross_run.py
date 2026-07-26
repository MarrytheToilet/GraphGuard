#!/usr/bin/env python3
"""Aggregate drift-contract + amplification results across runs into headline figures.

Outputs:
  reports/cross_run/figures/figA_contract_violations_heatmap.png
  reports/cross_run/figures/figB_amplification_consistency.png
  reports/cross_run/figures/figC_query_drift_by_run.png
  reports/cross_run/cross_run_summary.json
  reports/cross_run/cross_run_summary.md
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.viz import (  # noqa: E402
    apply_rc, save_fig, despine,
    PINK, BLUE, PINK_DARK, BLUE_DARK, GREEN, GRAY, BLACK, WHITE,
    PALETTE,
)

apply_rc()

# ---------- friendly mapping + grouping (paper-facing names) -----------------
RUN_LABEL = {
    "docred__deepseek-v4-flash__300d":   "DocRED · 300d",
    "redocred__deepseek-v4-flash__300d": "Re-DocRED · 300d",
    "cdr__deepseek-v4-flash__300d":      "BC5CDR · 300d",
    "scierc__deepseek-v4-flash__100d":    "SciERC · 100d",
    "docred__glm-5__100d":               "GLM-5 · 100d",
    "docred__kimi-k2__100d":             "Kimi-K2 · 100d",
    "docred__qwen3-32b__100d":           "Qwen3-32B · 100d",
}
# "Primary" group: same model (DeepSeek-V4-Flash) across 4 datasets, 300d main
GROUP_PRIMARY = [
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "cdr__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
]
# "Cross-model" group: same dataset (DocRED) across 4 models
GROUP_CROSSMODEL = [
    "docred__deepseek-v4-flash__300d",
    "docred__glm-5__100d",
    "docred__kimi-k2__100d",
    "docred__qwen3-32b__100d",
]
CROSSMODEL_LABEL = {
    "docred__deepseek-v4-flash__300d": "DeepSeek-V4-Flash · 300d",
    "docred__glm-5__100d":             "GLM-5 · 100d",
    "docred__kimi-k2__100d":           "Kimi-K2 · 100d",
    "docred__qwen3-32b__100d":         "Qwen3-32B · 100d",
}
DIAGNOSTIC_IDS = [
    "diagnostic.edge_identity",
    "diagnostic.two_hop_endpoints",
    "diagnostic.fanout_join",
    "diagnostic.top_undirected_degree",
    "diagnostic.short_connectivity",
]
DIAGNOSTIC_SHORT = {
    "diagnostic.edge_identity": "D1 edge identity",
    "diagnostic.two_hop_endpoints": "D2 two-hop endpoints",
    "diagnostic.fanout_join": "D3 fan-out join",
    "diagnostic.top_undirected_degree": "D4 top degree",
    "diagnostic.short_connectivity": "D5 short connectivity",
}
GROUP_COLORS = {
    # Primary (datasets)
    "docred__deepseek-v4-flash__300d":   BLUE,
    "redocred__deepseek-v4-flash__300d": BLUE_DARK,
    "cdr__deepseek-v4-flash__300d":      GREEN,
    "scierc__deepseek-v4-flash__100d":    "#9FC9DE",
    # Cross-model (already includes deepseek as anchor; rest)
    "docred__glm-5__100d":               PINK,
    "docred__kimi-k2__100d":             PINK_DARK,
    "docred__qwen3-32b__100d":           "#F2A9C0",
}


def load_run(run_dir: Path) -> dict | None:
    cj = run_dir / "eval" / "contracts.json"
    diagnostic = (
        ROOT / "reports" / "cross_run"
        / f"diagnostic_{run_dir.name}.json"
    )
    if not cj.exists():
        return None
    contracts = json.loads(cj.read_text())
    amp = json.loads(diagnostic.read_text()) if diagnostic.exists() else None
    return {"name": run_dir.name, "contracts": contracts, "amp": amp}


def fig_contract_heatmap(runs: list[dict], out: Path) -> None:
    contract_ids = []
    seen = set()
    for r in runs:
        for c in r["contracts"]["contracts"]:
            cid = c["contract_id"]
            if cid not in seen:
                seen.add(cid)
                contract_ids.append(cid)

    M = np.full((len(runs), len(contract_ids)), np.nan)
    annot = [["" for _ in contract_ids] for _ in runs]
    for i, r in enumerate(runs):
        m = {c["contract_id"]: c for c in r["contracts"]["contracts"]}
        for j, cid in enumerate(contract_ids):
            c = m.get(cid)
            if not c or c["n_pairs"] == 0:
                annot[i][j] = "—"
                continue
            v = c["violation_rate"]
            M[i, j] = v
            annot[i][j] = f"{v:.2f}"

    y_labels = [RUN_LABEL.get(r["name"], r["name"]) for r in runs]
    fig, ax = plt.subplots(figsize=(max(8, 1.0 * len(contract_ids) + 3), 1.2 + 0.65 * len(runs)))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue_pink", [WHITE, BLUE, PINK, PINK_DARK])
    im = ax.imshow(M, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(contract_ids)))
    ax.set_xticklabels(contract_ids, fontsize=12)
    ax.set_yticks(range(len(runs)))
    ax.set_yticklabels(y_labels, fontsize=11)
    for i in range(len(runs)):
        for j in range(len(contract_ids)):
            color = WHITE if (M[i, j] is not np.nan and M[i, j] > 0.6) else BLACK
            ax.text(j, i, annot[i][j], ha="center", va="center",
                    fontsize=11, color=color, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("violation rate", rotation=270, labelpad=14)
    ax.set_title("Drift-contract violation rate · run × contract", pad=12)
    save_fig(fig, out)


def _grouped_bar_panel(ax, rows, qnames, qshort, metric_key, title, ylabel,
                       label_map, show_amp_line=False):
    """Draw a grouped bar chart on a single Axes for one group of runs."""
    width = 0.8 / max(1, len(rows))
    x = np.arange(len(qnames))
    for i, r in enumerate(rows):
        bq = r["amp"]["summary"]
        vals = [bq.get(q, {}).get(metric_key, np.nan) for q in qnames]
        color = GROUP_COLORS.get(r["name"], PALETTE[i % len(PALETTE)])
        ax.bar(x + (i - len(rows) / 2 + 0.5) * width, vals, width,
               color=color, edgecolor=BLACK, linewidth=0.6,
               label=label_map.get(r["name"], r["name"]))
    if show_amp_line:
        ax.axhline(1.0, color=GRAY, linestyle="--", linewidth=1.0, alpha=0.7)
    # highlight join column
    join_idx = next(
        (j for j, q in enumerate(qnames) if q == "diagnostic.fanout_join"),
        None,
    )
    if join_idx is not None:
        ax.axvspan(join_idx - 0.48, join_idx + 0.48, color=PINK, alpha=0.08, zorder=0)
    ax.set_xticks(x)
    ax.set_xticklabels([qshort[q] for q in qnames], rotation=0, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=13, pad=8)
    ax.legend(loc="upper left", frameon=False, fontsize=10)
    ax.tick_params(axis="y", labelsize=11)
    despine(ax)


def _split_groups(runs):
    """Split runs into (primary_cross_domain, cross_model_docred) lists."""
    by_name = {r["name"]: r for r in runs if r.get("amp")}
    primary = [by_name[n] for n in GROUP_PRIMARY if n in by_name]
    crossm  = [by_name[n] for n in GROUP_CROSSMODEL if n in by_name]
    return primary, crossm


def fig_amp_consistency(runs: list[dict], out: Path) -> None:
    primary, crossm = _split_groups(runs)
    if not primary and not crossm:
        return
    # use the first available run to enumerate query names
    src = (primary or crossm)[0]
    qnames = [query_id for query_id in DIAGNOSTIC_IDS
              if query_id in src["amp"]["summary"]]
    qshort = DIAGNOSTIC_SHORT

    fig, axes = plt.subplots(1, 2, figsize=(16, 5.2), sharey=True)
    _grouped_bar_panel(
        axes[0], primary, qnames, qshort, "amplification_mean_per_pair",
                       "(a) Cross-domain · DeepSeek-V4-Flash",
                       "Amp(D) = QueryDrift / (GraphDrift + ε)",
                       RUN_LABEL, show_amp_line=True,
    )
    _grouped_bar_panel(
        axes[1], crossm, qnames, qshort, "amplification_mean_per_pair",
                       "(b) Cross-model · DocRED",
                       "", CROSSMODEL_LABEL, show_amp_line=True,
    )
    fig.suptitle(
        "Drift amplification by diagnostic type", fontsize=14, y=1.00
    )
    fig.tight_layout()
    save_fig(fig, out)


def fig_query_drift_by_run(runs: list[dict], out: Path) -> None:
    primary, crossm = _split_groups(runs)
    if not primary and not crossm:
        return
    src = (primary or crossm)[0]
    qnames = [query_id for query_id in DIAGNOSTIC_IDS
              if query_id in src["amp"]["summary"]]
    qshort = DIAGNOSTIC_SHORT

    fig, axes = plt.subplots(1, 2, figsize=(16, 5.2), sharey=True)
    _grouped_bar_panel(axes[0], primary, qnames, qshort, "query_drift_mean",
                       "(a) Cross-domain · DeepSeek-V4-Flash",
                       "Query drift (1 − Jaccard of answer sets)",
                       RUN_LABEL, show_amp_line=False)
    _grouped_bar_panel(axes[1], crossm, qnames, qshort, "query_drift_mean",
                       "(b) Cross-model · DocRED",
                       "", CROSSMODEL_LABEL, show_amp_line=False)
    fig.suptitle("Per-query drift across runs", fontsize=14, y=1.00)
    fig.tight_layout()
    save_fig(fig, out)


def write_summary(runs: list[dict], out_json: Path, out_md: Path) -> None:
    summary = {"runs": []}
    for r in runs:
        cs = r["contracts"]["contracts"]
        amp = (r.get("amp") or {}).get("summary", {})
        amp_d1 = amp.get("diagnostic.edge_identity", {}).get(
            "amplification_mean_per_pair"
        )
        amp_d3 = amp.get("diagnostic.fanout_join", {}).get(
            "amplification_mean_per_pair"
        )
        ratio = (amp_d3 / amp_d1) if (amp_d1 and amp_d3) else None
        summary["runs"].append({
            "name": r["name"],
            "contracts": {
                c["contract_id"]: {
                    "n_pairs": c["n_pairs"],
                    "violation_rate": c["violation_rate"],
                    "verdict": c["verdict"],
                } for c in cs
            },
            "Amp_D1_mean": amp_d1,
            "Amp_D3_mean": amp_d3,
            "Amp_D3_over_D1": ratio,
        })
    out_json.write_text(json.dumps(summary, indent=2))

    lines = ["# Cross-run summary", "",
             "| Run | K1 | K1b | K1c | K2 | K3 | K4 | K5 | K6 | Amp(D3) | Amp(D3)/Amp(D1) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summary["runs"]:
        c = s["contracts"]
        def cell(k):
            x = c.get(k)
            if not x or x["n_pairs"] == 0: return "—"
            verdict_mark = {"VIOLATED": "🔴", "SATISFIED": "🟢", "INCONCLUSIVE": "⚪"}.get(x["verdict"], "")
            return f"{x['violation_rate']:.2f} {verdict_mark}"
        lines.append("| " + " | ".join([
            RUN_LABEL.get(s["name"], s["name"]).replace("\n", " "),
            cell("K1"), cell("K1b"), cell("K1c"), cell("K2"),
            cell("K3"), cell("K4"), cell("K5"), cell("K6"),
            f"{s['Amp_D3_mean']:.2f}" if s.get("Amp_D3_mean") is not None else "—",
            f"{s['Amp_D3_over_D1']:.2f}×" if s.get("Amp_D3_over_D1") is not None else "—",
        ]) + " |")
    out_md.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default="reports/runs")
    ap.add_argument("--out-dir", default="reports/cross_run")
    ap.add_argument("--include", nargs="+", default=None,
                    help="Optional list of run names to include; else auto-discover.")
    args = ap.parse_args()

    runs_dir = Path(args.runs_dir)
    out_dir = Path(args.out_dir)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    runs = []
    candidates = sorted(p for p in runs_dir.iterdir() if p.is_dir())
    for p in candidates:
        if args.include and p.name not in args.include:
            continue
        r = load_run(p)
        if r is not None:
            runs.append(r)
            print(f"  loaded {p.name}: {len(r['contracts']['contracts'])} contracts, "
                  f"{'amp' if r['amp'] else 'no amp'}")

    if not runs:
        print("no runs found", file=sys.stderr)
        return 1

    fig_contract_heatmap(runs, fig_dir / "figA_contract_violations_heatmap.png")
    fig_amp_consistency(runs, fig_dir / "figB_amplification_consistency.png")
    fig_query_drift_by_run(runs, fig_dir / "figC_query_drift_by_run.png")
    write_summary(runs, out_dir / "cross_run_summary.json",
                  out_dir / "cross_run_summary.md")
    print(f"[done] wrote {out_dir}/  ({len(runs)} runs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
