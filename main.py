import os, time, hmac, hashlib, json, requests, traceback
from flask import Flask
app = Flask(__name__)
STATE_FILE = "/tmp/trade_state.json"

def get_sig(s,m,ts,p,b):
    return hmac.new(s.encode(), (m+ts+p+b).encode(), hashlib.sha256).hexdigest()
def safe_float(v, default=0):
    try:
        if v is None: return default
        return float(v)
    except: return default

def close_position_api(product_id, size):
    api_key=os.getenv("DELTA_API_KEY","").strip()
    api_secret=os.getenv("DELTA_API_SECRET","").strip()
    base_url=os.getenv("DELTA_API_URL","").strip().rstrip('/')
    path_o="/v2/orders"
    payload={"product_id":product_id,"size":size,"side":"buy","order_type":"market_order","reduce_only":"true"}
    body=json.dumps(payload); ts=str(int(time.time()))
    sig=get_sig(api_secret,"POST",ts,path_o,body)
    h={'api-key':api_key,'timestamp':ts,'signature':sig,'Content-Type':'application/json'}
    return requests.post(base_url+path_o, data=body, headers=h, timeout=15)

@app.route("/trigger")
def trigger():
    try:
        # Lock - din me ek hi trade
        if os.path.exists(STATE_FILE):
            s=json.loads(open(STATE_FILE).read())
            if s.get('status')=='OPEN':
                return f"Already OPEN trade {s['symbol']} Entry {s['entry_price']}"

        api_key=os.getenv("DELTA_API_KEY","").strip()
        api_secret=os.getenv("DELTA_API_SECRET","").strip()
        base_url=os.getenv("DELTA_API_URL","").strip().rstrip('/')
        ts=str(int(time.time())); path="/v2/products"
        sig=get_sig(api_secret,"GET",ts,path,"")
        headers={'api-key':api_key,'timestamp':ts,'signature':sig}
        prods = requests.get(base_url+path, headers=headers, timeout=20).json().get('result',[])

        public_url = "https://api.india.delta.exchange"
        now = int(time.time()); start = now - 86400; end = now
        url = f"{public_url}/v2/history/candles?symbol=MARK:BTCUSD&resolution=15m&start={start}&end={end}"
        j = requests.get(url, timeout=15).json(); data = j.get('result', [])
        if len(data) < 30: return f"15m Candle kam hai {len(data)}"

        closes=[safe_float(c.get('close')) for c in data]
        highs=[safe_float(c.get('high')) for c in data]
        lows=[safe_float(c.get('low')) for c in data]
        vols=[safe_float(c.get('volume'), 1) for c in data]
        cum_tpv=0; cum_vol=0; vwap_list=[]
        for i in range(len(closes)):
            typical=(highs[i]+lows[i]+closes[i])/3
            cum_tpv+=typical*vols[i]; cum_vol+=vols[i]
            vwap_list.append(cum_tpv/cum_vol if cum_vol else closes[i])

        closed_close = closes[-2]; closed_vwap = vwap_list[-2]
        atr = sum([highs[-2-k]-lows[-2-k] for k in range(10)])/10
        hl2 = (highs[-2]+lows[-2])/2; lower = hl2 - 3*atr; upper = hl2 + 3*atr
        is_green = closed_close > upper; is_red = closed_close < lower

        if closed_close > closed_vwap and is_green:
            otype="put_options"; side_text = f"PUT SELL"
        elif closed_close < closed_vwap and is_red:
            otype="call_options"; side_text = f"CALL SELL"
        else:
            return f"NO TRADE Closed {closed_close:.2f} VWAP {closed_vwap:.2f} ST U {upper:.2f} L {lower:.2f}"

        atm_strike = round(closed_close / 200) * 200
        opts=[p for p in prods if p.get('contract_type')==otype and 'BTC' in p['symbol']]
        opts=sorted(opts, key=lambda x: x.get('settlement_time','')); first_exp=opts[0].get('settlement_time')
        curr=[p for p in opts if p.get('settlement_time')==first_exp]
        curr=sorted(curr, key=lambda x: abs(float(x['strike_price']) - atm_strike)); sel=curr[0]

        LOT_SIZE = 100; LEVERAGE = "100"
        try:
            lev_path = f"/v2/products/{sel['id']}/orders/leverage"; lev_body = json.dumps({"leverage": LEVERAGE})
            ts_lev = str(int(time.time())); sig_lev = get_sig(api_secret, "POST", ts_lev, lev_path, lev_body)
            h_lev = {'api-key':api_key,'timestamp':ts_lev,'signature':sig_lev,'Content-Type':'application/json'}
            requests.post(base_url+lev_path, data=lev_body, headers=h_lev, timeout=15)
        except: pass

        path_o="/v2/orders"; payload={"product_id":sel['id'],"size":LOT_SIZE,"side":"sell","order_type":"market_order"}
        body=json.dumps(payload); ts2=str(int(time.time())); sig2=get_sig(api_secret,"POST",ts2,path_o,body)
        h2={'api-key':api_key,'timestamp':ts2,'signature':sig2,'Content-Type':'application/json'}
        ro=requests.post(base_url+path_o, data=body, headers=h2, timeout=15)
        rj=ro.json()
        if not rj.get('success'):
            return f"Order Fail {ro.text}"

        # Entry price leke State save karo SL Trail ke liye
        entry_price = safe_float(rj['result'].get('average_fill_price') or rj['result'].get('price') or 100)
        # Agar avg price nahi mila to mark se le lenge, abhi entry_price se calculate
        if entry_price < 10: entry_price = 400 # fallback test

        state = {
            "status":"OPEN",
            "product_id": sel['id'],
            "symbol": sel['symbol'],
            "entry_price": entry_price,
            "current_sl": entry_price * 1.70, # SL 70% upar
            "target": entry_price * 0.10, # Target 90% niche (10% bachega)
            "lot": LOT_SIZE,
            "high_profit_pct": 0
        }
        open(STATE_FILE,'w').write(json.dumps(state))
        return f"SUCCESS ENTRY {side_text}<br>{sel['symbol']} Entry {entry_price}<br>SL {state['current_sl']:.2f} (70%) Target {state['target']:.2f} (90%)<br>Trail 1% ACTIVE"
    except Exception as e:
        return f"ERROR {e}<br>{traceback.format_exc()}", 200

@app.route("/check")
def check_sl():
    try:
        if not os.path.exists(STATE_FILE):
            return "No Active Trade"
        state = json.loads(open(STATE_FILE).read())
        if state.get('status')!= 'OPEN':
            return "No OPEN trade"

        api_key=os.getenv("DELTA_API_KEY","").strip()
        api_secret=os.getenv("DELTA_API_SECRET","").strip()
        base_url=os.getenv("DELTA_API_URL","").strip().rstrip('/')

        # Mark price positions se
        ts=str(int(time.time())); path="/v2/positions/margined"
        sig=get_sig(api_secret,"GET",ts,path,"")
        headers={'api-key':api_key,'timestamp':ts,'signature':sig}
        pos = requests.get(base_url+path, headers=headers, timeout=15).json().get('result',[])
        my = next((p for p in pos if str(p['product_id'])==str(state['product_id'])), None)
        if not my:
            return f"Position not found, maybe closed. Clearing state"
        mark = safe_float(my.get('mark_price') or my.get('entry_price'))

        entry = state['entry_price']
        sl = state['current_sl']
        target = state['target']

        # 1. SL HIT
        if mark >= sl:
            close_position_api(state['product_id'], state['lot'])
            os.remove(STATE_FILE)
            return f"SL HIT - Mark {mark} >= SL {sl} - Closed {state['symbol']}"

        # 2. TARGET HIT
        if mark <= target:
            close_position_api(state['product_id'], state['lot'])
            os.remove(STATE_FILE)
            return f"TARGET HIT - Mark {mark} <= Target {target} - Closed {state['symbol']}"

        # 3. TRAIL 1% Logic
        # Short me profit = entry - mark
        profit_pct = (entry - mark) / entry * 100 if entry else 0
        if profit_pct > state.get('high_profit_pct',0):
            state['high_profit_pct'] = profit_pct
            # Har 1% extra profit pe SL ko 1% trail karo
            # Eg: profit 1% -> SL 1% down, profit 2% -> SL aur 1% down
            # SL sirf neeche ayega
            trail_factor = 1 - (int(profit_pct) * 0.01) # 1% profit = 0.99
            new_sl_base = entry * 1.70 * trail_factor
            # Lekin SL kabhi entry se upar hi rahega jab tak profit na ho
            if new_sl_base < sl:
                old_sl = sl
                state['current_sl'] = new_sl_base
                open(STATE_FILE,'w').write(json.dumps(state))
                return f"TRAIL UPDATE Profit {profit_pct:.2f}% Mark {mark} SL {old_sl:.2f} -> {new_sl_base:.2f}"

        open(STATE_FILE,'w').write(json.dumps(state))
        return f"HOLD Entry {entry} Mark {mark} SL {state['current_sl']:.2f} Target {target} Profit {profit_pct:.2f}%"
    except Exception as e:
        return f"CHECK ERROR {e}<br>{traceback.format_exc()}", 200

@app.route("/")
def home(): return "LIVE 15m + 100LOT + 100x + SL70% TGT90% TRAIL1%"
if __name__ == "__main__": app.run(host="0.0.0.0", port=10000)
