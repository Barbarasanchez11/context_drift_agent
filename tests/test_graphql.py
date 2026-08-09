from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.datahub.graphql import get_context, get_schema
from agent.models import ContextSnapshot, SchemaField

GMS_URL = "http://localhost:8080"
URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,test.schema.table,PROD)"


def _mock_response(payload: dict) -> MagicMock:
    mock = MagicMock()
    mock.ok = True
    mock.json.return_value = payload
    return mock


class TestGetSchema:
    def test_returns_schema_fields(self) -> None:
        payload = {
            "data": {
                "dataset": {
                    "schemaMetadata": {
                        "fields": [
                            {
                                "fieldPath": "credit_limit",
                                "nativeDataType": "NUMBER",
                                "description": None,
                            },  # noqa: E501
                            {
                                "fieldPath": "cust_email",
                                "nativeDataType": "STRING",
                                "description": "Customer email",
                            },  # noqa: E501
                        ]
                    }
                }
            }
        }
        with patch("agent.datahub.graphql.requests.post", return_value=_mock_response(payload)):
            result = get_schema(URN, GMS_URL)

        assert result == [
            SchemaField(field_path="credit_limit", native_data_type="NUMBER", description=None),
            SchemaField(
                field_path="cust_email", native_data_type="STRING", description="Customer email"
            ),  # noqa: E501
        ]

    def test_returns_empty_list_when_schema_metadata_null(self) -> None:
        payload = {"data": {"dataset": {"schemaMetadata": None}}}
        with patch("agent.datahub.graphql.requests.post", return_value=_mock_response(payload)):
            result = get_schema(URN, GMS_URL)
        assert result == []

    def test_returns_empty_list_when_dataset_not_found(self) -> None:
        payload = {"data": {"dataset": None}}
        with patch("agent.datahub.graphql.requests.post", return_value=_mock_response(payload)):
            result = get_schema(URN, GMS_URL)
        assert result == []


class TestGetContext:
    def test_returns_full_context_snapshot(self) -> None:
        payload = {
            "data": {
                "dataset": {
                    "properties": {
                        "description": "Customer records",
                        "customProperties": [
                            {"key": "owner", "value": "data-team"},
                        ],
                    },
                    "glossaryTerms": {"terms": [{"term": {"name": "PII"}}]},
                }
            }
        }
        with patch("agent.datahub.graphql.requests.post", return_value=_mock_response(payload)):
            result = get_context(URN, GMS_URL)

        assert result == ContextSnapshot(
            dataset_urn=URN,
            description="Customer records",
            glossary_terms=["PII"],
            custom_properties={"owner": "data-team"},
        )

    def test_handles_missing_glossary_terms(self) -> None:
        payload = {
            "data": {
                "dataset": {
                    "properties": {"description": "No terms", "customProperties": []},
                    "glossaryTerms": None,
                }
            }
        }
        with patch("agent.datahub.graphql.requests.post", return_value=_mock_response(payload)):
            result = get_context(URN, GMS_URL)

        assert result.glossary_terms == []
        assert result.description == "No terms"

    def test_returns_empty_snapshot_when_dataset_not_found(self) -> None:
        payload = {"data": {"dataset": None}}
        with patch("agent.datahub.graphql.requests.post", return_value=_mock_response(payload)):
            result = get_context(URN, GMS_URL)

        assert result == ContextSnapshot(
            dataset_urn=URN,
            description=None,
            glossary_terms=[],
            custom_properties={},
        )
