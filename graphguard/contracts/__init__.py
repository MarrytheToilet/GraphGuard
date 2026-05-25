"""Drift contracts for stochastic graph views.

A drift contract is a declared invariance / monotonicity / bounded-drift property
that an LLM-extracted graph database is *expected* to satisfy under a specified
family of configuration perturbations. GraphGuard checks contracts on a
recorded counterfactual run-DB and emits per-contract pass/fail + severity +
attribution.

Public API:
    from graphguard.contracts import (
        Contract, ContractKind, ContractResult,
        REGISTRY, register, run_all,
    )
"""
from .base import Contract, ContractKind, ContractResult, PairObservation
from .registry import REGISTRY, register
from .runner import run_all

# Side-effect: populates REGISTRY
from . import contracts as _contracts  # noqa: F401

__all__ = [
    "Contract", "ContractKind", "ContractResult", "PairObservation",
    "REGISTRY", "register", "run_all",
]
