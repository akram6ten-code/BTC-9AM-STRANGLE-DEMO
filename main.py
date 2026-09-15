from flask import Flask
import os, time, hmac, hashlib, json, requests

app = Flask(__name__)
BASE_URL = "https://testnet-api.delta.exchange"
API_KEY = os.environ.get("DELTA_API_KEY", "").strip()
API_SECRET = os.environ.get("DELTA_API_SECRET", "").strip()

def place_sell():
    if not API_KEY or not API_SECRET:
        return "FAIL: Render > Environment me DELTA_API_KEY aur SECRET nahi hai"

    try:
        prods = requests.get(f"{BASE_URL}/v2/products", timeout=15).json()['result']

        # Tere screenshot ke hisab se ATM 76000 hai
        FINAL_STRIKE = 76000

        # Aaj ki expiry (16 Sep) ka option dhoondo - sabse jaldi expire hone wala
        btc_calls = [p for p in prods if p.get('contract_type')=='call_options' and 'BTC' in p.get('symbol','') and p.get('strike_price') and int(float(p['strike_price']))==FINAL_STRIKE]
        btc_puts = [p for p in prods if p.get('contract_type')=='put_options' and 'BTC' in p.get('symbol','') and p.get('strike_price') and int(float(p['strike_price']))==FINAL_STRIKE]

        if not btc_calls or not btc_puts:
            # agar 76000 na mile to 75000-77000 me se jo mile
            all_strikes = sorted(list(set([int(float(p['strike_price'])) for p in prods if 'BTC' in p.get('symbol','') and p.get('strike_price')])))
            return f"76000 strike nahi mila. Teri chain me ye strikes hain: {all_strikes} | Calls found for 76000: {len(btc_calls)} Puts: {len(btc_puts)}"

        call = sorted(btc_calls, key=lambda x: x['settlement_time'])[0]
        put = sorted(btc_puts, key=lambda x: x['settlement_time'])[0]

        out = [f"Chain Price: ~75762 | FINAL STRIKE LOCKED: {FINAL_STRIKE}", f"CALL: {call['symbol']} Expiry: {call['settlement_time']}", f"PUT: {put['symbol']} Expiry: {put['settlement_time']}"]

        for prod in [call, put]:
            ts = str(int(time.time()))
            body = {"product_id": prod['id'], "size": 1, "side": "sell", "order_type": "market_order"}
            payload = json.dumps(body)
            sig = hmac.new(API_SECRET.encode(), (f"POST{ts}/v2/orders{payload}").encode(), hashlib.sha256).hexdigest()
            headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
            r = requests.post(BASE_URL+"/v2/orders", headers=headers, data=payload, timeout=15)
            out.append(f"ORDER {prod['symbol']} => Status {r.status_code} | {r.text[:900]}")

        return "\n\n".join(out)

    except Exception as e:
        import traceback
        return f"Exception: {e} | {traceback.format_exc()[:1500]}"

@app.route('/')
def home(): return "FINAL BOT LIVE - Strike 76000 - /trigger pe SELL hoga"

@app.route('/trigger')
def trigger():
    return place_sell().replace("\n","<br>")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
