from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.llm.validator import validate_context_sufficiency
from agent.models import ContextSnapshot, ValidationResult

RICH_CONTEXT = ContextSnapshot(
    dataset_urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,customers,PROD)",
    description="Customer master table. credit_limit is the maximum credit in USD. "
                "high_value_customer flag indicates lifetime value > $10,000.",
    glossary_terms=["CreditLimit", "HighValueCustomer"],
    custom_properties={},
)

THIN_CONTEXT = ContextSnapshot(
    dataset_urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,customers,PROD)",
    description=None,
    glossary_terms=[],
    custom_properties={},
)

_QUESTIONS_RESPONSE = json.dumps({
    "questions": [
        "What does credit_limit represent?",
        "Can I use this table to filter high-value customers?",
        "What currency is credit_limit stored in?",
    ]
})


def _make_text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    message = MagicMock()
    message.content = [block]
    client = MagicMock()
    client.messages.create.return_value = message
    return client


class TestValidateContextSufficiency:
    def test_rich_context_returns_answerable_true(self) -> None:
        high_confidence_answer = json.dumps({
            "answered": True, "confidence": 0.9,
            "reasoning": "Description clearly explains this field."
        })
        responses = iter([_QUESTIONS_RESPONSE] + [high_confidence_answer] * 3)
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = lambda **kw: _msg(next(responses))

        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = validate_context_sufficiency(
                RICH_CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6"
            )

        assert isinstance(result, ValidationResult)
        assert result.context_answerable is True
        assert result.context_qa_confidence > 0.5
        assert len(result.questions) == 3

    def test_thin_context_returns_answerable_false(self) -> None:
        low_confidence_answer = json.dumps({
            "answered": False, "confidence": 0.1,
            "reasoning": "No description available."
        })
        responses = iter([_QUESTIONS_RESPONSE] + [low_confidence_answer] * 3)
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = lambda **kw: _msg(next(responses))

        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = validate_context_sufficiency(
                THIN_CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6"
            )

        assert result.context_answerable is False
        assert result.context_qa_confidence <= 0.5

    def test_partial_failure_continues_and_averages_correctly(self) -> None:
        good_answer = json.dumps({"answered": True, "confidence": 0.8, "reasoning": "Clear."})
        bad_answer = json.dumps({"answered": False, "confidence": 0.2, "reasoning": "Unclear."})
        # question 1 good, question 2 good, question 3 bad
        responses = iter([_QUESTIONS_RESPONSE, good_answer, good_answer, bad_answer])
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = lambda **kw: _msg(next(responses))

        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = validate_context_sufficiency(
                RICH_CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6"
            )

        assert len(result.questions) == 3
        expected_avg = round((0.8 + 0.8 + 0.2) / 3, 4)
        assert result.context_qa_confidence == pytest.approx(expected_avg, abs=0.001)
        assert result.context_answerable is True  # avg = 0.6 > 0.5


def _msg(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    message = MagicMock()
    message.content = [block]
    return message
