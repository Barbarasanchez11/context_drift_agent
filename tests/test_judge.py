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

VALID_LLM_RESPONSE = json.dumps({
    "context_stale": True,
    "context_confidence": 0.92,
    "context_drift_reason": "Field type changed from NUMBER to STRING, description implies numeric value.",
})


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


class TestEvaluate:
    def _mock_anthropic_client(self, text: str) -> MagicMock:
        content_block = MagicMock()
        content_block.text = text
        message = MagicMock()
        message.content = [content_block]
        client = MagicMock()
        client.messages.create.return_value = message
        return client

    def test_returns_drift_result_for_anthropic(self) -> None:
        mock_client = self._mock_anthropic_client(VALID_LLM_RESPONSE)
        with patch("agent.llm.judge.anthropic.Anthropic", return_value=mock_client):
            result = evaluate(DIFF, CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6")

        assert isinstance(result, DriftResult)
        assert result.context_stale is True
        assert result.context_confidence == pytest.approx(0.92)
        assert result.dataset_urn == DIFF.dataset_urn

    def test_raises_value_error_on_non_json_response(self) -> None:
        mock_client = self._mock_anthropic_client("I cannot answer this question.")
        with patch("agent.llm.judge.anthropic.Anthropic", return_value=mock_client):
            with pytest.raises(ValueError, match="non-JSON"):
                evaluate(DIFF, CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6")

    def test_raises_value_error_on_missing_fields(self) -> None:
        incomplete = json.dumps({"context_stale": True})
        mock_client = self._mock_anthropic_client(incomplete)
        with patch("agent.llm.judge.anthropic.Anthropic", return_value=mock_client):
            with pytest.raises(ValueError, match="missing fields"):
                evaluate(DIFF, CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6")

    def test_raises_on_unknown_provider(self) -> None:
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            evaluate(DIFF, CONTEXT, "cohere", "fake-key", "command")
