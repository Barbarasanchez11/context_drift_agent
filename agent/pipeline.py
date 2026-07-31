from __future__ import annotations

import logging

from agent.config import Settings
from agent.datahub.graphql import get_context, get_schema
from agent.datahub.poller import run_poll_loop
from agent.datahub.writer import write_drift_result
from agent.llm.judge import evaluate
from agent.models import SchemaDiff

logger = logging.getLogger(__name__)


def run(settings: Settings) -> None:
    urns = settings.get_urns()
    if not urns:
        raise ValueError("No dataset URNs configured. Set DATASET_URNS in your .env file.")

    logger.info("Starting Context Drift Agent — watching %d dataset(s)", len(urns))
    logger.info("Poll interval: %ds | LLM provider: %s | Model: %s",
                settings.poll_interval_seconds, settings.llm_provider, settings.llm_model)

    def get_schema_fn(urn: str) -> list:
        return get_schema(urn, settings.datahub_gms_url, settings.datahub_token)

    def on_change(diff: SchemaDiff) -> None:
        logger.info("Schema change detected for %s — %d field(s) changed",
                    diff.dataset_urn, len(diff.changed_fields))

        context = get_context(diff.dataset_urn, settings.datahub_gms_url, settings.datahub_token)
        logger.info("Context retrieved: description=%r, glossary_terms=%s",
                    context.description, context.glossary_terms)

        result = evaluate(
            diff=diff,
            context=context,
            llm_provider=settings.llm_provider,
            api_key=settings.get_api_key(),
            model=settings.llm_model,
        )
        logger.info("LLM evaluation: context_stale=%s, confidence=%.2f",
                    result.context_stale, result.context_confidence)
        logger.info("Reason: %s", result.context_drift_reason)

        write_drift_result(diff.dataset_urn, result, settings.datahub_gms_url, settings.datahub_token)
        logger.info("Drift result written to DataHub for %s", diff.dataset_urn)

    run_poll_loop(
        urns=urns,
        interval_seconds=settings.poll_interval_seconds,
        on_change=on_change,
        get_schema_fn=get_schema_fn,
    )
