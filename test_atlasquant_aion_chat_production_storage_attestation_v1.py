from __future__ import annotations

import unittest

import atlasquant_aion_chat_production_storage_attestation_v1 as contract


def ready_inputs():
    return {
        "owner_context": {
            "is_human_owner": True,
            "owner_id": "HUMAN_OWNER",
            "session_bound": True,
        },
        "storage_evidence": {
            "production": True,
            "non_ephemeral": True,
            "durable": True,
            "scope_bound": True,
            "default_deny": True,
            "encryption_at_rest_attested": True,
            "encryption_in_transit_attested": True,
            "backup_policy_attested": True,
            "restore_test_attested": True,
            "schema_migration_plan_attested": True,
            "health_check_attested": True,
            "fail_closed_on_unavailable": True,
            "retention_policy_attested": True,
            "auditability_attested": True,
            "ephemeral_runtime_filesystem": False,
            "staging_only": False,
            "production_ready": True,
        },
    }


class ProductionStorageAttestationV1Tests(unittest.TestCase):
    def assert_zero_execution(self, out):
        for key in contract.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_complete_evidence_unlocks_review_only(self):
        out = contract.evaluate_production_storage_attestation(**ready_inputs())
        self.assertEqual(out["state"], contract.READY)
        self.assertTrue(out["attestation_design_only"])
        self.assertTrue(out["vendor_neutral"])
        self.assertEqual(
            out["next_allowed_step"],
            "SUPPLY_ATTESTED_STORAGE_TO_PRODUCTION_CHAT_ACTIVATION",
        )
        self.assert_zero_execution(out)

    def test_owner_binding_is_required(self):
        data = ready_inputs()
        data["owner_context"]["is_human_owner"] = False
        data["owner_context"]["session_bound"] = False
        out = contract.evaluate_production_storage_attestation(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("HUMAN_OWNER_SESSION_REQUIRED", out["blockers"])
        self.assertIn("HUMAN_OWNER_SESSION_BINDING_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_ephemeral_runtime_filesystem_is_rejected(self):
        data = ready_inputs()
        data["storage_evidence"]["ephemeral_runtime_filesystem"] = True
        data["storage_evidence"]["non_ephemeral"] = False
        out = contract.evaluate_production_storage_attestation(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EPHEMERAL_RUNTIME_FILESYSTEM_FORBIDDEN", out["blockers"])
        self.assertIn("NON_EPHEMERAL_STORAGE_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_staging_only_backend_is_rejected(self):
        data = ready_inputs()
        data["storage_evidence"]["staging_only"] = True
        data["storage_evidence"]["production_ready"] = False
        out = contract.evaluate_production_storage_attestation(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("STAGING_ONLY_STORAGE_FORBIDDEN", out["blockers"])
        self.assertIn("PRODUCTION_READY_ATTESTATION_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_backup_without_restore_proof_is_not_enough(self):
        data = ready_inputs()
        data["storage_evidence"]["restore_test_attested"] = False
        out = contract.evaluate_production_storage_attestation(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("RESTORE_TEST_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_encryption_requires_at_rest_and_in_transit(self):
        data = ready_inputs()
        data["storage_evidence"]["encryption_at_rest_attested"] = False
        data["storage_evidence"]["encryption_in_transit_attested"] = False
        out = contract.evaluate_production_storage_attestation(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ENCRYPTION_AT_REST_REQUIRED", out["blockers"])
        self.assertIn("ENCRYPTION_IN_TRANSIT_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_scope_and_default_deny_are_required(self):
        data = ready_inputs()
        data["storage_evidence"]["scope_bound"] = False
        data["storage_evidence"]["default_deny"] = False
        out = contract.evaluate_production_storage_attestation(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SCOPE_BINDING_REQUIRED", out["blockers"])
        self.assertIn("DEFAULT_DENY_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_unhealthy_or_non_fail_closed_store_is_rejected(self):
        data = ready_inputs()
        data["storage_evidence"]["health_check_attested"] = False
        data["storage_evidence"]["fail_closed_on_unavailable"] = False
        out = contract.evaluate_production_storage_attestation(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("HEALTH_CHECK_REQUIRED", out["blockers"])
        self.assertIn("FAIL_CLOSED_UNAVAILABLE_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)


if __name__ == "__main__":
    unittest.main()
