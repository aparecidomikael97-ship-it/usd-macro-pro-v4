import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_sandbox_baseline_acceptance import (
    SCHEMA as ACCEPTANCE_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_materialization import (
    lifecycle_materialization_policy,
    materialize_lifecycle_plan,
)
from atlasquant_aion_business_team_access_sandbox_evidence import (
    SCHEMA as BASELINE_SCHEMA,
)


SESSION = "a" * 32


def _raw_baseline():
    return {
        "schema": BASELINE_SCHEMA,
        "version": "1",
        "operator_session_id": SESSION,
        "environment": "SANDBOX",
        "production_environment": False,
        "captured_at": "2026-09-30T21:20:00+00:00",
        "collector_executes_mutation": False,
        "external_side_effects_executed": False,
        "secrets_included": False,
        "keycloak_image": "quay.io/keycloak/keycloak:26.7.5",
        "postgres_image": "postgres:18.6",
        "running_services": ["keycloak", "keycloak-db", "registry-db"],
        "registry_tables": ["registry_revisions", "team_memberships"],
        "oidc": {
            "issuer": "http://127.0.0.1:18080/realms/atlasquant-sandbox",
        },
        "artifacts": {
            "compose_sha256": "b" * 64,
            "realm_sha256": "c" * 64,
            "registry_schema_sha256": "d" * 64,
        },
    }


def _acceptance(baseline_digest):
    return {
        "schema": ACCEPTANCE_SCHEMA,
        "state": "EXPLICIT_SANDBOX_BASELINE_ACCEPTANCE_VERIFIED",
        "acceptance_record_verified": True,
        "baseline_accepted": True,
        "lifecycle_plan_input_authorized": True,
        "baseline_evidence_digest": baseline_digest,
        "operator_session_id": SESSION,
        "acceptance_record_digest": "e" * 64,
        "lifecycle_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }


class TeamAccessSandboxLifecycleMaterializationTests(unittest.TestCase):
    def test_policy_is_review_only(self):
        policy = lifecycle_materialization_policy()
        self.assertTrue(policy["raw_baseline_revalidation_required"])
        self.assertTrue(policy["explicit_baseline_acceptance_required"])
        self.assertTrue(policy["plan_review_required"])
        self.assertFalse(policy["automatic_lifecycle_authorization"])
        self.assertFalse(policy["automatic_step_execution"])
        self.assertFalse(policy["executes_action"])

    def test_accepted_baseline_materializes_reviewable_plan(self):
        from atlasquant_aion_business_team_access_sandbox_evidence import (
            validate_baseline_evidence,
        )
        baseline_review = validate_baseline_evidence(_raw_baseline())
        acceptance = _acceptance(baseline_review["evidence_digest"])

        result = materialize_lifecycle_plan(
            _raw_baseline(),
            acceptance,
            test_username="sandbox.operador.demo",
            tenant_ids=["tenant-a"],
            factor_type="PASSKEY",
            requested_by="admin.demo",
        )
        self.assertEqual(
            result["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW",
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertEqual(len(result["plan"]["steps"]), 10)
        self.assertTrue(result["materialization_digest"])
        self.assertFalse(result["lifecycle_authorization_recorded"])
        self.assertFalse(result["lifecycle_execution_authorized"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

    def test_missing_acceptance_blocks_materialization(self):
        result = materialize_lifecycle_plan(
            _raw_baseline(),
            {},
            test_username="sandbox.operador.demo",
            tenant_ids=["tenant-a"],
            factor_type="PASSKEY",
            requested_by="admin.demo",
        )
        self.assertEqual(
            result["state"],
            "TEAM_ACCESS_SANDBOX_LIFECYCLE_MATERIALIZATION_BLOCKED",
        )
        self.assertIn("acceptance_schema_valid", result["blockers"])
        self.assertIn("plan_ready", result["blockers"])
        self.assertEqual(result["plan"], {})

    def test_wrong_acceptance_baseline_digest_blocks(self):
        acceptance = _acceptance("f" * 64)
        result = materialize_lifecycle_plan(
            _raw_baseline(),
            acceptance,
            test_username="sandbox.operador.demo",
            tenant_ids=["tenant-a"],
            factor_type="TOTP",
            requested_by="admin.demo",
        )
        self.assertEqual(
            result["state"],
            "TEAM_ACCESS_SANDBOX_LIFECYCLE_MATERIALIZATION_BLOCKED",
        )
        self.assertIn("plan_ready", result["blockers"])

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_sandbox_lifecycle_materialization.py"
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
