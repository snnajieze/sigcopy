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
import time
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel
from dotenv import load_dotenv
import os
from parser import process_signal

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Your two personal output channels (use @username or numeric ID)
MY_CHANNEL_1 = os.getenv("MY_CHANNEL_1")   # e.g. @mychannel1 or -1001234567890
MY_CHANNEL_2 = os.getenv("MY_CHANNEL_2")   # e.g. @mychannel2 or -1009876543210

# Source channels to monitor (comma-separated in .env)
# Use @username format (preferred) or numeric IDs if you're a member
# e.g. SOURCE_CHANNELS=@signals1,@signals2,@signals3
SOURCE_CHANNELS = [
    ch.strip()
    for ch in os.getenv("SOURCE_CHANNELS", "").split(",")
    if ch.strip()
]

if not SOURCE_CHANNELS:
    print("WARNING: No SOURCE_CHANNELS configured in .env")
    print("Add SOURCE_CHANNELS=@channel1,@channel2 to your .env file")

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

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
client = TelegramClient("signal_session", API_ID, API_HASH, loop=loop)


def looks_like_signal(text: str) -> bool:
    """
    Quick pre-filter: only process messages that look like trading signals.
    Avoids reformatting random announcements or text posts.
    """
    text_up = text.upper()
    has_direction = any(kw in text_up for kw in [
                        "LONG", "SHORT", "BUY", "SELL"])
    has_entry = any(kw in text_up for kw in ["ENTRY", "BUY:", "ZONE"])
    has_target = any(kw in text_up for kw in ["TARGET", "TP", "🎯"])
    has_stop = any(kw in text_up for kw in ["STOP", "SL", "STOPLOSS"])
    return has_direction and (has_entry or has_target) and has_stop


@client.on(events.NewMessage())
async def on_new_signal(event):
    # Check if message is from a monitored source channel
    # Handle both numeric IDs (-1001234567890) and @usernames
    chat_id = event.chat_id
    is_monitored = False

    for channel in SOURCE_CHANNELS:
        channel = channel.strip()
        # Numeric ID comparison
        if channel.lstrip('-').isdigit() and int(channel) == chat_id:
            is_monitored = True
            break
        # Username comparison
        if channel.startswith('@') and hasattr(event.chat, 'username'):
            if f"@{event.chat.username}".lower() == channel.lower():
                is_monitored = True
                break

    if not is_monitored:
        return  # Not from a monitored channel, ignore

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
        if ch1_entity:
            await client.send_message(ch1_entity, msg1)
            log.info(f"Posted to Channel 1:\n{msg1}\n")
        else:
            log.error("Channel 1 entity not resolved. Skipping.")

        await asyncio.sleep(1)

        if ch2_entity:
            await client.send_message(ch2_entity, msg2)
            log.info(f"Posted to Channel 2:\n{msg2}\n")
        else:
            log.error("Channel 2 entity not resolved. Skipping.")

    except ValueError as e:
        log.error(f"Invalid channel ID: {e}")
        log.error(f"Check MY_CHANNEL_1 and MY_CHANNEL_2 in your .env file")
    except Exception as e:
        log.error(f"Failed to send message: {e}")

# Resolved output channel entities (set at startup)
ch1_entity = None
ch2_entity = None


def to_peer_channel(full_id: str):
    """Convert Bot API format (-1001234567890) to Telethon PeerChannel."""
    raw = int(full_id)
    # Strip the -100 prefix to get the real channel ID
    channel_id = int(str(raw).replace('-100', '', 1))
    return PeerChannel(channel_id)


async def main():
    global ch1_entity, ch2_entity

    log.info("Starting signal bot...")
    log.info(f"Monitoring channels: {SOURCE_CHANNELS}")
    log.info(f"Output Channel 1: {MY_CHANNEL_1}")
    log.info(f"Output Channel 2: {MY_CHANNEL_2}")

    # Track if we hit the asyncio error
    loop_error = []
    loop = asyncio.get_event_loop()

    def handle_exception(loop, context):
        exception = context.get('exception')
        if isinstance(exception, RuntimeError) and "got Future" in str(exception):
            log.warning(
                "Detected asyncio loop error in Telethon. Restarting...")
            loop_error.append(True)  # Mark that error occurred
        # Print the error but don't stop - let client handle reconnection
        log.debug(f"Asyncio exception: {exception}")

    loop.set_exception_handler(handle_exception)

    await client.start()
    log.info("Connected to Telegram")

    log.info("Syncing channel list...")
    await client.get_dialogs()

    # Resolve output channel entities once at startup
    try:
        ch1_entity = await client.get_entity(to_peer_channel(MY_CHANNEL_1))
        log.info(f"Resolved Channel 1: {ch1_entity.title}")
    except Exception as e:
        log.error(f"Could not resolve MY_CHANNEL_1 ({MY_CHANNEL_1}): {e}")

    try:
        ch2_entity = await client.get_entity(to_peer_channel(MY_CHANNEL_2))
        log.info(f"Resolved Channel 2: {ch2_entity.title}")
    except Exception as e:
        log.error(f"Could not resolve MY_CHANNEL_2 ({MY_CHANNEL_2}): {e}")

    log.info("Bot is running. Waiting for signals...")
    await client.run_until_disconnected()

    # If we detected the asyncio error, raise it so retry logic can handle it
    if loop_error:
        raise RuntimeError("Asyncio event loop error detected - restarting")


if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")
    finally:
        loop.close()
