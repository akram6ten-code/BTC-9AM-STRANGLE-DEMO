import time, hmac, hashlib, json, requests, datetime, threading
from fastapi import FastAPI
from zoneinfo import ZoneInfo # pytz ki zarurat nahi

API_KEY = "1vX1L8Q7Jm2K4N9Pq6R3"
API_SECRET = "i8m3UqX2yZ5aB9cD0eF1gH2jK3lM4nO5pQ6rS7tU8vW9xY0zA1bC2dE3fG4h"
BASE_URL = "https://api.india.delta.exchange"

app = FastAPI()
bot_status = {"running": False, "position": None, "last_check": "Waiting"}

def api_call(method, endpoint, payload=None):
    try:
        ts = str(int(time.time()))
        path = f"/v2{endpoint}"
        body = json.dumps(payload) if payload else ""
        msg = method + ts + path + body
        sig = hmac.new(API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
        url = f"{BASE_URL}{path}"
        r = requests.request(method, url, headers=headers, data=body if payload else None, timeout=15)
        print(f"REQ {endpoint} {payload} -> RESP {r.text[:800]}", flush=True)
        return r.json()
    except Exception as e:
        print(f"API ERROR {e}", flush=True)
        return {}

def get_live_expiry():
    # Delta India: daily expiry, aaj ka ya kal ka jo live ho
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    for i in range(0, 4):
        d = (now + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        res = requests.get(f"{BASE_URL}/v2/products", params={"contract_types":"call_options", "states":"live", "expiry": d}, timeout=10).json()
        if res.get('result'):
            return d, res['result']
    return None, []

def get_atm(spot, products):
    strike = int(round(spot / 1000) * 1000)
    for p in products:
        if f"-{strike}-" in p['symbol']:
            return p['symbol'], strike
    # agar exact ATM na mile to pehla wala le lo
    return products[0]['symbol'], strike if products else (None, None)

def bot_loop():
    bot_status["running"] = True
    while bot_status["running"]:
        try:
            expiry_date, products = get_live_expiry()
            if not products:
                bot_status["last_check"] = "No live expiry"
                time.sleep(60)
                continue

            spot = float(requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=10).json()['result']['spot_price'])
            product_id, atm = get_atm(spot, products)

            ticker = requests.get(f"{BASE_URL}/v2/tickers/{product_id}", timeout=10).json().get('result', {})
            premium = float(ticker.get('mark_price', 0))

            bot_status["last_check"] = f"Exp:{expiry_date} Spot:{spot} ATM:{atm} Prod:{product_id} Prem:{premium}"
            print(bot_status["last_check"], flush=True)

            # ---- TERI STRATEGY YAHI LAGEGI (1 MIN) ----
            # Abhi ke liye sirf check kar raha hai, order tabhi marega jab tu bolega
            # Example: if premium < supertrend and not bot_status["position"]:
            # api_call("POST", "/orders", {...})

        except Exception as e:
            print(f"LOOP ERR {e}", flush=True)
        time.sleep(60) # 1 minute

@app.get("/")
def home():
    return {"message": "BTC Bot is live", "status": "running" if bot_status["running"] else "idle", "last_check": bot_status["last_check"], "position": bot_status["position"]}

@app.get("/start")
def start():
    if not bot_status["running"]:
        threading.Thread(target=bot_loop, daemon=True).start()
    return {"started": True}
