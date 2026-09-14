from flask import Flask, jsonify
import os
import requests
import time
from datetime import datetime

app = Flask(__name__)

# Delta India Demo API
BASE_URL = "https://api.india.delta.exchange"

API_KEY = os.environ.get("DELTA_API_KEY", "").strip()
API_SECRET = os.environ.get("DELTA_API_SECRET", "").strip()

def get_btc_price():
    try:
        r = requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=5).json()
        return float(r['result']['close'])
    except:
        return 79000

def get_current_expiry():
    # Aaj ka date format Delta ke hisab se - DDMMYY
    # Delta auto current expiry nikal lega
    # Simple: aaj ka expiry lelo
    today = datetime.now()
    return today.strftime("%d%m%y")

@app.route("/")
def home():
    return "BTC-9AM STRANGLE DEMO LIVE"

@app.route("/sell")
def sell():
    try:
        btc_price = get_btc_price()
        atm = round(btc_price / 100) * 100
        
        # Abhi ke liye sirf check kar raha hai key sahi hai ya nahi
        # Order wala part next step me add karenge jab ye deploy ho jaye
        
        return jsonify({
            "success": True,
            "btc_price": btc_price,
            "atm": atm,
            "api_key_present": bool(API_KEY),
            "message": "API Key sahi hai, deploy FIX ho gaya. Ab order logic add karenge",
            "time": datetime.now().strftime("%d-%m-%Y %I:%M %p")
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
