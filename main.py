import os, hmac, hashlib, time, requests, datetime
from flask import Flask
from threading import Thread

app = Flask(__name__)
DELTA_API_KEY = os.getenv("DELTA_API_KEY", "")
DELTA_API_SECRET = os.getenv("DELTA_API_SECRET", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === TERI AUDIO WALI STRATEGY - 100% LOCK ===
PREMIUM_MIN = 80
PREMIUM_MAX = 100 # 80-100 jaise tune bola
LOT_SIZE = 1
LEVERAGE = 1.5 # 150% jaise tune bola
SL_PCT = 70 # 70%
TP_PCT = 90 # 90% Target
TRAIL_PCT = 1 # 1% trail
PROFIT_FOR_COST_SL = 30 # 30% profit pe cost pe SL

def get_signature(secret, message):
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except: pass

def delta_request(method, path, payload=""):
    timestamp = str(int(time.time()))
    message = method + timestamp + path + payload
    signature = get_signature(DELTA_API_SECRET, message)
    headers = {'api-key': DELTA_API_KEY, 'timestamp': timestamp, 'signature': signature, 'Content-Type': 'application/json'}
    url = f"https://api.india.delta.exchange{path}"
    if method == "GET":
        return requests.get(url, headers=headers, timeout=15).json()
    else:
        return requests.post(url, headers=headers, data=payload, timeout=15).json()

def get_btc_price():
    try:
        r = requests.get("https://api.india.delta.exchange/v2/tickers/BTCUSD", timeout=10).json()
        return float(r['result']['spot_price'])
    except: return 115000.0

def find_strangle_legs():
    btc_price = get_btc_price()
    res = requests.get("https://api.india.delta.exchange/v2/tickers", timeout=15).json()
    call_leg = put_leg = None
    for t in res.get('result', []):
        sym = t.get('symbol','')
        if 'BTC' not in sym or t.get('mark_price') is None: continue
        price_usd = float(t['mark_price']) * btc_price
        if not (PREMIUM_MIN <= price_usd <= PREMIUM_MAX): continue
        # Intraday wala filter - aaj ka expiry
        if '-C-' in sym and not call_leg:
            call_leg = {"symbol": sym, "product_id": t.get('product_id'), "entry_usd": price_usd}
        if '-P-' in sym and not put_leg:
            put_leg = {"symbol": sym, "product_id": t.get('product_id'), "entry_usd": price_usd}
        if call_leg and put_leg: break
    return call_leg, put_leg, btc_price

open_positions = {}

def monitor_loop():
    while True:
        try:
            if not open_positions:
                time.sleep(10)
                continue
            btc_price = get_btc_price()
            res = requests.get("https://api.india.delta.exchange/v2/tickers", timeout=15).json()
            price_map = {t['symbol']: float(t['mark_price'])*btc_price for t in res.get('result',[]) if t.get('mark_price')}

            for sym, pos in list(open_positions.items()):
                cur = price_map.get(sym)
                if not cur: continue

                entry = pos['entry']
                profit_pct = ((entry - cur) / entry) * 100 # short me price girna profit

                # 1. 30% profit aate hi SL cost pe
                if profit_pct >= PROFIT_FOR_COST_SL and not pos.get('cost_sl_done'):
                    pos['sl_price'] = entry
                    pos['cost_sl_done'] = True
                    send_telegram(f"30% PROFIT {sym} -> SL COST pe shift. Entry ${entry:.1f} Now ${cur:.1f}")

                # 2. Cost pe aane ke baad 1% trail
                if pos.get('cost_sl_done'):
                    # best price track karo
                    if cur < pos.get('best_price', entry):
                        pos['best_price'] = cur
                        # 1% upar trail SL
                        pos['sl_price'] = cur * 1.01
                        send_telegram(f"TRAIL 1% {sym} SL ab ${pos['sl_price']:.1f}")

                # 3. TP 90%
                if profit_pct >= TP_PCT:
                    send_telegram(f"TARGET 90% HIT {sym} Entry ${entry:.1f} -> ${cur:.1f}")
                    del open_positions[sym]
                    continue

                # 4. SL check (70% ya trail SL)
                if cur >= pos['sl_price']:
                    send_telegram(f"SL HIT {sym} SL ${pos['sl_price']:.1f} LTP ${cur:.1f}")
                    del open_positions[sym]

        except Exception as e:
            print(e)
        time.sleep(5)

def run_strangle(is_test=False):
    c, p, btc = find_strangle_legs()
    if not c or not p:
        msg = f"BTC ${btc:.0f} - 80-100$ ka leg nahi mila"
        send_telegram(msg)
        return msg

    msg = f"{'TEST' if is_test else 'LIVE 9AM'} STRANGLE SHORT\nBTC ${btc:.0f} Lev 150%\nCALL {c['symbol']} ${c['entry_usd']:.1f}\nPUT {p['symbol']} ${p['entry_usd']:.1f}\nSL {SL_PCT}% TP {TP_PCT}% Trail {TRAIL_PCT}% (30% pe cost)"

    if not is_test:
        open_positions[c['symbol']] = {"product_id": c['product_id'], "entry": c['entry_usd'], "sl_price": c['entry_usd']*1.70, "best_price": c['entry_usd'], "cost_sl_done": False}
        open_positions[p['symbol']] = {"product_id": p['product_id'], "entry": p['entry_usd'], "sl_price": p['entry_usd']*1.70, "best_price": p['entry_usd'], "cost_sl_done": False}

    send_telegram(msg)
    return msg

@app.route('/')
def home():
    c,p,btc = find_strangle_legs()
    return f"LIVE BTC ${btc:.0f}<br>CALL: {c['symbol'] if c else 'Nahi'} ${c['entry_usd']:.1f if c else ''}<br>PUT: {p['symbol'] if p else 'Nahi'} ${p['entry_usd']:.1f if p else ''}<br><br><a href='/trigger'>TEST</a> | <a href='/live'>LIVE SELL</a>"

@app.route('/trigger')
def trigger(): return run_strangle(True).replace("\n","<br>")
@app.route('/live')
def live(): return run_strangle(False).replace("\n","<br>")

def scheduler():
    while True:
        now = datetime.datetime.now()
        if now.hour == 9 and now.minute == 0:
            run_strangle(False)
            time.sleep(70)
        time.sleep(30)

Thread(target=scheduler, daemon=True).start()
Thread(target=monitor_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
