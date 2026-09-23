import math
from datetime import datetime,timezone,timedelta
from atlasquant_risk_authorization import RiskRequest,authorize_risk
from atlasquant_risk_guardian import RiskLimits,RiskState
from atlasquant_paper_authorization_bridge import paper_request_from_authorization,paper_request_id_for_authorization
from atlasquant_opportunity_ranking import build_rankings
from atlasquant_radar_views import build_radar_views
from atlasquant_paper_runtime import paper_state_snapshot,recover_paper_state

NOW=datetime(2026,9,23,12,tzinfo=timezone.utc)
L=RiskLimits(1000,30,10,5,2,20,2); S=RiskState()
PASS_GATES={"DATA":"PASS","DIRECTION":"PASS_LONG","MACRO":"ALIGNED_LONG","STRATEGY":"TRIGGERED","TRIGGER":"CONFIRMED","SESSION":"OPTIMAL","NEWS":"CLEAR","MARKET_CONDITION":"NORMAL","RISK":"APPROVED"}

def req(**kw):
 d=dict(opportunity_id="O1",pair="EUR/USD",strategy_version="AMD-1",requested_trade_risk=5,requested_exposure=5,
 structural_stop_valid=True,rr_after_costs=2,spread_ok=True,slippage_ok=True,liquidity_ok=True,volatility_ok=True,
 news_clear=True,data_fresh=True,opportunity_state="TRIGGERED")
 d.update(kw); return RiskRequest(**d)

def auth(**kw):
 d={"approved":True,"risk_gate":"APPROVED","risk_auth_id":"R1","expires_at":(NOW+timedelta(minutes=5)).isoformat(),
 "real_orders_enabled":False,"opportunity_id":"O1","pair":"EUR/USD","strategy_version":"AMD-1",
 "max_authorized_risk":5,"max_authorized_exposure":5,"direction":"SELL","stop_price":1.2}
 d.update(kw);return d

def test_risk_rejects_unsupported_pair_and_invalid_min_rr():
 assert "PAIR_INVALID" in authorize_risk(req(pair="USD/BRL"),L,S,now=NOW)["reasons"]
 assert "MIN_RR_INVALID" in authorize_risk(req(),L,S,now=NOW,min_rr=math.nan)["reasons"]

def test_naive_now_is_normalized_to_utc():
 r=authorize_risk(req(),L,S,now=datetime(2026,9,23,12))
 assert r["issued_at"].endswith("+00:00")

def test_paper_auth_binds_pair_and_positive_sizing():
 assert "RISK_AUTH_PAIR_MISMATCH" in paper_request_from_authorization(auth(),now=NOW,pair="GBP/USD")["reasons"]
 assert "REQUESTED_RISK_INVALID" in paper_request_from_authorization(auth(),now=NOW,requested_risk=-1)["reasons"]
 assert "RISK_AUTH_MAX_EXPOSURE_INVALID" in paper_request_from_authorization(auth(max_authorized_exposure=math.nan),now=NOW)["reasons"]

def test_authoritative_wait_gate_blocks_high_score_ranking():
 g=dict(PASS_GATES);g["NEWS"]="WAIT"
 r=build_rankings([{"pair":"EUR/USD","quality_score":99,"confidence":99,"data_ready":True,"trigger":"CONFIRMED","risk_gate":"APPROVED","gates":g}])
 assert not r["TOP_AGORA"][0]["executable"] and r["TOP_AGORA"][0]["gate_waits"]

def test_explicit_risk_block_never_appears_preparing():
 r=build_rankings([{"pair":"EUR/USD","quality_score":99,"confidence":99,"data_ready":True,"trigger":"CONFIRMED","risk_gate":"BLOCKED"}])
 assert r["TOP_PREPARANDO"]==[] and r["TOP_AGORA"][0]["operational_status"]=="BLOQUEADO"

def test_radar_macro_policy_is_row_specific():
 g=dict(PASS_GATES);g["MACRO"]="NEUTRAL"
 base={"pair":"EUR/USD","bias":"COMPRA","quality":90,"data_score":95,"data_ready":True,"signal_status_code":"CONFIRMED","risk_gate":"APPROVED","gates":g}
 wait=build_radar_views([{**base,"macro_policy":"WAIT"}])
 assert not wait["TOP_AGORA"][0]["executable"] and wait["TOP_PREPARANDO"][0]["pair"]=="EUR/USD"
 assert build_radar_views([{**base,"macro_policy":"PASS"}])["TOP_AGORA"][0]["executable"]

def test_wait_entry_restart_requires_current_authorization():
 row={"pair":"EUR/USD","status":"WAIT_ENTRY","paper_request_id":paper_request_id_for_authorization(auth()),"opportunity_id":"O1","risk_auth_id":"R1","strategy_version":"AMD-1","environment":"PAPER","real_orders_enabled":False}
 s=paper_state_snapshot([row],created_at=NOW.isoformat()); market={"EUR/USD":{"price":1.1,"fresh":True,"valid":True}}
 r=recover_paper_state(s,current_market=market,now=NOW)
 assert r["trades"][0]["recovery_state"]=="REAUTHORIZATION_REQUIRED" and r["trades"][0]["entry_authorized"] is False
 r2=recover_paper_state(s,current_market=market,current_authorizations={"R1":auth()},now=NOW)
 assert r2["trades"][0]["recovery_state"]=="RECOVERED" and r2["trades"][0]["entry_authorized"] is True

def test_expired_auth_cannot_reopen_wait_entry_but_open_is_management_only():
 wait={"pair":"EUR/USD","status":"WAIT_ENTRY","paper_request_id":paper_request_id_for_authorization(auth()),"opportunity_id":"O1","risk_auth_id":"R1","strategy_version":"AMD-1","environment":"PAPER","real_orders_enabled":False}
 s=paper_state_snapshot([wait]);market={"EUR/USD":{"price":1.1,"fresh":True,"valid":True}}
 expired=auth(expires_at=(NOW-timedelta(seconds=1)).isoformat())
 assert recover_paper_state(s,current_market=market,current_authorizations={"R1":expired},now=NOW)["trades"][0]["recovery_state"]=="REAUTHORIZATION_REQUIRED"
 opened={**wait,"status":"OPEN","entry_event_id":"E1","entry_price":1.1,"stop_price":1.2,"opened_at":NOW.isoformat(),"direction":"SELL"}
 s2=paper_state_snapshot([opened]);r=recover_paper_state(s2,current_market=market,now=NOW)
 assert r["trades"][0]["recovery_state"]=="RECOVERED" and r["trades"][0]["management_only"] is True
