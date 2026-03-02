"""
Crypto Signal Parser
Parses signals from different Telegram channels and reformats them
into two different output formats for your personal channels.
"""

import re


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def clean_coin(raw: str) -> str:
    """Normalize coin name → e.g. DOGS/USDT"""
    coin = raw.strip().lstrip("#").upper()
    if "/" not in coin:
        coin = coin + "/USDT"
    return coin


def parse_direction(text: str) -> str:
    """Return 'Long' or 'Short'"""
    upper = text.upper()
    # look for explicit SHORT first (short zone, short, sell)
    if re.search(r'\bSHORT\b|\bSELL\b', upper):
        return "Short"
    if re.search(r'\bLONG\b|\bBUY\b', upper):
        return "Long"
    return "Long"  # default fallback


def parse_entry(text: str) -> str:
    """
    Extract entry range. Handles:
      Entry: 0.028 - 0.029
      Buy: 0.028 - 0.029
      SHORT ZONE: 4680 - 4774
    Returns 'low - high' string.
    """
    patterns = [
        r'(?:entry|buy|long zone|short zone|entry zone)[:\s]*'
        r'([\d.]+)\s*[-–]\s*([\d.]+)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return f"{m.group(1)} - {m.group(2)}"

    # single value entry
    m = re.search(r'(?:entry|buy)[:\s]*([\d.]+)', text, re.IGNORECASE)
    if m:
        return m.group(1)

    return "N/A"


def parse_targets(text: str) -> list:
    """
    Extract all target values. Handles:
      Target 1: 0.028  Target 2: 0.029  ...
      Target: 0.028 - 0.029 - 0.030
      1.🎯 4645   2.🎯 4599  ...
      🎯 4645  (plain emoji lines)
    """
    targets = []

    # Format: "Target 1: val", "TP1 val", etc.
    numbered = re.findall(
        r'(?:target|tp)\s*\d+\s*[:\s]+([\d.]+)',
        text, re.IGNORECASE
    )
    if numbered:
        return numbered

    # Format: "Target: val - val - val"
    m = re.search(r'target[:\s]+([\d.\s\-–]+)', text, re.IGNORECASE)
    if m:
        targets = re.findall(r'[\d.]+', m.group(1))
        if targets:
            return targets

    # Format: "1.🎯 4645" or "🎯 4645"
    emoji_targets = re.findall(r'(?:\d+\.)?\s*🎯\s*([\d.]+)', text)
    if emoji_targets:
        return emoji_targets

    return targets


def parse_stoploss(text: str) -> str:
    """Extract stop loss value."""
    m = re.search(
        r'(?:stop.?loss|stop|sl|stoploss)[:\s]*([\d.]+)',
        text, re.IGNORECASE
    )
    return m.group(1) if m else "N/A"


# ─────────────────────────────────────────────
#  CORE PARSER
# ─────────────────────────────────────────────

def parse_signal(raw_text: str) -> dict:
    """
    Parse a raw signal from any source channel into a structured dict.
    Returns:
        {
            coin, direction, entry, targets (list), stoploss
        }
    """
    # Extract coin — look for #SYMBOL/USDT or #SYMBOL pattern
    coin_match = re.search(r'#([A-Z0-9]+(?:/USDT)?)', raw_text, re.IGNORECASE)
    if not coin_match:
        # fallback: look for WORD/USDT without hash
        coin_match = re.search(r'\b([A-Z0-9]{2,10}/USDT)\b', raw_text, re.IGNORECASE)

    coin = clean_coin(coin_match.group(1)) if coin_match else "UNKNOWN/USDT"

    direction = parse_direction(raw_text)
    entry     = parse_entry(raw_text)
    targets   = parse_targets(raw_text)
    stoploss  = parse_stoploss(raw_text)

    return {
        "coin":      coin,
        "direction": direction,
        "entry":     entry,
        "targets":   targets,
        "stoploss":  stoploss,
    }


# ─────────────────────────────────────────────
#  FORMATTERS
# ─────────────────────────────────────────────

def format_channel1(signal: dict) -> str:
    """
    Format for Channel 1:

    #DOGE/USDT

    Long
    Leverage: cross 20x

    Entry zone: 0.09947 - 0.10130

    Target: 0.10252 - 0.10353 - ...

    Stop: 0.09822
    """
    coin      = f"#{signal['coin']}"
    direction = signal["direction"]
    entry     = signal["entry"]
    targets   = " - ".join(signal["targets"])
    stoploss  = signal["stoploss"]

    return (
        f"{coin}\n\n"
        f"{direction}\n"
        f"Leverage: cross 20x\n\n"
        f"Entry zone: {entry}\n\n"
        f"Target: {targets}\n\n"
        f"Stop: {stoploss}"
    )


def format_channel2(signal: dict) -> str:
    """
    Format for Channel 2:

    DOGE/USDT 📈 BUY

    🔹Entry zone: 0.09947 - 0.10120

    💰TP1 0.10252
    💰TP2 0.10353
    ...
    🚫SL 0.09600

    〽️Leverage cross 10x

    ⚠️Respect the entry zone. Check the bio of the channel for all the info required to follow our signals
    """
    coin      = signal["coin"]
    direction = signal["direction"].upper()
    entry     = signal["entry"]
    stoploss  = signal["stoploss"]

    # Direction emoji
    dir_emoji = "📈" if signal["direction"] == "Long" else "📉"

    # Numbered TPs
    tp_lines = "\n".join(
        f"💰TP{i+1} {val}"
        for i, val in enumerate(signal["targets"])
    )

    return (
        f"{coin} {dir_emoji} {direction}\n\n"
        f"🔹Entry zone: {entry}\n\n"
        f"{tp_lines}\n"
        f"🚫SL {stoploss}\n\n"
        f"〽️Leverage cross 10x\n\n"
        f"⚠️Respect the entry zone. Check the bio of the channel for all the info required to follow our signals"
    )


# ─────────────────────────────────────────────
#  MAIN PIPELINE
# ─────────────────────────────────────────────

def process_signal(raw_text: str) -> tuple[str, str]:
    """
    Full pipeline: raw text → (channel1_msg, channel2_msg)
    """
    signal = parse_signal(raw_text)
    msg1   = format_channel1(signal)
    msg2   = format_channel2(signal)
    return msg1, msg2
