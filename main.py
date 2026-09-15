import os, time, hmac, hashlib, json, requests
from flask import Flask
app = Flask(__name__)

def get_sig(s,m,ts,p,b):
    return hmac.new(s.encode(), (m+ts+p+b).encode(), hashlib.sha256).hexdigest()

@app.route("/trigger")
def trigger():
    api_key=os.getenv("DELTA_API_KEY","").strip()
    api_secret=os.getenv("DELTA_API_SECRET","").strip()
    base_url=os.getenv("DELTA_API_URL","").strip().rstrip('/')

    ts=str(int(time.time())); path="/v2/products"
    sig=get_sig(api_secret,"GET",ts,path,"")
    headers={'api-key':api_key,'timestamp':ts,'signature':sig}

    try:
        prods = requests.get(base_url+path, headers=headers, timeout=20).json().get('result',[])
    except Exception as e:
        return f"Products API fail {e}"

    btc = next((p for p in prods if p['symbol']=='BTCUSD' and p['contract_type']=='perpetual_futures'), None)
    if not btc: return "BTCUSD perp nahi mila"

    # FIX: Candle Public Live Server se lete hain - Demo pe nahi milta
    # Yahan auth ki zarurat nahi
    try:
        public_url = "https://api.india.delta.exchange"
        candle_path = f"/v2/history/candles?resolution=1m&symbol=MARK:BTCUSD&limit=100"
        r = requests.get(public_url + candle_path, timeout=15).json()
        data = r.get('result', [])
        if len(data) < 20:
            # fallback 15m
            candle_path = f"/v2/history/candles?resolution=15m&symbol=MARK:BTCUSD&limit=100"
            r = requests.get(public_url + candle_path, timeout=15).json()
            data = r.get('result', [])
    except Exception as e:
        return f"Public Candle API fail {e}"

    if len(data) < 20:
        return f"Candle abhi bhi fail hai len {len(data)} - Resp {str(data)[:200]}"

    closes=[float(c['close']) for c in data]
    highs=[float(c['high']) for c in data]
    lows=[float(c['low']) for c in data]
    vols=[float(c['volume']) for c in data]

    # VWAP
    cum_tpv=0; cum_vol=0
    vwap_list=[]
    for i in range(len(closes)):
        typical=(highs[i]+lows[i]+closes[i])/3
        cum_tpv+=typical*vols[i]
        cum_vol+=vols[i]
        vwap_list.append(cum_tpv/cum_vol if cum_vol else closes[i])

    close=closes[-1]
    vwap=vwap_list[-1]

    atr = sum([highs[-i]-lows[-i] for i in range(1,11)])/10 if len(highs)>=11 else highs[-1]-lows[-1]
    hl2=(highs[-1]+lows[-1])/2
    upper=hl2+3*atr
    lower=hl2-3*atr

    is_up=True
    if close <= lower: is_up=False
    elif close >= upper: is_up=True
    else: is_up = close > vwap

    if close < vwap and not is_up: otype="call_options"
    elif close > vwap and is_up: otype="put_options"
    else: return f"NO TRADE<br>Close {close:.2f} VWAP {vwap:.2f} ST {'GREEN' if is_up else 'RED'}<br>Public Candle OK {len(data)} candles"

    atm_strike = round(close / 200) * 200

    opts=[p for p in prods if p.get('contract_type')==otype and 'BTC' in p['symbol']]
    opts=sorted(opts, key=lambda x: x.get('settlement_time',''))
    if not opts: return f"{otype} nahi mila"
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

    return f"SUCCESS FIXED<br>Spot {close:.2f} VWAP {vwap:.2f} ST {'GREEN' if is_up else 'RED'}<br>ATM {atm_strike} Selected {sel['symbol']} Strike {sel['strike_price']}<br>Order {ro.status_code} {ro.text[:500]}"

@app.route("/")
def home(): return "LIVE - FIXED PUBLIC CANDLE - 1m VWAP+ST"

if __name__ == "__main__": app.run(host="0.0.0.0", port=10000)
