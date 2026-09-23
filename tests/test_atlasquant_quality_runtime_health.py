from atlasquant_quality_gate import quality_gate
from atlasquant_quality_gate import CRITICAL
def checks():return {k:{"state":"PASS","evidence":"ci://ok"} for k in CRITICAL}
def test_all_tests_green_but_protected_runtime_is_blocked(): assert quality_gate(checks(),system_health={"state":"PROTECTED"})["release_state"]=="BLOCKED"
def test_runtime_unknown_is_not_ready(): assert quality_gate(checks())["release_state"]=="NOT_READY"
def test_green_evidence_and_normal_runtime_only_rc_eligible(): assert quality_gate(checks(),system_health={"state":"NORMAL"})["release_state"]=="RC_ELIGIBLE"
