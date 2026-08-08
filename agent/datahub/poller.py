from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from agent.models import FieldChange, SchemaDiff, SchemaField

logger = logging.getLogger(__name__)


def compute_schema_hash(fields: list[SchemaField]) -> str:
    sorted_pairs = sorted((f.field_path, f.native_data_type) for f in fields)
    payload = json.dumps(sorted_pairs, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def detect_change(
    urn: str,
    current_fields: list[SchemaField],
    previous_fields: list[SchemaField],
) -> SchemaDiff | None:
    if compute_schema_hash(current_fields) == compute_schema_hash(previous_fields):
        return None

    previous_by_path = {f.field_path: f for f in previous_fields}
    current_by_path = {f.field_path: f for f in current_fields}

    changes: list[FieldChange] = []

    for path, field in current_by_path.items():
        if path not in previous_by_path:
            changes.append(
                FieldChange(
                    field_path=path,
                    old_type=None,
                    new_type=field.native_data_type,
                    change_type="added",
                )
            )
        elif previous_by_path[path].native_data_type != field.native_data_type:
            changes.append(FieldChange(
                field_path=path,
                old_type=previous_by_path[path].native_data_type,
                new_type=field.native_data_type,
                change_type="type_changed",
            ))

    for path, field in previous_by_path.items():
        if path not in current_by_path:
            changes.append(
                FieldChange(
                    field_path=path,
                    old_type=field.native_data_type,
                    new_type=None,
                    change_type="removed",
                )
            )

    return SchemaDiff(
        dataset_urn=urn,
        detected_at=datetime.now(UTC),
        changed_fields=changes,
        previous_fields=previous_fields,
        current_fields=current_fields,
    )


def _load_state(state_path: Path) -> dict:
    if state_path.exists():
        return json.loads(state_path.read_text())
    return {}


def _save_state(urn: str, fields: list[SchemaField], state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = _load_state(state_path)
    state[urn] = {
        "hash": compute_schema_hash(fields),
        "fields": [f.model_dump() for f in fields],
        "last_checked": datetime.now(UTC).isoformat(),
    }
    state_path.write_text(json.dumps(state, indent=2))


def run_poll_loop(
    urns: list[str],
    interval_seconds: int,
    on_change: Callable[[SchemaDiff], None],
    get_schema_fn: Callable[[str], list[SchemaField]],
    state_path: Path = Path(".state/schema_hashes.json"),
) -> None:
    while True:
        for urn in urns:
            try:
                current = get_schema_fn(urn)
                state = _load_state(state_path)

                if urn not in state:
                    _save_state(urn, current, state_path)
                    logger.info("Initial schema stored for %s", urn)
                    continue

                previous = [SchemaField(**f) for f in state[urn]["fields"]]
                diff = detect_change(urn, current, previous)

                if diff:
                    logger.info(
                        "Schema change detected for %s: %d field(s) changed",
                        urn,
                        len(diff.changed_fields),
                    )
                    _save_state(urn, current, state_path)
                    on_change(diff)
                else:
                    _save_state(urn, current, state_path)

            except Exception as exc:
                if isinstance(exc, StopIteration):
                    raise
                logger.warning("Poll error for %s: %s", urn, exc)

        time.sleep(interval_seconds)
