import os
import requests
import pandas as pd
import ta
from datetime import datetime

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
CMC_API_KEY = os.getenv("CMC_API_KEY")

symbol = "BTC"

url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"

headers = {
    "X-CMC_PRO_API_KEY": CMC_API_KEY
}

params = {
    "symbol": symbol,
    "convert": "USD"
}

resp = requests.get(url, headers=headers, params=params)
data = resp.json()

# 🔴 check API error
if "data" not in data:
    print("CMC ERROR:", data)
    exit()

price = data["data"][symbol]["quote"]["USD"]["price"]

message = f"""
📊 Crypto Scanner (CMC)
🕒 {datetime.utcnow()}

💰 {symbol}/USD
Price: {price}
"""

# --- fake signal logic (همون منطق قبلی ساده) ---
signal = False

# ساده‌سازی: بدون کندل چون CMC OHLC نمی‌دهد
if price % 2 < 1:   # فقط تستی برای سیگنال
    message += "\n🟢 BUY SIGNAL (test)"
    signal = True
else:
    message += "\n🔴 SELL SIGNAL (test)"
    signal = True

requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    data={"chat_id": CHAT_ID, "text": message}
)

print(message)
