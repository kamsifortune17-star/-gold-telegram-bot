import os
import requests
import yfinance as yf
import pandas as pd

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def get_data(interval):
    df = yf.download(
            "GC=F",
        period="5d",
        interval=interval,
        progress=False
    )

    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return df.dropna()

def calculate_signal():
    m5 = get_data("5m")
    m15 = get_data("15m")

    if m5 is None or m15 is None:
        return "Gold price data is unavailable."

    if len(m5) < 30 or len(m15) < 30:
        return "Not enough price data to calculate signals."

    def indicators(df):
        close = df["Close"]
        fast = close.rolling(9).mean()
        slow = close.rolling(21).mean()

        previous_fast = fast.iloc[-2]
        previous_slow = slow.iloc[-2]
        current_fast = fast.iloc[-1]
        current_slow = slow.iloc[-1]

        return (
            previous_fast,
            previous_slow,
            current_fast,
            current_slow
        )

    p5f, p5s, f5, s5 = indicators(m5)
    _, _, f15, s15 = indicators(m15)

    buy_cross = p5f <= p5s and f5 > s5
    sell_cross = p5f >= p5s and f5 < s5

    if buy_cross and f15 > s15:
        direction = "BUY"
    elif sell_cross and f15 < s15:
        direction = "SELL"
    else:
        return None

    high = m5["High"]
    low = m5["Low"]
    close = m5["Close"]

    previous_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - previous_close).abs(),
        (low - previous_close).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(14).mean().iloc[-1]
    entry = float(close.iloc[-1])

    if pd.isna(atr) or atr <= 0:
        return None

    if direction == "BUY":
        sl = entry - 1.5 * atr
        tp1 = entry + atr
        tp2 = entry + 2 * atr
        tp3 = entry + 3 * atr
    else:
        sl = entry + 1.5 * atr
        tp1 = entry - atr
        tp2 = entry - 2 * atr
        tp3 = entry - 3 * atr

    confidence = 75

    return (
        f"🟡 XAUUSD {direction}\n\n"
        f"📍 Entry: {entry:.2f}\n"
        f"🛑 Stop Loss: {sl:.2f}\n"
        f"🎯 TP1: {tp1:.2f}\n"
        f"🎯 TP2: {tp2:.2f}\n"
        f"🎯 TP3: {tp3:.2f}\n\n"
        f"⏱️ Timeframes: M5 + M15\n"
        f"📊 Strategy: MA Crossover + ATR\n"
        f"💪 Strategy Score: {confidence}/100\n\n"
        f"⚠️ Educational signal; verify prices with your broker."
    )

def main():
    signal = calculate_signal()

    if not signal:
        print("No new confirmed signal.")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": signal
        },
        timeout=20
    )

    response.raise_for_status()
    print("Signal sent successfully.")

if __name__ == "__main__":
    main()
