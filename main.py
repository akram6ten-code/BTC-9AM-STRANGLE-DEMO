import time, hmac, hashlib, json, requests, threading
from fastapi import FastAPI
from zoneinfo import ZoneInfo
import datetime

API_KEY = "TERA_KEY_YAHAN_DAAL"
API_SECRET = "TERA_SECRET_YAHAN_DAAL"
BASE_URL = "https://api.india.delta.exchange"

app = FastAPI()
bot_status = {"last_check": "Idle", "position": None}

def api_call(method, endpoint, payload=None):
    ts = str(int(time.time()))
    path = f"/v2{endpoint}"
    body = json.dumps(payload) if payload else ""
    msg = method + ts + path + body
    sig = hmac.new(API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
    r = requests.request(method, f"{BASE_URL}{path}", headers=headers, data=body if payload else None, timeout=15)
    print(f"{endpoint} -> {r.text[:1200]}", flush=True)
    return r.json()

def get_live_expiry():
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    for i in range(5):
        d = (now + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        res = requests.get(f"{BASE_URL}/v2/products", params={"contract_types":"call_options,put_options", "states":"live", "expiry": d}, timeout=10).json()
        if res.get('result'):
            return d, res['result']
    return None, []

def find_near_100(products, side):
    best_sym, best_prem, best_diff = None, 0, 9999
    for p in products:
        if not p['symbol'].startswith(f"{side}-BTC-"): continue
        try:
            prem = float(requests.get(f"{BASE_URL}/v2/tickers/{p['symbol']}", timeout=5).json()['result']['mark_price'])
            diff = abs(prem - 100)
            if diff < best_diff and prem > 10: # 10 se kam wala illiquid hata diya
                best_diff = diff
                best_sym = p['symbol']
                best_prem = prem
        except: continue
    return best_sym, best_prem

def bot_loop():
    expiry, products = get_live_expiry()
    spot = float(requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=10).json()['result']['spot_price'])
    print(f"Scanning expiry {expiry} spot {spot}", flush=True)

    call_sym, call_prem = find_near_100(products, 'C')
    put_sym, put_prem = find_near_100(products, 'P')

    bot_status["last_check"] = f"Exp:{expiry} Spot:{spot} CALL:{call_sym} ~{call_prem} | PUT:{put_sym} ~{put_prem}"
    print(bot_status["last_check"], flush=True)

    if call_sym:
        print(f"SELL CALL {call_sym}", flush=True)
        api_call("POST", "/orders", {"product_symbol": call_sym, "size": 1, "side": "sell", "order_type": "market_order"})
        time.sleep(1)
    if put_sym:
        print(f"SELL PUT {put_sym}", flush=True)
        api_call("POST", "/orders", {"product_symbol": put_sym, "size": 1, "side": "sell", "order_type": "market_order"})

    bot_status["position"] = f"SHORT {call_sym} & {put_sym}"

@app.get("/")
def home(): return bot_status

@app.get("/start")
def start():
    threading.Thread(target=bot_loop, daemon=True).start()
    return {"started": True}
