import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_physical_sandbox import (
    KEYCLOAK_IMAGE,
    POSTGRES_IMAGE,
    physical_sandbox_policy,
    sandbox_command_plan,
    sandbox_start_preflight,
)


def _config():
    return {
        "sandbox_only": True,
        "production_environment": False,
        "keycloak_image": KEYCLOAK_IMAGE,
        "postgres_image": POSTGRES_IMAGE,
        "keycloak_host": "127.0.0.1",
        "registry_host": "127.0.0.1",
        "keycloak_port": 18080,
        "registry_port": 15432,
        "admin_username": "atlasquant-sandbox-admin",
        "admin_password": "a-unique-sandbox-admin-password-001",
        "keycloak_db_username": "keycloak_sandbox",
        "keycloak_db_password": "a-unique-keycloak-db-password-002",
        "registry_db_username": "atlasquant_registry_sandbox",
        "registry_db_password": "a-unique-registry-db-password-003",
        "env_file_gitignored": True,
        "compose_config_validated": True,
        "docker_engine_observed": True,
        "automatic_start_requested": False,
    }


class TeamAccessPhysicalSandboxTests(unittest.TestCase):
    def test_policy_is_local_non_production_and_non_executing(self):
        policy = physical_sandbox_policy()
        self.assertEqual(
            policy["state"], "TEAM_ACCESS_PHYSICAL_SANDBOX_POLICY_DEFINED"
        )
        self.assertEqual(policy["keycloak_image"], "quay.io/keycloak/keycloak:26.7.5")
        self.assertEqual(policy["postgres_image"], "postgres:18.6")
        self.assertTrue(policy["sandbox_only"])
        self.assertFalse(policy["production_use_allowed"])
        self.assertFalse(policy["automatic_start_allowed"])
        self.assertFalse(policy["executes_action"])

    def test_complete_runtime_only_config_reaches_admin_start_review(self):
        result = sandbox_start_preflight(_config())
        self.assertEqual(
            result["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_PHYSICAL_SANDBOX_START_REVIEW",
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertTrue(result["evidence_digest"])
        self.assertFalse(result["secret_values_returned"])
        self.assertFalse(result["docker_started"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

    def test_placeholders_or_non_localhost_fail_closed(self):
        row = _config()
        row["admin_password"] = "CHANGE_ME_LONG_RANDOM_ADMIN_PASSWORD"
        row["keycloak_host"] = "0.0.0.0"
        result = sandbox_start_preflight(row)
        self.assertEqual(
            result["state"], "TEAM_ACCESS_PHYSICAL_SANDBOX_START_BLOCKED"
        )
        self.assertIn("secret_placeholders_absent", result["blockers"])
        self.assertIn("keycloak_localhost_only", result["blockers"])
        self.assertEqual(result["evidence_digest"], "")

    def test_production_or_automatic_start_fails_closed(self):
        row = _config()
        row["sandbox_only"] = False
        row["production_environment"] = True
        row["automatic_start_requested"] = True
        result = sandbox_start_preflight(row)
        self.assertEqual(
            result["state"], "TEAM_ACCESS_PHYSICAL_SANDBOX_START_BLOCKED"
        )
        self.assertIn("sandbox_only_true", result["blockers"])
        self.assertIn("production_environment_false", result["blockers"])
        self.assertIn("automatic_start_requested", result["blockers"])

    def test_command_plan_is_review_only_and_rejects_prod_env(self):
        plan = sandbox_command_plan(env_file="sandbox.env.local")
        self.assertEqual(
            plan["state"], "TEAM_ACCESS_PHYSICAL_SANDBOX_COMMAND_PLAN_READY"
        )
        self.assertIn("docker compose", plan["commands"]["start"])
        self.assertTrue(plan["start_requires_explicit_admin_apply"])
        self.assertFalse(plan["production_command_generated"])
        self.assertFalse(plan["executes_action"])

        blocked = sandbox_command_plan(env_file=".env.production")
        self.assertEqual(
            blocked["state"], "TEAM_ACCESS_PHYSICAL_SANDBOX_COMMAND_PLAN_BLOCKED"
        )
        self.assertEqual(blocked["commands"]["start"], "")

    def test_compose_is_localhost_pinned_and_contains_no_secret_values(self):
        compose = Path("deploy/sandbox/team-access/compose.yml").read_text(
            encoding="utf-8"
        )
        example = Path(
            "deploy/sandbox/team-access/sandbox.env.example"
        ).read_text(encoding="utf-8")
        self.assertIn("127.0.0.1:", compose)
        self.assertNotIn("0.0.0.0:", compose)
        self.assertIn("quay.io/keycloak/keycloak:26.7.5", example)
        self.assertIn("postgres:18.6", example)
        self.assertNotIn("password=admin", compose.lower())
        self.assertIn("CHANGE_ME_", example)

    def test_local_secret_env_is_explicitly_gitignored(self):
        ignore = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn("**/sandbox.env.local", ignore)
        self.assertNotIn("CHANGE_ME_LONG_RANDOM_ADMIN_PASSWORD\nKC_DB_PASSWORD", ignore)

    def test_module_imports_no_network_process_or_docker_executor(self):
        source = Path(
            "atlasquant_aion_business_team_access_physical_sandbox.py"
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
