"""Budget-aware contract planner experiment.

Simulates choosing which counterfactual extractions to materialize under a
budget. Compares random sampling, family-balanced round-robin, and a
family-prior greedy planner against a full endpoint-union plan.

Metric: harm-recall = (harmful pairs evaluated / total harmful), as a function
of fraction-of-full extraction budget.

Pair records come from the frozen formal actual-Kuzu N=300 artifacts.
"""
from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from graphguard.viz import style as gg_style  # noqa: F401
from graphguard.formal_artifacts import (
    DEFAULT_INDEX,
    load_artifact_index,
    load_formal_kuzu,
)
from graphguard.sqlite_snapshot import sha256_file

ROOT = Path(__file__).resolve().parents[1]

DATASETS = [
    ("DocRED",    "docred__deepseek-v4-flash__300d"),
    ("Re-DocRED", "redocred__deepseek-v4-flash__300d"),
    ("SciERC",    "scierc__deepseek-v4-flash__100d"),
    ("BC5CDR",    "cdr__deepseek-v4-flash__300d"),
]
OUT_FIG = Path("assets/figures/fig_budget_planner.png")
OUT_JSON = Path("reports/cross_run/budget_planner_formal_v1.json")

BUDGETS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
N_SEEDS = 50


@lru_cache(maxsize=None)
def load_pairs(run):
    artifact = load_formal_kuzu(ROOT, run)
    out = []
    for record in artifact["per_pair"]:
        out.append({
            "family": record["cause_family"],
            "harmful": float(record["mean_delta_f1_signed"]) > 0.05,
        })
    return out


def family_prior(calib_pairs):
    """Per-family empirical harm rate from a calibration split."""
    by_fam = defaultdict(list)
    for p in calib_pairs:
        by_fam[p["family"]].append(p["harmful"])
    return {f: (sum(v) / len(v) if v else 0.0) for f, v in by_fam.items()}


def harm_recall(selected, deploy):
    total_harm = sum(p["harmful"] for p in deploy)
    if total_harm == 0:
        return 0.0
    selected_harm = sum(p["harmful"] for p in selected)
    return selected_harm / total_harm


def plan_random(deploy, k, rng):
    idx = rng.permutation(len(deploy))[:k]
    return [deploy[i] for i in idx]


def plan_family_balanced(deploy, k, rng):
    by_fam = defaultdict(list)
    for i, p in enumerate(deploy):
        by_fam[p["family"]].append(i)
    for f in by_fam:
        rng.shuffle(by_fam[f])
    families = list(by_fam.keys())
    rng.shuffle(families)
    picked = []
    pointers = {f: 0 for f in families}
    while len(picked) < k:
        progressed = False
        for f in families:
            if pointers[f] < len(by_fam[f]):
                picked.append(by_fam[f][pointers[f]])
                pointers[f] += 1
                progressed = True
                if len(picked) >= k:
                    break
        if not progressed:
            break
    return [deploy[i] for i in picked]


def plan_greedy(deploy, k, prior, rng):
    # Sort pairs by descending family-prior harm rate; break ties randomly.
    scored = [(prior.get(p["family"], 0.0), rng.random(), i) for i, p in enumerate(deploy)]
    scored.sort(key=lambda x: (-x[0], x[1]))
    chosen = [i for _, _, i in scored[:k]]
    return [deploy[i] for i in chosen]


def plan_oracle(deploy, k, rng):
    # Oracle: knows which pairs are harmful; upper bound on any prior-based planner.
    scored = [(1.0 if p["harmful"] else 0.0, rng.random(), i) for i, p in enumerate(deploy)]
    scored.sort(key=lambda x: (-x[0], x[1]))
    chosen = [i for _, _, i in scored[:k]]
    return [deploy[i] for i in chosen]


def run_one(run, rng):
    pairs = load_pairs(run)
    n = len(pairs)
    # Calibration / deployment split (50/50).
    perm = rng.permutation(n)
    half = n // 2
    calib = [pairs[i] for i in perm[:half]]
    deploy = [pairs[i] for i in perm[half:]]
    prior = family_prior(calib)
    results = {"random": [], "balanced": [], "greedy": [], "oracle": []}
    for B in BUDGETS:
        k = max(1, int(round(B * len(deploy))))
        results["random"].append(harm_recall(plan_random(deploy, k, rng), deploy))
        results["balanced"].append(harm_recall(plan_family_balanced(deploy, k, rng), deploy))
        results["greedy"].append(harm_recall(plan_greedy(deploy, k, prior, rng), deploy))
        results["oracle"].append(harm_recall(plan_oracle(deploy, k, rng), deploy))
    return results


def aggregate():
    agg = {ds: {m: np.zeros(len(BUDGETS)) for m in ["random", "balanced", "greedy", "oracle"]}
           for ds, _ in DATASETS}
    for ds_name, run in DATASETS:
        for s in range(N_SEEDS):
            rng = np.random.default_rng(1000 + s)
            r = run_one(run, rng)
            for m in r:
                agg[ds_name][m] += np.array(r[m]) / N_SEEDS
    return agg


def main():
    agg = aggregate()
    index = load_artifact_index(ROOT)
    # Persist numeric results.
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "artifact_type": "graphguard.budget_planner_analysis",
        "artifact_version": 1,
        "sources": {
            "formal_index": {
                "path": str(DEFAULT_INDEX),
                "sha256": sha256_file(ROOT / DEFAULT_INDEX),
            },
            "kuzu_sha256": {
                run: index["entries"][f"kuzu:{run}"]["raw_sha256"]
                for _, run in DATASETS
            },
        },
        "protocol": {
            "n_seeds": N_SEEDS,
            "seeds": "1000+s",
            "split": "pair-level random 50/50 calibration/deployment",
        },
        "budgets": BUDGETS,
        "datasets": {ds: {m: agg[ds][m].tolist() for m in agg[ds]} for ds in agg},
    }, indent=2) + "\n")
    # Native single-column canvas so fonts render ~1:1 in the PDF.
    gg_style.apply_rc(font_size=7)
    fig, axes = plt.subplots(1, 4, figsize=(3.5, 0.62), sharey=True,
                             gridspec_kw={"wspace": 0.20})
    line_handles = None
    line_labels = None
    for ax, (ds_name, _) in zip(axes, DATASETS):
        r = agg[ds_name]
        local_handles = []
        local_labels = []
        for m, label, kw in [
            ("random",   "Random",         dict(color=gg_style.GRAY,       ls=":",  lw=0.9)),
            ("balanced", "Family-bal.",    dict(color=gg_style.BLUE_DARK,  ls="--", lw=0.9)),
            ("greedy",   "Greedy",         dict(color=gg_style.PINK_DARK,            lw=1.1)),
            ("oracle",   "Oracle (UB)",    dict(color=gg_style.GREEN_DARK, ls="-.", lw=0.9)),
        ]:
            (ln,) = ax.plot(BUDGETS, r[m], marker="o", markersize=1.8, **kw)
            local_handles.append(ln); local_labels.append(label)
        if line_handles is None:
            line_handles, line_labels = local_handles, local_labels
        ax.plot([0, 1], [0, 1], color=gg_style.GRAY_LIGHT, lw=0.6, zorder=0)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.set_title(ds_name, fontsize=7)
        ax.tick_params(labelsize=9)
        ax.set_xticks([0, 0.5, 1.0])
        ax.set_xticklabels(["0", ".5", "1"])
        ax.set_yticks([0, 0.5, 1.0])
        ax.set_xlabel("Budget (frac.)", fontsize=6.5)
        ax.grid(alpha=0.3, ls=":")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("Harm recall", fontsize=6.5)
    fig.tight_layout(w_pad=0.4)
    leg = fig.legend(line_handles, line_labels, loc="upper center", ncol=4,
                     bbox_to_anchor=(0.5, -0.46), bbox_transform=fig.transFigure,
                     fontsize=6, frameon=False, handlelength=1.5,
                     columnspacing=1.5, handletextpad=0.4)
    fig.savefig(OUT_FIG, dpi=400, bbox_inches="tight", pad_inches=0.025,
                bbox_extra_artists=[leg])
    print("wrote", OUT_FIG)
    # Print summary headline numbers.
    for ds_name, _ in DATASETS:
        i40 = BUDGETS.index(0.40)
        print(f"{ds_name:10s} @40%  random={agg[ds_name]['random'][i40]:.2f}  "
              f"balanced={agg[ds_name]['balanced'][i40]:.2f}  "
              f"greedy={agg[ds_name]['greedy'][i40]:.2f}")


if __name__ == "__main__":
    main()
