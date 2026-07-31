# Component Interface Contract

This document is the single source of truth for the data contracts between
the four main components. Subagents MUST implement exactly these signatures
and data shapes. If something in the task requires data not described here,
stop and flag it — do not invent a format.

---

## Shared Models (`agent/models.py`)

**All components import from here. This file contains no business logic.**

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class SchemaField(BaseModel):
    field_path: str
    native_data_type: str          # e.g. "NUMBER", "STRING", "BOOLEAN"
    description: str | None = None


class FieldChange(BaseModel):
    field_path: str
    old_type: str | None           # None when change_type == "added"
    new_type: str | None           # None when change_type == "removed"
    change_type: Literal["added", "removed", "type_changed"]


class SchemaDiff(BaseModel):
    dataset_urn: str
    detected_at: datetime
    changed_fields: list[FieldChange]
    previous_fields: list[SchemaField]
    current_fields: list[SchemaField]


class ContextSnapshot(BaseModel):
    dataset_urn: str
    description: str | None
    glossary_terms: list[str]      # list of term names, e.g. ["CreditRisk"]
    custom_properties: dict[str, str]


class DriftResult(BaseModel):
    dataset_urn: str
    evaluated_at: datetime
    context_stale: bool
    context_confidence: float      # 0.0–1.0
    context_drift_reason: str      # human-readable, ≤ 500 chars
```

---

## Component 1 — Schema Reader + Context Retriever

**File:** `agent/datahub/graphql.py`
**Owns:** this file only. Does NOT touch `poller.py`, `writer.py`, `llm/`.

### Public API

```python
def get_schema(
    urn: str,
    gms_url: str,
    token: str | None = None,
) -> list[SchemaField]:
    ...

def get_context(
    urn: str,
    gms_url: str,
    token: str | None = None,
) -> ContextSnapshot:
    ...
```

### `get_schema` — example output

```json
[
  { "field_path": "customer_id",   "native_data_type": "NUMBER",  "description": null },
  { "field_path": "credit_limit",  "native_data_type": "NUMBER",  "description": null },
  { "field_path": "cust_email",    "native_data_type": "STRING",  "description": null }
]
```

### `get_context` — example output

```json
{
  "dataset_urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.customers,PROD)",
  "description": "Maximum credit amount for the customer",
  "glossary_terms": ["CreditRisk"],
  "custom_properties": {}
}
```

### GraphQL queries to implement

**Schema query:**
```graphql
query GetSchema($urn: String!) {
  dataset(urn: $urn) {
    schemaMetadata {
      fields {
        fieldPath
        nativeDataType
        description
      }
    }
  }
}
```

**Context query:**
```graphql
query GetContext($urn: String!) {
  dataset(urn: $urn) {
    properties {
      description
      customProperties { key value }
    }
    glossaryTerms {
      terms { term { name } }
    }
  }
}
```

### Assumptions

- DataHub GMS is reachable at `gms_url` (caller's responsibility to pass correct URL).
- Auth header is `Authorization: Bearer <token>` when token is not None.
- Returns empty list / empty ContextSnapshot fields on missing data — never raises on "not found".

---

## Component 2 — Change Detector / Poller

**File:** `agent/datahub/poller.py`
**Owns:** this file only + `.state/schema_hashes.json` (runtime artifact, git-ignored).
**Does NOT touch:** `graphql.py`, `writer.py`, `llm/`.

### Public API

```python
def compute_schema_hash(fields: list[SchemaField]) -> str:
    """SHA-256 of sorted (field_path, native_data_type) pairs."""
    ...

def detect_change(
    urn: str,
    current_fields: list[SchemaField],
    previous_fields: list[SchemaField],
) -> SchemaDiff | None:
    """Returns SchemaDiff if schema changed, None if identical."""
    ...

def run_poll_loop(
    urns: list[str],
    interval_seconds: int,
    on_change: Callable[[SchemaDiff], None],
    get_schema_fn: Callable[[str], list[SchemaField]],
    state_path: Path = Path(".state/schema_hashes.json"),
) -> None:
    """Blocking loop. Calls on_change whenever a schema change is detected."""
    ...
```

### State file format (`.state/schema_hashes.json`)

```json
{
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.customers,PROD)": {
    "hash": "a3f8c2d1...",
    "fields": [
      { "field_path": "credit_limit", "native_data_type": "NUMBER", "description": null }
    ],
    "last_checked": "2026-07-31T10:00:00Z"
  }
}
```

### `detect_change` — example output when type changes

```json
{
  "dataset_urn": "urn:li:dataset:(...)",
  "detected_at": "2026-07-31T10:05:00Z",
  "changed_fields": [
    {
      "field_path": "credit_limit",
      "old_type": "NUMBER",
      "new_type": "STRING",
      "change_type": "type_changed"
    }
  ],
  "previous_fields": [ { "field_path": "credit_limit", "native_data_type": "NUMBER", "description": null } ],
  "current_fields":  [ { "field_path": "credit_limit", "native_data_type": "STRING", "description": null } ]
}
```

### Assumptions

- `get_schema_fn` is injected (not imported directly) — allows unit testing without HTTP.
- First run always stores the hash without triggering `on_change`.
- Loop continues on transient errors (logs warning, sleeps, retries).

---

## Component 3 — LLM Judge

**Files:** `agent/llm/judge.py`, `agent/llm/prompts.py`
**Owns:** the `agent/llm/` folder only.
**Does NOT touch:** `datahub/`, `pipeline.py`.

### Public API

```python
# agent/llm/judge.py
def evaluate(
    diff: SchemaDiff,
    context: ContextSnapshot,
    llm_provider: str,       # "anthropic" or "openai"
    api_key: str,
    model: str,              # e.g. "claude-sonnet-4-6", "gpt-4o"
) -> DriftResult:
    ...
```

```python
# agent/llm/prompts.py
def build_prompt(diff: SchemaDiff, context: ContextSnapshot) -> str:
    """Returns the user message string for the LLM call."""
    ...
```

### LLM structured output contract

The LLM MUST return a JSON object. Parse it strictly — do not accept free text.

```json
{
  "context_stale": true,
  "context_confidence": 0.92,
  "context_drift_reason": "Field credit_limit changed from NUMBER to STRING. The description 'Maximum credit amount for the customer' implies a numeric value, but the field now stores free-text strings like '5000 EUR'. Numeric aggregations on this field would produce incorrect results."
}
```

- `context_stale`: boolean
- `context_confidence`: float 0.0–1.0
- `context_drift_reason`: string ≤ 500 characters

### `evaluate` — example output

```json
{
  "dataset_urn": "urn:li:dataset:(...)",
  "evaluated_at": "2026-07-31T10:05:03Z",
  "context_stale": true,
  "context_confidence": 0.92,
  "context_drift_reason": "Field credit_limit changed from NUMBER to STRING. The description 'Maximum credit amount for the customer' implies a numeric value, but the field now stores free-text strings like '5000 EUR'. Numeric aggregations on this field would produce incorrect results."
}
```

### Prompt structure (implement in `prompts.py`)

```
You are a data governance assistant. Given a schema change and existing
dataset context, evaluate whether the existing documentation is still accurate.

## Schema change detected
Dataset: {dataset_urn}
Changed fields:
  - {field_path}: {old_type} → {new_type}

## Existing context
Description: "{description}"
Glossary terms: {glossary_terms}

## Task
Respond with ONLY a JSON object — no preamble, no explanation outside the JSON:
{
  "context_stale": <true|false>,
  "context_confidence": <0.0-1.0>,
  "context_drift_reason": "<≤500 chars, explain why the existing context is or is not still valid>"
}
```

### Assumptions

- Caller passes valid `api_key` and `model`.
- LLM response is a JSON string (use `json.loads` on the raw text or parsed content block).
- If parsing fails, raise `ValueError` with the raw response — do not silently swallow errors.
- No retry logic in this component — retries are the caller's responsibility.

---

## Component 4 — Metadata Writer

**File:** `agent/datahub/writer.py`
**Owns:** this file only.
**Does NOT touch:** `graphql.py`, `poller.py`, `llm/`.

### Public API

```python
def write_drift_result(
    urn: str,
    result: DriftResult,
    gms_url: str,
    token: str | None = None,
) -> None:
    """Writes DriftResult to DataHub customProperties via the Python SDK emitter."""
    ...
```

### Payload written to DataHub

`customProperties` keys (all values serialized as strings):

```json
{
  "context_stale": "true",
  "context_confidence": "0.92",
  "context_drift_reason": "Field credit_limit changed from NUMBER to STRING. The description 'Maximum credit amount for the customer' implies a numeric value..."
}
```

**Important:** `customProperties` values are always strings in DataHub.
Convert `bool` and `float` before writing:
- `context_stale`: `str(result.context_stale).lower()` → `"true"` / `"false"`
- `context_confidence`: `str(round(result.context_confidence, 4))`
- `context_drift_reason`: pass as-is

### SDK usage pattern

```python
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    DatasetPropertiesClass,
    MetadataChangeProposalWrapper,
)

emitter = DatahubRestEmitter(gms_server=gms_url, token=token)
mcp = MetadataChangeProposalWrapper(
    entityUrn=urn,
    aspect=DatasetPropertiesClass(customProperties={...}),
)
emitter.emit(mcp)
```

### Assumptions

- Task 5 (LLM Judge) is complete and `DriftResult` format is finalized before this component is tested end-to-end.
- DataHub GMS is reachable at `gms_url`.
- Raises on HTTP error — no silent failures.

---

## Dependency Map

```
agent/models.py          ← no deps (base layer)
        ↓
agent/datahub/graphql.py ← imports models
agent/datahub/poller.py  ← imports models + receives get_schema_fn via injection
agent/llm/judge.py       ← imports models
        ↓
agent/datahub/writer.py  ← imports models (DriftResult)
        ↓
agent/pipeline.py        ← imports all four components + config
agent/__main__.py        ← imports pipeline + config
```

**Subagents work in isolation:**
- Subagent A owns: `agent/datahub/graphql.py`
- Subagent B owns: `agent/llm/judge.py`, `agent/llm/prompts.py`
- Subagent C owns: `agent/datahub/poller.py`
- Integration (Task 7): `agent/pipeline.py`, `agent/__main__.py`, `agent/config.py`, `agent/models.py`
