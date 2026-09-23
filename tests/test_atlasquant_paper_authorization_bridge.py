from datetime import datetime,timezone,timedelta
from atlasquant_paper_authorization_bridge import paper_request_from_authorization
NOW=datetime(2026,9,23,12,0,tzinfo=timezone.utc)
def auth(exp):
 return {"approved":True,"risk_gate":"APPROVED","risk_auth_id":"RISK-1","expires_at":exp.isoformat(),"real_orders_enabled":False,"opportunity_id":"O1","pair":"EUR/USD","strategy_version":"AMD-1","max_authorized_risk":5,"max_authorized_exposure":5,"fail_closed":True}
def test_valid_auth_goes_only_to_paper():
 r=paper_request_from_authorization(auth(NOW+timedelta(minutes=2)),now=NOW)
 assert r["accepted"] and r["environment"]=="PAPER" and r["real_orders_enabled"] is False
def test_expired_auth_fails_closed():
 r=paper_request_from_authorization(auth(NOW-timedelta(seconds=1)),now=NOW)
 assert not r["accepted"] and "RISK_AUTH_EXPIRED" in r["reasons"]
def test_missing_live_false_flag_is_blocked():
 a=auth(NOW+timedelta(minutes=2)); a.pop("real_orders_enabled")
 assert not paper_request_from_authorization(a,now=NOW)["accepted"]
