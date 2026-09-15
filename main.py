import time, hmac, hashlib, requests, json, pandas as pd, threading, os
from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

# --- CONFIG - DEMO.DELTA.EXCHANGE ---
BASE_URL = "https://cdn-ind.testnet.deltaex.org"
API_KEY = "vPbT9hNZnAlZwu7ESb1SXh4Ugh64FQ"
API_SECRET = "rHOasGMfXzrsjtupKY0hRKXT031d09mlPxicu8xyUXouNQWvD9O0xYA6PDmz"
LEVERAGE = 100
LOT_SIZE = 50
TARGET_PCT = 0.90
SL_PCT = 0.50
RESOLUTION = "15m"

bot_status = {"status": "idle", "last_check": "", "position": None}

def get_signature(secret, message):
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

def api_call(method, path, query="", payload=""):
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + path + query + payload
    signature = get_signature(API_SECRET, signature_data)
    headers = {'api-key': API_KEY, 'timestamp': timestamp, 'signature': signature, 'Content-Type': 'application/json'}
    url = BASE_URL + path + query
    r = requests.request(method, url, data=payload, headers=headers, timeout=10)
    return r.json()

def get_atm_call_product():
    res = requests.get(f"{BASE_URL}/v2/products?contract_types=call_options&underlying_asset_symbols=BTC")
    products = [p for p in res.json()['result'] if p['state']=='live']
    products.sort(key=lambda x: x['settlement_time'])
    current_expiry_time = products[0]['settlement_time']
    current_expiry_products = [p for p in products if p['settlement_time']==current_expiry_time]
    spot = float(requests.get(f"{BASE_URL}/v2/tickers/BTCUSD").json()['result']['spot_price'])
    atm_strike = int(round(spot / 100) * 100)
    atm_call = next((p for p in current_expiry_products if float(p['strike_price'])==atm_strike), None)
    if not atm_call:
        atm_call = min(current_expiry_products, key=lambda x: abs(float(x['strike_price'])-atm_strike))
    print(f"LOCKED: Spot={spot} | ATM Strike={atm_call['strike_price']} | Product={atm_call['symbol']}")
    return atm_call

def get_supertrend_value(symbol):
    end = int(time.time())
    start = end - (200*15*60)
    r = requests.get(f"{BASE_URL}/v2/history/candles?symbol={symbol}&resolution={RESOLUTION}&start={start}&end={end}")
    candles = r.json()['result']
    df = pd.DataFrame(candles)
    df['hl2'] = (df['high'] + df['low'])/2
    df['tr'] = df['high'] - df['low']
    period = 10
    multiplier = 3
    df['atr'] = df['tr'].rolling(period).mean()
    df['upperband'] = df['hl2'] + (multiplier * df['atr'])
    df['lowerband'] = df['hl2'] - (multiplier * df['atr'])
    df['supertrend'] = 0.0
    df['in_uptrend'] = True
    # FIXED:.loc use kiya hai taaki warning aur slow na ho
    for i in range(1, len(df)):
        close = df.loc[i, 'close']
        ub_prev = df.loc[i-1, 'upperband']
        lb_prev = df.loc[i-1, 'lowerband']
        if close > ub_prev:
            df.loc[i, 'in_uptrend'] = True
        elif close < lb_prev:
            df.loc[i, 'in_uptrend'] = False
        else:
            df.loc[i, 'in_uptrend'] = df.loc[i-1, 'in_uptrend']
            if df.loc[i, 'in_uptrend'] and df.loc[i, 'lowerband'] < lb_prev:
                df.loc[i, 'lowerband'] = lb_prev
            if not df.loc[i, 'in_uptrend'] and df.loc[i, 'upperband'] > ub_prev:
                df.loc[i, 'upperband'] = ub_prev
        df.loc[i, 'supertrend'] = df.loc[i, 'lowerband'] if df.loc[i, 'in_uptrend'] else df.loc[i, 'upperband']
    return float(df.iloc[-1]['supertrend']), float(df.iloc[-1]['close'])

def bot_loop():
    global bot_status
    try:
        product = get_atm_call_product()
        try:
            api_call("POST", "/v2/products/"+str(product['id'])+"/orders/leverage", payload=json.dumps({"leverage": str(LEVERAGE)}))
        except: pass
        position = None
        entry_price = 0
        initial_sl = 0
        trailing_sl = 0
        bot_status["status"] = "running"
        print("Bot Started - Waiting for Premium < SuperTrend...")
        while True:
            try:
                ticker = requests.get(f"{BASE_URL}/v2/tickers/{product['symbol']}").json()['result']
                premium_ltp = float(ticker['mark_price'])
                st_value, _ = get_supertrend_value(product['symbol'])
                bot_status["last_check"] = f"Premium {premium_ltp} | ST {st_value} | Pos {position}"
                if position is None:
                    if premium_ltp < st_value:
                        order = api_call("POST", "/v2/orders", payload=json.dumps({"product_id": product['id'], "size": LOT_SIZE, "side": "sell", "order_type": "market_order"}))
                        position = "SHORT"
                        entry_price = premium_ltp
                        initial_sl = entry_price * (1 + SL_PCT)
                        trailing_sl = initial_sl
                        bot_status["position"] = f"SHORTED @ {entry_price} SL {initial_sl}"
                else:
                    profit = entry_price - premium_ltp
                    if profit > 0:
                        new_trail = initial_sl - profit
                        if new_trail < trailing_sl:
                            trailing_sl = new_trail
                    target_price = entry_price * (1 - TARGET_PCT)
                    if premium_ltp <= target_price or premium_ltp >= trailing_sl:
                        api_call("POST", "/v2/orders", payload=json.dumps({"product_id": product['id'], "size": LOT_SIZE, "side": "buy", "order_type": "market_order"}))
                        bot_status["position"] = f"EXITED @ {premium_ltp}"
                        break
                time.sleep(5)
            except Exception as e:
                print("Error:", e)
                time.sleep(5)
    except Exception as e:
        bot_status["status"] = f"error: {e}"

@app.get("/")
def home():
    return {"message": "BTC Bot is Live", "bot": bot_status}

@app.get("/start")
def start_bot():
    if bot_status["status"]!= "running":
        threading.Thread(target=bot_loop, daemon=True).start()
        return {"started": True}
    return {"started": False, "msg": "already running"}

# Render ke liye port bind fix
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
