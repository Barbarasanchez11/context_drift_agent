from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.llm.adversarial_judge import evaluate_adversarial
from agent.models import ContextSnapshot, DriftResult, SchemaDiff

_fixture = json.loads(Path("tests/fixtures/sample_diff.json").read_text())
DIFF = SchemaDiff(**_fixture["diff"])
CONTEXT = ContextSnapshot(**_fixture["context"])


def _make_anthropic_tool_response(data: dict) -> MagicMock:
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "report_drift"
    tool_block.input = data
    message = MagicMock()
    message.content = [tool_block]
    return message


def _make_anthropic_client_with_side_effects(responses: list[dict]) -> MagicMock:
    messages = [_make_anthropic_tool_response(r) for r in responses]
    client = MagicMock()
    client.messages.create.side_effect = messages
    return client


class TestAdversarialJudge:
    def test_consensus_stale_returns_stale_true(self) -> None:
        """Both agents agree context is stale → context_stale=True, confidence is average."""
        prosecutor_data = {
            "context_stale": True,
            "context_confidence": 0.9,
            "context_drift_reason": "Field changed from NUMBER to STRING; description is invalid.",
        }
        defender_data = {
            "context_stale": True,
            "context_confidence": 0.8,
            "context_drift_reason": "Type change warrants updating the description.",
        }
        mock_client = _make_anthropic_client_with_side_effects([prosecutor_data, defender_data])

        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = evaluate_adversarial(
                DIFF, CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6"
            )

        assert isinstance(result, DriftResult)
        assert result.context_stale is True
        assert result.context_confidence == pytest.approx(0.85, abs=1e-4)
        assert result.context_drift_reason.startswith("[Consensus]")
        assert mock_client.messages.create.call_count == 2

    def test_consensus_not_stale_returns_stale_false(self) -> None:
        """Both agents agree context is NOT stale → context_stale=False."""
        prosecutor_data = {
            "context_stale": False,
            "context_confidence": 0.75,
            "context_drift_reason": "The description is generic enough to remain valid.",
        }
        defender_data = {
            "context_stale": False,
            "context_confidence": 0.85,
            "context_drift_reason": "No evidence the description needs updating after this change.",
        }
        mock_client = _make_anthropic_client_with_side_effects([prosecutor_data, defender_data])

        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = evaluate_adversarial(
                DIFF, CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6"
            )

        assert isinstance(result, DriftResult)
        assert result.context_stale is False
        assert result.context_confidence == pytest.approx(0.8, abs=1e-4)
        assert result.context_drift_reason.startswith("[Consensus]")
        assert mock_client.messages.create.call_count == 2

    def test_disagreement_caps_confidence_and_marks_disputed(self) -> None:
        """Agents disagree → confidence capped at 0.7, reason contains '[Disputed]'."""
        prosecutor_data = {
            "context_stale": True,
            "context_confidence": 0.95,
            "context_drift_reason": "Type change invalidates numeric description.",
        }
        defender_data = {
            "context_stale": False,
            "context_confidence": 0.6,
            "context_drift_reason": "Description is vague enough to still apply.",
        }
        mock_client = _make_anthropic_client_with_side_effects([prosecutor_data, defender_data])

        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = evaluate_adversarial(
                DIFF, CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6"
            )

        assert isinstance(result, DriftResult)
        # Average of 0.95 and 0.6 is 0.775, but capped at 0.7
        assert result.context_confidence <= 0.7
        assert "[Disputed]" in result.context_drift_reason
        assert "Prosecutor:" in result.context_drift_reason
        assert "Defender:" in result.context_drift_reason
        assert mock_client.messages.create.call_count == 2
