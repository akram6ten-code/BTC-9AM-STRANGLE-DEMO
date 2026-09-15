from flask import Flask
import os, time, hmac, hashlib, json, requests, threading
from datetime import datetime
import pytz

app = Flask(__name__)
BASE_URL = "https://testnet-api.delta.exchange"
IST = pytz.timezone('Asia/Kolkata')

# Render -> Environment me daal dena
API_KEY = os.environ.get("DELTA_API_KEY", "").strip()
API_SECRET = os.environ.get("DELTA_API_SECRET", "").strip()
TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")

def tg(msg):
    try:
        if TG_TOKEN and TG_CHAT:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": TG_CHAT, "text": msg}, timeout=5)
    except: pass
    print(msg)

def delta_request(method, path, payload=""):
    ts = str(int(time.time()))
    sig_data = method + ts + path + payload
    sig = hmac.new(API_SECRET.encode(), sig_data.encode(), hashlib.sha256).hexdigest()
    headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
    url = BASE_URL + path
    if method == "GET":
        return requests.get(url, headers=headers, timeout=15)
    else:
        return requests.post(url, headers=headers, data=payload, timeout=15)

def place_sell_straddle():
    try:
        if not API_KEY or not API_SECRET:
            return "API Key Secret Environment me daal pehle"

        # 1. BTC Price
        price = float(requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=10).json()['result']['mark_price'])
        strike = int(round(price/1000)*1000)
        tg(f"SELL Try: BTC {price} -> ATM {strike}")

        # 2. Products
        prods = requests.get(f"{BASE_URL}/v2/products", timeout=15).json()['result']
        calls = [p for p in prods if p['contract_type']=='call_options' and p['strike_price']==str(strike) and 'BTC' in p['symbol']]
        puts = [p for p in prods if p['contract_type']=='put_options' and p['strike_price']==str(strike) and 'BTC' in p['symbol']]

        if not calls or not puts:
            msg = f"Strike {strike} ka option nahi mila Delta pe"
            tg(msg)
            return msg

        # sabse nazdeek expiry wala
        call = sorted(calls, key=lambda x: x['settlement_time'])[0]
        put = sorted(puts, key=lambda x: x['settlement_time'])[0]

        # 3. SELL Both
        results = []
        for prod in [call, put]:
            data = {"product_id": prod['id'], "size": 1, "side": "sell", "order_type": "market_order"}
            payload = json.dumps(data)
            r = delta_request("POST", "/v2/orders", payload)
            results.append(f"{prod['symbol']} SELL -> {r.status_code} {r.text[:200]}")

        final_msg = f"✅ SELL DONE:\n{call['symbol']}\n{put['symbol']}\n\n{results[0]}\n{results[1]}"
        tg(final_msg)
        return final_msg

    except Exception as e:
        tg(f"Error: {e}")
        return f"Error: {e}"

@app.route('/')
def home():
    return "SELL Bot Live - /trigger kholte hi trade lagega"

@app.route('/trigger')
def trigger():
    threading.Thread(target=place_sell_straddle).start()
    return "SELL Order bhej diya - 5 sec me Telegram / Delta Demo me check kar"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
