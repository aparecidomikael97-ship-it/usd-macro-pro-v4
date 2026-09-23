import math,pytest
from atlasquant_result_store import decision_record,attach_result,rejected_record
BASE=dict(opportunity_id="O",environment="PAPER",pair="EUR/USD",direction="SELL",strategy_version="AMD1",score_version="S1",risk_version="R1",quality_score=90,confidence=80,gates={},risk_decision={},timestamp="2026-09-23T12:00:00+00:00")
def test_result_has_distinct_id_and_decision_link():
 d=decision_record(**BASE); r=attach_result(d,outcome="WIN",realized_r=1)
 assert r["record_id"]!=d["record_id"] and r["record_id"].startswith("RES-") and r["decision_record_id"]==d["record_id"]
def test_rejected_has_distinct_type_id(): assert rejected_record(**BASE)["record_id"].startswith("REJ-")
@pytest.mark.parametrize("field,value",[("quality_score",101),("confidence",-1),("quality_score",math.nan)])
def test_invalid_scores_fail(field,value):
 with pytest.raises(ValueError): decision_record(**{**BASE,field:value})
def test_invalid_pair_or_direction_fail():
 with pytest.raises(ValueError): decision_record(**{**BASE,"pair":"USD/BRL"})
 with pytest.raises(ValueError): decision_record(**{**BASE,"direction":"SIDEWAYS"})
