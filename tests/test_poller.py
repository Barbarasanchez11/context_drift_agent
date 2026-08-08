from __future__ import annotations

from pathlib import Path

from agent.datahub.poller import compute_schema_hash, detect_change, run_poll_loop
from agent.models import SchemaDiff, SchemaField

FIELD_NUMBER = SchemaField(field_path="credit_limit", native_data_type="NUMBER")
FIELD_STRING = SchemaField(field_path="credit_limit", native_data_type="STRING")
FIELD_EMAIL = SchemaField(field_path="cust_email", native_data_type="STRING")


class TestComputeSchemaHash:
    def test_same_hash_regardless_of_input_order(self) -> None:
        fields_a = [FIELD_NUMBER, FIELD_EMAIL]
        fields_b = [FIELD_EMAIL, FIELD_NUMBER]
        assert compute_schema_hash(fields_a) == compute_schema_hash(fields_b)

    def test_different_hash_when_type_changes(self) -> None:
        assert compute_schema_hash([FIELD_NUMBER]) != compute_schema_hash([FIELD_STRING])


class TestDetectChange:
    def test_returns_none_when_schemas_identical(self) -> None:
        fields = [FIELD_NUMBER, FIELD_EMAIL]
        assert detect_change("urn:test", fields, fields) is None

    def test_detects_type_change(self) -> None:
        diff = detect_change("urn:test", [FIELD_STRING], [FIELD_NUMBER])
        assert diff is not None
        assert len(diff.changed_fields) == 1
        fc = diff.changed_fields[0]
        assert fc.field_path == "credit_limit"
        assert fc.old_type == "NUMBER"
        assert fc.new_type == "STRING"
        assert fc.change_type == "type_changed"

    def test_detects_added_field(self) -> None:
        diff = detect_change("urn:test", [FIELD_NUMBER, FIELD_EMAIL], [FIELD_NUMBER])
        assert diff is not None
        added = [fc for fc in diff.changed_fields if fc.change_type == "added"]
        assert len(added) == 1
        assert added[0].field_path == "cust_email"
        assert added[0].old_type is None

    def test_detects_removed_field(self) -> None:
        diff = detect_change("urn:test", [FIELD_NUMBER], [FIELD_NUMBER, FIELD_EMAIL])
        assert diff is not None
        removed = [fc for fc in diff.changed_fields if fc.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].field_path == "cust_email"
        assert removed[0].new_type is None


class TestRunPollLoop:
    def test_calls_on_change_after_schema_change(self, tmp_path: Path) -> None:
        call_count = 0

        def fake_get_schema(urn: str) -> list[SchemaField]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [FIELD_NUMBER]
            raise StopIteration

        changes: list[SchemaDiff] = []
        try:
            run_poll_loop(
                urns=["urn:test"],
                interval_seconds=0,
                on_change=changes.append,
                get_schema_fn=fake_get_schema,
                state_path=tmp_path / "state.json",
            )
        except StopIteration:
            pass

        assert len(changes) == 0

    def test_calls_on_change_when_type_changes(self, tmp_path: Path) -> None:
        call_count = 0

        def fake_get_schema(urn: str) -> list[SchemaField]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [FIELD_NUMBER]
            if call_count == 2:
                return [FIELD_STRING]
            raise StopIteration

        changes: list[SchemaDiff] = []
        try:
            run_poll_loop(
                urns=["urn:test"],
                interval_seconds=0,
                on_change=changes.append,
                get_schema_fn=fake_get_schema,
                state_path=tmp_path / "state.json",
            )
        except StopIteration:
            pass

        assert len(changes) == 1
        assert changes[0].changed_fields[0].change_type == "type_changed"
