"""
bot/helpers.py — Pure utility functions (no I/O, no Telegram).
"""

import re
import hashlib


def is_admin(user_id: int) -> bool:
    from bot.config import ADMIN_IDS
    return user_id in ADMIN_IDS


def clean_domain(raw: str) -> str:
    """Strip protocol and path, lowercase."""
    return re.sub(r"^https?://", "", raw.strip()).rstrip("/").split("/")[0].lower()


def clean_subdomain(sub: str, domain: str) -> str | None:
    """
    Normalise a raw subdomain string.
    Returns cleaned subdomain string if valid, else None.
    """
    sub = sub.strip().lower()
    sub = re.sub(r"^\*\.", "", sub)           # remove wildcard prefix
    sub = re.sub(r"^https?://", "", sub)      # remove protocol
    sub = sub.split("/")[0].strip().rstrip(".")
    if domain in sub and re.match(r'^[a-z0-9._-]+$', sub):
        return sub
    return None


def is_valid_domain(raw: str) -> str | None:
    """Returns cleaned domain if valid, else None."""
    d   = clean_domain(raw)
    pat = r'^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    return d if re.match(pat, d) else None


def progress_bar(done: int, total: int, width: int = 20) -> str:
    pct  = done / total if total else 0
    fill = int(pct * width)
    bar  = "█" * fill + "░" * (width - fill)
    return f"[{bar}] {done}/{total} ({int(pct * 100)}%)"


def scan_id_for(chat_id: int, filename: str) -> str:
    return hashlib.md5(f"{chat_id}:{filename}".encode()).hexdigest()[:10]


def deduplicate_domains(raw_list: list[str]) -> tuple[list[str], int]:
    """
    Remove case-insensitive duplicates while preserving order.
    Returns (deduped_list, dup_count).
    """
    seen: set[str] = set()
    result: list[str] = []
    for d in raw_list:
        dl = d.lower()
        if dl not in seen:
            seen.add(dl)
            result.append(dl)
    return result, len(raw_list) - len(result)
