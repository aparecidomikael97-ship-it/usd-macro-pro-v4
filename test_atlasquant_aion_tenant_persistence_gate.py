import unittest

from atlasquant_aion_tenant_persistence_gate import (
    REQUIRED_EVIDENCE,
    tenant_persistence_readiness,
)


def _pass_evidence():
    return {
        name: {
            "status": "PASS",
            "digest": "sha256:" + ("a" * 64),
            "scope": "tenant/workspace",
        }
        for name in REQUIRED_EVIDENCE
    }


class AionTenantPersistenceGateTests(unittest.TestCase):
    def test_current_code_is_fail_closed_until_durable_io_exists(self):
        result = tenant_persistence_readiness()
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["code_ready"])
        self.assertIn("DURABLE_IO_NOT_IMPLEMENTED", result["blockers"])
        self.assertIn("TENANT_PERSISTENCE_DISABLED", result["blockers"])
        self.assertFalse(result["persistence_activation_authorized"])
        self.assertFalse(result["automatic_activation"])

    def test_fake_green_evidence_cannot_bypass_code_policy(self):
        result = tenant_persistence_readiness(_pass_evidence())
        self.assertTrue(result["evidence_ready"])
        self.assertFalse(result["code_ready"])
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("DURABLE_IO_NOT_IMPLEMENTED", result["blockers"])
        self.assertFalse(result["evidence_is_authority"])

    def test_missing_evidence_is_explicit(self):
        result = tenant_persistence_readiness({})
        for name in REQUIRED_EVIDENCE:
            self.assertIn(f"EVIDENCE_{name}_MISSING", result["blockers"])
        self.assertFalse(result["evidence_ready"])

    def test_pass_without_bound_digest_is_not_valid_evidence(self):
        evidence = _pass_evidence()
        evidence["ACL_STORE"] = {
            "status": "PASS",
            "digest": "not-a-bound-digest",
            "scope": "tenant/workspace",
        }
        result = tenant_persistence_readiness(evidence)
        self.assertIn("EVIDENCE_ACL_STORE_DIGEST_INVALID", result["blockers"])
        self.assertFalse(result["evidence"]["ACL_STORE"]["valid"])
        self.assertFalse(result["evidence_ready"])

    def test_failed_evidence_remains_blocking(self):
        evidence = _pass_evidence()
        evidence["TENANT_E2E"] = {
            "status": "FAIL",
            "digest": "sha256:" + ("b" * 64),
            "scope": "tenant/workspace",
        }
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
