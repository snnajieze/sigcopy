"""
Crypto Signal Parser
Parses signals from different Telegram channels and reformats them
into two different output formats for your personal channels.

Stop Loss Adjustment Rules (using 20x leverage as reference):
  - Entry reference: highest price for Long, lowest price for Short
  - Acceptable loss range: 100% – 128% at 20x → keep original SL
  - Outside that range → adjust SL to give exactly 110% loss at 20x
  - Same adjusted SL price is used for both channels
    (at 10x it gives ~55% loss)
"""

import re
import logging

log = logging.getLogger(__name__)


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
    if re.search(r'\bSHORT\b|\bSELL\b', upper):
        return "Short"
    if re.search(r'\bLONG\b|\bBUY\b', upper):
        return "Long"
    return "Long"  # default fallback


def parse_entry(text: str) -> dict:
    """
    Extract entry range. Handles:
      Entry: 0.028 - 0.029
      Buy: 0.028 - 0.029
      SHORT ZONE: 4680 - 4774
    Returns dict with raw string plus low and high as floats.
    """
    m = re.search(
        r'(?:entry|buy|long zone|short zone|entry zone)[:\s]*'
        r'([\d.]+)\s*[-–]\s*([\d.]+)',
        text, re.IGNORECASE
    )
    if m:
        return {
            "raw":  f"{m.group(1)} - {m.group(2)}",
            "low":  float(m.group(1)),
            "high": float(m.group(2)),
        }

    # Single value entry
    m = re.search(r'(?:entry|buy)[:\s]*([\d.]+)', text, re.IGNORECASE)
    if m:
        v = float(m.group(1))
        return {"raw": m.group(1), "low": v, "high": v}

    return {"raw": "N/A", "low": 0.0, "high": 0.0}


def parse_targets(text: str) -> list:
    """
    Extract all target values. Handles:
      Target 1: 0.028  Target 2: 0.029  ...
      Target: 0.028 - 0.029 - 0.030
      1.🎯 4645   2.🎯 4599  ...
      🎯 4645  (plain emoji lines)
    """
    # Format A: "Target 1: val", "TP1 val", etc.
    numbered = re.findall(
        r'(?:target|tp)\s*\d+\s*[:\s]+([\d.]+)',
        text, re.IGNORECASE
    )
    if numbered:
        return numbered

    # Format B: "Target: val - val - val"
    m = re.search(r'target[:\s]+([\d.\s\-–]+)', text, re.IGNORECASE)
    if m:
        targets = re.findall(r'[\d.]+', m.group(1))
        if targets:
            return targets

    # Format C: "1.🎯 4645" or "🎯 4645"
    emoji_targets = re.findall(r'(?:\d+\.)?\s*🎯\s*([\d.]+)', text)
    if emoji_targets:
        return emoji_targets

    return []


def parse_stoploss(text: str) -> float | None:
    """Extract stop loss value as float, or None if not found."""
    m = re.search(
        r'(?:stop.?loss|stop|sl|stoploss)[:\s]*([\d.]+)',
        text, re.IGNORECASE
    )
    return float(m.group(1)) if m else None


def get_decimals(num: float) -> int:
    """Count decimal places of a float."""
    s = str(num)
    dot = s.find('.')
    return 0 if dot == -1 else len(s) - dot - 1


# ─────────────────────────────────────────────
#  STOP LOSS ADJUSTMENT
# ─────────────────────────────────────────────

def adjust_stoploss(direction: str, entry_low: float, entry_high: float,
                    raw_sl: float) -> tuple[float, bool, float]:
    """
    Checks whether the stop loss represents an acceptable loss at 20x leverage.
    Entry reference price:
      Long  → highest entry price (closest to market when going long)
      Short → lowest entry price  (closest to market when going short)

    Acceptable range: 100% – 128% loss at 20x → keep original SL.
    Outside that range → adjust SL to give exactly 110% loss at 20x.
    Same SL price is used for both channels (gives ~55% loss at 10x).

    Returns:
        (final_sl, was_adjusted, loss_pct_at_20x)
    """
    entry_ref = entry_high if direction == "Long" else entry_low
    leverage = 20

    loss_pct = (
        ((entry_ref - raw_sl) / entry_ref) * leverage * 100
        if direction == "Long"
        else ((raw_sl - entry_ref) / entry_ref) * leverage * 100
    )

    # Already within acceptable range — keep as-is
    if 100 <= loss_pct <= 128:
        return raw_sl, False, loss_pct

    # Adjust to exactly 110% loss at 20x
    target_loss = 1.10
    new_sl = (
        entry_ref * (1 - target_loss / leverage)
        if direction == "Long"
        else entry_ref * (1 + target_loss / leverage)
    )

    new_loss_pct = (
        ((entry_ref - new_sl) / entry_ref) * leverage * 100
        if direction == "Long"
        else ((new_sl - entry_ref) / entry_ref) * leverage * 100
    )

    return new_sl, True, new_loss_pct


# ─────────────────────────────────────────────
#  CORE PARSER
# ─────────────────────────────────────────────

def parse_signal(raw_text: str) -> dict:
    """
    Parse a raw signal from any source channel into a structured dict.
    Adjusts the stop loss if it falls outside the acceptable risk range.
    """
    # Extract coin
    coin_match = re.search(r'#([A-Z0-9]+(?:/USDT)?)', raw_text, re.IGNORECASE)
    if not coin_match:
        coin_match = re.search(
            r'\b([A-Z0-9]{2,10}/USDT)\b', raw_text, re.IGNORECASE)
    coin = clean_coin(coin_match.group(1)) if coin_match else "UNKNOWN/USDT"

    direction = parse_direction(raw_text)
    entry = parse_entry(raw_text)
    targets = parse_targets(raw_text)
    raw_sl = parse_stoploss(raw_text)

    # Adjust SL if we have enough data
    if raw_sl is not None and entry["low"] > 0:
        final_sl, adjusted, loss_pct_20x = adjust_stoploss(
            direction, entry["low"], entry["high"], raw_sl
        )
        # Preserve decimal precision of original values
        decimals = max(get_decimals(raw_sl), get_decimals(entry["low"]))
        stoploss = f"{final_sl:.{decimals}f}"

        if adjusted:
            log.info(
                f"SL adjusted: {raw_sl} → {stoploss} "
                f"(loss at 20x: {loss_pct_20x:.2f}%, at 10x: {loss_pct_20x/2:.2f}%)"
            )
        else:
            log.info(
                f"SL OK: {stoploss} "
                f"(loss at 20x: {loss_pct_20x:.2f}%, at 10x: {loss_pct_20x/2:.2f}%)"
            )
    else:
        stoploss = str(raw_sl) if raw_sl is not None else "N/A"

    return {
        "coin":      coin,
        "direction": direction,
        "entry":     entry["raw"],
        "targets":   targets,
        "stoploss":  stoploss,
    }


# ─────────────────────────────────────────────
#  FORMATTERS
# ─────────────────────────────────────────────

def format_channel1(signal: dict) -> str:
    """
    #DOGE/USDT

    Long
    Leverage: cross 20x

    Entry zone: 0.09947 - 0.10130

    Target: 0.10252 - 0.10353 - ...

    Stop: 0.09822
    """
    return (
        f"#{signal['coin']}\n\n"
        f"{signal['direction']}\n"
        f"Leverage: cross 20x\n\n"
        f"Entry zone: {signal['entry']}\n\n"
        f"Target: {' - '.join(signal['targets'])}\n\n"
        f"Stop: {signal['stoploss']}"
    )


def format_channel2(signal: dict) -> str:
    """
    DOGE/USDT 📈 BUY

    🔹Entry zone: 0.09947 - 0.10120

    💰TP1 0.10252
    💰TP2 0.10353
    ...
    🚫SL 0.09600

    〽️Leverage cross 10x

    ⚠️Respect the entry zone. Check the bio of the channel for all the info required to follow our signals
    """
    dir_emoji = "📈" if signal["direction"] == "Long" else "📉"
    tp_lines = "\n".join(
        f"💰TP{i+1} {val}"
        for i, val in enumerate(signal["targets"])
    )

    return (
        f"{signal['coin']} {dir_emoji} {signal['direction'].upper()}\n\n"
        f"🔹Entry zone: {signal['entry']}\n\n"
        f"{tp_lines}\n"
        f"🚫SL {signal['stoploss']}\n\n"
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
    return format_channel1(signal), format_channel2(signal)
