"""
bot/notifications.py — Fire-and-forget Telegram channel notifications.

notify_new_user()      — sent when a brand-new user starts the bot
log_scan_to_channel()  — silently posts scan results to the admin log channel
"""

import io
import asyncio
from datetime import datetime

from telegram.constants import ParseMode

from bot.config  import LOG_CHANNEL_ID
from bot.database import db
from bot.logger  import log
from bot.scanner.output import build_final_content


async def notify_new_user(bot, user) -> None:
    """Send new-user notification to LOG_CHANNEL_ID (best-effort)."""
    if not LOG_CHANNEL_ID:
        return
    try:
        username = f"@{user.username}" if user.username else "No username"
        name     = (
            f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
        )
        await bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            parse_mode=ParseMode.HTML,
            text=(
                f"👤 <b>New User Joined!</b>\n\n"
                f"🆔 ID   : <code>{user.id}</code>\n"
                f"📛 Name : {name}\n"
                f"🔗 User : {username}\n"
                f"📅 Time : <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n"
                f"👥 Total Users: <b>{db.total_count()}</b>"
            ),
        )
        log.info(f"[Notify] New-user log sent for {user.id}")
    except Exception as exc:
        log.error(f"[Notify] new_user failed: {exc}")


async def log_scan_to_channel(
    bot,
    user_id: int,
    domains: list,
    all_subs: set,
    elapsed: float,
    filename: str,
) -> None:
    """
    Silently post scan result file to the admin log channel.
    disable_notification=True — no ping/sound for channel members.
    """
    if not LOG_CHANNEL_ID:
        return
    try:
        u = db.get(user_id)
        if not u:
            return

        uname   = f"@{u.get('username')}" if u.get("username") else "No username"
        name    = (
            f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or "Unknown"
        )
        caption = (
            f"📊 <b>Scan Log</b>\n\n"
            f"👤 User   : {name}\n"
            f"🆔 ID     : <code>{user_id}</code>\n"
            f"🔗 Handle : {uname}\n"
            f"📅 Time   : <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n"
            f"🎯 Domains    : {len(domains)}\n"
            f"📊 Subdomains : {len(all_subs)}\n"
            f"⏱ Duration   : <code>{elapsed}s</code>\n"
            f"📄 Targets    : {', '.join(domains[:5])}{'…' if len(domains) > 5 else ''}"
        )

        content = build_final_content(domains, all_subs, elapsed, filename)
        buf     = io.BytesIO(content.encode("utf-8"))
        buf.name = filename

        await bot.send_document(
            chat_id=LOG_CHANNEL_ID,
            document=buf,
            filename=filename,
            caption=caption,
            parse_mode=ParseMode.HTML,
            disable_notification=True,
        )
        log.info(f"[Notify] Scan log sent silently for user {user_id}")
    except Exception as exc:
        log.error(f"[Notify] log_scan_to_channel failed: {exc}")
