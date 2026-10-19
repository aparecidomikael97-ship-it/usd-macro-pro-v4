"""M71 independent RED contract: a pre-reopening READY gate must not validate later.

No external authorization, no Writer, no Worker, no provider, no merge/deploy.
Synthetic mapping is ONLY a negative validator input, not a real approval.
Pin: A118 original source c62fab663c6349d7320f7843c8d09587c514426b.
"""
import unittest
from copy import deepcopy
from datetime import timedelta

from atlasquant_aion_global_worker_incident_reconciliation import (
    reconcile_global_worker_incident_center,
)
from atlasquant_aion_global_worker_reactivation_gate import (
    BLOCKED_STATUS,
    READY_STATUS,
    assess_post_incident_reactivation_gate,
    validate_reactivation_gate_for_execution,
)
from test_atlasquant_aion_global_worker_reactivation_gate import (
    NOW,
    _post_incident_runtime,
    _readiness,
    _safe_flag,
    _safe_reconciled_snapshot,
)


class M71OriginalGateReplayNegativeTest(unittest.TestCase):
    def test_reopened_incident_invalidates_pre_reopening_ready_gate(self):
        runtime, incident = _post_incident_runtime()
        readiness, flag = _readiness(), _safe_flag()
        safe_gate = assess_post_incident_reactivation_gate(
            runtime, _safe_reconciled_snapshot(runtime), readiness, flag, now=NOW
        )
        self.assertEqual(safe_gate["status"], READY_STATUS)
        self.assertIs(safe_gate["reactivation_authorized"], False)

        reopened_at = NOW + timedelta(seconds=10)
        reopened = deepcopy(incident)
        reopened["generated_at"] = reopened_at.isoformat()
        reopened_snapshot = reconcile_global_worker_incident_center(
            {}, reopened, runtime, now=reopened_at
        )
        self.assertEqual(
            reopened_snapshot["global_worker_reconciliation"]["state"], "REOPENED"
        )
        fresh_gate = assess_post_incident_reactivation_gate(
            runtime, reopened_snapshot, readiness, flag, now=reopened_at
        )
        self.assertEqual(fresh_gate["status"], BLOCKED_STATUS)
        self.assertIn(
            "ACTIVE_GLOBAL_WORKER_INCIDENT_PRESENT", fresh_gate["blockers"]
        )

        # Only the shape required by validate_reactivation_gate_for_execution.
        # This is NOT a signed or even issued approval and cannot activate A118.
        synthetic_negative_input = {
            "post_incident_gate_required": True,
            "post_incident_closure_ledger_digest":
                safe_gate["closure_ledger_digest"],
            "post_incident_latest_closure_record_id":
                safe_gate["latest_closure_record_id"],
        }
        with_fresh_evidence = validate_reactivation_gate_for_execution(
            runtime, flag, synthetic_negative_input, fresh_gate, now=reopened_at
        )
        self.assertEqual(with_fresh_evidence["state"], "BLOCKED")

        # Adversarial replay: stale pre-reopening gate remains inside TTL.
        # Desired safety property is BLOCKED, even though caller replays READY.
        replayed = validate_reactivation_gate_for_execution(
            runtime, flag, synthetic_negative_input, safe_gate, now=reopened_at
        )
        self.assertEqual(
            replayed["state"],
            "BLOCKED",
            "M71_RED_STALE_READY_GATE_ACCEPTED_AFTER_REOPENED_INCIDENT",
        )


if __name__ == "__main__":
    unittest.main()
