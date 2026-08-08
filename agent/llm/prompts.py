from __future__ import annotations

from agent.models import ContextSnapshot, RichContext, SchemaDiff


def build_prompt(
    diff: SchemaDiff,
    context: ContextSnapshot,
    rich_context: RichContext | None = None,
) -> str:
    changed_fields_block = "\n".join(
        f"  - {fc.field_path}: {fc.old_type} → {fc.new_type} ({fc.change_type})"
        for fc in diff.changed_fields
    )
    glossary = ", ".join(context.glossary_terms) if context.glossary_terms else "none"
    description = context.description or "(no description)"

    downstream_block = ""
    if rich_context and rich_context.downstream_assets:
        assets = rich_context.downstream_assets[:10]
        lines = "\n".join(
            f"  - {a.name} ({a.entity_type}{', ' + a.platform if a.platform else ''})"
            for a in assets
        )
        total = len(rich_context.downstream_assets)
        suffix = f" (showing {len(assets)} of {total})" if total > len(assets) else ""
        downstream_block = f"\n## Downstream impact{suffix}\n{lines}\n"

    owners_block = ""
    if rich_context and rich_context.owners:
        owner_names = [u.split(":")[-1] for u in rich_context.owners]
        owners_block = f"\nOwners: {', '.join(owner_names)}"

    domain_block = ""
    if rich_context and rich_context.domain:
        domain_block = f"\nDomain: {rich_context.domain}"

    return f"""You are a data governance assistant. \
Given a schema change and existing dataset context, \
evaluate whether the existing documentation is still accurate.

## Schema change detected
Dataset: {diff.dataset_urn}
Changed fields:
{changed_fields_block}

## Existing context
Description: "{description}"
Glossary terms: {glossary}{owners_block}{domain_block}
{downstream_block}
## Task
Respond with ONLY a JSON object — no preamble, no explanation outside the JSON.
context_confidence must be the probability (0.0–1.0) that your context_stale verdict is correct.
Example: 90% sure context is stale → context_stale=true, context_confidence=0.9.
{{
  "context_stale": <true|false>,
  "context_confidence": <float 0.0–1.0>,
  "context_drift_reason": "<≤500 chars, explain why the existing context is or is not still valid>"
}}"""


def build_question_generation_prompt(context: ContextSnapshot) -> str:  # noqa: E501
    description = context.description or "(no description)"
    glossary = ", ".join(context.glossary_terms) if context.glossary_terms else "none"

    return (  # noqa: E501
        f"You are a data analyst. Given a dataset's documentation, "
        "generate exactly 3 realistic questions that a downstream "
        "AI agent might ask before using this dataset.\n\n"
        "## Dataset documentation\n"
        f'Description: "{description}"\n'
        f"Glossary terms: {glossary}\n\n"
        "## Task\n"
        "Generate questions that test whether the documentation is "
        "sufficient for an AI agent to use this dataset with confidence. "
        "Questions must be grounded in the actual content described — "
        "not generic.\n\n"
        "Respond with ONLY a JSON object — no preamble, no explanation "
        "outside the JSON:\n"
        "{\n"
        '  "questions": [\n'
        '    "<specific question 1>",\n'
        '    "<specific question 2>",\n'
        '    "<specific question 3>"\n'
        "  ]\n"
        "}"
    )


def build_answer_prompt(question: str, context: ContextSnapshot) -> str:  # noqa: E501
    description = context.description or "(no description)"
    glossary = ", ".join(context.glossary_terms) if context.glossary_terms else "none"

    return (  # noqa: E501
        "You are a data analyst. Answer the question using ONLY the "
        "documentation provided below. Do NOT use external knowledge or "
        "assumptions beyond what is written.\n\n"
        "## Dataset documentation\n"
        f'Description: "{description}"\n'
        f"Glossary terms: {glossary}\n\n"
        "## Question\n"
        f"{question}\n\n"
        "## Task\n"
        "If the documentation contains enough information to answer "
        "confidently, set answered=true and confidence accordingly.\n"
        "If the documentation is too vague or missing key information, "
        "set answered=false.\n\n"
        "Respond with ONLY a JSON object — no preamble, no explanation "
        "outside the JSON:\n"
        "{\n"
        '  "answered": <true|false>,\n'
        '  "confidence": <float 0.0-1.0>,\n'
        '  "reasoning": "<one sentence explaining why you can or cannot answer>"\n'
        "}"
    )
