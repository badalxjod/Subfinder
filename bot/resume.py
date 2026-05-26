"""
bot/resume.py — Save / load / delete scan resume state (JSON files on disk).
"""

import json
from pathlib import Path

from bot.config import RESUME_DIR
from bot.logger import log


def resume_path(scan_id: str) -> Path:
    return RESUME_DIR / f"{scan_id}.json"


def save_resume(scan_id: str, data: dict):
    try:
        with open(resume_path(scan_id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        log.debug(f"[Resume] Saved {scan_id}")
    except Exception as exc:
        log.error(f"[Resume] Save failed {scan_id}: {exc}")


def load_resume(scan_id: str) -> dict | None:
    p = resume_path(scan_id)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.error(f"[Resume] Load failed {scan_id}: {exc}")
        return None


def delete_resume(scan_id: str):
    try:
        resume_path(scan_id).unlink(missing_ok=True)
        log.debug(f"[Resume] Deleted {scan_id}")
    except Exception as exc:
        log.warning(f"[Resume] Delete failed {scan_id}: {exc}")


def latest_resume_file() -> Path | None:
    """Return the most recently modified resume JSON, or None."""
    files = list(RESUME_DIR.glob("*.json"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)
