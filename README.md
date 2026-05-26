# SubHunter Bot — VPS Setup Guide

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Set environment variables

Create a `.env` file or export these before running:

```bash
export BOT_TOKEN="your_bot_token_here"
export ADMIN_IDS="123456789"          # comma-separated for multiple admins
export LOG_CHANNEL_ID="-1001234567890"
export UPDATES_CHANNEL_URL="https://t.me/yourchannel"
export DEVELOPER_USERNAME="yourusername"
```

Or use a `.env` file with `python-dotenv` (optional):
```
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789
LOG_CHANNEL_ID=-1001234567890
```

## 3. Run the bot

```bash
python main.py
```

## 4. Run as a systemd service (recommended for VPS)

Create `/etc/systemd/system/subhunter.service`:

```ini
[Unit]
Description=SubHunter Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/SubHunterBot
Environment=BOT_TOKEN=your_token_here
Environment=ADMIN_IDS=123456789
Environment=LOG_CHANNEL_ID=-1001234567890
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable subhunter
sudo systemctl start subhunter
sudo systemctl status subhunter
```

View logs:
```bash
journalctl -u subhunter -f        # live systemd logs
tail -f /tmp/subhunter.log        # bot's own log file
```

## Optional paths (defaults use /tmp)

| Variable      | Default              | Description        |
|---------------|----------------------|--------------------|
| RESUME_DIR    | /tmp/resume_data     | Scan resume files  |
| USERS_FILE    | /tmp/users.json      | User database      |
| LOG_FILE      | /tmp/subhunter.log   | Bot log file       |

For persistence across reboots, change these to a permanent directory:
```bash
export RESUME_DIR=/home/ubuntu/subhunter_data/resume
export USERS_FILE=/home/ubuntu/subhunter_data/users.json
export LOG_FILE=/home/ubuntu/subhunter_data/bot.log
```
