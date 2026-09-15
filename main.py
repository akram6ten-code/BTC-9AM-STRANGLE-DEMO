import os, time, hmac, hashlib, requests, json, threading
from flask import Flask
from datetime import datetime
import pytz
import telegram
from telegram.ext import Updater, CommandHandler

API_KEY = "YAHAN_DEMO_WALI_KEY"
API_SECRET = "YAHAN_DEMO_WALI_SECRET"
TELEGRAM_TOKEN = "YAHAN_TELEGRAM_TOKEN"
CHAT_ID = "YAHAN_CHAT_ID"
BASE_URL = "https://testnet-api.delta.exchange"

app = Flask(__name__)
ist = pytz.timezone('Asia/Kolkata')

def get_price():
    try:
        r = requests.get(f"{BASE_URL}/v2/tickers/BTCUSD", timeout=5)
        return float(r.json()['result']['mark_price'])
    except:
        return 70000

def place_orders():
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    try:
        price = get_price()
        strike = int(round(price/1000)*1000)
        r = requests.get(f"{BASE_URL}/v2/products", params={"contract_types":"call_options,put_options"}, timeout=10)
        products = r.json()['result']
        calls = [p for p in products if p['contract_type']=='call_options' and p['strike_price']==str(strike)]
        puts = [p for p in products if p['contract_type']=='put_options' and p['strike_price']==str(strike)]
        if not calls:
            bot.send_message(chat_id=CHAT_ID, text="Strike nahi mila")
            return
        call = sorted(calls, key=lambda x: x['settlement_time'])[0]
        put = sorted(puts, key=lambda x: x['settlement_time'])[0]

        bot.send_message(chat_id=CHAT_ID, text=f"Strangle lag raha hai: {call['symbol']} + {put['symbol']}")

        for prod in [call, put]:
            ts = str(int(time.time()))
            data = {"product_id": prod['id'], "size": 1, "side": "buy", "order_type": "market_order"}
            payload = json.dumps(data)
            msg = "POST" + ts + "/v2/orders" + "" + payload
            sig = hmac.new(API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
            headers = {"api-key": API_KEY, "timestamp": ts, "signature": sig, "Content-Type": "application/json"}
            requests.post(BASE_URL+"/v2/orders", headers=headers, data=payload, timeout=10)

        bot.send_message(chat_id=CHAT_ID, text="✅ Order History check karo demo.delta.exchange pe")
    except Exception as e:
        bot.send_message(chat_id=CHAT_ID, text=f"Error: {e}")

def start(update, context):
    update.message.reply_text("Bot ON hai ✅ / se trigger hoga, 9 AM auto")

def trigger(update, context):
    update.message.reply_text("Trigger kar raha hu...")
    threading.Thread(target=place_orders).start()

@app.route('/')
def home():
    return "Bot Running"

def run_bot():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("t", trigger)) # /t se trigger
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
