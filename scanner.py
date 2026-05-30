import os
import sys
import requests
import pandas as pd
import ta
import time
from datetime import datetime

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
CMC_API_KEY = os.getenv("CMC_API_KEY")

TOP_LIMIT = 80


def get_top_coins():

    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": str(CMC_API_KEY).strip()
    }

    print("HEADER KEY LENGTH =", len(str(CMC_API_KEY)))

    params = {
        "start": 1,
        "limit": TOP_LIMIT,
        "convert": "USD"
    }

    r = requests.get(
        print("REQUEST HEADERS:", headers)
        print("STATUS:", r.status_code)
        print("BODY:", r.text[:500])
        url,
        timeout=10,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    print("STATUS:", r.status_code)
    print("RESPONSE:", r.text[:300])

    data = r.json()

    if "data" not in data:
        print("CMC ERROR:", data)
        return []

    coins = []

    for c in data["data"]:
        symbol = c["symbol"]

        if symbol.isalpha():
            coins.append(symbol + "USDT")

    return coins


def get_data(symbol):

    try:

        symbol = symbol.replace("USDT", "")

        url = (
            f"https://api.bybit.com/v5/market/kline"
            f"?category=linear"
            f"&symbol={symbol}USDT"
            f"&interval=15"
            f"&limit=150"
        )

        r = requests.get(url, timeout=10)
        data = r.json()

        if "result" not in data or "list" not in data["result"]:
            print(f"{symbol} -> BYBIT ERROR")
            return None

        rows = data["result"]["list"]

        if not rows:
            return None

        df = pd.DataFrame(rows)
        df = df.iloc[:, :6]

        df.columns = [
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]

        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)

        df = df.iloc[::-1].reset_index(drop=True)

        print(f"{symbol} -> DATA OK")

        return df

    except Exception as e:

        print(f"{symbol} ERROR: {e}")
        return None


def calculate_atr(df):

    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)

    return tr.rolling(14).mean().iloc[-1]


def analyze(df, symbol):

    close = df["close"]
    price = close.iloc[-1]

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]

    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1]
    ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1]

    macd = ta.trend.MACD(close)
    macd_line = macd.macd().iloc[-1]
    macd_signal = macd.macd_signal().iloc[-1]

    current_volume = df["volume"].iloc[-1]
    avg_volume = df["volume"].rolling(20).mean().iloc[-1]

    score = 0

    if ema20 > ema50:
        score += 2
    else:
        score -= 2

    if macd_line > macd_signal:
        score += 2
    else:
        score -= 2

    if 45 <= rsi <= 70:
        score += 1
    elif 30 <= rsi < 45:
        score += 2
    elif rsi > 75:
        score -= 3

    if current_volume > avg_volume * 1.3:
        score += 1

    direction = None

    if score >= 5:
        direction = "BUY"
    elif score <= -5:
        direction = "SELL"

    if not direction:
        return None

    atr = calculate_atr(df)

    if direction == "BUY":
        sl = price - atr * 1.5
        tp1 = price + atr * 2
        tp2 = price + atr * 3.5
    else:
        sl = price + atr * 1.5
        tp1 = price - atr * 2
        tp2 = price - atr * 3.5

    rr = abs(tp2 - price) / abs(price - sl)

    confidence = min(95, 55 + abs(score) * 6)

    return {
        "symbol": symbol,
        "direction": direction,
        "entry": round(price, 6),
        "sl": round(sl, 6),
        "tp1": round(tp1, 6),
        "tp2": round(tp2, 6),
        "rr": round(rr, 2),
        "score": score,
        "rsi": round(rsi, 2),
        "confidence": confidence
    }


def main():
    print("CMC_API_KEY =", repr(CMC_API_KEY))
    print("SCANNER STARTED")

    manual_mode = len(sys.argv) > 1 and sys.argv[1] == "manual"

    coins = get_top_coins()
    results = []
    now = datetime.utcnow()

    for symbol in coins:

        try:

            print(f"CHECKING {symbol}")

            time.sleep(0.1)

            df = get_data(symbol)

            if df is None:
                continue

            result = analyze(df, symbol)

            if result:
                results.append(result)

        except Exception as e:

            print(symbol, e)

    results = sorted(
        results,
        key=lambda x: abs(x["score"]),
        reverse=True
    )

    top = results[:5]

    if not manual_mode and not top:
        print("NO SIGNAL")
        return

    if not top:

        msg = f"❌ NO SIGNAL\n\n🕒 {now}"

    else:

        msg = f"🏛 ELITE CRYPTO SCANNER\n\n🕒 {now}\n\n"

        for r in top:

            msg += f"""
💰 {r['symbol']}
📊 {r['direction']}

🔥 Confidence: {r['confidence']}%
🧠 Score: {r['score']}
📉 RSI: {r['rsi']}

💵 Entry: {r['entry']}
🛑 Stop Loss: {r['sl']}
🎯 TP1: {r['tp1']}
🚀 TP2: {r['tp2']}

⚖ Risk/Reward: 1:{r['rr']}

------------------------
"""

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": msg
        }
    )

    print(msg)


if __name__ == "__main__":
    main()
