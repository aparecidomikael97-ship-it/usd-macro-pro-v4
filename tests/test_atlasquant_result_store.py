import pytest
from atlasquant_result_store import decision_record,attach_result,rejected_record

BASE=dict(opportunity_id="O1",environment="PAPER",pair="EUR/USD",direction="SELL",strategy_version="AMD-1",
score_version="AQ_SCORE_1",risk_version="AQ_RISK_1",quality_score=88,confidence=91,gates={"DATA":"PASS"},
risk_decision={"risk_gate":"APPROVED"},timestamp="2026-09-23T12:00:00+00:00")

def test_environment_separation_and_lineage():
 a=decision_record(**BASE); b=decision_record(**{**BASE,"environment":"BACKTEST"})
 assert a["environment"]=="PAPER" and b["environment"]=="BACKTEST" and a["record_id"]!=b["record_id"]
def test_missing_lineage_fails_closed():
 with pytest.raises(ValueError): decision_record(**{**BASE,"strategy_version":""})
def test_result_keeps_decision_link_and_costs_in_r():
 d=decision_record(**BASE); r=attach_result(d,outcome="WIN",realized_r=2,spread_cost_r=.1,slippage_cost_r=.05,mae_r=-.4,mfe_r=2.3,closed_at="2026-09-23T13:00:00+00:00")
 assert r["decision_record_id"]==d["record_id"] and abs(r["net_r"]-1.85)<1e-9
def test_rejected_opportunity_is_preserved():
 r=rejected_record(**{**BASE,"risk_decision":{"risk_gate":"BLOCKED","reasons":["NEWS_LOCK"]}})
 assert r["record_type"]=="REJECTED_OPPORTUNITY"
