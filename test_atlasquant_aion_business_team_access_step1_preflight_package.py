import ast
import hashlib
import json
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_lifecycle_authorization_package import (
    validate_materialized_authorization,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_authorization import (
    SCHEMA as AUTH_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_materialization import (
    SCHEMA as MATERIALIZATION_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
    REQUIRED_ACKNOWLEDGEMENTS,
    REQUIRED_DECISION_TOKEN,
    SCHEMA as PLAN_SCHEMA,
)
from atlasquant_aion_business_team_access_step1_preflight_package import (
    OBSERVATION_SCHEMA,
    build_step1_preflight_package,
    readiness_observation_template,
    step1_preflight_package_policy,
)


def _digest(value):
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _plan():
    steps = [
        {
            "order": i,
            "id": step_id,
            "mutation": i in {1, 2, 4, 6, 7, 8},
            "requires_manual_apply": True,
            "evidence_required": ["proof"],
        }
        for i, step_id in enumerate(LIFECYCLE_STEP_IDS, start=1)
    ]
    payload = {
        "baseline_evidence_digest": "a" * 64,
        "baseline_acceptance_record_digest": "b" * 64,
        "test_username": "sandbox.operador.demo",
        "tenant_ids": ["tenant-a"],
        "factor_type": "PASSKEY",
        "requested_by": "admin.demo",
        "steps": steps,
    }
    return {
        "schema": PLAN_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION",
        **payload,
        "plan_digest": _digest(payload),
        "required_decision_token": REQUIRED_DECISION_TOKEN,
        "required_acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "decision_recorded": False,
        "account_creation_authorized": False,
        "mfa_enrollment_authorized": False,
        "registry_write_authorized": False,
        "session_revocation_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def _materialization():
    plan = _plan()
    payload = {
        "operator_session_id": "c" * 32,
        "baseline_evidence_digest": "a" * 64,
        "baseline_acceptance_record_digest": "b" * 64,
        "plan_digest": plan["plan_digest"],
        "test_username": plan["test_username"],
        "tenant_ids": plan["tenant_ids"],
        "factor_type": plan["factor_type"],
        "requested_by": plan["requested_by"],
    }
    return {
        "schema": MATERIALIZATION_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW",
        "operator_session_id": "c" * 32,
        "baseline_evidence_digest": "a" * 64,
        "baseline_acceptance_record_digest": "b" * 64,
        "plan_digest": plan["plan_digest"],
        "materialization_digest": _digest(payload),
        "plan": plan,
        "lifecycle_authorization_recorded": False,
        "lifecycle_execution_authorized": False,
        "automatic_step_execution": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def _authorization_package():
    materialization = _materialization()
    plan = materialization["plan"]
    record = {
        "schema": AUTH_SCHEMA,
        "decision": REQUIRED_DECISION_TOKEN,
        "materialization_digest": materialization["materialization_digest"],
        "plan_digest": plan["plan_digest"],
        "baseline_evidence_digest": "a" * 64,
        "approved_by": "admin.demo",
        "approved_at": "2026-09-30T21:40:00+00:00",
        "sandbox_only": True,
        "production_targeted": False,
        "secret_material_included": False,
        "executor_enabled": False,
        "acknowledgements": {
            name: True for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    }
    return validate_materialized_authorization(materialization, record)


def _observation():
    return {
        "schema": OBSERVATION_SCHEMA,
        "version": "1",
        "operator_session_id": "c" * 32,
        "baseline_evidence_digest_observed": "a" * 64,
        "observed_at": "2026-09-30T21:45:00+00:00",
        "observed_by": "admin.demo",
        "sandbox_health_verified": True,
        "oidc_verified": True,
        "registry_schema_verified": True,
        "secrets_local": True,
        "production_targets_absent": True,
        "cleanup_path_ready": True,
        "secret_material_included": False,
        "production_targeted": False,
        "external_mutations_executed": False,
    }


class TeamAccessStep1PreflightPackageTests(unittest.TestCase):
    def test_policy_never_authorizes_or_executes_step(self):
        policy = step1_preflight_package_policy()
        self.assertTrue(policy["zero_receipt_ledger_required"])
        self.assertEqual(policy["target_step_order"], 1)
        self.assertEqual(policy["target_step_id"], LIFECYCLE_STEP_IDS[0])
        self.assertFalse(policy["generic_language_is_step_authorization"])
        self.assertFalse(policy["step_execution_authorized"])
        self.assertFalse(policy["automatic_ledger_append"])
        self.assertFalse(policy["executor_enabled"])
        self.assertFalse(policy["production_authorized"])
        self.assertFalse(policy["executes_action"])

    def test_observation_template_is_fail_closed(self):
        row = readiness_observation_template()
        self.assertEqual(row["schema"], OBSERVATION_SCHEMA)
        self.assertFalse(row["sandbox_health_verified"])
        self.assertFalse(row["oidc_verified"])
        self.assertFalse(row["registry_schema_verified"])
        self.assertFalse(row["cleanup_path_ready"])
        self.assertFalse(row["external_mutations_executed"])

    def test_valid_inputs_build_zero_ledger_and_step1_decision_packet(self):
        result = build_step1_preflight_package(
            _materialization(),
            _authorization_package(),
            _observation(),
            evaluated_at="2026-09-30T21:50:00+00:00",
        )
        self.assertEqual(
            result["state"],
            "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_DECISION_PACKET",
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertEqual(result["observation_age_seconds"], 300)
        self.assertEqual(
            result["ledger"]["state"],
            "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP",
        )
        self.assertEqual(result["ledger"]["completed_count"], 0)
        self.assertEqual(result["ledger"]["entries"], [])
        self.assertEqual(result["ledger"]["next_expected_step_order"], 1)
        self.assertEqual(
            result["preflight"]["state"],
            "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_DECISION",
        )
        self.assertEqual(result["target_step_order"], 1)
        self.assertEqual(result["target_step_id"], LIFECYCLE_STEP_IDS[0])
        self.assertTrue(result["required_step_decision_token"].startswith(
            "AUTHORIZE_SANDBOX_LIFECYCLE_STEP_1_"
        ))
        self.assertTrue(result["step1_packet_digest"])
        self.assertFalse(result["manual_decision_recorded"])
        self.assertFalse(result["step_execution_authorized"])
        self.assertFalse(result["automatic_execution_authorized"])
        self.assertFalse(result["automatic_ledger_append"])
        self.assertFalse(result["executor_enabled"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

    def test_stale_observation_blocks(self):
        result = build_step1_preflight_package(
            _materialization(),
            _authorization_package(),
            _observation(),
            evaluated_at="2026-09-30T22:01:00+00:00",
        )
        self.assertEqual(
            result["state"], "TEAM_ACCESS_STEP1_PREFLIGHT_PACKAGE_BLOCKED"
        )
        self.assertIn("observation_fresh", result["blockers"])
        self.assertEqual(
            result["preflight"]["state"],
            "SANDBOX_LIFECYCLE_STEP_PREFLIGHT_NOT_EVALUATED",
        )
        self.assertEqual(
            result["preflight"]["required_step_decision_token"], ""
        )
        self.assertEqual(result["step1_packet_digest"], "")
        self.assertFalse(result["step_execution_authorized"])

    def test_session_or_baseline_drift_blocks(self):
        observation = _observation()
        observation["operator_session_id"] = "d" * 32
        observation["baseline_evidence_digest_observed"] = "e" * 64
        result = build_step1_preflight_package(
            _materialization(),
            _authorization_package(),
            observation,
            evaluated_at="2026-09-30T21:50:00+00:00",
        )
        self.assertIn("observation_session_matches", result["blockers"])
        self.assertIn("observed_baseline_matches", result["blockers"])
        self.assertFalse(result["step_execution_authorized"])

    def test_health_or_cleanup_failure_blocks(self):
        observation = _observation()
        observation["sandbox_health_verified"] = False
        observation["cleanup_path_ready"] = False
        result = build_step1_preflight_package(
            _materialization(),
            _authorization_package(),
            observation,
            evaluated_at="2026-09-30T21:50:00+00:00",
        )
        self.assertIn("sandbox_health_verified", result["blockers"])
        self.assertIn("cleanup_path_ready", result["blockers"])

    def test_tampered_authorization_package_blocks(self):
        auth = _authorization_package()
        auth["authorization_package_digest"] = "f" * 64
        result = build_step1_preflight_package(
            _materialization(),
            auth,
            _observation(),
            evaluated_at="2026-09-30T21:50:00+00:00",
        )
        self.assertIn("authorization_binding_match", result["blockers"])
        self.assertFalse(result["step_execution_authorized"])

    def test_tampered_materialization_blocks(self):
        materialization = _materialization()
        materialization["materialization_digest"] = "f" * 64
        result = build_step1_preflight_package(
            materialization,
            _authorization_package(),
            _observation(),
            evaluated_at="2026-09-30T21:50:00+00:00",
        )
        self.assertIn(
            "materialization_digest_integrity", result["blockers"]
        )
        self.assertFalse(result["step_execution_authorized"])

    def test_windows_observation_helper_is_read_only_and_external_local(self):
        script = Path(
            "deploy/sandbox/team-access/Get-TeamAccessStep1ReadinessObservation.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("$env:LOCALAPPDATA", script)
        self.assertIn("$LocalPrefix", script)
        self.assertIn("$OutputResolved", script)
        self.assertIn("outside the repository tree", script)
        self.assertIn("Test-TeamAccessSandbox.ps1", script)
        self.assertIn("Test-TeamAccessRegistry.ps1", script)
        self.assertIn("external_mutations_executed = $false", script)
        self.assertNotIn("Start-TeamAccessSandbox.ps1", script)
        self.assertNotIn("docker compose up", script)
        self.assertNotIn("docker compose down", script)
        self.assertNotIn("CREATE USER", script.upper())
        self.assertNotIn("INSERT INTO", script.upper())
        self.assertNotIn("UPDATE ", script.upper())
        self.assertNotIn("DELETE FROM", script.upper())

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_step1_preflight_package.py"
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
