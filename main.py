import time, threading
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')
current_pos = {} # {'CE': {...}, 'PE': {...}}
last_trade_date = None

def get_atm():
    price = float(delta_client.get_ticker('BTCUSD')['close']) # tera wala function use karna
    return round(price / 100) * 100

def place_sell(symbol):
    order = delta_client.place_order(symbol=symbol, side='sell', size=100, leverage=200, type='market')
    entry = float(order['avg_price'] or order['price'])
    current_pos[symbol] = {
        'entry': entry,
        'sl': entry * 1.5, # 50% SL
        'target': entry * 0.5, # 50% Target
        'sl_moved_to_cost': False
    }
    print(f"SELL {symbol} @ {entry}")
    return symbol

def deploy_both():
    atm = get_atm()
    expiry = get_current_expiry() # tera existing
    ce = f"C-BTC-{atm+100}-{expiry}"
    pe = f"P-BTC-{atm-100}-{expiry}"
    place_sell(ce)
    place_sell(pe)

def close_leg(symbol):
    delta_client.place_order(symbol=symbol, side='buy', size=100, type='market')
    if symbol in current_pos: del current_pos[symbol]

def monitor():
    global current_pos
    while True:
        now = datetime.now(IST)
        # 5 PM to 6:30 PM - NO TRADE ZONE
        if now.hour == 17 or (now.hour == 18 and now.minute < 30):
            if current_pos:
                print("5 PM - Closing all")
                for sym in list(current_pos.keys()): close_leg(sym)
            time.sleep(60)
            continue

        # Agar position khali hai aur trading time hai to naya deploy
        if not current_pos and (now.hour < 17 or now.hour >= 18):
            deploy_both()

        # SL / Target Check
        for sym in list(current_pos.keys()):
            ltp = float(delta_client.get_ltp(sym))
            data = current_pos[sym]

            # SL HIT
            if ltp >= data['sl']:
                print(f"SL HIT {sym} @ {ltp}")
                closed_side = 'CE' if 'C-BTC' in sym else 'PE'
                close_leg(sym)

                # Dusri leg ka SL cost pe le aa
                for other_sym in list(current_pos.keys()):
                    current_pos[other_sym]['sl'] = current_pos[other_sym]['entry']
                    current_pos[other_sym]['sl_moved_to_cost'] = True
                    print(f"Other leg {other_sym} SL moved to COST @ {current_pos[other_sym]['entry']}")

                # Usi side ki new entry same condition pe
                atm = get_atm()
                expiry = get_current_expiry()
                if closed_side == 'CE':
                    new_sym = f"C-BTC-{atm+100}-{expiry}"
                else:
                    new_sym = f"P-BTC-{atm-100}-{expiry}"
                time.sleep(2)
                place_sell(new_sym)

            # TARGET HIT
            elif ltp <= data['target']:
                print(f"TARGET HIT {sym}")
                close_leg(sym)
                # Target hit pe bhi usi side ki new entry
                atm = get_atm()
                expiry = get_current_expiry()
                new_sym = f"C-BTC-{atm+100}-{expiry}" if 'C-BTC' in sym else f"P-BTC-{atm-100}-{expiry}"
                place_sell(new_sym)

        time.sleep(3)

@app.route('/sell')
def sell():
    threading.Thread(target=monitor, daemon=True).start()
    deploy_both()
    return {"success": True, "msg": "ATM+-1 Strangle LIVE | SL 50% | Target 50% | SL hit pe dusri leg cost pe + new entry | 5PM close, 6:30PM restart"}
