import ast
import unittest
from pathlib import Path

from atlasquant_access_control import ROLE_PERMISSIONS
from atlasquant_aion_business_team_access_rbac import (
    audit_team_registry,
    membership_record,
)
from atlasquant_aion_business_team_access_production_binding import (
    account_provisioning_attestation,
    production_binding_policy,
    registry_persistence_attestation,
    revocation_execution_attestation,
    strong_auth_attestation,
    team_access_activation_review,
)


def _membership():
    return membership_record(
        username="operador.demo",
        profile="OPERATOR",
        tenant_ids=["tenant-a"],
        active=True,
        strong_auth_required=True,
    )


def _invitation():
    member = _membership()
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_RBAC_V1",
        "version": "1",
        "state": "TEAM_INVITATION_REVIEW_READY",
        "actor": "admin.demo",
        "membership": member,
        "expires_at": "2026-10-01T18:00:00+00:00",
        "invitation_plan_digest": "1" * 64,
        "requires_individual_account": True,
        "requires_strong_auth": True,
        "shared_admin_login_allowed": False,
        "invitation_sent": False,
        "account_created": False,
        "membership_applied": False,
        "executes_action": False,
    }


def _account():
    return account_provisioning_attestation(
        _invitation(),
        provider_ref="identity://primary",
        account_ref="identity://account/operator-demo",
        account_username="operador.demo",
        individual_account_verified=True,
        shared_account_detected=False,
        account_active_verified=True,
        observed_at="2026-09-30T18:00:00+00:00",
    )


def _strong_auth():
    return strong_auth_attestation(
        _account(),
        factor_type="PASSKEY",
        factor_ref="identity://factor/passkey-01",
        enrollment_verified=True,
        challenge_verified=True,
        observed_at="2026-09-30T18:01:00+00:00",
    )


def _registry_audit():
    return audit_team_registry(
        [_membership()],
        known_tenant_ids=["tenant-a"],
    )


def _registry():
    audit = _registry_audit()
    # Derive digest through an intentionally blocked probe, then use its expected
    # value by reconstructing the same canonical payload in the tested function.
    # The read-back value is obtained from a first call with a placeholder and
    # then recomputed by the function's stable registry payload contract below.
    import hashlib, json
    member = audit["memberships"][0]
    payload = {
        "team_rbac_schema": audit["schema"],
        "member_count": audit["member_count"],
        "memberships": [{
            "username": member["username"],
            "profile": member["profile"],
            "tenant_ids": sorted(member["tenant_ids"]),
            "active": member["active"] is True,
            "strong_auth_required": member["strong_auth_required"] is True,
            "membership_digest": member["membership_digest"],
        }],
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return registry_persistence_attestation(
        audit,
        storage_ref="registry://business/team/v1",
        revision=1,
        previous_revision_digest="0" * 64,
        readback_registry_digest=digest,
        persistence_verified=True,
        readback_verified=True,
        observed_at="2026-09-30T18:02:00+00:00",
    )


class TeamAccessProductionBindingTests(unittest.TestCase):
    def test_policy_requires_individual_account_and_never_executes(self):
        row = production_binding_policy()
        self.assertTrue(row["individual_account_required"])
        self.assertFalse(row["shared_account_allowed"])
        self.assertFalse(row["account_provisioning_executed_here"])
        self.assertFalse(row["session_revocation_executed_here"])

    def test_account_attestation_rejects_shared_account(self):
        good = _account()
        self.assertEqual(good["state"], "ACCOUNT_PROVISIONING_ATTESTATION_READY")
        self.assertFalse(good["account_created_by_module"])

        bad = account_provisioning_attestation(
            _invitation(),
            provider_ref="identity://primary",
            account_ref="identity://account/shared",
            account_username="operador.demo",
            individual_account_verified=False,
            shared_account_detected=True,
            account_active_verified=True,
            observed_at="2026-09-30T18:00:00+00:00",
        )
        self.assertEqual(
            bad["state"],
            "ACCOUNT_PROVISIONING_ATTESTATION_BLOCKED",
        )

    def test_account_username_must_match_invitation(self):
        row = account_provisioning_attestation(
            _invitation(),
            provider_ref="identity://primary",
            account_ref="identity://account/other",
            account_username="outro.usuario",
            individual_account_verified=True,
            shared_account_detected=False,
            account_active_verified=True,
            observed_at="2026-09-30T18:00:00+00:00",
        )
        self.assertEqual(
            row["state"],
            "ACCOUNT_PROVISIONING_ATTESTATION_BLOCKED",
        )

    def test_only_strong_factors_are_accepted(self):
        good = _strong_auth()
        self.assertEqual(good["state"], "STRONG_AUTH_ATTESTATION_READY")
        self.assertEqual(good["factor_type"], "PASSKEY")
        self.assertFalse(good["mfa_enabled_by_module"])

        sms = strong_auth_attestation(
            _account(),
            factor_type="SMS",
            factor_ref="identity://factor/sms-01",
            enrollment_verified=True,
            challenge_verified=True,
            observed_at="2026-09-30T18:01:00+00:00",
        )
        self.assertEqual(sms["state"], "STRONG_AUTH_ATTESTATION_BLOCKED")

    def test_registry_persistence_requires_exact_readback(self):
        good = _registry()
        self.assertEqual(
            good["state"],
            "REGISTRY_PERSISTENCE_ATTESTATION_READY",
        )
        self.assertFalse(good["registry_written_by_module"])
        self.assertIn(_membership()["membership_digest"], good["membership_digests"])

        bad = registry_persistence_attestation(
            _registry_audit(),
            storage_ref="registry://business/team/v1",
            revision=1,
            previous_revision_digest="0" * 64,
            readback_registry_digest="f" * 64,
            persistence_verified=True,
            readback_verified=True,
            observed_at="2026-09-30T18:02:00+00:00",
        )
        self.assertEqual(
            bad["state"],
            "REGISTRY_PERSISTENCE_ATTESTATION_BLOCKED",
        )

    def test_activation_review_stops_before_activation(self):
        row = team_access_activation_review(
            _invitation(),
            _account(),
            _strong_auth(),
            _registry(),
            requested_by="admin.demo",
        )
        self.assertEqual(
            row["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_ACTIVATION_REVIEW",
        )
        self.assertFalse(row["access_activation_authorized"])
        self.assertFalse(row["session_activation_authorized"])
        self.assertFalse(row["permission_escalation_authorized"])
        self.assertFalse(row["runtime_authorized"])

    def test_revocation_requires_account_session_registry_evidence(self):
        plan = {
            "schema": "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_RBAC_V1",
            "version": "1",
            "state": "TEAM_REVOCATION_REVIEW_READY",
            "actor": "admin.demo",
            "target_username": "operador.demo",
            "reason": "access no longer required",
            "revocation_plan_digest": "2" * 64,
            "membership_revoked": False,
            "session_revoked": False,
            "account_disabled": False,
            "executes_action": False,
        }
        row = revocation_execution_attestation(
            plan,
            provider_ref="identity://primary",
            evidence_ref="audit://revocation/001",
            account_disabled_verified=True,
            sessions_revoked_verified=True,
            registry_membership_inactive_verified=True,
            registry_readback_verified=True,
            observed_at="2026-09-30T18:03:00+00:00",
        )
        self.assertEqual(row["state"], "TEAM_REVOCATION_EXTERNALLY_VERIFIED")
        self.assertFalse(row["account_disable_executed_by_module"])
        self.assertFalse(row["session_revocation_executed_by_module"])

        blocked = revocation_execution_attestation(
            plan,
            provider_ref="identity://primary",
            evidence_ref="audit://revocation/001",
            account_disabled_verified=True,
            sessions_revoked_verified=False,
            registry_membership_inactive_verified=True,
            registry_readback_verified=True,
            observed_at="2026-09-30T18:03:00+00:00",
        )
        self.assertEqual(
            blocked["state"],
            "TEAM_REVOCATION_VERIFICATION_BLOCKED",
        )

    def test_admin_exposes_team_access_production_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("37 · Equipe & Acessos · Producao", source)
        self.assertIn("business_team_production_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_production_binding.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests",
            "urllib",
            "httpx",
            "socket",
            "subprocess",
            "github",
            "paramiko",
            "docker",
            "kubernetes",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
