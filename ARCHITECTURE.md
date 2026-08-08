# Architecture

## Overview

Context Drift Agent is a polling daemon that detects when DataHub dataset documentation
becomes inconsistent with the actual schema, then explains why using an LLM.

## Flow

```
┌─────────────────────────────────────────────────────────┐
│  Poller  (agent/datahub/poller.py)                       │
│  polls DataHub GraphQL every POLL_INTERVAL_SECONDS       │
│  stores schema hashes in .state/schema_hashes.json       │
└──────────────────────────┬──────────────────────────────┘
                           │ SchemaDiff (changed fields)
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Context Retrieval  (agent/datahub/graphql.py)           │
│  fetches description, glossary terms, custom props       │
│                                                          │
│  MCP Consumer  (agent/datahub/mcp_context.py)            │
│  optionally fetches lineage + owners via mcp-server-     │
│  datahub (USE_MCP_CONTEXT=true)                          │
└──────────────────────────┬──────────────────────────────┘
                           │ ContextSnapshot + RichContext
                           ▼
┌─────────────────────────────────────────────────────────┐
│  LLM Judge  (agent/llm/judge.py)                         │
│  Anthropic tool_use / OpenAI json_object / Groq          │
│  prompt built in agent/llm/prompts.py                    │
│  shared HTTP client in agent/llm/client.py               │
└──────────────────────────┬──────────────────────────────┘
                           │ DriftResult
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Writer  (agent/datahub/writer.py)                       │
│  DataHub Python SDK — emits MetadataChangeProposal       │
│  writes customProperties to dataset entity               │
└─────────────────────────────────────────────────────────┘
```

## Module Map

```
agent/
├── __main__.py          entry point (reads config, starts poll loop)
├── config.py            pydantic-settings config from .env
├── models.py            shared data models (SchemaDiff, DriftResult, …)
├── pipeline.py          orchestrates one drift-check cycle
├── datahub/
│   ├── graphql.py       GraphQL queries (schema + context)
│   ├── poller.py        hash-based schema change detection
│   ├── mcp_context.py   MCP consumer (lineage, owners via stdio)
│   └── writer.py        metadata writeback via Python SDK
├── llm/
│   ├── client.py        shared LLM HTTP calls (Anthropic/OpenAI/Groq)
│   ├── judge.py         single-pass drift evaluation
│   ├── prompts.py       all LLM prompt builders
│   └── validator.py     synthetic Q&A context sufficiency check
└── mcp_server.py        FastMCP server (agent as MCP tool)

scripts/
├── setup_demo.py        writes demo description + glossary term
├── simulate_drift.py    changes credit_limit type → triggers detection
└── validate_context.py  standalone synthetic validation demo

tests/
├── test_client.py
├── test_judge.py
├── test_poller.py
├── test_prompts.py
├── test_validator.py
└── test_writer.py
```

## Key Design Decisions

See [`DECISIONS.md`](DECISIONS.md) for the rationale behind:
- Writing to `customProperties` (not Structured Properties) — Decision 006
- Polling (not Actions Framework) — Decision 007
- Scope boundary vs. DataHub Cloud Context Platform — Decision 008

## State

The agent maintains a single state file: `.state/schema_hashes.json`
(hash per dataset URN). This is the only persistence layer — no database required.
