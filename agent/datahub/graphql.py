from __future__ import annotations

import base64

import requests

from agent.models import ContextSnapshot, SchemaField

# Default credentials for DataHub OSS local quickstart (overridable via token param)
_DEFAULT_BASIC_AUTH = "Basic " + base64.b64encode(b"datahub:datahub").decode()

_SCHEMA_QUERY = """
query GetSchema($urn: String!) {
  dataset(urn: $urn) {
    schemaMetadata {
      fields {
        fieldPath
        nativeDataType
        description
      }
    }
  }
}
"""

_CONTEXT_QUERY = """
query GetContext($urn: String!) {
  dataset(urn: $urn) {
    properties {
      description
      customProperties { key value }
    }
    glossaryTerms {
      terms { term { name } }
    }
  }
}
"""


def _post(gms_url: str, token: str | None, query: str, variables: dict) -> dict:
    endpoint = f"{gms_url}/api/graphql"
    auth_header = f"Bearer {token}" if token else _DEFAULT_BASIC_AUTH
    headers = {
        "Content-Type": "application/json",
        "Authorization": auth_header,
    }
    response = requests.post(
        endpoint,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(
            f"DataHub GraphQL request failed: {response.status_code} {response.text}"
        )
    return response.json()


def get_schema(
    urn: str,
    gms_url: str,
    token: str | None = None,
) -> list[SchemaField]:
    body: dict = _post(gms_url, token, _SCHEMA_QUERY, {"urn": urn})
    dataset: dict | None = body.get("data", {}).get("dataset")
    if not dataset:
        return []
    schema_metadata: dict | None = dataset.get("schemaMetadata")
    if not schema_metadata:
        return []
    fields: list[dict] = schema_metadata.get("fields") or []
    return [
        SchemaField(
            field_path=f["fieldPath"],
            native_data_type=f["nativeDataType"],
            description=f.get("description"),
        )
        for f in fields
    ]


def get_context(
    urn: str,
    gms_url: str,
    token: str | None = None,
) -> ContextSnapshot:
    body: dict = _post(gms_url, token, _CONTEXT_QUERY, {"urn": urn})
    dataset: dict | None = body.get("data", {}).get("dataset")
    if not dataset:
        return ContextSnapshot(
            dataset_urn=urn,
            description=None,
            glossary_terms=[],
            custom_properties={},
        )
    properties: dict = dataset.get("properties") or {}
    raw_custom: list[dict] = properties.get("customProperties") or []
    custom_properties: dict[str, str] = {e["key"]: e["value"] for e in raw_custom}
    glossary_data: dict | None = dataset.get("glossaryTerms")
    glossary_terms: list[str] = []
    if glossary_data:
        glossary_terms = [
            t["term"]["name"]
            for t in (glossary_data.get("terms") or [])
            if t.get("term")
        ]
    return ContextSnapshot(
        dataset_urn=urn,
        description=properties.get("description"),
        glossary_terms=glossary_terms,
        custom_properties=custom_properties,
    )
