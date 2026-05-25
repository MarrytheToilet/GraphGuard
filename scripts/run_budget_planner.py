"""Budget-aware contract planner experiment.

Simulates choosing which counterfactual extractions to materialize under a
budget. Compares random sampling, family-balanced round-robin, and a
family-prior greedy planner against a full endpoint-union plan.

Metric: harm-recall = (harmful pairs evaluated / total harmful), as a function
of fraction-of-full extraction budget.

Pair records come from the existing Kuzu N=300 runs (no new LLM calls).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from graphguard.viz import style as gg_style  # noqa: F401

DATASETS = [
    ("DocRED",    "docred__deepseek-v4-flash__300d"),
    ("Re-DocRED", "redocred__deepseek-v4-flash__300d"),
    ("SciERC",    "scierc__deepseek-v4-flash__100d"),
    ("BC5CDR",    "cdr__deepseek-v4-flash__300d"),
]
OUT_FIG = Path("assets/figures/fig_budget_planner.png")
OUT_JSON = Path("reports/cross_run/budget_planner.json")

BUDGETS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
N_SEEDS = 50


def load_pairs(run):
    j = json.loads(Path(f"reports/cross_run/e2e_kuzu_case_{run}__N300.json").read_text())
    out = []
    for r in j["pair_records"]:
        out.append({
            "family": r.get("family", "unknown"),
            "harmful": bool(r.get("harmful", False)),
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
    # Persist numeric results.
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "budgets": BUDGETS,
        "datasets": {ds: {m: agg[ds][m].tolist() for m in agg[ds]} for ds in agg},
    }, indent=2))
    gg_style.apply_rc(font_size=10)
    fig, axes = plt.subplots(1, 4, figsize=(7.6, 2.6), sharey=True)
    line_handles = None
    line_labels = None
    for ax, (ds_name, _) in zip(axes, DATASETS):
        r = agg[ds_name]
        local_handles = []
        local_labels = []
        for m, label, kw in [
            ("random",   "Random",         dict(color=gg_style.GRAY,       ls=":",  lw=1.2)),
            ("balanced", "Family-bal.",    dict(color=gg_style.BLUE_DARK,  ls="--", lw=1.2)),
            ("greedy",   "Greedy",         dict(color=gg_style.PINK_DARK,            lw=1.5)),
            ("oracle",   "Oracle (UB)",    dict(color=gg_style.GREEN_DARK, ls="-.", lw=1.2)),
        ]:
            (ln,) = ax.plot(BUDGETS, r[m], marker="o", markersize=3.4, **kw)
            local_handles.append(ln); local_labels.append(label)
        if line_handles is None:
            line_handles, line_labels = local_handles, local_labels
        ax.plot([0, 1], [0, 1], color=gg_style.GRAY_LIGHT, lw=0.6, zorder=0)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.set_title(ds_name, fontsize=11, fontweight="bold")
        ax.tick_params(labelsize=9)
        ax.set_xticks([0, 0.5, 1.0])
        ax.set_yticks([0, 0.5, 1.0])
        ax.set_xlabel("Budget (frac.)", fontsize=10)
        ax.grid(alpha=0.3, ls=":")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("Harm recall", fontsize=10)
    fig.legend(line_handles, line_labels, loc="lower center", ncol=4,
               fontsize=9.5, frameon=False, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(w_pad=0.4)
    fig.savefig(OUT_FIG, dpi=200, bbox_inches="tight")
    print("wrote", OUT_FIG)
    # Print summary headline numbers.
    for ds_name, _ in DATASETS:
        i40 = BUDGETS.index(0.40)
        print(f"{ds_name:10s} @40%  random={agg[ds_name]['random'][i40]:.2f}  "
              f"balanced={agg[ds_name]['balanced'][i40]:.2f}  "
              f"greedy={agg[ds_name]['greedy'][i40]:.2f}")


if __name__ == "__main__":
    main()
