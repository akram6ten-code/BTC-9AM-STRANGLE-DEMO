import os, time, hmac, hashlib, json, requests
from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

DELTA_API_URL = os.environ.get("DELTA_API_URL", "https://api.demo.india.delta.exchange")
DELTA_API_KEY = os.environ.get("DELTA_API_KEY", "")
DELTA_API_SECRET = os.environ.get("DELTA_API_SECRET", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def send_tg(msg):
    try:
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except: pass

def delta_sign(method, path, body=""):
    ts = str(int(time.time()))
    msg = method + ts + path + body
    sig = hmac.new(DELTA_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return ts, sig

def delta_request(method, path, payload=None):
    body = json.dumps(payload) if payload else ""
    ts, sig = delta_sign(method, path, body)
    headers = {"api-key": DELTA_API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
    url = DELTA_API_URL + path
    if method == "GET":
        r = requests.get(url, headers=headers, timeout=15)
    else:
        r = requests.post(url, headers=headers, data=body, timeout=15)
    return r.json()

@app.get("/")
def home():
    return {"status": "DEMO Bot Running", "url": DELTA_API_URL, "time": str(datetime.now())}

@app.get("/sell")
def sell():
    try:
        # 1. Check API Key
        bal = delta_request("GET", "/v2/wallet/balances")
        if "error" in bal and bal["error"].get("code") == "invalid_api_key":
            return {"success": False, "error": "invalid_api_key", "full": bal}

        # 2. Get BTC Price
        tick = requests.get(f"{DELTA_API_URL}/v2/tickers/BTCUSD", timeout=10).json()
        btc_price = float(tick["result"]["spot_price"])
        atm = round(btc_price / 1000) * 1000

        # 3. Find Options for today - OTM 1500 points away
        call_strike = atm + 1500
        put_strike = atm - 1500
        
        # Get products
        prods = requests.get(f"{DELTA_API_URL}/v2/products", timeout=10).json()
        call_symbol = None
        put_symbol = None
        
        for p in prods["result"]:
            if p["contract_type"] == "call_options" and str(int(call_strike)) in p["symbol"]:
                if "BTC" in p["symbol"]:
                    call_symbol = p["symbol"]
                    break
        
        for p in prods["result"]:
            if p["contract_type"] == "put_options" and str(int(put_strike)) in p["symbol"]:
                if "BTC" in p["symbol"]:
                    put_symbol = p["symbol"]
                    break

        # For DEMO test, we will place order if symbol found
        orders = []
        if call_symbol:
            o1 = delta_request("POST", "/v2/orders", {"product_symbol": call_symbol, "size": 1, "side": "sell", "order_type": "market_order"})
            orders.append({"call": call_symbol, "resp": o1})
        
        if put_symbol:
            o2 = delta_request("POST", "/v2/orders", {"product_symbol": put_symbol, "size": 1, "side": "sell", "order_type": "market_order"})
            orders.append({"put": put_symbol, "resp": o2})

        send_tg(f"DEMO SELL Triggered\nBTC: {btc_price}\nCall: {call_symbol}\nPut: {put_symbol}\nResp: {orders}")
        
        return {"success": True, "btc_price": btc_price, "call": call_symbol, "put": put_symbol, "orders": orders, "balance": bal}

    except Exception as e:
        send_tg(f"ERROR /sell: {e}")
        return {"success": False, "error": str(e)}
