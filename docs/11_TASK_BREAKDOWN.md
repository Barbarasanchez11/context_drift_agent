# Task Breakdown

## Task 1 — Schema Reader (`agent/datahub/graphql.py`)

Query DataHub GMS via GraphQL to retrieve the current schema (field list + types) for a given dataset URN.

**Definition of done:**
- `get_schema(urn)` returns a `list[SchemaField]` for the demo dataset
- Verified against live DataHub Quickstart
- Unit test with a mocked HTTP response

---

## Task 2 — Context Retriever (`agent/datahub/graphql.py`)

Query DataHub GMS via GraphQL to retrieve the current business context (description, glossary terms, custom properties) for a given dataset URN.

**Definition of done:**
- `get_context(urn)` returns a `ContextSnapshot`
- Verified against live DataHub Quickstart (demo dataset has a description)
- Unit test with a mocked HTTP response

---

## Task 3 — Shared Models (`agent/models.py`)

Define all Pydantic models shared across components: `SchemaField`, `ContextSnapshot`, `SchemaDiff`, `FieldChange`, `DriftResult`.

**Definition of done:**
- All models defined, typed, importable
- No business logic in this file

---

## Task 4 — Change Detector / Poller (`agent/datahub/poller.py`)

Polling loop that calls `get_schema()` every N seconds, computes a hash of the schema, detects changes, and triggers the pipeline on change.

**Definition of done:**
- `run_poll_loop(urns, interval, on_change)` runs indefinitely
- Persists state to `.state/schema_hashes.json` (survives restarts)
- Unit test for `compute_schema_hash` and `detect_change`

---

## Task 5 — LLM Judge (`agent/llm/judge.py`, `agent/llm/prompts.py`)

Given a `SchemaDiff` and a `ContextSnapshot`, calls an LLM and returns a structured `DriftResult`.

**Definition of done:**
- `evaluate(diff, context)` returns a `DriftResult` with all three fields
- Works with both `anthropic` and `openai` providers (env-driven)
- Structured output parsing tested with a fixture response
- Unit test for prompt construction and response parsing (no live LLM call needed)

---

## Task 6 — Metadata Writer (`agent/datahub/writer.py`)

Writes a `DriftResult` back into DataHub as `customProperties` on the dataset.

**Definition of done:**
- `write_drift_result(urn, result)` posts to DataHub via the Python SDK emitter
- Verified against live DataHub Quickstart (property visible in UI)
- Unit test for payload construction

---

## Task 7 — Pipeline Integration (`agent/pipeline.py`, `agent/__main__.py`)

Wires all components: poller detects change → retriever gets context → judge evaluates → writer writes back.

**Definition of done:**
- Full end-to-end flow works against live DataHub Quickstart with the demo dataset
- `python -m agent` runs the agent from the CLI
- Logs at each stage show the pipeline progressing
