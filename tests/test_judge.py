from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.llm.judge import evaluate
from agent.llm.prompts import build_prompt
from agent.models import ContextSnapshot, DriftResult, SchemaDiff

_fixture = json.loads(Path("tests/fixtures/sample_diff.json").read_text())
DIFF = SchemaDiff(**_fixture["diff"])
CONTEXT = ContextSnapshot(**_fixture["context"])

VALID_DATA = {
    "context_stale": True,
    "context_confidence": 0.92,
    "context_drift_reason": "Field type changed from NUMBER to STRING, description implies numeric value.",
}


class TestBuildPrompt:
    def test_includes_field_change(self) -> None:
        prompt = build_prompt(DIFF, CONTEXT)
        assert "credit_limit" in prompt
        assert "NUMBER" in prompt
        assert "STRING" in prompt

    def test_includes_description(self) -> None:
        prompt = build_prompt(DIFF, CONTEXT)
        assert "Maximum credit amount for the customer" in prompt

    def test_includes_dataset_urn(self) -> None:
        prompt = build_prompt(DIFF, CONTEXT)
        assert DIFF.dataset_urn in prompt


def _make_anthropic_tool_response(data: dict) -> MagicMock:
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "report_drift"
    tool_block.input = data
    message = MagicMock()
    message.content = [tool_block]
    client = MagicMock()
    client.messages.create.return_value = message
    return client


def _make_groq_response(text: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = text
    response = MagicMock()
    response.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


class TestEvaluate:
    def test_returns_drift_result_for_anthropic(self) -> None:
        mock_client = _make_anthropic_tool_response(VALID_DATA)
        with patch("agent.llm.judge.anthropic.Anthropic", return_value=mock_client):
            result = evaluate(DIFF, CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6")

        assert isinstance(result, DriftResult)
        assert result.context_stale is True
        assert result.context_confidence == pytest.approx(0.92)
        assert result.dataset_urn == DIFF.dataset_urn

    def test_anthropic_uses_tool_use_with_timeout(self) -> None:
        mock_client = _make_anthropic_tool_response(VALID_DATA)
        with patch("agent.llm.judge.anthropic.Anthropic", return_value=mock_client):
            evaluate(DIFF, CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["timeout"] == 30
        assert any(t["name"] == "report_drift" for t in call_kwargs["tools"])
        assert call_kwargs["tool_choice"] == {"type": "tool", "name": "report_drift"}

    def test_groq_strips_markdown_fenced_json(self) -> None:
        wrapped = f"```json\n{json.dumps(VALID_DATA)}\n```"
        mock_client = _make_groq_response(wrapped)
        with patch("agent.llm.judge.groq_sdk.Groq", return_value=mock_client):
            result = evaluate(DIFF, CONTEXT, "groq", "fake-key", "llama-3.1-8b-instant")

        assert result.context_stale is True
        assert result.context_confidence == pytest.approx(0.92)

    def test_groq_strips_plain_code_fence(self) -> None:
        wrapped = f"```\n{json.dumps(VALID_DATA)}\n```"
        mock_client = _make_groq_response(wrapped)
        with patch("agent.llm.judge.groq_sdk.Groq", return_value=mock_client):
            result = evaluate(DIFF, CONTEXT, "groq", "fake-key", "llama-3.1-8b-instant")

        assert result.context_stale is True

    def test_raises_value_error_on_non_json_response(self) -> None:
        mock_client = _make_groq_response("I cannot answer this question.")
        with patch("agent.llm.judge.groq_sdk.Groq", return_value=mock_client):
            with pytest.raises(ValueError, match="non-JSON"):
                evaluate(DIFF, CONTEXT, "groq", "fake-key", "llama-3.1-8b-instant")

    def test_raises_value_error_on_missing_fields(self) -> None:
        incomplete = json.dumps({"context_stale": True})
        mock_client = _make_groq_response(incomplete)
        with patch("agent.llm.judge.groq_sdk.Groq", return_value=mock_client):
            with pytest.raises(ValueError, match="missing fields"):
                evaluate(DIFF, CONTEXT, "groq", "fake-key", "llama-3.1-8b-instant")

    def test_raises_on_anthropic_timeout(self) -> None:
        client = MagicMock()
        client.messages.create.side_effect = TimeoutError("Connection timed out")
        with patch("agent.llm.judge.anthropic.Anthropic", return_value=client):
            with pytest.raises(TimeoutError):
                evaluate(DIFF, CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6")

    def test_raises_on_unknown_provider(self) -> None:
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            evaluate(DIFF, CONTEXT, "cohere", "fake-key", "command")
