"""
bot/config.py — All configuration, constants, and global shared state.

Set the variables below via environment variables or a .env file.
Never hardcode credentials here.
"""

import os
from pathlib import Path

# ════════════════════════════════════════════════════════
#  REQUIRED — set as environment variables
# ════════════════════════════════════════════════════════
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")              # Required
ADMIN_IDS: list = [
    int(x) for x in os.environ.get("ADMIN_IDS", "8410766211").split(",") if x.strip()
]
LOG_CHANNEL_ID      = int(os.environ.get("LOG_CHANNEL_ID", "-1003508685581"))
UPDATES_CHANNEL_URL = os.environ.get("UPDATES_CHANNEL_URL", "https://t.me/BadalPvt")
DEVELOPER_USERNAME  = os.environ.get("DEVELOPER_USERNAME", "BADALxJOD")

# ════════════════════════════════════════════════════════
#  SCAN SETTINGS
# ════════════════════════════════════════════════════════
DOMAIN_WORKERS = int(os.environ.get("DOMAIN_WORKERS", "15"))
CHUNK_SIZE     = int(os.environ.get("CHUNK_SIZE", "50"))
SOURCE_TIMEOUT = int(os.environ.get("SOURCE_TIMEOUT", "20"))

# ════════════════════════════════════════════════════════
#  PATHS
# ════════════════════════════════════════════════════════
RESUME_DIR = Path(os.environ.get("RESUME_DIR", "/tmp/resume_data"))
USERS_FILE = Path(os.environ.get("USERS_FILE", "/tmp/users.json"))
LOG_FILE   = Path(os.environ.get("LOG_FILE",   "/tmp/subhunter.log"))

RESUME_DIR.mkdir(parents=True, exist_ok=True)

# ════════════════════════════════════════════════════════
#  CONVERSATION STATES
# ════════════════════════════════════════════════════════
CHOOSING_MODE     = 0
WAITING_DOMAIN    = 1
WAITING_FILE      = 2
ADMIN_BROADCAST   = 3
ADMIN_BAN_INPUT   = 4
ADMIN_UNBAN_INPUT = 5

# ════════════════════════════════════════════════════════
#  GLOBAL SHARED STATE
#  NOTE: SCAN_LOCK is intentionally NOT created here.
#  It is created lazily inside handlers after the event
#  loop is running, avoiding "no current event loop" on
#  Python < 3.10.  Import it from bot.state instead.
# ════════════════════════════════════════════════════════
ACTIVE_SCANS: dict     = {}   # chat_id → {cancel, scan_id, total, done, …}
LAST_FINAL_FILES: dict = {}   # chat_id → {content, fname, domains, subs, elapsed, nosub}
