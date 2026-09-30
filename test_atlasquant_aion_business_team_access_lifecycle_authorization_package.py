import ast
import hashlib
import json
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_lifecycle_authorization_package import (
    authorization_package_requirements,
    validate_materialized_authorization,
    verify_materialized_authorization_binding,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_authorization import (
    SCHEMA as AUTH_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_materialization import (
    SCHEMA as MATERIALIZATION_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    REQUIRED_ACKNOWLEDGEMENTS,
    REQUIRED_DECISION_TOKEN,
    SCHEMA as PLAN_SCHEMA,
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
        for i, step_id in enumerate(
            (
                "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
                "ENROLL_STRONG_AUTH",
                "VERIFY_STRONG_AUTH_CHALLENGE",
                "WRITE_REGISTRY_REVISION",
                "VERIFY_REGISTRY_EXACT_READBACK",
                "DISABLE_SANDBOX_ACCOUNT",
                "REVOKE_SANDBOX_SESSIONS",
                "MARK_REGISTRY_MEMBERSHIP_INACTIVE",
                "VERIFY_INACTIVE_REGISTRY_READBACK",
                "ASSEMBLE_E2E_EVIDENCE_PACKET",
            ),
            start=1,
        )
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


def _record(materialization_digest):
    plan = _plan()
    return {
        "schema": AUTH_SCHEMA,
        "decision": REQUIRED_DECISION_TOKEN,
        "materialization_digest": materialization_digest,
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


class TeamAccessLifecycleAuthorizationPackageTests(unittest.TestCase):
    def test_policy_keeps_package_non_executing(self):
        req = authorization_package_requirements()
        self.assertTrue(req["materialization_binding_required"])
        self.assertTrue(req["authorization_record_integrity_required"])
        self.assertFalse(req["generic_language_is_authorization"])
        self.assertFalse(req["authorization_package_verified"])
        self.assertFalse(req["executor_enabled"])
        self.assertFalse(req["production_authorized"])

    def test_valid_materialized_authorization_builds_bound_package(self):
        materialization = _materialization()
        result = validate_materialized_authorization(
            materialization,
            _record(materialization["materialization_digest"]),
        )
        self.assertEqual(
            result["state"],
            "EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED",
        )
        self.assertTrue(result["authorization_record_verified"])
        self.assertTrue(result["materialization_binding_verified"])
        self.assertTrue(result["authorization_package_digest"])
        self.assertFalse(result["automatic_execution_authorized"])
        self.assertFalse(result["executor_enabled"])
        self.assertFalse(result["production_authorized"])

        binding = verify_materialized_authorization_binding(
            materialization["plan"], result
        )
        self.assertTrue(binding["binding_match"])

    def test_materialization_drift_rejects(self):
        materialization = _materialization()
        record = _record("f" * 64)
        result = validate_materialized_authorization(
            materialization, record
        )
        self.assertEqual(
            result["state"],
            "SANDBOX_LIFECYCLE_AUTHORIZATION_PACKAGE_REJECTED",
        )
        self.assertIn("materialization_digest", result["package_blockers"])
        self.assertFalse(result["authorization_record_verified"])

    def test_tampered_package_digest_rejects_binding(self):
        materialization = _materialization()
        result = validate_materialized_authorization(
            materialization,
            _record(materialization["materialization_digest"]),
        )
        result["authorization_package_digest"] = "f" * 64
        binding = verify_materialized_authorization_binding(
            materialization["plan"], result
        )
        self.assertFalse(binding["binding_match"])

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_lifecycle_authorization_package.py"
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
