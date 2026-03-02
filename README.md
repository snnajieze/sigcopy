# Crypto Signal Bot

Automatically parses trading signals from source Telegram channels and reposts them in your custom format to two personal channels.

---

## Project Structure

```
signal-bot/
├── parser.py          # Signal parsing and formatting logic
├── bot.py             # Telegram bot (listener + poster)
├── test_parser.py     # Test the parser without Telegram
├── requirements.txt
├── .env.example       # Copy this to .env and fill in your values
└── README.md
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Telegram API credentials
- Go to https://my.telegram.org/apps
- Create an app and copy your **API ID** and **API Hash**

### 3. Configure environment
```bash
cp .env.example .env
```
Edit `.env` and fill in:
- `API_ID` and `API_HASH` from step 2
- `MY_CHANNEL_1` and `MY_CHANNEL_2` — your two output channels
- `SOURCE_CHANNELS` — the channels you want to monitor (comma-separated)

### 4. Test the parser locally (no Telegram needed)
```bash
python test_parser.py
```
This runs the three sample signals through the parser and prints both output formats so you can verify everything looks correct before going live.

### 5. Run the bot
```bash
python bot.py
```
On first run, Telethon will ask for your phone number and a one-time code sent by Telegram. After that, a `signal_session.session` file is created and you won't need to log in again.

---

## How It Works

1. `bot.py` listens for new messages in your source channels using your Telegram account (userbot)
2. Each message is checked by `looks_like_signal()` to filter out non-signal posts
3. `parser.py` extracts: coin name, direction, entry zone, targets, stop loss
4. The signal is formatted into two different styles
5. Both formatted messages are posted to your respective channels

---

## Adding a New Source Channel Format

If a new source channel uses a format the parser doesn't recognize, open `parser.py` and update the relevant function:

- `parse_entry()` — for new entry/buy zone formats
- `parse_targets()` — for new target formats
- `parse_stoploss()` — for new stop loss label variations
- `parse_direction()` — for new direction keywords

---

## Deploying to a Server

Once tested locally, you can deploy to any Linux VPS:

```bash
# Install dependencies
pip install -r requirements.txt

# Copy your .env file to the server (with your credentials)

# Run in background with screen or tmux
screen -S signalbot
python bot.py
# Press Ctrl+A then D to detach

# Or use systemd for automatic restart on reboot
```

The `signal_session.session` file keeps you logged in — make sure to copy it to the server after first-time login on your local machine.
