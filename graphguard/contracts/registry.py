"""Decorator-based registry of contracts."""
from __future__ import annotations

from typing import Dict
from .base import Contract


REGISTRY: Dict[str, Contract] = {}


def register(contract: Contract) -> Contract:
    if contract.id in REGISTRY:
        raise ValueError(f"contract {contract.id} already registered")
    REGISTRY[contract.id] = contract
    return contract
