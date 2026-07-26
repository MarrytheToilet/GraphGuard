"""Drift contract data model.

Contract is a first-class object. It is NOT a thin reporting wrapper.
Each contract carries:
  - id, name, kind (invariance/monotonicity/bounded_drift)
  - scope: which intervention pairs it applies to (cause_family,
    semantic_class, operator filter)
  - metric: maps (base_edges, cf_edges) -> float in [0,1]
  - direction: "min" (metric must be >= threshold) or "max" (metric must be <= threshold)
  - threshold and population budget alpha (sensitivity sweep also reported)
  - optional query id or gold requirement for specialized evaluators

A check produces a ContractResult with per-pair observations, pass/fail,
violation_rate, severity, and family-level attribution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable, Optional


class ContractKind(str, Enum):
    INVARIANCE = "invariance"          # metric should stay near 1.0 (or 0.0)
    MONOTONICITY = "monotonicity"      # metric should move in expected direction
    BOUNDED_DRIFT = "bounded_drift"    # |metric| should not exceed bound


@dataclass
class PairObservation:
    """One (base, cf) extraction pair contributing to a contract check."""
    document_id: str
    intervention_id: str
    cause_family: str
    semantic_class: str
    operator: str
    metric: float
    passed: bool


@dataclass
class ContractResult:
    contract_id: str
    name: str
    kind: ContractKind
    scope: dict
    threshold: float
    direction: str
    alpha: float
    min_pairs: int
    n_pairs: int
    n_pass: int
    n_fail: int
    violation_rate: float
    severity_mean: float            # mean shortfall vs threshold among failing pairs
    severity_p95: float
    metric_mean: float
    metric_median: float
    by_family: dict                 # family -> {n, violation_rate, mean_metric}
    by_query: dict = field(default_factory=dict)  # only for query-scoped contracts
    threshold_sensitivity: dict = field(default_factory=dict)  # alt thresholds -> violation_rate
    examples: list = field(default_factory=list)  # up to N example violations
    notes: str = ""

    def verdict(self) -> str:
        if self.n_pairs < self.min_pairs:
            return "INCONCLUSIVE"
        return "VIOLATED" if self.violation_rate > self.alpha else "SATISFIED"

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()}
        d["kind"] = self.kind.value
        d["verdict"] = self.verdict()
        # Make scope JSON-safe (sets → sorted lists)
        if isinstance(d.get("scope"), dict):
            d["scope"] = {
                k: (sorted(v) if isinstance(v, (set, frozenset)) else v)
                for k, v in d["scope"].items()
            }
        return d


@dataclass
class Contract:
    id: str
    name: str
    kind: ContractKind
    scope: dict                                # {cause_family, semantic_class, operator_in}
    direction: str                             # "min" or "max"
    threshold: float
    metric_fn: Callable                        # (base_edges, cf_edges, ctx?) -> float
    alpha: float = 0.20                        # maximum permitted pair-level violation rate
    min_pairs: int = 1                         # fewer observations -> inconclusive
    description: str = ""
    query_scoped: bool = False                 # if True, metric_fn signature is (base_edges, cf_edges, query_name)
    query_id: Optional[str] = None              # Q3 / Q5 / Q6 / Q7 for query-scoped contracts
    needs_gold: bool = False                    # metric consumes the per-document gold edge set
    sensitivity_thresholds: tuple = (0.5, 0.7, 0.8, 0.9)

    def applies(self, cause_family: str, semantic_class: str, operator: str,
                description: str = "") -> bool:
        s = self.scope or {}
        if "cause_family_in" in s and cause_family not in s["cause_family_in"]:
            return False
        if "semantic_class_in" in s and semantic_class not in s["semantic_class_in"]:
            return False
        if "operator_in" in s and operator not in s["operator_in"]:
            return False
        if "operator_prefix" in s and not (operator or "").startswith(s["operator_prefix"]):
            return False
        d = (description or "").lower()
        if "description_substring_in" in s:
            needles = [str(x).lower() for x in s["description_substring_in"]]
            if not any(n in d for n in needles):
                return False
        if "description_substring_not_in" in s:
            needles = [str(x).lower() for x in s["description_substring_not_in"]]
            if any(n in d for n in needles):
                return False
        return True

    def passes(self, metric_value: float) -> bool:
        if self.direction == "min":
            return metric_value >= self.threshold
        return metric_value <= self.threshold

    def shortfall(self, metric_value: float) -> float:
        """How far the metric is on the wrong side of the threshold (>=0)."""
        if self.direction == "min":
            return max(0.0, self.threshold - metric_value)
        return max(0.0, metric_value - self.threshold)
