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

# ---------------------------
# AI WEIGHTS (adaptive)
# ---------------------------
weights = {
    "rsi": 1.0,
    "macd": 1.0,
    "trend": 1.0
}

# pseudo performance memory (simple learning)
performance = {
    "wins": 0,
    "losses": 0
}

# ---------------------------
# GET TOP COINS
# ---------------------------
def get_top_coins():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
    params = {"start": 1, "limit": TOP_LIMIT, "convert": "USD"}

    r = requests.get(url, headers=headers, params=params)
    data = r.json()

    if "data" not in data:
        return []

    return [c["symbol"] + "USDT" for c in data["data"] if c["symbol"].isalpha()]


# ---------------------------
# GET DATA
# ---------------------------
def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=100"
    r = requests.get(url)
    data = r.json()

    if not isinstance(data, list):
        return None

    df = pd.DataFrame(data)
    df = df.iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "volume"]
    df["close"] = df["close"].astype(float)

    return df


# ---------------------------
# AI ANALYSIS ENGINE
# ---------------------------
def analyze(df):

    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["signal"] = macd.macd_signal()

    last = df.iloc[-1]
    price = last["close"]

    score = 0

    # RSI logic
    if last["rsi"] < 30:
        score += 30 * weights["rsi"]
    elif last["rsi"] > 70:
        score -= 30 * weights["rsi"]

    # MACD logic
    if last["macd"] > last["signal"]:
        score += 25 * weights["macd"]
    else:
        score -= 25 * weights["macd"]

    # trend filter (simple)
    ma = df["close"].rolling(20).mean().iloc[-1]
    if price > ma:
        score += 15 * weights["trend"]
    else:
        score -= 15 * weights["trend"]

    direction = None

    if score >= 40:
        direction = "BUY"
    elif score <= -40:
        direction = "SELL"

    if not direction:
        return None

    # risk management
    sl = price * (0.985 if direction == "BUY" else 1.015)
    tp = price * (1.03 if direction == "BUY" else 0.97)

    rr = abs(tp - price) / abs(price - sl)

    return {
        "entry": price,
        "sl": round(sl, 6),
        "tp": round(tp, 6),
        "rr": round(rr, 2),
        "score": score,
        "direction": direction
    }


# ---------------------------
# AI WEIGHT ADJUSTMENT
# ---------------------------
def update_weights():

    if performance["wins"] + performance["losses"] == 0:
        return

    winrate = performance["wins"] / (performance["wins"] + performance["losses"])

    # adaptive tuning
    if winrate < 0.4:
        weights["rsi"] *= 1.05
        weights["macd"] *= 1.05
    elif winrate > 0.6:
        weights["trend"] *= 1.05


# ---------------------------
# MAIN
# ---------------------------
def main():

    coins = get_top_coins()
    results = []

    now = datetime.utcnow()

    for i, symbol in enumerate(coins):

        time.sleep(0.1)

        df = get_data(symbol)
        if df is None:
            continue

        res = analyze(df)

        if res:
            res["symbol"] = symbol
            results.append(res)

    results = sorted(results, key=lambda x: abs(x["score"]), reverse=True)

    top = results[:5]

    if not top:
        msg = f"❌ No Signal\n🕒 {now}"
    else:
        msg = f"🤖 AI TRADING ENGINE\n🕒 {now}\n\n"

        for r in top:
            msg += f"""
💰 {r['symbol']}
📊 {r['direction']}
Score: {round(r['score'],2)}
Entry: {r['entry']}
SL: {r['sl']}
TP: {r['tp']}
RR: 1:{r['rr']}
------------------
"""

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

    print(msg)


if __name__ == "__main__":
    main()
