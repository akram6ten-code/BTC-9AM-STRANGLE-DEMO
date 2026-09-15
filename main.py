from flask import Flask
import os, time, hmac, hashlib, json, requests

app = Flask(__name__)
BASE_URL = "https://testnet-api.delta.exchange"
API_KEY = os.environ.get("DELTA_API_KEY", "").strip()
API_SECRET = os.environ.get("DELTA_API_SECRET", "").strip()

def place_sell():
    if not API_KEY:
        return "FAIL: API Key nahi hai. Render > Environment me daalo"

    try:
        # 1. Price
        try:
            r = requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=10).json()
            price = float(r['result']['mark_price'])
        except:
            price = 115000.0

        target_strike = int(round(price/1000)*1000)

        # 2. Saare BTC options nikalo
        prods = requests.get(f"{BASE_URL}/v2/products", timeout=15).json()['result']
        btc_calls = [p for p in prods if p['contract_type']=='call_options' and 'BTC' in p['symbol']]

        # Available strikes
        available_strikes = sorted(list(set([int(float(p['strike_price'])) for p in btc_calls if p['strike_price'].replace('.','').isdigit()])))

        if not available_strikes:
            return "BTC options hi nahi mile testnet pe"

        # Nearest strike dhoondo
        nearest_strike = min(available_strikes, key=lambda x: abs(x - target_strike))

        calls = [p for p in btc_calls if int(float(p['strike_price']))==nearest_strike]
        puts = [p for p in prods if p['contract_type']=='put_options' and 'BTC' in p['symbol'] and int(float(p['strike_price']))==nearest_strike]

        call = sorted(calls, key=lambda x: x['settlement_time'])[0]
        put = sorted(puts, key=lambda x: x['settlement_time'])[0]

        out = [f"BTC Price: {price} | Target: {target_strike} | Final Strike Used: {nearest_strike} (Testnet pe yahi hai)", f"Available Strikes: {available_strikes[:15]}...", f"Call: {call['symbol']} | Put: {put['symbol']}"]

        for prod in [call, put]:
            ts = str(int(time.time()))
            data = {"product_id": prod['id'], "size": 1, "side": "sell", "order_type": "market_order"}
            payload = json.dumps(data)
            sig = hmac.new(API_SECRET.encode(), (f"POST{ts}/v2/orders{payload}").encode(), hashlib.sha256).hexdigest()
            headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
            resp = requests.post(BASE_URL+"/v2/orders", headers=headers, data=payload, timeout=10)
            out.append(f"SELL {prod['symbol']} => {resp.status_code} {resp.text[:800]}")

        return "\n\n".join(out)
    except Exception as e:
        return f"Exception: {e}"

@app.route('/')
def home():
    return "Bot Live - /trigger pe auto nearest strike pe SELL hoga"

@app.route('/trigger')
def trigger():
    res = place_sell()
    print(res)
    return res.replace("\n", "<br>")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
