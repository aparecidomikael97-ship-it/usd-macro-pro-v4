from datetime import datetime,timezone,timedelta
from atlasquant_scanner_scheduler import build_scan_plan
from atlasquant_instrument_registry import FX_28
from twelve_budget_v1108 import Budget

NOW=datetime(2026,9,23,12,0,tzinfo=timezone.utc)

class Store:
    def __init__(self): self.state={}; self.rev=0
    def load(self): return dict(self.state),self.rev
    def save(self,state,revision):
        if revision!=self.rev: return False
        self.state=dict(state); self.rev+=1; return True

def test_scheduler_due_count_is_bounded_by_28():
    jobs=build_scan_plan({}, {}, now=NOW)
    assert len(jobs)==28
    assert sum(j.due for j in jobs)==28

def test_fresh_background_does_not_create_unnecessary_due_work():
    stamp=(NOW-timedelta(minutes=30)).timestamp()
    fetch={f"{s[:3]}/{s[3:]}":{"m15":stamp} for s in FX_28}
    jobs=build_scan_plan(fetch,{},now=NOW)
    assert sum(j.due for j in jobs)==0

def test_budget_remains_authority_even_if_all_28_are_due():
    store=Store(); budget=Budget(store)
    jobs=build_scan_plan({}, {}, now=NOW)
    granted=0
    # Simulate scheduler asking for all due jobs at same instant.
    for _ in jobs:
        ok,_,_=budget.reserve(NOW)
        granted+=int(ok)
    assert granted==6
    assert store.state["used"]==6
