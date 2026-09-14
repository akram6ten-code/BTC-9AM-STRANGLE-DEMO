from flask import Flask, jsonify
import os, time, hmac, hashlib, requests
from datetime import datetime

app = Flask(__name__)

BASE_URL = "https://api.india.delta.exchange"
API_KEY = os.environ.get("DELTA_API_KEY", "").strip()
API_SECRET = os.environ.get("DELTA_API_SECRET", "").strip()

def get_signature(secret, message):
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

def get_btc_price():
    r = requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=10).json()
    return float(r['result']['close'])

def place_order(symbol, side):
    method = "POST"
    path = "/v2/orders"
    timestamp = str(int(time.time()))
    body = {
        "product_symbol": symbol,
        "size": 10,  # 10 LOT
        "side": side,
        "order_type": "market_order",
        "time_in_force": "gtc"
    }
    import json
    body_str = json.dumps(body)
    msg = method + timestamp + path + body_str
    sign = get_signature(API_SECRET, msg)
    headers = {
        'api-key': API_KEY,
        'timestamp': timestamp,
        'signature': sign,
        'Content-Type': 'application/json'
    }
    r = requests.post(BASE_URL + path, headers=headers, data=body_str, timeout=10)
    return r.json()

def get_expiry_symbol():
    # Daily expiry list se aaj ka expiry nikalna
    r = requests.get(f"{BASE_URL}/v2/products", timeout=10).json()
    for p in r['result']:
        if 'BTC' in p['symbol'] and p['contract_type'] == 'call_options':
            # Sabse najdeek ka expiry lelo
            return p['symbol'].split('-')[-1] 
    return None

@app.route("/")
def home():
    return "LIVE - Ready to SELL"

@app.route("/sell")
def sell():
    try:
        btc = get_btc_price()
        atm = int(round(btc / 100) * 100)

        # Aaj ki expiry - Delta format DD-MM-YY
        # Agar ye galat ho to Delta ke website se exact format dekh lenge
        from datetime import timedelta
        expiry = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%y") 
        # Demo ke liye try karte hain call list se
        # Better: direct products API se ATM symbol dhoondhna
        
        # ATM symbol try
        ce_sym = f"C-BTC-{atm}-{expiry}"
        pe_sym = f"P-BTC-{atm}-{expiry}"

        # Pehle products check karke sahi symbol dhoondh lete hain
        products = requests.get(f"{BASE_URL}/v2/products", timeout=10).json()['result']
        ce_real = next((p['symbol'] for p in products if str(atm) in p['symbol'] and 'C-BTC' in p['symbol']), ce_sym)
        pe_real = next((p['symbol'] for p in products if str(atm) in p['symbol'] and 'P-BTC' in p['symbol']), pe_sym)

        ce_order = place_order(ce_real, 'sell')
        pe_order = place_order(pe_real, 'sell')

        return jsonify({
            "btc": btc,
            "atm": atm,
            "sold": [ce_real, pe_real],
            "ce_result": ce_order,
            "pe_result": pe_order
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
