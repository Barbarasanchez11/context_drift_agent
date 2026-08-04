from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import anthropic
import groq as groq_sdk
import openai

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

_LLM_TIMEOUT = 30


def evaluate(
    diff: SchemaDiff,
    context: ContextSnapshot,
    llm_provider: str,
    api_key: str,
    model: str,
    rich_context: RichContext | None = None,
) -> DriftResult:
    prompt = build_prompt(diff, context, rich_context)
    data = _call_llm(prompt, llm_provider, api_key, model)
    return _parse_response(data, diff.dataset_urn)


def _call_llm(prompt: str, provider: str, api_key: str, model: str) -> dict:
    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=256,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=[{"role": "user", "content": prompt}],
            timeout=_LLM_TIMEOUT,
        )
        for block in message.content:
            if block.type == "tool_use" and block.name == _TOOL_NAME:
                return block.input
        raise ValueError(f"Anthropic response missing tool_use block: {message.content!r}")

    if provider == "openai":
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=256,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
            timeout=_LLM_TIMEOUT,
        )
        return json.loads(response.choices[0].message.content)

    if provider == "groq":
        client = groq_sdk.Groq(api_key=api_key)
        last_error: json.JSONDecodeError | None = None
        for _ in range(2):
            response = client.chat.completions.create(
                model=model,
                max_tokens=256,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
                timeout=_LLM_TIMEOUT,
            )
            raw = response.choices[0].message.content or ""
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                last_error = exc
        raise ValueError(f"Groq returned non-JSON after 2 attempts: {raw!r}") from last_error

    raise ValueError(f"Unsupported LLM provider: {provider!r}. Use 'anthropic', 'openai', or 'groq'.")  # noqa: E501


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
