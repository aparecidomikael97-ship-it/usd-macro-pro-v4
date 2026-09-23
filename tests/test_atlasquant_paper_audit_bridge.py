from atlasquant_paper_audit_bridge import audit_paper_decision
def test_paper_audit_never_becomes_live():
 o={"opportunity_id":"O1","pair":"EUR/USD","direction":"SELL","strategy_version":"AMD-1","score_version":"S1","risk_version":"R1","quality_score":90,"confidence":90,"gates":{"DATA":"PASS"},"timestamp":"2026-09-23T12:00:00+00:00"}
 r={"risk_gate":"APPROVED","approved":True,"risk_auth_id":"RA1","reasons":[]}
 p={"accepted":True,"paper_request_id":"P1"}
 a=audit_paper_decision(o,r,p)
 assert a["environment"]=="PAPER" and a["paper_accepted"] and a["real_orders_enabled"] is False
