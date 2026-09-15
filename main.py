import os, time, hmac, hashlib, json, requests, traceback
from flask import Flask
app = Flask(__name__)

def get_sig(s,m,ts,p,b):
    return hmac.new(s.encode(), (m+ts+p+b).encode(), hashlib.sha256).hexdigest()

def safe_float(v, default=0):
    try:
        if v is None: return default
        return float(v)
    except:
        return default

@app.route("/trigger")
def trigger():
    try:
        api_key=os.getenv("DELTA_API_KEY","").strip()
        api_secret=os.getenv("DELTA_API_SECRET","").strip()
        base_url=os.getenv("DELTA_API_URL","").strip().rstrip('/')

        ts=str(int(time.time())); path="/v2/products"
        sig=get_sig(api_secret,"GET",ts,path,"")
        headers={'api-key':api_key,'timestamp':ts,'signature':sig}

        prods = requests.get(base_url+path, headers=headers, timeout=20).json().get('result',[])
        btc = next((p for p in prods if p['symbol']=='BTCUSD' and p['contract_type']=='perpetual_futures'), None)

        public_url = "https://api.india.delta.exchange"
        now = int(time.time())
        start = now - 10800
        end = now
        url = f"{public_url}/v2/history/candles?symbol=MARK:BTCUSD&resolution=1m&start={start}&end={end}"
        j = requests.get(url, timeout=15).json()
        data = j.get('result', [])

        if len(data) < 30:
            return f"Candle kam hai len {len(data)} Resp {str(j)[:400]}"

        # FIX: None handle
        closes=[safe_float(c.get('close')) for c in data]
        highs=[safe_float(c.get('high')) for c in data]
        lows=[safe_float(c.get('low')) for c in data]
        vols=[safe_float(c.get('volume'), 1) for c in data]

        # VWAP
        cum_tpv=0; cum_vol=0
        vwap_list=[]
        for i in range(len(closes)):
            typical=(highs[i]+lows[i]+closes[i])/3
            cum_tpv+=typical*vols[i]
            cum_vol+=vols[i]
            vwap_list.append(cum_tpv/cum_vol if cum_vol else closes[i])

        # TERI LOGIC - Closed candle pe, live pe nahi
        # -2 = last closed 1m candle
        closed_close = closes[-2]
        closed_vwap = vwap_list[-2]

        # Supertrend on closed candle
        atr_period = 10
        atr = sum([highs[-2-k]-lows[-2-k] for k in range(atr_period)])/atr_period
        hl2 = (highs[-2]+lows[-2])/2
        lower = hl2 - 3*atr
        upper = hl2 + 3*atr

        is_red = closed_close < lower
        is_green = closed_close > upper
        # agar beech me hai to pichle trend se decide karo, yahan simple: vwap se
        if not is_red and not is_green:
            is_green = closed_close > closed_vwap
            is_red = not is_green

        if closed_close < closed_vwap and is_red:
            otype="call_options"
            side_text = f"CALL SELL - Close {closed_close:.2f} < VWAP {closed_vwap:.2f} + ST RED"
        elif closed_close > closed_vwap and is_green:
            otype="put_options"
            side_text = f"PUT SELL - Close {closed_close:.2f} > VWAP {closed_vwap:.2f} + ST GREEN"
        else:
            return f"NO TRADE<br>Closed Candle {closed_close:.2f} VWAP {closed_vwap:.2f}<br>ST Upper {upper:.2f} Lower {lower:.2f}<br>Status {'GREEN' if is_green else 'RED'}<br>Condition match nahi"

        atm_strike = round(closed_close / 200) * 200
        opts=[p for p in prods if p.get('contract_type')==otype and 'BTC' in p['symbol']]
        opts=sorted(opts, key=lambda x: x.get('settlement_time',''))
        first_exp=opts[0].get('settlement_time')
        curr=[p for p in opts if p.get('settlement_time')==first_exp]
        curr=sorted(curr, key=lambda x: abs(float(x['strike_price']) - atm_strike))
        sel=curr[0]

        path_o="/v2/orders"
        payload={"product_id":sel['id'],"size":1,"side":"sell","order_type":"market_order"}
        body=json.dumps(payload); ts2=str(int(time.time()))
        sig2=get_sig(api_secret,"POST",ts2,path_o,body)
        h2={'api-key':api_key,'timestamp':ts2,'signature':sig2,'Content-Type':'application/json'}
        ro=requests.post(base_url+path_o, data=body, headers=h2, timeout=15)

        return f"SUCCESS - {side_text}<br>ATM {atm_strike} Sel {sel['symbol']}<br>Order {ro.status_code} {ro.text[:600]}"

    except Exception as e:
        return f"ERROR:<br>{str(e)}<br><br>{traceback.format_exc()}", 200

@app.route("/")
def home(): return "LIVE - FIXED NoneType + Closed Candle Logic"

if __name__ == "__main__": app.run(host="0.0.0.0", port=10000)
