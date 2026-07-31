from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SchemaField(BaseModel):
    field_path: str
    native_data_type: str
    description: str | None = None


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
