from flask import Flask
import os, time, hmac, hashlib, json, requests
from datetime import datetime
import pytz

app = Flask(__name__)
BASE_URL = "https://testnet-api.delta.exchange"
IST = pytz.timezone('Asia/Kolkata')

API_KEY = os.environ.get("DELTA_API_KEY", "").strip()
API_SECRET = os.environ.get("DELTA_API_SECRET", "").strip()

def place_sell_straddle():
    if not API_KEY or not API_SECRET:
        return "FAIL: DELTA_API_KEY / SECRET Render Environment me nahi hai. Waha daal pehle."

    try:
        price = float(requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=10).json()['result']['mark_price'])
        strike = int(round(price/1000)*1000)

        prods = requests.get(f"{BASE_URL}/v2/products", timeout=15).json()['result']
        calls = [p for p in prods if p['contract_type']=='call_options' and p['strike_price']==str(strike) and 'BTC' in p['symbol']]
        puts = [p for p in prods if p['contract_type']=='put_options' and p['strike_price']==str(strike) and 'BTC' in p['symbol']]

        if not calls or not puts:
            return f"Strike {strike} ka option nahi mila"

        call = sorted(calls, key=lambda x: x['settlement_time'])[0]
        put = sorted(puts, key=lambda x: x['settlement_time'])[0]

        results = []
        for prod in [call, put]:
            ts = str(int(time.time()))
            data = {"product_id": prod['id'], "size": 1, "side": "sell", "order_type": "market_order"}
            payload = json.dumps(data)
            sig = hmac.new(API_SECRET.encode(), (f"POST{ts}/v2/orders{payload}").encode(), hashlib.sha256).hexdigest()
            headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
            r = requests.post(BASE_URL+"/v2/orders", headers=headers, data=payload, timeout=10)
            results.append(f"{prod['symbol']} -> {r.status_code} {r.text[:500]}")

        return f"BTC {price} Strike {strike}\n\n" + "\n\n".join(results)

    except Exception as e:
        return f"Error: {e}"

@app.route('/')
def home():
    return "Bot Live - /trigger kholo"

@app.route('/trigger')
def trigger():
    result = place_sell_straddle()
    print(result)
    return result.replace("\n", "<br>")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
