from __future__ import annotations

import json
from datetime import UTC, datetime

import anthropic
import groq as groq_sdk
import openai

from agent.llm.prompts import build_prompt
from agent.models import ContextSnapshot, DriftResult, SchemaDiff


def evaluate(
    diff: SchemaDiff,
    context: ContextSnapshot,
    llm_provider: str,
    api_key: str,
    model: str,
) -> DriftResult:
    prompt = build_prompt(diff, context)
    raw_text = _call_llm(prompt, llm_provider, api_key, model)
    return _parse_response(raw_text, diff.dataset_urn)


def _call_llm(prompt: str, provider: str, api_key: str, model: str) -> str:
    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    if provider == "openai":
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    if provider == "groq":
        client = groq_sdk.Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    raise ValueError(f"Unsupported LLM provider: {provider!r}. Use 'anthropic', 'openai', or 'groq'.")


def _parse_response(raw_text: str, dataset_urn: str) -> DriftResult:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON response: {raw_text!r}") from exc

    required = {"context_stale", "context_confidence", "context_drift_reason"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"LLM response missing fields {missing}: {raw_text!r}")

    return DriftResult(
        dataset_urn=dataset_urn,
        evaluated_at=datetime.now(UTC),
        context_stale=bool(data["context_stale"]),
        context_confidence=float(data["context_confidence"]),
        context_drift_reason=str(data["context_drift_reason"]),
    )
