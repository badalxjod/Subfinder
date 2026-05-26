"""
bot/scanner/engine.py — Core scan engine.

scan_single_domain()    — hits all 16 sources in parallel for one domain
scan_domains_parallel() — runs N domains concurrently (semaphore-limited)

FIX v5.0:
  • Removed domain_done_cb — it was called INSIDE asyncio.Lock, causing
    sequential Telegram sends and triggering FloodWait on large batches.
  • asyncio.Lock used correctly (was threading.Lock in v4, which blocked
    the event loop inside async workers).
"""

import asyncio
import time

from bot.config          import DOMAIN_WORKERS
from bot.logger          import log
from bot.scanner.sources import ALL_SOURCES


async def scan_single_domain(domain: str) -> set:
    """
    Query all sources concurrently for one domain.
    Returns merged set of unique subdomain strings.
    """
    log.info(f"[Engine] START {domain}")
    t0           = time.time()
    tasks        = [fn(domain) for fn, _ in ALL_SOURCES.values()]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    merged: set = set()
    for name, result in zip(ALL_SOURCES.keys(), results_list):
        if isinstance(result, Exception):
            log.error(f"[Engine] {domain}/{name} raised: {result}")
        elif isinstance(result, set):
            merged.update(result)

    elapsed = round(time.time() - t0, 1)
    log.info(f"[Engine] DONE {domain} → {len(merged)} subs in {elapsed}s")
    return merged


async def scan_domains_parallel(
    domains: list,
    cancel_event: asyncio.Event,
    progress_cb=None,
    already_done: set | None = None,
) -> dict:
    """
    Scan a list of domains with up to DOMAIN_WORKERS running at once.

    Args:
        domains       : list of domain strings to scan
        cancel_event  : set this to abort mid-scan
        progress_cb   : async callable(done, total, domain, sub_count)
        already_done  : set of domains to skip (resume support)

    Returns:
        dict mapping domain → set[str] of subdomains
    """
    sem        = asyncio.Semaphore(DOMAIN_WORKERS)
    results: dict = {}
    done_count = 0
    total      = len(domains)
    # FIX: asyncio.Lock (not threading.Lock) — safe inside async workers
    lock       = asyncio.Lock()

    async def worker(domain: str):
        nonlocal done_count

        if cancel_event.is_set():
            return
        if already_done and domain in already_done:
            log.debug(f"[Engine] Skip {domain} (already done)")
            return

        async with sem:
            subs = await scan_single_domain(domain)

        # FIX: Only counter + dict update inside lock.
        # Sending Telegram files is NOT done here anymore — that was the
        # root cause of FloodWait on large batches (domain_done_cb was
        # called while holding the lock, serialising all sends).
        async with lock:
            done_count += 1
            results[domain] = subs
            if progress_cb:
                await progress_cb(done_count, total, domain, len(subs))

    await asyncio.gather(*[worker(d) for d in domains])
    return results
