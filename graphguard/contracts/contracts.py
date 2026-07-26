"""Contract catalogue K1–K6.

Each contract is a first-class declarative object. Implementation lives in
runner.py; here we only declare the metric, scope, threshold, and direction.

Numbering matches the paper directly:
  K1 / K1b / K1c : schema presentation / description / semantic-shading
  K2             : prompt presentation invariance
  K3             : evidence + entity-alias presentation invariance
  K4 / K4b–d     : join / path / aggregation / RAG robustness (query-scoped)
  K5             : cross-model recall stability
  K6             : controlled decoding-resample stability
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

# K4 — canonical diagnostic fan-out-join robustness
# D3 answer Jaccard should remain reasonably high under presentation changes.
# This is QUERY-SCOPED and distinct from the gold-instantiated deployment Q3.
register(Contract(
    id="K4",
    name="Diagnostic fan-out join robustness (D3)",
    kind=ContractKind.BOUNDED_DRIFT,
    scope={
        "semantic_class_in": {"presentation"},  # only presentation perturbations
    },
    direction="min",
    # Catalogue tolerance tau=0.30 on answer drift, i.e. violate when the
    # D3 answer Jaccard falls below 0.70 (paper Table 1; primary-run
    # violation rate 0.91 at this threshold).
    threshold=0.70,
    metric_fn=M.edge_jaccard,  # per-pair D3 Jaccard, computed in runner
    description=(
        "Canonical diagnostic fan-out-join answers should not collapse "
        "under presentation drift."
    ),
    query_scoped=True,
    query_id="D3",
))

# K4b–d — revision query contracts (same presentation-family paired views)
register(Contract(
    id="K4b",
    name="Shortest-path robustness (Q5)",
    kind=ContractKind.BOUNDED_DRIFT,
    scope={"semantic_class_in": {"presentation"}},
    direction="min",
    threshold=0.70,
    metric_fn=M.query_jaccard,
    description="Shortest-path answers should have drift at most 0.30.",
    query_scoped=True,
    query_id="Q5",
))

register(Contract(
    id="K4c",
    name="Degree-aggregation robustness (Q6)",
    kind=ContractKind.BOUNDED_DRIFT,
    scope={"semantic_class_in": {"presentation"}},
    direction="min",
    threshold=0.70,
    metric_fn=M.query_jaccard,
    description="Top-degree aggregation answers should have drift at most 0.30.",
    query_scoped=True,
    query_id="Q6",
))

register(Contract(
    id="K4d",
    name="GraphRAG-retrieval robustness (Q7)",
    kind=ContractKind.BOUNDED_DRIFT,
    scope={"semantic_class_in": {"presentation"}},
    direction="min",
    threshold=0.70,
    metric_fn=M.query_jaccard,
    description="Two-hop GraphRAG retrieval context should have drift at most 0.30.",
    query_scoped=True,
    query_id="Q7",
))

# K5 — model swap recall
register(Contract(
    id="K5",
    name="Model swap recall stability",
    kind=ContractKind.BOUNDED_DRIFT,
    scope={
        "cause_family_in": {"model"},
    },
    direction="max",
    threshold=0.20,
    metric_fn=M.recall_difference,
    description="Per-document absolute gold recall difference should not exceed 0.20.",
    needs_gold=True,
))

# K6 — controlled decoding resampling (fixed task, varied decoding sample)
register(Contract(
    id="K6",
    name="Decoding-resample stability",
    kind=ContractKind.INVARIANCE,
    scope={
        "cause_family_in": {"stochastic"},
    },
    direction="min",
    # The paper catalogue declares graph drift <= 0.15.  This contract
    # operates on edge Jaccard similarity, so the equivalent threshold is
    # 1 - 0.15 = 0.85.
    threshold=0.85,
    metric_fn=M.edge_jaccard,
    description=(
        "With document, schema, prompt, evidence, and model fixed, controlled "
        "decoding resamples should yield near-identical graphs."
    ),
))
