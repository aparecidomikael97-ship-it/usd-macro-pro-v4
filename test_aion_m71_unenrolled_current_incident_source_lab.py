"""M71 first-effect ACTIVATION fail-closed regression, offline and unprivileged.

The current incident-state source is NOT independently enrolled. The direct
public validator must not return READY based solely on caller-supplied runtime,
approval and an in-TTL READY gate. These are denial contracts, not a new trust
root, not real identity or real incident adjudication.
"""
import unittest
from copy import deepcopy
from datetime import timedelta

from atlasquant_aion_global_worker_incident_reconciliation import (
    reconcile_global_worker_incident_center,
)
from atlasquant_aion_global_worker_reactivation_gate import (
    READY_STATUS,
    BLOCKED_STATUS,
    assess_post_incident_reactivation_gate,
    validate_reactivation_gate_for_execution as validate,
)
from test_atlasquant_aion_global_worker_reactivation_gate import (
    NOW, _post_incident_runtime, _readiness, _safe_flag, _safe_reconciled_snapshot,
    _armed_checkpoint,
)

NO_TRUST = "INDEPENDENT_POST_INCIDENT_CURRENT_STATE_NOT_ENROLLED"


def setup_gate():
    runtime, incident = _post_incident_runtime()
    flag = _safe_flag()
    gate = assess_post_incident_reactivation_gate(
        runtime, _safe_reconciled_snapshot(runtime), _readiness(), flag, now=NOW,
    )
    assert gate["status"] == READY_STATUS
    approval = {
        "post_incident_gate_required": True,
        "post_incident_closure_ledger_digest": gate["closure_ledger_digest"],
        "post_incident_latest_closure_record_id": gate["latest_closure_record_id"],
    }
    return runtime, incident, flag, gate, approval


class M71NoIndependentIncidentSourceDenialTests(unittest.TestCase):
    def assert_no_effect(self, result, *, reason=None):
        self.assertEqual(result["state"], "BLOCKED", result)
        self.assertIs(result.get("reactivation_authorized", False), False)
        self.assertIs(result.get("feature_flag_modified", False), False)
        self.assertIs(result.get("global_worker_executed", False), False)
        if reason is not None:
            self.assertEqual(result["reason"], reason, result)

    def test_01_valid_five_minute_old_ready_still_requires_independent_source(self):
        runtime, _, flag, gate, approval = setup_gate()
        result = validate(runtime, flag, approval, gate, now=NOW + timedelta(seconds=10))
        self.assert_no_effect(result, reason=NO_TRUST)

    def test_02_ready_immediately_after_healthy_reconciliation_does_not_grant_execution(self):
        runtime, _, flag, gate, approval = setup_gate()
        self.assert_no_effect(validate(runtime, flag, approval, gate, now=NOW), reason=NO_TRUST)

    def test_03_reopened_incident_replayed_ready_is_denied(self):
        runtime, incident, flag, gate, approval = setup_gate()
        reopened = deepcopy(incident)
        reopened["generated_at"] = (NOW + timedelta(seconds=10)).isoformat()
        state = reconcile_global_worker_incident_center({}, reopened, runtime, now=NOW + timedelta(seconds=10))
        self.assertEqual(state["global_worker_reconciliation"]["state"], "REOPENED")
        self.assert_no_effect(validate(runtime, flag, approval, gate, now=NOW + timedelta(seconds=10)), reason=NO_TRUST)

    def test_04_forged_approval_claim_of_fresh_external_incident_source_does_not_enroll(self):
        runtime, _, flag, gate, approval = setup_gate()
        approval["incident_source_authenticated"] = True
        approval["independent_source_enrolled"] = True
        approval["reconciled_after_gate"] = True
        self.assert_no_effect(validate(runtime, flag, approval, gate, now=NOW), reason=NO_TRUST)

    def test_05_no_durable_incident_history_does_not_prove_freshness(self):
        runtime = {"status":"CONFIRMED","checkpoint":_armed_checkpoint(),"sha":"no-ledger-synthetic"}
        self.assert_no_effect(validate(runtime, _safe_flag(), {"post_incident_gate_required":False}, None, now=NOW), reason=NO_TRUST)

    def test_06_invalid_gate_rejected_before_any_claimed_trust(self):
        runtime, _, flag, gate, approval = setup_gate()
        invalid = deepcopy(gate)
        invalid["activation_plan_allowed"] = False
        self.assert_no_effect(validate(runtime, flag, approval, invalid, now=NOW),
                              reason="FRESH_POST_INCIDENT_GATE_INTEGRITY_MISMATCH")

    def test_07_expired_ready_gate_remains_blocked(self):
        runtime, _, flag, gate, approval = setup_gate()
        self.assert_no_effect(validate(runtime, flag, approval, gate,
                                       now=NOW + timedelta(minutes=7)),
                              reason="FRESH_POST_INCIDENT_GATE_EXPIRED")

    def test_08_inputs_not_mutated_to_forge_newer_reconciliation(self):
        runtime, _, flag, gate, approval = setup_gate()
        previous = deepcopy((runtime, flag, gate, approval))
        self.assert_no_effect(validate(runtime, flag, approval, gate, now=NOW), reason=NO_TRUST)
        self.assertEqual((runtime, flag, gate, approval), previous)

    def test_09_mismatched_approval_requires_local_contract_before_external_source(self):
        runtime, _, flag, gate, approval = setup_gate()
        approval["post_incident_latest_closure_record_id"] = "forged-old-closure"
        self.assert_no_effect(validate(runtime, flag, approval, gate, now=NOW),
                              reason="POST_INCIDENT_APPROVAL_CLOSURE_BINDING_CHANGED")

    def test_10_forced_no_history_with_required_approval_still_denies(self):
        runtime = {"status":"CONFIRMED","checkpoint":_armed_checkpoint(),"sha":"no-ledger-synthetic"}
        self.assert_no_effect(validate(runtime, _safe_flag(), {"post_incident_gate_required":True}, None, now=NOW),
                              reason="POST_INCIDENT_GATE_REQUIREMENT_CHANGED")


if __name__ == "__main__":
    unittest.main()
