"""
bot/scanner/background.py — Background file-scan coroutine.

run_file_scan_background() is launched with asyncio.create_task() from
the file handler. It runs the full chunk loop, sends chunk files, sends
the final merged file + no-subdomain report, then cleans up.
"""

import io
import asyncio
import time
from datetime import datetime

from bot.config  import (
    ACTIVE_SCANS, LAST_FINAL_FILES,
    CHUNK_SIZE, DOMAIN_WORKERS,
)
from bot.state    import get_scan_lock
from bot.logger   import log
from bot.database import db
from bot.retry    import send_with_retry
from bot.resume   import save_resume, delete_resume
from bot.helpers  import progress_bar
from bot.scanner.sources import ALL_SOURCES
from bot.scanner.engine  import scan_domains_parallel
from bot.scanner.output  import (
    build_final_content,
    build_chunk_content,
    build_nosub_content,
)

from telegram.constants import ParseMode
from telegram           import InlineKeyboardButton, InlineKeyboardMarkup


async def run_file_scan_background(
    bot,
    chat_id: int,
    status_msg_id: int,
    domains: list,
    basename: str,
    scan_id: str,
    resume_state: dict | None = None,
):
    # ── Register in global active-scan table ─────────────────────
    cancel_event = asyncio.Event()
    async with get_scan_lock():
        ACTIVE_SCANS[chat_id] = {
            "cancel":   cancel_event,
            "scan_id":  scan_id,
            "basename": basename,
            "total":    len(domains),
            "done":     0,
        }

    log.info(
        f"[BgScan] START scan_id={scan_id} "
        f"domains={len(domains)} chat={chat_id}"
    )

    # ── Resume state ──────────────────────────────────────────────
    already_done_map: dict = {}
    start_chunk             = 0
    all_merged: set         = set()
    no_sub_domains: list    = []

    if resume_state:
        already_done_map = {
            d: set(s)
            for d, s in resume_state.get("results", {}).items()
        }
        start_chunk    = resume_state.get("next_chunk", 0)
        all_merged     = set(resume_state.get("all_merged",    []))
        no_sub_domains = list(resume_state.get("no_sub_domains", []))
        log.info(
            f"[BgScan] Resuming from chunk {start_chunk}, "
            f"done={len(already_done_map)}"
        )

    already_done_set: set = set(already_done_map.keys())
    for subs in already_done_map.values():
        all_merged.update(subs)

    t_start       = time.time()
    summary: dict = dict(already_done_map)
    chunks        = [
        domains[i: i + CHUNK_SIZE]
        for i in range(0, len(domains), CHUNK_SIZE)
    ]
    total_chunks  = len(chunks)

    # ── Rate-limited status editor ────────────────────────────────
    last_edit  = [0.0]
    _edit_lock = asyncio.Lock()

    async def safe_edit(text: str):
        now = time.time()
        if now - last_edit[0] < 3.5:
            return
        async with _edit_lock:
            if time.time() - last_edit[0] < 3.5:
                return
            last_edit[0] = time.time()
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            log.debug(f"[safe_edit] {exc}")

    # ══════════════════════════════════════════════════════════════
    #   C H U N K   L O O P
    # ══════════════════════════════════════════════════════════════
    for chunk_idx in range(start_chunk, total_chunks):
        if cancel_event.is_set():
            break

        chunk        = chunks[chunk_idx]
        chunk_number = chunk_idx + 1
        log.info(
            f"[BgScan] Chunk {chunk_number}/{total_chunks} "
            f"start ({len(chunk)} domains)"
        )

        # ── Progress callback ──────────────────────────────────────
        async def on_progress(
            done, total_d, domain, count,
            _ci=chunk_idx, _cn=chunk_number,
        ):
            async with get_scan_lock():
                if chat_id in ACTIVE_SCANS:
                    ACTIVE_SCANS[chat_id]["done"] = _ci * CHUNK_SIZE + done
            bar = progress_bar(_ci * CHUNK_SIZE + done, len(domains))
            await safe_edit(
                f"🔄 <b>Scanning…</b>\n\n"
                f"📦 Chunk    : <code>{_cn}/{total_chunks}</code>\n"
                f"🎯 Current  : <code>{domain}</code>\n"
                f"📊 Merged   : <b>{len(all_merged) + count}</b>\n\n"
                f"<code>{bar}</code>\n\n"
                f"⚡ <b>{DOMAIN_WORKERS} domains async parallel</b>\n"
                f"❌ /cancel to stop"
            )

        # ── Run chunk ──────────────────────────────────────────────
        chunk_results = await scan_domains_parallel(
            chunk,
            cancel_event,
            progress_cb=on_progress,
            already_done=already_done_set,
        )

        if cancel_event.is_set():
            break

        # ── Aggregate results ──────────────────────────────────────
        chunk_subs:    set  = set()
        chunk_domains: list = []
        for domain, subs in chunk_results.items():
            summary[domain] = subs
            all_merged.update(subs)
            chunk_subs.update(subs)
            already_done_set.add(domain)
            chunk_domains.append(domain)
            if not subs:
                no_sub_domains.append(domain)

        elapsed_so_far = round(time.time() - t_start, 1)

        # ── Save resume ────────────────────────────────────────────
        save_resume(scan_id, {
            "scan_id":        scan_id,
            "basename":       basename,
            "domains":        domains,
            "results":        {d: list(s) for d, s in summary.items()},
            "all_merged":     list(all_merged),
            "no_sub_domains": no_sub_domains,
            "next_chunk":     chunk_number,
            "timestamp":      datetime.now().isoformat(),
        })

        log.info(
            f"[BgScan] Chunk {chunk_number} done: "
            f"{len(chunk_domains)} domains, {len(chunk_subs)} subs"
        )

        # ── Chunk summary message ──────────────────────────────────
        try:
            await bot.send_message(
                chat_id=chat_id,
                parse_mode=ParseMode.HTML,
                text=(
                    f"📦 <b>Chunk {chunk_number}/{total_chunks} Complete!</b>\n\n"
                    f"🎯 Domains scanned : <b>{len(chunk_domains)}</b>\n"
                    f"📊 Subs this chunk : <b>{len(chunk_subs)}</b>\n"
                    f"🔢 Total so far    : <b>{len(all_merged)}</b>\n"
                    f"📭 No-sub so far   : <b>{len(no_sub_domains)}</b>\n"
                    f"⏱ Elapsed         : <code>{elapsed_so_far}s</code>\n\n"
                    f"📦 Chunk file below ↓"
                ),
            )
        except Exception as exc:
            log.error(f"[BgScan] Chunk {chunk_number} summary msg failed: {exc}")

        # ── Chunk file ─────────────────────────────────────────────
        if chunk_subs:
            chunk_content = build_chunk_content(
                chunk_number, total_chunks,
                chunk_domains, chunk_subs, elapsed_so_far,
            )
            chunk_fname = f"chunk_{chunk_number}_of_{total_chunks}_{basename}.txt"

            async def _send_chunk(
                _c=chunk_content, _f=chunk_fname,
                _n=chunk_number, _cd=chunk_domains, _cs=chunk_subs,
                _el=elapsed_so_far,
            ):
                buf = io.BytesIO(_c.encode("utf-8"))
                buf.name = _f
                return await bot.send_document(
                    chat_id=chat_id,
                    document=buf,
                    filename=_f,
                    caption=(
                        f"📦 <b>Chunk {_n}/{total_chunks}</b>\n\n"
                        f"🎯 Domains : <b>{len(_cd)}</b>\n"
                        f"📊 Subs    : <b>{len(_cs)}</b> unique\n"
                        f"⏱ Elapsed : <code>{_el}s</code>"
                    ),
                    parse_mode=ParseMode.HTML,
                )

            try:
                await send_with_retry(_send_chunk)
                log.info(
                    f"[BgScan] Chunk {chunk_number} file sent "
                    f"({len(chunk_subs)} subs)"
                )
            except Exception as exc:
                log.error(
                    f"[BgScan] Chunk {chunk_number} file failed "
                    f"after retries: {exc}"
                )
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        parse_mode=ParseMode.HTML,
                        text=(
                            f"⚠️ Chunk {chunk_number} file could not be sent.\n"
                            f"<code>{exc}</code>"
                        ),
                    )
                except Exception:
                    pass

        # Small pause between chunks to stay under Telegram rate limits
        await asyncio.sleep(1.0)

    # ══════════════════════════════════════════════════════════════
    #   P O S T   L O O P
    # ══════════════════════════════════════════════════════════════
    total_elapsed = round(time.time() - t_start, 1)
    cancelled     = cancel_event.is_set()

    async with get_scan_lock():
        ACTIVE_SCANS.pop(chat_id, None)

    log.info(
        f"[BgScan] DONE scan_id={scan_id} cancelled={cancelled} "
        f"subs={len(all_merged)} time={total_elapsed}s"
    )

    # ── Cancelled ─────────────────────────────────────────────────
    if cancelled:
        try:
            await bot.send_message(
                chat_id=chat_id,
                parse_mode=ParseMode.HTML,
                text=(
                    f"⛔ <b>Scan Cancelled</b>\n\n"
                    f"📊 Completed : <b>{len(already_done_set)}/{len(domains)}</b> domains\n"
                    f"🔢 Subdomains: <b>{len(all_merged)}</b>\n\n"
                    f"💾 Resume saved — use /resume to continue."
                ),
            )
        except Exception as exc:
            log.error(f"[BgScan] Cancel msg failed: {exc}")
        return

    # ── Final merged file ─────────────────────────────────────────
    final_content = build_final_content(
        domains, all_merged, total_elapsed, basename
    )
    final_fname = f"subdomain_{basename}_FINAL.txt"

    LAST_FINAL_FILES[chat_id] = {
        "content": final_content,
        "fname":   final_fname,
        "domains": len(domains),
        "subs":    len(all_merged),
        "elapsed": total_elapsed,
        "nosub":   len(no_sub_domains),
    }

    async def _send_final():
        buf = io.BytesIO(final_content.encode("utf-8"))
        buf.name = final_fname
        return await bot.send_document(
            chat_id=chat_id,
            document=buf,
            filename=final_fname,
            caption=(
                f"✅ <b>COMPLETE MERGED FILE</b>\n\n"
                f"🎯 Domains : <b>{len(domains)}</b>\n"
                f"📊 Total   : <b>{len(all_merged)} unique subdomains</b>\n"
                f"⏱ Time    : <code>{total_elapsed}s</code>\n\n"
                f"💡 Didn't receive this? Use /getfinal"
            ),
            parse_mode=ParseMode.HTML,
        )

    try:
        await send_with_retry(_send_final, max_retries=5)
        log.info(f"[BgScan] Final file sent ({len(all_merged)} subs)")
    except Exception as exc:
        log.error(f"[BgScan] Final file failed after all retries: {exc}")
        try:
            await bot.send_message(
                chat_id=chat_id,
                parse_mode=ParseMode.HTML,
                text=(
                    f"⚠️ <b>Final file could not be delivered.</b>\n\n"
                    f"📊 Found <b>{len(all_merged)}</b> subdomains "
                    f"across <b>{len(domains)}</b> domains.\n\n"
                    f"👉 Use /getfinal to request the file again."
                ),
            )
        except Exception:
            pass

    # ── No-subdomain report ───────────────────────────────────────
    if no_sub_domains:
        nosub_content = build_nosub_content(no_sub_domains, basename)
        nosub_fname   = f"no_subdomains_{basename}.txt"

        async def _send_nosub():
            buf = io.BytesIO(nosub_content.encode("utf-8"))
            buf.name = nosub_fname
            return await bot.send_document(
                chat_id=chat_id,
                document=buf,
                filename=nosub_fname,
                caption=(
                    f"📭 <b>Domains With NO Subdomains Found</b>\n\n"
                    f"🎯 Count : <b>{len(no_sub_domains)}</b> domains\n"
                    f"ℹ️ Zero results from all {len(ALL_SOURCES)} sources."
                ),
                parse_mode=ParseMode.HTML,
            )

        try:
            await send_with_retry(_send_nosub)
            log.info(f"[BgScan] No-sub file sent ({len(no_sub_domains)} domains)")
        except Exception as exc:
            log.error(f"[BgScan] No-sub file failed: {exc}")

    # ── Final summary message ─────────────────────────────────────
    top         = sorted(summary.items(), key=lambda x: len(x[1]), reverse=True)[:15]
    summary_txt = "\n".join(
        f"  <code>{d}</code> → <b>{len(s)}</b>"
        for d, s in top if s
    ) or "  <i>No subdomains found.</i>"
    if len(summary) > 15:
        summary_txt += f"\n  <i>…and {len(summary) - 15} more</i>"

    try:
        await bot.send_message(
            chat_id=chat_id,
            parse_mode=ParseMode.HTML,
            text=(
                f"📊 <b>Final Summary</b>\n\n{summary_txt}\n\n"
                f"🏆 Grand Total    : <b>{len(all_merged)} unique subdomains</b>\n"
                f"📭 No-sub domains : <b>{len(no_sub_domains)}</b>\n"
                f"⏱ Total Time     : <code>{total_elapsed}s</code>"
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🎯 New Scan",  callback_data="mode_single"),
                    InlineKeyboardButton("📄 New File",  callback_data="mode_file"),
                ],
                [
                    InlineKeyboardButton("🔁 Get Final File", callback_data="getfinal"),
                    InlineKeyboardButton("🏠 Main Menu",      callback_data="back_menu"),
                ],
            ]),
        )
    except Exception as exc:
        log.error(f"[BgScan] Summary msg failed: {exc}")

    # ── Cleanup ───────────────────────────────────────────────────
    delete_resume(scan_id)
    db.increment_scans(chat_id)

    from bot.notifications import log_scan_to_channel
    asyncio.create_task(
        log_scan_to_channel(
            bot, chat_id, domains, all_merged, total_elapsed, final_fname
        )
    )

    # Update the original status message
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg_id,
            parse_mode=ParseMode.HTML,
            text=(
                f"✅ <b>Scan Finished!</b>\n\n"
                f"🎯 <b>{len(domains)}</b> domains scanned\n"
                f"📊 <b>{len(all_merged)}</b> unique subdomains\n"
                f"📭 <b>{len(no_sub_domains)}</b> domains had no results\n"
                f"⏱ <code>{total_elapsed}s</code> total\n\n"
                f"💡 Missed the final file? /getfinal"
            ),
        )
    except Exception as exc:
        log.debug(f"[BgScan] Final status edit failed: {exc}")
