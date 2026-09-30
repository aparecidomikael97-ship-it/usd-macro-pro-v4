import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from atlasquant_aion_business_team_access_step1_provider_runner import (
    MAX_EXECUTION_ENVELOPE_AGE_SECONDS,
    build_provider_runner_preflight,
    provider_runner_policy,
    required_physical_apply_token,
)


def _envelope():
    return {
        "prepared_at": "2026-09-30T22:40:00+00:00",
    }


def _plan():
    return {
        "apply_plan_digest": "a" * 64,
        "provider_operation": {
            "realm": "atlasquant-sandbox",
            "relative_path": "/admin/realms/atlasquant-sandbox/users",
        },
        "target_step_order": 1,
        "target_step_id": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
        "target_username": "sandbox.operador.demo",
        "provider_command_generated": False,
        "physical_execution_performed": False,
        "step_execution_receipt_present": False,
        "ledger_append_authorized": False,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


_PATCHES = (
    patch(
        "atlasquant_aion_business_team_access_step1_provider_runner."
        "verify_step1_execution_envelope",
        return_value={"binding_match": True},
    ),
    patch(
        "atlasquant_aion_business_team_access_step1_provider_runner."
        "verify_step1_apply_plan",
        return_value={"binding_match": True},
    ),
    patch(
        "atlasquant_aion_business_team_access_step1_provider_runner."
        "verify_step1_apply_plan_source_binding",
        return_value={"binding_match": True},
    ),
)


class TeamAccessStep1ProviderRunnerTests(unittest.TestCase):
    def setUp(self):
        self.patchers = list(_PATCHES)
        for item in self.patchers:
            item.start()

    def tearDown(self):
        for item in reversed(self.patchers):
            item.stop()

    def test_policy_defaults_to_plan_only(self):
        policy = provider_runner_policy()
        self.assertTrue(policy["plan_only_default"])
        self.assertTrue(policy["apply_switch_required"])
        self.assertTrue(policy["exact_physical_apply_token_required"])
        self.assertTrue(policy["fresh_execution_envelope_required"])
        self.assertEqual(
            policy["max_execution_envelope_age_seconds"],
            MAX_EXECUTION_ENVELOPE_AGE_SECONDS,
        )
        self.assertFalse(
            policy["generic_language_is_physical_authorization"]
        )
        self.assertFalse(policy["automatic_execution_authorized"])
        self.assertFalse(policy["production_authorized"])

    def test_plan_only_returns_exact_non_secret_token(self):
        plan = _plan()
        result = build_provider_runner_preflight(
            _envelope(),
            plan,
            evaluated_at="2026-09-30T22:41:00+00:00",
            base_url="http://127.0.0.1:18080",
            sandbox_only=True,
            production_targeted=False,
            secrets_local=True,
            apply_requested=False,
            authorization_token="",
        )
        self.assertEqual(
            result["state"], "STEP1_PROVIDER_RUNNER_PLAN_ONLY"
        )
        self.assertTrue(all(result["gates"].values()))
        token = result["required_physical_apply_token"]
        self.assertEqual(token, required_physical_apply_token(plan))
        self.assertTrue(
            token.startswith(
                "APPLY_SANDBOX_STEP1_"
                "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT_"
            )
        )
        self.assertFalse(result["physical_apply_authorized"])
        self.assertFalse(result["physical_execution_performed"])
        self.assertFalse(result["receipt_created"])

    def test_apply_requires_exact_token(self):
        plan = _plan()
        expected = required_physical_apply_token(plan)
        result = build_provider_runner_preflight(
            _envelope(),
            plan,
            evaluated_at="2026-09-30T22:41:00+00:00",
            base_url="http://127.0.0.1:18080",
            sandbox_only=True,
            production_targeted=False,
            secrets_local=True,
            apply_requested=True,
            authorization_token=expected,
        )
        self.assertEqual(
            result["state"],
            "READY_FOR_EXPLICIT_MANUAL_STEP1_PROVIDER_APPLY",
        )
        self.assertTrue(result["physical_apply_authorized"])
        self.assertFalse(result["physical_execution_performed"])

        result = build_provider_runner_preflight(
            _envelope(),
            plan,
            evaluated_at="2026-09-30T22:41:00+00:00",
            base_url="http://127.0.0.1:18080",
            sandbox_only=True,
            production_targeted=False,
            secrets_local=True,
            apply_requested=True,
            authorization_token="vamos lá",
        )
        self.assertEqual(
            result["state"], "STEP1_PROVIDER_RUNNER_BLOCKED"
        )
        self.assertIn("authorization_token_exact", result["blockers"])
        self.assertFalse(result["physical_apply_authorized"])

    def test_stale_envelope_blocks(self):
        result = build_provider_runner_preflight(
            _envelope(),
            _plan(),
            evaluated_at="2026-09-30T22:42:01+00:00",
            base_url="http://127.0.0.1:18080",
            sandbox_only=True,
            production_targeted=False,
            secrets_local=True,
            apply_requested=False,
            authorization_token="",
        )
        self.assertIn("execution_envelope_fresh", result["blockers"])
        self.assertEqual(
            result["state"], "STEP1_PROVIDER_RUNNER_BLOCKED"
        )

    def test_non_local_or_production_context_blocks(self):
        result = build_provider_runner_preflight(
            _envelope(),
            _plan(),
            evaluated_at="2026-09-30T22:41:00+00:00",
            base_url="http://192.168.1.8:18080",
            sandbox_only=False,
            production_targeted=True,
            secrets_local=False,
            apply_requested=False,
            authorization_token="",
        )
        self.assertIn("localhost_base_url_valid", result["blockers"])
        self.assertIn("sandbox_only", result["blockers"])
        self.assertIn("production_not_targeted", result["blockers"])
        self.assertIn("secrets_local", result["blockers"])

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_step1_provider_runner.py"
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
