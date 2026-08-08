from __future__ import annotations

import logging
import sys

from agent import pipeline
from agent.config import Settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    try:
        settings = Settings()
        pipeline.run(settings)
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Agent stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
