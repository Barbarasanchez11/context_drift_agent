"""
Schema drift simulation script.

Changes credit_limit from FLOAT to VARCHAR(16777216) in DataHub,
simulating a schema migration where the field starts storing values
like '5000 EUR' instead of a raw number.

Run this WHILE the agent is polling to trigger the full pipeline.

Usage:
    python scripts/simulate_drift.py          # apply drift (FLOAT -> VARCHAR)
    python scripts/simulate_drift.py --reset  # restore original (VARCHAR -> FLOAT)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    AuditStampClass,
    NumberTypeClass,
    OtherSchemaClass,
    SchemaFieldClass,
    SchemaFieldDataTypeClass,
    SchemaMetadataClass,
    StringTypeClass,
)

DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.customers,PROD)"
GMS_URL = "http://localhost:8080"

_AUDIT_STAMP = AuditStampClass(time=0, actor="urn:li:corpuser:datahub")

_STRING_TYPE = SchemaFieldDataTypeClass(type=StringTypeClass())
_NUMBER_TYPE = SchemaFieldDataTypeClass(type=NumberTypeClass())


def _make_field(path: str, native_type: str, field_type: SchemaFieldDataTypeClass) -> SchemaFieldClass:
    return SchemaFieldClass(
        fieldPath=path,
        type=field_type,
        nativeDataType=native_type,
        nullable=True,
    )


ORIGINAL_SCHEMA: list[SchemaFieldClass] = [
    _make_field("customer_id",      "NUMBER(38,0)",      _NUMBER_TYPE),
    _make_field("cust_first_name",  "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("cust_last_name",   "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("nls_language",     "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("nls_territory",    "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("credit_limit",     "FLOAT",             _NUMBER_TYPE),  # original
    _make_field("cust_email",       "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("account_mgr_id",   "NUMBER(38,0)",      _NUMBER_TYPE),
    _make_field("customer_since",   "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("customer_class",   "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("suggestions",      "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("dob",              "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("mailshot",         "NUMBER(38,0)",      _NUMBER_TYPE),
    _make_field("partner_mailshot", "NUMBER(38,0)",      _NUMBER_TYPE),
    _make_field("phone_number",     "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("address_line1",    "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("address_line2",    "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("address_line3",    "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("town_city",        "VARCHAR(16777216)", _STRING_TYPE),
    _make_field("country_id",       "NUMBER(38,0)",      _NUMBER_TYPE),
    _make_field("zipcode",          "NUMBER(38,0)",      _NUMBER_TYPE),
    _make_field("region_id",        "NUMBER(38,0)",      _NUMBER_TYPE),
]

DRIFTED_SCHEMA: list[SchemaFieldClass] = [
    f if f.fieldPath != "credit_limit"
    else _make_field("credit_limit", "VARCHAR(16777216)", _STRING_TYPE)
    for f in ORIGINAL_SCHEMA
]


def _write_schema(fields: list[SchemaFieldClass], label: str) -> None:
    emitter = DatahubRestEmitter(gms_server=GMS_URL)
    schema = SchemaMetadataClass(
        schemaName="customer",
        platform="urn:li:dataPlatform:snowflake",
        version=0,
        hash="",
        platformSchema=OtherSchemaClass(rawSchema=""),
        fields=fields,
        created=_AUDIT_STAMP,
        lastModified=_AUDIT_STAMP,
    )
    mcp = MetadataChangeProposalWrapper(entityUrn=DATASET_URN, aspect=schema)
    emitter.emit(mcp)
    print(f"Schema written ({label}) for:\n  {DATASET_URN}")
    credit = next(f for f in fields if f.fieldPath == "credit_limit")
    print(f"  credit_limit → {credit.nativeDataType}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate schema drift on credit_limit field")
    parser.add_argument("--reset", action="store_true", help="Restore original FLOAT type")
    args = parser.parse_args()

    if args.reset:
        _write_schema(ORIGINAL_SCHEMA, "ORIGINAL — credit_limit: FLOAT")
        print("\nReset done. credit_limit is back to FLOAT.")
    else:
        _write_schema(DRIFTED_SCHEMA, "DRIFTED — credit_limit: VARCHAR(16777216)")
        print("\nDrift applied. The agent should detect this change within the next poll interval.")


if __name__ == "__main__":
    main()
