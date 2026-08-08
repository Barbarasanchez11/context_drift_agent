from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SchemaField(BaseModel):
    field_path: str
    native_data_type: str
    description: str | None = None


class DownstreamAsset(BaseModel):
    urn: str
    name: str
    entity_type: str  # "DATASET", "DASHBOARD", "CHART", etc.
    platform: str | None = None


class RichContext(BaseModel):
    """Extended context fetched via DataHub MCP Server (lineage + ownership)."""

    dataset_urn: str
    downstream_assets: list[DownstreamAsset] = []
    owners: list[str] = []
    domain: str | None = None
    data_source: Literal["mcp", "unavailable"] = "unavailable"


class FieldChange(BaseModel):
    field_path: str
    old_type: str | None
    new_type: str | None
    change_type: Literal["added", "removed", "type_changed"]


class SchemaDiff(BaseModel):
    dataset_urn: str
    detected_at: datetime
    changed_fields: list[FieldChange]
    previous_fields: list[SchemaField]
    current_fields: list[SchemaField]


class ContextSnapshot(BaseModel):
    dataset_urn: str
    description: str | None
    glossary_terms: list[str]
    custom_properties: dict[str, str]


class DriftResult(BaseModel):
    dataset_urn: str
    evaluated_at: datetime
    context_stale: bool
    context_confidence: float
    context_drift_reason: str


class AnswerResult(BaseModel):
    question: str
    answered: bool
    confidence: float
    reasoning: str


class ValidationResult(BaseModel):
    questions: list[AnswerResult]
    context_answerable: bool  # True if avg_confidence > 0.5
    context_qa_confidence: float  # average confidence across all questions
