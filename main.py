import time, hmac, hashlib, requests, pandas as pd, json

BASE_URL = "https://cdn-ind.testnet.deltaex.org" # demo.delta.exchange ka API【8460388681980791653†L419-L431】
API_KEY = "TERA_DEMO_API_KEY"
API_SECRET = "TERA_DEMO_SECRET"

def get_signature(secret, message):
    return hmac.new(bytes(secret, 'utf-8'), bytes(message, 'utf-8'), hashlib.sha256).hexdigest()

def api_call(method, path, query="", payload=""):
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + path + query + payload
    signature = get_signature(API_SECRET, signature_data)
    headers = {'api-key': API_KEY, 'timestamp': timestamp, 'signature': signature, 'Content-Type': 'application/json'}
    url = BASE_URL + path + query
    r = requests.request(method, url, data=payload, headers=headers)
    return r.json()

# 1. Current Expiry + ATM
def get_current_atm_call_product():
    # Products list
    res = requests.get(f"{BASE_URL}/v2/products?contract_types=call_options,put_options&underlying_asset_symbols=BTC")
    products = res.json()['result']
    # Current expiry = sabse chhota expiry time
    btc_calls = [p for p in products if p['contract_type']=='call_options' and p['state']=='live']
    btc_calls.sort(key=lambda x: x['settlement_time'])
    current_expiry = btc_calls[0]['settlement_time'] # first expiry
    # Spot
    spot = requests.get(f"{BASE_URL}/v2/tickers/BTCUSD").json()['result']['spot_price']
    atm_strike = round(float(spot)/100)*100

    # ATM Call product dhoondo
    atm_call = [p for p in btc_calls if p['strike_price']==str(atm_strike) and p['settlement_time']==current_expiry][0]
    return atm_call, float(spot)

# 2. SuperTrend
def supertrend(df, period=10, multiplier=3):
    hl2 = (df['high'] + df['low']) / 2
    atr = df['high'].rolling(period).max() - df['low'].rolling(period).min() # simplified ATR for demo
    #... actual ATR calc yahan ayega
    # Logic: agar close < supertrend -> sell signal
    return df

# 3. Main Loop
atm_call, spot = get_current_atm_call_product()
print(f"FINAL LOCKED: Spot {spot} | ATM {atm_call['strike_price']} | Product {atm_call['symbol']} | Expiry {atm_call['settlement_time']}")

# Entry logic
# candles = api_call('GET', f"/v2/history/candles?symbol={atm_call['symbol']}&resolution=15m")
# premium = live mark price
# if premium < supertrend_value:
# api_call('POST', '/v2/orders', payload=json.dumps({"product_id": atm_call['id'], "size": 50, "side": "sell", "order_type": "market_order"}))
