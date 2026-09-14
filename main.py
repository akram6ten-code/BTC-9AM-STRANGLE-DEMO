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
    except Exception as e:
        print(f"TG Error: {e}")

def delta_request(method, path, payload=None):
    if not DELTA_API_KEY or not DELTA_API_SECRET:
        return {"error": {"code": "no_keys", "message": "Keys not set in ENV"}}
    body = json.dumps(payload) if payload else ""
    ts = str(int(time.time()))
    message = method + ts + path + body
    signature = hmac.new(DELTA_API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    headers = {"api-key": DELTA_API_KEY, "timestamp": ts, "signature": signature, "Content-Type": "application/json"}
    url = DELTA_API_URL + path
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=15)
        else:
            r = requests.post(url, headers=headers, data=body, timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def home():
    return {"status": "DEMO Bot Live", "api": DELTA_API_URL, "time": str(datetime.now())}

@app.get("/sell")
def sell():
    bal = delta_request("GET", "/v2/wallet/balances")
    if "error" in str(bal).lower():
        return {"success": False, "step": "balance_check", "error": bal}

    try:
        tick = requests.get(f"{DELTA_API_URL}/v2/tickers/BTCUSD", timeout=10).json()
        btc_price = float(tick["result"]["spot_price"])
    except Exception as e:
        return {"success": False, "error": f"Price fetch failed: {e}"}

    send_tg(f"DEMO Connected OK\nBTC: {btc_price}\nBalance OK: {str(bal)[:200]}")
    return {"success": True, "btc_price": btc_price, "balance": bal, "message": "API Key sahi hai, ab order logic add karenge"}
