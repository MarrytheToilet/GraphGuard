"""Graph-only versus query-aware detection of workload-visible change.

The target is mean absolute per-query F1 change over the registered Q1--Q4
workload. The primary query-aware score therefore uses the corresponding
mean answer-set Jaccard drift. Maximum answer drift is retained as a
sensitivity score for policies that care whether any registered query changes,
including the separate Kuzu release-gate experiment.

All fixed-budget comparisons select exactly the same number of graph pairs.
Ties are resolved by a deterministic, label-blind hash of the pair ID.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.deployment_evidence import (  # noqa: E402
    DEFAULT_INDEX,
    load_artifact_index,
    load_downstream_evidence,
)
from graphguard.sqlite_snapshot import sha256_file  # noqa: E402

FIXED_REVIEW_BUDGETS = (0.30, 0.50, 0.70, 0.90)
BOOTSTRAP_DRAWS = 1000
BOOTSTRAP_SEED = 20260831


def confusion(flags, positive):
    tp = fp = fn = tn = 0
    for flag, label in zip(flags, positive):
        if flag and label:
            tp += 1
        elif flag and not label:
            fp += 1
        elif not flag and label:
            fn += 1
        else:
            tn += 1
    n = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "review_rate": (tp + fp) / n if n else 0.0,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def flags_at_count(scores, row_ids, n_review):
    """Select exactly ``n_review`` rows with a stable label-blind tie break."""
    n_review = max(0, min(len(scores), n_review))
    ranked = sorted(
        range(len(scores)),
        key=lambda index: (
            -scores[index],
            hashlib.sha256(row_ids[index].encode()).hexdigest(),
        ),
    )
    selected = set(ranked[:n_review])
    flags = [index in selected for index in range(len(scores))]
    boundary = scores[ranked[n_review - 1]] if n_review else float("inf")
    return flags, boundary


def rank_auc(labels, scores):
    """Mann--Whitney AUROC with average ranks for tied scores."""
    ordered = sorted(zip(scores, labels), key=lambda item: item[0])
    rank_sum_positive = 0.0
    index = 0
    while index < len(ordered):
        stop = index + 1
        while stop < len(ordered) and ordered[stop][0] == ordered[index][0]:
            stop += 1
        average_rank = ((index + 1) + stop) / 2.0
        rank_sum_positive += average_rank * sum(
            label for _, label in ordered[index:stop]
        )
        index = stop
    n_positive = sum(labels)
    n_negative = len(labels) - n_positive
    if not n_positive or not n_negative:
        raise ValueError("AUROC requires both classes")
    return (
        rank_sum_positive - n_positive * (n_positive + 1) / 2.0
    ) / (n_positive * n_negative)


def average_precision(labels, scores):
    """Non-interpolated average precision with tied scores grouped together."""
    n_positive = sum(labels)
    if not n_positive:
        raise ValueError("average precision requires a positive class")
    grouped = defaultdict(lambda: [0, 0])
    for label, score in zip(labels, scores):
        grouped[score][0] += int(label)
        grouped[score][1] += 1
    true_positive = selected = 0
    previous_recall = 0.0
    area = 0.0
    for score in sorted(grouped, reverse=True):
        positives, count = grouped[score]
        true_positive += positives
        selected += count
        recall = true_positive / n_positive
        precision = true_positive / selected
        area += (recall - previous_recall) * precision
        previous_recall = recall
    return area


def document_cluster_bootstrap(
    rows, labels, graph_scores, query_scores, seed_key
):
    by_document = defaultdict(list)
    for index, row in enumerate(rows):
        by_document[row["document_id"]].append(index)
    documents = sorted(by_document)
    seed_prefix = hashlib.sha256(seed_key.encode()).hexdigest()[:8]
    seed_offset = int(seed_prefix, 16)
    effective_seed = BOOTSTRAP_SEED + seed_offset
    rng = random.Random(effective_seed)
    differences = []
    for _ in range(BOOTSTRAP_DRAWS):
        indices = []
        for _ in documents:
            indices.extend(by_document[documents[rng.randrange(len(documents))]])
        sampled_labels = [labels[index] for index in indices]
        if not any(sampled_labels) or all(sampled_labels):
            continue
        differences.append(
            rank_auc(sampled_labels, [query_scores[index] for index in indices])
            - rank_auc(sampled_labels, [graph_scores[index] for index in indices])
        )
    differences.sort()
    if not differences:
        raise ValueError("document bootstrap produced no valid samples")
    lo = differences[int(0.025 * (len(differences) - 1))]
    hi = differences[int(0.975 * (len(differences) - 1))]
    return (
        [round(lo, 4), round(hi, 4)],
        len(differences),
        {
            "base_seed": BOOTSTRAP_SEED,
            "seed_key": seed_key,
            "sha256_prefix8": seed_prefix,
            "seed_offset": seed_offset,
            "effective_seed": effective_seed,
            "derivation": (
                "base_seed + int(SHA256(seed_key)[:8], 16)"
            ),
        },
    )


def score_summary(labels, scores):
    return {
        "auroc": round(rank_auc(labels, scores), 4),
        "average_precision": round(average_precision(labels, scores), 4),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--out")
    parser.add_argument("--change-threshold", type=float, default=0.05)
    args = parser.parse_args()

    artifact = load_downstream_evidence(ROOT, args.run)
    rows = [
        {
            "run_id": pair["run_id"],
            "document_id": pair["document_id"],
            "graph_drift": pair["graph_drift"],
            "query_mean": pair["mean_answer_drift"],
            "query_max": pair["max_answer_drift"],
            "mean_abs_delta_f1": pair["mean_delta_f1_abs"],
            "positive": pair["mean_delta_f1_abs"] > args.change_threshold,
        }
        for pair in artifact["per_pair"]
    ]
    labels = [row["positive"] for row in rows]
    graph_scores = [row["graph_drift"] for row in rows]
    mean_scores = [row["query_mean"] for row in rows]
    max_scores = [row["query_max"] for row in rows]
    row_ids = [row["run_id"] for row in rows]

    graph_summary = score_summary(labels, graph_scores)
    mean_summary = score_summary(labels, mean_scores)
    max_summary = score_summary(labels, max_scores)
    bootstrap_ci, valid_draws, bootstrap_seed = document_cluster_bootstrap(
        rows, labels, graph_scores, mean_scores, args.run
    )

    index = load_artifact_index(ROOT)
    out = {
        "artifact_type": "graphguard.graph_vs_query_ablation",
        "artifact_version": 2,
        "run": args.run,
        "source": {
            "evidence_index": {
                "path": str(DEFAULT_INDEX),
                "sha256": sha256_file(ROOT / DEFAULT_INDEX),
            },
            "downstream_sha256": index["entries"][
                f"downstream:{args.run}"
            ]["raw_sha256"],
        },
        "n_pairs": len(rows),
        "label_definition": (
            "mean absolute per-query gold-F1 change across registered Q1--Q4 "
            "> threshold"
        ),
        "change_threshold_delta_f1": args.change_threshold,
        "positive_base_rate": round(sum(labels) / len(labels), 4),
        "score_definitions": {
            "graph_only": "canonicalized typed-edge Jaccard drift",
            "query_mean": (
                "mean answer-set Jaccard drift across registered query instances; "
                "primary score for the mean-change target"
            ),
            "query_max": (
                "maximum answer-set Jaccard drift across registered query instances; "
                "sensitivity score for any-query change"
            ),
        },
        "decision_signal": (
            "scores use paired graph and answer sets; gold answers define only "
            "the offline evaluation label"
        ),
        "fixed_budget_ties": (
            "exact top-k selection; score ties broken by SHA-256(run_id) "
            "without target labels"
        ),
        "threshold_free": {
            "graph_only": graph_summary,
            "query_mean": mean_summary,
            "query_max": max_summary,
            "query_mean_minus_graph_auroc": {
                "difference": round(
                    mean_summary["auroc"] - graph_summary["auroc"], 4
                ),
                "document_cluster_bootstrap_ci95": bootstrap_ci,
                "requested_draws": BOOTSTRAP_DRAWS,
                "valid_draws": valid_draws,
                "rng": bootstrap_seed,
            },
        },
        "fixed_review_budgets": [],
    }

    for budget in FIXED_REVIEW_BUDGETS:
        n_review = round(budget * len(rows))
        graph_flags, graph_boundary = flags_at_count(
            graph_scores, row_ids, n_review
        )
        mean_flags, mean_boundary = flags_at_count(mean_scores, row_ids, n_review)
        max_flags, max_boundary = flags_at_count(max_scores, row_ids, n_review)
        graph_result = confusion(graph_flags, labels)
        mean_result = confusion(mean_flags, labels)
        max_result = confusion(max_flags, labels)
        out["fixed_review_budgets"].append({
            "review_budget": budget,
            "n_review": n_review,
            "score_boundary": {
                "graph_only": round(graph_boundary, 4),
                "query_mean": round(mean_boundary, 4),
                "query_max": round(max_boundary, 4),
            },
            "graph_only": graph_result,
            "query_mean": mean_result,
            "query_max": max_result,
            "query_mean_minus_graph_f1": round(
                mean_result["f1"] - graph_result["f1"], 4
            ),
            "query_max_minus_graph_f1": round(
                max_result["f1"] - graph_result["f1"], 4
            ),
            "mean_graph_selection_disagreement": sum(
                graph != query
                for graph, query in zip(graph_flags, mean_flags)
            ),
        })

    output = Path(args.out) if args.out else (
        ROOT / "reports" / "cross_run" / f"graph_vs_query_{args.run}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {output}: n_pairs={len(rows)} "
        f"positive_rate={out['positive_base_rate']:.3f}"
    )
    print(
        "  AUROC graph/query-mean/query-max: "
        f"{graph_summary['auroc']:.3f}/{mean_summary['auroc']:.3f}/"
        f"{max_summary['auroc']:.3f}"
    )
    print(
        "  query-mean minus graph F1: "
        + ", ".join(
            f"{row['review_budget']:.0%}={row['query_mean_minus_graph_f1']:+.3f}"
            for row in out["fixed_review_budgets"]
        )
    )


if __name__ == "__main__":
    main()
