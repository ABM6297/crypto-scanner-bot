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

    try:
        r = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20
        )

        data = r.json()

        if "data" not in data:
            print(data)
            return []

        blacklist = {
            "USDT",
            "USDC",
            "DAI",
            "FDUSD",
            "PYUSD"
        }

        coins = []

        for c in data["data"]:

            symbol = c["symbol"]

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

        df = df.rename(columns={
            "volumefrom": "volume"
        })

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


def analyze(df):

    close = df["close"]

    ema20 = ta.trend.EMAIndicator(
        close,
        window=20
    ).ema_indicator().iloc[-1]

    ema50 = ta.trend.EMAIndicator(
        close,
        window=50
    ).ema_indicator().iloc[-1]

    rsi = ta.momentum.RSIIndicator(
        close,
        window=14
    ).rsi().iloc[-1]

    price = close.iloc[-1]

    return {
        "price": round(price, 4),
        "ema20": round(ema20, 4),
        "ema50": round(ema50, 4),
        "rsi": round(rsi, 2)
    }


def main():

    print("SCANNER STARTED")

    coins = get_top_coins()

    print("COINS:", len(coins))

    for symbol in coins:

        print("CHECKING", symbol)

        df = get_data(symbol)

        if df is None:
            continue

        result = analyze(df)

        print(symbol, result)


if __name__ == "__main__":
    main()
