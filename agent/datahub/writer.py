from __future__ import annotations

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import DatasetPropertiesClass

from agent.models import DriftResult


def write_drift_result(
    urn: str,
    result: DriftResult,
    gms_url: str,
    token: str | None = None,
) -> None:
    custom_properties = {
        "context_stale": str(result.context_stale).lower(),
        "context_confidence": str(round(result.context_confidence, 4)),
        "context_drift_reason": result.context_drift_reason,
    }

    emitter = DatahubRestEmitter(gms_server=gms_url, token=token)
    mcp = MetadataChangeProposalWrapper(
        entityUrn=urn,
        aspect=DatasetPropertiesClass(customProperties=custom_properties),
    )
    emitter.emit(mcp)
