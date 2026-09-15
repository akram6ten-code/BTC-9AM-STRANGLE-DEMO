import os, time, hmac, hashlib, json, requests
from flask import Flask

app = Flask(__name__)

def get_signature(secret, method, timestamp, path, body):
    signature_data = method + timestamp + path + body
    return hmac.new(secret.encode(), signature_data.encode(), hashlib.sha256).hexdigest()

@app.route("/")
def home():
    return "Bot Live - Delta India Demo"

@app.route("/trigger")
def trigger():
    api_key = os.getenv("DELTA_API_KEY","").strip()
    api_secret = os.getenv("DELTA_API_SECRET","").strip()
    base_url = os.getenv("DELTA_API_URL","").strip().rstrip('/')

    if not api_key or not api_secret or not base_url:
        return "Env khali hai - KEY / SECRET / URL check karo"

    # 1. Pehle products list lelo - Demo ka sahi ID pata chalega
    try:
        path_prod = "/v2/products"
        timestamp = str(int(time.time()))
        sig = get_signature(api_secret, "GET", timestamp, path_prod, "")
        headers = {'api-key': api_key, 'timestamp': timestamp, 'signature': sig}
        r = requests.get(base_url + path_prod, headers=headers, timeout=15)

        if r.status_code!= 200:
            return f"Products fetch fail {base_url} => {r.status_code} {r.text[:500]}"

        products = r.json().get('result', [])
        # BTC ka koi bhi perpetual dhoondh lo
        btc_product = None
        for p in products:
            if 'BTC' in p.get('symbol','') and 'USD' in p.get('symbol','') and p.get('contract_type') == 'perpetual_futures':
                btc_product = p
                break
        if not btc_product:
            btc_product = products[0] if products else None

        if not btc_product:
            return "Koi product nahi mila demo pe"

        prod_id = btc_product['id']
        prod_sym = btc_product['symbol']

    except Exception as e:
        return f"Products error: {e}"

    # 2. Ab usi product pe order lagao
    try:
        path = "/v2/orders"
        url = base_url + path
        payload = {
            "product_id": prod_id,
            "size": 1,
            "side": "buy",
            "order_type": "market_order"
        }
        body = json.dumps(payload)
        timestamp = str(int(time.time()))
        signature = get_signature(api_secret, "POST", timestamp, path, body)
        headers = {
            'api-key': api_key,
            'timestamp': timestamp,
            'signature': signature,
            'Content-Type': 'application/json'
        }
        r = requests.post(url, data=body, headers=headers, timeout=10)
        return f"Trying {prod_sym} (ID:{prod_id}) on {base_url}<br><br>Status: {r.status_code}<br>{r.text}"
    except Exception as e:
        return f"Order error: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
