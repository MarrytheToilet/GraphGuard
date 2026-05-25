"""Contract catalogue K1–K6.

Each contract is a first-class declarative object. Implementation lives in
runner.py; here we only declare the metric, scope, threshold, and direction.

Numbering matches the paper directly:
  K1 / K1b / K1c : schema presentation / description / semantic-shading
  K2             : prompt presentation invariance
  K3             : evidence + entity-alias presentation invariance
  K4             : multi-hop join robustness (query-scoped)
  K5             : cross-model recall stability
  K6             : stochastic repeatability
"""
from __future__ import annotations

from .base import Contract, ContractKind
from .registry import register
from . import metrics as M


# K1 — schema STRICT presentation invariance (rename / reorder only)
# These are pure presentation: same relations, same descriptions, only surface form differs.
# The model SHOULD be invariant.
register(Contract(
    id="K1",
    name="Schema rename/reorder invariance (strict)",
    kind=ContractKind.INVARIANCE,
    scope={
        "cause_family_in": {"schema"},
        "semantic_class_in": {"presentation"},
        "description_substring_in": {"'rename'", "'reorder'"},
    },
    direction="min",
    threshold=0.85,
    metric_fn=M.edge_jaccard,
    description="Pure surface-level schema edits (rename, reorder) should preserve edges (near-invariance, threshold 0.85).",
))

# K1b — schema description-tweak invariance (desc_added)
# Adding helpful description text shouldn't *destabilize* extraction.
register(Contract(
    id="K1b",
    name="Schema description-add invariance",
    kind=ContractKind.INVARIANCE,
    scope={
        "cause_family_in": {"schema"},
        "semantic_class_in": {"presentation"},
        "description_substring_in": {"'desc_added'"},
    },
    direction="min",
    threshold=0.80,
    metric_fn=M.edge_jaccard,
    description="Adding relation descriptions should clarify, not flip, extraction outcomes.",
))

# K1c — schema semantic-shading bounded drift (hierarchical / desc_removed)
# These do change relation semantics; we don't expect invariance, but drift should be bounded.
register(Contract(
    id="K1c",
    name="Schema semantic-shading bounded drift",
    kind=ContractKind.BOUNDED_DRIFT,
    scope={
        "cause_family_in": {"schema"},
        "description_substring_in": {"'hierarchical'", "'desc_removed'"},
    },
    direction="min",
    threshold=0.50,
    metric_fn=M.edge_jaccard,
    description="Hierarchical rewrite or description removal may drift, but shouldn't collapse the graph.",
))

# K2 — prompt presentation invariance
register(Contract(
    id="K2",
    name="Prompt presentation invariance",
    kind=ContractKind.INVARIANCE,
    scope={
        "cause_family_in": {"prompt"},
        "semantic_class_in": {"presentation"},
    },
    direction="min",
    threshold=0.80,
    metric_fn=M.edge_jaccard,
    description="Prompt tone/persona edits with no instruction change should preserve edges (near-invariance, threshold 0.80).",
))

# K3 — evidence + entity-alias presentation invariance
register(Contract(
    id="K3",
    name="Evidence/entity-alias reorder invariance",
    kind=ContractKind.INVARIANCE,
    scope={
        "cause_family_in": {"evidence", "entity_alias"},
        "semantic_class_in": {"presentation"},
    },
    direction="min",
    threshold=0.80,
    metric_fn=M.edge_jaccard,
    description="Reordering paragraphs / aliasing entities (with audit-time alias canonicalization) should preserve edges (threshold 0.80).",
))

# K4 — multi-hop join robustness
# Q3 query Jaccard should remain reasonably high under any non-noop perturbation.
# This is QUERY-SCOPED: metric is per-query, applies to Q3 only.
register(Contract(
    id="K4",
    name="Multi-hop join robustness (Q3)",
    kind=ContractKind.BOUNDED_DRIFT,
    scope={
        "semantic_class_in": {"presentation"},  # only presentation perturbations
    },
    direction="min",
    threshold=0.50,
    metric_fn=M.edge_jaccard,                 # per-pair: Q3 jaccard, computed in runner
    description="Multi-hop join answers should not collapse under presentation drift.",
    query_scoped=True,
))

# K5 — model swap recall
# Recall over the relation distribution shouldn't drop dramatically across model swap.
register(Contract(
    id="K5",
    name="Model swap recall stability",
    kind=ContractKind.BOUNDED_DRIFT,
    scope={
        "operator_prefix": "model:",
    },
    direction="min",
    threshold=0.40,
    metric_fn=M.relation_distribution_l1,
    description="Different LLMs should agree on the bulk relation distribution.",
))

# K6 — stochastic repeatability (same config, fresh seed)
register(Contract(
    id="K6",
    name="Stochastic repeatability",
    kind=ContractKind.INVARIANCE,
    scope={
        "cause_family_in": {"stochastic"},
    },
    direction="min",
    threshold=0.90,
    metric_fn=M.edge_jaccard,
    description="Re-running the same configuration should yield near-identical graphs.",
))
