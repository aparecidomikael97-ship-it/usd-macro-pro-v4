import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_step1_apply_plan import (
    EXPECTED_HTTP_STATUS,
    HTTP_METHOD,
    REALM,
    RELATIVE_PATH,
    build_step1_apply_plan,
    step1_apply_plan_policy,
    verify_step1_apply_plan,
    verify_step1_apply_plan_source_binding,
)
from atlasquant_aion_business_team_access_step1_execution_envelope import (
    SCHEMA as ENVELOPE_SCHEMA,
)


def _envelope():
    return {
        "schema": ENVELOPE_SCHEMA,
        "state": "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY",
        "execution_envelope_digest": "a" * 64,
        "plan_digest": "b" * 64,
        "operator_session_id": "c" * 32,
        "baseline_evidence_digest": "d" * 64,
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "target_username": "sandbox.operador.demo",
        "tenant_ids": ["tenant-a", "tenant-b"],
        "factor_type": "PASSKEY",
        "manual_apply_eligible": True,
        "provider_command_generated": False,
        "physical_execution_performed": False,
        "ledger_append_authorized": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


class TeamAccessStep1ApplyPlanTests(unittest.TestCase):
    def test_policy_is_non_executable(self):
        policy = step1_apply_plan_policy()
        self.assertEqual(policy["realm"], REALM)
        self.assertEqual(policy["method"], HTTP_METHOD)
        self.assertEqual(policy["relative_path"], RELATIVE_PATH)
        self.assertEqual(
            policy["expected_http_status"], EXPECTED_HTTP_STATUS
        )
        self.assertFalse(policy["provider_command_generated"])
        self.assertFalse(policy["authorization_header_included"])
        self.assertFalse(policy["access_token_included"])
        self.assertFalse(policy["secret_material_included"])
        self.assertFalse(policy["physical_execution_performed"])
        self.assertFalse(policy["executor_enabled"])
        self.assertFalse(policy["production_authorized"])
        self.assertFalse(policy["executes_action"])

    @patch(
        "atlasquant_aion_business_team_access_step1_apply_plan."
        "verify_step1_execution_envelope",
        return_value={"binding_match": True},
    )
    def test_valid_envelope_builds_structured_provider_plan_only(
        self, _verify
    ):
        result = build_step1_apply_plan(_envelope())
        self.assertEqual(
            result["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_REVIEW",
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertTrue(result["apply_plan_digest"])

        operation = result["provider_operation"]
        self.assertEqual(operation["provider"], "KEYCLOAK")
        self.assertEqual(operation["realm"], "atlasquant-sandbox")
        self.assertEqual(operation["method"], "POST")
        self.assertEqual(
            operation["relative_path"],
            "/admin/realms/atlasquant-sandbox/users",
        )
        self.assertEqual(operation["expected_http_status"], 201)
        self.assertEqual(
            operation["body"]["username"], "sandbox.operador.demo"
        )
        self.assertTrue(operation["body"]["enabled"])
        self.assertNotIn("credentials", operation["body"])

        self.assertFalse(result["provider_command_generated"])
        self.assertEqual(result["powershell_command"], "")
        self.assertEqual(result["curl_command"], "")
        self.assertFalse(result["authorization_header_included"])
        self.assertFalse(result["access_token_included"])
        self.assertFalse(result["secret_material_included"])
        self.assertFalse(result["physical_execution_performed"])
        self.assertFalse(result["step_execution_receipt_present"])
        self.assertFalse(result["ledger_append_authorized"])
        self.assertFalse(result["automatic_execution_authorized"])
        self.assertFalse(result["executor_enabled"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

        binding = verify_step1_apply_plan(result)
        self.assertTrue(binding["binding_match"])
        self.assertEqual(
            binding["state"], "STEP1_PROVIDER_APPLY_PLAN_BINDING_MATCH"
        )

    @patch(
        "atlasquant_aion_business_team_access_step1_apply_plan."
        "verify_step1_execution_envelope",
        return_value={"binding_match": True},
    )
    def test_apply_plan_source_binding_matches_exact_envelope(
        self, _verify
    ):
        envelope = _envelope()
        result = build_step1_apply_plan(envelope)
        binding = verify_step1_apply_plan_source_binding(
            envelope, result
        )
        self.assertTrue(binding["binding_match"])
        self.assertEqual(
            binding["state"],
            "STEP1_PROVIDER_APPLY_PLAN_SOURCE_BINDING_MATCH",
        )

        changed = _envelope()
        changed["target_username"] = "sandbox.outro.demo"
        binding = verify_step1_apply_plan_source_binding(
            changed, result
        )
        self.assertFalse(binding["binding_match"])

    @patch(
        "atlasquant_aion_business_team_access_step1_apply_plan."
        "verify_step1_execution_envelope",
        return_value={"binding_match": False},
    )
    def test_bad_envelope_binding_blocks_plan(self, _verify):
        result = build_step1_apply_plan(_envelope())
        self.assertEqual(
            result["state"], "TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_BLOCKED"
        )
        self.assertIn("envelope_binding_match", result["blockers"])
        self.assertEqual(result["apply_plan_digest"], "")
        self.assertEqual(result["provider_operation"], {})

    @patch(
        "atlasquant_aion_business_team_access_step1_apply_plan."
        "verify_step1_execution_envelope",
        return_value={"binding_match": True},
    )
    def test_tampered_endpoint_breaks_integrity(self, _verify):
        result = build_step1_apply_plan(_envelope())
        result["provider_operation"]["relative_path"] = (
            "/admin/realms/master/users"
        )
        binding = verify_step1_apply_plan(result)
        self.assertFalse(binding["binding_match"])
        self.assertIn("provider_exact", binding["blockers"])

    @patch(
        "atlasquant_aion_business_team_access_step1_apply_plan."
        "verify_step1_execution_envelope",
        return_value={"binding_match": True},
    )
    def test_tampered_body_or_digest_breaks_integrity(self, _verify):
        result = build_step1_apply_plan(_envelope())
        result["provider_operation"]["body"]["enabled"] = False
        binding = verify_step1_apply_plan(result)
        self.assertFalse(binding["binding_match"])
        self.assertIn("provider_exact", binding["blockers"])

        result = build_step1_apply_plan(_envelope())
        result["apply_plan_digest"] = "f" * 64
        binding = verify_step1_apply_plan(result)
        self.assertFalse(binding["binding_match"])
        self.assertIn("apply_plan_digest_integrity", binding["blockers"])

    @patch(
        "atlasquant_aion_business_team_access_step1_apply_plan."
        "verify_step1_execution_envelope",
        return_value={"binding_match": True},
    )
    def test_plan_contains_no_secret_or_executable_material(self, _verify):
        result = build_step1_apply_plan(_envelope())
        rendered = str(result).lower()
        self.assertNotIn("bearer ", rendered)
        self.assertNotIn('"credentials"', rendered)
        self.assertEqual(result["powershell_command"], "")
        self.assertEqual(result["curl_command"], "")

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_step1_apply_plan.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(
            imported.intersection(
                {"requests", "httpx", "socket", "subprocess", "docker"}
            )
        )


if __name__ == "__main__":
    unittest.main()
