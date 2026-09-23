from datetime import datetime,timezone,timedelta
from atlasquant_paper_entry import activate_paper_entry
from atlasquant_paper_authorization_bridge import paper_request_id_for_authorization

NOW=datetime(2026,9,23,12,tzinfo=timezone.utc)

def trade(**kw):
 d={"paper_request_id":paper_request_id_for_authorization(auth()),"opportunity_id":"O1","pair":"EUR/USD","strategy_version":"AMD-1","risk_auth_id":"RA1",
 "status":"WAIT_ENTRY","environment":"PAPER","real_orders_enabled":False};d.update(kw);return d

def auth(**kw):
 d={"approved":True,"risk_gate":"APPROVED","risk_auth_id":"RA1","opportunity_id":"O1","pair":"EUR/USD","strategy_version":"AMD-1",
 "expires_at":(NOW+timedelta(minutes=5)).isoformat(),"real_orders_enabled":False,"direction":"BUY","stop_price":1.17};d.update(kw);return d

def market(**kw):
 d={"price":1.18,"fresh":True,"valid":True};d.update(kw);return d

def test_valid_wait_entry_opens_paper_only():
 r=activate_paper_entry(trade(),auth(),market(),now=NOW)
 assert r["opened"] and r["state"]=="OPENED"
 x=r["trade"];assert x["status"]=="OPEN" and x["entry_price"]==1.18 and x["entry_event_id"].startswith("PENTRY-")
 assert x["real_orders_enabled"] is False

def test_stale_or_invalid_market_never_opens():
 assert "MARKET_DATA_STALE" in activate_paper_entry(trade(),auth(),market(fresh=False),now=NOW)["reasons"]
 assert "MARKET_DATA_INVALID" in activate_paper_entry(trade(),auth(),market(valid=False),now=NOW)["reasons"]

def test_expired_or_mismatched_auth_never_opens():
 expired=auth(expires_at=(NOW-timedelta(seconds=1)).isoformat())
 assert "RISK_AUTH_EXPIRED" in activate_paper_entry(trade(),expired,market(),now=NOW)["reasons"]
 assert "PAIR_MISMATCH" in activate_paper_entry(trade(),auth(pair="GBP/USD"),market(),now=NOW)["reasons"]

def test_non_normal_system_health_blocks_entry():
 r=activate_paper_entry(trade(),auth(),market(),system_state="PROTECTED",now=NOW)
 assert not r["opened"] and "SYSTEM_HEALTH_NOT_NORMAL" in r["reasons"]

def test_invalid_entry_price_blocks():
 assert "ENTRY_PRICE_INVALID" in activate_paper_entry(trade(),auth(),market(price=float("nan")),now=NOW)["reasons"]

def test_already_open_entry_event_is_idempotent():
 t=trade(status="OPEN",entry_event_id="PENTRY-X")
 r=activate_paper_entry(t,auth(),market(),now=NOW)
 assert r["state"]=="ALREADY_OPEN" and not r["opened"] and r["trade"]["entry_event_id"]=="PENTRY-X"

def test_missing_or_wrong_stop_geometry_blocks_entry():
 assert "STRUCTURAL_STOP_PRICE_INVALID" in activate_paper_entry(trade(),auth(stop_price=None),market(),now=NOW)["reasons"]
 assert "STOP_GEOMETRY_INVALID" in activate_paper_entry(trade(),auth(direction="BUY",stop_price=1.19),market(),now=NOW)["reasons"]

def test_forged_paper_request_id_never_opens():
 r=activate_paper_entry(trade(paper_request_id="PAPER-FORGED"),auth(),market(),now=NOW)
 assert not r["opened"] and "PAPER_REQUEST_ID_AUTH_MISMATCH" in r["reasons"]
