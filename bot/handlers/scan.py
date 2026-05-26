"""
bot/handlers/scan.py — Scan-related command and message handlers.
"""

import os
import io
import asyncio
import time

from telegram.constants import ParseMode, ChatAction
from telegram.ext       import ConversationHandler

from bot.config  import (
    CHOOSING_MODE, WAITING_DOMAIN, WAITING_FILE,
    ACTIVE_SCANS, LAST_FINAL_FILES,
    DOMAIN_WORKERS, CHUNK_SIZE,
)
from bot.state     import get_scan_lock
from bot.database  import db
from bot.helpers   import is_valid_domain, progress_bar, scan_id_for, deduplicate_domains
from bot.retry     import send_with_retry
from bot.resume    import load_resume, latest_resume_file
from bot.keyboards import kb_back
from bot.logger    import log
from bot.handlers.common import ban_check
from bot.scanner.engine  import scan_single_domain
from bot.scanner.output  import build_single_content
from bot.scanner.background import run_file_scan_background
from bot.scanner.sources import ALL_SOURCES
from bot.notifications   import log_scan_to_channel


# ── /cancel ──────────────────────────────────────────────────────
async def cmd_cancel(update, ctx):
    chat_id = update.effective_chat.id
    async with get_scan_lock():
        info = ACTIVE_SCANS.get(chat_id)
    if not info:
        await update.message.reply_text(
            "❌ No active scan to cancel.", parse_mode=ParseMode.HTML
        )
        return
    info["cancel"].set()
    log.info(f"[Cancel] chat={chat_id} scan_id={info.get('scan_id')}")
    await update.message.reply_text(
        "⛔ <b>Cancelling scan…</b>\n\nProgress saved — use /resume to continue.",
        parse_mode=ParseMode.HTML,
    )


# ── /resume ───────────────────────────────────────────────────────
async def cmd_resume(update, ctx):
    if await ban_check(update):
        return
    chat_id = update.effective_chat.id
    latest  = latest_resume_file()
    if not latest:
        await update.message.reply_text(
            "❌ No saved scan found.", parse_mode=ParseMode.HTML
        )
        return
    state = load_resume(latest.stem)
    if not state:
        await update.message.reply_text(
            "❌ Could not load resume state.", parse_mode=ParseMode.HTML
        )
        return

    domains    = state["domains"]
    basename   = state["basename"]
    scan_id    = state["scan_id"]
    next_chunk = state.get("next_chunk", 0)
    done_count = len(state.get("results", {}))

    log.info(f"[Resume] chat={chat_id} scan_id={scan_id} chunk={next_chunk}")
    status_msg = await update.message.reply_text(
        f"🔄 <b>Resuming scan…</b>\n\n"
        f"📄 File   : <code>{basename}.txt</code>\n"
        f"🎯 Total  : <b>{len(domains)}</b> domains | ✅ Done: <b>{done_count}</b>\n"
        f"📦 From chunk <b>{next_chunk + 1}</b> | ⚡ {DOMAIN_WORKERS} parallel",
        parse_mode=ParseMode.HTML,
    )
    asyncio.create_task(
        run_file_scan_background(
            ctx.bot, chat_id, status_msg.message_id,
            domains, basename, scan_id, resume_state=state,
        )
    )


# ── /status ───────────────────────────────────────────────────────
async def cmd_status(update, ctx):
    chat_id = update.effective_chat.id
    async with get_scan_lock():
        info = ACTIVE_SCANS.get(chat_id)
    if not info:
        await update.message.reply_text(
            "💤 No active scan.\nUse /scan to start.", parse_mode=ParseMode.HTML
        )
        return
    done  = info.get("done",  0)
    total = info.get("total", 1)
    await update.message.reply_text(
        f"📊 <b>Scan Status</b>\n\n"
        f"<code>{progress_bar(done, total)}</code>\n\n"
        f"🎯 <code>{done}/{total}</code> domains done\n"
        f"❌ /cancel to stop",
        parse_mode=ParseMode.HTML,
    )


# ── /getfinal ─────────────────────────────────────────────────────
async def cmd_getfinal(update, ctx):
    if await ban_check(update):
        return
    chat_id = update.effective_chat.id
    info    = LAST_FINAL_FILES.get(chat_id)
    if not info:
        await update.message.reply_text(
            "❌ <b>No final file stored.</b>\n\n"
            "Run a scan first.\n"
            "Note: file is kept until the next bot restart.",
            parse_mode=ParseMode.HTML,
        )
        return

    notice = await update.message.reply_text(
        "🔄 <b>Sending final file…</b>", parse_mode=ParseMode.HTML
    )

    from bot.handlers.start import _resend_final
    await _resend_final(ctx.bot, chat_id, info)

    try:
        await notice.delete()
    except Exception:
        pass


# ── Single domain text message ────────────────────────────────────
async def handle_domain_input(update, ctx):
    if await ban_check(update):
        return CHOOSING_MODE

    raw    = update.message.text.strip()
    domain = is_valid_domain(raw)
    if not domain:
        await update.message.reply_text(
            f"❌ Invalid domain: <code>{raw[:60]}</code>\n\n"
            f"Example: <code>example.com</code>",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_DOMAIN

    chat_id = update.effective_chat.id
    async with get_scan_lock():
        already_active = chat_id in ACTIVE_SCANS
    if already_active:
        await update.message.reply_text(
            "⚠️ Active scan running! Use /status or /cancel first.",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_DOMAIN

    log.info(f"[SingleScan] START {domain} chat={chat_id}")
    status_msg = await update.message.reply_text(
        f"🔍 <b>Scanning:</b> <code>{domain}</code>\n\n"
        f"⏳ Querying <b>{len(ALL_SOURCES)} sources</b> in parallel…\n"
        f"Typically 20–60 seconds.",
        parse_mode=ParseMode.HTML,
    )
    await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)

    t0 = time.time()
    try:
        subs = await scan_single_domain(domain)
    except Exception as exc:
        log.error(f"[SingleScan] FAILED {domain}: {exc}")
        await status_msg.edit_text(f"❌ Scan failed: {exc}")
        return CHOOSING_MODE

    elapsed = round(time.time() - t0, 1)
    count   = len(subs)
    log.info(f"[SingleScan] DONE {domain} → {count} subs in {elapsed}s")

    await status_msg.edit_text(
        f"✅ <b>Scan Complete!</b>\n\n"
        f"🎯 Domain  : <code>{domain}</code>\n"
        f"📊 Found   : <b>{count} subdomains</b>\n"
        f"⏱ Time    : <code>{elapsed}s</code>\n"
        f"🔥 Sources : <code>{len(ALL_SOURCES)} APIs</code>\n\n"
        f"{'📭 No subdomains found.' if count == 0 else '📁 Sending file…'}",
        parse_mode=ParseMode.HTML,
    )

    if count > 0:
        fname   = f"subdomain_{domain.replace('.', '_')}.txt"
        content = build_single_content(domain, subs, elapsed)

        LAST_FINAL_FILES[chat_id] = {
            "content": content,
            "fname":   fname,
            "domains": 1,
            "subs":    count,
            "elapsed": elapsed,
            "nosub":   0,
        }

        async def _send_single():
            buf = io.BytesIO(content.encode("utf-8"))
            buf.name = fname
            return await ctx.bot.send_document(
                chat_id=chat_id,
                document=buf,
                filename=fname,
                caption=(
                    f"🕵️ <b>SubHunter</b> — <code>{domain}</code>\n"
                    f"📊 <b>{count}</b> subdomains\n"
                    f"💡 Use /getfinal to resend anytime"
                ),
                parse_mode=ParseMode.HTML,
            )

        try:
            await send_with_retry(_send_single)
        except Exception as exc:
            log.error(f"[SingleScan] File send failed {domain}: {exc}")
            await ctx.bot.send_message(
                chat_id=chat_id,
                text="⚠️ File could not be sent. Use /getfinal to retry.",
                parse_mode=ParseMode.HTML,
            )

        db.increment_scans(chat_id)
        asyncio.create_task(
            log_scan_to_channel(ctx.bot, chat_id, [domain], subs, elapsed, fname)
        )

    await update.message.reply_text("🔄 What next?", reply_markup=kb_back())
    return CHOOSING_MODE


# ── Uploaded .txt file ────────────────────────────────────────────
async def handle_file_input(update, ctx):
    if await ban_check(update):
        return CHOOSING_MODE

    doc = update.message.document
    if not doc:
        await update.message.reply_text(
            "❌ Please upload a .txt file.", parse_mode=ParseMode.HTML
        )
        return WAITING_FILE
    if not doc.file_name.lower().endswith(".txt"):
        await update.message.reply_text(
            "❌ Only .txt files are supported.", parse_mode=ParseMode.HTML
        )
        return WAITING_FILE

    chat_id = update.effective_chat.id
    async with get_scan_lock():
        already_active = chat_id in ACTIVE_SCANS
    if already_active:
        await update.message.reply_text(
            "⚠️ Active scan running! Use /status or /cancel first.",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_FILE

    status_msg = await update.message.reply_text("📥 Downloading file…")
    tg_file    = await ctx.bot.get_file(doc.file_id)
    raw_bytes  = await tg_file.download_as_bytearray()
    content    = raw_bytes.decode("utf-8", errors="ignore")

    raw_domains: list = []
    skipped:     list = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        d = is_valid_domain(line)
        if d:
            raw_domains.append(d)
        else:
            skipped.append(line)

    domains, dup_count = deduplicate_domains(raw_domains)

    if not domains:
        await status_msg.edit_text(
            "❌ <b>No valid domains found in the file.</b>",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_FILE

    log.info(
        f"[FileInput] {doc.file_name}: {len(domains)} domains "
        f"({dup_count} dups removed, {len(skipped)} invalid) "
        f"chat={chat_id}"
    )

    basename     = os.path.splitext(doc.file_name)[0]
    scan_id      = scan_id_for(chat_id, doc.file_name)
    total_chunks = (len(domains) + CHUNK_SIZE - 1) // CHUNK_SIZE

    notes: list = []
    if skipped:
        notes.append(f"⚠️ Skipped <b>{len(skipped)}</b> invalid lines")
    if dup_count:
        notes.append(f"🔄 Removed <b>{dup_count}</b> duplicate domains")
    note_str = ("\n" + "\n".join(notes)) if notes else ""

    resume_state = load_resume(scan_id)
    resume_note  = ""
    if resume_state:
        prev_done   = len(resume_state.get("results", {}))
        resume_note = (
            f"\n\n💾 <b>Resume found!</b> Done: <b>{prev_done}</b> domains\n"
            f"Continuing from chunk <b>{resume_state.get('next_chunk', 0) + 1}</b>"
        )

    await status_msg.edit_text(
        f"✅ <b>File loaded!</b>\n\n"
        f"📄 <code>{doc.file_name}</code>\n"
        f"🎯 Domains : <b>{len(domains)}</b>{note_str}\n"
        f"📦 Chunks  : <b>{total_chunks}</b> (×{CHUNK_SIZE} domains each)\n"
        f"⚡ {DOMAIN_WORKERS} async parallel"
        f"{resume_note}\n\n"
        f"🚀 <b>Starting…</b> /status   /cancel",
        parse_mode=ParseMode.HTML,
    )

    asyncio.create_task(
        run_file_scan_background(
            ctx.bot, chat_id, status_msg.message_id,
            domains, basename, scan_id, resume_state=resume_state,
        )
    )
    return CHOOSING_MODE
