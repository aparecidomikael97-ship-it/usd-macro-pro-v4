from atlasquant_paper_store_health import paper_store_health
from atlasquant_system_health import system_health

def row():
 return {"paper_request_id":"P1","opportunity_id":"O1","status":"OPEN","environment":"PAPER"}

def components(paper):
 good={"state":"NORMAL","healthy":True}
 return {"market_data":dict(good),"scanner":dict(good),"risk":dict(good),"result_store":dict(good),"paper_store":paper}

def test_clean_store_is_normal():
 p=paper_store_health([row()],[row()],[])
 assert p["state"]=="NORMAL" and p["healthy"] and p["integrity_ok"]
 assert system_health(components(p))["state"]=="NORMAL"

def test_integrity_ambiguity_protects_but_store_remains_available():
 p=paper_store_health([row()],[],[])
 assert p["state"]=="PROTECTED" and p["healthy"] and not p["integrity_ok"] and p["management_mode"]=="SAFE_ONLY"
 h=system_health(components(p));assert h["state"]=="PROTECTED" and not h["new_entries_allowed"]

def test_unavailable_store_halts_system():
 p=paper_store_health([],[],[],store_available=False)
 assert p["state"]=="HALTED" and not p["healthy"]
 assert system_health(components(p))["state"]=="HALTED"
