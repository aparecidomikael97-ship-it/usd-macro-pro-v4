"""Negative audit of A53/A76 legacy READY expectations after M71 fail-closed.

These tests do not waive or modify either canonical test. They document the
current implementation's independent-source DENIAL, demonstrate the canonical
expectation mismatch and preserve the 86-event RED baseline. A PASS here
is merely a characterization of why those historical assertions fail.

No GitHub writer, external network, Worker activation, credential enrollment.
"""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch
import unittest

import atlasquant_aion_global_worker_activation as activation
import atlasquant_aion_global_worker_reactivation_gate as gates
import test_atlasquant_aion_global_worker_activation as prior
import test_atlasquant_aion_global_worker_reactivation_gate as incident
import test_atlasquant_aion_activation_authority_a74 as old_fixture


DENIAL="FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED"
PLAN_DENIAL="INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED"


class A53A76NoExternalIncidentSourceAuditLAB(unittest.TestCase):
    def setUp(self):
        self.guard=old_fixture.A74PlanTicketDenialTests()
        self.guard.setUp()
        self.now=self.guard.now

    def test_01_original_a53_legacy_ready_plan_now_denied_before_approval(self):
        f=prior.GlobalWorkerActivationCeremonyTests()
        f.setUp()
        result=activation.prepare_global_worker_activation_plan(
            f.access,f.runtime,f.readiness,prior._safe_flag("UNSET"),
            now=prior.NOW)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["reason"],PLAN_DENIAL)
        self.assertNotIn("plan",result)
        self.assertIs(result.get("global_worker_executed"),False)
        self.assertIs(result.get("feature_flag_modified"),False)

    def test_02_no_ledger_requirement_still_requires_external_fresh_source(self):
        f=prior.GlobalWorkerActivationCeremonyTests()
        f.setUp()
        value=gates.validate_reactivation_gate_for_execution(
            f.runtime,prior._safe_flag("UNSET"),
            {"post_incident_gate_required":False},None,now=prior.NOW)
        self.assertEqual(value["state"],"BLOCKED")
        self.assertEqual(value["reason"],DENIAL)
        self.assertIs(value["gate_required"],False)
        self.assertIs(value["reactivation_authorized"],False)

    def test_03_a76_fully_consistent_legacy_gate_is_still_execution_denied(self):
        runtime, _=incident._post_incident_runtime()
        readiness,flag=incident._readiness(),incident._safe_flag()
        snapshot=incident._safe_reconciled_snapshot(runtime)
        gate=gates.assess_post_incident_reactivation_gate(
            runtime,snapshot,readiness,flag,now=incident.NOW)
        self.assertEqual(gates.gate_integrity(gate)["state"],"MATCH")
        self.assertIs(gate["reactivation_authorized"],False)
        approval={
            "post_incident_gate_required":True,
            "post_incident_closure_ledger_digest":gate["closure_ledger_digest"],
            "post_incident_latest_closure_record_id":gate["latest_closure_record_id"],
        }
        value=gates.validate_reactivation_gate_for_execution(
            runtime,flag,approval,gate,now=incident.NOW)
        self.assertEqual(value["state"],"BLOCKED")
        self.assertEqual(value["reason"],DENIAL)
        self.assertIs(value["gate_required"],True)
        self.assertIs(value["reactivation_authorized"],False)
        self.assertEqual(value["gate_digest"],gate["gate_digest"])

    def test_04_plan_shape_ready_does_not_authorize_execution(self):
        runtime, _=incident._post_incident_runtime()
        readiness,flag=incident._readiness(),incident._safe_flag()
        snap=incident._safe_reconciled_snapshot(runtime)
        gate=gates.assess_post_incident_reactivation_gate(
            runtime,snap,readiness,flag,now=incident.NOW)
        shape=gates.validate_reactivation_gate_for_plan(
            runtime,readiness,flag,gate,now=incident.NOW)
        execution=gates.validate_reactivation_gate_for_execution(
            runtime,flag,{"post_incident_gate_required":True,
                          "post_incident_closure_ledger_digest":gate["closure_ledger_digest"],
                          "post_incident_latest_closure_record_id":gate["latest_closure_record_id"]},
            gate,now=incident.NOW)
        self.assertEqual(shape["state"],"READY")
        self.assertEqual(execution["state"],"BLOCKED")
        self.assertEqual(execution["reason"],DENIAL)
        self.assertFalse(execution["reactivation_authorized"])

    def test_05_self_asserted_independent_source_booleans_cannot_make_plan(self):
        f=prior.GlobalWorkerActivationCeremonyTests()
        f.setUp()
        for claimed in (False,True):
            with self.subTest(claimed=claimed):
                readiness=deepcopy(f.readiness)
                for key in ("source_authenticity_verified","independent_witness_verified",
                            "source_resource_owner_bound","external_activation_allowed"):
                    readiness[key]=claimed
                result=activation.prepare_global_worker_activation_plan(
                    f.access,f.runtime,readiness,prior._safe_flag("UNSET"),
                    now=prior.NOW)
                self.assertEqual(result["status"],"BLOCKED")
                self.assertEqual(result["reason"],PLAN_DENIAL)
                self.assertNotIn("plan",result)

    def test_06_locally_signed_historical_plan_not_a_ticket(self):
        f=old_fixture.A74PlanTicketDenialTests()
        f.setUp()
        local=f.legacy_plan()
        response=activation.approve_global_worker_activation_plan(
            f.fixture.access,local,confirmation=True,
            confirmation_phrase=activation.CONFIRMATION_PHRASE,now=f.now)
        self.assertEqual(response["status"],"BLOCKED")
        self.assertEqual(response["reason"],PLAN_DENIAL)
        self.assertNotIn("approval",response)

    def test_07_local_signature_does_not_unlock_activation_write(self):
        f=old_fixture.A74PlanTicketDenialTests()
        f.setUp()
        ticket=f.legacy_ticket()
        with patch.object(activation,"write_repository_feature_flag_enabled",
                          side_effect=AssertionError("WRITER_MUST_NOT_RUN")) as writer:
            outcome=activation.validate_global_worker_activation_approval(
                f.fixture.access,ticket,f.fixture.runtime,
                prior._safe_flag("UNSET"),now=f.now)
            self.assertEqual(outcome["state"],"BLOCKED")
            writer.assert_not_called()

    def test_08_runtime_and_reactivation_gate_input_not_mutated(self):
        runtime, _=incident._post_incident_runtime()
        flag=incident._safe_flag()
        readiness=incident._readiness()
        gate=gates.assess_post_incident_reactivation_gate(
            runtime,incident._safe_reconciled_snapshot(runtime),
            readiness,flag,now=incident.NOW)
        inputs=deepcopy((runtime,flag,gate))
        approval={"post_incident_gate_required":True,
                  "post_incident_closure_ledger_digest":gate["closure_ledger_digest"],
                  "post_incident_latest_closure_record_id":gate["latest_closure_record_id"]}
        for _ in range(3):
            x=gates.validate_reactivation_gate_for_execution(
                runtime,flag,approval,gate,now=incident.NOW)
            self.assertEqual(x["reason"],DENIAL)
        self.assertEqual((runtime,flag,gate),inputs)

    def test_09_true_auth_flags_on_fake_execution_approval_still_fail_closed(self):
        runtime,_=incident._post_incident_runtime()
        readiness,flag=incident._readiness(),incident._safe_flag()
        gate=gates.assess_post_incident_reactivation_gate(
            runtime,incident._safe_reconciled_snapshot(runtime),
            readiness,flag,now=incident.NOW)
        approval={
            "post_incident_gate_required":True,
            "post_incident_closure_ledger_digest":gate["closure_ledger_digest"],
            "post_incident_latest_closure_record_id":gate["latest_closure_record_id"],
            "independent_source_verified":True,"issuer_signature_verified":True,
            "external_authority_verified":True,"human_owner_approved":True,
        }
        x=gates.validate_reactivation_gate_for_execution(
            runtime,flag,approval,gate,now=incident.NOW)
        self.assertEqual(x["state"],"BLOCKED")
        self.assertEqual(x["reason"],DENIAL)
        self.assertIs(x["reactivation_authorized"],False)

    def test_10_a76_expected_ready_is_a_historical_assertion_not_new_gate_pass(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        source=(root/"test_atlasquant_aion_activation_denial_coverage_a76.py").read_text()
        self.assertIn('self.assertEqual(e["state"], "READY")',source)
        self.assertIn('self.assertIs(e["reactivation_authorized"], False)',source)
        current=(root/"atlasquant_aion_global_worker_reactivation_gate.py").read_text()
        self.assertIn('"FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED"',current)
        self.assertIn("Do not add a caller-provided",current)

    def test_11_a53_historical_ticket_fixture_expected_plan_ready_not_authority(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/
                "test_atlasquant_aion_global_worker_activation.py").read_text()
        self.assertIn('self.assertEqual(result["status"], "ACTIVATION_PLAN_READY")',source)
        self.assertIn("test_a53_local_ticket_cannot_authorize_injected_activation_writer",source)

    def test_12_synthetic_lab_cannot_be_promoted_to_p0(self):
        f=prior.GlobalWorkerActivationCeremonyTests()
        f.setUp()
        out=activation.prepare_global_worker_activation_plan(
            f.access,f.runtime,f.readiness,prior._safe_flag("UNSET"),
            now=prior.NOW)
        self.assertIs(out.get("feature_flag_modified"),False)
        self.assertIs(out.get("global_worker_executed"),False)
        self.assertEqual(out["status"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
