#!/usr/bin/env python3
"""
SubHunter Bot — main.py
Entry point: builds the Application, registers all handlers, starts polling.
"""

import warnings
from telegram.warnings import PTBUserWarning
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

warnings.filterwarnings(
    "ignore",
    message=r".*per_message=False.*CallbackQueryHandler.*",
    category=PTBUserWarning,
)

from bot.logger import log  # noqa: E402 — must be first

from bot.config import (
    BOT_TOKEN,
    DOMAIN_WORKERS, CHUNK_SIZE, SOURCE_TIMEOUT,
    RESUME_DIR, USERS_FILE, LOG_FILE, LOG_CHANNEL_ID, ADMIN_IDS,
    CHOOSING_MODE, WAITING_DOMAIN, WAITING_FILE,
    ADMIN_BROADCAST, ADMIN_BAN_INPUT, ADMIN_UNBAN_INPUT,
)

from bot.handlers.start import (
    cmd_start, cmd_scan, cmd_help, cmd_about, cmd_fallback, button_handler,
)
from bot.handlers.scan import (
    cmd_cancel, cmd_resume, cmd_status, cmd_getfinal,
    handle_domain_input, handle_file_input,
)
from bot.handlers.admin import (
    cmd_admin, cmd_ban, cmd_unban, cmd_broadcast,
    handle_admin_broadcast, handle_admin_ban_input, handle_admin_unban_input,
)


def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            CommandHandler("scan",  cmd_scan),
        ],
        states={
            CHOOSING_MODE: [
                CallbackQueryHandler(button_handler),
            ],
            WAITING_DOMAIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_domain_input),
                CallbackQueryHandler(button_handler),
            ],
            WAITING_FILE: [
                MessageHandler(filters.Document.ALL, handle_file_input),
                CallbackQueryHandler(button_handler),
            ],
            ADMIN_BROADCAST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_broadcast),
                CallbackQueryHandler(button_handler),
            ],
            ADMIN_BAN_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_ban_input),
                CallbackQueryHandler(button_handler),
            ],
            ADMIN_UNBAN_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_unban_input),
                CallbackQueryHandler(button_handler),
            ],
        },
        fallbacks=[
            CommandHandler("start",     cmd_start),
            CommandHandler("scan",      cmd_scan),
            CommandHandler("cancel",    cmd_cancel),
            CommandHandler("resume",    cmd_resume),
            CommandHandler("status",    cmd_status),
            CommandHandler("getfinal",  cmd_getfinal),
            CommandHandler("help",      cmd_help),
            CommandHandler("about",     cmd_about),
            CommandHandler("admin",     cmd_admin),
            CommandHandler("ban",       cmd_ban),
            CommandHandler("unban",     cmd_unban),
            CommandHandler("broadcast", cmd_broadcast),
            MessageHandler(filters.ALL, cmd_fallback),
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)

    # Global commands (work outside conversation too)
    for cmd, fn in [
        ("cancel",    cmd_cancel),
        ("resume",    cmd_resume),
        ("status",    cmd_status),
        ("getfinal",  cmd_getfinal),
        ("help",      cmd_help),
        ("about",     cmd_about),
        ("admin",     cmd_admin),
        ("ban",       cmd_ban),
        ("unban",     cmd_unban),
        ("broadcast", cmd_broadcast),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    return app


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Export it as an environment variable.")

    log.info("SubHunter Bot starting…")
    log.info(f"  ADMIN_IDS      : {ADMIN_IDS}")
    log.info(f"  LOG_CHANNEL    : {LOG_CHANNEL_ID}")
    log.info(f"  DOMAIN_WORKERS : {DOMAIN_WORKERS}")
    log.info(f"  CHUNK_SIZE     : {CHUNK_SIZE}")
    log.info(f"  SOURCE_TIMEOUT : {SOURCE_TIMEOUT}s")
    log.info(f"  RESUME_DIR     : {RESUME_DIR}")
    log.info(f"  USERS_FILE     : {USERS_FILE}")
    log.info(f"  LOG_FILE       : {LOG_FILE}")

    app = build_app()
    log.info("Bot is live — polling started. Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
