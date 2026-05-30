import os
import requests
import pandas as pd
import ta

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

BLACKLIST = {"USDT", "USDC", "DAI", "FDUSD", "PYUSD"}


# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("TELEGRAM CONFIG MISSING")
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, json={
            "chat_id": TG_CHAT_ID,
            "text": msg
        }, timeout=15)
    except Exception as e:
        print("TG ERROR:", e)


# =========================
# SYMBOLS (SAFE BINANCE ONLY)
# =========================
def get_symbols():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10)
        data = r.json()

        if not isinstance(data, list):
            raise Exception("Binance blocked")

        symbols = [
            x["symbol"]
            for x in data
            if isinstance(x, dict)
            and x.get("symbol", "").endswith("USDT")
        ]

        return symbols[:10]

    except:
        # fallback static
        return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]


# =========================
# DATA SOURCE 1: BINANCE
# =========================
def fetch_binance(symbol):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": "1h", "limit": 200}

        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if not isinstance(data, list):
            return None

        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tbb","tbq","ignore"
        ])

        df = df.astype(float)
        return df

    except:
        return None


# =========================
# DATA SOURCE 2: COINGECKO
# =========================
def fetch_coingecko(symbol):
    try:
        coin = symbol.replace("USDT", "").lower()

        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
        params = {"vs_currency": "usd", "days": 2, "interval": "hourly"}

        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        prices = data["prices"]

        df = pd.DataFrame(prices, columns=["time", "close"])
        df["high"] = df["close"]
        df["low"] = df["close"]
        df["open"] = df["close"]
        df["volume"] = 1

        return df

    except:
        return None


# =========================
# DATA SOURCE 3: CRYPTOCOMPARE
# =========================
def fetch_cryptocompare(symbol):
    try:
        coin = symbol.replace("USDT", "")

        url = f"https://min-api.cryptocompare.com/data/v2/histohour"
        params = {"fsym": coin, "tsym": "USD", "limit": 200}

        r = requests.get(url, params=params, timeout=10)
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
# UNIFIED DATA LAYER (ULTRA STABLE)
# =========================
def get_data(symbol):
    df = fetch_binance(symbol)

    if df is None:
        df = fetch_coingecko(symbol)

    if df is None:
        df = fetch_cryptocompare(symbol)

    return df


# =========================
# ANALYSIS (V3 ENGINE)
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

    adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], 14).adx()

    atr = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], 14).average_true_range()

    adx_v = float(adx.iloc[-1])
    rsi_v = float(rsi.iloc[-1])
    atr_v = float(atr.iloc[-1])

    # ===== REGIME =====
    if adx_v < 18:
        return {"direction": "NEUTRAL", "score": -999, "price": price}

    score = 0

    if ema20.iloc[-1] > ema50.iloc[-1]:
        score += 4
    else:
        score -= 4

    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        score += 3
    else:
        score -= 3

    if 45 <= rsi_v <= 65:
        score += 3
    elif rsi_v > 75:
        score -= 4
    elif rsi_v < 30:
        score += 2

    high20 = df["high"].rolling(20).max().iloc[-1]
    low20 = df["low"].rolling(20).min().iloc[-1]

    if price > high20:
        score += 4
    elif price < low20:
        score -= 4

    vol_avg = df["volume"].rolling(20).mean().iloc[-1]
    vol_now = df["volume"].iloc[-1]

    if vol_now > vol_avg:
        score += 2

    direction = "NEUTRAL"

    if score >= 9:
        direction = "BUY"
    elif score <= -9:
        direction = "SELL"

    entry = price

    stop = tp1 = tp2 = 0

    if direction == "BUY":
        stop = entry - atr_v * 1.6
        risk = entry - stop
        tp1 = entry + risk * 2
        tp2 = entry + risk * 3

    elif direction == "SELL":
        stop = entry + atr_v * 1.6
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
🚀 {symbol} (V3.3 ULTRA STABLE)

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
    print("V3.3 ULTRA STABLE STARTED")

    symbols = get_symbols()
    print("SYMBOLS:", symbols)

    results = []

    for s in symbols:
        df = get_data(s)

        if df is None or len(df) < 120:
            continue

        r = analyze(df)
        r["symbol"] = s
        results.append(r)

    results.sort(key=lambda x: x["score"], reverse=True)

    signals = [r for r in results if r["direction"] != "NEUTRAL"]

    if not signals:
        send_telegram("📊 V3.3: NO SIGNAL")
        return

    best = signals[0]

    msg = format_msg(best["symbol"], best)

    print(msg)
    send_telegram(msg)


if __name__ == "__main__":
    main()
