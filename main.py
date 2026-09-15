import time, hmac, hashlib, json, requests, threading, datetime
from fastapi import FastAPI
from zoneinfo import ZoneInfo

API_KEY = "PASTE_YOUR_REAL_KEY"
API_SECRET = "PASTE_YOUR_REAL_SECRET"
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
    print(r.text[:1500], flush=True)
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

def bot_loop():
    try:
        expiry, products = get_live_expiry()
        if not products:
            bot_status["last_check"] = "No expiry"
            return

        spot = float(requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=10).json()['result']['spot_price'])
        
        # Sirf is expiry ke product symbols
        prod_symbols = [p['symbol'] for p in products]
        # bulk tickers lekin filter nahi karna expiry string se
        tickers = requests.get(f"{BASE_URL}/v2/tickers", params={"contract_types":"call_options,put_options"}, timeout=20).json().get('result', [])

        best_call = None
        best_put = None
        bc_diff = 9999
        bp_diff = 9999

        for t in tickers:
            sym = t.get('symbol')
            if sym not in prod_symbols: continue
            prem = t.get('mark_price')
            if prem is None: continue
            prem = float(prem)
            if prem < 10: continue # bahut cheap hatao
            diff = abs(prem - 100)
            if sym.startswith("C-BTC-") and diff < bc_diff:
                bc_diff = diff
                best_call = (sym, prem, diff)
            if sym.startswith("P-BTC-") and diff < bp_diff:
                bp_diff = diff
                best_put = (sym, prem, diff)

        print(f"Found CALL {best_call} PUT {best_put}", flush=True)

        if not best_call or not best_put:
            bot_status["last_check"] = f"No near 100 for {expiry} total tickers {len(tickers)}"
            return

        call_sym, call_prem, _ = best_call
        put_sym, put_prem, _ = best_put

        bot_status["last_check"] = f"Exp:{expiry} Spot:{spot} | CALL:{call_sym} @{call_prem} | PUT:{put_sym} @{put_prem}"
        
        api_call("POST", "/orders", {"product_symbol": call_sym, "size": 1, "side": "sell", "order_type": "market_order"})
        time.sleep(1)
        api_call("POST", "/orders", {"product_symbol": put_sym, "size": 1, "side": "sell", "order_type": "market_order"})
        bot_status["position"] = f"SHORT {call_sym} & {put_sym}"

    except Exception as e:
        print(f"ERROR {e}", flush=True)
        bot_status["last_check"] = f"Error {e}"

@app.get("/")
def home(): return bot_status
@app.get("/start")
def start():
    threading.Thread(target=bot_loop, daemon=True).start()
    return {"started": True}
