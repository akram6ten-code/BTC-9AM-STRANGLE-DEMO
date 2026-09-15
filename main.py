import os, time, hmac, hashlib, json, requests, pandas as pd
from flask import Flask
app = Flask(__name__)

def get_sig(s,m,ts,p,b): return hmac.new(s.encode(), (m+ts+p+b).encode(), hashlib.sha256).hexdigest()

@app.route("/trigger")
def trigger():
    api_key=os.getenv("DELTA_API_KEY","").strip()
    api_secret=os.getenv("DELTA_API_SECRET","").strip()
    base_url=os.getenv("DELTA_API_URL","").strip().rstrip('/')

    # Products lo
    ts=str(int(time.time())); path="/v2/products"
    sig=get_sig(api_secret,"GET",ts,path,"")
    headers={'api-key':api_key,'timestamp':ts,'signature':sig}
    prods = requests.get(base_url+path, headers=headers, timeout=20).json().get('result',[])
    if not prods: return "Products nahi aaye"

    btc = next((p for p in prods if p['symbol']=='BTCUSD' and p['contract_type']=='perpetual_futures'), None)
    if not btc: return "BTCUSD nahi mila"

    # 15m candles se VWAP + Supertrend
    try:
        path_c = f"/v2/history/candles?resolution=15m&symbol=MARK:{btc['id']}&limit=100"
        r = requests.get(base_url+path_c, headers=headers, timeout=15).json().get('result',[])
        df = pd.DataFrame(r)
        df['close']=df['close'].astype(float); df['high']=df['high'].astype(float); df['low']=df['low'].astype(float); df['volume']=df['volume'].astype(float)

        typical=(df['high']+df['low']+df['close'])/3
        vwap=(typical*df['volume']).cumsum()/df['volume'].cumsum()

        hl2=(df['high']+df['low'])/2
        atr=(df['high']-df['low']).rolling(10).mean()
        upper=hl2+3*atr; lower=hl2-3*atr
        is_up=True
        for i in range(1,len(df)):
            if df['close'].iloc[i] <= lower.iloc[i-1]: is_up=False
            elif df['close'].iloc[i] >= upper.iloc[i-1]: is_up=True

        close=df['close'].iloc[-1]; vwap_last=vwap.iloc[-1]
    except Exception as e:
        return f"Candle error {e}"

    # Condition
    otype=None
    if close < vwap_last and not is_up: otype="call_options"
    elif close > vwap_last and is_up: otype="put_options"
    else: return f"NO TRADE Close {close:.1f} VWAP {vwap_last:.1f} Uptrend {is_up}"

    # 1st OTM Current Daily Expiry
    opts=[p for p in prods if p.get('contract_type')==otype and 'BTC' in p.get('symbol','')]
    opts=sorted(opts, key=lambda x: x.get('settlement_time',''))
    if not opts: return f"{otype} nahi mile"
    first_exp=opts[0].get('settlement_time')
    curr=[p for p in opts if p.get('settlement_time')==first_exp]

    if otype=="call_options":
        valid=[p for p in curr if float(p.get('strike_price',0)) > close]
        valid=sorted(valid, key=lambda x: float(x['strike_price']))
    else:
        valid=[p for p in curr if float(p.get('strike_price',0)) < close]
        valid=sorted(valid, key=lambda x: float(x['strike_price']), reverse=True)

    if not valid: return f"OTM {otype} nahi mila spot {close}"
    selected=valid[0] # 1st OTM

    # SELL 50 Lot
    path_o="/v2/orders"
    payload={"product_id":selected['id'],"size":50,"side":"sell","order_type":"market_order"}
    body=json.dumps(payload); ts2=str(int(time.time()))
    sig2=get_sig(api_secret,"POST",ts2,path_o,body)
    h2={'api-key':api_key,'timestamp':ts2,'signature':sig2,'Content-Type':'application/json'}
    ro=requests.post(base_url+path_o, data=body, headers=h2, timeout=15)

    return f"DONE {otype} {selected['symbol']} Strike {selected['strike_price']} | Close {close:.1f} VWAP {vwap_last:.1f} Uptrend {is_up} | {ro.status_code} {ro.text[:300]}"

@app.route("/")
def home(): return "Live - 1st OTM 15m VWAP+ST"

if __name__ == "__main__": app.run(host="0.0.0.0", port=10000)
