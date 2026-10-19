"""M71 P0 LAB: no external incident authority means NO execution READY.

Tests were authored BEFORE any modification to the A118 public reactivation
validator. The original independent M71 RED is also run directly in CI.
A digest, caller-supplied gate, TTL, or local reconciliation snapshot is
NOT proof of incident freshness immediately before flag enable.
No Worker execution, deploy, flag writing, or network.
"""
from copy import deepcopy
from datetime import timedelta
import unittest

import test_atlasquant_aion_global_worker_reactivation_gate as fixture
from atlasquant_aion_global_worker_incident_reconciliation import (
    reconcile_global_worker_incident_center,
)
from atlasquant_aion_global_worker_reactivation_gate import (
    READY_STATUS, BLOCKED_STATUS, _payload_digest,
    assess_post_incident_reactivation_gate,
    gate_integrity,
    validate_reactivation_gate_for_execution,
    validate_reactivation_gate_for_plan,
)

NOW=fixture.NOW
FRESH_SOURCE_MISSING="FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED"


class M71ExecutionFreshSourceDenialTests(unittest.TestCase):
    def setUp(self):
        self.runtime, self.incident=fixture._post_incident_runtime()
        self.readiness=fixture._readiness()
        self.flag=fixture._safe_flag()
        self.safe_gate=assess_post_incident_reactivation_gate(
            self.runtime,fixture._safe_reconciled_snapshot(self.runtime),
            self.readiness,self.flag,now=NOW,
        )
        self.assertEqual(self.safe_gate["status"],READY_STATUS)
        self.approval={
            "post_incident_gate_required":True,
            "post_incident_closure_ledger_digest":self.safe_gate["closure_ledger_digest"],
            "post_incident_latest_closure_record_id":self.safe_gate["latest_closure_record_id"],
        }

    def check_untrusted(self, gate=None, runtime=None, approval=None, when=None):
        result=validate_reactivation_gate_for_execution(
            self.runtime if runtime is None else runtime,
            self.flag,
            self.approval if approval is None else approval,
            self.safe_gate if gate is None else gate,
            now=NOW if when is None else when,
        )
        self.assertEqual(result["state"],"BLOCKED",result)
        self.assertIs(result.get("reactivation_authorized",False),False)
        self.assertIs(result.get("feature_flag_modified",False),False)
        self.assertIs(result.get("global_worker_executed",False),False)
        return result

    def test_01_reopened_incident_rejects_previous_ready_during_ttl(self):
        reopened=deepcopy(self.incident)
        reopened["generated_at"]=(NOW+timedelta(seconds=10)).isoformat()
        snapshot=reconcile_global_worker_incident_center(
            {},reopened,self.runtime,now=NOW+timedelta(seconds=10),
        )
        self.assertEqual(snapshot["global_worker_reconciliation"]["state"],"REOPENED")
        current=assess_post_incident_reactivation_gate(
            self.runtime,snapshot,self.readiness,self.flag,
            now=NOW+timedelta(seconds=10),
        )
        self.assertEqual(current["status"],BLOCKED_STATUS)
        result=self.check_untrusted(when=NOW+timedelta(seconds=10))
        self.assertEqual(result["reason"],FRESH_SOURCE_MISSING)

    def test_02_unexpired_ready_gate_not_execution_authority_even_without_visible_reopen(self):
        result=self.check_untrusted()
        self.assertEqual(result["reason"],FRESH_SOURCE_MISSING)

    def test_03_gate_not_required_after_missing_local_history_is_not_external_proof(self):
        no_history={
            "status":"CONFIRMED","checkpoint":fixture._armed_checkpoint(),
            "sha":"synthetic-no-history-runtime",
        }
        out=validate_reactivation_gate_for_execution(
            no_history,self.flag,{"post_incident_gate_required":False},
            None,now=NOW,
        )
        self.assertEqual(out["state"],"BLOCKED",out)
        self.assertEqual(out["reason"],FRESH_SOURCE_MISSING)

    def test_04_synthetic_claim_fields_in_gate_cannot_create_incident_authority(self):
        forged=deepcopy(self.safe_gate)
        forged["independent_witness_authenticated"]=True
        forged["latest_incident_checked_after_reopen"]=True
        forged["source_freshness_confirmed"]=True
        forged["gate_digest"]=_payload_digest(forged,"gate_digest")
        self.assertEqual(gate_integrity(forged)["state"],"MATCH")
        self.assertEqual(self.check_untrusted(gate=forged)["reason"],FRESH_SOURCE_MISSING)

    def test_05_self_claimed_approval_authority_does_not_unlock(self):
        forged=deepcopy(self.approval)
        forged.update({"independent_witness_authenticated":True,
                       "post_incident_snapshot":fixture._safe_reconciled_snapshot(self.runtime),
                       "fresh_source":True,"owner_confirmed":True})
        self.assertEqual(self.check_untrusted(approval=forged)["reason"],FRESH_SOURCE_MISSING)

    def test_06_public_plan_assessment_remains_readonly_ready_but_not_execution(self):
        planned=validate_reactivation_gate_for_plan(
            self.runtime,self.readiness,self.flag,self.safe_gate,now=NOW,
        )
        self.assertEqual(planned["state"],"READY")
        self.assertEqual(self.check_untrusted()["reason"],FRESH_SOURCE_MISSING)

    def test_07_expired_gate_retains_expired_reason(self):
        self.assertEqual(
            self.check_untrusted(when=NOW+timedelta(minutes=6))["reason"],
            "FRESH_POST_INCIDENT_GATE_EXPIRED",
        )

    def test_08_corrupted_digest_remains_rejected(self):
        broken=deepcopy(self.safe_gate)
        broken["runtime_sha"]="altered"
        self.assertEqual(
            self.check_untrusted(gate=broken)["reason"],
            "FRESH_POST_INCIDENT_GATE_INTEGRITY_MISMATCH",
        )

    def test_09_runtime_sha_binding_still_checked(self):
        modified=deepcopy(self.runtime)
        modified["sha"]="different-runtime-sha"
        self.assertEqual(
            self.check_untrusted(runtime=modified)["reason"],
            "FRESH_POST_INCIDENT_GATE_RUNTIME_SHA_CHANGED",
        )

    def test_10_latest_approval_closure_binding_still_checked(self):
        approval=deepcopy(self.approval)
        approval["post_incident_latest_closure_record_id"]="changed-closure"
        self.assertEqual(
            self.check_untrusted(approval=approval)["reason"],
            "POST_INCIDENT_APPROVAL_CLOSURE_BINDING_CHANGED",
        )

    def test_11_blocked_incident_gate_cannot_be_bypassed(self):
        reopened=deepcopy(self.incident)
        reopened["generated_at"]=(NOW+timedelta(seconds=1)).isoformat()
        snapshot=reconcile_global_worker_incident_center(
            {},reopened,self.runtime,now=NOW+timedelta(seconds=1)
        )
        denied=assess_post_incident_reactivation_gate(
            self.runtime,snapshot,self.readiness,self.flag,now=NOW+timedelta(seconds=1)
        )
        self.assertEqual(denied["status"],BLOCKED_STATUS)
        self.assertEqual(
            self.check_untrusted(gate=denied,when=NOW+timedelta(seconds=1))["reason"],
            "FRESH_POST_INCIDENT_GATE_INTEGRITY_MISMATCH",
        )

    def test_12_requirement_mismatch_still_blocks(self):
        approval=deepcopy(self.approval)
        approval["post_incident_gate_required"]=False
        self.assertEqual(
            self.check_untrusted(approval=approval)["reason"],
            "POST_INCIDENT_GATE_REQUIREMENT_CHANGED",
        )


if __name__=="__main__":
    unittest.main()
