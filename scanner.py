import os
import requests
import pandas as pd
import ta

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
CMC_API_KEY = os.getenv("CMC_API_KEY")

TOP_LIMIT = 10

BLACKLIST = {"USDT", "USDC", "DAI", "FDUSD", "PYUSD"}


# =========================
# TELEGRAM
# =========================
def send_telegram(message: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("TELEGRAM CONFIG MISSING")
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message
    }

    try:
        r = requests.post(url, json=payload, timeout=15)
        print("TG STATUS:", r.status_code)
    except Exception as e:
        print("TG ERROR:", e)


# =========================
# TOP COINS (CMC)
# =========================
def get_top_coins():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": str(CMC_API_KEY or "").strip()
    }

    params = {
        "start": 1,
        "limit": TOP_LIMIT,
        "convert": "USD"
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        data = r.json()

        if "data" not in data:
            print("CMC ERROR:", data)
            return []

        coins = []
        for coin in data["data"]:
            symbol = coin["symbol"]
            if symbol not in BLACKLIST:
                coins.append(symbol)

        return coins

    except Exception as e:
        print("CMC ERROR:", e)
        return []


# =========================
# PRICE DATA (CryptoCompare)
# =========================
def get_data(symbol):
    url = (
        "https://min-api.cryptocompare.com/data/v2/histohour"
        f"?fsym={symbol}&tsym=USD&limit=200"
    )

    try:
        r = requests.get(url, timeout=20)
        data = r.json()

        if data.get("Response") != "Success":
            print(symbol, "NO DATA")
            return None

        rows = data["Data"]["Data"]

        if len(rows) < 100:
            print(symbol, "NOT ENOUGH DATA")
            return None

        df = pd.DataFrame(rows)

        df = df[["time", "open", "high", "low", "close", "volumefrom"]]
        df = df.rename(columns={"volumefrom": "volume"})

        return df

    except Exception as e:
        print(symbol, "ERROR:", e)
        return None


# =========================
# ATR
# =========================
def calculate_atr(df):
    atr = ta.volatility.AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )
    return float(atr.average_true_range().iloc[-1])


# =========================
# ANALYSIS ENGINE
# =========================
def analyze(df):
    close = df["close"]

    price = float(close.iloc[-1])

    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator()

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()

    macd = ta.trend.MACD(close)
    macd_line = macd.macd()
    signal_line = macd.macd_signal()

    score = 0

    # Trend
    if ema20.iloc[-1] > ema50.iloc[-1]:
        score += 3
    else:
        score -= 3

    # MACD
    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        score += 2
    else:
        score -= 2

    # RSI filter
    current_rsi = float(rsi.iloc[-1])

    if 50 <= current_rsi <= 70:
        score += 2
    elif current_rsi > 75:
        score -= 2

    # Breakout
    breakout_high = df["high"].rolling(20).max().shift(1).iloc[-1]
    breakout_low = df["low"].rolling(20).min().shift(1).iloc[-1]

    if price > breakout_high:
        score += 3
    if price < breakout_low:
        score -= 3

    atr = calculate_atr(df)

    # Direction
    if score >= 3:
        direction = "BUY"
    elif score <= -3:
        direction = "SELL"
    else:
        direction = "NEUTRAL"

    entry = price

    stop = tp1 = tp2 = 0

    if direction == "BUY":
        stop = entry - (atr * 1.5)
        risk = entry - stop
        tp1 = entry + (risk * 2)
        tp2 = entry + (risk * 3)

    elif direction == "SELL":
        stop = entry + (atr * 1.5)
        risk = stop - entry
        tp1 = entry - (risk * 2)
        tp2 = entry - (risk * 3)

    return {
        "price": round(price, 6),
        "score": int(score),
        "direction": direction,
        "rsi": round(current_rsi, 2),
        "atr": round(atr, 6),
        "entry": round(entry, 6),
        "stop": round(stop, 6),
        "tp1": round(tp1, 6),
        "tp2": round(tp2, 6)
    }


# =========================
# FORMAT MESSAGE
# =========================
def format_message(symbol, r):
    return f"""
🚀 {symbol}

Direction: {r['direction']}
Score: {r['score']}

Entry: {r['entry']}
Stop Loss: {r['stop']}
Take Profit 1: {r['tp1']}
Take Profit 2: {r['tp2']}

RSI: {r['rsi']}
ATR: {r['atr']}
"""


# =========================
# MAIN
# =========================
def main():
    print("SCANNER STARTED")

    coins = get_top_coins()
    print("COINS:", coins)

    results = []

    for symbol in coins:
        print("CHECKING", symbol)

        df = get_data(symbol)
        if df is None:
            continue

        result = analyze(df)
        result["symbol"] = symbol

        results.append(result)

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    signals = [r for r in results if r["direction"] != "NEUTRAL"]

    if not signals:
        print("NO SIGNAL")
        send_telegram("📊 NO SIGNAL FOUND")
        return

    for r in signals:
        msg = format_message(r["symbol"], r)
        print(msg)
        send_telegram(msg)


# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
