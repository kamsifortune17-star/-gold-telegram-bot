import os
import json
import base64
import requests
import yfinance as yf
import pandas as pd

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GH_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
BRANCH = "main"

API = f"https://api.github.com/repos/{REPO}/contents/last_signal.json"

HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}


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

        # Exclude the currently forming candle.
        if len(df) > 1:
            df = df.iloc[:-1]

        return df if len(df) >= 30 else None

    except Exception as e:
        print(f"Price data error: {e}")
        return None


def read_last_signal():
    response = requests.get(
        API,
        headers=HEADERS,
        params={"ref": BRANCH},
        timeout=20
    )

    if response.status_code == 404:
        return None, None

    response.raise_for_status()
    item = response.json()

    content = base64.b64decode(item["content"]).decode()
    return json.loads(content), item["sha"]


def save_last_signal(signal, sha):
    content = base64.b64encode(
        json.dumps(signal).encode()
    ).decode()

    payload = {
        "message": "Save last processed gold signal",
        "content": content,
        "branch": BRANCH
    }

    if sha:
        payload["sha"] = sha

    response = requests.put(
        API,
        headers=HEADERS,
        json=payload,
        timeout=20
    )

    response.raise_for_status()


def calculate_signal():
    m5 = get_data("5m")
    m15 = get_data("15m")

    if m5 is None:
        print("M5 gold price data unavailable.")
        return None

    close = m5["Close"]
    fast = close.rolling(9).mean()
    slow = close.rolling(21).mean()

    # Search the four most recent completed M5 candles.
    start = max(1, len(m5) - 4)
    crossover = None

    for i in range(start, len(m5)):
        buy = (
            fast.iloc[i - 1] <= slow.iloc[i - 1]
            and fast.iloc[i] > slow.iloc[i]
        )

        sell = (
            fast.iloc[i - 1] >= slow.iloc[i - 1]
            and fast.iloc[i] < slow.iloc[i]
        )

        if buy or sell:
            crossover = (
                i,
                "BUY" if buy else "SELL"
            )

    if crossover is None:
        print("No recent MA 9/21 crossover found.")
        return None

    i, direction = crossover
    candle_time = m5.index[i].isoformat()

    signal_id = f"{candle_time}_{direction}"

    last_signal, sha = read_last_signal()

    if last_signal and last_signal.get("id") == signal_id:
        print("This crossover was already processed.")
        return None

    high = m5["High"]
    low = m5["Low"]
    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    atr = true_range.rolling(14).mean().iloc[i]
    entry = float(close.iloc[i])

    if pd.isna(atr) or atr <= 0:
        print("Unable to calculate ATR.")
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

    score = 60
    trend = "Unavailable"

    if m15 is not None:
        c15 = m15["Close"]
        ma9 = c15.rolling(9).mean().iloc[-1]
        ma21 = c15.rolling(21).mean().iloc[-1]

        if ma9 > ma21:
            trend = "Bullish"
            if direction == "BUY":
                score = 80
        elif ma9 < ma21:
            trend = "Bearish"
            if direction == "SELL":
                score = 80
        else:
            trend = "Neutral"

    message = (
        f"🟡 XAUUSD {direction}\n\n"
        f"📍 Entry: {entry:.2f}\n"
        f"🛑 Stop Loss: {sl:.2f}\n"
        f"🎯 TP1: {tp1:.2f}\n"
        f"🎯 TP2: {tp2:.2f}\n"
        f"🎯 TP3: {tp3:.2f}\n\n"
        f"⏱️ Timeframe: M5 + M15\n"
        f"📈 Strategy: MA 9/21 Crossover\n"
        f"📊 M15 Trend: {trend}\n"
        f"💪 Setup score: {score}/100\n\n"
        f"⚠️ Score is not a win probability. "
        f"GC=F futures prices may differ from broker XAUUSD. "
        f"Verify prices before trading."
    )

    return {
        "id": signal_id,
        "message": message
    }, sha


def main():
    result = calculate_signal()

    if result is None:
        print("No new signal to send.")
        return

    signal, sha = result

    # Save the crossover first to prevent duplicate alerts.
    save_last_signal({"id": signal["id"]}, sha)

    response = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": signal["message"]
        },
        timeout=20
    )

    response.raise_for_status()
    print("Signal sent successfully!")


if __name__ == "__main__":
    main()
