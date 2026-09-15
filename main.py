import os, time, hmac, hashlib, json, requests
from flask import Flask

app = Flask(__name__)

# Delta India Demo ka sahi URL
URLS = [
    "https://cdn-ind.testnet.deltaex.org",
    "https://cdn-ind-demo.deltaex.org", 
    "https://api.india.delta.exchange"
]

def place_order_for_url(base_url, api_key, api_secret):
    try:
        path = "/v2/orders"
        url = base_url + path
        # BTC Options ka symbol demo pe
        payload = {
            "product_id": 1, # BTCUSD - pehle isi pe test karte hain
            "size": 1,
            "side": "buy",
            "order_type": "market_order"
        }
        body = json.dumps(payload)
        timestamp = str(int(time.time()))
        signature_data = "POST" + timestamp + path + body
        signature = hmac.new(api_secret.encode(), signature_data.encode(), hashlib.sha256).hexdigest()
        headers = {
            'api-key': api_key,
            'timestamp': timestamp,
            'signature': signature,
            'Content-Type': 'application/json'
        }
        r = requests.post(url, data=body, headers=headers, timeout=10)
        return r.status_code, r.text
    except Exception as e:
        return 500, str(e)

@app.route("/")
def home():
    return "Bot Live - Demo.delta.exchange Fix Applied"

@app.route("/trigger")
def trigger():
    api_key = os.getenv("DELTA_API_KEY","").strip()
    api_secret = os.getenv("DELTA_API_SECRET","").strip()
    if not api_key or not api_secret:
        return "Render me DELTA_API_KEY / SECRET khali hai"

    results = []
    for base_url in URLS:
        code, text = place_order_for_url(base_url, api_key, api_secret)
        results.append(f"{base_url} => {code} {text[:200]}")
        if code == 200 or code == 201:
            return f"SUCCESS: Key kaam kar gayi is URL pe: {base_url}<br><br>{text}"
    
    return "<br><br>".join(results) + "<br><br>NOTE: demo.delta.exchange ki key sirf cdn-ind.testnet pe kaam karegi - ye wahi check ho rahi hai"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
