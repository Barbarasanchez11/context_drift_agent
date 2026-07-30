# Architecture Decisions Log

## Decision 001

Date: Initial research

Decision: Build an external DataHub agent.

Reason: Avoid modifying DataHub core.

---

## Decision 002

Decision: Use Python.

Reason: Best ecosystem for APIs, LLMs, and the DataHub SDK.

---

## Decision 003

Decision: Focus on Context Drift, not schema impact analysis.

Reason: Differentiate from existing public "blast radius" projects
confirmed in competition research (see docs/06_COMPETITION_ANALYSIS.md).

---

## Decision 004

Decision: Use an explicit freshness signal as the output.

Reason: Simple and demonstrable to judges.

(Superseded in mechanism by Decision 006 — signal remains conceptually the
same, storage mechanism changes.)

---

## Decision 005

Decision: Prioritize a working demo over enterprise completeness.

Reason: Hackathon timeline is 12 days.

---

## Decision 006 (NEW)

Decision: Use `customProperties` on `DatasetProperties` instead of a typed
Structured Property for the MVP output signal (`context_stale`,
`context_drift_reason`, `context_confidence`).

Reason: Structured Properties require a `StructuredPropertyDefinition` to
be created before values can be assigned. Official documentation confirms
this requirement exists, but no verified, complete official example
(YAML+CLI or GraphQL mutation) was found for a boolean property type. In
contrast, `customProperties` is a documented, low-risk mechanism with a
working Python SDK example (`StructuredPropertiesClass` for the typed
route is available, but the definition step is the unresolved risk — see
docs/10_STRUCTURED_PROPERTIES_RESEARCH.md).

For a 12-day hackathon, this removes a non-trivial risk of losing 1-2 days
debugging an undocumented definition step. The demo-visible result is
identical: judges see `context_stale: true` and a reason string on the
dataset in the DataHub UI.

Fallback if `customProperties` has any issue: use a simple Tag
(`CONTEXT_STALE`) instead — also fully supported, even simpler.

Migration to typed Structured Properties is optional, only if time remains
after Day 9.

---

## Decision 007 (NEW)

Decision: Trigger the agent via polling (GraphQL query every 30–60s
comparing a schema hash) instead of the Actions Framework for the MVP.

Reason: No verified official "hello world" example was found for an
Actions Framework listener reacting to a schema change event in a local
Quickstart environment. Official documentation does not clearly confirm
event-driven triggering works out-of-the-box without additional Kafka/event
configuration. Estimated cost: 1-2 days if it goes smoothly, 3+ days if
there are configuration issues — too much risk for a 12-day timeline.

Polling is estimated at 2-4 hours to implement and is fully demonstrable:
the judge-visible behavior (schema changes, agent reacts, DataHub is
updated) is identical regardless of trigger mechanism.

Migration to Actions Framework is optional, only if time remains in the
last 2 days.

---

## Decision 008 (NEW)

Decision: Positioning explicitly differentiates this project from
DataHub Cloud's Context Platform / Context Curator.

Reason: Research (docs/09_CONTEXT_PLATFORM_ANALYSIS.md) confirmed Context
Platform is a Cloud-only, Private Beta product focused on *generating* new
context via SME review — not on detecting staleness of *existing* context
triggered by schema change. No public evidence of overlap in the specific
mechanism was found. To avoid judges perceiving this as "a copy of
DataHub's own roadmap," the pitch explicitly names the distinction:
open-source vs. paid/beta, and "detect drift in what exists" vs.
"generate what's missing."
