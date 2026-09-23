from atlasquant_paper_state_audit import audit_paper_state

def wait(**kw):
 d={"paper_request_id":"P1","opportunity_id":"O1","risk_auth_id":"RA1","status":"WAIT_ENTRY","environment":"PAPER","real_orders_enabled":False};d.update(kw);return d

def opened(**kw):
 d={"paper_request_id":"P1","opportunity_id":"O1","risk_auth_id":"RA1","status":"OPEN","environment":"PAPER","real_orders_enabled":False,
 "entry_event_id":"E1","entry_price":1.18,"stop_price":1.17,"opened_at":"2026-09-23T12:00:00+00:00","direction":"BUY"};d.update(kw);return d

def test_wait_entry_without_fill_evidence_is_valid():
 r=audit_paper_state([wait()]);assert r["ok"] and r["active_count"]==1

def test_wait_entry_with_fill_evidence_is_protected():
 r=audit_paper_state([wait(entry_price=1.18)]);assert not r["ok"] and any("WAIT_ENTRY_HAS_FILL_EVIDENCE" in x for x in r["reasons"])

def test_open_requires_complete_entry_evidence():
 r=audit_paper_state([opened()]);assert r["ok"]
 bad=audit_paper_state([opened(entry_event_id="")]);assert not bad["ok"] and any("ENTRY_EVENT_ID_MISSING" in x for x in bad["reasons"])

def test_open_initial_stop_geometry_is_checked():
 r=audit_paper_state([opened(stop_price=1.19)]);assert not r["ok"] and any("INITIAL_STOP_GEOMETRY_INVALID" in x for x in r["reasons"])

def test_duplicate_active_identity_is_protected():
 a=wait();b={**wait(),"paper_request_id":"P2","risk_auth_id":"RA2"}
 r=audit_paper_state([a,b]);assert not r["ok"] and any("DUPLICATE_ACTIVE_OPPORTUNITY_ID" in x for x in r["reasons"])

def test_management_allows_stop_moved_beyond_entry_after_open():
 r=audit_paper_state([opened(status="MANAGING",stop_price=1.19)])
 assert r["ok"]
