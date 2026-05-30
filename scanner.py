import os
import requests
import pandas as pd
import ta

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")


# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("TELEGRAM CONFIG MISSING")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": msg},
            timeout=15
        )
    except:
        pass


# =========================
# SYMBOLS (STATIC SAFE LIST)
# =========================
def get_symbols():
    return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]


# =========================
# COINGECKO DATA (MAIN SOURCE)
# =========================
def fetch_coingecko(symbol):
    try:
        coin = symbol.replace("USDT", "").lower()

        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
        params = {"vs_currency": "usd", "days": 3, "interval": "hourly"}

        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        prices = data.get("prices", [])

        if len(prices) < 50:
            return None

        df = pd.DataFrame(prices, columns=["time", "close"])

        # 🔥 fake OHLC (but usable for TA)
        df["open"] = df["close"].shift(1).fillna(df["close"])
        df["high"] = df["close"] * 1.002
        df["low"] = df["close"] * 0.998
        df["volume"] = 1

        return df

    except:
        return None


# =========================
# CRYPTOCOMPARE (FALLBACK)
# =========================
def fetch_crypto_compare(symbol):
    try:
        coin = symbol.replace("USDT", "")

        url = "https://min-api.cryptocompare.com/data/v2/histohour"
        params = {"fsym": coin, "tsym": "USD", "limit": 200}

        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if data.get("Response") != "Success":
            return None

        rows = data["Data"]["Data"]

        df = pd.DataFrame(rows)

        df = df.rename(columns={"volumefrom": "volume"})

        return df

    except:
        return None


# =========================
# UNIFIED DATA LAYER
# =========================
def get_data(symbol):
    df = fetch_coingecko(symbol)

    if df is None:
        df = fetch_crypto_compare(symbol)

    return df


# =========================
# ANALYZE ENGINE (V3 LOGIC)
# =========================
def analyze(df):
    if df is None or len(df) < 60:
        return None

    close = df["close"]
    price = float(close.iloc[-1])

    ema20 = ta.trend.EMAIndicator(close, 20).ema_indicator()
    ema50 = ta.trend.EMAIndicator(close, 50).ema_indicator()

    rsi = ta.momentum.RSIIndicator(close, 14).rsi()

    macd = ta.trend.MACD(close)
    macd_line = macd.macd()
    signal_line = macd.macd_signal()

    atr = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], 14
    ).average_true_range()

    atr_v = float(atr.iloc[-1])
    rsi_v = float(rsi.iloc[-1])

    # =========================
    # SCORE ENGINE
    # =========================
    score = 0

    if ema20.iloc[-1] > ema50.iloc[-1]:
        score += 3
    else:
        score -= 3

    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        score += 2
    else:
        score -= 2

    if 45 <= rsi_v <= 65:
        score += 2
    elif rsi_v > 75:
        score -= 3
    elif rsi_v < 30:
        score += 2

    high20 = df["close"].rolling(20).max().iloc[-1]
    low20 = df["close"].rolling(20).min().iloc[-1]

    if price > high20:
        score += 3
    elif price < low20:
        score -= 3

    vol_avg = df["volume"].rolling(20).mean().iloc[-1]
    vol_now = df["volume"].iloc[-1]

    if vol_now > vol_avg:
        score += 1

    # =========================
    # DECISION
    # =========================
    direction = "NEUTRAL"

    if score >= 9:
        direction = "BUY"
    elif score <= -9:
        direction = "SELL"

    entry = price
    stop = tp1 = tp2 = 0

    if direction == "BUY":
        stop = entry - atr_v * 1.5
        risk = entry - stop
        tp1 = entry + risk * 2
        tp2 = entry + risk * 3

    elif direction == "SELL":
        stop = entry + atr_v * 1.5
        risk = stop - entry
        tp1 = entry - risk * 2
        tp2 = entry - risk * 3

    return {
        "price": round(price, 6),
        "score": int(score),
        "direction": direction,
        "rsi": round(rsi_v, 2),
        "atr": round(atr_v, 6),
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
🚀 {symbol} (V3.4 NO BINANCE)

Direction: {r['direction']}
Score: {r['score']}

Entry: {r['entry']}
Stop: {r['stop']}
TP1: {r['tp1']}
TP2: {r['tp2']}

RSI: {r['rsi']}
ATR: {r['atr']}
"""


# =========================
# MAIN
# =========================
def main():
    print("V3.4 FULL STABLE STARTED")

    symbols = get_symbols()

    results = []

    for s in symbols:
        df = get_data(s)

        r = analyze(df)

        if r is None:
            continue

        r["symbol"] = s
        results.append(r)

    if not results:
        send_telegram("📊 V3.4: NO DATA (FALLBACK ACTIVE)")
        print("NO DATA")
        return

    results.sort(key=lambda x: x["score"], reverse=True)

    signals = [r for r in results if r["direction"] != "NEUTRAL"]

    if not signals:
        msg = "📊 V3.4: NO SIGNAL"
        print(msg)
        send_telegram(msg)
        return

    best = signals[0]

    msg = format_msg(best["symbol"], best)

    print(msg)
    send_telegram(msg)


if __name__ == "__main__":
    main()
