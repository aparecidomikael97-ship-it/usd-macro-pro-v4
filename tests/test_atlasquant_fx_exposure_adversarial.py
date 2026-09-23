import pytest
from atlasquant_fx_exposure import decompose_fx,aggregate_currency_exposure,concentration_gate
@pytest.mark.parametrize("w",[0,-1,float("nan"),float("inf")])
def test_invalid_weight_fails(w):
 with pytest.raises(ValueError): decompose_fx("EUR/USD","BUY",w)
def test_invalid_existing_position_blocks_concentration():
 r=concentration_gate([{"pair":"BAD","side":"BUY","weight":1}],{"pair":"EUR/USD","side":"BUY","weight":1},max_currency_gross=10)
 assert not r["approved"] and r["reason"]=="PORTFOLIO_EXPOSURE_UNKNOWN"
def test_net_hedge_does_not_hide_gross():
 a=aggregate_currency_exposure([{"pair":"EUR/USD","side":"BUY","weight":1},{"pair":"EUR/USD","side":"SELL","weight":1}])
 assert a["net"]["EUR"]==0 and a["gross"]["EUR"]==2
