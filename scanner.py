import os
import requests
import pandas as pd
import ta
from datetime import datetime

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

BASE_URL = "https://api.binance.com/api/v3/klines"

BLACKLIST = {"USDT", "USDC", "DAI", "FDUSD", "PYUSD"}

LAST_SIGNAL_FILE = "last_signal.txt"


# =========================
# TELEGRAM
# =========================
def send_telegram(message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("TELEGRAM CONFIG MISSING")
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": TG_CHAT_ID,
        "text": message
    }, timeout=15)


# =========================
# TOP COINS (BINANCE ONLY)
# =========================
def get_top_symbols():
    url = "https://api.binance.com/api/v3/ticker/24hr"

    try:
        r = requests.get(url, timeout=15)
        data = r.json()

        symbols = []

        for item in data:
            symbol = item["symbol"]

            if symbol.endswith("USDT") and not any(b in symbol for b in BLACKLIST):
                symbols.append(symbol)

        return symbols[:10]

    except Exception as e:
        print("SYMBOL ERROR:", e)
        return []


# =========================
# GET DATA
# =========================
def get_data(symbol):
    try:
        params = {
            "symbol": symbol,
            "interval": "1h",
            "limit": 200
        }

        r = requests.get(BASE_URL, params=params, timeout=15)
        data = r.json()

        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tbb","tbq","ignore"
        ])

        df = df.astype({
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "volume": float
        })

        return df

    except Exception as e:
        print(symbol, "DATA ERROR:", e)
        return None


# =========================
# ATR
# =========================
def atr(df):
    return ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14
    ).average_true_range().iloc[-1]


# =========================
# ANALYSIS (PRO VERSION)
# =========================
def analyze(df):
    close = df["close"]
    price = float(close.iloc[-1])

    ema20 = ta.trend.EMAIndicator(close, 20).ema_indicator()
    ema50 = ta.trend.EMAIndicator(close, 50).ema_indicator()

    rsi = ta.momentum.RSIIndicator(close, 14).rsi()

    macd = ta.trend.MACD(close)
    macd_line = macd.macd()
    signal_line = macd.macd_signal()

    score = 0

    # Trend Strength (IMPORTANT)
    if ema20.iloc[-1] > ema50.iloc[-1]:
        score += 4
    else:
        score -= 4

    # MACD
    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        score += 3
    else:
        score -= 3

    # RSI filtering (stricter)
    r = float(rsi.iloc[-1])

    if 45 <= r <= 65:
        score += 3
    elif r > 75:
        score -= 3
    elif r < 30:
        score += 1

    # Breakout (strong filter)
    high20 = df["high"].rolling(20).max().shift(1).iloc[-1]
    low20 = df["low"].rolling(20).min().shift(1).iloc[-1]

    if price > high20:
        score += 4
    elif price < low20:
        score -= 4

    a = float(atr(df))

    direction = "NEUTRAL"

    if score >= 6:
        direction = "BUY"
    elif score <= -6:
        direction = "SELL"

    entry = price
    stop = tp1 = tp2 = 0

    if direction == "BUY":
        stop = entry - (a * 1.5)
        risk = entry - stop
        tp1 = entry + risk * 2
        tp2 = entry + risk * 3

    elif direction == "SELL":
        stop = entry + (a * 1.5)
        risk = stop - entry
        tp1 = entry - risk * 2
        tp2 = entry - risk * 3

    return {
        "price": price,
        "score": score,
        "direction": direction,
        "rsi": r,
        "atr": a,
        "entry": entry,
        "stop": stop,
        "tp1": tp1,
        "tp2": tp2
    }


# =========================
# ANTI-SPAM SYSTEM
# =========================
def load_last_signal():
    if not os.path.exists(LAST_SIGNAL_FILE):
        return None

    return open(LAST_SIGNAL_FILE, "r").read().strip()


def save_last_signal(symbol):
    with open(LAST_SIGNAL_FILE, "w") as f:
        f.write(symbol)


# =========================
# FORMAT MESSAGE
# =========================
def format_msg(symbol, r):
    return f"""
🚀 {symbol}

Direction: {r['direction']}
Score: {r['score']}

Entry: {round(r['entry'], 6)}
Stop: {round(r['stop'], 6)}
TP1: {round(r['tp1'], 6)}
TP2: {round(r['tp2'], 6)}

RSI: {round(r['rsi'], 2)}
ATR: {round(r['atr'], 6)}
"""


# =========================
# MAIN
# =========================
def main():
    print("PRO SCANNER STARTED")

    symbols = get_top_symbols()
    print("SYMBOLS:", symbols)

    results = []

    for s in symbols:
        df = get_data(s)
        if df is None:
            continue

        res = analyze(df)
        res["symbol"] = s
        results.append(res)

    # sort best signal
    results.sort(key=lambda x: x["score"], reverse=True)

    signals = [r for r in results if r["direction"] != "NEUTRAL"]

    if not signals:
        print("NO SIGNAL")
        send_telegram("📊 NO SIGNAL (PRO MODE)")
        return

    best = signals[0]

    last = load_last_signal()

    # جلوگیری از تکرار
    if last == best["symbol"] + best["direction"]:
        print("DUPLICATE SIGNAL BLOCKED")
        return

    msg = format_msg(best["symbol"], best)
    print(msg)

    send_telegram(msg)
    save_last_signal(best["symbol"] + best["direction"])


if __name__ == "__main__":
    main()
