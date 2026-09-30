import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_rbac import (
    TEAM_PROFILES,
    audit_team_registry,
    membership_record,
    prepare_membership_revocation_plan,
    prepare_team_invitation_plan,
    team_access_decision,
)


def _admin():
    return {
        "username": "mikael",
        "role": "ADMIN",
        "permissions": ["app:read", "admin:manage_users"],
    }


def _staff():
    return {
        "username": "maria",
        "role": "USER",
        "permissions": ["app:read"],
    }


def _member(profile="SUPPORT", tenants=None):
    if tenants is None:
        tenants = ["client-a"]
    return membership_record(
        username="maria",
        profile=profile,
        tenant_ids=tenants,
        active=True,
        strong_auth_required=True,
    )


class BusinessTeamAccessRbacTests(unittest.TestCase):
    def test_expected_profiles_exist(self):
        self.assertEqual(
            TEAM_PROFILES,
            (
                "BUSINESS_OWNER",
                "BUSINESS_MANAGER",
                "FINANCE",
                "SUPPORT",
                "MARKETING",
                "OPERATOR",
                "VIEWER",
            ),
        )

    def test_membership_is_individual_and_scoped(self):
        row = _member()
        self.assertEqual(row["state"], "TEAM_MEMBERSHIP_VALID")
        self.assertEqual(row["username"], "maria")
        self.assertEqual(row["tenant_ids"], ["client-a"])
        self.assertIn("support:manage", row["permissions"])
        self.assertNotIn("finance:manage", row["permissions"])
        self.assertFalse(row["account_created"])
        self.assertFalse(row["executes_action"])

    def test_admin_can_prepare_but_not_send_invitation(self):
        plan = prepare_team_invitation_plan(
            _admin(),
            username="maria",
            profile="SUPPORT",
            tenant_ids=["client-a"],
            expires_at="2026-10-07T12:00:00Z",
        )
        self.assertEqual(plan["state"], "TEAM_INVITATION_REVIEW_READY")
        self.assertTrue(plan["requires_individual_account"])
        self.assertTrue(plan["requires_strong_auth"])
        self.assertFalse(plan["shared_admin_login_allowed"])
        self.assertFalse(plan["invitation_sent"])
        self.assertFalse(plan["account_created"])
        self.assertFalse(plan["executes_action"])

    def test_non_admin_cannot_prepare_invitation(self):
        plan = prepare_team_invitation_plan(
            _staff(),
            username="joao",
            profile="VIEWER",
            tenant_ids=["client-a"],
            expires_at="2026-10-07T12:00:00Z",
        )
        self.assertEqual(plan["state"], "TEAM_INVITATION_BLOCKED")

    def test_registry_rejects_unknown_tenant_scope(self):
        audit = audit_team_registry(
            [_member(tenants=["client-x"])],
            known_tenant_ids=["client-a", "client-b"],
        )
        self.assertFalse(audit["integrity_verified"])
        self.assertIn("row_1_unknown_tenant_scope", audit["blockers"])

    def test_registry_rejects_duplicate_username(self):
        audit = audit_team_registry(
            [_member(), _member(profile="VIEWER")],
            known_tenant_ids=["client-a"],
        )
        self.assertFalse(audit["integrity_verified"])
        self.assertIn("row_2_duplicate_username", audit["blockers"])

    def test_support_can_manage_support_only_inside_scope(self):
        allowed = team_access_decision(
            _staff(),
            _member(),
            tenant_id="client-a",
            action="manage_support",
            strong_auth_verified=True,
        )
        self.assertTrue(allowed["allowed"])
        self.assertTrue(allowed["aion_must_obey_same_decision"])
        self.assertFalse(allowed["executes_action"])

        denied = team_access_decision(
            _staff(),
            _member(),
            tenant_id="client-a",
            action="manage_finance",
            strong_auth_verified=True,
        )
        self.assertFalse(denied["allowed"])
        self.assertIn("profile_permission", denied["blockers"])

    def test_cross_tenant_access_is_blocked(self):
        decision = team_access_decision(
            _staff(),
            _member(),
            tenant_id="client-b",
            action="read_client",
            strong_auth_verified=True,
        )
        self.assertFalse(decision["allowed"])
        self.assertIn("tenant_in_scope", decision["blockers"])
        self.assertFalse(decision["cross_tenant_access"])

    def test_strong_auth_is_required(self):
        decision = team_access_decision(
            _staff(),
            _member(),
            tenant_id="client-a",
            action="read_client",
            strong_auth_verified=False,
        )
        self.assertFalse(decision["allowed"])
        self.assertIn("strong_auth_verified", decision["blockers"])

    def test_critical_actions_are_never_granted_by_team_profile(self):
        owner = membership_record(
            username="maria",
            profile="BUSINESS_OWNER",
            tenant_ids=["client-a"],
        )
        decision = team_access_decision(
            _staff(),
            owner,
            tenant_id="client-a",
            action="deploy_production",
            strong_auth_verified=True,
        )
        self.assertFalse(decision["allowed"])
        self.assertEqual(
            decision["reason"],
            "CRITICAL_ACTION_REQUIRES_SEPARATE_GATE",
        )

    def test_forged_membership_digest_is_blocked(self):
        member = _member()
        member["profile"] = "FINANCE"
        decision = team_access_decision(
            _staff(),
            member,
            tenant_id="client-a",
            action="read_finance",
            strong_auth_verified=True,
        )
        self.assertFalse(decision["allowed"])
        self.assertIn("membership_integrity", decision["blockers"])

    def test_revocation_is_only_a_plan(self):
        plan = prepare_membership_revocation_plan(
            _admin(),
            _member(),
            reason="employee offboarding",
        )
        self.assertEqual(plan["state"], "TEAM_REVOCATION_REVIEW_READY")
        self.assertFalse(plan["membership_revoked"])
        self.assertFalse(plan["session_revoked"])
        self.assertFalse(plan["account_disabled"])
        self.assertFalse(plan["executes_action"])

    def test_admin_ui_exposes_team_access_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("23 · Equipe & Acessos / RBAC", source)
        self.assertIn("business_team_access_profiles", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_rbac.py"
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
