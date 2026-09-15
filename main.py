# Last candle jo close ho chuki hai
closed_close = closes[-2]
closed_high = highs[-2]
closed_low = lows[-2]
closed_vwap = vwap_list[-2]

# Supertrend usi closed candle ka
hl2 = (closed_high + closed_low)/2
atr = sum([highs[i]-lows[i] for i in range(len(highs)-12, len(highs)-2)])/10
upper = hl2 + 3*atr
lower = hl2 - 3*atr

# Condition sirf closed candle pe
if closed_close < closed_vwap and closed_close < lower:
    # RED + VWAP ke niche = CALL SELL
    otype = "call_options"
elif closed_close > closed_vwap and closed_close > upper:
    # GREEN + VWAP ke upar = PUT SELL
    otype = "put_options"
else:
    return f"NO TRADE - Closed Candle {closed_close:.2f} VWAP {closed_vwap:.2f} ST {'RED' if closed_close < lower else 'GREEN' if closed_close > upper else 'MIDDLE'}"
