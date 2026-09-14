import os, time, hmac, hashlib, json, requests
from flask import Flask
app = Flask(__name__)

URL = "https://api.india.delta.exchange"
KEY = os.environ.get("DELTA_API_KEY")
SECRET = os.environ.get("DELTA_API_SECRET")
BOT = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT = os.environ.get("TELEGRAM_CHAT_ID")

def tg(m):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", json={"chat_id": CHAT, "text": m}, timeout=10)
    except: pass

def sign(m,p,js=""):
    ts=str(int(time.time()))
    s=hmac.new(SECRET.encode(), (m+ts+p+js).encode(), hashlib.sha256).hexdigest()
    return s,ts

def req(method, path, payload=None):
    js=json.dumps(payload) if payload else ""
    sig,ts=sign(method,path,js)
    h={'api-key':KEY,'timestamp':ts,'signature':sig,'Content-Type':'application/json'}
    u=URL+path
    r=requests.request(method,u,headers=h,data=js,timeout=15)
    return r.json()

def get_atm():
    # Spot
    spot=float(requests.get(f"{URL}/v2/tickers/BTCUSD",timeout=10).json()['result']['spot_price'])
    # Products
    prods=req("GET","/v2/products").get('result',[])
    opts=[p for p in prods if p.get('underlying_asset',{}).get('symbol')=='BTC' and 'option' in p.get('contract_type','')]
    opts.sort(key=lambda x:x.get('settlement_time',''))
    curr_exp=opts[0]['settlement_time']
    curr=[p for p in opts if p.get('settlement_time')==curr_exp]
    # ATM
    atm=min(curr, key=lambda x: abs(float(x['strike_price'])-spot))
    strike=float(atm['strike_price'])
    ce=pe=None
    for p in curr:
        if float(p['strike_price'])==strike:
            if p['contract_type']=='call_options': ce=p['symbol']
            if p['contract_type']=='put_options': pe=p['symbol']
    return ce,pe,spot,strike,curr_exp

@app.route('/')
def home():
    ce,pe,spot,strike,exp=get_atm()
    return f"BTC:{spot} STRIKE:{strike} CE:{ce} PE:{pe} <br><a href='/sell'>/sell pe click kar</a>"

@app.route('/sell')
def sell():
    ce,pe,spot,strike,exp=get_atm()
    r1=req("POST","/v2/orders",{"product_symbol":ce,"size":1,"side":"sell","order_type":"market_order"})
    r2=req("POST","/v2/orders",{"product_symbol":pe,"size":1,"side":"sell","order_type":"market_order"})
    msg=f"✅ TEST SOLD\nBTC:{spot}\nStrike:{strike}\nCE:{ce}\nPE:{pe}\nCE_Res:{r1}\nPE_Res:{r2}"
    tg(msg)
    return msg.replace("\n","<br>")

app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))
