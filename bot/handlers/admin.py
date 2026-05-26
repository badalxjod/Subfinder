"""
bot/handlers/admin.py — Admin panel: commands + callback handlers.
"""

import asyncio
import io

from telegram.constants import ParseMode
from telegram.ext       import ConversationHandler

from bot.config    import (
    CHOOSING_MODE, ADMIN_BROADCAST, ADMIN_BAN_INPUT, ADMIN_UNBAN_INPUT,
    ACTIVE_SCANS,
)
from bot.state     import get_scan_lock
from bot.database  import db
from bot.helpers   import is_admin, progress_bar
from bot.keyboards import kb_admin_menu, kb_admin_back, kb_admin_cancel
from bot.logger    import log


# ── /admin ───────────────────────────────────────────────────────
async def cmd_admin(update, ctx):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "❌ <b>Access Denied.</b>", parse_mode=ParseMode.HTML
        )
        return
    await update.message.reply_text(
        _admin_panel_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=kb_admin_menu(),
    )


def _admin_panel_text() -> str:
    total  = db.total_count()
    banned = db.banned_count()
    active = len(ACTIVE_SCANS)
    return (
        f"🛡️ <b>Admin Panel</b>\n\n"
        f"👥 Total Users  : <b>{total}</b>\n"
        f"🚫 Banned       : <b>{banned}</b>\n"
        f"⚡ Active Scans : <b>{active}</b>\n\n"
        f"Choose an action below:"
    )


# ── /ban  /unban ─────────────────────────────────────────────────
async def cmd_ban(update, ctx):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Not authorized.")
        return
    if not ctx.args:
        await update.message.reply_text(
            "Usage: <code>/ban &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML
        )
        return
    try:
        uid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Must be a number.")
        return
    if db.ban(uid):
        await update.message.reply_text(
            f"🚫 User <code>{uid}</code> has been <b>banned</b>.",
            parse_mode=ParseMode.HTML,
        )
        log.info(f"[Admin] /ban {uid} by {update.effective_user.id}")
    else:
        await update.message.reply_text(
            f"❌ User <code>{uid}</code> not found in DB.",
            parse_mode=ParseMode.HTML,
        )


async def cmd_unban(update, ctx):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Not authorized.")
        return
    if not ctx.args:
        await update.message.reply_text(
            "Usage: <code>/unban &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML
        )
        return
    try:
        uid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    if db.unban(uid):
        await update.message.reply_text(
            f"✅ User <code>{uid}</code> has been <b>unbanned</b>.",
            parse_mode=ParseMode.HTML,
        )
        log.info(f"[Admin] /unban {uid} by {update.effective_user.id}")
    else:
        await update.message.reply_text(
            f"❌ User <code>{uid}</code> not found in DB.",
            parse_mode=ParseMode.HTML,
        )


# ── /broadcast ───────────────────────────────────────────────────
async def cmd_broadcast(update, ctx):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Not authorized.")
        return
    if not ctx.args:
        await update.message.reply_text(
            "Usage: <code>/broadcast &lt;message&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    text = " ".join(ctx.args)
    await _do_broadcast(update.message, ctx.bot, text)


async def _do_broadcast(reply_obj, bot, text: str):
    users    = db.all_users()
    active   = [u for u in users if not u.get("is_banned")]
    progress = await reply_obj.reply_text(
        f"📢 Broadcasting to <b>{len(active)}</b> users…",
        parse_mode=ParseMode.HTML,
    )
    success = fail = 0
    for u in active:
        try:
            await bot.send_message(
                chat_id=u["user_id"],
                text=f"📢 <b>Announcement from SubHunter Bot</b>\n\n{text}",
                parse_mode=ParseMode.HTML,
            )
            success += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)   # ~20 msg/s — within Telegram limits
    try:
        await progress.edit_text(
            f"✅ <b>Broadcast Complete!</b>\n\n"
            f"📤 Sent   : <b>{success}</b>\n"
            f"❌ Failed : <b>{fail}</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


# ── Admin callback handler ────────────────────────────────────────
async def admin_callback_handler(update, ctx):
    query   = update.callback_query
    data    = query.data
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await query.answer("❌ Not authorized.", show_alert=True)
        return CHOOSING_MODE

    await query.answer()

    if data == "admin_stats":
        total  = db.total_count()
        banned = db.banned_count()
        active = len(ACTIVE_SCANS)
        await query.edit_message_text(
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 Total Users   : <b>{total}</b>\n"
            f"✅ Active Users  : <b>{total - banned}</b>\n"
            f"🚫 Banned Users  : <b>{banned}</b>\n"
            f"⚡ Active Scans  : <b>{active}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin_back(),
        )

    elif data == "admin_users":
        users = db.all_users()
        if not users:
            await query.edit_message_text(
                "👥 No users registered yet.",
                reply_markup=kb_admin_back(),
            )
            return CHOOSING_MODE

        lines = []
        for i, u in enumerate(users[:30], 1):
            status = "🚫" if u.get("is_banned") else "✅"
            uname  = f"@{u['username']}" if u.get("username") else "—"
            lines.append(
                f"{i}. {status} <code>{u['user_id']}</code> | "
                f"{u.get('first_name', '')[:12]} | {uname} | "
                f"Scans:{u.get('total_scans', 0)}"
            )

        text = f"👥 <b>Users ({len(users)} total)</b>\n\n" + "\n".join(lines)
        if len(users) > 30:
            text += f"\n\n<i>…{len(users) - 30} more. Export for full list.</i>"
        if len(text) > 4000:
            text = text[:3900] + "\n<i>…truncated</i>"

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        kb_rows = []
        if len(users) > 30:
            kb_rows.append([
                InlineKeyboardButton("📄 Export Full List", callback_data="admin_users_export")
            ])
        kb_rows.append([InlineKeyboardButton("◀️ Back", callback_data="admin_back")])
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb_rows),
        )

    elif data == "admin_users_export":
        users = db.all_users()
        rows  = ["SubHunter Bot — Full Users Export", "=" * 60, ""]
        for i, u in enumerate(users, 1):
            status = "BANNED" if u.get("is_banned") else "ACTIVE"
            uname  = f"@{u['username']}" if u.get("username") else "—"
            rows.append(
                f"{i}. [{status}] "
                f"ID:{u['user_id']} | "
                f"{u.get('first_name', '')} {u.get('last_name', '')} | "
                f"{uname} | "
                f"Scans:{u.get('total_scans', 0)} | "
                f"Joined:{u.get('join_date', '')[:10]}"
            )
        buf      = io.BytesIO("\n".join(rows).encode())
        buf.name = "users_export.txt"
        await ctx.bot.send_document(
            chat_id=query.message.chat_id,
            document=buf,
            filename="users_export.txt",
            caption=f"👥 <b>Full Export</b> — {len(users)} users",
            parse_mode=ParseMode.HTML,
        )

    elif data == "admin_scans":
        async with get_scan_lock():
            scans = dict(ACTIVE_SCANS)
        if not scans:
            text = "⚡ <b>Active Scans</b>\n\n💤 None running."
        else:
            lines = [
                f"• Chat <code>{cid}</code>\n"
                f"  {progress_bar(info.get('done', 0), info.get('total', 1))}"
                for cid, info in scans.items()
            ]
            text = f"⚡ <b>Active Scans ({len(scans)})</b>\n\n" + "\n".join(lines)
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb_admin_back()
        )

    elif data == "admin_broadcast":
        ctx.user_data["admin_action"] = "broadcast"
        await query.edit_message_text(
            "📢 <b>Broadcast Message</b>\n\nType message below:",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin_cancel(),
        )
        return ADMIN_BROADCAST

    elif data == "admin_ban":
        ctx.user_data["admin_action"] = "ban"
        await query.edit_message_text(
            "🚫 <b>Ban User</b>\n\nSend the <b>Telegram User ID</b>:",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin_cancel(),
        )
        return ADMIN_BAN_INPUT

    elif data == "admin_unban":
        ctx.user_data["admin_action"] = "unban"
        await query.edit_message_text(
            "✅ <b>Unban User</b>\n\nSend the <b>Telegram User ID</b>:",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin_cancel(),
        )
        return ADMIN_UNBAN_INPUT

    elif data == "admin_back":
        ctx.user_data.pop("admin_action", None)
        await query.edit_message_text(
            _admin_panel_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin_menu(),
        )

    return CHOOSING_MODE


# ── Conversation state handlers ───────────────────────────────────
async def handle_admin_broadcast(update, ctx):
    if not is_admin(update.effective_user.id):
        return CHOOSING_MODE
    if ctx.user_data.get("admin_action") != "broadcast":
        return CHOOSING_MODE
    text = update.message.text.strip()
    ctx.user_data.pop("admin_action", None)
    await _do_broadcast(update.message, ctx.bot, text)
    return CHOOSING_MODE


async def handle_admin_ban_input(update, ctx):
    if not is_admin(update.effective_user.id):
        return CHOOSING_MODE
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Send a number.")
        return ADMIN_BAN_INPUT
    ctx.user_data.pop("admin_action", None)
    if db.ban(uid):
        await update.message.reply_text(
            f"🚫 User <code>{uid}</code> banned.", parse_mode=ParseMode.HTML
        )
        log.info(f"[Admin] Panel-ban {uid}")
    else:
        await update.message.reply_text(
            f"❌ User <code>{uid}</code> not in DB.", parse_mode=ParseMode.HTML
        )
    return CHOOSING_MODE


async def handle_admin_unban_input(update, ctx):
    if not is_admin(update.effective_user.id):
        return CHOOSING_MODE
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Send a number.")
        return ADMIN_UNBAN_INPUT
    ctx.user_data.pop("admin_action", None)
    if db.unban(uid):
        await update.message.reply_text(
            f"✅ User <code>{uid}</code> unbanned.", parse_mode=ParseMode.HTML
        )
        log.info(f"[Admin] Panel-unban {uid}")
    else:
        await update.message.reply_text(
            f"❌ User <code>{uid}</code> not in DB.", parse_mode=ParseMode.HTML
        )
    return CHOOSING_MODE
