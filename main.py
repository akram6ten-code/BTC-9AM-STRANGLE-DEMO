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
    prods = requests.get(base_url+path, headers=headers, timeout=20).json().get('result',[])
    btc = next((p for p in prods if p['symbol']=='BTCUSD' and p['contract_type']=='perpetual_futures'), None)
    if not btc: return "BTCUSD nahi mila"

    # 1 MIN Candle - Supertrend + VWAP
    path_c = f"/v2/history/candles?resolution=1m&symbol=MARK:{btc['id']}&limit=100"
    data = requests.get(base_url+path_c, headers=headers, timeout=15).json().get('result',[])
    if len(data) < 20: return f"1m data kam hai {len(data)}"

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

    # Supertrend 10,3
    period=10; mult=3.0
    atr = sum([highs[-i]-lows[-i] for i in range(1,11)])/10
    hl2 = (highs[-1]+lows[-1])/2
    upper = hl2 + mult*atr
    lower = hl2 - mult*atr

    # Direction check - pichle candle se
    prev_close=closes[-2]
    prev_hl2=(highs[-2]+lows[-2])/2
    prev_upper=prev_hl2+mult*atr
    prev_lower=prev_hl2-mult*atr

    is_up=True
    if close <= prev_lower:
        is_up=False # RED - Down trend
    elif close >= prev_upper:
        is_up=True # GREEN - Up trend
    else:
        # Agar beech me hai toh VWAP se decide karo
        is_up = close > vwap

    # FINAL CONDITION - Dono compulsory
    otype=None
    reason=""
    if close < vwap and not is_up:
        otype="call_options"
        reason=f"Down Trend CONFIRMED: Close {close:.2f} < VWAP {vwap:.2f} AND Supertrend RED"
    elif close > vwap and is_up:
        otype="put_options"
        reason=f"Up Trend CONFIRMED: Close {close:.2f} > VWAP {vwap:.2f} AND Supertrend GREEN"
    else:
        return f"NO TRADE - Condition fail<br>Close {close:.2f} VWAP {vwap:.2f} Supertrend {'GREEN' if is_up else 'RED'}<br>Entry ke liye VWAP + Supertrend dono chahiye"

    # ATM Strike - 200 ka multiple
    atm_strike = round(close / 200) * 200

    # Daily expiry ka ATM uthao
    opts=[p for p in prods if p.get('contract_type')==otype and 'BTC' in p['symbol']]
    opts=sorted(opts, key=lambda x: x.get('settlement_time',''))
    if not opts: return f"{otype} nahi mila"
    first_exp=opts[0].get('settlement_time')
    curr=[p for p in opts if p.get('settlement_time')==first_exp]
    curr=sorted(curr, key=lambda x: abs(float(x['strike_price']) - atm_strike))
    sel=curr[0]

    # SELL - Size 1 se test kar, baad me 50 kar dena
    path_o="/v2/orders"
    payload={"product_id":sel['id'],"size":1,"side":"sell","order_type":"market_order"}
    body=json.dumps(payload); ts2=str(int(time.time()))
    sig2=get_sig(api_secret,"POST",ts2,path_o,body)
    h2={'api-key':api_key,'timestamp':ts2,'signature':sig2,'Content-Type':'application/json'}
    ro=requests.post(base_url+path_o, data=body, headers=h2, timeout=15)

    return f"SUCCESS<br>{reason}<br>Selected ATM {sel['symbol']} Strike {sel['strike_price']} Spot {close:.2f}<br>Expiry {first_exp}<br>Order {ro.status_code} {ro.text}"

@app.route("/")
def home(): return "LIVE - 1m VWAP + Supertrend COMPULSORY - ATM"

if __name__ == "__main__": app.run(host="0.0.0.0", port=10000)
