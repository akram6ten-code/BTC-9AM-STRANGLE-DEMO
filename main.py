from flask import Flask, jsonify
import os, time, hmac, hashlib, requests, json
import pytz
from datetime import datetime

app = Flask(__name__)
BASE_URL = "https://api.india.delta.exchange"
API_KEY = os.environ.get("DELTA_API_KEY","").strip()
API_SECRET = os.environ.get("DELTA_API_SECRET","").strip()

def sign(secret, msg):
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

def get_btc():
    r = requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=10).json()
    return float(r['result']['close'])

def get_products():
    r = requests.get(f"{BASE_URL}/v2/products", timeout=15).json()
    return [p for p in r['result'] if p['state']=='live' and 'BTC' in p['symbol']]

def place(symbol):
    ts = str(int(time.time()))
    path = "/v2/orders"
    body = {"product_symbol": symbol, "size": 10, "side": "sell", "order_type": "market_order"}
    body_str = json.dumps(body)
    sig = sign(API_SECRET, "POST"+ts+path+body_str)
    headers = {'api-key': API_KEY, 'timestamp': ts, 'signature': sig, 'Content-Type': 'application/json'}
    r = requests.post(BASE_URL+path, headers=headers, data=body_str, timeout=10)
    print(f"SELL {symbol} -> {r.text[:300]}")
    return r.json()

@app.route("/")
def home():
    return "LIVE - ATM READY - /sell dabao"

@app.route("/sell")
def sell():
    try:
        btc = get_btc()
        atm = round(btc / 100) * 100

        prods = get_products()
        # ATM ke sabse kareeb wala Call aur Put
        ce = sorted([p for p in prods if p['contract_type']=='call_options'], key=lambda x: abs(float(x['strike_price'])-atm))[0]
        pe = sorted([p for p in prods if p['contract_type']=='put_options'], key=lambda x: abs(float(x['strike_price'])-atm))[0]

        ce_sym = ce['symbol']
        pe_sym = pe['symbol']

        ce_res = place(ce_sym)
        pe_res = place(pe_sym)

        return jsonify({
            "success": True,
            "btc": btc,
            "atm": atm,
            "sold": [ce_sym, pe_sym],
            "ce_res": ce_res,
            "pe_res": pe_res
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
