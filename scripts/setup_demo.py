"""
Demo setup script.

Writes a description and attaches a glossary term to the customers dataset
in DataHub so the LLM judge has rich context to evaluate against.
Run once before starting the agent.

Usage:
    python scripts/setup_demo.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    AuditStampClass,
    DatasetPropertiesClass,
    GlossaryTermAssociationClass,
    GlossaryTermInfoClass,
    GlossaryTermsClass,
)

DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.customers,PROD)"  # noqa: E501
GLOSSARY_TERM_URN = "urn:li:glossaryTerm:Finance.NumericMetric"
GMS_URL = "http://localhost:8080"

DESCRIPTION = (
    "Customer master table. The credit_limit field represents the maximum credit amount "
    "approved for each customer, stored as a numeric value in the account currency."
)

_AUDIT_STAMP = AuditStampClass(time=0, actor="urn:li:corpuser:datahub")


def main() -> None:
    emitter = DatahubRestEmitter(gms_server=GMS_URL)

    emitter.emit(MetadataChangeProposalWrapper(
        entityUrn=DATASET_URN,
        aspect=DatasetPropertiesClass(
            description=DESCRIPTION,
            customProperties={},
        ),
    ))
    print(f"Description written for:\n  {DATASET_URN}")

    emitter.emit(MetadataChangeProposalWrapper(
        entityUrn=GLOSSARY_TERM_URN,
        aspect=GlossaryTermInfoClass(
            definition=(
                "A field that stores a numeric financial measurement such as "
                "an amount, limit, or balance. Values are expected to be numbers."
            ),
            name="NumericMetric",
            termSource="INTERNAL",
        ),
    ))
    print(f"\nGlossary term created:\n  {GLOSSARY_TERM_URN}")

    emitter.emit(MetadataChangeProposalWrapper(
        entityUrn=DATASET_URN,
        aspect=GlossaryTermsClass(
            terms=[GlossaryTermAssociationClass(urn=GLOSSARY_TERM_URN)],
            auditStamp=_AUDIT_STAMP,
        ),
    ))
    print("\nGlossary term attached to dataset.")
    print("\nDone. You can now start the agent with: python -m agent")


if __name__ == "__main__":
    main()
