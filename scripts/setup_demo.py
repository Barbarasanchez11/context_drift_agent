"""
Demo setup script.

Writes a description to the customers dataset in DataHub so the LLM judge
has context to evaluate against. Run once before starting the agent.

Usage:
    python scripts/setup_demo.py
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import DatasetPropertiesClass

DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.customers,PROD)"
GMS_URL = "http://localhost:8080"

DESCRIPTION = (
    "Customer master table. The credit_limit field represents the maximum credit amount "
    "approved for each customer, stored as a numeric value in the account currency."
)


def main() -> None:
    emitter = DatahubRestEmitter(gms_server=GMS_URL)
    mcp = MetadataChangeProposalWrapper(
        entityUrn=DATASET_URN,
        aspect=DatasetPropertiesClass(
            description=DESCRIPTION,
            customProperties={},
        ),
    )
    emitter.emit(mcp)
    print(f"Description written to DataHub for:\n  {DATASET_URN}")
    print(f"\nDescription:\n  {DESCRIPTION}")
    print("\nDone. You can now start the agent with: python -m agent")


if __name__ == "__main__":
    main()
