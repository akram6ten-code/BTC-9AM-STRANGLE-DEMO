def place_sell(symbol):
    order = delta_client.place_order(
        symbol=symbol, 
        side='sell', 
        size=10,  # <--- 10 LOT FINAL
        leverage=200, 
        type='market'
    )
