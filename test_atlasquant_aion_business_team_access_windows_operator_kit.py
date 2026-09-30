import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_windows_operator_kit import (
    READINESS_SCHEMA,
    baseline_operator_handoff,
    validate_windows_operator_readiness,
    windows_operator_policy,
)


def _report():
    return {
        "schema": READINESS_SCHEMA,
        "version": "1",
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION",
        "captured_at": "2026-09-30T21:00:00+00:00",
        "checks": {
            "env_file_exists": True,
            "sandbox_marker": True,
            "placeholders_absent": True,
            "docker_cli": True,
            "docker_compose": True,
            "compose_config_valid": True,
            "production_name_absent": True,
        },
        "secrets_included": False,
        "container_started": False,
        "production_targeted": False,
        "executes_mutation": False,
    }


class TeamAccessWindowsOperatorKitTests(unittest.TestCase):
    def test_policy_defaults_to_plan_only(self):
        policy = windows_operator_policy()
        self.assertTrue(policy["secret_bootstrap_plan_only_default"])
        self.assertTrue(policy["sandbox_start_plan_only_default"])
        self.assertTrue(policy["explicit_apply_required_for_secret_file"])
        self.assertTrue(policy["explicit_apply_start_required"])
        self.assertFalse(policy["secret_values_may_be_printed"])
        self.assertFalse(policy["production_targets_allowed"])
        self.assertFalse(policy["lifecycle_execution_included"])
        self.assertFalse(policy["executes_action"])

    def test_valid_readiness_stops_before_manual_apply(self):
        result = validate_windows_operator_readiness(_report())
        self.assertEqual(
            result["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION",
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertTrue(result["readiness_digest"])
        self.assertFalse(result["sandbox_start_authorized"])
        self.assertFalse(result["baseline_collection_authorized"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

        handoff = baseline_operator_handoff(result)
        self.assertEqual(
            handoff["state"], "WINDOWS_OPERATOR_MANUAL_APPLY_REQUIRED"
        )
        self.assertTrue(handoff["manual_apply_required"])
        self.assertFalse(handoff["automatic_start"])
        self.assertFalse(handoff["automatic_baseline_collection"])

    def test_missing_compose_or_prod_name_blocks(self):
        row = _report()
        row["checks"]["docker_compose"] = False
        row["checks"]["production_name_absent"] = False
        row["state"] = "TEAM_ACCESS_WINDOWS_OPERATOR_READINESS_BLOCKED"
        result = validate_windows_operator_readiness(row)
        self.assertEqual(
            result["state"], "TEAM_ACCESS_WINDOWS_OPERATOR_READINESS_REJECTED"
        )
        self.assertIn("state_ready", result["blockers"])
        self.assertIn("required_checks_complete", result["blockers"])
        self.assertEqual(result["readiness_digest"], "")

    def test_scripts_do_not_print_secret_values_or_auto_start(self):
        prepare = Path(
            "deploy/sandbox/team-access/Prepare-TeamAccessSandboxEnv.ps1"
        ).read_text(encoding="utf-8")
        operator = Path(
            "deploy/sandbox/team-access/Invoke-TeamAccessSandboxOperator.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("if (-not $Apply)", prepare)
        self.assertIn("Secret values are never printed", prepare)
        self.assertNotIn('Write-Host "$adminPassword"', prepare)
        self.assertNotIn('Write-Host "$keycloakDbPassword"', prepare)
        self.assertNotIn('Write-Host "$registryDbPassword"', prepare)

        self.assertIn("if (-not $ApplyStart)", operator)
        self.assertIn("-ApplyStart -CollectBaseline", operator)
        self.assertNotIn("Start-TeamAccessSandbox.ps1 -Apply\n", operator)

    def test_operator_reports_are_gitignored(self):
        ignore = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn("**/.atlasquant_sandbox_operator/", ignore)

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_windows_operator_kit.py"
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
