import os
import time
import hmac
import hashlib
import requests
import json
from datetime import datetime, timedelta
import pytz
from flask import Flask
import threading
import telegram
from telegram.ext import Updater, CommandHandler

# ========== TUMHARI KEYS YAHA DAALO ==========
DELTA_API_KEY = "KCdIJwHwIFkcVFLynabxJ0kkL1gLZ5"
DELTA_API_SECRET = "NEHJCYK5fihJpCeaJh7X6xQgxn7jYpGmWpzrAOj15F9vRcQa2yAqtYFYw47I"
TELEGRAM_BOT_TOKEN = "8470029646:AAHuy2_FeSA4DZRz6L25n0LvSJgX-r9OiAU"
TELEGRAM_CHAT_ID = "6107508649"

# Global Demo ka sahi URL - India wala nahi
BASE_URL = "https://testnet-api.delta.exchange"

# Strategy Setting
SYMBOL = "BTCUSD"
CAPITAL_PERCENT = 10 # 10% capital use
LOT_SIZE = 1
STOPLOSS_PERCENT = 50
TARGET_PERCENT = 100

app = Flask(__name__)
bot = telegram.Bot(token=TELEGRAM_TOKEN)
ist = pytz.timezone('Asia/Kolkata')

def generate_signature(method, endpoint, query_string="", payload=""):
    timestamp = str(int(time.time()))
    message = method + timestamp + endpoint + query_string + payload
    signature = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return signature, timestamp

def api_call(method, endpoint, params=None, data=None):
    url = BASE_URL + endpoint
    query_string = ""
    payload = ""
    if params:
        query_string = "?" + "&".join([f"{k}={v}" for k,v in params.items()])
    if data:
        payload = json.dumps(data)

    sig, ts = generate_signature(method, endpoint, query_string, payload)
    headers = {
        "api-key": API_KEY,
        "timestamp": ts,
        "signature": sig,
        "Content-Type": "application/json"
    }
    try:
        if method == "GET":
            r = requests.get(url + query_string, headers=headers, timeout=10)
        else:
            r = requests.post(url, headers=headers, data=payload, timeout=10)
        print(f"API Response: {r.text}")
        return r.json()
    except Exception as e:
        print(f"API Error: {e}")
        return {"success": False, "error": str(e)}

def get_btc_price():
    try:
        r = requests.get(f"{BASE_URL}/v2/tickers/{SYMBOL}", timeout=5)
        return float(r.json()['result']['mark_price'])
    except:
        return 75000

def get_nearest_options():
    # 9 AM pe nearest expiry ke ATM ke aas paas Call Put lega
    price = get_btc_price()
    strike = int(round(price / 1000) * 1000) # Round to 1000
    try:
        r = requests.get(f"{BASE_URL}/v2/products", params={"contract_types": "call_options,put_options"}, timeout=10)
        products = r.json()['result']
        # Next expiry wala option dhoondho
        today = datetime.now(ist).date()
        calls = [p for p in products if p['contract_type']=='call_options' and p['strike_price']==str(strike)]
        puts = [p for p in products if p['contract_type']=='put_options' and p['strike_price']==str(strike)]
        if calls and puts:
            # sabse nazdeek expiry lo
            calls_sorted = sorted(calls, key=lambda x: x['settlement_time'])
            puts_sorted = sorted(puts, key=lambda x: x['settlement_time'])
            return calls_sorted[0], puts_sorted[0]
    except Exception as e:
        print(f"Option fetch error: {e}")
    return None, None

def place_strangle():
    call_opt, put_opt = get_nearest_options()
    if not call_opt:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ Call/Put option nahi mila")
        return

    msg = f"🔥 9 AM STRANGLE PLACING\nBTC Price: {get_btc_price()}\nCall: {call_opt['symbol']} @ {call_opt['mark_price']}\nPut: {put_opt['symbol']} @ {put_opt['mark_price']}"
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

    # Call Buy
    api_call("POST", "/v2/orders", data={
        "product_id": call_opt['id'],
        "size": LOT_SIZE,
        "side": "buy",
        "order_type": "market_order"
    })
    # Put Buy
    api_call("POST", "/v2/orders", data={
        "product_id": put_opt['id'],
        "size": LOT_SIZE,
        "side": "buy",
        "order_type": "market_order"
    })
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="✅ Dono orders place ho gaye. Order History check karo demo pe.")

def scheduler_loop():
    while True:
        now = datetime.now(ist)
        if now.hour == 9 and now.minute == 0 and now.second < 10:
            place_strangle()
            time.sleep(60) # 1 min ruk jao taaki dobara na lage
        time.sleep(1)

# Telegram Commands
def start(update, context):
    update.message.reply_text("Bot ON hai ✅\n/start - bot check\n/ - manual strangle trigger karega\n9 AM pe auto trigger hoga IST")

def trigger(update, context):
    update.message.reply_text("Manual trigger kar raha hu...")
    place_strangle()

@app.route('/')
def home():
    return "BTC 9AM Strangle Demo Bot Running - Global Demo"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    # Telegram Bot Thread
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("", trigger)) # / command
    updater.start_polling()

    # Scheduler Thread
    threading.Thread(target=scheduler_loop, daemon=True).start()

    # Flask Thread
    run_flask()
