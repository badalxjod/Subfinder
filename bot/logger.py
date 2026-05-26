"""
bot/logger.py — Central logging configuration.
Import `log` from here in every module.
"""

import logging
from bot.config import LOG_FILE


def _setup() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,   # DEBUG is too noisy for VPS production
        format="%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        ],
    )
    logger = logging.getLogger("SubHunter")

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "telegram", "urllib3", "asyncio", "aiohttp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger.info("=" * 60)
    logger.info("SubHunter Bot — Logger initialised")
    logger.info("=" * 60)
    return logger


log: logging.Logger = _setup()
