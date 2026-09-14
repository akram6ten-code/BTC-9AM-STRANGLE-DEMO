@app.route('/sell')
def sell():
    # 1. BTC ka live price
    btc_price = float(delta_client.get_ticker('BTCUSD')['close'])
    atm = round(btc_price / 100) * 100
    print(f"BTC: {btc_price} | ATM: {atm}")

    # 2. Expiry - aaj ka daily expiry
    expiry = get_current_expiry() # tera wala function - ex: 17-09-2026

    # 3. Symbol - Delta ka format aisa hota hai
    call_symbol = f"C-BTC-{atm}-{expiry}"
    put_symbol = f"P-BTC-{atm}-{expiry}"

    print(f"Selling: {call_symbol} + {put_symbol}")

    # 4. SELL - 10 Lot, 200x
    call_order = delta_client.place_order(symbol=call_symbol, side='sell', size=10, leverage=200, type='market')
    put_order = delta_client.place_order(symbol=put_symbol, side='sell', size=10, leverage=200, type='market')

    return {
        "success": True,
        "btc": btc_price,
        "atm": atm,
        "sold": [call_symbol, put_symbol],
        "call_result": call_order,
        "put_result": put_order
    }
