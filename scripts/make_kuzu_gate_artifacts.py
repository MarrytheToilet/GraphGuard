"""Build the release-gate table and threshold risk--coverage curve."""
from __future__ import annotations
import random
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from graphguard.viz import style as gg_style  # noqa: F401
from graphguard.formal_artifacts import load_formal_kuzu

ROOT = Path(__file__).resolve().parents[1]

DATASETS = [
    ("DocRED",    "docred__deepseek-v4-flash__300d"),
    ("Re-DocRED", "redocred__deepseek-v4-flash__300d"),
    ("SciERC",    "scierc__deepseek-v4-flash__100d"),
    ("BC5CDR",    "cdr__deepseek-v4-flash__300d"),
]
OUT_TABLE = Path("reports/cross_run/tab_e2ekuzu_v2.tex")
OUT_FIG = Path("assets/figures/fig_riskcoverage.png")

TAU_GRAPH_DEFAULT = 0.45
TAU_QUERY_DEFAULT = 0.70


def load_pairs(run: str):
    artifact = load_formal_kuzu(ROOT, run)
    pairs = []
    for record in artifact["per_pair"]:
        pairs.append({
            "run_id": record["run_id"],
            "doc": record["document_id"],
            "family": record["cause_family"],
            "graph_drift": float(record["graph_drift"]),
            "max_dq": float(record["max_answer_drift"]),
            "mean_abs_delta_f1": float(record["mean_delta_f1_abs"]),
            "mean_df1_signed": float(record["mean_delta_f1_signed"]),
            "harmful": float(record["mean_delta_f1_signed"]) > 0.05,
        })
    return pairs


def gate_metrics(pairs, blocked_mask):
    n = len(pairs)
    n_blocked = sum(blocked_mask)
    n_published = n - n_blocked
    harm_total = sum(p["harmful"] for p in pairs)
    benign_total = n - harm_total
    harm_blocked = sum(1 for p, b in zip(pairs, blocked_mask) if b and p["harmful"])
    benign_blocked = n_blocked - harm_blocked
    harm_published = harm_total - harm_blocked
    pub_harm_rate = (harm_published / n_published) if n_published else 0.0
    harm_recall = (harm_blocked / harm_total) if harm_total else 0.0
    harm_precision = (harm_blocked / n_blocked) if n_blocked else 0.0
    false_block_rate = (benign_blocked / benign_total) if benign_total else 0.0
    fidelity = [
        1.0 - p["mean_abs_delta_f1"]
        for p, b in zip(pairs, blocked_mask) if not b
    ]
    mean_fidelity = (sum(fidelity) / len(fidelity)) if fidelity else 0.0
    # Cluster-bootstrap 95% CIs by document. Multiple perturbation pairs from
    # one document are correlated and must travel together in a resample.
    rng = np.random.default_rng(0)
    n_boot = 1000
    published = [
        p for p, blocked in zip(pairs, blocked_mask) if not blocked
    ]
    by_doc = {}
    for pair in published:
        by_doc.setdefault(pair["doc"], []).append(pair)
    docs = sorted(by_doc)
    if docs:
        boot_pub_harm = []
        boot_fidelity = []
        for _ in range(n_boot):
            sampled_docs = rng.choice(docs, size=len(docs), replace=True)
            sample = [
                pair
                for doc in sampled_docs
                for pair in by_doc[doc]
            ]
            boot_pub_harm.append(np.mean([p["harmful"] for p in sample]))
            boot_fidelity.append(np.mean([
                1.0 - p["mean_abs_delta_f1"] for p in sample
            ]))
        pub_harm_lo, pub_harm_hi = np.quantile(boot_pub_harm, [0.025, 0.975])
        fidelity_lo, fidelity_hi = np.quantile(
            boot_fidelity, [0.025, 0.975]
        )
    else:
        pub_harm_lo = pub_harm_hi = 0.0
        fidelity_lo = fidelity_hi = 0.0
    return {
        "published_pct": 100.0 * n_published / n,
        "blocked_pct":   100.0 * n_blocked / n,
        "harm_recall":   harm_recall,
        "harm_precision": harm_precision,
        "false_block_rate": false_block_rate,
        "published_harmful_rate": pub_harm_rate,
        "pub_harm_ci": (float(pub_harm_lo), float(pub_harm_hi)),
        "f1_fidelity": mean_fidelity,
        "f1_fidelity_ci": (float(fidelity_lo), float(fidelity_hi)),
    }


def policy_publish_all(pairs):
    return [False] * len(pairs)


def policy_graph_only(pairs, tau_g):
    return [p["graph_drift"] >= tau_g for p in pairs]


def policy_graphguard(pairs, tau_g, tau_q):
    return [(p["graph_drift"] >= tau_g) or (p["max_dq"] >= tau_q) for p in pairs]


def policy_random(pairs, block_rate, seed=0):
    """Block exactly the requested number of pairs, selected uniformly."""
    rng = random.Random(seed)
    n_blocked = round(block_rate * len(pairs))
    blocked = set(rng.sample(range(len(pairs)), n_blocked))
    return [i in blocked for i in range(len(pairs))]


def fmt(x, pct=False):
    return (f"{100*x:.0f}\\%" if pct else f"{x:.2f}")


def build_table():
    L = []
    L.append(r"\begin{table*}[t]")
    L.append(r"\centering\small")
    L.append(r"\caption{End-to-end Kuzu ingestion guard at $N{=}300$ pairs per corpus. \emph{Publish-all} ingests every extracted graph; \emph{Graph-only} blocks when typed-edge Jaccard drift $\geq\tau_g{=}0.45$; \emph{GraphGuard} additionally blocks when any workload query has decision-time gold-free answer-set Jaccard drift $\geq\tau_q{=}0.70$; \emph{Random} is matched to GraphGuard's block rate. Harm is a directional regression in mean per-query $F_1$ ($f_1^{\mathrm{base}}{-}f_1^{\mathrm{cf}}>0.05$). F1Fid is $1-\operatorname{mean}_Q|F_1^{\mathrm{base}}-F_1^{\mathrm{cf}}|$, a fidelity measure rather than absolute task utility. CIs cluster-bootstrap documents ($1{,}000$ resamples).}")
    L.append(r"\label{tab:e2ekuzu}")
    L.append(r"\begin{tabular}{llcccccll}")
    L.append(r"\toprule")
    L.append(r"Dataset & Policy & Pub.\% & Blk.\% & HarmRec. & HarmPrec. & FalseBlk. & Pub.HarmRate [CI] & F1Fid. [CI] \\")
    L.append(r"\midrule")
    for ds_name, run in DATASETS:
        pairs = load_pairs(run)
        rows = []
        m_pub = gate_metrics(pairs, policy_publish_all(pairs))
        rows.append(("Publish-all", m_pub))
        m_g  = gate_metrics(pairs, policy_graph_only(pairs, TAU_GRAPH_DEFAULT))
        rows.append(("Graph-only gate", m_g))
        gg_mask = policy_graphguard(pairs, TAU_GRAPH_DEFAULT, TAU_QUERY_DEFAULT)
        m_gg = gate_metrics(pairs, gg_mask)
        rows.append(("GraphGuard", m_gg))
        block_rate = sum(gg_mask) / len(pairs)
        m_r  = gate_metrics(pairs, policy_random(pairs, block_rate, seed=0))
        rows.append(("Random (matched)", m_r))
        for i, (name, m) in enumerate(rows):
            ds_cell = ds_name if i == 0 else ""
            ph_lo, ph_hi = m["pub_harm_ci"]
            ut_lo, ut_hi = m["f1_fidelity_ci"]
            L.append(
                f"{ds_cell} & {name} & "
                f"{m['published_pct']:.0f} & {m['blocked_pct']:.0f} & "
                f"{m['harm_recall']:.2f} & {m['harm_precision']:.2f} & "
                f"{m['false_block_rate']:.2f} & "
                f"{m['published_harmful_rate']:.2f} [{ph_lo:.2f},{ph_hi:.2f}] & "
                f"{m['f1_fidelity']:.2f} [{ut_lo:.2f},{ut_hi:.2f}] \\\\"
            )
        L.append(r"\midrule")
    L.pop()
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    L.append(r"\end{table*}")
    OUT_TABLE.parent.mkdir(parents=True, exist_ok=True)
    OUT_TABLE.write_text("\n".join(L) + "\n")
    print("wrote", OUT_TABLE)


def risk_coverage_curve(pairs, score_fn):
    """Sweep deployable thresholds without splitting equal-score groups."""
    scored = [(score_fn(p), p) for p in pairs]
    scored.sort(key=lambda item: item[0])
    n = len(scored)
    pts = []
    k = 0
    while k < n:
        score = scored[k][0]
        while (
            k < n
            and abs(scored[k][0] - score) <= 1e-12
        ):
            k += 1
        published = scored[:k]
        n_pub = len(published)
        harm_pub = sum(p["harmful"] for _, p in published)
        coverage = n_pub / n
        pub_harm = harm_pub / n_pub
        pts.append((coverage, pub_harm))
    return pts


def build_figure():
    # Native single-column canvas so fonts render ~1:1 in the PDF.
    gg_style.apply_rc(font_size=7)
    fig, axes = plt.subplots(1, 4, figsize=(3.5, 0.64), sharey=True,
                             gridspec_kw={"wspace": 0.20})
    for ax, (ds_name, run) in zip(axes, DATASETS):
        pairs = load_pairs(run)
        n = len(pairs)
        base_harm_rate = sum(p["harmful"] for p in pairs) / n
        g_pts = risk_coverage_curve(pairs, lambda p: p["graph_drift"])
        scale = TAU_GRAPH_DEFAULT / TAU_QUERY_DEFAULT
        gg_pts = risk_coverage_curve(pairs, lambda p: max(p["graph_drift"], p["max_dq"] * scale))
        rng = np.random.default_rng(0)
        rand_scores = rng.random(n).tolist()
        r_pts = risk_coverage_curve(pairs, lambda p, _it=iter(rand_scores): next(_it))
        line_handles = []
        line_labels = []
        for pts, label, kw in [
            (r_pts,  "Random",      dict(color=gg_style.GRAY,      ls=":",  lw=1.2)),
            (g_pts,  "Graph-only",  dict(color=gg_style.BLUE_DARK,           lw=1.4)),
            (gg_pts, "GraphGuard",  dict(color=gg_style.PINK_DARK,           lw=1.4)),
        ]:
            xs = [c for c, _ in pts]
            ys = [h for _, h in pts]
            (ln,) = ax.plot(xs, ys, **kw)
            line_handles.append(ln); line_labels.append(label)
        ax.axhline(base_harm_rate, color=gg_style.BLACK, ls="--", lw=0.6, alpha=0.5)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, max(0.5, base_harm_rate * 1.2))
        ax.set_title(ds_name, fontsize=7)
        ax.tick_params(labelsize=6)
        ax.set_xticks([0, 0.5, 1.0])
        ax.set_xticklabels(["0", ".5", "1"])
        ax.set_xlabel("Pub. coverage", fontsize=6.5)
        ax.grid(alpha=0.3, ls=":")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("Pub. harm rate", fontsize=6.5)
    fig.tight_layout()
    leg = fig.legend(line_handles, line_labels, loc="upper center", ncol=3,
                     bbox_to_anchor=(0.5, -0.46), bbox_transform=fig.transFigure,
                     fontsize=6, frameon=False, handlelength=1.5,
                     columnspacing=1.5, handletextpad=0.4)
    fig.savefig(OUT_FIG, dpi=400, bbox_inches="tight", pad_inches=0.025,
                bbox_extra_artists=[leg])
    print("wrote", OUT_FIG)


if __name__ == "__main__":
    build_table()
    build_figure()
