from atlasquant_risk_authorization import RiskRequest,authorize_risk
from atlasquant_risk_guardian import RiskLimits,RiskState

L=RiskLimits(1000,30,10,5,2,20,2); S=RiskState()

def req(**kw):
 d=dict(opportunity_id="opp-1",pair="EUR/USD",strategy_version="AMD-1.0",requested_trade_risk=5,
 requested_exposure=5,structural_stop_valid=True,rr_after_costs=2,spread_ok=True,slippage_ok=True,
 liquidity_ok=True,volatility_ok=True,news_clear=True,data_fresh=True,opportunity_state="TRIGGERED")
 d.update(kw); return RiskRequest(**d)

def test_clean_request_gets_expiring_auth_but_no_real_orders():
 r=authorize_risk(req(),L,S); assert r["approved"] and r["risk_auth_id"] and r["expires_at"]
 assert r["real_orders_enabled"] is False

def test_100_quality_is_irrelevant_when_news_or_data_fail():
 assert not authorize_risk(req(news_clear=False),L,S)["approved"]
 assert not authorize_risk(req(data_fresh=False),L,S)["approved"]

def test_bad_rr_and_missing_structural_stop_block():
 r=authorize_risk(req(rr_after_costs=.5,structural_stop_valid=False),L,S)
 assert not r["approved"] and "RR_INSUFFICIENT" in r["reasons"] and "STRUCTURAL_STOP_INVALID" in r["reasons"]

def test_guard_limit_blocks_oversized_risk():
 r=authorize_risk(req(requested_trade_risk=20),L,S)
 assert not r["approved"] and any(x.startswith("GUARD:") for x in r["reasons"])
