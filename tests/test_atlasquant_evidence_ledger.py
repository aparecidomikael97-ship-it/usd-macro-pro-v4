from atlasquant_result_store import decision_record,attach_result,rejected_record
from atlasquant_evidence_ledger import append_evidence,validate_evidence_ledger

BASE=dict(opportunity_id="O1",environment="PAPER",pair="EUR/USD",direction="SELL",strategy_version="AMD-1",
score_version="S1",risk_version="R1",quality_score=90,confidence=90,gates={"DATA":"PASS"},risk_decision={"risk_gate":"APPROVED"},timestamp="2026-09-23T12:00:00+00:00")

def decision(): return decision_record(**BASE)

def test_decision_then_result_append_is_valid():
 d=decision();a=append_evidence([],d);assert a["appended"]
 r=attach_result(d,outcome="WIN",realized_r=1,closed_at="2026-09-23T13:00:00+00:00")
 b=append_evidence(a["ledger"],r)
 assert b["appended"] and validate_evidence_ledger(b["ledger"])["ok"]

def test_same_record_is_idempotent_not_duplicated():
 d=decision();a=append_evidence([],d);b=append_evidence(a["ledger"],d)
 assert b["state"]=="ALREADY_EXISTS" and len(b["ledger"])==1

def test_conflicting_same_record_id_requires_recovery():
 d=decision();a=append_evidence([],d);tampered=dict(d);tampered["quality_score"]=1
 b=append_evidence(a["ledger"],tampered)
 assert b["state"]=="RECOVERY_REQUIRED" and not b["appended"]

def test_result_without_parent_is_rejected():
 d=decision();r=attach_result(d,outcome="LOSS",realized_r=-1,closed_at="2026-09-23T13:00:00+00:00")
 x=append_evidence([],r);assert x["state"]=="REJECTED" and "RESULT_PARENT_DECISION_NOT_UNIQUE" in x["reasons"]

def test_second_result_for_same_decision_requires_recovery():
 d=decision();a=append_evidence([],d)
 r1=attach_result(d,outcome="WIN",realized_r=1,closed_at="2026-09-23T13:00:00+00:00")
 b=append_evidence(a["ledger"],r1)
 r2=attach_result(d,outcome="WIN",realized_r=2,closed_at="2026-09-23T14:00:00+00:00")
 x=append_evidence(b["ledger"],r2)
 assert x["state"]=="RECOVERY_REQUIRED"

def test_rejected_opportunity_is_valid_immutable_evidence():
 r=rejected_record(**{**BASE,"risk_decision":{"risk_gate":"BLOCKED"}})
 x=append_evidence([],r);assert x["appended"] and validate_evidence_ledger(x["ledger"])["ok"]
