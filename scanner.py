import os
import requests
import pandas as pd
import ta

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

BASE_URL = "https://api.binance.com/api/v3/klines"

BLACKLIST = {"USDT", "USDC", "DAI", "FDUSD", "PYUSD"}


# =========================
# TELEGRAM
# =========================
def send_telegram(message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("TELEGRAM CONFIG MISSING")
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, json={
            "chat_id": TG_CHAT_ID,
            "text": message
        }, timeout=15)
    except Exception as e:
        print("TG ERROR:", e)


# =========================
# TOP COINS FROM BINANCE
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
# GET OHLC DATA
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
# ANALYZE (V3 ENGINE)
# =========================
def analyze(df):
    close = df["close"]
    price = float(close.iloc[-1])

    # ===== Indicators =====
    ema20 = ta.trend.EMAIndicator(close, 20).ema_indicator()
    ema50 = ta.trend.EMAIndicator(close, 50).ema_indicator()

    rsi = ta.momentum.RSIIndicator(close, 14).rsi()

    macd = ta.trend.MACD(close)
    macd_line = macd.macd()
    signal_line = macd.macd_signal()

    adx = ta.trend.ADXIndicator(
        df["high"], df["low"], df["close"], window=14
    ).adx()

    atr_ind = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14
    )

    atr_value = float(atr_ind.average_true_range().iloc[-1])

    adx_value = float(adx.iloc[-1])
    rsi_value = float(rsi.iloc[-1])

    # =========================
    # MARKET REGIME
    # =========================
    if adx_value >= 25:
        regime = "STRONG_TREND"
    elif adx_value >= 18:
        regime = "TREND"
    else:
        regime = "RANGE"

    # =========================
    # RANGE FILTER (NO TRADE)
    # =========================
    if regime == "RANGE":
        return {
            "direction": "NEUTRAL",
            "score": -999,
            "price": price,
            "trend": regime
        }

    # =========================
    # SCORE ENGINE
    # =========================
    score = 0

    # Trend
    if ema20.iloc[-1] > ema50.iloc[-1]:
        score += 4
    else:
        score -= 4

    # MACD
    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        score += 3
    else:
        score -= 3

    # RSI logic
    if 45 <= rsi_value <= 65:
        score += 3
    elif rsi_value > 75:
        score -= 4
    elif rsi_value < 30:
        score += 2

    # Breakout
    high20 = df["high"].rolling(20).max().shift(1).iloc[-1]
    low20 = df["low"].rolling(20).min().shift(1).iloc[-1]

    if price > high20:
        score += 4
    elif price < low20:
        score -= 4

    # Volume confirmation
    vol_avg = df["volume"].rolling(20).mean().iloc[-1]
    vol_now = df["volume"].iloc[-1]

    if vol_now > vol_avg:
        score += 2
    else:
        score -= 1

    # =========================
    # WEAK TREND FILTER
    # =========================
    if regime == "TREND" and abs(score) < 8:
        return {
            "direction": "NEUTRAL",
            "score": score,
            "price": price,
            "trend": regime
        }

    # =========================
    # FINAL DECISION
    # =========================
    direction = "NEUTRAL"

    if score >= 9:
        direction = "BUY"
    elif score <= -9:
        direction = "SELL"

    entry = price
    stop = tp1 = tp2 = 0

    if direction == "BUY":
        stop = entry - (atr_value * 1.6)
        risk = entry - stop
        tp1 = entry + risk * 2
        tp2 = entry + risk * 3

    elif direction == "SELL":
        stop = entry + (atr_value * 1.6)
        risk = stop - entry
        tp1 = entry - risk * 2
        tp2 = entry - risk * 3

    return {
        "price": round(price, 6),
        "score": int(score),
        "direction": direction,
        "rsi": round(rsi_value, 2),
        "atr": round(atr_value, 6),
        "trend": regime,
        "entry": round(entry, 6),
        "stop": round(stop, 6),
        "tp1": round(tp1, 6),
        "tp2": round(tp2, 6)
    }


# =========================
# FORMAT MESSAGE
# =========================
def format_msg(symbol, r):
    return f"""
🚀 {symbol} (V3)

Trend: {r.get('trend')}
Direction: {r['direction']}
Score: {r['score']}

Entry: {r['entry']}
Stop Loss: {r['stop']}
TP1: {r['tp1']}
TP2: {r['tp2']}

RSI: {r['rsi']}
ATR: {r['atr']}
"""


# =========================
# MAIN
# =========================
def main():
    print("V3 SCANNER STARTED")

    symbols = get_top_symbols()
    print("SYMBOLS:", symbols)

    results = []

    for s in symbols:
        df = get_data(s)

        if df is None or len(df) < 150:
            continue

        res = analyze(df)
        res["symbol"] = s
        results.append(res)

    # sort
    results.sort(key=lambda x: x["score"], reverse=True)

    signals = [r for r in results if r["direction"] != "NEUTRAL"]

    if not signals:
        print("NO SIGNAL")
        send_telegram("📊 V3: NO SIGNAL")
        return

    best = signals[0]

    msg = format_msg(best["symbol"], best)
    print(msg)

    send_telegram(msg)


if __name__ == "__main__":
    main()
