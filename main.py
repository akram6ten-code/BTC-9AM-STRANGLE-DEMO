import os, time, requests, datetime
from flask import Flask
from threading import Thread

app = Flask(__name__)
PREMIUM_MIN = 80
PREMIUM_MAX = 100

def get_btc_price():
    try:
        r = requests.get("https://api.india.delta.exchange/v2/tickers/BTCUSD", timeout=10).json()
        return float(r['result']['spot_price'])
    except:
        return 115000.0

def get_options_in_range():
    try:
        btc = get_btc_price()
        res = requests.get("https://api.india.delta.exchange/v2/tickers", timeout=10).json()
        valid = []
        for t in res.get('result', []):
            sym = t.get('symbol','')
            if 'BTC' not in sym: continue
            if '-C-' not in sym and '-P-' not in sym: continue
            if not t.get('mark_price'): continue
            price_usd = float(t['mark_price']) * btc
            if PREMIUM_MIN <= price_usd <= PREMIUM_MAX:
                valid.append(f"{sym} -> ${price_usd:.2f}")
        return valid[:10] if valid else ["80-100$ me leg nahi mila"]
    except Exception as e:
        return [f"Error: {e}"]

@app.route('/')
def home():
    data = get_options_in_range()
    btc = get_btc_price()
    return f"<h2>BTC ${btc:.0f}</h2>80-100$ Filter:<br>{'<br>'.join(data)}"

@app.route('/trigger')
def trigger():
    return home()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
