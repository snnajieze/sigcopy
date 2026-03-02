"""
Telegram Signal Bot
Listens to source channels and auto-posts reformatted signals to your two channels.

Requirements:
    pip install telethon python-dotenv

Setup:
    1. Fill in your .env file (see .env.example)
    2. Run: python bot.py
    3. On first run, enter your phone number and OTP to authenticate
"""

import asyncio
import logging
from telethon import TelegramClient, events
from dotenv import load_dotenv
import os
from parser import process_signal

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

load_dotenv()

API_ID   = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Your two personal output channels (use @username or numeric ID)
MY_CHANNEL_1 = os.getenv("MY_CHANNEL_1")   # e.g. @mychannel1 or -1001234567890
MY_CHANNEL_2 = os.getenv("MY_CHANNEL_2")   # e.g. @mychannel2 or -1009876543210

# Source channels to monitor (comma-separated in .env)
# e.g. SOURCE_CHANNELS=@signals1,@signals2,@signals3
SOURCE_CHANNELS = [
    ch.strip()
    for ch in os.getenv("SOURCE_CHANNELS", "").split(",")
    if ch.strip()
]

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  BOT
# ─────────────────────────────────────────────

client = TelegramClient("signal_session", API_ID, API_HASH)


def looks_like_signal(text: str) -> bool:
    """
    Quick pre-filter: only process messages that look like trading signals.
    Avoids reformatting random announcements or text posts.
    """
    text_up = text.upper()
    has_direction = any(kw in text_up for kw in ["LONG", "SHORT", "BUY", "SELL"])
    has_entry     = any(kw in text_up for kw in ["ENTRY", "BUY:", "ZONE"])
    has_target    = any(kw in text_up for kw in ["TARGET", "TP", "🎯"])
    has_stop      = any(kw in text_up for kw in ["STOP", "SL", "STOPLOSS"])
    return has_direction and (has_entry or has_target) and has_stop


@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def on_new_signal(event):
    raw = event.raw_text
    if not raw or not looks_like_signal(raw):
        log.info("Skipped non-signal message.")
        return

    log.info(f"Signal detected from {event.chat_id}:\n{raw}\n")

    try:
        msg1, msg2 = process_signal(raw)
    except Exception as e:
        log.error(f"Parser error: {e}")
        return

    try:
        await client.send_message(MY_CHANNEL_1, msg1)
        log.info(f"Posted to Channel 1:\n{msg1}\n")

        await asyncio.sleep(1)  # small delay between posts

        await client.send_message(MY_CHANNEL_2, msg2)
        log.info(f"Posted to Channel 2:\n{msg2}\n")

    except Exception as e:
        log.error(f"Failed to send message: {e}")


async def main():
    log.info("Starting signal bot...")
    log.info(f"Monitoring channels: {SOURCE_CHANNELS}")
    await client.start()
    log.info("Bot is running. Waiting for signals...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
