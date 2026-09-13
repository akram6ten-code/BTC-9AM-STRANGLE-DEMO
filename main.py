from flask import Flask
import os
import time
import datetime
import requests

app = Flask(__name__)

# DELTA CONFIG - Render me ENV me dalna
API_KEY = os.getenv("DELTA_API_KEY", "demo")
API_SECRET = os.getenv("DELTA_API_SECRET", "demo")

# 9AM STRANGLE 80-90 PREMIUM LOGIC
def get_btc_price():
    try:
        r = requests.get("https://api.delta.exchange/v2/tickers/BTCUSD", timeout=5).json()
        return float(r['result']['mark_price'])
    except:
        return 115000.0 # fallback

def find_strikes_for_premium():
    btc_price = get_btc_price()
    # Ye demo logic hai - Real me Delta options chain se LTP lena padega
    # Target premium 80-90 USDT
    # Rough: OTM ~ 2-3% away
    target_premium = 85
    
    # Simple calc: CE strike = spot + 2500, PE strike = spot - 2500 for 80-90 range
    # Tum isko apne hisab se adjust karna
    ce_strike = round((btc_price + 2500) / 100) * 100
    pe_strike = round((btc_price - 2500) / 100) * 100
    
    return {
        "btc_price": btc_price,
        "ce_strike": ce_strike,
        "pe_strike": pe_strike,
        "target_premium": target_premium
    }

def run_strangle():
    now_ist = datetime.datetime.now() + datetime.timedelta(hours=5, minutes=30)
    # 9:00 AM IST check
    if now_ist.hour == 9 and now_ist.minute < 5:
        data = find_strikes_for_premium()
        print(f"[9AM TRIGGER] BTC: {data['btc_price']} | SELL {data['pe_strike']} PE @ ~85$ + SELL {data['ce_strike']} CE @ ~85$")
        # Yahan pe Delta sell order lagega
        # place_order(f"C-{data['ce_strike']}", "sell")
        # place_order(f"P-{data['pe_strike']}", "sell")
        return True
    return False

@app.route('/')
def home():
    data = find_strikes_for_premium()
    return f"BTC 9AM STRANGLE DEMO LIVE | BTC Price: {data['btc_price']} | CE: {data['ce_strike']} PE: {data['pe_strike']} @ 80-90$ | IST Time: {datetime.datetime.now() + datetime.timedelta(hours=5, minutes=30)}"

@app.route('/trigger')
def trigger():
    ran = run_strangle()
    if ran:
        return "9AM STRANGLE TRIGGERED - Check logs"
    else:
        return "Not 9AM yet - Bot waiting for 9AM IST"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
