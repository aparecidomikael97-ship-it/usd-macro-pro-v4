from atlasquant_paper_ledger_reconciliation import reconcile_active_paper
def test_clean_active_matches_ledger():
 r={"paper_request_id":"P1","opportunity_id":"O1","status":"OPEN"}
 x=reconcile_active_paper([r],[r]);assert x["ok"] and x["system_state"]=="NORMAL"
def test_orphan_active_protects_new_entries():
 s={"paper_request_id":"P1","opportunity_id":"O1","status":"OPEN"}
 x=reconcile_active_paper([s],[]);assert not x["ok"] and x["system_state"]=="PROTECTED" and x["management_allowed"]
def test_duplicate_request_id_protects():
 a={"paper_request_id":"P1","opportunity_id":"O1","status":"OPEN"};b={"paper_request_id":"P1","opportunity_id":"O2","status":"OPEN"}
 x=reconcile_active_paper([a,b],[a,b]);assert not x["new_entries_allowed"]

def test_foreign_environment_protects_and_is_excluded():
 p={"paper_request_id":"P1","opportunity_id":"O1","status":"OPEN","environment":"PAPER"}
 live={"paper_request_id":"L1","opportunity_id":"L1","status":"OPEN","environment":"LIVE"}
 x=reconcile_active_paper([p,live],[p,live])
 assert not x["ok"] and "ENVIRONMENT_MIX_DETECTED" in x["reasons"] and x["foreign_count"]==2
 assert x["management_mode"]=="SAFE_ONLY" and not x["entry_recovery_allowed"]
