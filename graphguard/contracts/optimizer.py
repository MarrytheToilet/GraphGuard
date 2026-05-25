"""Budget-aware contract execution optimizer.

Given a stream of candidate (pair, contract) checks, an audit budget B (max
number of pair extractions), and per-pair side-information, select an ordered
subset that maximises detection of harmful regressions.

The selector combines four signals:

  - workload-aware priority   w_w  (downstream query coverage of pair's doc)
  - history-aware priority    w_h  (prior mean severity of pair's family)
  - reuse-aware priority      w_r  (#contracts sharing the pair's endpoints)
  - sequential early stopping       (Wilson lower bound on family violation rate)

Pure-Python, no LLM calls; the budget simulation in
Replays from an existing paired-view stream (e.g. a recorded run).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Iterable, List, Dict, Optional, Sequence
import math


def wilson_lcb(p: float, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    rad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - rad)


@dataclass
class PairCandidate:
    pair_id: str
    family: str
    doc_id: str
    workload_weight: float = 1.0  # how many queries touch this doc
    reuse_weight: float = 1.0     # how many contracts can reuse this materialization
    history_severity: float = 0.0 # prior mean drift for this family
    cost: float = 1.0             # extraction cost units
    graph_drift: float = 0.0      # per-pair edge-level drift (used by GraphOnlyPrioritySelector)


@dataclass
class SelectionResult:
    order: List[str] = field(default_factory=list)        # pair_ids in chosen order
    skipped: List[str] = field(default_factory=list)      # skipped due to early stopping
    family_states: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self):
        return {
            "n_selected": len(self.order),
            "n_skipped": len(self.skipped),
            "order": self.order,
            "family_states": self.family_states,
        }


class BudgetAwareSelector:
    """Greedy budget-aware selector with optional Wilson-CI family stopping.

    Parameters
    ----------
    budget : float
        Total cost units. The selector stops once cumulative cost > budget.
    alpha_workload, alpha_history, alpha_reuse : float
        Weights on the three priority signals; the priority of a pair is
        ``alpha_workload * w_w + alpha_history * w_h + alpha_reuse * w_r``.
    family_stop : bool
        If True, once a family's Wilson LCB on violation rate clears
        ``family_threshold`` (e.g. 0.20 = contract budget), further pairs from
        that family are skipped.
    sequential_observations :
        Optional callable ``(pair_id) -> bool`` returning the observed
        violation outcome after extraction; used by the simulator to update
        family Wilson statistics. Must be deterministic.
    """

    def __init__(self,
                 budget: float,
                 alpha_workload: float = 1.0,
                 alpha_history: float = 1.0,
                 alpha_reuse: float = 1.0,
                 family_stop: bool = True,
                 family_threshold: float = 0.20,
                 min_family_n: int = 25):
        self.budget = budget
        self.alpha_w = alpha_workload
        self.alpha_h = alpha_history
        self.alpha_r = alpha_reuse
        self.family_stop = family_stop
        self.family_threshold = family_threshold
        self.min_family_n = min_family_n

    def priority(self, c: PairCandidate) -> float:
        return (self.alpha_w * c.workload_weight
                + self.alpha_h * c.history_severity
                + self.alpha_r * c.reuse_weight)

    def select(self,
               candidates: Sequence[PairCandidate],
               observe: Optional[callable] = None) -> SelectionResult:
        order = sorted(candidates, key=self.priority, reverse=True)
        result = SelectionResult()
        cost = 0.0
        family_pos = defaultdict(int)
        family_n   = defaultdict(int)
        family_stopped = set()
        for c in order:
            if cost + c.cost > self.budget:
                result.skipped.append(c.pair_id)
                continue
            if self.family_stop and c.family in family_stopped:
                result.skipped.append(c.pair_id)
                continue
            result.order.append(c.pair_id)
            cost += c.cost
            if observe is not None:
                violated = bool(observe(c.pair_id))
                family_n[c.family] += 1
                if violated:
                    family_pos[c.family] += 1
                n = family_n[c.family]
                if self.family_stop and n >= self.min_family_n:
                    p = family_pos[c.family] / n
                    if wilson_lcb(p, n) > self.family_threshold:
                        family_stopped.add(c.family)
        for fam, n in family_n.items():
            p = family_pos[fam] / n if n else 0.0
            result.family_states[fam] = {
                "n": n, "pos": family_pos[fam],
                "p": round(p, 4),
                "wilson_lcb": round(wilson_lcb(p, n), 4),
                "stopped": fam in family_stopped,
            }
        return result


class RandomSelector:
    """Uniform-random baseline: shuffle and take pairs until budget exhausted."""
    def __init__(self, budget: float, seed: int = 0):
        self.budget = budget
        self.seed = seed

    def select(self, candidates: Sequence[PairCandidate], observe=None) -> SelectionResult:
        import random
        rng = random.Random(self.seed)
        order = list(candidates); rng.shuffle(order)
        result = SelectionResult()
        cost = 0.0
        for c in order:
            if cost + c.cost > self.budget:
                result.skipped.append(c.pair_id); continue
            result.order.append(c.pair_id); cost += c.cost
        return result


class RoundRobinSelector:
    """Round-robin across families: ensures coverage but ignores priorities."""
    def __init__(self, budget: float):
        self.budget = budget

    def select(self, candidates: Sequence[PairCandidate], observe=None) -> SelectionResult:
        by_fam = defaultdict(list)
        for c in candidates: by_fam[c.family].append(c)
        fams = list(by_fam.keys())
        idx = {f: 0 for f in fams}
        result = SelectionResult()
        cost = 0.0
        progress = True
        while progress and cost < self.budget:
            progress = False
            for f in fams:
                if idx[f] >= len(by_fam[f]): continue
                c = by_fam[f][idx[f]]; idx[f] += 1
                if cost + c.cost > self.budget:
                    result.skipped.append(c.pair_id); continue
                result.order.append(c.pair_id); cost += c.cost
                progress = True
        return result


class GraphOnlyPrioritySelector:
    """Rank pairs by per-pair graph-level drift (largest first).

    Models the natural baseline of an operator who triages by edge-level
    disagreement only, ignoring workload coverage and family reuse. Pairs whose
    graph_drift is unknown are deprioritised to the end.
    """
    def __init__(self, budget: float):
        self.budget = budget

    def select(self, candidates: Sequence[PairCandidate], observe=None) -> SelectionResult:
        def key(c):
            return getattr(c, "graph_drift", 0.0)
        order = sorted(candidates, key=key, reverse=True)
        result = SelectionResult()
        cost = 0.0
        for c in order:
            if cost + c.cost > self.budget:
                result.skipped.append(c.pair_id); continue
            result.order.append(c.pair_id); cost += c.cost
        return result


class HistoryOnlySelector:
    """Rank pairs by family historical severity only (no workload / reuse).

    Equivalent to ``BudgetAwareSelector`` with alpha_w = alpha_r = 0; surfaced
    as a named baseline so ablation rows are explicit in the comparison table.
    """
    def __init__(self, budget: float):
        self.budget = budget

    def select(self, candidates: Sequence[PairCandidate], observe=None) -> SelectionResult:
        order = sorted(candidates, key=lambda c: c.history_severity, reverse=True)
        result = SelectionResult()
        cost = 0.0
        for c in order:
            if cost + c.cost > self.budget:
                result.skipped.append(c.pair_id); continue
            result.order.append(c.pair_id); cost += c.cost
        return result
