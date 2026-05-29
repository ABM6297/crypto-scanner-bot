import os
import requests
import pandas as pd
import ta
from datetime import datetime

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")

symbol = "BTCUSDT"
interval = "5m"
limit = 100

url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
data = requests.get(url).json()

df = pd.DataFrame(data)

df = df.iloc[:, :6]
df.columns = ["time", "open", "high", "low", "close", "volume"]

df["close"] = df["close"].astype(float)
df["high"] = df["high"].astype(float)
df["low"] = df["low"].astype(float)

df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

macd = ta.trend.MACD(df["close"])
df["macd"] = macd.macd()
df["signal"] = macd.macd_signal()

last = df.iloc[-1]

message = f"""
📊 Crypto Scanner
🕒 {datetime.utcnow()}

💰 BTCUSDT
Price: {last['close']}
RSI: {round(last['rsi'],2)}
"""

signal = False

if last["rsi"] < 35 and last["macd"] > last["signal"]:
    entry = last["close"]
    sl = round(entry * 0.985, 2)
    tp = round(entry * 1.03, 2)

    message += f"""

🟢 BUY SIGNAL
Entry: {entry}
SL: {sl}
TP: {tp}
"""
    signal = True

elif last["rsi"] > 65 and last["macd"] < last["signal"]:
    entry = last["close"]
    sl = round(entry * 1.015, 2)
    tp = round(entry * 0.97, 2)

    message += f"""

🔴 SELL SIGNAL
Entry: {entry}
SL: {sl}
TP: {tp}
"""
    signal = True

if not signal:
    message += "\n❌ No Signal"

requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    data={"chat_id": CHAT_ID, "text": message}
)

print(message)
