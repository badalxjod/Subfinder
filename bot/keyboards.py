"""
bot/keyboards.py — Every InlineKeyboardMarkup used by the bot.
Centralised here so button labels / callback_data are never duplicated.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.config import UPDATES_CHANNEL_URL, DEVELOPER_USERNAME


def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 Single Domain", callback_data="mode_single"),
            InlineKeyboardButton("📄 TXT File",      callback_data="mode_file"),
        ],
        [
            InlineKeyboardButton("📖 Help",  callback_data="help"),
            InlineKeyboardButton("ℹ️ About", callback_data="about"),
        ],
        [
            InlineKeyboardButton("📢 Updates Channel", url=UPDATES_CHANNEL_URL),
            InlineKeyboardButton("👨‍💻 Developer",      url=f"https://t.me/{DEVELOPER_USERNAME}"),
        ],
    ])


def kb_back() -> InlineKeyboardMarkup:
    """Post-scan / generic back keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 New Scan",        callback_data="mode_single"),
            InlineKeyboardButton("📄 File Mode",       callback_data="mode_file"),
        ],
        [
            InlineKeyboardButton("🔁 Get Final File",  callback_data="getfinal"),
            InlineKeyboardButton("🏠 Main Menu",       callback_data="back_menu"),
        ],
        [
            InlineKeyboardButton("📢 Updates Channel", url=UPDATES_CHANNEL_URL),
            InlineKeyboardButton("👨‍💻 Developer",      url=f"https://t.me/{DEVELOPER_USERNAME}"),
        ],
    ])


def kb_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 Users List",   callback_data="admin_users"),
            InlineKeyboardButton("📊 Bot Stats",    callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("📢 Broadcast",    callback_data="admin_broadcast"),
            InlineKeyboardButton("⚡ Active Scans", callback_data="admin_scans"),
        ],
        [
            InlineKeyboardButton("🚫 Ban User",     callback_data="admin_ban"),
            InlineKeyboardButton("✅ Unban User",   callback_data="admin_unban"),
        ],
        [
            InlineKeyboardButton("🏠 Main Menu",    callback_data="back_menu"),
        ],
    ])


def kb_admin_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Back", callback_data="admin_back")],
    ])


def kb_admin_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_back")],
    ])


def kb_channel_dev() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Updates", url=UPDATES_CHANNEL_URL),
            InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{DEVELOPER_USERNAME}"),
        ],
    ])
