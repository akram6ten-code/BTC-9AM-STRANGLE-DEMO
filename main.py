from flask import Flask
import os, time, hmac, hashlib, json, requests

app = Flask(__name__)
BASE_URL = "https://testnet-api.delta.exchange"

API_KEY = os.environ.get("DELTA_API_KEY", "").strip()
API_SECRET = os.environ.get("DELTA_API_SECRET", "").strip()

def get_btc_price():
    try:
        # try 1: BTCUSD ticker
        r = requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=10).json()
        if r.get('result') and r['result'].get('mark_price'):
            return float(r['result']['mark_price'])

        # try 2: BTCUSDT or index
        r2 = requests.get(f"{BASE_URL}/v2/tickers", timeout=10).json()
        for t in r2.get('result', []):
            if t['symbol'] == 'BTCUSD' and t.get('mark_price'):
                return float(t['mark_price'])
        # fallback
        return 115000.0
    except:
        return 115000.0

def place_sell():
    if not API_KEY:
        return "FAIL: Render > Environment me DELTA_API_KEY / SECRET daalo pehle"

    try:
        price = get_btc_price()
        strike = int(round(price/1000)*1000)

        prods = requests.get(f"{BASE_URL}/v2/products", timeout=15).json()['result']
        calls = [p for p in prods if p['contract_type']=='call_options' and p['strike_price']==str(strike) and 'BTC' in p['symbol']]
        puts = [p for p in prods if p['contract_type']=='put_options' and p['strike_price']==str(strike) and 'BTC' in p['symbol']]

        if not calls:
            # strike nahi mila to nearest strike lo
            all_strikes = sorted(list(set([int(float(p['strike_price'])) for p in prods if 'BTC' in p['symbol'] and p['contract_type']=='call_options'])))
            nearest = min(all_strikes, key=lambda x: abs(x - strike))
            return f"Strike {strike} nahi mila. Nearest available: {nearest}. Code me strike={nearest} karke try karo. Price={price}"

        call = sorted(calls, key=lambda x: x['settlement_time'])[0]
        put = sorted(puts, key=lambda x: x['settlement_time'])[0]

        out = [f"BTC Price: {price} -> ATM Strike: {strike}", f"Call: {call['symbol']} | Put: {put['symbol']}"]

        for prod in [call, put]:
            ts = str(int(time.time()))
            data = {"product_id": prod['id'], "size": 1, "side": "sell", "order_type": "market_order"}
            payload = json.dumps(data)
            sig = hmac.new(API_SECRET.encode(), (f"POST{ts}/v2/orders{payload}").encode(), hashlib.sha256).hexdigest()
            headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
            r = requests.post(BASE_URL+"/v2/orders", headers=headers, data=payload, timeout=10)
            out.append(f"{prod['symbol']} SELL => {r.status_code} {r.text[:800]}")

        return "\n\n".join(out)

    except Exception as e:
        return f"Exception: {e}"

@app.route('/')
def home():
    return f"Live. Price check: {get_btc_price()}"

@app.route('/trigger')
def trigger():
    res = place_sell()
    print(res)
    return res.replace("\n", "<br>")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
