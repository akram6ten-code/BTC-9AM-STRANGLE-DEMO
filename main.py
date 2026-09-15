import time, hmac, hashlib, json, requests, threading, datetime
from fastapi import FastAPI
from zoneinfo import ZoneInfo

API_KEY = "PASTE_YOUR_DEMO_KEY_YAHAN"
API_SECRET = "PASTE_YOUR_DEMO_SECRET_YAHAN"

# --- YAHI MAIN FIX HAI - DEMO URL ---
BASE_URL = "https://cdn-ind.testnet.deltaex.org"

app = FastAPI()
bot_status = {"last_check": "Idle", "position": None, "last_order_response": None}

def api_call(method, endpoint, payload=None):
    ts = str(int(time.time()))
    path = f"/v2{endpoint}"
    body = json.dumps(payload) if payload else ""
    msg = method + ts + path + body
    sig = hmac.new(API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
    r = requests.request(method, f"{BASE_URL}{path}", headers=headers, data=body if payload else None, timeout=15)
    print(f"API {endpoint} -> {r.text[:1000]}", flush=True)
    try:
        return r.json()
    except:
        return {"raw": r.text}

def get_live_expiry():
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    for i in range(5):
        d = (now + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        res = requests.get(f"{BASE_URL}/v2/products", params={"contract_types":"call_options,put_options", "states":"live", "expiry": d}, timeout=10).json()
        if res.get('result'):
            return d, res['result']
    return None, []

def bot_loop():
    try:
        expiry, products = get_live_expiry()
        if not products:
            bot_status["last_check"] = "No expiry found"
            return
        prod_symbols = [p['symbol'] for p in products]
        tickers = requests.get(f"{BASE_URL}/v2/tickers", params={"contract_types":"call_options,put_options"}, timeout=20).json().get('result', [])

        best_call = best_put = None
        bc_diff = bp_diff = 9999

        for t in tickers:
            sym = t.get('symbol')
            if sym not in prod_symbols: continue
            prem = t.get('mark_price')
            if prem is None: continue
            prem = float(prem)
            if prem < 10: continue
            diff = abs(prem - 100)
            if sym.startswith("C-BTC-") and diff < bc_diff:
                bc_diff = diff
                best_call = (sym, prem)
            if sym.startswith("P-BTC-") and diff < bp_diff:
                bp_diff = diff
                best_put = (sym, prem)

        if not best_call or not best_put:
            bot_status["last_check"] = f"No near 100 for {expiry}"
            return

        call_sym, call_prem = best_call
        put_sym, put_prem = best_put
        bot_status["last_check"] = f"Exp:{expiry} CALL:{call_sym}@{call_prem} PUT:{put_sym}@{put_prem}"

        r1 = api_call("POST", "/orders", {"product_symbol": call_sym, "size": 1, "side": "sell", "order_type": "market_order"})
        time.sleep(1)
        r2 = api_call("POST", "/orders", {"product_symbol": put_sym, "size": 1, "side": "sell", "order_type": "market_order"})

        bot_status["last_order_response"] = {"call": r1, "put": r2}
        bot_status["position"] = f"SHORT {call_sym} & {put_sym}"

    except Exception as e:
        bot_status["last_check"] = f"Error {e}"
        print(f"ERROR {e}", flush=True)

@app.get("/")
def home(): return bot_status

@app.get("/start")
def start():
    threading.Thread(target=bot_loop, daemon=True).start()
    return {"started": True}
