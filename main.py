import os, time, hmac, hashlib, json, requests
from flask import Flask

app = Flask(__name__)

DELTA_API_URL = os.environ.get("DELTA_API_URL", "https://api.india.delta.exchange")
DELTA_API_KEY = os.environ.get("DELTA_API_KEY", "Qpsok03gYv1vaDygBevzwrFPQwxkPo8")
DELTA_API_SECRET = os.environ.get("DELTA_API_SECRET", "cprm4Bdy9K5BY3XJL8AB1lYp00XgIRkQkURM1lT+rf26kakITFmwhsPCzO")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8470029646:AAHuy2_fw5A8D2XbL25edvUSlgX+9GiLAU")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6187580649")
LOT_SIZE = 1

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except: pass

def sign(m, p, pay=""):
    ts = str(int(time.time()))
    sig = hmac.new(DELTA_API_SECRET.encode(), (m+ts+p+pay).encode(), hashlib.sha256).hexdigest()
    return sig, ts

def delta_req(method, path, payload=None):
    js = json.dumps(payload) if payload else ""
    sig, ts = sign(method, path, js)
    headers = {'api-key': DELTA_API_KEY, 'timestamp': ts, 'signature': sig, 'Content-Type': 'application/json'}
    url = DELTA_API_URL + path
    try:
        if method == "GET": return requests.get(url, headers=headers, timeout=15).json()
        else: return requests.post(url, headers=headers, data=js, timeout=15).json()
    except: return {}

def get_atm():
    try:
        spot = float(requests.get(f"{DELTA_API_URL}/v2/tickers/BTCUSD", timeout=10).json()['result']['spot_price'])
    except: spot = 115000.0
    prods = delta_req("GET", "/v2/products").get('result', [])
    btc_opts = [p for p in prods if p.get('underlying_asset',{}).get('symbol')=='BTC' and p.get('contract_type') in ['call_options','put_options']]
    btc_opts.sort(key=lambda x: x.get('settlement_time',''))
    if not btc_opts: return None, None, spot, None, None
    curr_exp = btc_opts[0].get('settlement_time')
    curr_opts = [p for p in btc_opts if p.get('settlement_time')==curr_exp]
    atm_strike, min_diff = None, 1e9
    for p in curr_opts:
        try:
            s = float(p.get('strike_price')); d = abs(spot-s)
            if d < min_diff: min_diff=d; atm_strike=s
        except: continue
    ce, pe = None, None
    for p in curr_opts:
        if float(p.get('strike_price',0))==atm_strike:
            if p.get('contract_type')=='call_options': ce=p.get('symbol')
            if p.get('contract_type')=='put_options': pe=p.get('symbol')
    return ce, pe, spot, atm_strike, curr_exp

def place_sell(sym):
    return delta_req("POST", "/v2/orders", {"product_symbol": sym, "size": LOT_SIZE, "side": "sell", "order_type": "market_order"})

@app.route('/')
def home():
    ce, pe, spot, strike, exp = get_atm()
    return f"READY | BTC:{spot} | Strike:{strike} | Exp:{exp} | CE:{ce} | PE:{pe} | <a href='/sell'>/sell</a>"

@app.route('/sell')
def sell():
    ce, pe, spot, strike, exp = get_atm()
    if not ce or not pe: return f"ATM not found Spot:{spot}"
    r1 = place_sell(ce); r2 = place_sell(pe)
    msg = f"✅ SOLD ATM\nBTC:{spot}\nStrike:{strike}\nExp:{exp}\nCE:{ce}\nPE:{pe}"
    send_telegram(msg)
    return msg

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
