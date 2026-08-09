from __future__ import annotations

import logging

from agent.config import Settings
from agent.datahub.graphql import get_context, get_schema
from agent.datahub.poller import run_poll_loop
from agent.datahub.writer import write_drift_result
from agent.llm.adversarial_judge import evaluate_adversarial
from agent.llm.judge import evaluate
from agent.models import RichContext, SchemaDiff

logger = logging.getLogger(__name__)


def _get_rich_context(urn: str, settings: Settings) -> RichContext | None:
    if not settings.use_mcp_context:
        return None
    try:
        from agent.datahub.mcp_context import get_rich_context

        return get_rich_context(urn, settings.datahub_gms_url, settings.datahub_token)
    except ImportError:
        logger.debug("mcp package not installed — skipping MCP context enrichment")
        return None


def run(settings: Settings) -> None:
    urns = settings.get_urns()
    if not urns:
        raise ValueError("No dataset URNs configured. Set DATASET_URNS in your .env file.")

    logger.info("Starting Context Drift Agent — watching %d dataset(s)", len(urns))
    logger.info(
        "Poll interval: %ds | LLM provider: %s | Model: %s | MCP context: %s",
        settings.poll_interval_seconds,
        settings.llm_provider,
        settings.llm_model,
        "enabled" if settings.use_mcp_context else "disabled",
    )

    def get_schema_fn(urn: str) -> list:
        return get_schema(urn, settings.datahub_gms_url, settings.datahub_token)

    def on_change(diff: SchemaDiff) -> None:
        logger.info(
            "Schema change detected for %s — %d field(s) changed",
            diff.dataset_urn,
            len(diff.changed_fields),
        )

        context = get_context(diff.dataset_urn, settings.datahub_gms_url, settings.datahub_token)
        logger.info(
            "Context retrieved: description=%r, glossary_terms=%s",
            context.description,
            context.glossary_terms,
        )

        rich_context = _get_rich_context(diff.dataset_urn, settings)

        if settings.use_adversarial_judge:
            result = evaluate_adversarial(
                diff=diff,
                context=context,
                rich_context=rich_context,
                llm_provider=settings.llm_provider,
                api_key=settings.get_api_key(),
                model=settings.llm_model,
            )
        else:
            result = evaluate(
                diff=diff,
                context=context,
                rich_context=rich_context,
                llm_provider=settings.llm_provider,
                api_key=settings.get_api_key(),
                model=settings.llm_model,
            )
        logger.info(
            "LLM evaluation: context_stale=%s, confidence=%.2f",
            result.context_stale,
            result.context_confidence,
        )
        logger.info("Reason: %s", result.context_drift_reason)

        write_drift_result(
            diff.dataset_urn,
            result,
            settings.datahub_gms_url,
            settings.datahub_token,
            existing_description=context.description,
        )
        logger.info("Drift result written to DataHub for %s", diff.dataset_urn)

    run_poll_loop(
        urns=urns,
        interval_seconds=settings.poll_interval_seconds,
        on_change=on_change,
        get_schema_fn=get_schema_fn,
    )
