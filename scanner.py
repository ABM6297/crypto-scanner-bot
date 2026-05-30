import requests

url = (
    "https://min-api.cryptocompare.com/data/v2/histohour"
    "?fsym=BTC"
    "&tsym=USDT"
    "&limit=3"
)

r = requests.get(url, timeout=20)

print(r.json())
