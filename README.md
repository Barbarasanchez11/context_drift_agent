# Context Drift Agent

![CI](https://github.com/Barbarasanchez11/context-drift-agent/workflows/ci/badge.svg)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)

**Open-source agent that watches your DataHub metadata and tells you the moment it stops being true.**

Schema changes silently break existing documentation. A field changes from `FLOAT` to `VARCHAR`
and nobody updates the description that says *"numeric value in the account currency"* — or the
glossary term that says values must be numeric. Downstream dashboards and ML models keep consuming
the field assuming the old contract. This is context drift.

Context Drift Agent detects it automatically, explains why the context is stale, and writes the
result back into DataHub so every person and agent downstream inherits the signal.

---

## How it works

```
Schema change detected (polling every N seconds)
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│  Context Retrieval                                           │
│  ├── GraphQL   → description, glossary terms, custom props  │
│  └── DataHub MCP Server → lineage, owners, domain           │
└───────────────────────────┬──────────────────────────────────┘
                            │ ContextSnapshot + RichContext
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  LLM Judge  (Anthropic tool_use / OpenAI / Groq)             │
│  "Is the existing documentation still accurate?"             │
│  → context_stale  · context_confidence  · reason            │
└───────────────────────────┬──────────────────────────────────┘
                            │ DriftResult
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Metadata Writer  (DataHub Python SDK)                       │
│  Writes to dataset customProperties — visible in the UI      │
│    context_stale=true                                        │
│    context_confidence=0.95                                   │
│    context_drift_reason="Field credit_limit changed…"        │
└──────────────────────────────────────────────────────────────┘
```

---

## Positioning

DataHub Cloud announced **Context Platform** in May 2026 — a paid, private-beta product that
**generates new context** from query logs and SME review.

This project does something different and complementary:

> "DataHub Cloud generates context you don't have yet.
> Context Drift Agent protects the context you already wrote."

- **Open-source** — Apache 2.0, runs on DataHub OSS today
- **Drift detection** — detects when *existing* documentation becomes wrong after a schema change
- **MCP-native** — reads from DataHub's MCP Server, exposes itself as an MCP tool

---

## Quickstart

**Prerequisites:** Python 3.11+, Docker, [DataHub OSS Quickstart](https://datahubproject.io/docs/quickstart)

```bash
# 1. Start DataHub
pip install acryl-datahub && datahub docker quickstart

# 2. Clone and configure
git clone https://github.com/Barbarasanchez11/context-drift-agent
cd context-drift-agent
cp .env.example .env   # add your ANTHROPIC_API_KEY (or OPENAI / GROQ)

# 3. Run the agent
uv run python -m agent
```

Then in a second terminal, trigger a drift event:

```bash
uv run python scripts/setup_demo.py    # write description + glossary term
uv run python scripts/simulate_drift.py  # change credit_limit FLOAT → VARCHAR
```

Watch the agent detect the change and write `context_stale=true` back to DataHub.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DATAHUB_GMS_URL` | `http://localhost:8080` | DataHub GMS endpoint |
| `DATAHUB_TOKEN` | *(empty)* | Personal Access Token |
| `LLM_PROVIDER` | `anthropic` | `anthropic` / `openai` / `groq` |
| `ANTHROPIC_API_KEY` | *(required)* | Anthropic API key |
| `OPENAI_API_KEY` | *(optional)* | OpenAI API key |
| `GROQ_API_KEY` | *(optional)* | Groq API key (free tier available) |
| `LLM_MODEL` | `claude-sonnet-4-6` | Model name |
| `POLL_INTERVAL_SECONDS` | `30` | Polling frequency |
| `DATASET_URNS` | *(required)* | Pipe-separated dataset URNs to watch |
| `USE_MCP_CONTEXT` | `true` | Enrich via DataHub MCP Server |

`DATASET_URNS` uses `|` as separator because URNs themselves contain commas:
```
DATASET_URNS=urn:li:dataset:(urn:li:dataPlatform:snowflake,db.schema.customers,PROD)
```

---

## MCP Integration

### Reading from DataHub's MCP Server

With `USE_MCP_CONTEXT=true` (default), the agent calls `mcp-server-datahub` for each drift event
to fetch downstream lineage, owners, and domain. This enriches the judge's prompt:
*"3 downstream assets (credit_risk_dashboard, risk_scoring_model) depend on this field."*

Verify it works:
```bash
DATAHUB_GMS_URL=http://localhost:8080 uvx mcp-server-datahub --help
```

### Our agent as an MCP tool

The agent exposes itself as an MCP server. Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "context-drift-agent": {
      "command": "uv",
      "args": ["--directory", "/path/to/context-drift-agent", "run", "context-drift-mcp"],
      "env": {
        "DATAHUB_GMS_URL": "http://localhost:8080",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Restart Claude Desktop, then ask:
- *"Check for drift on urn:li:dataset:(...,customers,PROD)"*
- *"What datasets is the Context Drift Agent monitoring?"*

| Tool | Description |
|---|---|
| `check_drift(urn)` | On-demand drift evaluation |
| `get_drift_status(urn)` | Last recorded result |
| `list_monitored_datasets()` | All watched datasets |

---

## Docker

```bash
# DataHub must be running first: datahub docker quickstart
docker compose up --build
```

---

## Development

```bash
uv sync --all-extras
uv run pytest           # 28+ tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run pyright          # type check
```

---

## Examples

See [`examples/`](examples/) for real agent outputs:
- [`drift_detected.json`](examples/drift_detected.json) — full output when context is stale
- [`context_stable.json`](examples/context_stable.json) — type change that doesn't break context

---

## Architecture decisions

See [`DECISIONS.md`](DECISIONS.md) — key choices explained:
- `customProperties` over Structured Properties (Decision 006)
- Polling over Actions Framework (Decision 007)
- Positioning vs DataHub Cloud Context Platform (Decision 008)

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
