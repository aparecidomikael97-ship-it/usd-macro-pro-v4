import ast
import hashlib
import json
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_sandbox_e2e import (
    identity_provider_sandbox_binding,
    registry_storage_sandbox_binding,
    revocation_connector_sandbox_binding,
    run_team_access_sandbox_e2e,
    selected_sandbox_stack,
)


RBAC_SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_RBAC_V1"


def _membership():
    return {
        "username": "operador.demo",
        "profile": "OPERATOR",
        "tenant_ids": ["tenant-a"],
        "active": True,
        "strong_auth_required": True,
        "membership_digest": "a" * 64,
    }


def _invitation():
    return {
        "schema": RBAC_SCHEMA,
        "version": "1",
        "state": "TEAM_INVITATION_REVIEW_READY",
        "actor": "admin.demo",
        "membership": _membership(),
        "expires_at": "2026-10-01T18:00:00+00:00",
        "invitation_plan_digest": "b" * 64,
        "requires_individual_account": True,
        "requires_strong_auth": True,
        "shared_admin_login_allowed": False,
        "invitation_sent": False,
        "account_created": False,
        "membership_applied": False,
        "executes_action": False,
    }


def _registry():
    member = _membership()
    return {
        "schema": RBAC_SCHEMA,
        "version": "1",
        "state": "TEAM_REGISTRY_INTEGRITY_VERIFIED",
        "integrity_verified": True,
        "member_count": 1,
        "memberships": [member],
        "executes_action": False,
    }


def _registry_digest():
    member = _membership()
    payload = {
        "team_rbac_schema": RBAC_SCHEMA,
        "member_count": 1,
        "memberships": [{
            "username": "operador.demo",
            "profile": "OPERATOR",
            "tenant_ids": ["tenant-a"],
            "active": True,
            "strong_auth_required": True,
            "membership_digest": member["membership_digest"],
        }],
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _revocation():
    return {
        "schema": RBAC_SCHEMA,
        "version": "1",
        "state": "TEAM_REVOCATION_REVIEW_READY",
        "target_username": "operador.demo",
        "reason": "sandbox lifecycle test",
        "revocation_plan_digest": "c" * 64,
        "membership_revoked": False,
        "session_revoked": False,
        "account_disabled": False,
        "executes_action": False,
    }


def _identity_binding():
    return identity_provider_sandbox_binding({
        "environment": "SANDBOX",
        "production_environment": False,
        "provider_name": "KEYCLOAK",
        "protocol": "OIDC",
        "issuer_ref": "https://idp.sandbox.invalid/realms/atlasquant",
        "admin_api_ref": "keycloak-admin-rest:sandbox",
        "strong_auth_factors": ["PASSKEY", "TOTP"],
        "supports_individual_accounts": True,
        "supports_account_disable": True,
        "supports_session_revocation": True,
        "secret_material_present": False,
        "external_side_effects_executed": False,
    })


def _storage_binding():
    return registry_storage_sandbox_binding({
        "environment": "SANDBOX",
        "production_environment": False,
        "provider_name": "POSTGRESQL",
        "storage_ref": "postgresql://sandbox-registry-ref",
        "supports_transactional_writes": True,
        "supports_versioned_snapshot": True,
        "supports_exact_readback": True,
        "secret_material_present": False,
        "external_side_effects_executed": False,
    })


def _revocation_binding():
    return revocation_connector_sandbox_binding({
        "environment": "SANDBOX",
        "production_environment": False,
        "connector_name": "KEYCLOAK_ADMIN_REST",
        "connector_ref": "keycloak-admin-rest:sandbox-revocation",
        "supports_session_revocation": True,
        "supports_account_disable": True,
        "supports_registry_readback_verification": True,
        "secret_material_present": False,
        "external_side_effects_executed": False,
    })


class TeamAccessSandboxE2ETests(unittest.TestCase):
    def test_reference_stack_is_bounded_and_non_executing(self):
        policy = selected_sandbox_stack()
        self.assertEqual(
            policy["state"], "TEAM_ACCESS_SANDBOX_REFERENCE_STACK_SELECTED"
        )
        self.assertEqual(policy["identity_provider"]["provider"], "KEYCLOAK")
        self.assertEqual(policy["registry_storage"]["provider"], "POSTGRESQL")
        self.assertEqual(
            policy["session_revocation"]["connector"], "KEYCLOAK_ADMIN_REST"
        )
        self.assertEqual(policy["selection_scope"], "SANDBOX_VALIDATION_ONLY")
        self.assertFalse(policy["production_provider_activation_authorized"])
        self.assertFalse(policy["secret_configuration_authorized"])
        self.assertFalse(policy["executes_action"])

    def test_bindings_fail_closed_for_production_or_secrets(self):
        bad_identity = identity_provider_sandbox_binding({
            "environment": "PRODUCTION",
            "production_environment": True,
            "provider_name": "KEYCLOAK",
            "protocol": "OIDC",
            "issuer_ref": "https://id.example",
            "admin_api_ref": "admin-api",
            "strong_auth_factors": ["PASSKEY"],
            "supports_individual_accounts": True,
            "supports_account_disable": True,
            "supports_session_revocation": True,
            "secret_material_present": True,
            "external_side_effects_executed": False,
        })
        self.assertEqual(
            bad_identity["state"], "IDENTITY_PROVIDER_SANDBOX_BINDING_BLOCKED"
        )
        self.assertEqual(bad_identity["binding_digest"], "")
        self.assertFalse(bad_identity["executes_action"])

        bad_storage = registry_storage_sandbox_binding({
            "environment": "SANDBOX",
            "production_environment": False,
            "provider_name": "SQLITE",
            "storage_ref": "local.db",
            "supports_transactional_writes": True,
            "supports_versioned_snapshot": True,
            "supports_exact_readback": True,
            "secret_material_present": False,
            "external_side_effects_executed": False,
        })
        self.assertEqual(
            bad_storage["state"], "REGISTRY_STORAGE_SANDBOX_BINDING_BLOCKED"
        )

    def test_full_sandbox_lifecycle_reaches_admin_exit_review_only(self):
        result = run_team_access_sandbox_e2e(
            _invitation(),
            _registry(),
            _revocation(),
            identity_binding=_identity_binding(),
            storage_binding=_storage_binding(),
            revocation_binding=_revocation_binding(),
            account_evidence={
                "account_ref": "keycloak-user:sandbox:operador.demo",
                "username": "operador.demo",
                "individual_account_verified": True,
                "shared_account_detected": False,
                "account_active_verified": True,
                "observed_at": "2026-09-30T19:30:00+00:00",
            },
            strong_auth_evidence={
                "factor_type": "PASSKEY",
                "factor_ref": "webauthn-credential:sandbox",
                "enrollment_verified": True,
                "challenge_verified": True,
                "observed_at": "2026-09-30T19:31:00+00:00",
            },
            registry_evidence={
                "revision": 1,
                "previous_revision_digest": "0" * 64,
                "readback_registry_digest": _registry_digest(),
                "persistence_verified": True,
                "readback_verified": True,
                "observed_at": "2026-09-30T19:32:00+00:00",
            },
            revocation_evidence={
                "evidence_ref": "sandbox-revocation-proof:001",
                "account_disabled_verified": True,
                "sessions_revoked_verified": True,
                "registry_membership_inactive_verified": True,
                "registry_readback_verified": True,
                "observed_at": "2026-09-30T19:33:00+00:00",
            },
            requested_by="admin.demo",
        )
        self.assertEqual(
            result["state"], "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_EXIT_REVIEW"
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertTrue(result["evidence_digest"])
        self.assertEqual(
            result["activation_review"]["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_ACTIVATION_REVIEW",
        )
        self.assertEqual(
            result["revocation_verification"]["state"],
            "TEAM_REVOCATION_EXTERNALLY_VERIFIED",
        )
        self.assertFalse(result["production_provider_activation_authorized"])
        self.assertFalse(result["production_registry_write_authorized"])
        self.assertFalse(result["production_session_revocation_authorized"])
        self.assertFalse(result["deploy_authorized"])
        self.assertFalse(result["runtime_authorized"])
        self.assertFalse(result["executes_action"])

    def test_missing_revocation_proof_blocks_e2e(self):
        result = run_team_access_sandbox_e2e(
            _invitation(),
            _registry(),
            _revocation(),
            identity_binding=_identity_binding(),
            storage_binding=_storage_binding(),
            revocation_binding=_revocation_binding(),
            account_evidence={
                "account_ref": "keycloak-user:sandbox:operador.demo",
                "username": "operador.demo",
                "individual_account_verified": True,
                "shared_account_detected": False,
                "account_active_verified": True,
                "observed_at": "2026-09-30T19:30:00+00:00",
            },
            strong_auth_evidence={
                "factor_type": "TOTP",
                "factor_ref": "totp:sandbox",
                "enrollment_verified": True,
                "challenge_verified": True,
                "observed_at": "2026-09-30T19:31:00+00:00",
            },
            registry_evidence={
                "revision": 1,
                "previous_revision_digest": "0" * 64,
                "readback_registry_digest": _registry_digest(),
                "persistence_verified": True,
                "readback_verified": True,
                "observed_at": "2026-09-30T19:32:00+00:00",
            },
            revocation_evidence={
                "evidence_ref": "sandbox-revocation-proof:blocked",
                "account_disabled_verified": True,
                "sessions_revoked_verified": False,
                "registry_membership_inactive_verified": True,
                "registry_readback_verified": True,
                "observed_at": "2026-09-30T19:33:00+00:00",
            },
            requested_by="admin.demo",
        )
        self.assertEqual(result["state"], "TEAM_ACCESS_SANDBOX_E2E_BLOCKED")
        self.assertIn("revocation_verification_ready", result["blockers"])
        self.assertEqual(result["evidence_digest"], "")
        self.assertFalse(result["executes_action"])

    def test_module_has_no_network_or_process_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_sandbox_e2e.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(
            imported.intersection({"requests", "httpx", "socket", "subprocess"})
        )


if __name__ == "__main__":
    unittest.main()
