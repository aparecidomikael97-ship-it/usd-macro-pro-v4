import unittest

from atlasquant_aion_b2b_demo_sandbox_read_model import (
    SCHEMA,
    build_demo_sandbox_read_model,
)


def sandbox_result(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_DEMO_SANDBOX_V1",
        "state": "REVIEWABLE",
        "decision": "SANDBOX_REVIEW_CANDIDATE",
        "sandbox_id": "sandbox-demo-a",
        "customer_id": "customer-secret-a",
        "service_tenant_id": "tenant-demo-a",
        "package": "PROFISSIONAL",
        "dataset_class": "SYNTHETIC",
        "duration_hours": 24,
        "synthetic_records": 1000,
        "concurrent_sessions": 2,
        "blockers": [],
        "evidence_digest": "sha256:" + "1" * 64,
        "owner_sandbox_approval_required": True,
        "sandbox_creation_authorized": False,
        "tenant_creation_authorized": False,
        "quota_change_authorized": False,
        "credential_use_authorized": False,
        "live_integration_authorized": False,
        "customer_data_use_authorized": False,
        "outbound_contact_authorized": False,
        "billing_authorized": False,
        "automatic_sandbox_creation": False,
        "automatic_tenant_creation": False,
        "automatic_quota_change": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class DemoSandboxReadModelTests(unittest.TestCase):
    def test_reviewable_sandbox_projects_safe_admin_summary(self):
        out = build_demo_sandbox_read_model(sandbox_result())
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["sandbox_state"], "REVIEWABLE")
        self.assertEqual(
            out["sandbox_decision"],
            "SANDBOX_REVIEW_CANDIDATE",
        )
        self.assertEqual(out["sandbox_id"], "sandbox-demo-a")
        self.assertEqual(out["service_tenant_id"], "tenant-demo-a")
        self.assertEqual(out["package"], "PROFISSIONAL")
        self.assertEqual(out["dataset_class"], "SYNTHETIC")
        self.assertEqual(out["duration_hours"], 24)
        self.assertEqual(out["synthetic_records"], 1000)
        self.assertEqual(out["concurrent_sessions"], 2)
        self.assertTrue(out["read_only"])
        self.assertTrue(out["synthetic_only"])

    def test_customer_identity_is_not_projected(self):
        out = build_demo_sandbox_read_model(sandbox_result())
        self.assertNotIn("customer_id", out)
        self.assertNotIn("customer-secret-a", str(out))
        self.assertFalse(out["customer_identity_exposed"])

    def test_evidence_and_provider_internals_are_hidden(self):
        out = build_demo_sandbox_read_model(sandbox_result())
        self.assertNotIn("evidence_refs", out)
        self.assertFalse(out["evidence_internals_exposed"])
        self.assertFalse(out["credential_details_exposed"])
        self.assertFalse(out["provider_details_exposed"])

    def test_blocked_source_is_not_presentable(self):
        out = build_demo_sandbox_read_model(
            sandbox_result(
                state="BLOCKED",
                decision="BLOCKED",
                blockers=["REAL_CUSTOMER_DATA_FORBIDDEN"],
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("DEMO_SANDBOX_NOT_REVIEWABLE", out["blockers"])

    def test_non_synthetic_source_blocks(self):
        out = build_demo_sandbox_read_model(
            sandbox_result(dataset_class="REAL")
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("DEMO_SANDBOX_NOT_SYNTHETIC", out["blockers"])

    def test_any_authority_flip_blocks_projection(self):
        unsafe_keys = (
            "sandbox_creation_authorized",
            "tenant_creation_authorized",
            "quota_change_authorized",
            "credential_use_authorized",
            "live_integration_authorized",
            "customer_data_use_authorized",
            "outbound_contact_authorized",
            "billing_authorized",
            "automatic_sandbox_creation",
            "automatic_tenant_creation",
            "automatic_quota_change",
            "automatic_billing",
            "automatic_provisioning",
            "automatic_customer_contact",
            "automatic_deploy",
            "crm_write",
            "provider_called",
            "production_mutation",
            "executes_action",
        )
        for key in unsafe_keys:
            with self.subTest(key=key):
                out = build_demo_sandbox_read_model(
                    sandbox_result(**{key: True})
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(
                    "DEMO_SANDBOX_UNSAFE_FIELD:" + key,
                    out["blockers"],
                )

    def test_read_model_exposes_no_operational_controls(self):
        out = build_demo_sandbox_read_model(sandbox_result())
        for key in (
            "sandbox_creation_control_exposed",
            "tenant_creation_control_exposed",
            "quota_control_exposed",
            "provisioning_control_exposed",
            "billing_control_exposed",
            "customer_contact_control_exposed",
            "grants_authority",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
