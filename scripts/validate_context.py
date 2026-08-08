from __future__ import annotations

import argparse
import logging
import sys

from agent.config import Settings
from agent.datahub.graphql import get_context
from agent.datahub.writer import write_qa_result
from agent.llm.validator import validate_context_sufficiency

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate whether a dataset's documentation is sufficient for AI agents."
    )
    parser.add_argument("urn", help="Dataset URN to validate")
    args = parser.parse_args()

    settings = Settings()
    urn: str = args.urn

    log.info("Fetching context for %s", urn)
    context = get_context(urn, settings.datahub_gms_url, settings.datahub_token)

    if not context.description and not context.glossary_terms:
        log.warning("Dataset has no description or glossary terms — validation will likely fail")

    log.info("Running synthetic context validation (3 questions)...")
    result = validate_context_sufficiency(
        context,
        settings.llm_provider,
        settings.get_api_key(),
        settings.llm_model,
    )

    print("\n=== Synthetic Context Validation ===")
    print(f"Dataset:              {urn}")
    print(f"context_answerable:   {result.context_answerable}")
    print(f"context_qa_confidence:{result.context_qa_confidence:.2f}")
    print()
    for i, answer in enumerate(result.questions, 1):
        status = "PASS" if answer.answered else "FAIL"
        print(f"Q{i} [{status}] {answer.question}")
        print(f"     confidence={answer.confidence:.2f} — {answer.reasoning}")
    print()

    log.info("Writing results to DataHub...")
    try:
        write_qa_result(
            urn=urn,
            result=result,
            gms_url=settings.datahub_gms_url,
            token=settings.datahub_token,
            existing_description=context.description,
        )
        log.info("Done. Properties written: context_answerable, context_qa_confidence")
    except Exception as exc:
        log.error("Writeback failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
