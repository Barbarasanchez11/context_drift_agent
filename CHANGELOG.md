# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-08

### Added

**Core drift detection pipeline**
- Schema polling via DataHub GraphQL (configurable interval via `POLL_INTERVAL_SECONDS`)
- LLM-based context drift evaluation — supports Anthropic (tool_use), OpenAI, and Groq
- Writeback to DataHub `customProperties`: `context_stale`, `context_confidence`, `context_drift_reason`
- MCP consumer: enriches LLM prompt with downstream lineage, owners, and domain via `mcp-server-datahub`
- MCP server: exposes agent as an MCP tool (`check_drift`, `get_drift_status`, `list_monitored_datasets`)

**Synthetic context validation**
- `scripts/validate_context.py` — standalone script that generates 3 synthetic Q&A pairs and tests if existing documentation can answer them
- Writes `context_answerable` and `context_qa_confidence` back to DataHub
- Shared LLM client (`agent/llm/client.py`) reused by both judge and validator

**Infrastructure**
- GitHub Actions CI: ruff + pyright + pytest on push/PR
- Dockerfile (multi-stage build) and docker-compose
- Apache 2.0 license
- `uv.lock` for reproducible installs

**Demo scripts**
- `scripts/setup_demo.py` — writes description + glossary term to DataHub
- `scripts/simulate_drift.py` — changes `credit_limit` type to trigger detection

### Fixed
- Preserved existing dataset description on metadata writeback (previously erased)
- Groq LLM confidence score was always `0.0` — fixed with `json_object` response format
- Removed accidentally committed `venv/` directory from git tracking

[0.1.0]: https://github.com/Barbarasanchez11/context-drift-agent/releases/tag/v0.1.0
