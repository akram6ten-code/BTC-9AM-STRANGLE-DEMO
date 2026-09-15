import time, hmac, hashlib, requests, json, pandas as pd
from datetime import datetime

# --- CONFIG - DEMO.DELTA.EXCHANGE ---
BASE_URL = "https://cdn-ind.testnet.deltaex.org"
API_KEY = "DAL DE APNA DEMO KEY"
API_SECRET = "DAL DE APNA DEMO SECRET"
LEVERAGE = 100
LOT_SIZE = 50
TARGET_PCT = 0.90 # 90% target
SL_PCT = 0.50 # 50% SL
RESOLUTION = "15m"

def get_signature(secret, message):
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

def api_call(method, path, query="", payload=""):
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + path + query + payload
    signature = get_signature(API_SECRET, signature_data)
    headers = {'api-key': API_KEY, 'timestamp': timestamp, 'signature': signature, 'Content-Type': 'application/json'}
    url = BASE_URL + path + query
    r = requests.request(method, url, data=payload, headers=headers, timeout=10)
    return r.json()

def get_atm_call_product():
    res = requests.get(f"{BASE_URL}/v2/products?contract_types=call_options&underlying_asset_symbols=BTC")
    products = [p for p in res.json()['result'] if p['state']=='live']
    products.sort(key=lambda x: x['settlement_time'])
    current_expiry_time = products[0]['settlement_time']
    current_expiry_products = [p for p in products if p['settlement_time']==current_expiry_time]

    spot = float(requests.get(f"{BASE_URL}/v2/tickers/BTCUSD").json()['result']['spot_price'])
    atm_strike = int(round(spot / 100) * 100)

    atm_call = next((p for p in current_expiry_products if float(p['strike_price'])==atm_strike), None)
    if not atm_call:
        # agar exact ATM nahi mila to nearest lo
        atm_call = min(current_expiry_products, key=lambda x: abs(float(x['strike_price'])-atm_strike))

    print(f"LOCKED: Spot={spot} | ATM Strike={atm_call['strike_price']} | Product={atm_call['symbol']}")
    return atm_call

def get_supertrend_value(symbol):
    # 15min candles of PREMIUM (Mark Price)
    end = int(time.time())
    start = end - (200*15*60)
    r = requests.get(f"{BASE_URL}/v2/history/candles?symbol={symbol}&resolution={RESOLUTION}&start={start}&end={end}")
    candles = r.json()['result']
    df = pd.DataFrame(candles)
    df = df.rename(columns={'open':'open','high':'high','low':'low','close':'close'})

    # ATR
    period = 10
    multiplier = 3
    df['hl2'] = (df['high'] + df['low'])/2
    df['tr'] = df['high'] - df['low']
    df['atr'] = df['tr'].rolling(period).mean()

    df['upperband'] = df['hl2'] + (multiplier * df['atr'])
    df['lowerband'] = df['hl2'] - (multiplier * df['atr'])

    # SuperTrend logic
    df['supertrend'] = 0.0
    df['in_uptrend'] = True
    for i in range(1, len(df)):
        if df['close'][i] > df['upperband'][i-1]:
            df['in_uptrend'][i] = True
        elif df['close'][i] < df['lowerband'][i-1]:
            df['in_uptrend'][i] = False
        else:
            df['in_uptrend'][i] = df['in_uptrend'][i-1]
            if df['in_uptrend'][i] and df['lowerband'][i] < df['lowerband'][i-1]:
                df['lowerband'][i] = df['lowerband'][i-1]
            if not df['in_uptrend'][i] and df['upperband'][i] > df['upperband'][i-1]:
                df['upperband'][i] = df['upperband'][i-1]

        df['supertrend'][i] = df['lowerband'][i] if df['in_uptrend'][i] else df['upperband'][i]

    return float(df.iloc[-1]['supertrend']), float(df.iloc[-1]['close'])

# --- MAIN LOOP ---
position = None
entry_price = 0
initial_sl = 0
trailing_sl = 0

product = get_atm_call_product()

# Leverage set - demo pe
try:
    api_call("POST", "/v2/products/"+str(product['id'])+"/orders/leverage", payload=json.dumps({"leverage": str(LEVERAGE)}))
    print(f"Leverage set to {LEVERAGE}x")
except: pass

print("Bot Started - Waiting for Premium < SuperTrend...")

while True:
    try:
        ticker = requests.get(f"{BASE_URL}/v2/tickers/{product['symbol']}").json()['result']
        premium_ltp = float(ticker['mark_price'])
        st_value, _ = get_supertrend_value(product['symbol'])

        if position is None:
            print(f"Check: Premium {premium_ltp} | ST {st_value}")
            if premium_ltp < st_value:
                print(f"ENTRY CONDITION HIT: {premium_ltp} < {st_value}")
                order = api_call("POST", "/v2/orders", payload=json.dumps({
                    "product_id": product['id'],
                    "size": LOT_SIZE,
                    "side": "sell",
                    "order_type": "market_order"
                }))
                print("SELL Order:", order)
                position = "SHORT"
                entry_price = premium_ltp
                initial_sl = entry_price * (1 + SL_PCT) # 100 -> 150
                trailing_sl = initial_sl
                print(f"SHORTED @ {entry_price} | Initial SL @ {initial_sl}")

        else:
            # Profit calculate
            profit = entry_price - premium_ltp

            # Tera 1:1 Trail logic
            if profit > 0:
                # Market meri side aaya toh SL utna hi niche khisakega
                new_trail = initial_sl - profit
                if new_trail < trailing_sl:
                    trailing_sl = new_trail
                    print(f"TRAIL UPDATE: Profit {profit:.2f} | New SL {trailing_sl:.2f}")

            # Exit conditions
            target_price = entry_price * (1 - TARGET_PCT) # 100 -> 10
            if premium_ltp <= target_price:
                print(f"TARGET HIT {premium_ltp} <= {target_price} -> EXIT")
                api_call("POST", "/v2/orders", payload=json.dumps({"product_id": product['id'], "size": LOT_SIZE, "side": "buy", "order_type": "market_order"}))
                break

            if premium_ltp >= trailing_sl:
                print(f"SL HIT {premium_ltp} >= {trailing_sl} -> EXIT")
                api_call("POST", "/v2/orders", payload=json.dumps({"product_id": product['id'], "size": LOT_SIZE, "side": "buy", "order_type": "market_order"}))
                break

        time.sleep(5)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
