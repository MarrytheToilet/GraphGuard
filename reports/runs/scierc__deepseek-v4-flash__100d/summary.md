# Aggregate report

## DB row counts

- documents: 150
- sentences: 826
- entities: 2004
- schemas: 15
- prompts: 10
- extraction_events: 7004
- extracted_edges: 55697
- intervention_candidates: 3306
- counterfactual_runs: 6336
- edge_outcomes: 47057
- edge_reliability_scores: 3338
- edge_correctness: 1208
- gold_edges: 1429

## Loaded artifacts

- e0
- e1
- e2
- e3
- e4
- repair

## Case studies (8)

### Case 1 — edge `evt-scierc-dev-000005-ICCV_2009_47_abs-914bbc41d2::415c5ea5db`

```json
{
  "edge": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-914bbc41d2::415c5ea5db",
    "document_id": "scierc-dev-000005-ICCV_2009_47_abs",
    "subject_name": "robust estimation",
    "relation": "HYPONYM-OF",
    "object_name": "robust estimation procedure",
    "confidence": 0.9,
    "risk_score": 2.6,
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0
  },
  "why_edge_top": [
    {
      "variable_type": "prompt_clause",
      "variable_id": "C1_evidence_only",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C1_evidence_only",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C1_evidence_only' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C3_use_schema",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C3_use_schema",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C3_use_schema' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C4_allow_other",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C4_allow_other",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C4_allow_other' \u2192 edge disappears in 1/1 runs"
    }
  ],
  "why_type_top": [],
  "risk": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-914bbc41d2::415c5ea5db",
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0,
    "risk_score": 2.6,
    "computed_at": "2026-05-25T10:40:51.409029+00:00"
  }
}
```

### Case 2 — edge `evt-scierc-dev-000005-ICCV_2009_47_abs-914bbc41d2::7d713bf1d9`

```json
{
  "edge": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-914bbc41d2::7d713bf1d9",
    "document_id": "scierc-dev-000005-ICCV_2009_47_abs",
    "subject_name": "RANSAC techniques",
    "relation": "EVALUATE-FOR",
    "object_name": "efficient robust estimation algorithm",
    "confidence": 0.95,
    "risk_score": 2.6,
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0
  },
  "why_edge_top": [
    {
      "variable_type": "prompt_clause",
      "variable_id": "C1_evidence_only",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C1_evidence_only",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C1_evidence_only' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C3_use_schema",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C3_use_schema",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C3_use_schema' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C4_allow_other",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C4_allow_other",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C4_allow_other' \u2192 edge disappears in 1/1 runs"
    }
  ],
  "why_type_top": [
    {
      "variable_type": "schema",
      "variable_id": "hierarchical",
      "operator": "switch_schema",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::schema::scierc_full::hierarchical",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "switch_schema on schema 'hierarchical' \u2192 relation type flips in 1/1 runs"
    }
  ],
  "risk": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-914bbc41d2::7d713bf1d9",
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0,
    "risk_score": 2.6,
    "computed_at": "2026-05-25T10:40:51.413568+00:00"
  }
}
```

### Case 3 — edge `evt-scierc-dev-000005-ICCV_2009_47_abs-914bbc41d2::8707ac8e07`

```json
{
  "edge": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-914bbc41d2::8707ac8e07",
    "document_id": "scierc-dev-000005-ICCV_2009_47_abs",
    "subject_name": "sampling process",
    "relation": "PART-OF",
    "object_name": "RANSAC techniques",
    "confidence": 0.7,
    "risk_score": 2.6,
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0
  },
  "why_edge_top": [
    {
      "variable_type": "prompt_clause",
      "variable_id": "C1_evidence_only",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C1_evidence_only",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C1_evidence_only' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C3_use_schema",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C3_use_schema",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C3_use_schema' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C4_allow_other",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C4_allow_other",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C4_allow_other' \u2192 edge disappears in 1/1 runs"
    }
  ],
  "why_type_top": [
    {
      "variable_type": "schema",
      "variable_id": "with_other",
      "operator": "switch_schema",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::schema::scierc_full::with_other",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "switch_schema on schema 'with_other' \u2192 relation type flips in 1/1 runs"
    }
  ],
  "risk": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-914bbc41d2::8707ac8e07",
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0,
    "risk_score": 2.6,
    "computed_at": "2026-05-25T10:40:51.415707+00:00"
  }
}
```

### Case 4 — edge `evt-scierc-dev-000027-E99-1023-9f26051afa::dc8059c220`

```json
{
  "edge": {
    "edge_id": "evt-scierc-dev-000027-E99-1023-9f26051afa::dc8059c220",
    "document_id": "scierc-dev-000027-E99-1023",
    "subject_name": "chunking",
    "relation": "HYPONYM-OF",
    "object_name": "tagging task",
    "confidence": 0.85,
    "risk_score": 2.6,
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0
  },
  "why_edge_top": [
    {
      "variable_type": "prompt_clause",
      "variable_id": "C1_evidence_only",
      "operator": "remove",
      "intervention_id": "scierc-dev-000027-E99-1023::iv::prompt::base_v1::drop::C1_evidence_only",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C1_evidence_only' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C3_use_schema",
      "operator": "remove",
      "intervention_id": "scierc-dev-000027-E99-1023::iv::prompt::base_v1::drop::C3_use_schema",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C3_use_schema' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C4_allow_other",
      "operator": "remove",
      "intervention_id": "scierc-dev-000027-E99-1023::iv::prompt::base_v1::drop::C4_allow_other",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C4_allow_other' \u2192 edge disappears in 1/1 runs"
    }
  ],
  "why_type_top": [],
  "risk": {
    "edge_id": "evt-scierc-dev-000027-E99-1023-9f26051afa::dc8059c220",
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0,
    "risk_score": 2.6,
    "computed_at": "2026-05-25T10:40:51.700229+00:00"
  }
}
```

### Case 5 — edge `evt-scierc-dev-000027-E99-1023-967567df38::390447830a`

```json
{
  "edge": {
    "edge_id": "evt-scierc-dev-000027-E99-1023-967567df38::390447830a",
    "document_id": "scierc-dev-000027-E99-1023",
    "subject_name": "data set",
    "relation": "USED-FOR",
    "object_name": "memory-based learning chunker",
    "confidence": 0.8,
    "risk_score": 2.6,
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0
  },
  "why_edge_top": [
    {
      "variable_type": "prompt_clause",
      "variable_id": "C1_evidence_only",
      "operator": "remove",
      "intervention_id": "scierc-dev-000027-E99-1023::iv::prompt::base_v1::drop::C1_evidence_only",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C1_evidence_only' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C3_use_schema",
      "operator": "remove",
      "intervention_id": "scierc-dev-000027-E99-1023::iv::prompt::base_v1::drop::C3_use_schema",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C3_use_schema' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C4_allow_other",
      "operator": "remove",
      "intervention_id": "scierc-dev-000027-E99-1023::iv::prompt::base_v1::drop::C4_allow_other",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C4_allow_other' \u2192 edge disappears in 1/1 runs"
    }
  ],
  "why_type_top": [],
  "risk": {
    "edge_id": "evt-scierc-dev-000027-E99-1023-967567df38::390447830a",
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0,
    "risk_score": 2.6,
    "computed_at": "2026-05-25T10:40:53.527273+00:00"
  }
}
```

### Case 6 — edge `evt-scierc-dev-000005-ICCV_2009_47_abs-2cf5bcbd23::2759be138d`

```json
{
  "edge": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-2cf5bcbd23::2759be138d",
    "document_id": "scierc-dev-000005-ICCV_2009_47_abs",
    "subject_name": "robust estimation",
    "relation": "HYPONYM-OF",
    "object_name": "robust estimation procedure",
    "confidence": 0.9,
    "risk_score": 2.6,
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0
  },
  "why_edge_top": [
    {
      "variable_type": "prompt_clause",
      "variable_id": "C1_evidence_only",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C1_evidence_only",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C1_evidence_only' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C3_use_schema",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C3_use_schema",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C3_use_schema' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C4_allow_other",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C4_allow_other",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C4_allow_other' \u2192 edge disappears in 1/1 runs"
    }
  ],
  "why_type_top": [],
  "risk": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-2cf5bcbd23::2759be138d",
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0,
    "risk_score": 2.6,
    "computed_at": "2026-05-25T10:40:53.183558+00:00"
  }
}
```

### Case 7 — edge `evt-scierc-dev-000005-ICCV_2009_47_abs-2cf5bcbd23::2b38ceb012`

```json
{
  "edge": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-2cf5bcbd23::2b38ceb012",
    "document_id": "scierc-dev-000005-ICCV_2009_47_abs",
    "subject_name": "strategies",
    "relation": "CONJUNCTION",
    "object_name": "technique",
    "confidence": 0.8,
    "risk_score": 2.6,
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0
  },
  "why_edge_top": [
    {
      "variable_type": "prompt_clause",
      "variable_id": "C1_evidence_only",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C1_evidence_only",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C1_evidence_only' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C3_use_schema",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C3_use_schema",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C3_use_schema' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C4_allow_other",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C4_allow_other",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C4_allow_other' \u2192 edge disappears in 1/1 runs"
    }
  ],
  "why_type_top": [],
  "risk": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-2cf5bcbd23::2b38ceb012",
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0,
    "risk_score": 2.6,
    "computed_at": "2026-05-25T10:40:53.185889+00:00"
  }
}
```

### Case 8 — edge `evt-scierc-dev-000005-ICCV_2009_47_abs-2cf5bcbd23::f054efa525`

```json
{
  "edge": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-2cf5bcbd23::f054efa525",
    "document_id": "scierc-dev-000005-ICCV_2009_47_abs",
    "subject_name": "RANSAC techniques",
    "relation": "EVALUATE-FOR",
    "object_name": "efficient robust estimation algorithm",
    "confidence": 0.95,
    "risk_score": 2.6,
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0
  },
  "why_edge_top": [
    {
      "variable_type": "prompt_clause",
      "variable_id": "C1_evidence_only",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C1_evidence_only",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C1_evidence_only' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C3_use_schema",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C3_use_schema",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C3_use_schema' \u2192 edge disappears in 1/1 runs"
    },
    {
      "variable_type": "prompt_clause",
      "variable_id": "C4_allow_other",
      "operator": "remove",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::prompt::base_v1::drop::C4_allow_other",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "remove on prompt_clause 'C4_allow_other' \u2192 edge disappears in 1/1 runs"
    }
  ],
  "why_type_top": [
    {
      "variable_type": "schema",
      "variable_id": "hierarchical",
      "operator": "switch_schema",
      "intervention_id": "scierc-dev-000005-ICCV_2009_47_abs::iv::schema::scierc_full::hierarchical",
      "n_runs": 1,
      "effect": 1.0,
      "interpretation": "switch_schema on schema 'hierarchical' \u2192 relation type flips in 1/1 runs"
    }
  ],
  "risk": {
    "edge_id": "evt-scierc-dev-000005-ICCV_2009_47_abs-2cf5bcbd23::f054efa525",
    "stability_score": 0.0,
    "text_responsibility": 0.0,
    "prompt_sensitivity": 1.0,
    "schema_sensitivity": 1.0,
    "stochastic_variance": 0.0,
    "risk_score": 2.6,
    "computed_at": "2026-05-25T10:40:53.188196+00:00"
  }
}
```
