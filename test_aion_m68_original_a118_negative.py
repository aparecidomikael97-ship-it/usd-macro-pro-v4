"""M68 LAB: two negative checks on original A118 modules and original fixtures.

Safety: synthetic in-memory inputs only. This file never calls activation,
approval, feature-flag writers, real providers, deploy or Worker execution.
Original A118 source is pinned at c62fab663c6349d7320f7843c8d09587c514426b.
M67 prepared these cases but did not execute them; M68 owns any new CI result.
"""
import unittest
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from atlasquant_aion_global_worker_activation import (
    prepare_global_worker_activation_plan,
)
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
    _access,
    _post_incident_runtime,
    _readiness,
    _safe_flag,
    _safe_reconciled_snapshot,
)


class M68OriginalA118NegativeTests(unittest.TestCase):
    def test_n_m67_01_ready_diagnostics_cannot_mint_activation_plan(self):
        runtime, _ = _post_incident_runtime()
        readiness = _readiness()
        flag = _safe_flag()
        gate = assess_post_incident_reactivation_gate(
            runtime,
            _safe_reconciled_snapshot(runtime),
            readiness,
            flag,
            now=NOW,
        )
        self.assertEqual(gate["status"], READY_STATUS)
        self.assertFalse(gate["reactivation_authorized"])
        before_runtime, before_readiness, before_flag = (
            deepcopy(runtime), deepcopy(readiness), deepcopy(flag)
        )
        # Any writer invocation is an immediate test failure, even with fake inputs.
        with patch(
            "atlasquant_aion_global_worker_activation.write_repository_feature_flag_enabled",
            side_effect=AssertionError("WRITER_MUST_NOT_BE_CALLED"),
        ) as writer:
            result = prepare_global_worker_activation_plan(
                _access(),
                runtime,
                readiness,
                flag,
                reactivation_gate=gate,
                now=NOW,
            )
            writer.assert_not_called()
        self.assertEqual(result.get("status"), "BLOCKED")
        self.assertEqual(
            result.get("reason"), "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED"
        )
        self.assertNotIn("plan", result)
        self.assertNotIn("approval", result)
        self.assertIs(result.get("feature_flag_modified"), False)
        self.assertIs(result.get("global_worker_executed"), False)
        self.assertEqual(runtime, before_runtime)
        self.assertEqual(readiness, before_readiness)
        self.assertEqual(flag, before_flag)

    def test_n_m67_02_reopened_incident_blocks_gate_and_validation(self):
        runtime, incident = _post_incident_runtime()
        readiness = _readiness()
        flag = _safe_flag()
        safe_gate = assess_post_incident_reactivation_gate(
            runtime,
            _safe_reconciled_snapshot(runtime),
            readiness,
            flag,
            now=NOW,
        )
        self.assertEqual(safe_gate["status"], READY_STATUS)
        before_runtime, before_flag = deepcopy(runtime), deepcopy(flag)
        reopened_at = NOW + timedelta(seconds=10)
        reopened = deepcopy(incident)
        reopened["generated_at"] = reopened_at.isoformat()
        snapshot = reconcile_global_worker_incident_center(
            {}, reopened, runtime, now=reopened_at
        )
        self.assertEqual(
            snapshot["global_worker_reconciliation"]["state"], "REOPENED"
        )
        blocked_gate = assess_post_incident_reactivation_gate(
            runtime,
            snapshot,
            readiness,
            flag,
            now=reopened_at,
        )
        self.assertEqual(blocked_gate["status"], BLOCKED_STATUS)
        self.assertIn(
            "ACTIVE_GLOBAL_WORKER_INCIDENT_PRESENT",
            blocked_gate.get("blockers", []),
        )
        self.assertIs(blocked_gate["activation_plan_allowed"], False)
        self.assertIs(blocked_gate["reactivation_authorized"], False)

        # Deliberately synthetic mapping ONLY for a negative validator check.
        # It is not an approval issued or signed by any authority.
        fake_approval = {
            "post_incident_gate_required": True,
            "post_incident_closure_ledger_digest": safe_gate["closure_ledger_digest"],
            "post_incident_latest_closure_record_id":
                safe_gate["latest_closure_record_id"],
        }
        result = validate_reactivation_gate_for_execution(
            runtime, flag, fake_approval, blocked_gate, now=reopened_at
        )
        self.assertEqual(result.get("state"), "BLOCKED")
        self.assertEqual(
            result.get("reason"), "FRESH_POST_INCIDENT_GATE_INTEGRITY_MISMATCH"
        )
        self.assertEqual(runtime, before_runtime)
        self.assertEqual(flag, before_flag)


if __name__ == "__main__":
    unittest.main()
