import os, time, hmac, hashlib, json, requests
from flask import Flask

app = Flask(__name__)

DELTA_API_URL = os.environ.get("DELTA_API_URL", "https://api.india.delta.exchange")
DELTA_API_KEY = os.environ.get("DELTA_API_KEY")
DELTA_API_SECRET = os.environ.get("DELTA_API_SECRET")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
LOT_SIZE = 1

def send_telegram(msg):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def sign(method, path, payload=""):
    ts = str(int(time.time()))
    msg = method + ts + path + payload
    sig = hmac.new(DELTA_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return sig, ts

def delta_req(method, path, payload=None):
    if not DELTA_API_KEY or not DELTA_API_SECRET:
        return {"error": "API KEYS MISSING IN ENV"}
    js = json.dumps(payload) if payload else ""
    sig, ts = sign(method, path, js)
    headers = {'api-key': DELTA_API_KEY, 'timestamp': ts, 'signature': sig, 'Content-Type': 'application/json'}
    try:
        url = DELTA_API_URL + path
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=15)
        else:
            r = requests.post(url, headers=headers, data=js, timeout=15)
        print(f"Delta {path} -> {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"Delta Error: {e}")
        return {"error": str(e)}

def get_atm():
    try:
        spot_data = requests.get(f"{DELTA_API_URL}/v2/tickers/BTCUSD", timeout=10).json()
        spot = float(spot_data['result']['spot_price'])
    except:
        spot = 115000.0

    prods_resp = delta_req("GET", "/v2/products")
    prods = prods_resp.get('result', [])
    if not prods:
        return None, None, spot, None, None, prods_resp

    btc_opts = [p for p in prods if p.get('underlying_asset',{}).get('symbol')=='BTC' and p.get('contract_type') in ['call_options','put_options']]
    if not btc_opts:
        return None, None, spot, None, None, "No BTC options found"

    btc_opts.sort(key=lambda x: x.get('settlement_time',''))
    curr_exp = btc_opts[0].get('settlement_time')
    curr_opts = [p for p in btc_opts if p.get('settlement_time')==curr_exp]

    atm_strike = min(curr_opts, key=lambda x: abs(float(x.get('strike_price',0)) - spot))
    atm_strike_val = float(atm_strike.get('strike_price'))

    ce, pe = None, None
    for p in curr_opts:
        # FIX: Tolerance ke saath compare
        if abs(float(p.get('strike_price',0)) - atm_strike_val) < 0.5:
            if p.get('contract_type')=='call_options': ce=p.get('symbol')
            if p.get('contract_type')=='put_options': pe=p.get('symbol')

    return ce, pe, spot, atm_strike_val, curr_exp, None

def place_sell(sym):
    return delta_req("POST", "/v2/orders", {"product_symbol": sym, "size": LOT_SIZE, "side": "sell", "order_type": "market_order"})

@app.route('/')
def home():
    ce, pe, spot, strike, exp, err = get_atm()
    if err: return f"ERROR: {err}"
    return f"READY | BTC:{spot} | Strike:{strike} | Exp:{exp} | CE:{ce} | PE:{pe} | <br><a href='/sell'>/sell pe click karke TEST kar</a>"

@app.route('/sell')
def sell():
    ce, pe, spot, strike, exp, err = get_atm()
    if err: return f"ERROR: {err}"
    if not ce or not pe: return f"ATM not found Spot:{spot} Strike:{strike}"

    r1 = place_sell(ce)
    r2 = place_sell(pe)
    msg = f"✅ SOLD ATM\nBTC:{spot}\nStrike:{strike}\nExp:{exp}\nCE:{ce} -> {r1}\nPE:{pe} -> {r2}"
    send_telegram(msg)
    return msg.replace("\n","<br>")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
