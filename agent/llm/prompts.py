from __future__ import annotations

from agent.models import ContextSnapshot, SchemaDiff


def build_prompt(diff: SchemaDiff, context: ContextSnapshot) -> str:
    changed_fields_block = "\n".join(
        f"  - {fc.field_path}: {fc.old_type} → {fc.new_type} ({fc.change_type})"
        for fc in diff.changed_fields
    )
    glossary = ", ".join(context.glossary_terms) if context.glossary_terms else "none"
    description = context.description or "(no description)"

    return f"""You are a data governance assistant. Given a schema change and existing dataset context, evaluate whether the existing documentation is still accurate.

## Schema change detected
Dataset: {diff.dataset_urn}
Changed fields:
{changed_fields_block}

## Existing context
Description: "{description}"
Glossary terms: {glossary}

## Task
Respond with ONLY a JSON object — no preamble, no explanation outside the JSON:
{{
  "context_stale": <true|false>,
  "context_confidence": <0.0-1.0>,
  "context_drift_reason": "<≤500 chars, explain why the existing context is or is not still valid>"
}}"""
