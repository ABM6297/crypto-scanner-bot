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
INITIAL_BALANCE = 1000

balance = INITIAL_BALANCE


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
# MARKET DATA
# ---------------------------
def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=120"
    r = requests.get(url)
    data = r.json()

    if not isinstance(data, list):
        return None

    df = pd.DataFrame(data)
    df = df.iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "volume"]

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)

    return df


# ---------------------------
# MARKET REGIME DETECTION
# ---------------------------
def market_regime(df):

    ma20 = df["close"].rolling(20).mean()
    ma50 = df["close"].rolling(50).mean()

    trend_strength = abs(ma20.iloc[-1] - ma50.iloc[-1])

    atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]

    if trend_strength > atr:
        return "TREND"
    elif atr > trend_strength * 1.5:
        return "VOLATILE"
    else:
        return "RANGE"


# ---------------------------
# FEATURE ENGINEERING
# ---------------------------
def score_signal(df):

    rsi = ta.momentum.RSIIndicator(df["close"], 14).rsi().iloc[-1]

    macd = ta.trend.MACD(df["close"])
    macd_val = macd.macd().iloc[-1]
    macd_sig = macd.macd_signal().iloc[-1]

    price = df["close"].iloc[-1]
    ma20 = df["close"].rolling(20).mean().iloc[-1]

    score = 0

    # RSI logic
    if rsi < 30:
        score += 2
    elif rsi > 70:
        score -= 2

    # MACD logic
    if macd_val > macd_sig:
        score += 2
    else:
        score -= 2

    # trend logic
    if price > ma20:
        score += 1
    else:
        score -= 1

    return score, rsi


# ---------------------------
# ATR RISK MODEL
# ---------------------------
def atr(df):
    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)

    return tr.rolling(14).mean().iloc[-1]


# ---------------------------
# ANALYZE
# ---------------------------
def analyze(df, symbol):

    regime = market_regime(df)
    score, rsi = score_signal(df)

    price = df["close"].iloc[-1]

    direction = None

    if score >= 3:
        direction = "BUY"
    elif score <= -3:
        direction = "SELL"

    if not direction:
        return None

    a = atr(df)

    # adaptive risk based on regime
    if regime == "TREND":
        sl_mult, tp_mult = 1.5, 3.0
    elif regime == "RANGE":
        sl_mult, tp_mult = 1.2, 2.0
    else:
        sl_mult, tp_mult = 2.0, 2.5

    sl = price - a * sl_mult if direction == "BUY" else price + a * sl_mult
    tp = price + a * tp_mult if direction == "BUY" else price - a * tp_mult

    rr = abs(tp - price) / abs(price - sl)

    return {
        "symbol": symbol,
        "direction": direction,
        "entry": price,
        "sl": round(sl, 6),
        "tp": round(tp, 6),
        "rr": round(rr, 2),
        "score": score,
        "rsi": round(rsi, 2),
        "regime": regime
    }


# ---------------------------
# MAIN ENGINE
# ---------------------------
def main():

    coins = get_top_coins()
    results = []

    now = datetime.utcnow()

    for i, symbol in enumerate(coins):

        time.sleep(0.08)

        df = get_data(symbol)
        if df is None:
            continue

        res = analyze(df, symbol)

        if res:
            results.append(res)

    results = sorted(results, key=lambda x: abs(x["score"]), reverse=True)

    top = results[:5]

    if not top:
        msg = f"❌ No Institutional-Grade Signal\n🕒 {now}"
    else:
        msg = f"🏛 INSTITUTIONAL TRADING ENGINE v5\n🕒 {now}\n\n"

        for r in top:
            msg += f"""
💰 {r['symbol']}
📊 {r['direction']}
Regime: {r['regime']}
Score: {r['score']}
RSI: {r['rsi']}
Entry: {r['entry']}
SL: {r['sl']}
TP: {r['tp']}
RR: 1:{r['rr']}
--------------------
"""

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

    print(msg)


if __name__ == "__main__":
    main()
