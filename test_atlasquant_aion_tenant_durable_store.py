import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_entitlements import (
    approve_entitlement_request,
    mark_entitlement_from_provider_evidence,
    new_entitlement_request,
)
from atlasquant_aion_tenant import PERSONAL_SCOPE, tenant_namespace
from atlasquant_aion_tenant_durable_store import (
    DurableTenantStore,
    durable_store_policy,
    normalize_workspace_id,
    tenant_workspace_paths,
)


class AionTenantDurableStoreE2ETests(unittest.TestCase):
    def setUp(self):
        self.admin = {"role": "ADMIN", "username": "admin.01"}
        self.user = {
            "session": {
                "username": "cliente.01",
                "role": "USER",
                "credential_fingerprint": "a" * 32,
            }
        }
        self.other = {
            "session": {
                "username": "cliente.02",
                "role": "USER",
                "credential_fingerprint": "b" * 32,
            }
        }
        self.now = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DurableTenantStore(self.tmp.name)
        self.entitlement = self._active("cliente.01", "ent-1")
        self.other_entitlement = self._active("cliente.02", "ent-2")

    def tearDown(self):
        self.tmp.cleanup()

    def _active(self, subject, external_id):
        row = new_entitlement_request(
            subject,
            scope=PERSONAL_SCOPE,
            source_kind="MANUAL_GRANT",
            created_at="2026-10-02T08:00:00Z",
        )
        row = approve_entitlement_request(row, self.admin)
        return mark_entitlement_from_provider_evidence(
            row,
            {
                "confirmed": True,
                "provider": "test_registry",
                "external_id": external_id,
            },
        )

    def test_policy_is_local_fail_closed_and_not_production(self):
        policy = durable_store_policy()
        self.assertTrue(policy["local_durable_io_implemented"])
        self.assertTrue(policy["identity_registry_implemented"])
        self.assertTrue(policy["acl_store_implemented"])
        self.assertTrue(policy["atomic_replace"])
        self.assertTrue(policy["optimistic_concurrency"])
        self.assertTrue(policy["backup_restore_implemented"])
        self.assertFalse(policy["network_io_implemented"])
        self.assertFalse(policy["production_persistence_activated"])
        self.assertFalse(policy["automatic_write"])
        self.assertFalse(policy["automatic_overwrite"])

    def test_write_read_and_revision_conflict(self):
        denied = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Mikael"}},
            approved=False,
            now=self.now,
        )
        self.assertFalse(denied["stored"])
        self.assertEqual(denied["reason"], "EXPLICIT_WRITE_APPROVAL_REQUIRED")
        first = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Mikael"}},
            approved=True,
            now=self.now,
        )
        self.assertTrue(first["stored"])
        loaded = self.store.read(self.user, [self.entitlement], now=self.now)
        self.assertTrue(loaded["loaded"])
        self.assertEqual(loaded["memory"]["profile"]["display_name"], "Mikael")
        self.assertEqual(loaded["revision"], first["revision"])
        stale = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Novo"}},
            approved=True,
            expected_revision="sha256:" + ("0" * 64),
            now=self.now,
        )
        self.assertFalse(stale["stored"])
        self.assertEqual(stale["reason"], "REVISION_CONFLICT")
        self.assertTrue(stale["requires_reload"])

    def test_tenant_and_workspace_are_isolated(self):
        first = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Tenant A"}},
            workspace_id="alpha",
            approved=True,
            now=self.now,
        )
        self.assertTrue(first["stored"])
        foreign = self.store.read(
            self.other,
            [self.other_entitlement],
            workspace_id="alpha",
            now=self.now,
        )
        self.assertFalse(foreign["loaded"])
        self.assertEqual(foreign["reason"], "NOT_FOUND")
        other_paths = tenant_workspace_paths(
            self.other,
            self.tmp.name,
            workspace_id="alpha",
        )
        self.assertNotEqual(first["tenant_id"], other_paths["tenant_id"])
        second_workspace = self.store.read(
            self.user,
            [self.entitlement],
            workspace_id="beta",
            now=self.now,
        )
        self.assertFalse(second_workspace["loaded"])
        self.assertEqual(second_workspace["reason"], "NOT_FOUND")

    def test_workspace_path_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_workspace_id("../admin")
        with self.assertRaises(ValueError):
            tenant_workspace_paths(
                self.user,
                self.tmp.name,
                workspace_id="alpha/../../admin",
            )

    def test_tamper_is_detected_fail_closed(self):
        written = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Original"}},
            approved=True,
            now=self.now,
        )
        self.assertTrue(written["stored"])
        paths = tenant_workspace_paths(self.user, self.tmp.name)
        memory_path = Path(paths["memory"])
        raw = json.loads(memory_path.read_text(encoding="utf-8"))
        raw["memory"]["profile"]["display_name"] = "Tampered"
        memory_path.write_text(
            json.dumps(raw, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        loaded = self.store.read(self.user, [self.entitlement], now=self.now)
        self.assertFalse(loaded["loaded"])
        self.assertEqual(loaded["reason"], "PAYLOAD_DIGEST_MISMATCH")

    def test_backup_and_restore_require_approval_and_revision(self):
        first = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "V1"}},
            approved=True,
            now=self.now,
        )
        self.assertTrue(first["stored"])
        denied = self.store.backup(
            self.user,
            [self.entitlement],
            approved=False,
            now=self.now,
        )
        self.assertFalse(denied["backed_up"])
        backup = self.store.backup(
            self.user,
            [self.entitlement],
            approved=True,
            now=self.now,
        )
        self.assertTrue(backup["backed_up"])
        second = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "V2"}},
            approved=True,
            expected_revision=first["revision"],
            now=self.now,
        )
        self.assertTrue(second["stored"])
        restore = self.store.restore(
            self.user,
            [self.entitlement],
            backup["revision"],
            approved=True,
            expected_revision=second["revision"],
            now=self.now,
        )
        self.assertTrue(restore["restored"])
        loaded = self.store.read(self.user, [self.entitlement], now=self.now)
        self.assertTrue(loaded["loaded"])
        self.assertEqual(loaded["memory"]["profile"]["display_name"], "V1")

    def test_identity_registry_is_credential_bound(self):
        first = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Bound"}},
            approved=True,
            now=self.now,
        )
        self.assertTrue(first["stored"])
        rotated = {
            "session": {
                "username": "cliente.01",
                "role": "USER",
                "credential_fingerprint": "c" * 32,
            }
        }
        self.assertNotEqual(
            tenant_namespace(self.user)["tenant_id"],
            tenant_namespace(rotated)["tenant_id"],
        )
        loaded = self.store.read(rotated, [self.entitlement], now=self.now)
        self.assertFalse(loaded["loaded"])
        self.assertEqual(loaded["reason"], "NOT_FOUND")

    def test_revoked_or_missing_entitlement_blocks_read(self):
        written = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Revocable"}},
            approved=True,
            now=self.now,
        )
        self.assertTrue(written["stored"])
        loaded = self.store.read(self.user, [], now=self.now)
        self.assertFalse(loaded["loaded"])
        self.assertEqual(loaded["reason"], "AION_PERSONAL_ENTITLEMENT_REQUIRED")

    def test_acl_tampering_is_fail_closed(self):
        written = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "ACL"}},
            approved=True,
            now=self.now,
        )
        self.assertTrue(written["stored"])
        paths = tenant_workspace_paths(self.user, self.tmp.name)
        acl_path = Path(paths["acl"])
        acl = json.loads(acl_path.read_text(encoding="utf-8"))
        acl["principal_id"] = "0" * 64
        acl_path.write_text(
            json.dumps(acl, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        loaded = self.store.read(self.user, [self.entitlement], now=self.now)
        self.assertFalse(loaded["loaded"])
        self.assertEqual(loaded["reason"], "ACL_MISMATCH")

    def test_cross_tenant_envelope_transplant_is_rejected(self):
        first = self.store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Tenant A"}},
            approved=True,
            now=self.now,
        )
        second = self.store.write(
            self.other,
            [self.other_entitlement],
            {"profile": {"display_name": "Tenant B"}},
            approved=True,
            now=self.now,
        )
        self.assertTrue(first["stored"])
        self.assertTrue(second["stored"])
        a_paths = tenant_workspace_paths(self.user, self.tmp.name)
        b_paths = tenant_workspace_paths(self.other, self.tmp.name)
        Path(b_paths["memory"]).write_bytes(Path(a_paths["memory"]).read_bytes())
        loaded = self.store.read(
            self.other,
            [self.other_entitlement],
            now=self.now,
        )
        self.assertFalse(loaded["loaded"])
        self.assertEqual(
            loaded["reason"],
            "FOREIGN_TENANT_ENVELOPE_REJECTED",
        )


if __name__ == "__main__":
    unittest.main()
