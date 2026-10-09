import os
import requests
import yfinance as yf
import pandas as pd

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def get_data(interval):
    try:
        df = yf.download(
            "GC=F",
            period="5d",
            interval=interval,
            progress=False,
            auto_adjust=False
        )

        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.dropna()

        # Use completed candles only
        if len(df) > 1:
            df = df.iloc[:-1]

        return df if len(df) >= 25 else None

    except Exception as e:
        print(f"Data error ({interval}): {e}")
        return None


def calculate_signal():
    m5 = get_data("5m")
    m15 = get_data("15m")

    if m5 is None:
        print("M5 gold price data unavailable.")
        return None

    close = m5["Close"]
    fast = close.rolling(9).mean()
    slow = close.rolling(21).mean()

    previous_fast = fast.iloc[-2]
    previous_slow = slow.iloc[-2]
    current_fast = fast.iloc[-1]
    current_slow = slow.iloc[-1]

    buy_cross = (
        previous_fast <= previous_slow
        and current_fast > current_slow
    )

    sell_cross = (
        previous_fast >= previous_slow
        and current_fast < current_slow
    )

    if not buy_cross and not sell_cross:
        print("No fresh MA crossover on the latest completed M5 candle.")
        return None

    direction = "BUY" if buy_cross else "SELL"

    high = m5["High"]
    low = m5["Low"]
    previous_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    atr = tr.rolling(14).mean().iloc[-1]
    entry = float(close.iloc[-1])

    if pd.isna(atr) or atr <= 0:
        print("Unable to calculate ATR.")
        return None

    # Check the M15 trend for context, not as a signal blocker
    score = 60
    trend_text = "M15 trend unavailable"

    if m15 is not None:
        m15_close = m15["Close"]
        m15_fast = m15_close.rolling(9).mean().iloc[-1]
        m15_slow = m15_close.rolling(21).mean().iloc[-1]

        if m15_fast > m15_slow:
            trend_text = "M15 bullish"
            if direction == "BUY":
                score = 80
        elif m15_fast < m15_slow:
            trend_text = "M15 bearish"
            if direction == "SELL":
                score = 80
        else:
            trend_text = "M15 neutral"

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

    return (
        f"🟡 XAUUSD {direction}\n\n"
        f"📍 Entry: {entry:.2f}\n"
        f"🛑 Stop Loss: {sl:.2f}\n"
        f"🎯 TP1: {tp1:.2f}\n"
        f"🎯 TP2: {tp2:.2f}\n"
        f"🎯 TP3: {tp3:.2f}\n\n"
        f"⏱️ Timeframe: M5\n"
        f"📈 Strategy: MA 9/21 Crossover\n"
        f"📊 {trend_text}\n"
        f"💪 Setup score: {score}/100\n\n"
        f"⚠️ Score is not a win probability. "
        f"GC=F futures prices can differ from your broker's XAUUSD. "
        f"Verify prices before trading."
    )


def main():
    signal = calculate_signal()

    if not signal:
        print("No signal sent on this run.")
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
    print("Signal sent successfully!")


if __name__ == "__main__":
    main()
