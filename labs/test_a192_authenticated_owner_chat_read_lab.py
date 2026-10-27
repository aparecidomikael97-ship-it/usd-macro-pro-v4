"""A192: existing PBKDF2 authenticate + real SQLiteChatStore, synthetic only."""
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_access_control import (
    AccessUser,
    has_permission,
    hash_password,
)
from labs.a192_authenticated_owner_chat_read_lab import (
    SCHEMA,
    authenticated_owner_conversation_read,
)

PASS_A = "synthetic-only-long-password-A"
PASS_B = "synthetic-only-long-password-B"


class A192AuthenticatedOwnerChatReadLab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Deterministic synthetic PBKDF2 fixtures; no real credentials.
        cls.h_owner = hash_password(PASS_A, salt=b"fixed-lab-salt-001", iterations=200_000)
        cls.h_sub = hash_password(PASS_B, salt=b"fixed-lab-salt-002", iterations=200_000)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SQLiteChatStore(Path(self.temp.name) / "chat.sqlite3")
        self.addCleanup(self.store.close)
        self.users = {
            "owner-a": AccessUser("owner-a", "ADMIN", self.h_owner, active=True),
            "subscriber-b": AccessUser("subscriber-b", "USER", self.h_sub, active=True),
        }
        self.profiles = {
            "owner-a": {
                "active": True, "role": "ADMIN",
                "owner_id": "owner-id-a", "tenant_id": "tenant-owner-a",
                "allowed_workspaces": ["aion", "trader", "investimentos"],
            },
        }
        self.own = {}
        for workspace in ("aion", "trader", "investimentos"):
            scope = Scope("owner-id-a", "tenant-owner-a", workspace)
            self.own[workspace] = self.store.create_conversation(
                scope, "OWNER_PRIVATE_" + workspace,
            )
        self.other = self.store.create_conversation(
            Scope("owner-id-b", "tenant-owner-b", "aion"),
            "OTHER_OWNER_SECRET_MARKER",
        )

    def read(self, *, workspace="aion", cid=None, **overrides):
        args = dict(
            store=self.store,
            username="owner-a",
            password=PASS_A,
            requested_workspace=workspace,
            conversation_id=cid or self.own[workspace].id,
            trusted_users=self.users,
            trusted_owner_profiles=self.profiles,
            untrusted_claims=None,
        )
        args.update(overrides)
        return authenticated_owner_conversation_read(**args)

    def assert_blocked(self, out):
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "DENIED")
        self.assertFalse(out["local_read_performed"])
        self.assertFalse(out["data_exposed"])
        self.assertFalse(out["operational_authority"])
        self.assertFalse(out["external_action_authorized"])
        self.assertFalse(out["real_session_authentication_proven"])
        self.assertTrue(out["hard_no_go"])
        self.assertEqual(out["p0_homologated"], 0)
        self.assertNotIn("title", out)

    def test_actual_authenticated_owner_aion_summary(self):
        out = self.read()
        self.assertEqual(out["state"], "LOCAL_READ")
        self.assertEqual(out["title"], "OWNER_PRIVATE_aion")
        self.assertTrue(out["local_read_performed"])
        self.assertFalse(out["external_action_authorized"])
        self.assertFalse(out["operational_authority"])
        self.assertFalse(out["real_session_authentication_proven"])
        self.assertTrue(out["hard_no_go"])
        self.assertEqual(out["p0_homologated"], 0)

    def test_actual_authenticated_owner_trader(self):
        out = self.read(workspace="trader")
        self.assertEqual(out["state"], "LOCAL_READ")
        self.assertEqual(out["title"], "OWNER_PRIVATE_trader")

    def test_actual_authenticated_owner_investimentos(self):
        out = self.read(workspace="investimentos")
        self.assertEqual(out["state"], "LOCAL_READ")
        self.assertEqual(out["title"], "OWNER_PRIVATE_investimentos")

    def test_wrong_password_denies_local_read(self):
        self.assert_blocked(self.read(password="bad-password"))

    def test_empty_or_missing_password_denies(self):
        for value in ("", None, ["not-password"]):
            with self.subTest(value=value):
                self.assert_blocked(self.read(password=value))

    def test_unknown_username_denies(self):
        self.assert_blocked(self.read(username="unknown-username"))

    def test_stolen_role_claim_without_password_does_not_authenticate(self):
        self.assert_blocked(self.read(
            password="invalid",
            untrusted_claims={"role": "ADMIN", "approved": True, "owner_id": "owner-id-a"},
        ))

    def test_untrusted_tenant_override_is_ignored(self):
        out = self.read(untrusted_claims={
            "tenant_id": "tenant-owner-b", "workspace_id": "aion",
            "owner_id": "owner-id-b", "role": "ADMIN", "authenticated": True,
        })
        self.assertEqual(out["state"], "LOCAL_READ")
        self.assertEqual(out["title"], "OWNER_PRIVATE_aion")

    def test_subscriber_password_cannot_impersonate_admin(self):
        self.assert_blocked(self.read(username="subscriber-b", password=PASS_B))

    def test_inactive_admin_denied(self):
        self.users["owner-a"] = AccessUser("owner-a", "ADMIN", self.h_owner, False)
        self.assert_blocked(self.read())

    def test_profile_missing_denied(self):
        self.assert_blocked(self.read(trusted_owner_profiles={}))

    def test_profile_inactive_denied(self):
        self.profiles["owner-a"]["active"] = False
        self.assert_blocked(self.read())

    def test_server_profile_role_mismatch_denied(self):
        self.profiles["owner-a"]["role"] = "USER"
        self.assert_blocked(self.read())

    def test_bad_server_ids_denied(self):
        for value in ("../owner-b", "", "A" * 81, "owner/b"):
            with self.subTest(value=value):
                self.profiles["owner-a"]["owner_id"] = value
                self.assert_blocked(self.read())

    def test_unassigned_workspace_denied(self):
        self.profiles["owner-a"]["allowed_workspaces"] = ["aion"]
        self.assert_blocked(self.read(workspace="trader"))

    def test_negocios_frozen_even_if_misconfigured_as_allowed(self):
        self.profiles["owner-a"]["allowed_workspaces"].append("negocios")
        self.assert_blocked(self.read(
            workspace="negocios",
            cid=self.own["aion"].id,
        ))

    def test_invalid_workspace_values_denied(self):
        for workspace in (None, "", "admin", "trader/../../secrets", ["aion"]):
            with self.subTest(workspace=workspace):
                self.assert_blocked(self.read(workspace=workspace, cid=self.own["aion"].id))

    def test_valid_password_cannot_cross_conversation_workspace(self):
        self.assert_blocked(self.read(
            workspace="trader",
            cid=self.own["aion"].id,
        ))

    def test_valid_password_cannot_cross_owner_or_tenant(self):
        self.assert_blocked(self.read(cid=self.other.id))

    def test_no_registry_means_no_authorization(self):
        self.assert_blocked(self.read(trusted_users={}))
        self.assert_blocked(self.read(trusted_users=None))
        self.assert_blocked(self.read(trusted_owner_profiles=None))

    def test_revocation_after_password_rotation_blocks_old_secret(self):
        self.users["owner-a"] = AccessUser("owner-a", "ADMIN", self.h_sub, True)
        self.assert_blocked(self.read(password=PASS_A))

    def test_malformed_conversation_ids_denied(self):
        for value in (["fake"], "A" * 121):
            with self.subTest(value=str(value)):
                self.assert_blocked(self.read(cid=value))

    def test_no_fallback_if_local_store_closed(self):
        self.store.close()
        # Existing raw SQLiteChatStore lacks closed-state checking here:
        # a direct call raises AttributeError instead of StorageUnavailableError.
        with self.assertRaises(AttributeError):
            self.store.get_conversation(
                Scope("owner-id-a", "tenant-owner-a", "aion"),
                self.own["aion"].id,
            )
        print("A192_RAW_CLOSED_STORE_GET=UNHANDLED_ATTRIBUTE_ERROR_RED", flush=True)
        out = self.read()
        self.assert_blocked(out)
        self.assertEqual(out["reason"], "STORE_CLOSED")

    def test_role_only_has_permission_is_not_authentication_expected_red(self):
        # Existing helper has_permission checks role, not actual credentials.
        self.assertTrue(has_permission({"role": "ADMIN"}, "admin:read"))
        print("A192_ROLE_ONLY_PERMISSION_HELPER=NOT_AUTHENTICATION_RED", flush=True)
        self.assert_blocked(self.read(
            password="wrong",
            untrusted_claims={"role": "ADMIN"},
        ))

    def test_direct_scope_forgery_bypasses_bridge_expected_red(self):
        # Deliberate counterexample: caller receiving raw store handle can
        # bypass this wrapper. Real backend entrypoint must prohibit this.
        raw_scope = Scope("owner-id-b", "tenant-owner-b", "aion")
        self.assertEqual(
            self.store.get_conversation(raw_scope, self.other.id).title,
            "OTHER_OWNER_SECRET_MARKER",
        )
        self.assert_blocked(self.read(cid=self.other.id))
        print("A192_RAW_STORE_SCOPE_FORGERY=ENTRYPOINT_BOUNDARY_REQUIRED_RED", flush=True)

    def test_attacker_control_of_server_registry_is_a_red_counterexample(self):
        # If the caller can replace the trusted server registry, it can
        # bind its *own* password to another owner's data. This is NOT safe.
        fabricated_users = {
            "attacker": AccessUser("attacker", "ADMIN", self.h_sub, True),
        }
        fabricated_profiles = {
            "attacker": {
                "active": True, "role": "ADMIN",
                "owner_id": "owner-id-b", "tenant_id": "tenant-owner-b",
                "allowed_workspaces": ["aion"],
            },
        }
        out = self.read(
            username="attacker", password=PASS_B,
            cid=self.other.id,
            trusted_users=fabricated_users,
            trusted_owner_profiles=fabricated_profiles,
        )
        self.assertEqual(out["state"], "LOCAL_READ")
        self.assertEqual(out["title"], "OTHER_OWNER_SECRET_MARKER")
        print("A192_SERVER_REGISTRY_CONTROL=NO_EXTERNAL_TRUST_ROOT_RED", flush=True)


if __name__ == "__main__":
    unittest.main()
