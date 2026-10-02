import unittest

from atlasquant_aion_tenant_evidence_binding import build_evidence_record
from atlasquant_aion_tenant_persistence_gate import (
    REQUIRED_EVIDENCE,
    tenant_persistence_readiness,
)


def _pass_evidence():
    return {
        name: build_evidence_record(
            name,
            subject_digest="sha256:" + ("a" * 64),
            result_digest="sha256:" + ("b" * 64),
            test_count=10,
        )
        for name in REQUIRED_EVIDENCE
    }


class AionTenantPersistenceGateTests(unittest.TestCase):
    def test_current_code_is_ready_locally_but_blocked_without_evidence(self):
        result = tenant_persistence_readiness()
        self.assertEqual(result["state"], "BLOCKED")
        self.assertTrue(result["code_ready"])
        self.assertTrue(result["local_durable_ready"])
        self.assertNotIn("LOCAL_DURABLE_STORE_NOT_READY", result["blockers"])
        self.assertIn("EVIDENCE_DURABLE_STORE_MISSING", result["blockers"])
        self.assertFalse(result["persistence_activation_authorized"])
        self.assertFalse(result["automatic_activation"])

    def test_green_evidence_only_reaches_admin_review_never_activation(self):
        result = tenant_persistence_readiness(_pass_evidence())
        self.assertTrue(result["evidence_ready"])
        self.assertTrue(result["code_ready"])
        self.assertEqual(result["state"], "READY_FOR_ADMIN_REVIEW")
        self.assertFalse(result["evidence_is_authority"])
        self.assertFalse(result["persistence_activation_authorized"])
        self.assertFalse(result["automatic_activation"])

    def test_missing_evidence_is_explicit(self):
        result = tenant_persistence_readiness({})
        for name in REQUIRED_EVIDENCE:
            self.assertIn(f"EVIDENCE_{name}_MISSING", result["blockers"])
        self.assertFalse(result["evidence_ready"])

    def test_pass_without_bound_digest_is_not_valid_evidence(self):
        evidence = _pass_evidence()
        evidence["ACL_STORE"]["digest"] = "not-a-bound-digest"
        result = tenant_persistence_readiness(evidence)
        self.assertIn("EVIDENCE_ACL_STORE_BINDING_INVALID", result["blockers"])
        self.assertFalse(result["evidence"]["ACL_STORE"]["valid"])
        self.assertFalse(result["evidence_ready"])

    def test_wrong_evidence_scope_is_blocking(self):
        evidence = _pass_evidence()
        evidence["ACL_STORE"]["scope"] = "admin/global"
        result = tenant_persistence_readiness(evidence)
        self.assertIn("EVIDENCE_ACL_STORE_BINDING_INVALID", result["blockers"])
        self.assertFalse(result["evidence_ready"])

    def test_failed_evidence_remains_blocking(self):
        evidence = _pass_evidence()
        evidence["TENANT_E2E"] = build_evidence_record(
            "TENANT_E2E",
            subject_digest="sha256:" + ("a" * 64),
            result_digest="sha256:" + ("c" * 64),
            test_count=3,
            status="FAIL",
        )
        result = tenant_persistence_readiness(evidence)
        self.assertIn("EVIDENCE_TENANT_E2E_NOT_PASS", result["blockers"])
        self.assertEqual(result["state"], "BLOCKED")

    def test_security_invariants_are_visible_in_snapshot(self):
        result = tenant_persistence_readiness(_pass_evidence())
        self.assertFalse(result["tenant_policy"]["cross_tenant_access"])
        self.assertTrue(result["tenant_policy"]["credential_bound_namespace"])
        self.assertTrue(result["store_policy"]["explicit_write_approval_required"])
        self.assertFalse(result["store_policy"]["automatic_overwrite"])
        self.assertFalse(result["external_action_executed"])


if __name__ == "__main__":
    unittest.main()
