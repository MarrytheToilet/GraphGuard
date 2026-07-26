-- GraphGuard SQLite lineage schema.
-- Tables cover source data, extraction lineage, counterfactuals, cached calls,
-- and evaluation metadata used by current or existing run databases.

CREATE TABLE IF NOT EXISTS documents (
  document_id TEXT PRIMARY KEY,
  dataset     TEXT,
  title       TEXT,
  raw_text    TEXT,
  split       TEXT
);

CREATE TABLE IF NOT EXISTS sentences (
  sentence_id    TEXT PRIMARY KEY,
  document_id    TEXT NOT NULL REFERENCES documents(document_id),
  sentence_index INTEGER NOT NULL,
  text           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sentences_doc ON sentences(document_id);

CREATE TABLE IF NOT EXISTS entities (
  entity_id      TEXT PRIMARY KEY,
  document_id    TEXT NOT NULL REFERENCES documents(document_id),
  canonical_name TEXT NOT NULL,
  aliases_json   TEXT,
  entity_type    TEXT
);
CREATE INDEX IF NOT EXISTS idx_entities_doc ON entities(document_id);

CREATE TABLE IF NOT EXISTS schemas (
  schema_id           TEXT PRIMARY KEY,
  name                TEXT,
  description         TEXT,
  relation_types_json TEXT,
  parent_schema_id    TEXT
);

CREATE TABLE IF NOT EXISTS prompts (
  prompt_id       TEXT PRIMARY KEY,
  name            TEXT,
  full_prompt     TEXT,
  clause_ids_json TEXT
);

CREATE TABLE IF NOT EXISTS prompt_clauses (
  clause_id   TEXT PRIMARY KEY,
  prompt_id   TEXT NOT NULL REFERENCES prompts(prompt_id),
  clause_type TEXT,
  clause_text TEXT
);

CREATE TABLE IF NOT EXISTS extraction_events (
  event_id                TEXT PRIMARY KEY,
  document_id             TEXT NOT NULL REFERENCES documents(document_id),
  prompt_id               TEXT REFERENCES prompts(prompt_id),
  schema_id               TEXT REFERENCES schemas(schema_id),
  model_id                TEXT,
  temperature             REAL,
  seed                    INTEGER,
  input_sentence_ids_json TEXT,
  input_entity_ids_json   TEXT,
  created_at              TEXT,
  token_input             INTEGER,
  token_output            INTEGER,
  latency_ms              INTEGER
);
CREATE INDEX IF NOT EXISTS idx_events_doc ON extraction_events(document_id);

CREATE TABLE IF NOT EXISTS extracted_edges (
  edge_id                     TEXT PRIMARY KEY,
  event_id                    TEXT NOT NULL REFERENCES extraction_events(event_id),
  document_id                 TEXT NOT NULL REFERENCES documents(document_id),
  subject_entity_id           TEXT,
  subject_name                TEXT,
  relation                    TEXT,
  object_entity_id            TEXT,
  object_name                 TEXT,
  evidence_sentence_ids_json  TEXT,
  confidence                  REAL,
  raw_json                    TEXT
);
CREATE INDEX IF NOT EXISTS idx_edges_event ON extracted_edges(event_id);
CREATE INDEX IF NOT EXISTS idx_edges_doc   ON extracted_edges(document_id);

-- ---------------------------------------------------------------
-- Counterfactual lineage and reliability metadata
-- ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS intervention_candidates (
  intervention_id TEXT PRIMARY KEY,
  document_id     TEXT,
  target_type     TEXT,
  target_id       TEXT,
  operator        TEXT,
  description     TEXT,
  estimated_cost  REAL,
  group_id        TEXT,
  semantic_class  TEXT,
  cause_family    TEXT
);

CREATE TABLE IF NOT EXISTS counterfactual_runs (
  run_id          TEXT PRIMARY KEY,
  base_event_id   TEXT,
  intervention_id TEXT,
  document_id     TEXT,
  prompt_id       TEXT,
  schema_id       TEXT,
  model_id        TEXT,
  temperature     REAL,
  seed            INTEGER,
  token_input     INTEGER,
  token_output    INTEGER,
  latency_ms      INTEGER,
  status          TEXT,
  created_at      TEXT,
  cf_event_id     TEXT
);

CREATE TABLE IF NOT EXISTS edge_outcomes (
  outcome_id        TEXT PRIMARY KEY,
  run_id            TEXT,
  original_edge_id  TEXT,
  outcome_type      TEXT,
  matched_edge_id   TEXT,
  relation_after    TEXT,
  confidence_after  REAL,
  match_score       REAL
);

CREATE TABLE IF NOT EXISTS edge_reliability_scores (
  edge_id              TEXT PRIMARY KEY,
  stability_score      REAL,
  text_responsibility  REAL,
  prompt_sensitivity   REAL,
  schema_sensitivity   REAL,
  stochastic_variance  REAL,
  risk_score           REAL,
  computed_at          TEXT
);

-- Cache table for extraction and counterfactual calls
CREATE TABLE IF NOT EXISTS llm_call_cache (
  cache_key   TEXT PRIMARY KEY,
  response    TEXT,
  created_at  TEXT
);

-- ===== Reference annotations and stability metadata =====

-- DocRED gold relation triples
CREATE TABLE IF NOT EXISTS gold_edges (
  gold_edge_id              TEXT PRIMARY KEY,
  document_id               TEXT NOT NULL REFERENCES documents(document_id),
  head_entity_id            TEXT,
  tail_entity_id            TEXT,
  head_name                 TEXT,
  tail_name                 TEXT,
  relation_base             TEXT,
  evidence_sentence_ids_json TEXT,
  source                    TEXT
);
CREATE INDEX IF NOT EXISTS idx_gold_doc ON gold_edges(document_id);

-- Per extracted edge correctness vs gold
CREATE TABLE IF NOT EXISTS edge_correctness (
  edge_id      TEXT PRIMARY KEY,
  document_id  TEXT,
  label        TEXT CHECK (label IN ('correct','wrong','unmatched','ambiguous')),
  gold_edge_id TEXT,
  matched_at   TEXT
);

-- Repeated-extraction stability metrics (per-document aggregate)
CREATE TABLE IF NOT EXISTS stability_reports (
  document_id        TEXT PRIMARY KEY,
  n_runs             INTEGER,
  avg_edge_overlap   REAL,
  type_agreement     REAL,
  disappearance_rate REAL,
  type_flip_rate     REAL,
  new_edge_rate      REAL,
  computed_at        TEXT
);

-- ===== Optional edge-level evaluation metadata =====
-- One row per (edge, signal_name). `score` is "higher = more risky / more likely error".
CREATE TABLE IF NOT EXISTS edge_baseline_scores (
  edge_id     TEXT NOT NULL REFERENCES extracted_edges(edge_id),
  signal      TEXT NOT NULL,
  score       REAL,
  computed_at TEXT,
  PRIMARY KEY (edge_id, signal)
);
CREATE INDEX IF NOT EXISTS idx_baseline_edge ON edge_baseline_scores(edge_id);
CREATE INDEX IF NOT EXISTS idx_baseline_sig  ON edge_baseline_scores(signal);

-- Per-document natural variance estimate from repeated extractions.
CREATE TABLE IF NOT EXISTS document_natural_change (
  document_id     TEXT PRIMARY KEY REFERENCES documents(document_id),
  n_runs          INTEGER,
  natural_change  REAL,    -- mean Change(e, no-op) across edges/runs in this doc
  computed_at     TEXT
);

-- Optional synthetic-injection metadata retained for existing lineage databases.
CREATE TABLE IF NOT EXISTS injection_cases (
  case_id        TEXT PRIMARY KEY,
  base_document_id TEXT,
  cause_type     TEXT,    -- 'sentence' | 'prompt_clause' | 'schema' | 'context' | 'stochastic'
  cause_target   TEXT,    -- e.g. injected sentence_id, prompt clause id, schema variant id
  gold_subject   TEXT,
  gold_relation  TEXT,
  gold_object    TEXT,
  injected_doc_id TEXT REFERENCES documents(document_id),
  notes          TEXT
);
