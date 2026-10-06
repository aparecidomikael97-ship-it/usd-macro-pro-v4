import unittest

from atlasquant_aion_b2b_demo_sandbox import (
    ADMISSION_SCHEMA,
    POLICY_SCHEMA,
    SCHEMA,
    evaluate_demo_sandbox,
)


class DemoSandboxGateTests(unittest.TestCase):
    def setUp(self):
        self.scope = {
            "owner_id": "owner-a",
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        }
        self.admission = {
            "schema": ADMISSION_SCHEMA,
            "state": "REVIEWABLE",
            "decision": "TENANT_ADMISSION_REVIEW_CANDIDATE",
            "customer_id": "customer-a",
            "service_tenant_id": "tenant-demo-a",
            "package": "PROFISSIONAL",
            "review_reasons": [],
            "blockers": [],
            "evidence_digest": "sha256:" + "a" * 64,
            "owner_admission_approval_required": True,
            "tenant_creation_authorized": False,
            "quota_change_authorized": False,
            "admission_token_issued": False,
            "automatic_tenant_creation": False,
            "automatic_quota_change": False,
            "automatic_package_change": False,
            "automatic_pricing_change": False,
            "automatic_contract_change": False,
            "automatic_billing": False,
            "automatic_provisioning": False,
            "automatic_customer_contact": False,
            "automatic_deploy": False,
            "crm_write": False,
            "provider_called": False,
            "production_mutation": False,
            "executes_action": False,
        }
        self.policy = {
            **self.scope,
            "schema": POLICY_SCHEMA,
            "state": "VERIFIED",
            "max_duration_hours": 72,
            "max_synthetic_records": 5000,
            "max_concurrent_sessions": 5,
            "synthetic_data_only": True,
            "production_credentials_forbidden": True,
            "live_integrations_forbidden": True,
            "outbound_channels_forbidden": True,
            "evidence_refs": [
                "policy:demo-isolation",
                "policy:synthetic-data",
                "policy:no-egress",
            ],
        }
        self.request = {
            **self.scope,
            "sandbox_id": "sandbox-demo-a",
            "customer_id": "customer-a",
            "service_tenant_id": "tenant-demo-a",
            "package": "PROFISSIONAL",
            "dataset_class": "SYNTHETIC",
            "contains_real_customer_data": False,
            "contains_production_secrets": False,
            "uses_live_integrations": False,
            "outbound_channels_enabled": False,
            "external_provider_required": False,
            "duration_hours": 24,
            "synthetic_records": 1000,
            "concurrent_sessions": 2,
            "demo_script_ref": "demo-script:v1",
            "evidence_refs": [
                "demo:synthetic-fixture",
                "demo:script-reviewed",
                "demo:isolation-plan",
            ],
        }

    def evaluate(self, **overrides):
        request = dict(self.request)
        request.update(overrides)
        return evaluate_demo_sandbox(
            trusted_scope=self.scope,
            admission_result=self.admission,
            demo_request=request,
            policy=self.policy,
        )

    def test_safe_candidate_is_reviewable_only(self):
        result = self.evaluate()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "REVIEWABLE")
        self.assertEqual(result["decision"], "SANDBOX_REVIEW_CANDIDATE")
        self.assertEqual(result["blockers"], [])
        self.assertTrue(result["owner_sandbox_approval_required"])
        for key in (
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
        ):
            self.assertIs(result[key], False, key)

    def test_real_customer_data_is_blocked(self):
        result = self.evaluate(contains_real_customer_data=True)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("REAL_CUSTOMER_DATA_FORBIDDEN", result["blockers"])

    def test_live_integration_provider_or_secret_is_blocked(self):
        result = self.evaluate(
            contains_production_secrets=True,
            uses_live_integrations=True,
            outbound_channels_enabled=True,
            external_provider_required=True,
        )
        self.assertEqual(result["state"], "BLOCKED")
        for expected in (
            "PRODUCTION_SECRETS_FORBIDDEN",
            "LIVE_INTEGRATIONS_FORBIDDEN",
            "OUTBOUND_CHANNELS_FORBIDDEN",
            "EXTERNAL_PROVIDER_FORBIDDEN",
        ):
            self.assertIn(expected, result["blockers"])

    def test_policy_limits_are_fail_closed(self):
        result = self.evaluate(
            duration_hours=73,
            synthetic_records=5001,
            concurrent_sessions=6,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("SANDBOX_DURATION_EXCEEDS_POLICY", result["blockers"])
        self.assertIn("SANDBOX_RECORD_COUNT_EXCEEDS_POLICY", result["blockers"])
        self.assertIn("SANDBOX_SESSION_COUNT_EXCEEDS_POLICY", result["blockers"])

    def test_admission_must_be_clean_and_non_authoritative(self):
        unsafe = dict(self.admission)
        unsafe["tenant_creation_authorized"] = True
        result = evaluate_demo_sandbox(
            trusted_scope=self.scope,
            admission_result=unsafe,
            demo_request=self.request,
            policy=self.policy,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "ADMISSION_UNSAFE_FIELD:tenant_creation_authorized",
            result["blockers"],
        )

    def test_scope_mismatch_is_blocked(self):
        result = self.evaluate(workspace_id="wrong-workspace")
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("SANDBOX_REQUEST_SCOPE_MISMATCH", result["blockers"])

    def test_evidence_digest_is_deterministic(self):
        first = self.evaluate()
        second = self.evaluate()
        self.assertEqual(first["evidence_digest"], second["evidence_digest"])
        self.assertTrue(first["evidence_digest"].startswith("sha256:"))

    def test_missing_demo_script_or_evidence_is_blocked(self):
        result = self.evaluate(demo_script_ref="", evidence_refs=[])
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("DEMO_SCRIPT_REF_REQUIRED", result["blockers"])
        self.assertIn("SANDBOX_REQUEST_EVIDENCE_INSUFFICIENT", result["blockers"])


if __name__ == "__main__":
    unittest.main()
