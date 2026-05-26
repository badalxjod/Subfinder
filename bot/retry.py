"""
bot/retry.py — Retry wrapper for Telegram API calls.

FIX: Original code had no retry logic on final file send, causing silent
     failures when Telegram returned FloodWait or transient network errors.

Usage:
    async def _factory():
        buf = io.BytesIO(content.encode())
        buf.name = "file.txt"
        return await bot.send_document(chat_id=..., document=buf, ...)

    await send_with_retry(_factory, max_retries=5)

IMPORTANT: The factory must be a zero-arg callable that returns a fresh
coroutine each time, because a BytesIO object cannot be reused after the
first send (the stream position is at the end).
"""

import asyncio
from typing import Callable, Awaitable, Any

from telegram.error import RetryAfter, TimedOut, NetworkError, BadRequest

from bot.logger import log


async def send_with_retry(
    coro_factory: Callable[[], Awaitable[Any]],
    max_retries: int = 5,
    base_delay:  float = 2.0,
) -> Any:
    """
    Call coro_factory() up to max_retries times.

    Retry strategy:
      • RetryAfter (FloodWait) → sleep exactly retry_after + 1.5 s
      • TimedOut / NetworkError  → exponential back-off (2^attempt * base_delay)
      • BadRequest               → not retried (permanent error)
      • Other exceptions         → exponential back-off, re-raise on last attempt
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await coro_factory()

        except RetryAfter as exc:
            wait = float(exc.retry_after) + 1.5
            log.warning(
                f"[Retry] FloodWait {wait:.1f}s — attempt {attempt}/{max_retries}"
            )
            await asyncio.sleep(wait)
            last_exc = exc

        except (TimedOut, NetworkError) as exc:
            wait = base_delay * (2 ** (attempt - 1))
            log.warning(
                f"[Retry] {type(exc).__name__} — backoff {wait:.1f}s "
                f"(attempt {attempt}/{max_retries})"
            )
            await asyncio.sleep(wait)
            last_exc = exc

        except BadRequest as exc:
            log.error(f"[Retry] BadRequest (permanent — not retrying): {exc}")
            raise

        except Exception as exc:
            wait = base_delay * (2 ** (attempt - 1))
            log.error(
                f"[Retry] {type(exc).__name__}: {exc} — backoff {wait:.1f}s "
                f"(attempt {attempt}/{max_retries})"
            )
            await asyncio.sleep(wait)
            last_exc = exc

    log.error(f"[Retry] All {max_retries} attempts exhausted. Last: {last_exc}")
    raise last_exc  # type: ignore[misc]
