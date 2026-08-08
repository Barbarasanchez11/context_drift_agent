from __future__ import annotations

import logging
from datetime import UTC, datetime

from agent.llm.client import call_llm
from agent.llm.prompts import build_adversarial_defender_prompt, build_adversarial_prosecutor_prompt
from agent.models import ContextSnapshot, DriftResult, RichContext, SchemaDiff

log = logging.getLogger(__name__)

_TOOL_NAME = "report_drift"
_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": "Report whether the dataset context is stale after a schema change.",
    "input_schema": {
        "type": "object",
        "properties": {
            "context_stale": {"type": "boolean"},
            "context_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "context_drift_reason": {"type": "string"},
        },
        "required": ["context_stale", "context_confidence", "context_drift_reason"],
    },
}


def evaluate_adversarial(
    diff: SchemaDiff,
    context: ContextSnapshot,
    llm_provider: str,
    api_key: str,
    model: str,
    rich_context: RichContext | None = None,
) -> DriftResult:
    prosecutor_prompt = build_adversarial_prosecutor_prompt(diff, context, rich_context)
    defender_prompt = build_adversarial_defender_prompt(diff, context, rich_context)

    log.debug("Adversarial evaluation: calling prosecutor...")
    prosecutor = call_llm(
        prosecutor_prompt,
        llm_provider,
        api_key,
        model,
        tool_name=_TOOL_NAME,
        tool_schema=_TOOL_SCHEMA,
    )
    log.debug("Adversarial evaluation: calling defender...")
    defender = call_llm(
        defender_prompt,
        llm_provider,
        api_key,
        model,
        tool_name=_TOOL_NAME,
        tool_schema=_TOOL_SCHEMA,
    )

    return _arbitrate(prosecutor, defender, diff.dataset_urn)


def _arbitrate(prosecutor: dict, defender: dict, dataset_urn: str) -> DriftResult:
    p_stale = bool(prosecutor["context_stale"])
    d_stale = bool(defender["context_stale"])
    p_conf = float(prosecutor["context_confidence"])
    d_conf = float(defender["context_confidence"])

    if p_stale == d_stale:
        final_stale = p_stale
        final_confidence = round((p_conf + d_conf) / 2, 4)
        reason = f"[Consensus] {prosecutor['context_drift_reason']}"
    else:
        # Disagreement — pick higher-confidence verdict, cap confidence at 0.7
        final_confidence = round(min((p_conf + d_conf) / 2, 0.7), 4)
        if p_conf >= d_conf:
            final_stale = p_stale
        else:
            final_stale = d_stale
        reason = (
            f"[Disputed] Prosecutor: {prosecutor['context_drift_reason']} | "
            f"Defender: {defender['context_drift_reason']}"
        )

    return DriftResult(
        dataset_urn=dataset_urn,
        evaluated_at=datetime.now(UTC),
        context_stale=final_stale,
        context_confidence=final_confidence,
        context_drift_reason=reason[:500],
    )
