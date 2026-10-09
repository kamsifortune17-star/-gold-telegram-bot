import os
import requests
import yfinance as yf

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def get_signal():
    data = yf.download(
        "XAUUSD=X",
        period="5d",
        interval="15m",
        progress=False
    )

    if data.empty:
        return "⚠️ Gold price data is unavailable."

    close = data["Close"].dropna()

    fast = close.rolling(9).mean()
    slow = close.rolling(21).mean()

    if fast.iloc[-1] > slow.iloc[-1]:
        return "🟢 XAUUSD: BUY BIAS\nTimeframe: M15"
    elif fast.iloc[-1] < slow.iloc[-1]:
        return "🔴 XAUUSD: SELL BIAS\nTimeframe: M15"

    return "⏳ No clear signal."

if __name__ == "__main__":
    print(get_signal())
