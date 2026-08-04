# Design: MCP Integration + Repository Polish
Date: 2026-08-04
Status: Approved

## Problem
Context Drift Agent works end-to-end but (a) does not use DataHub's MCP Server (judging criterion #1),
(b) lacks the submission requirements (LICENSE, CI, Dockerfile, README), and (c) only uses
description + glossary for drift evaluation — missing lineage and ownership context.

## Solution

### Branch: feature/mcp-consumer
The LLM judge gets richer context by calling `mcp-server-datahub` (v0.6.0) via the MCP stdio
transport. On each drift event, we spawn the DataHub MCP server as a subprocess and call:
- `get_lineage(urn, upstream=False, max_results=10)` → downstream blast radius
- `get_entities([urn])` → owners, domain, platform

The richer context goes into the prompt: "N downstream dashboards/datasets depend on this field."
This makes confidence scores and reasons significantly more meaningful.

Fallback: if `mcp-server-datahub` is not installed or DataHub is unreachable, pipeline falls back
to GraphQL-only context (existing behavior). Controlled by `USE_MCP_CONTEXT=true/false`.

New files: `agent/datahub/mcp_context.py`
Modified: `agent/models.py` (RichContext), `agent/config.py`, `agent/llm/prompts.py`, `agent/pipeline.py`

### Branch: feature/mcp-server
Our agent exposes itself as an MCP server via `mcp.server.fastmcp.FastMCP`.
Entry point: `context-drift-mcp` (new script in pyproject.toml).

Tools:
- `check_drift(urn)` — on-demand drift check, full pipeline
- `get_drift_status(urn)` — reads latest result from .state/ file
- `list_monitored_datasets()` — lists URNs + last drift status

Enables: Claude Desktop / Cursor / any MCP client can trigger drift checks interactively.
New file: `agent/mcp_server.py`

### Branch: feature/polish
- `LICENSE` (Apache 2.0) — required for hackathon submission
- `README.md` — full rewrite: architecture diagram, quickstart, badges, positioning
- `.github/workflows/ci.yml` — ruff + pyright + pytest with uv
- `Dockerfile` — multi-stage, final ~180MB
- `docker-compose.yml` — agent only (DataHub uses its own quickstart)
- `examples/` — 2 sample JSON outputs (drift detected, context stable)
- `pyproject.toml` — add mcp>=1.0, mcp-server-datahub>=0.6, ruff, pyright

## Tool API (verified from source)
```python
get_lineage(urn, upstream=False, max_results=10, max_hops=2)  # upstream=False → downstream
get_entities(urns=[urn])  # returns owners, domain, schemaMetadata
```

## What user needs to test
```bash
# MCP Consumer
datahub docker quickstart
DATAHUB_GMS_URL=http://localhost:8080 uvx mcp-server-datahub --help  # verify installed
USE_MCP_CONTEXT=true python -m agent
# expect logs: "MCP context: 3 downstream assets, owners: [...]"

# MCP Server (our agent as tool)
context-drift-mcp  # or: uv run context-drift-mcp
# add to Claude Desktop config, ask: "check drift on [URN]"
```
