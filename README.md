# Mini Countryman E Favoured Monitor

Monitors the Mini Turkey online store for Countryman E "Favoured" pack availability.

## What It Monitors

1. **Tasarla Button** - Checks if preorder/design button appears for Countryman E
2. **Stock List** - Checks if "Favoured" pack vehicles are in stock

## Quick Setup

### 1. Install Dependencies

```bash
cd ~/Desktop/mini-bot
pip3 install -r requirements.txt
python3 -m playwright install chromium
```

### 2. Set Up Telegram Notifications

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow prompts to create a bot
3. Copy the **bot token** (looks like `1234567890:ABCdefGHI...`)
4. Message your new bot (important: send any message first!)
5. Message [@userinfobot](https://t.me/userinfobot) to get your **chat ID**

### 3. Configure the Script

Edit `mini_monitor.py` and fill in:

```python
TELEGRAM_BOT_TOKEN = "your_bot_token_here"
TELEGRAM_CHAT_ID = "your_chat_id_here"
```

### 4. Run the Monitor

```bash
python mini_monitor.py
```

## Running in Background

### Option A: Screen/tmux (Recommended for Mac)

```bash
# Using screen
screen -S mini-monitor
python mini_monitor.py
# Press Ctrl+A, then D to detach

# To reattach later:
screen -r mini-monitor
```

### Option B: nohup

```bash
nohup python mini_monitor.py > monitor_output.log 2>&1 &
```

## Configuration Options

In `mini_monitor.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CHECK_INTERVAL_MINUTES` | 10 | How often to check (be respectful!) |
| `TARGET_PACK` | "Favoured" | Pack name to look for |
| `EMAIL_ENABLED` | False | Enable email notifications |

## Logs

Check `mini_monitor.log` for detailed check history.
