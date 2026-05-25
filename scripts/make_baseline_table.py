"""Emit LaTeX table comparing monitors at a matched alarm rate."""
from __future__ import annotations
import json
from pathlib import Path

DATASETS = [
    ("DocRED",    "docred__deepseek-v4-flash__300d"),
    ("Re-DocRED", "redocred__deepseek-v4-flash__300d"),
    ("SciERC",    "scierc__deepseek-v4-flash__100d"),
    ("BC5CDR",    "cdr__deepseek-v4-flash__300d"),
]
MONITORS = [
    ("confidence_inv",     "Confidence-only",      r"$1\times$"),
    ("min_confidence_inv", "Min-confidence",       r"$1\times$"),
    ("self_consistency",   "Self-consistency",     r"$5\times$"),
    ("graph_only_drift",   "Graph-only drift",     r"$2\times$"),
    ("contract_severity",  "GraphGuard contract",  r"$2\times$"),
]
TARGET = 0.30


def pick(sweep, rate):
    for row in sweep:
        if abs(row["target_alarm_rate"] - rate) < 1e-6:
            return row
    return None


def main():
    L = []
    L.append(r"\begin{table}[t]")
    L.append(r"\centering\small")
    L.append(r"\caption{Matched-alarm-rate baseline comparison at target alarm rate $0.30$ on the four primary runs. \emph{Harm label is gold-recall regression} $|\Delta\mathrm{recall}|>0.05$ on the same document; this is a stricter, extraction-utility harm definition than the query-level harm used in Table~\ref{tab:graphvsquery} and Table~\ref{tab:e2ekuzu}. Cost is relative LLM-extraction calls per flagged pair (confidence-only re-uses the base call; graph/contract monitors require one cf extraction; self-consistency uses $k{=}5$ base repeats). For Min-confidence and Self-consistency, the score distribution is too coarse (or base repeats too scarce) to hit $0.30$ exactly; we report the closest-achievable alarm rate. F1 of the best monitor per dataset is in bold.}")
    L.append(r"\label{tab:baselines}")
    L.append(r"\begin{tabular}{llccccc}")
    L.append(r"\toprule")
    L.append(r"Dataset & Monitor & Cost & Alarm & P & R & F1 \\")
    L.append(r"\midrule")
    for ds_name, run in DATASETS:
        path = Path(f"reports/cross_run/baselines_matched_{run}.json")
        if not path.exists():
            print("missing", path); continue
        j = json.loads(path.read_text())
        rows = []
        best_f1 = -1.0
        for key, name, cost in MONITORS:
            row = pick(j["by_monitor"][key], TARGET)
            if row is None:
                continue
            rows.append((key, name, cost, row))
            best_f1 = max(best_f1, row["f1"])
        for i, (key, name, cost, row) in enumerate(rows):
            ds_cell = ds_name if i == 0 else ""
            f1_cell = f"{row['f1']:.2f}"
            if row["f1"] == best_f1:
                f1_cell = r"\textbf{" + f1_cell + r"}"
            L.append(
                f"{ds_cell} & {name} & {cost} & "
                f"{row['alarm_rate']:.2f} & {row['precision']:.2f} & "
                f"{row['recall']:.2f} & {f1_cell} \\\\"
            )
        L.append(r"\midrule")
    L.pop()
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    L.append(r"\end{table}")
    Path("paper/tables/tab_baselines.tex").write_text("\n".join(L) + "\n")
    print("wrote paper/tables/tab_baselines.tex")


if __name__ == "__main__":
    main()
