from atlasquant_quality_gate import quality_gate,initial_unvalidated_gate,CRITICAL
def test_not_run_is_never_green():
 r=initial_unvalidated_gate(); assert r["release_state"]=="NOT_READY" and len(r["pending"])==len(CRITICAL)
def test_pass_without_evidence_is_pending():
 checks={x:{"state":"PASS"} for x in CRITICAL}; assert quality_gate(checks)["release_state"]=="NOT_READY"
def test_all_evidenced_pass_only_makes_rc_eligible_not_production():
 checks={x:{"state":"PASS","evidence":"pytest"} for x in CRITICAL}; r=quality_gate(checks)
 assert r["release_state"]=="RC_ELIGIBLE" and r["production_promotion_allowed"] is False and r["real_orders_enabled"] is False
