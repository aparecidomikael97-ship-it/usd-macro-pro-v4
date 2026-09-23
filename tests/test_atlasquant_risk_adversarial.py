import math
from datetime import datetime,timezone,timedelta
from atlasquant_risk_authorization import RiskRequest,authorize_risk
from atlasquant_risk_guardian import RiskLimits,RiskState
from atlasquant_paper_authorization_bridge import paper_request_from_authorization
L=RiskLimits(1000,30,10,5,2,20,2); S=RiskState(); NOW=datetime(2026,9,23,12,tzinfo=timezone.utc)
def req(**kw):
 d=dict(opportunity_id="O1",pair="EUR/USD",strategy_version="AMD-1",requested_trade_risk=5,requested_exposure=5,structural_stop_valid=True,rr_after_costs=2,spread_ok=True,slippage_ok=True,liquidity_ok=True,volatility_ok=True,news_clear=True,data_fresh=True,opportunity_state="TRIGGERED")
 d.update(kw); return RiskRequest(**d)
def test_nan_rr_fails_closed(): assert not authorize_risk(req(rr_after_costs=math.nan),L,S,now=NOW)["approved"]
def test_long_stop_must_be_below_entry():
 r=authorize_risk(req(direction="LONG",entry_price=1.1,stop_price=1.2),L,S,now=NOW); assert not r["approved"]
def test_short_valid_geometry_can_authorize():
 r=authorize_risk(req(direction="SHORT",entry_price=1.1,stop_price=1.2),L,S,now=NOW); assert r["approved"]
def test_bad_ttl_blocks_not_throws(): assert not authorize_risk(req(),L,S,now=NOW,ttl_minutes="bad")["approved"]
def test_paper_revalidates_identity_and_size():
 a=authorize_risk(req(),L,S,now=NOW)
 r=paper_request_from_authorization(a,now=NOW,opportunity_id="OTHER",strategy_version="AMD-2",requested_risk=6,requested_exposure=6)
 assert not r["accepted"] and {"RISK_AUTH_OPPORTUNITY_MISMATCH","RISK_AUTH_STRATEGY_MISMATCH","RISK_AUTH_RISK_EXCEEDED","RISK_AUTH_EXPOSURE_EXCEEDED"}.issubset(set(r["reasons"]))
