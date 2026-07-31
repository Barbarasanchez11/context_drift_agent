from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from agent.datahub.writer import write_drift_result
from agent.models import DriftResult

URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.customers,PROD)"

RESULT = DriftResult(
    dataset_urn=URN,
    evaluated_at=datetime.now(UTC),
    context_stale=True,
    context_confidence=0.92,
    context_drift_reason="Field credit_limit changed from NUMBER to STRING.",
)


class TestWriteDriftResult:
    def test_emits_correct_custom_properties(self) -> None:
        mock_emitter = MagicMock()
        with patch("agent.datahub.writer.DatahubRestEmitter", return_value=mock_emitter):
            write_drift_result(URN, RESULT, "http://localhost:8080")

        mock_emitter.emit.assert_called_once()
        mcp = mock_emitter.emit.call_args[0][0]
        props = mcp.aspect.customProperties

        assert props["context_stale"] == "true"
        assert props["context_confidence"] == "0.92"
        assert "NUMBER to STRING" in props["context_drift_reason"]

    def test_serializes_false_stale_correctly(self) -> None:
        not_stale = RESULT.model_copy(update={"context_stale": False, "context_confidence": 0.1})
        mock_emitter = MagicMock()
        with patch("agent.datahub.writer.DatahubRestEmitter", return_value=mock_emitter):
            write_drift_result(URN, not_stale, "http://localhost:8080")

        mcp = mock_emitter.emit.call_args[0][0]
        assert mcp.aspect.customProperties["context_stale"] == "false"

    def test_passes_token_to_emitter(self) -> None:
        mock_emitter = MagicMock()
        with patch("agent.datahub.writer.DatahubRestEmitter", return_value=mock_emitter) as mock_cls:
            write_drift_result(URN, RESULT, "http://localhost:8080", token="my-token")

        mock_cls.assert_called_once_with(gms_server="http://localhost:8080", token="my-token")
