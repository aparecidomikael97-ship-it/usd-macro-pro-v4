from atlasquant_quality_gate import quality_gate
def checks():return {k:{"state":"PASS","evidence":"ci://ok"} for k in ("instrument_registry","scanner_28","data_health","gate_chain","risk","paper","result_store","restart_recovery")}
def test_all_tests_green_but_protected_runtime_is_blocked(): assert quality_gate(checks(),system_health={"state":"PROTECTED"})["release_state"]=="BLOCKED"
def test_runtime_unknown_is_not_ready(): assert quality_gate(checks())["release_state"]=="NOT_READY"
def test_green_evidence_and_normal_runtime_only_rc_eligible(): assert quality_gate(checks(),system_health={"state":"NORMAL"})["release_state"]=="RC_ELIGIBLE"
