import os
import time
import requests
import pandas as pd
import ta

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
KLINE_URL = "https://api.binance.com/api/v3/klines"

BLACKLIST = {"USDT", "USDC", "DAI", "FDUSD", "PYUSD"}

_cached_symbols = []
_last_fetch_time = 0


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
    except Exception as e:
        print("TG ERROR:", e)


# =========================
# SYMBOLS (SAFE + CACHE)
# =========================
def get_symbols():
    global _cached_symbols, _last_fetch_time

    if time.time() - _last_fetch_time < 600 and _cached_symbols:
        return _cached_symbols

    try:
        r = requests.get(TICKER_URL, timeout=10)
        data = r.json()

        if not isinstance(data, list):
            raise Exception("BINANCE BLOCKED")

        symbols = [
            x["symbol"]
            for x in data
            if isinstance(x, dict)
            and x.get("symbol", "").endswith("USDT")
        ]

        if len(symbols) < 5:
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

        _cached_symbols = symbols[:10]
        _last_fetch_time = time.time()

        return _cached_symbols

    except:
        return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]


# =========================
# DATA
# =========================
def get_data(symbol):
    try:
        r = requests.get(
            KLINE_URL,
            params={"symbol": symbol, "interval": "1h", "limit": 200},
            timeout=10
        )

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
# ANALYZE (FINAL ENGINE)
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

    atr = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], 14
    ).average_true_range()

    adx_v = float(adx.iloc[-1])
    rsi_v = float(rsi.iloc[-1])
    atr_v = float(atr.iloc[-1])

    # =========================
    # REGIME
    # =========================
    if adx_v < 10:
        regime = "RANGE"
    elif adx_v < 18:
        regime = "WEAK"
    else:
        regime = "TREND"

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

    high20 = df["high"].rolling(20).max().iloc[-1]
    low20 = df["low"].rolling(20).min().iloc[-1]

    if price > high20:
        score += 3
    elif price < low20:
        score -= 3

    vol_avg = df["volume"].rolling(20).mean().iloc[-1]
    vol_now = df["volume"].iloc[-1]

    if vol_now > vol_avg:
        score += 1

    # =========================
    # THRESHOLD SYSTEM (FIXED)
    # =========================
    if regime == "RANGE":
        buy_th = 12
        sell_th = -12
    elif regime == "WEAK":
        buy_th = 10
        sell_th = -10
    else:
        buy_th = 9
        sell_th = -9

    direction = "NEUTRAL"

    if score >= buy_th:
        direction = "BUY"
    elif score <= sell_th:
        direction = "SELL"

    entry = price
    stop = tp1 = tp2 = 0

    if direction == "BUY":
        stop = entry - atr_v * 1.4
        risk = entry - stop
        tp1 = entry + risk * 2
        tp2 = entry + risk * 3

    elif direction == "SELL":
        stop = entry + atr_v * 1.4
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
        "tp2": round(tp2, 6),
        "regime": regime
    }


# =========================
# FORMAT
# =========================
def format_msg(symbol, r):
    return f"""
🚀 {symbol} (V3.3.1 FINAL)

Regime: {r['regime']}
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
    print("V3.3.1 FINAL STARTED")

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

    if not results:
        send_telegram("📊 V3.3.1: NO DATA")
        print("NO DATA")
        return

    results.sort(key=lambda x: x["score"], reverse=True)

    signals = [r for r in results if r["direction"] != "NEUTRAL"]

    if not signals:
        msg = "📊 V3.3.1: NO SIGNAL (MARKET UNCLEAR)"
        print(msg)
        send_telegram(msg)
        return

    best = signals[0]

    msg = format_msg(best["symbol"], best)

    print(msg)
    send_telegram(msg)


if __name__ == "__main__":
    main()
