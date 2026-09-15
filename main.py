from flask import Flask
import os, time, hmac, hashlib, json, requests
app = Flask(__name__)

API_KEY = os.environ.get("DELTA_API_KEY","").strip()
API_SECRET = os.environ.get("DELTA_API_SECRET","").strip()

def try_auth(base_url):
    try:
        ts = str(int(time.time()))
        msg = f"GET{ts}/v2/wallet/balances"
        sig = hmac.new(API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig}
        r = requests.get(base_url+"/v2/wallet/balances", headers=headers, timeout=10)
        return r.status_code, r.text[:500], base_url
    except Exception as e:
        return 0, str(e), base_url

@app.route('/')
def home():
    return f"Key: {API_KEY[:4]}...{API_KEY[-3:]} | <a href='/trigger'>CLICK TO TRIGGER</a>"

@app.route('/trigger')
def trigger():
    # Pehle check karo key kahan ki hai
    urls = ["https://testnet-api.delta.exchange", "https://api.india.delta.exchange", "https://api.delta.exchange"]
    working_url = None
    logs = []
    for url in urls:
        code, txt, _ = try_auth(url)
        logs.append(f"{url} => {code} | {txt[:200]}")
        if code==200:
            working_url = url
            break

    if not working_url:
        return "<br>".join(logs) + "<br><br>FAIL: Kisi bhi URL pe Key kaam nahi kar rahi. Key me space hai kya check karo Render Environment me."

    # Ab usi working URL pe order maro
    BASE_URL = working_url
    try:
        prods = requests.get(f"{BASE_URL}/v2/products", timeout=15).json()['result']
        strike=76000
        calls = [p for p in prods if p.get('contract_type')=='call_options' and 'BTC' in p.get('symbol','') and f"-{strike}-" in p.get('symbol','')]
        puts = [p for p in prods if p.get('contract_type')=='put_options' and 'BTC' in p.get('symbol','') and f"-{strike}-" in p.get('symbol','')]

        if not calls: calls = [p for p in prods if p.get('contract_type')=='call_options' and 'BTC' in p.get('symbol','') and str(strike) in p.get('symbol','')]
        if not puts: puts = [p for p in prods if p.get('contract_type')=='put_options' and 'BTC' in p.get('symbol','') and str(strike) in p.get('symbol','')]

        call = sorted(calls, key=lambda x: x['settlement_time'])[0]
        put = sorted(puts, key=lambda x: x['settlement_time'])[0]

        out = [f"SUCCESS: Key kaam kar gayi is URL pe: {BASE_URL}", f"CALL: {call['symbol']}", f"PUT: {put['symbol']}"] + logs

        for prod in [call, put]:
            ts = str(int(time.time()))
            body = {"product_id": prod['id'], "size": 1, "side": "sell", "order_type": "market_order"}
            payload = json.dumps(body, separators=(',', ':')) # no spaces - Delta ko aise chahiye
            sig = hmac.new(API_SECRET.encode(), (f"POST{ts}/v2/orders{payload}").encode(), hashlib.sha256).hexdigest()
            headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
            r = requests.post(BASE_URL+"/v2/orders", headers=headers, data=payload, timeout=15)
            out.append(f"ORDER {prod['symbol']} => {r.status_code} {r.text[:800]}")
        return "<br><br>".join(out)
    except Exception as e:
        import traceback
        return "<br>".join(logs) + f"<br><br>Error: {traceback.format_exc()}"

if __name__=="__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))
