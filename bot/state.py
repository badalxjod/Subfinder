"""
bot/state.py — Lazy asyncio primitives.

asyncio.Lock() must NOT be created at module import time if there is no
running event loop (Python < 3.10 raises DeprecationWarning / RuntimeError).
This module provides a get_scan_lock() helper that creates the lock on first
call, which always happens inside a running coroutine.
"""

import asyncio

_SCAN_LOCK: asyncio.Lock | None = None


def get_scan_lock() -> asyncio.Lock:
    """Return the singleton scan lock, creating it on first call."""
    global _SCAN_LOCK
    if _SCAN_LOCK is None:
        _SCAN_LOCK = asyncio.Lock()
    return _SCAN_LOCK


# Convenience alias — import SCAN_LOCK from here exactly like before,
# but call it as a function: `async with get_scan_lock():`
# Old code used `async with SCAN_LOCK:` — replace those with the helper.
SCAN_LOCK = property(get_scan_lock)  # type: ignore[assignment]
