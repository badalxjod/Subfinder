"""
bot/handlers/common.py — Shared handler utilities.
"""

from telegram.constants import ParseMode
from bot.config   import DEVELOPER_USERNAME
from bot.database import db
from bot.helpers  import is_admin


async def ban_check(update) -> bool:
    """
    Returns True (and sends a notice) if the user is banned.
    Admins are never blocked.
    """
    user_id = update.effective_user.id
    if is_admin(user_id):
        return False
    if db.is_banned(user_id):
        try:
            await update.effective_message.reply_text(
                "🚫 <b>You have been banned from using this bot.</b>\n"
                f"Contact <a href='https://t.me/{DEVELOPER_USERNAME}'>Developer</a> "
                f"to appeal.",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        return True
    return False
