import os
import requests
import pandas as pd
import ta

CMC_API_KEY = os.getenv("CMC_API_KEY")

TOP_LIMIT = 10


def get_top_coins():

    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": str(CMC_API_KEY).strip()
    }

    params = {
        "start": 1,
        "limit": TOP_LIMIT,
        "convert": "USD"
    }

    blacklist = {
        "USDT",
        "USDC",
        "DAI",
        "FDUSD",
        "PYUSD"
    }

    try:

        r = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20
        )

        data = r.json()

        if "data" not in data:
            print("CMC ERROR:", data)
            return []

        coins = []

        for coin in data["data"]:

            symbol = coin["symbol"]

            if symbol in blacklist:
                continue

            coins.append(symbol)

        return coins

    except Exception as e:

        print("CMC ERROR:", e)
        return []


def get_data(symbol):

    try:

        url = (
            "https://min-api.cryptocompare.com/data/v2/histohour"
            f"?fsym={symbol}"
            "&tsym=USDT"
            "&limit=200"
        )

        r = requests.get(
            url,
            timeout=20
        )

        data = r.json()

        if data.get("Response") != "Success":
            print(symbol, "NO DATA")
            return None

        rows = data["Data"]["Data"]

        if len(rows) < 100:
            print(symbol, "NOT ENOUGH DATA")
            return None

        df = pd.DataFrame(rows)

        df = df.rename(
            columns={
                "volumefrom": "volume"
            }
        )

        df = df[
            [
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        ]

        return df

    except Exception as e:

        print(symbol, "ERROR:", e)
        return None


def calculate_atr(df):

    atr = ta.volatility.AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    return float(
        atr.average_true_range().iloc[-1]
    )


def analyze(df):

    close = df["close"]

    price = float(close.iloc[-1])

    ema20 = ta.trend.EMAIndicator(
        close,
        window=20
    ).ema_indicator()

    ema50 = ta.trend.EMAIndicator(
        close,
        window=50
    ).ema_indicator()

    rsi = ta.momentum.RSIIndicator(
        close,
        window=14
    ).rsi()

    macd = ta.trend.MACD(close)

    macd_line = macd.macd()
    signal_line = macd.macd_signal()

    score = 0

    if ema20.iloc[-1] > ema50.iloc[-1]:
        score += 3
    else:
        score -= 3

    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        score += 2
    else:
        score -= 2

    current_rsi = float(rsi.iloc[-1])

    if 50 <= current_rsi <= 70:
        score += 2

    elif current_rsi > 75:
        score -= 2

    breakout_high = (
        df["high"]
        .rolling(20)
        .max()
        .shift(1)
        .iloc[-1]
    )

    breakout_low = (
        df["low"]
        .rolling(20)
        .min()
        .shift(1)
        .iloc[-1]
    )

    if price > breakout_high:
        score += 3

    if price < breakout_low:
        score -= 3

    atr = calculate_atr(df)

    return {
        "price": round(price, 6),
        "score": int(score),
        "rsi": round(current_rsi, 2),
        "atr": round(float(atr), 6)
    }


def main():

    print("SCANNER STARTED")

    coins = get_top_coins()

    print("COINS:", len(coins))

    results = []

    for symbol in coins:

        print("CHECKING", symbol)

        df = get_data(symbol)

        if df is None:
            continue

        result = analyze(df)

        results.append(
            {
                "symbol": symbol,
                **result
            }
        )

    results = sorted(
        results,
        key=lambda x: x["score"],
        reverse=True
    )

    print("\n===== TOP RESULTS =====\n")

    for r in results:

        print(
            f"{r['symbol']} | "
            f"Score={r['score']} | "
            f"RSI={r['rsi']} | "
            f"ATR={r['atr']} | "
            f"Price={r['price']}"
        )


if __name__ == "__main__":
    main()
