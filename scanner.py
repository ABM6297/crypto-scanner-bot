import requests

symbols = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT"
]

for symbol in symbols:

    try:

        url = (
            "https://api.binance.com/api/v3/klines"
            f"?symbol={symbol}"
            f"&interval=15m"
            f"&limit=5"
        )

        r = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        print("=" * 50)
        print(symbol)
        print("STATUS:", r.status_code)

        try:
            data = r.json()

            if isinstance(data, list):
                print("SUCCESS")
                print("CANDLES:", len(data))
                print("LAST CLOSE:", data[-1][4])

            else:
                print("JSON RESPONSE:")
                print(data)

        except Exception:
            print("RAW RESPONSE:")
            print(r.text[:500])

    except Exception as e:
        print(symbol, "ERROR:", e)
