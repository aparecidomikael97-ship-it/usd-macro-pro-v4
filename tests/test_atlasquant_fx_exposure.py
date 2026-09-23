from atlasquant_fx_exposure import decompose_fx,aggregate_currency_exposure,concentration_gate

def test_sell_eurusd_is_short_eur_long_usd():
 assert decompose_fx("EUR/USD","SELL",2)=={"EUR":-2.0,"USD":2.0}

def test_gross_exposure_is_not_hidden_by_net_hedge():
 x=aggregate_currency_exposure([{"pair":"EUR/USD","side":"BUY","weight":1},{"pair":"GBP/USD","side":"SELL","weight":1}])
 assert x["net"]["USD"]==0 and x["gross"]["USD"]==2

def test_candidate_can_be_blocked_by_currency_concentration():
 r=concentration_gate([{"pair":"EUR/USD","side":"SELL","weight":1}],{"pair":"GBP/USD","side":"SELL","weight":1},max_currency_gross=1.5)
 assert not r["approved"] and "USD" in r["breaches"]
