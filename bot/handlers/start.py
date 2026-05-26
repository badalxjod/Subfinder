"""
bot/handlers/start.py — /start, /scan, /help, /about, main button_handler.
"""

import asyncio

from telegram.constants import ParseMode
from telegram.ext       import ConversationHandler

from bot.config    import (
    CHOOSING_MODE, WAITING_DOMAIN, WAITING_FILE,
    UPDATES_CHANNEL_URL, DEVELOPER_USERNAME,
    LAST_FINAL_FILES,
)
from bot.database         import db
from bot.keyboards        import kb_main_menu, kb_back, kb_channel_dev
from bot.helpers          import is_admin
from bot.retry            import send_with_retry
from bot.scanner.sources  import ALL_SOURCES
from bot.notifications    import notify_new_user
from bot.handlers.common  import ban_check
from bot.logger           import log

import io
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


WELCOME_MSG = """
🕵️ <b>SubHunter Bot</b> v5.0 — Advanced Subdomain Finder

━━━━━━━━━━━━━━━━━━━━━━━━
🔥 <b>16 Sources</b> | Pure Async (aiohttp + asyncio)
⚡ <b>No Deadlock</b> — Semaphore-based concurrency
📦 <b>Per-chunk file</b> after every 50-domain chunk
🗂 <b>Complete merged file</b> at the end
📭 <b>No-subdomain report</b> file included
🔁 <b>/getfinal</b> — resend final file anytime
🔄 <b>Duplicate domains</b> auto-removed from input
💾 Resume support | 🛡 Rate-limit protected
━━━━━━━━━━━━━━━━━━━━━━━━

🚀 Choose a mode below to get started!
"""


async def cmd_start(update, ctx):
    user   = update.effective_user
    is_new = db.register(user)
    if await ban_check(update):
        return ConversationHandler.END

    ctx.user_data.clear()
    await update.message.reply_text(
        WELCOME_MSG,
        parse_mode=ParseMode.HTML,
        reply_markup=kb_main_menu(),
    )

    if is_new:
        asyncio.create_task(notify_new_user(ctx.bot, user))

    return CHOOSING_MODE


async def cmd_scan(update, ctx):
    if await ban_check(update):
        return ConversationHandler.END
    db.register(update.effective_user)
    ctx.user_data.clear()
    await update.message.reply_text(
        "🎛 <b>Choose scan mode:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_main_menu(),
    )
    return CHOOSING_MODE


async def cmd_help(update, ctx):
    await update.message.reply_text(
        "📖 <b>SubHunter Bot v5.0 — Help</b>\n\n"
        "<b>Commands:</b>\n"
        "/start    — Main menu\n"
        "/scan     — Choose scan mode\n"
        "/cancel   — Cancel active scan\n"
        "/resume   — Resume last scan\n"
        "/status   — View scan progress\n"
        "/getfinal — Resend last final file\n"
        "/admin    — Admin panel (admin only)\n\n"
        "<b>v5.0 Changes:</b>\n"
        "✅ No per-domain files (chunk + final only)\n"
        "✅ Duplicate domains auto-removed from input\n"
        "✅ No-subdomain report file at end\n"
        "✅ /getfinal — resend final file anytime\n"
        "✅ Retry + FloodWait protection on all sends\n"
        "✅ Async locks (no event-loop freezing)\n"
        "✅ Rate-limit safe between chunks\n\n"
        "<b>Log file:</b> <code>/tmp/subhunter.log</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_channel_dev(),
    )
    return ConversationHandler.END


async def cmd_about(update, ctx):
    await update.message.reply_text(
        f"🕵️ <b>SubHunter Bot v5.0</b>\n\n"
        f"<b>Engine  :</b> {len(ALL_SOURCES)} OSINT APIs via aiohttp\n"
        f"<b>Parallel:</b> asyncio.Semaphore — no deadlock\n"
        f"<b>Retry   :</b> FloodWait / NetworkError auto-handled\n"
        f"<b>Logging :</b> /tmp/subhunter.log\n\n"
        f"<b>Sources :</b>\n"
        f"DEVxDARK · crt.sh · HackerTarget · AlienVault OTX\n"
        f"RapidDNS · Anubis-DB · URLScan.io · VirusTotal\n"
        f"Wayback · CertSpotter · MerkleMap · Columbus\n"
        f"JLDC · LeakIX · ThreatMiner · SubdomainCenter 🔥",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_channel_dev(),
    )
    return ConversationHandler.END


async def cmd_fallback(update, ctx):
    await update.message.reply_text(
        "🤔 Use /start to begin.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_main_menu(),
    )
    return CHOOSING_MODE


# ── Main button router ──────────────────────────────────────────
async def button_handler(update, ctx):
    from bot.handlers.admin import admin_callback_handler

    query = update.callback_query
    await query.answer()
    data    = query.data
    chat_id = update.effective_chat.id

    # Route admin_ callbacks
    if data.startswith("admin_"):
        return await admin_callback_handler(update, ctx)

    if data == "mode_single":
        await query.edit_message_text(
            "🎯 <b>Single Domain Mode</b>\n\n"
            "Send me the domain:\n<code>example.com</code>",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_DOMAIN

    elif data == "mode_file":
        from bot.config import DOMAIN_WORKERS, CHUNK_SIZE
        await query.edit_message_text(
            f"📄 <b>TXT File Mode</b>\n\n"
            f"Upload a .txt with one domain per line.\n\n"
            f"⚡ {DOMAIN_WORKERS} async parallel\n"
            f"🔄 Duplicates auto-removed\n"
            f"📦 Per-chunk files (every {CHUNK_SIZE} domains)\n"
            f"🗂 Final merged file\n"
            f"📭 No-subdomain report file\n"
            f"🔁 /getfinal to resend anytime\n"
            f"💾 Auto-resume on interruption",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_FILE

    elif data == "getfinal":
        info = LAST_FINAL_FILES.get(chat_id)
        if not info:
            await query.answer(
                "❌ No final file stored. Run a scan first.",
                show_alert=True,
            )
            return CHOOSING_MODE
        await query.answer("📤 Sending final file…")
        await _resend_final(ctx.bot, chat_id, info)
        return CHOOSING_MODE

    elif data == "help":
        await query.edit_message_text(
            "📖 Use /help for full help.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Back", callback_data="back_menu")]
            ]),
        )
        return ConversationHandler.END

    elif data == "about":
        await query.edit_message_text(
            f"🕵️ <b>SubHunter Bot v5.0</b>\n\n"
            f"{len(ALL_SOURCES)} OSINT sources | asyncio | Retry-safe.\n\n"
            f"Use /about for full info.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📢 Updates", url=UPDATES_CHANNEL_URL),
                    InlineKeyboardButton("👨‍💻 Dev",    url=f"https://t.me/{DEVELOPER_USERNAME}"),
                ],
                [InlineKeyboardButton("◀️ Back", callback_data="back_menu")],
            ]),
        )
        return ConversationHandler.END

    elif data == "back_menu":
        await query.edit_message_text(
            WELCOME_MSG,
            parse_mode=ParseMode.HTML,
            reply_markup=kb_main_menu(),
        )
        return CHOOSING_MODE

    return CHOOSING_MODE


async def _resend_final(bot, chat_id: int, info: dict):
    """Helper shared by button_handler and cmd_getfinal."""
    async def _factory():
        buf = io.BytesIO(info["content"].encode("utf-8"))
        buf.name = info["fname"]
        return await bot.send_document(
            chat_id=chat_id,
            document=buf,
            filename=info["fname"],
            caption=(
                f"🔁 <b>Final File (Resent)</b>\n\n"
                f"🎯 Domains : <b>{info['domains']}</b>\n"
                f"📊 Total   : <b>{info['subs']} unique subdomains</b>\n"
                f"⏱ Time    : <code>{info['elapsed']}s</code>"
            ),
            parse_mode=ParseMode.HTML,
        )

    try:
        await send_with_retry(_factory, max_retries=5)
        log.info(f"[GetFinal] File resent to {chat_id}")
    except Exception as exc:
        log.error(f"[GetFinal] Resend failed: {exc}")
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Failed to send file. Try again in a moment.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
