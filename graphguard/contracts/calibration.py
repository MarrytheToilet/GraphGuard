"""Contract threshold calibration as a first-class system module.

Given:
  * a stream of paired views (each with a drift metric `m` and a downstream
    utility-regression magnitude `u`),
  * a harmful-regression rule `u_thresh` (default 0.05),
  * a service-level objective on either recall floor, alarm budget, or F1,

we return the threshold `tau` that satisfies the SLO and report the realised
operating point (alarm rate, precision, recall, F1).

The module is intentionally side-effect free; it accepts plain Python iterables
of dicts (or tuples) and emits a `CalibrationResult` so it can be invoked at
ingestion time from a runner, a CLI, or a notebook.

Modes
-----
* ``recall_floor``: smallest ``tau`` whose recall >= ``target``.
* ``alarm_budget``: largest ``tau`` whose alarm rate <= ``target``.
* ``youden``: ``tau`` maximising recall - alarm_rate (Youden's J on harm).
* ``f1``: ``tau`` maximising harmful-regression F1.
* ``utility``: ``tau`` maximising ``lambda * recall - (1 - lambda) * alarm``.

Direction
---------
``direction='max'`` (default) means alarm fires when ``m > tau`` (drift / loss
metric). ``direction='min'`` means alarm fires when ``m < tau`` (similarity
metric); the search reverses sign internally.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Iterable, Sequence, Tuple, Optional


@dataclass
class CalibrationResult:
    mode: str
    target: float
    direction: str
    tau: float
    alarm_rate: float
    precision: float
    recall: float
    f1: float
    n_pairs: int
    harmful_base_rate: float

    def to_dict(self) -> dict:
        return asdict(self)


def _confusion(flags: Sequence[bool], harm: Sequence[bool]):
    tp = fp = fn = tn = 0
    for f, h in zip(flags, harm):
        if f and h: tp += 1
        elif f and not h: fp += 1
        elif not f and h: fn += 1
        else: tn += 1
    n = tp + fp + fn + tn
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec  = tp / (tp + fn) if (tp + fn) else 0.0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    alarm = (tp + fp) / n if n else 0.0
    return alarm, prec, rec, f1


def calibrate_threshold(
    pairs: Iterable[Tuple[float, float]],
    *,
    mode: str = "f1",
    target: float = 0.0,
    direction: str = "max",
    u_thresh: float = 0.05,
    lam: float = 0.5,
) -> CalibrationResult:
    """Calibrate a contract threshold from paired (m, u) observations.

    Parameters
    ----------
    pairs : iterable of (metric, utility_regression) tuples.
    mode  : one of {"recall_floor", "alarm_budget", "youden", "f1", "utility"}.
    target: SLO target (interpretation depends on mode).
    direction: "max" (alarm if m > tau) or "min" (alarm if m < tau).
    u_thresh: harm threshold; harmful if |u| > u_thresh.
    lam   : tradeoff weight in "utility" mode.
    """
    obs = [(float(m), abs(float(u))) for m, u in pairs]
    if not obs:
        raise ValueError("calibrate_threshold: empty pairs")
    harm = [u > u_thresh for _, u in obs]
    base = sum(harm) / len(harm)

    metrics = sorted({m for m, _ in obs})
    # candidate thresholds bracket each unique value
    cands = [metrics[0] - 1e-9] + [
        (metrics[i] + metrics[i + 1]) / 2 for i in range(len(metrics) - 1)
    ] + [metrics[-1] + 1e-9]

    if direction not in ("max", "min"):
        raise ValueError("direction must be 'max' or 'min'")

    def flag_at(tau: float):
        if direction == "max":
            return [m > tau for m, _ in obs]
        return [m < tau for m, _ in obs]

    best_tau = cands[0]
    best_score = float("-inf")
    best_alarm = best_prec = best_rec = best_f1 = 0.0

    def score(alarm, prec, rec, f1):
        if mode == "recall_floor":
            # smallest tau s.t. rec >= target; among feasible, prefer min alarm
            if rec >= target:
                return -alarm  # higher = better
            return float("-inf")
        if mode == "alarm_budget":
            if alarm <= target:
                return rec  # maximise recall under budget
            return float("-inf")
        if mode == "youden":
            return rec - alarm
        if mode == "f1":
            return f1
        if mode == "utility":
            return lam * rec - (1 - lam) * alarm
        raise ValueError(f"unknown mode {mode!r}")

    for tau in cands:
        flags = flag_at(tau)
        alarm, prec, rec, f1 = _confusion(flags, harm)
        s = score(alarm, prec, rec, f1)
        if s > best_score:
            best_score = s
            best_tau, best_alarm, best_prec, best_rec, best_f1 = (
                tau, alarm, prec, rec, f1,
            )

    if best_score == float("-inf"):
        # infeasible SLO -- fall back to closest feasible point
        if mode == "recall_floor":
            # take tau with maximum recall
            for tau in cands:
                flags = flag_at(tau)
                alarm, prec, rec, f1 = _confusion(flags, harm)
                if rec > best_rec:
                    best_tau, best_alarm, best_prec, best_rec, best_f1 = (
                        tau, alarm, prec, rec, f1,
                    )
        elif mode == "alarm_budget":
            for tau in cands:
                flags = flag_at(tau)
                alarm, prec, rec, f1 = _confusion(flags, harm)
                if alarm <= target and rec > best_rec:
                    best_tau, best_alarm, best_prec, best_rec, best_f1 = (
                        tau, alarm, prec, rec, f1,
                    )

    return CalibrationResult(
        mode=mode,
        target=target,
        direction=direction,
        tau=float(best_tau),
        alarm_rate=float(best_alarm),
        precision=float(best_prec),
        recall=float(best_rec),
        f1=float(best_f1),
        n_pairs=len(obs),
        harmful_base_rate=float(base),
    )


def calibrate_from_sla_report(report: dict, *, mode: str = "f1",
                              target: float = 0.0,
                              direction: str = "max",
                              u_thresh: float = 0.05) -> CalibrationResult:
    """Convenience wrapper for SLA JSONs that already contain (m, u) lists."""
    pairs = report.get("pairs")
    if pairs is None:
        raise ValueError("report missing 'pairs' field")
    return calibrate_threshold(
        ((p["m"], p["u"]) for p in pairs),
        mode=mode, target=target, direction=direction, u_thresh=u_thresh,
    )
