from __future__ import annotations

from datetime import UTC, datetime

from agent.llm.client import call_llm
from agent.llm.prompts import build_prompt
from agent.models import ContextSnapshot, DriftResult, RichContext, SchemaDiff

_TOOL_NAME = "report_drift"
_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": "Report whether the dataset context is stale after a schema change.",
    "input_schema": {
        "type": "object",
        "properties": {
            "context_stale": {"type": "boolean"},
            "context_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "context_drift_reason": {"type": "string"},
        },
        "required": ["context_stale", "context_confidence", "context_drift_reason"],
    },
}


def evaluate(
    diff: SchemaDiff,
    context: ContextSnapshot,
    llm_provider: str,
    api_key: str,
    model: str,
    rich_context: RichContext | None = None,
) -> DriftResult:
    prompt = build_prompt(diff, context, rich_context)
    data = call_llm(
        prompt, llm_provider, api_key, model, tool_name=_TOOL_NAME, tool_schema=_TOOL_SCHEMA
    )
    return _parse_response(data, diff.dataset_urn)


def _parse_response(data: dict, dataset_urn: str) -> DriftResult:
    required = {"context_stale", "context_confidence", "context_drift_reason"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"LLM response missing fields {missing}: {data!r}")

    return DriftResult(
        dataset_urn=dataset_urn,
        evaluated_at=datetime.now(UTC),
        context_stale=bool(data["context_stale"]),
        context_confidence=float(data["context_confidence"]),
        context_drift_reason=str(data["context_drift_reason"]),
    )
