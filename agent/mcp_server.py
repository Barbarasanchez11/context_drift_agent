"""MCP Server: exposes Context Drift Agent as an MCP tool.

Any MCP client (Claude Desktop, Cursor, other agents) can call:
  - check_drift(urn)            → run on-demand drift evaluation
  - get_drift_status(urn)       → query last recorded result
  - list_monitored_datasets()   → list what the agent is watching

Entry point: context-drift-mcp  (see pyproject.toml [project.scripts])

Usage (Claude Desktop claude_desktop_config.json):
  {
    "mcpServers": {
      "context-drift-agent": {
        "command": "uv",
        "args": ["--directory", "/path/to/repo", "run", "context-drift-mcp"],
        "env": {"DATAHUB_GMS_URL": "http://localhost:8080", "ANTHROPIC_API_KEY": "sk-ant-..."}
      }
    }
  }
"""

from __future__ import annotations

import logging
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from agent.config import Settings
from agent.datahub.graphql import get_context, get_schema
from agent.datahub.poller import _load_state, detect_change
from agent.datahub.writer import write_drift_result
from agent.llm.judge import evaluate
from agent.models import SchemaField

logger = logging.getLogger(__name__)

_STATE_PATH = Path(".state/schema_hashes.json")

mcp = MCPServer(
    "context-drift-agent",
    instructions=(
        "Tools for detecting and querying metadata context drift in DataHub datasets. "
        "Use check_drift to run an on-demand evaluation, get_drift_status to query "
        "the last recorded result, or list_monitored_datasets to see what is being watched."
    ),
)


@mcp.tool()
def check_drift(urn: str) -> dict:
    """Run a full on-demand context drift check for a DataHub dataset.

    Fetches the current schema, compares it with the stored baseline,
    runs an LLM evaluation if a change is detected, and writes the result
    back to DataHub as customProperties.

    Args:
        urn: DataHub dataset URN, e.g.
             urn:li:dataset:(urn:li:dataPlatform:snowflake,db.schema.table,PROD)
    """
    try:
        settings = Settings()
        state = _load_state(_STATE_PATH)

        current_fields = get_schema(urn, settings.datahub_gms_url, settings.datahub_token)
        if not current_fields:
            return {"status": "error", "urn": urn, "error": "Dataset not found or schema is empty."}

        if urn not in state:
            # First time — store baseline, nothing to compare yet
            from agent.datahub.poller import _save_state

            _save_state(urn, current_fields, _STATE_PATH)
            return {
                "status": "baseline_stored",
                "urn": urn,
                "message": "No previous schema on record. Baseline stored. Run again after a schema change.",  # noqa: E501
                "field_count": len(current_fields),
            }

        previous_fields = [SchemaField(**f) for f in state[urn]["fields"]]
        diff = detect_change(urn, current_fields, previous_fields)

        if diff is None:
            return {
                "status": "no_change",
                "urn": urn,
                "message": "Schema is unchanged since last check. No drift evaluation needed.",
                "last_checked": state[urn].get("last_checked"),
            }

        context = get_context(urn, settings.datahub_gms_url, settings.datahub_token)

        rich_context = None
        if settings.use_mcp_context:
            try:
                from agent.datahub.mcp_context import get_rich_context

                rich_context = get_rich_context(
                    urn, settings.datahub_gms_url, settings.datahub_token
                )
            except Exception:
                pass

        result = evaluate(
            diff=diff,
            context=context,
            llm_provider=settings.llm_provider,
            api_key=settings.get_api_key(),
            model=settings.llm_model,
            rich_context=rich_context,
        )

        write_drift_result(urn, result, settings.datahub_gms_url, settings.datahub_token)

        changed = [
            {"field": fc.field_path, "from": fc.old_type, "to": fc.new_type}
            for fc in diff.changed_fields
        ]
        return {
            "status": "evaluated",
            **result.model_dump(mode="json"),
            "changed_fields": changed,
        }

    except Exception as exc:
        logger.exception("check_drift failed for %s", urn)
        return {"status": "error", "urn": urn, "error": str(exc)}


@mcp.tool()
def get_drift_status(urn: str) -> dict:
    """Get the last recorded drift result for a DataHub dataset.

    Reads the context_stale, context_confidence, and context_drift_reason
    values that were last written to DataHub's customProperties.
    Does NOT trigger a new evaluation.

    Args:
        urn: DataHub dataset URN
    """
    try:
        settings = Settings()
        context = get_context(urn, settings.datahub_gms_url, settings.datahub_token)
        props = context.custom_properties

        if "context_stale" not in props:
            return {"status": "no_data", "urn": urn, "message": "No drift evaluation recorded yet."}

        return {
            "status": "ok",
            "urn": urn,
            "context_stale": props.get("context_stale") == "true",
            "context_confidence": float(props.get("context_confidence", 0)),
            "context_drift_reason": props.get("context_drift_reason", ""),
        }

    except Exception as exc:
        logger.exception("get_drift_status failed for %s", urn)
        return {"status": "error", "urn": urn, "error": str(exc)}


@mcp.tool()
def list_monitored_datasets() -> dict:
    """List all DataHub datasets being monitored by the Context Drift Agent.

    Returns datasets tracked in the state file (have been polled at least once)
    and datasets configured in DATASET_URNS.
    """
    try:
        settings = Settings()
        configured = settings.get_urns()

        state = _load_state(_STATE_PATH)
        tracked = [
            {
                "urn": urn,
                "last_checked": info.get("last_checked"),
                "field_count": len(info.get("fields", [])),
            }
            for urn, info in state.items()
        ]

        return {
            "configured": configured,
            "tracked": tracked,
            "total_tracked": len(tracked),
        }

    except Exception as exc:
        logger.exception("list_monitored_datasets failed")
        return {"status": "error", "error": str(exc)}


def run() -> None:
    logging.basicConfig(level=logging.WARNING)
    mcp.run(transport="stdio")
