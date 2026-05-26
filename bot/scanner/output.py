"""
bot/scanner/output.py — Build the text content for every output file type.

All functions are pure (no I/O) and return a plain str ready to be
encoded as UTF-8 and wrapped in io.BytesIO before sending.
"""

from datetime import datetime
from bot.scanner.sources import ALL_SOURCES


def _header_line(key: str, value: str) -> str:
    return f"# {key:<10}: {value}"


def _divider() -> str:
    return f"# {'─' * 42}"


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Final / merged file ─────────────────────────────────────────
def build_final_content(
    domains: list,
    all_subs: set,
    elapsed: float,
    basename: str,
) -> str:
    lines = [
        "# SubHunter Bot v5.0 — FINAL MERGED OUTPUT",
        _header_line("Domains",   str(len(domains))),
        _header_line("Targets",   ", ".join(domains[:10]) + ("..." if len(domains) > 10 else "")),
        _header_line("Found",     f"{len(all_subs)} unique subdomains"),
        _header_line("Date",      _timestamp()),
        _header_line("Time",      f"{elapsed}s"),
        _header_line("Sources",   f"{len(ALL_SOURCES)} APIs per domain"),
        _header_line("Engine",    "asyncio + semaphore (no deadlock)"),
        _divider(), "",
    ]
    lines += sorted(all_subs)
    return "\n".join(lines)


# ── Single-domain file ──────────────────────────────────────────
def build_single_content(domain: str, subs: set, elapsed: float) -> str:
    lines = [
        "# SubHunter Bot v5.0 — Single Domain Scan",
        _header_line("Domain",  domain),
        _header_line("Found",   f"{len(subs)} unique subdomains"),
        _header_line("Date",    _timestamp()),
        _header_line("Time",    f"{elapsed}s"),
        _header_line("Sources", f"{len(ALL_SOURCES)} APIs"),
        _divider(), "",
    ]
    lines += sorted(subs)
    return "\n".join(lines)


# ── Per-chunk file ──────────────────────────────────────────────
def build_chunk_content(
    chunk_number: int,
    total_chunks: int,
    domains_in_chunk: list,
    chunk_subs: set,
    elapsed: float,
) -> str:
    lines = [
        f"# SubHunter Bot v5.0 — CHUNK {chunk_number}/{total_chunks}",
        _header_line("Chunk",   f"{chunk_number} of {total_chunks}"),
        _header_line("Domains", str(len(domains_in_chunk))),
        _header_line("Targets", ", ".join(domains_in_chunk[:10]) + ("..." if len(domains_in_chunk) > 10 else "")),
        _header_line("Found",   f"{len(chunk_subs)} unique subdomains"),
        _header_line("Date",    _timestamp()),
        _header_line("Elapsed", f"{elapsed}s"),
        _divider(), "",
    ]
    lines += sorted(chunk_subs)
    return "\n".join(lines)


# ── No-subdomain report file ────────────────────────────────────
def build_nosub_content(no_sub_domains: list, basename: str) -> str:
    lines = [
        "# SubHunter Bot v5.0 — Domains With NO Subdomains Found",
        _header_line("Total",   f"{len(no_sub_domains)} domains"),
        _header_line("Scan",    basename),
        _header_line("Date",    _timestamp()),
        _header_line("Info",    f"0 results from all {len(ALL_SOURCES)} sources"),
        _divider(), "",
    ]
    lines += sorted(no_sub_domains)
    return "\n".join(lines)
