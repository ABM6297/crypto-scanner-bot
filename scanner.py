import requests

url = (
    "https://min-api.cryptocompare.com/data/v2/histominute"
    "?fsym=BTC"
    "&tsym=USDT"
    "&limit=5"
)

r = requests.get(url, timeout=20)

print("STATUS:", r.status_code)

try:
    data = r.json()

    print(data["Response"])

    print(
        "CANDLES:",
        len(data["Data"]["Data"])
    )

except Exception as e:
    print(e)
    print(r.text[:500])
