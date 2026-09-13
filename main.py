import os, hmac, hashlib, json, time, requests, datetime
from flask import Flask
from threading import Thread

app = Flask(__name__)

# Render ke Environment se ayega
DELTA_API_KEY = os.getenv("DELTA_API_KEY", "")
DELTA_API_SECRET = os.getenv("DELTA_API_SECRET", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

PREMIUM_MIN = 80
PREMIUM_MAX = 90

def get_signature(secret, message):
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

def delta_request(method, path, payload=""):
    timestamp = str(int(time.time()))
    message = method + timestamp + path + payload
    signature = get_signature(DELTA_API_SECRET, message)
    headers = {
        'api-key': DELTA_API_KEY,
        'timestamp': timestamp,
        'signature': signature,
        'User-Agent': 'python-bot'
    }
    url = f"https://api.india.delta.exchange{path}"
    if method == "GET":
        return requests.get(url, headers=headers, timeout=10).json()
    else:
        headers['Content-Type'] = 'application/json'
        return requests.post(url, headers=headers, data=payload, timeout=10).json()

def get_options_in_range():
    # BTC ke saare options lao
    try:
        res = requests.get("https://api.india.delta.exchange/v2/tickers", timeout=10).json()
        valid = []
        for t in res['result']:
            # Sirf kal expiry wala BTC option
            if 'BTC' in t['symbol'] and t['symbol'].endswith('C') or t['symbol'].endswith('P'):
                if t.get('mark_price'):
                    price_usd = float(t['mark_price']) * float(t.get('spot_price', 115000))
                    # agar premium 80-90$ ke beech hai
                    if PREMIUM_MIN <= price_usd <= PREMIUM_MAX:
                        valid.append(f"{t['symbol']} -> ${price_usd:.2f}")
        return valid[:5] # top 5
    except Exception as e:
        return [f"Error: {e}"]

@app.route('/')
def home():
    data = get_options_in_range()
    return f"<h2>LIVE</h2> 80-90$ Filter ke options:<br>{'<br>'.join(data)}<br><br><a href='/trigger'>Trigger</a>"

@app.route('/trigger')
def trigger():
    return home()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
