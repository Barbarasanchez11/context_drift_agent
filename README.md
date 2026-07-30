# Context Drift Agent

Open-source AI agent for maintaining trustworthy metadata context in DataHub OSS.

## Concept

Schema changes can silently make existing business documentation and glossary
definitions incorrect. Context Drift Agent detects these situations
automatically, evaluates whether existing context is still semantically
valid using an LLM, and writes an explicit, machine-readable freshness
signal back into DataHub.

## Positioning (important)

DataHub Cloud announced a **Context Platform** (Context Ingestion, Context
Intelligence, Context Hub, Context Activation) on May 28, 2026. Key
components (Context Intelligence, Context Hub, Context Activation) are in
**Private Beta** and are part of **DataHub Cloud**, a paid product — not
DataHub OSS.

Context Curator (part of that platform) analyzes query logs and dashboards
to **generate new** context documents, which are then reviewed by a Subject
Matter Expert (human-in-the-loop). Public documentation does not describe
an automated flow triggered by schema change that compares *existing*
documentation against a new schema and emits an explicit staleness signal.

**Our differentiation, stated explicitly in the pitch:**

> "DataHub Cloud has Context Platform, generating new context in private
> beta. We built the open-source agent that watches the context you
> already have, and tells you the moment it stops being true — available
> today, on OSS."

Do not describe this project as "AI that maintains context" — that phrase
overlaps with DataHub's own marketing language for Context Platform. Use
the "drift detection" framing instead.

## Workflow

```
Schema Change
     |
     v
Context Retrieval (description, glossary terms, custom properties)
     |
     v
LLM Semantic Validation (old context vs new schema)
     |
     v
customProperties writeback: context_stale, context_drift_reason, context_confidence
```

## Status

Research completed. Implementation phase starting.

## Requirements

- Python 3.11+
- Docker
- DataHub OSS (Quickstart)

## License

Apache 2.0
