"""Pluggable planners for selecting interventions under a budget.

Common interface:

    class Planner:
        name: str
        def choose(self, candidates, budget, *, conn=None) -> list[Candidate]: ...

`candidates` is a list of objects (or sqlite Row) exposing at least:
    target_type   -> 'sentence' | 'prompt_clause' | 'schema'
    operator      -> 'remove' | 'mask' | 'switch_schema'
    intervention_id, target_id, description

Each chosen candidate is assumed to cost 1 LLM call (one document-level rerun),
so `budget` is the maximum number of returned items.
"""
from __future__ import annotations

import random
import json
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


def _attr(c, key):
    if isinstance(c, dict):
        return c.get(key)
    try:
        return c[key]
    except Exception:
        return getattr(c, key, None)


def _filter(cands, target_type=None):
    if target_type is None:
        return list(cands)
    return [c for c in cands if _attr(c, "target_type") == target_type]


@dataclass
class _Base:
    name: str = "base"

    def choose(self, candidates, budget, *, conn=None):
        raise NotImplementedError


class ExhaustivePlanner(_Base):
    name = "exhaustive"

    def choose(self, candidates, budget, *, conn=None):
        cands = list(candidates)
        return cands if budget <= 0 else cands[: max(budget, len(cands))]


class RandomPlanner(_Base):
    name = "random"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def choose(self, candidates, budget, *, conn=None):
        cands = list(candidates)
        rng = random.Random(self.seed)
        rng.shuffle(cands)
        return cands[: budget]


class _OnlyPlanner(_Base):
    target = "sentence"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def choose(self, candidates, budget, *, conn=None):
        cands = _filter(candidates, self.target)
        rng = random.Random(self.seed)
        rng.shuffle(cands)
        return cands[: budget]


class SpanOnlyPlanner(_OnlyPlanner):
    name = "span_only"
    target = "sentence"


class PromptOnlyPlanner(_OnlyPlanner):
    name = "prompt_only"
    target = "prompt_clause"


class SchemaOnlyPlanner(_OnlyPlanner):
    name = "schema_only"
    target = "schema"


class GraphGuardPlanner(_Base):
    """Coarse-to-fine: schema variants & prompt ablations first (cheap, broad),
    then evidence-sentence interventions (broad signal of text causation),
    then mask before remove for sentences (gentler), then everything else.

    With a small budget this plays the role of "high-signal-first" scheduling.
    """
    name = "graphguard"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def _evidence_sentence_ids(self, conn, document_id):
        if conn is None:
            return set()
        try:
            out = set()
            for r in conn.execute(
                "SELECT evidence_sentence_ids_json FROM extracted_edges WHERE document_id = ?",
                (document_id,),
            ):
                if not r["evidence_sentence_ids_json"]:
                    continue
                try:
                    out.update(json.loads(r["evidence_sentence_ids_json"]))
                except Exception:
                    continue
            return out
        except Exception:
            return set()

    def _sentence_coverage(self, conn, document_id):
        if conn is None:
            return {}
        cov = {}
        try:
            for r in conn.execute(
                "SELECT evidence_sentence_ids_json FROM extracted_edges WHERE document_id = ?",
                (document_id,),
            ):
                if not r["evidence_sentence_ids_json"]:
                    continue
                for sid in json.loads(r["evidence_sentence_ids_json"]):
                    cov[sid] = cov.get(sid, 0) + 1
        except Exception:
            return {}
        return cov

    def choose(self, candidates, budget, *, conn=None):
        cands = list(candidates)
        if not cands:
            return []
        doc_id = _attr(cands[0], "document_id")
        evidence_ids = self._evidence_sentence_ids(conn, doc_id) if doc_id else set()
        coverage = self._sentence_coverage(conn, doc_id) if doc_id else {}

        def _priority(c) -> tuple[int, int, float]:
            t = _attr(c, "target_type")
            op = _attr(c, "operator")
            tid = _attr(c, "target_id")
            cost = float(_attr(c, "estimated_cost") or 1.0)
            util = 0.0
            # tier 0: schema variants (broadest impact)
            if t == "schema":
                util = 8.0 if str(tid).startswith(("drop:", "ambiguous:")) else 6.0
                return (0, 0, -util / cost)
            # tier 1: prompt clause ablations
            if t == "prompt_clause":
                prompt_weight = {
                    "C1_evidence_only": 5.0,
                    "C2_infer_implicit": 5.0,
                    "C3_use_schema": 4.0,
                    "C4_allow_other": 4.0,
                }.get(tid, 2.0)
                return (1, 0, -prompt_weight / cost)
            # tier 2: sentence interventions on evidence sentences (mask before remove)
            if t == "sentence" and tid in evidence_ids:
                util = 3.0 + coverage.get(tid, 0)
                return (2, 0 if op == "mask" else 1, -util / cost)
            # tier 3: sentence interventions on non-evidence sentences
            if t == "sentence":
                return (3, 0 if op == "mask" else 1, -0.5 / cost)
            return (9, 0, 0.0)

        rng = random.Random(self.seed)
        cands.sort(key=lambda c: (_priority(c), rng.random()))
        return cands[: budget]


class GreedyCostPlanner(_Base):
    """Cheapest-first scheduling. Picks interventions in ascending estimated_cost.

    This is the "cost myopic" baseline from README §15: chooses lots of cheap
    interventions, ignoring expected information value. Useful to show that
    GraphGuard's coarse-to-fine schedule beats blind cost minimization at
    fixed budget.
    """
    name = "greedy_cost"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def choose(self, candidates, budget, *, conn=None):
        cands = list(candidates)
        rng = random.Random(self.seed)
        cands.sort(key=lambda c: (float(_attr(c, "estimated_cost") or 1.0), rng.random()))
        return cands[: budget]


class AdaptivePlanner(_Base):
    """Probe → estimate yield → allocate → refine.

    Stage 1 (probe): pick one cheapest candidate from each ``cause_family``.
    Stage 2 (yield): from the recorded outcomes (`edge_outcomes` joined to
                     `counterfactual_runs`) estimate per-family change-rate
                     per token. This is "what we'd learn about the document
                     if we spend more of our budget on this family".
    Stage 3 (allocate): split the remaining budget proportional to yield.
    Stage 4 (refine): inside each family, pick the candidates whose recorded
                      group_id has the highest cumulative change.

    The planner is offline-replayable: when no recorded outcomes exist for a
    candidate it is treated as zero-yield, so the planner degrades to
    family-balanced sampling.
    """
    name = "adaptive_graphguard"

    CHANGE = ("TYPE_FLIP", "OBJECT_FLIP", "SUBJECT_FLIP", "DISAPPEARED", "AMBIGUOUS")

    def __init__(self, seed: int = 0, probes_per_family: int = 1,
                 probe_fraction: float = 0.34, min_budget_for_probes: int = 4,
                 yield_alpha: float = 1.5):
        self.seed = seed
        self.probes_per_family = max(1, int(probes_per_family))
        self.probe_fraction = probe_fraction
        self.min_budget_for_probes = min_budget_for_probes
        self.yield_alpha = yield_alpha

    def _family_yield(self, conn, document_id):
        if conn is None:
            return {}
        try:
            rows = conn.execute(
                """
                SELECT ic.cause_family AS family,
                       SUM(CASE WHEN eo.outcome_type IN ('TYPE_FLIP','OBJECT_FLIP',
                                                          'SUBJECT_FLIP','DISAPPEARED','AMBIGUOUS')
                                THEN 1 ELSE 0 END) AS changed,
                       COUNT(eo.outcome_id) AS total,
                       COALESCE(SUM(cfr.token_input + cfr.token_output), 0) AS tok
                FROM intervention_candidates ic
                JOIN counterfactual_runs cfr ON cfr.intervention_id = ic.intervention_id
                JOIN edge_outcomes eo ON eo.run_id = cfr.run_id
                WHERE ic.document_id = ?
                GROUP BY ic.cause_family
                """,
                (document_id,),
            ).fetchall()
        except Exception:
            return {}
        yields = {}
        for r in rows:
            fam = r["family"] or "unknown"
            tok = max(1.0, float(r["tok"] or 1.0))
            yields[fam] = float(r["changed"] or 0) / tok
        return yields

    def choose(self, candidates, budget, *, conn=None):
        cands = list(candidates)
        if not cands or budget <= 0:
            return []
        rng = random.Random(self.seed)

        by_family: dict[str, list] = {}
        for c in cands:
            fam = _attr(c, "cause_family") or _attr(c, "target_type") or "unknown"
            by_family.setdefault(fam, []).append(c)

        # Stage 1: probes — small fraction of budget, NOT one per family.
        # If budget too small to probe + refine, fall back to graphguard
        # priority (schema-first) to avoid wasting all of B on probing.
        n_families = len(by_family)
        if budget < self.min_budget_for_probes:
            # Use cheap-tier priority directly (skip probing)
            doc_id = _attr(cands[0], "document_id")
            yields = self._family_yield(conn, doc_id) if conn is not None else {}
            cands_sorted = sorted(
                cands,
                key=lambda c: (
                    -yields.get(_attr(c, "cause_family") or "", 0.0),
                    float(_attr(c, "estimated_cost") or 1.0),
                    rng.random(),
                ),
            )
            return cands_sorted[: budget]

        n_probes = max(1, min(n_families, int(round(budget * self.probe_fraction))))
        probes: list = []
        used: set = set()
        # Probe a rotating subset of families (cheapest first)
        sorted_families = sorted(by_family.keys())
        for fam in sorted_families[:n_probes]:
            lst_sorted = sorted(
                by_family[fam], key=lambda c: float(_attr(c, "estimated_cost") or 1.0))
            for c in lst_sorted[:1]:
                probes.append(c)
                used.add(_attr(c, "intervention_id"))
                if len(probes) >= n_probes:
                    break
            if len(probes) >= n_probes:
                break

        remaining = budget - len(probes)
        if remaining <= 0:
            return probes

        doc_id = _attr(cands[0], "document_id")
        yields = self._family_yield(conn, doc_id)
        # Sharpened allocation: weight = yield^alpha, with epsilon prior so
        # probed-but-zero-yield families still get a chance.
        eps = 1e-3
        weights = {fam: (yields.get(fam, 0.0) + eps) ** self.yield_alpha
                   for fam in by_family}
        total_w = sum(weights.values()) or 1.0

        alloc: dict[str, int] = {fam: 0 for fam in by_family}
        leftover = remaining
        sorted_fams = sorted(by_family, key=lambda f: -weights[f])
        for fam in sorted_fams:
            share = int(round(remaining * weights[fam] / total_w))
            alloc[fam] = share
            leftover -= share
        i = 0
        while leftover > 0 and sorted_fams:
            alloc[sorted_fams[i % len(sorted_fams)]] += 1
            leftover -= 1
            i += 1
        while leftover < 0 and sorted_fams:
            for fam in sorted_fams:
                if alloc[fam] > 0:
                    alloc[fam] -= 1
                    leftover += 1
                    if leftover == 0:
                        break

        # Stage 4: refine within each family — prefer candidates whose group_id
        # has historically yielded change.
        group_yield: dict[str, float] = {}
        if conn is not None and doc_id is not None:
            try:
                for r in conn.execute(
                    """
                    SELECT ic.group_id AS gid,
                           AVG(CASE WHEN eo.outcome_type IN
                                ('TYPE_FLIP','OBJECT_FLIP','SUBJECT_FLIP','DISAPPEARED','AMBIGUOUS')
                                THEN 1.0 ELSE 0.0 END) AS rate
                    FROM intervention_candidates ic
                    JOIN counterfactual_runs cfr ON cfr.intervention_id = ic.intervention_id
                    JOIN edge_outcomes eo ON eo.run_id = cfr.run_id
                    WHERE ic.document_id = ?
                    GROUP BY ic.group_id
                    """,
                    (doc_id,),
                ):
                    group_yield[r["gid"] or ""] = float(r["rate"] or 0.0)
            except Exception:
                pass

        refined: list = list(probes)
        for fam, take in alloc.items():
            if take <= 0:
                continue
            pool = [c for c in by_family[fam]
                    if _attr(c, "intervention_id") not in used]
            pool.sort(key=lambda c: (
                -group_yield.get(_attr(c, "group_id") or "", 0.0),
                float(_attr(c, "estimated_cost") or 1.0),
                rng.random(),
            ))
            for c in pool[: take]:
                refined.append(c)
                used.add(_attr(c, "intervention_id"))
        return refined[: budget]


PLANNERS = {
    "exhaustive": ExhaustivePlanner,
    "random": RandomPlanner,
    "span_only": SpanOnlyPlanner,
    "prompt_only": PromptOnlyPlanner,
    "schema_only": SchemaOnlyPlanner,
    "greedy_cost": GreedyCostPlanner,
    "graphguard": GraphGuardPlanner,
    "adaptive_graphguard": AdaptivePlanner,
}


def get_planner(name: str, **kw):
    if name not in PLANNERS:
        raise ValueError(f"unknown planner {name}; available={list(PLANNERS)}")
    cls = PLANNERS[name]
    try:
        return cls(**kw)
    except TypeError:
        return cls()
