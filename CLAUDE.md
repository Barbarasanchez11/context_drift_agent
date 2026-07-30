# Claude Code Instructions

Project: Context Drift Agent

## Mission

Build an open-source AI agent for DataHub OSS that detects stale metadata
context after schema changes.

## Core Problem

Metadata becomes outdated. A schema can evolve while:

- descriptions remain old,
- glossary terms become inaccurate,
- AI agents receive wrong context.

## Goal

```
Schema change (detected via polling, see DECISIONS.md #007)
        |
        v
Context inconsistency (evaluated by LLM)
        |
        v
customProperties writeback: context_stale, context_drift_reason,
context_confidence (see DECISIONS.md #006)
```

## Non-Goals

Do NOT build:

- schema impact analysis / blast radius engine (already public competition,
  see docs/06_COMPETITION_ANALYSIS.md)
- a generic metadata chatbot
- a metadata catalog replacement
- anything resembling DataHub Cloud's Context Platform / Context Curator
  (generating new context via SME review — see
  docs/09_CONTEXT_PLATFORM_ANALYSIS.md). This project detects drift in
  *existing* context; it does not generate new context.

## Technical Principles

1. Prefer DataHub native APIs (GraphQL + Python SDK).
2. Write metadata back into DataHub using `customProperties` (not typed
   Structured Properties — see DECISIONS.md #006).
3. Trigger via polling, not Actions Framework, for the MVP (DECISIONS.md #007).
4. Keep LLM reasoning explainable — always require structured output
   (status, confidence, reason).
5. Avoid unnecessary infrastructure (no Kafka, no distributed event
   handling in the MVP).

## Preferred Stack

- Python 3.11+
- DataHub OSS (Quickstart, Docker)
- GraphQL + Python SDK (`datahub` package)
- LLM API (provider-agnostic client — Claude or OpenAI)
- uv for package management

## Development Rules

Before implementing anything that touches the DataHub API:

- Check official documentation first (https://docs.datahub.com/).
- Never invent API behavior that hasn't been verified.
- If uncertain, mark `TODO` in code and flag it — do not guess silently.

## Demo Objective

The final demo must show, end to end:

1. Dataset exists with a description and a glossary term attached.
2. Schema changes (e.g. `age INT` → `age STRING`).
3. Agent detects the change (via polling).
4. LLM evaluates and explains why the existing context is now unreliable.
5. DataHub dataset is updated with `context_stale=true` and a human-readable
   reason, visible in the UI.

## Code Quality

Prefer:
- small, single-responsibility modules
- basic tests for the comparison and LLM-parsing logic
- clear logs at each pipeline stage
- typed Python (type hints)
- configuration via a `.env` / config file, not hardcoded values
