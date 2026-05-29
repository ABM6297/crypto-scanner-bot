import os
import requests
import pandas as pd
import ta
import time
from datetime import datetime

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
CMC_API_KEY = os.getenv("CMC_API_KEY")

TOP_LIMIT = 100

def get_top_coins():


url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

headers = {
    "X-CMC_PRO_API_KEY": CMC_API_KEY
}

params = {
    "start": 1,
    "limit": TOP_LIMIT,
    "convert": "USD"
}

r = requests.get(url, headers=headers, params=params)
data = r.json()

if "data" not in data:
    print("CMC ERROR:", data)
    return []

coins = []

for c in data["data"]:

    symbol = c["symbol"]

    if symbol.isalpha():
        coins.append(symbol + "USDT")

print(f"Loaded {len(coins)} coins")

return coins
```

def get_data(symbol):

```
try:

    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=120"

    r = requests.get(url, timeout=10)

    data = r.json()

    if not isinstance(data, list):
        print(f"{symbol} invalid data")
        return None

    df = pd.DataFrame(data)

    df = df.iloc[:, :6]

    df.columns = [
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["volume"] = df["volume"].astype(float)

    return df

except Exception as e:

    print(f"{symbol} DATA ERROR:", e)

    return None
```

def market_regime(df):

```
ma20 = df["close"].rolling(20).mean()
ma50 = df["close"].rolling(50).mean()

trend_strength = abs(ma20.iloc[-1] - ma50.iloc[-1])

atr_value = (
    df["high"] - df["low"]
).rolling(14).mean().iloc[-1]

if trend_strength > atr_value:
    return "TREND"

elif atr_value > trend_strength * 1.5:
    return "VOLATILE"

else:
    return "RANGE"
```

def score_signal(df):

```
rsi = ta.momentum.RSIIndicator(
    df["close"],
    window=14
).rsi().iloc[-1]

macd = ta.trend.MACD(df["close"])

macd_val = macd.macd().iloc[-1]
macd_sig = macd.macd_signal().iloc[-1]

price = df["close"].iloc[-1]

ma20 = df["close"].rolling(20).mean().iloc[-1]

avg_volume = df["volume"].rolling(20).mean().iloc[-1]
current_volume = df["volume"].iloc[-1]

score = 0

if rsi < 35:
    score += 2

elif rsi > 65:
    score -= 2

if macd_val > macd_sig:
    score += 2

else:
    score -= 2

if price > ma20:
    score += 1

else:
    score -= 1

if current_volume > avg_volume * 1.5:
    score += 1

print(
    f"RSI={round(rsi,2)} | "
    f"MACD={round(macd_val,4)} | "
    f"SCORE={score}"
)

return score, rsi
```

def atr(df):

```
tr = pd.concat([
    df["high"] - df["low"],
    abs(df["high"] - df["close"].shift()),
    abs(df["low"] - df["close"].shift())
], axis=1).max(axis=1)

return tr.rolling(14).mean().iloc[-1]
```

def analyze(df, symbol):

```
regime = market_regime(df)

score, rsi = score_signal(df)

price = df["close"].iloc[-1]

direction = None

if score >= 2:
    direction = "BUY"

elif score <= -2:
    direction = "SELL"

if not direction:
    print(f"{symbol} rejected")
    return None

a = atr(df)

if regime == "TREND":

    sl_mult = 1.5
    tp_mult = 3.0

elif regime == "RANGE":

    sl_mult = 1.2
    tp_mult = 2.0

else:

    sl_mult = 2.0
    tp_mult = 2.5

if direction == "BUY":

    sl = price - a * sl_mult
    tp = price + a * tp_mult

else:

    sl = price + a * sl_mult
    tp = price - a * tp_mult

rr = abs(tp - price) / abs(price - sl)

confidence = min(
    95,
    50 + abs(score) * 10
)

print(
    f"SIGNAL: {symbol} | "
    f"{direction} | "
    f"SCORE={score}"
)

return {
    "symbol": symbol,
    "direction": direction,
    "entry": round(price, 6),
    "sl": round(sl, 6),
    "tp": round(tp, 6),
    "rr": round(rr, 2),
    "score": score,
    "rsi": round(rsi, 2),
    "regime": regime,
    "confidence": confidence
}
```

def main():

```
coins = get_top_coins()

results = []

now = datetime.utcnow()

print("Scanner started...")

for symbol in coins:

    try:

        print(f"\nChecking {symbol}")

        time.sleep(0.08)

        df = get_data(symbol)

        if df is None:
            continue

        res = analyze(df, symbol)

        if res:
            results.append(res)

    except Exception as e:

        print(f"{symbol} ANALYZE ERROR:", e)

results = sorted(
    results,
    key=lambda x: abs(x["score"]),
    reverse=True
)

top = results[:5]

if not top:

    msg = f"""
```

❌ No High-Probability Signal

🕒 {now}
"""

```
else:

    msg = f"""
```

🏛 INSTITUTIONAL TRADING ENGINE v6

🕒 {now}

"""

```
    for r in top:

        msg += f"""
```

💰 {r['symbol']}
📊 {r['direction']}

🔥 Confidence: {r['confidence']}%

📈 Regime: {r['regime']}
📉 RSI: {r['rsi']}
🧠 Score: {r['score']}

💵 Entry: {r['entry']}
🛑 SL: {r['sl']}
🎯 TP: {r['tp']}

⚖ RR: 1:{r['rr']}

---

"""

```
requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    data={
        "chat_id": CHAT_ID,
        "text": msg
    }
)

print(msg)
```

if **name** == "**main**":
main()
