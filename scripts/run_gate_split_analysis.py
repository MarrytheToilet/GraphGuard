#!/usr/bin/env python3
"""Calibration/deployment split analysis for the Kuzu release gate.

Addresses the selection-bias concern: the paper's operating point
(tau_g=0.45, tau_q=0.70) was chosen from the full-data risk--coverage
sweep and evaluated on the same N=300 pairs. Here we separate selection
from evaluation:

  1. Split each corpus 50/50 into calibration and deployment sets *by
     document* (md5 order, deterministic), so no document contributes
     pairs to both sides.
  2. On the calibration split, grid-search (tau_g, tau_q) and keep the
     pair that maximizes published coverage subject to a published-harm
     target of <= 0.05 (the paper's conservative target).
  3. Freeze the selected thresholds and report published-harm rate,
     paired-view F1 fidelity, coverage, and harm recall on the held-out
     deployment split, for graph-only and GraphGuard policies, next to
     publish-all as reference.

No new LLM calls: everything replays from the registered actual-Kuzu
N=300 artifacts.

Writes reports/cross_run/gate_split.json and prints a summary.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from graphguard.deployment_evidence import (
    DEFAULT_INDEX,
    load_artifact_index,
    load_kuzu_evidence,
)
from graphguard.sqlite_snapshot import sha256_file

ROOT = Path(__file__).resolve().parents[1]

DATASETS = [
    ("DocRED",    "docred__deepseek-v4-flash__300d"),
    ("Re-DocRED", "redocred__deepseek-v4-flash__300d"),
    ("SciERC",    "scierc__deepseek-v4-flash__100d"),
    ("BC5CDR",    "cdr__deepseek-v4-flash__300d"),
]
HARM_TARGET = 0.05
GRID = [round(0.05 * k, 2) for k in range(1, 20)]  # 0.05 .. 0.95
FULL_DATA_POINT = (0.45, 0.70)


def load_pairs(run: str):
    artifact = load_kuzu_evidence(ROOT, run)
    pairs = []
    for record in artifact["per_pair"]:
        pairs.append({
            "run_id": record["run_id"],
            "doc": record["document_id"],
            "graph_drift": float(record["graph_drift"]),
            "max_dq": float(record["max_answer_drift"]),
            "mean_abs_delta_f1": float(record["mean_delta_f1_abs"]),
            "harmful": float(record["mean_delta_f1_signed"]) > 0.05,
        })
    return pairs


def split_by_doc(pairs):
    docs = sorted({p["doc"] for p in pairs},
                  key=lambda d: hashlib.md5(d.encode()).hexdigest())
    calib_docs = set(docs[::2])
    calib = [p for p in pairs if p["doc"] in calib_docs]
    deploy = [p for p in pairs if p["doc"] not in calib_docs]
    return calib, deploy


def blocked_graphguard(pairs, tg, tq):
    return [(p["graph_drift"] >= tg) or (p["max_dq"] >= tq) for p in pairs]


def blocked_graph_only(pairs, tg):
    return [p["graph_drift"] >= tg for p in pairs]


def metrics(pairs, blocked):
    n = len(pairs)
    pub = [p for p, b in zip(pairs, blocked) if not b]
    n_pub = len(pub)
    harm_total = sum(p["harmful"] for p in pairs)
    harm_pub = sum(p["harmful"] for p in pub)
    harm_blocked = harm_total - harm_pub
    out = {
        "coverage": n_pub / n if n else 0.0,
        "pub_harm_rate": harm_pub / n_pub if n_pub else 0.0,
        "harm_recall": harm_blocked / harm_total if harm_total else 1.0,
        "f1_fidelity": (
            float(np.mean([1.0 - p["mean_abs_delta_f1"] for p in pub]))
            if pub else 0.0
        ),
        "n": n, "n_published": n_pub, "harm_total": harm_total,
    }
    if pub:
        rng = np.random.default_rng(0)
        by_doc = {}
        for pair in pub:
            by_doc.setdefault(pair["doc"], []).append(pair)
        docs = sorted(by_doc)
        boot = []
        for _ in range(1000):
            sampled_docs = rng.choice(docs, size=len(docs), replace=True)
            sample = [
                pair
                for doc in sampled_docs
                for pair in by_doc[doc]
            ]
            boot.append(np.mean([p["harmful"] for p in sample]))
        out["pub_harm_ci"] = [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]
    return out


def select_thresholds(calib, target=HARM_TARGET):
    """Max published coverage on the calibration split s.t. pub harm <= target."""
    best = None
    for tg in GRID:
        for tq in GRID:
            m = metrics(calib, blocked_graphguard(calib, tg, tq))
            if m["pub_harm_rate"] <= target:
                key = (m["coverage"], tg + tq)  # tie-break: laxer thresholds
                if best is None or key > best[0]:
                    best = (key, (tg, tq), m)
    return best[1], best[2]


def main() -> int:
    index = load_artifact_index(ROOT)
    report = {
        "artifact_type": "graphguard.gate_split_analysis",
        "artifact_version": 1,
        "sources": {
            "evidence_index": {
                "path": str(DEFAULT_INDEX),
                "sha256": sha256_file(ROOT / DEFAULT_INDEX),
            },
            "kuzu_sha256": {
                run: index["entries"][f"kuzu:{run}"]["raw_sha256"]
                for _, run in DATASETS
            },
        },
        "harm_target": HARM_TARGET,
        "split": "50/50 by document (md5 order)",
        "selection": "max coverage s.t. calibration pub-harm <= target",
        "confidence_intervals": "cluster bootstrap by document",
        "corpora": {},
    }
    for name, run in DATASETS:
        pairs = load_pairs(run)
        calib, deploy = split_by_doc(pairs)
        (tg, tq), m_cal = select_thresholds(calib)
        entry = {
            "n_calib": len(calib), "n_deploy": len(deploy),
            "selected": {"tau_g": tg, "tau_q": tq},
            "calibration": m_cal,
            "deploy_publish_all": metrics(deploy, [False] * len(deploy)),
            "deploy_graph_only": metrics(deploy, blocked_graph_only(deploy, tg)),
            "deploy_graphguard": metrics(deploy, blocked_graphguard(deploy, tg, tq)),
            "deploy_graphguard_paper_point": metrics(
                deploy, blocked_graphguard(deploy, *FULL_DATA_POINT)),
        }
        report["corpora"][name] = entry
        d = entry["deploy_graphguard"]
        pp = entry["deploy_graphguard_paper_point"]
        print(f"{name:10s} sel=({tg:.2f},{tq:.2f}) "
              f"calib_harm={m_cal['pub_harm_rate']:.3f} cov={m_cal['coverage']:.2f} | "
              f"deploy: harm={d['pub_harm_rate']:.3f} fid={d['f1_fidelity']:.3f} "
              f"cov={d['coverage']:.2f} rec={d['harm_recall']:.2f} | "
              f"paper-point deploy harm={pp['pub_harm_rate']:.3f} fid={pp['f1_fidelity']:.3f} | "
              f"publish-all harm={entry['deploy_publish_all']['pub_harm_rate']:.3f}")
    out = ROOT / "reports/cross_run/gate_split.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
