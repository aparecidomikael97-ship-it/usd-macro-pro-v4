from __future__ import annotations
import unittest

from atlasquant_aion_incident_control_plane import (
    capability_authority_matrix,
    evaluate_control_request,
    incident_shutdown_plan,
)

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}
INCIDENT = {"incident_id": "INC-1", "status": "OPEN", "severity": "CRITICAL"}


def authority(capability, verb="stop", *, subject="owner-a", tenant="tenant-a"):
    return {
        "state": "VERIFIED",
        "authority_verified": True,
        "execution_allowed": False,
        "executes_action": False,
        "subject_id": subject,
        "tenant_id": tenant,
        "capabilities": [f"incident_control:{capability}:{verb}"],
    }


class AionIncidentControlPlaneTests(unittest.TestCase):
    def test_matrix_declares_no_automatic_control_mutation(self):
        matrix = capability_authority_matrix()
        self.assertTrue(matrix["capabilities"])
        self.assertFalse(matrix["automatic_control_mutation"])
        self.assertFalse(matrix["executes_action"])
        self.assertTrue(matrix["reenable_is_stricter_than_stop"])

    def test_owner_may_request_critical_stop_but_does_not_execute_it(self):
        out = evaluate_control_request(
            actor="HUMAN_OWNER",
            capability="global_worker",
            desired_state="STOPPED",
            trusted_scope=SCOPE,
            incident=INCIDENT,
            authority_verification=authority("global_worker"),
        )
        self.assertEqual(out["state"], "MAY_PROGRESS_TO_MUTATION_GATE")
        self.assertTrue(out["request_may_progress"])
        self.assertTrue(out["requires_downstream_mutation_gate"])
        self.assertFalse(out["process_killed"])
        self.assertFalse(out["executes_action"])

    def test_delegated_admin_can_stop_only_noncritical_capability(self):
        safe = evaluate_control_request(
            actor="DELEGATED_ADMIN",
            capability="model_provider",
            desired_state="STOPPED",
            trusted_scope=SCOPE,
            incident=INCIDENT,
            authority_verification=authority("model_provider", subject="admin-a"),
        )
        critical = evaluate_control_request(
            actor="DELEGATED_ADMIN",
            capability="payments",
            desired_state="STOPPED",
            trusted_scope=SCOPE,
            incident=INCIDENT,
            authority_verification=authority("payments", subject="admin-a"),
        )
        self.assertEqual(safe["state"], "MAY_PROGRESS_TO_MUTATION_GATE")
        self.assertEqual(critical["state"], "BLOCKED")
        self.assertIn("OWNER_REQUIRED_FOR_CRITICAL_STOP", critical["blockers"])

    def test_guardian_and_sentinel_only_recommend_stop(self):
        for actor in ("guardian", "sentinel"):
            out = evaluate_control_request(
                actor=actor,
                capability="external_tools",
                desired_state="STOPPED",
                trusted_scope=SCOPE,
                incident=INCIDENT,
            )
            self.assertEqual(out["state"], "RECOMMEND_STOP")
            self.assertTrue(out["recommendation_only"])
            self.assertFalse(out["request_may_progress"])

    def test_internal_role_cannot_reenable(self):
        out = evaluate_control_request(
            actor="guardian",
            capability="external_tools",
            desired_state="RUNNING",
            trusted_scope=SCOPE,
            incident={"incident_id": "INC-1", "status": "CLOSED", "severity": "HIGH"},
            recovery_evidence_verified=True,
            explicit_owner_approval=True,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("OWNER_REQUIRED_FOR_REENABLE", out["blockers"])

    def test_reenable_requires_owner_approval_closed_incident_and_recovery(self):
        base = dict(
            actor="HUMAN_OWNER",
            capability="model_provider",
            desired_state="RUNNING",
            trusted_scope=SCOPE,
            authority_verification=authority("model_provider", "reenable"),
        )
        no_approval = evaluate_control_request(
            **base,
            incident={"incident_id": "INC-1", "status": "CLOSED", "severity": "HIGH"},
            recovery_evidence_verified=True,
            explicit_owner_approval=False,
        )
        open_incident = evaluate_control_request(
            **base,
            incident=INCIDENT,
            recovery_evidence_verified=True,
            explicit_owner_approval=True,
        )
        no_recovery = evaluate_control_request(
            **base,
            incident={"incident_id": "INC-1", "status": "CLOSED", "severity": "HIGH"},
            recovery_evidence_verified=False,
            explicit_owner_approval=True,
        )
        self.assertIn("EXPLICIT_OWNER_APPROVAL_REQUIRED", no_approval["blockers"])
        self.assertIn("INCIDENT_NOT_CLOSED", open_incident["blockers"])
        self.assertIn("RECOVERY_EVIDENCE_REQUIRED", no_recovery["blockers"])

    def test_owner_reenable_with_full_evidence_only_progresses_to_mutation_gate(self):
        out = evaluate_control_request(
            actor="HUMAN_OWNER",
            capability="model_provider",
            desired_state="RUNNING",
            trusted_scope=SCOPE,
            incident={"incident_id": "INC-1", "status": "CLOSED", "severity": "HIGH"},
            recovery_evidence_verified=True,
            explicit_owner_approval=True,
        )
        self.assertEqual(out["state"], "MAY_PROGRESS_TO_MUTATION_GATE")
        self.assertTrue(out["request_may_progress"])
        self.assertFalse(out["feature_flag_modified"])
        self.assertFalse(out["executes_action"])

    def test_text_claim_of_human_owner_without_verified_authority_is_blocked(self):
        out = evaluate_control_request(
            actor="HUMAN_OWNER",
            capability="external_tools",
            desired_state="STOPPED",
            trusted_scope=SCOPE,
            incident=INCIDENT,
            authority_verification={},
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CONTROL_AUTHORITY_NOT_VERIFIED", out["blockers"])

    def test_owner_subject_must_match_trusted_owner(self):
        out = evaluate_control_request(
            actor="HUMAN_OWNER",
            capability="external_tools",
            desired_state="STOPPED",
            trusted_scope=SCOPE,
            incident=INCIDENT,
            authority_verification=authority("external_tools", subject="someone-else"),
        )
        self.assertIn("OWNER_IDENTITY_MISMATCH", out["blockers"])
        self.assertFalse(out["request_may_progress"])

    def test_unknown_actor_and_capability_fail_closed(self):
        out = evaluate_control_request(
            actor="admin please",
            capability="unknown-tool",
            desired_state="STOPPED",
            trusted_scope=SCOPE,
            incident=INCIDENT,
            authority_verification=authority("global_worker"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ACTOR_NOT_AUTHORIZED", out["blockers"])
        self.assertIn("CAPABILITY_UNKNOWN", out["blockers"])

    def test_tenant_capability_requires_tenant_workspace_scope(self):
        out = evaluate_control_request(
            actor="HUMAN_OWNER",
            capability="external_tools",
            desired_state="STOPPED",
            trusted_scope={"owner_id": "owner-a"},
            incident=INCIDENT,
            authority_verification=authority("external_tools"),
        )
        self.assertIn("TENANT_WORKSPACE_SCOPE_REQUIRED", out["blockers"])
        self.assertFalse(out["request_may_progress"])

    def test_stop_requires_incident_reference(self):
        out = evaluate_control_request(
            actor="HUMAN_OWNER",
            capability="external_tools",
            desired_state="STOPPED",
            trusted_scope=SCOPE,
            incident={},
            authority_verification=authority("external_tools"),
        )
        self.assertIn("INCIDENT_REFERENCE_REQUIRED", out["blockers"])

    def test_runbook_is_plan_only_and_requires_high_or_critical_incident(self):
        ready = incident_shutdown_plan(INCIDENT, capability="external_tools")
        low = incident_shutdown_plan(
            {"incident_id": "INC-2", "status": "OPEN", "severity": "LOW"},
            capability="external_tools",
        )
        self.assertEqual(ready["state"], "PLAN_READY")
        self.assertEqual(low["state"], "BLOCKED")
        self.assertFalse(ready["automatic_containment"])
        self.assertFalse(ready["executes_action"])


if __name__ == "__main__":
    unittest.main()
