from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.llm.client import call_llm


def _make_anthropic_text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "message"
    block.text = text
    message = MagicMock()
    message.content = [block]
    client = MagicMock()
    client.messages.create.return_value = message
    return client


class TestCallLlm:
    def test_anthropic_json_mode_returns_dict(self) -> None:
        data = {"answered": True, "confidence": 0.9, "reasoning": "clear"}
        mock_client = _make_anthropic_text_response(json.dumps(data))
        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = call_llm("some prompt", "anthropic", "fake-key", "claude-sonnet-4-6")
        assert result == data

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            call_llm("prompt", "cohere", "key", "model")
