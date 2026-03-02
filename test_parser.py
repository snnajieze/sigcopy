"""
Test the parser against all three sample channel formats.
Run: python test_parser.py
"""

from parser import process_signal

# ─────────────────────────────────────────────
#  SAMPLE SIGNALS
# ─────────────────────────────────────────────

CHANNEL_1_SIGNAL = """
📍Coin : #DOGS/USDT

🟢 LONG 

👉 Entry: 0.00002800 - 0.00002749

🌐 Leverage: 20x

🎯 Target 1: 0.00002828
🎯 Target 2: 0.00002856
🎯 Target 3: 0.00002884
🎯 Target 4: 0.00002913
🎯 Target 5: 0.00002942
🎯 Target 6: 0.00002972

❌ StopLoss: 0.00002610
"""

CHANNEL_2_SIGNAL = """
⚡ #GUN/USDT

📥 Short 

💹 Buy: 0.02850 - 0.02940

🧿 Target: 0.02822 - 0.02794 - 0.02767 - 0.02740 - 0.02713 - 0.02685

🧨 StopLoss: 0.03000 

🔘 Leverage: 20x
"""

CHANNEL_3_SIGNAL = """
🔱 Trade: #BTCDOM/USDT 🔱

🔴 SHORT ZONE: 4680 - 4774

🀄️ LEVERAGE: 27x

1.🎯 4645
2.🎯 4599
3.🎯 4540
4.🎯 4493
5.🎯 4446
6.🎯 4399

⛔️ STOP-LOSS: 4820
"""

SIGNALS = {
    "Channel 1 (DOGS - LONG)":   CHANNEL_1_SIGNAL,
    "Channel 2 (GUN - SHORT)":   CHANNEL_2_SIGNAL,
    "Channel 3 (BTCDOM - SHORT)": CHANNEL_3_SIGNAL,
}

# ─────────────────────────────────────────────
#  RUN TESTS
# ─────────────────────────────────────────────

DIVIDER = "=" * 60

for label, raw in SIGNALS.items():
    print(f"\n{DIVIDER}")
    print(f"SOURCE: {label}")
    print(DIVIDER)
    print("RAW INPUT:")
    print(raw.strip())
    print()

    msg1, msg2 = process_signal(raw)

    print("──── OUTPUT: MY CHANNEL 1 ────")
    print(msg1)
    print()
    print("──── OUTPUT: MY CHANNEL 2 ────")
    print(msg2)
    print()
