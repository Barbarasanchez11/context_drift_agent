# Project Brief

## Name

Context Drift Agent

## One Sentence

An open-source DataHub OSS agent that detects when business context
(documentation, glossary meaning) becomes semantically stale after schema
evolution, and emits an explicit, machine-readable freshness signal.

---

# Problem

Modern data platforms change continuously. Schemas evolve. Documentation
does not. This creates:

- inaccurate descriptions,
- broken glossary meaning,
- unreliable context for both humans and AI agents consuming DataHub metadata.

---

# Solution

The agent periodically monitors dataset schemas (via polling, see
DECISIONS.md #007). When a schema change is detected:

1. Retrieve existing context (description, glossary terms, custom properties).
2. Compare with the new schema.
3. Ask an LLM for semantic validation: is the existing context still true?
4. Write the result back into DataHub as `customProperties`
   (`context_stale`, `context_drift_reason`, `context_confidence`).

---

# Competitive Positioning

DataHub Cloud's Context Platform (announced May 28, 2026, components in
Private Beta) focuses on **generating new** context from query logs and
dashboards, with SME review. It is a **paid, Cloud-only** capability with
no public evidence of an automated schema-change-triggered staleness
detector.

This project is explicitly positioned as the open-source, immediately
usable counterpart that answers a different question: not "what new
context can we generate?" but "is the context we already have still true?"

See `docs/09_CONTEXT_PLATFORM_ANALYSIS.md` for full research and sources.

---

# Users

Primary:
- Data governance teams
- Data platform teams
- Analytics engineers

Secondary:
- AI agents consuming DataHub metadata

---

# Success Metric

A user can immediately identify: "Which assets have metadata that may no
longer be trustworthy, and why?"
