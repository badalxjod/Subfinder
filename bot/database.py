"""
bot/database.py — JSON-backed user database with thread-safe read/write.
Uses threading.Lock for the sync file I/O (NOT inside async handlers directly).
"""

import json
import threading
from datetime import datetime
from pathlib import Path

from bot.logger import log


class UserDB:
    """Persistent JSON user store with ban/unban and scan tracking."""

    def __init__(self, path: Path):
        self.path   = path
        self._lock  = threading.Lock()
        self._data  = self._load()

    # ── Private ────────────────────────────────────────────────

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log.error(f"[UserDB] Load failed: {e}")
        return {"users": {}}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"[UserDB] Save failed: {e}")

    # ── Public API ─────────────────────────────────────────────

    def register(self, user) -> bool:
        """Upsert Telegram user. Returns True if this is a brand-new user."""
        uid = str(user.id)
        with self._lock:
            is_new = uid not in self._data["users"]
            if is_new:
                self._data["users"][uid] = {
                    "user_id":    user.id,
                    "username":   user.username   or "",
                    "first_name": user.first_name or "",
                    "last_name":  user.last_name  or "",
                    "join_date":  datetime.now().isoformat(),
                    "last_seen":  datetime.now().isoformat(),
                    "is_banned":  False,
                    "total_scans": 0,
                }
            else:
                row = self._data["users"][uid]
                row["last_seen"]  = datetime.now().isoformat()
                row["username"]   = user.username   or row.get("username",   "")
                row["first_name"] = user.first_name or row.get("first_name", "")
                row["last_name"]  = user.last_name  or row.get("last_name",  "")
            self._save()
        return is_new

    def get(self, user_id: int) -> dict | None:
        return self._data["users"].get(str(user_id))

    def is_banned(self, user_id: int) -> bool:
        u = self.get(user_id)
        return u.get("is_banned", False) if u else False

    def ban(self, user_id: int) -> bool:
        uid = str(user_id)
        with self._lock:
            if uid not in self._data["users"]:
                return False
            self._data["users"][uid]["is_banned"] = True
            self._save()
        return True

    def unban(self, user_id: int) -> bool:
        uid = str(user_id)
        with self._lock:
            if uid not in self._data["users"]:
                return False
            self._data["users"][uid]["is_banned"] = False
            self._save()
        return True

    def increment_scans(self, user_id: int):
        uid = str(user_id)
        with self._lock:
            if uid in self._data["users"]:
                self._data["users"][uid]["total_scans"] = (
                    self._data["users"][uid].get("total_scans", 0) + 1
                )
                self._save()

    def all_users(self) -> list:
        return list(self._data["users"].values())

    def total_count(self) -> int:
        return len(self._data["users"])

    def banned_count(self) -> int:
        return sum(1 for u in self._data["users"].values() if u.get("is_banned"))


# ── Singleton ──────────────────────────────────────────────────
from bot.config import USERS_FILE
db = UserDB(USERS_FILE)
