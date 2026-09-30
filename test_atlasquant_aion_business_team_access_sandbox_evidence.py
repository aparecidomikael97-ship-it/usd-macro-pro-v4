import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_sandbox_evidence import (
    SCHEMA,
    lifecycle_evidence_template,
    sandbox_evidence_policy,
    validate_baseline_evidence,
)


def _evidence():
    return {
        "schema": SCHEMA,
        "version": "1",
        "environment": "SANDBOX",
        "production_environment": False,
        "captured_at": "2026-09-30T20:00:00+00:00",
        "collector_executes_mutation": False,
        "external_side_effects_executed": False,
        "secrets_included": False,
        "keycloak_image": "quay.io/keycloak/keycloak:26.7.5",
        "postgres_image": "postgres:18.6",
        "running_services": ["registry-db", "keycloak", "keycloak-db"],
        "registry_tables": ["team_memberships", "registry_revisions"],
        "oidc": {
            "issuer": "http://127.0.0.1:18080/realms/atlasquant-sandbox",
        },
        "artifacts": {
            "compose_sha256": "a" * 64,
            "realm_sha256": "b" * 64,
            "registry_schema_sha256": "c" * 64,
        },
    }


class TeamAccessSandboxEvidenceTests(unittest.TestCase):
    def test_policy_is_read_only_and_local(self):
        policy = sandbox_evidence_policy()
        self.assertEqual(
            policy["state"], "TEAM_ACCESS_SANDBOX_EVIDENCE_POLICY_DEFINED"
        )
        self.assertTrue(policy["local_only"])
        self.assertFalse(policy["secrets_allowed"])
        self.assertFalse(policy["production_evidence_allowed"])
        self.assertFalse(policy["executes_action"])

    def test_valid_baseline_reaches_lifecycle_review(self):
        result = validate_baseline_evidence(_evidence())
        self.assertEqual(
            result["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW",
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertTrue(result["evidence_digest"])
        self.assertFalse(result["lifecycle_mutation_authorized"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

    def test_non_local_issuer_or_missing_service_fails_closed(self):
        row = _evidence()
        row["oidc"]["issuer"] = "https://id.example.com/realms/atlasquant-sandbox"
        row["running_services"] = ["keycloak", "keycloak-db"]
        result = validate_baseline_evidence(row)
        self.assertEqual(
            result["state"], "TEAM_ACCESS_SANDBOX_BASELINE_EVIDENCE_BLOCKED"
        )
        self.assertIn("oidc_issuer_local", result["blockers"])
        self.assertIn("services_complete", result["blockers"])
        self.assertEqual(result["evidence_digest"], "")

    def test_sensitive_keys_fail_closed_even_when_declared_absent(self):
        row = _evidence()
        row["admin_password"] = "should-never-be-here"
        result = validate_baseline_evidence(row)
        self.assertEqual(
            result["state"], "TEAM_ACCESS_SANDBOX_BASELINE_EVIDENCE_BLOCKED"
        )
        self.assertIn("sensitive_keys_absent", result["blockers"])

    def test_lifecycle_template_requires_valid_baseline(self):
        baseline = validate_baseline_evidence(_evidence())
        template = lifecycle_evidence_template(baseline)
        self.assertEqual(
            template["state"],
            "TEAM_ACCESS_SANDBOX_LIFECYCLE_EVIDENCE_TEMPLATE_READY",
        )
        self.assertEqual(len(template["required_manual_evidence"]), 10)
        self.assertFalse(template["automatic_account_creation"])
        self.assertFalse(template["automatic_session_revocation"])
        self.assertFalse(template["executes_action"])

        blocked = lifecycle_evidence_template({})
        self.assertEqual(
            blocked["state"],
            "TEAM_ACCESS_SANDBOX_LIFECYCLE_EVIDENCE_TEMPLATE_BLOCKED",
        )

    def test_module_has_no_network_process_or_docker_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_sandbox_evidence.py"
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
