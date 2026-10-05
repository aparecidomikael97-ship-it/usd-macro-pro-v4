from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from atlasquant_aion_secret_backend import (
    EncryptedStagingSecretBackend,
    SecretBackendIntegrityError,
    verified_vault_backend_view,
)
from atlasquant_aion_vault import default_vault, new_vault_entry

SCOPE = Scope("owner-a", "tenant-a", "workspace-a")
NOW = "2026-10-05T13:40:00+00:00"
SECRET = "SYNTHETIC-SECRET-MARKER-DO-NOT-PERSIST-PLAINTEXT"


class KeyRing:
    def __init__(self):
        self.keys = {}

    def add(self, owner, tenant, workspace, key_ref, key_version, key_bytes):
        self.keys[(owner, tenant, workspace, key_ref, key_version)] = key_bytes

    def __call__(self, request):
        key = (
            request["owner_id"],
            request["tenant_id"],
            request["workspace_id"],
            request["key_ref"],
            request["key_version"],
        )
        if key not in self.keys:
            raise KeyError("key unavailable")
        return {**dict(request), "key_bytes": self.keys[key]}


class AionPhysicalSecretBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "vault.sqlite3"
        self.keys = KeyRing()
        self.keys.add(
            SCOPE.owner_id, SCOPE.tenant_id, SCOPE.workspace_id,
            "master-key", "v1", b"\x11" * 32,
        )
        self.keys.add(
            SCOPE.owner_id, SCOPE.tenant_id, SCOPE.workspace_id,
            "master-key", "v2", b"\x22" * 32,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def backend(self, *, scope=SCOPE, version="v1", ring=None):
        return EncryptedStagingSecretBackend(
            self.path,
            scope,
            key_resolver=ring or self.keys,
            key_ref="master-key",
            key_version=version,
            environment="STAGING",
        )

    def test_put_persists_ciphertext_not_plaintext(self):
        backend = self.backend()
        meta = backend.put(
            "provider.openai",
            SECRET,
            explicit_owner_approval=True,
            created_at=NOW,
        )
        self.assertEqual(meta["state"], "ACTIVE")
        self.assertFalse(meta["contains_secret_value"])
        self.assertNotIn(SECRET, repr(meta))
        backend.close()

        raw = self.path.read_bytes()
        self.assertNotIn(SECRET.encode("utf-8"), raw)
        for extra in (self.path.with_suffix(".sqlite3-wal"), self.path.with_suffix(".sqlite3-shm")):
            if extra.exists():
                self.assertNotIn(SECRET.encode("utf-8"), extra.read_bytes())

    def test_resolve_materializes_only_internal_secret_bytes(self):
        backend = self.backend()
        backend.put("provider.openai", SECRET, explicit_owner_approval=True, created_at=NOW)
        self.assertEqual(backend.resolve("provider.openai"), SECRET.encode("utf-8"))
        self.assertEqual(
            backend.credential_resolver("EXTERNAL_VAULT", "provider.openai"),
            SECRET.encode("utf-8"),
        )
        with self.assertRaises(PermissionError):
            backend.credential_resolver("ENVIRONMENT", "provider.openai")
        backend.close()

    def test_string_or_numeric_approval_never_writes_rotates_or_revokes(self):
        for value in ("true", "yes", 1, 0, None):
            with self.subTest(value=value):
                backend = self.backend()
                with self.assertRaises(PermissionError):
                    backend.put(
                        "provider.openai",
                        SECRET,
                        explicit_owner_approval=value,
                        created_at=NOW,
                    )
                backend.close()

    def test_rotation_is_atomic_versioned_and_changes_ciphertext(self):
        backend = self.backend()
        first = backend.put(
            "provider.openai", SECRET,
            explicit_owner_approval=True, created_at=NOW,
        )
        old_digest = first["ciphertext_digest"]
        backend.close()

        rotated_backend = self.backend(version="v2")
        second = rotated_backend.rotate(
            "provider.openai",
            "ROTATED-SYNTHETIC-SECRET",
            expected_version=1,
            explicit_owner_approval=True,
            changed_at="2026-10-05T13:41:00+00:00",
        )
        self.assertEqual(second["secret_version"], 2)
        self.assertEqual(second["key_version"], "v2")
        self.assertNotEqual(second["ciphertext_digest"], old_digest)
        self.assertEqual(
            rotated_backend.resolve("provider.openai"),
            b"ROTATED-SYNTHETIC-SECRET",
        )
        retired = rotated_backend.db.execute(
            """SELECT state FROM aion_staged_secrets
               WHERE owner=? AND tenant=? AND workspace=? AND secret_id=? AND secret_version=1""",
            (SCOPE.owner_id, SCOPE.tenant_id, SCOPE.workspace_id, "provider.openai"),
        ).fetchone()
        self.assertEqual(retired["state"], "RETIRED")
        rotated_backend.close()

    def test_stale_rotation_version_is_rejected_without_mutation(self):
        backend = self.backend()
        backend.put("provider.openai", SECRET, explicit_owner_approval=True, created_at=NOW)
        with self.assertRaisesRegex(ValueError, "SECRET_VERSION_CONFLICT"):
            backend.rotate(
                "provider.openai", "new",
                expected_version=2,
                explicit_owner_approval=True,
                changed_at="2026-10-05T13:41:00+00:00",
            )
        self.assertEqual(backend.metadata("provider.openai")["secret_version"], 1)
        backend.close()

    def test_revocation_prevents_future_resolution(self):
        backend = self.backend()
        backend.put("provider.openai", SECRET, explicit_owner_approval=True, created_at=NOW)
        meta = backend.revoke(
            "provider.openai",
            expected_version=1,
            explicit_owner_approval=True,
            changed_at="2026-10-05T13:42:00+00:00",
        )
        self.assertEqual(meta["state"], "REVOKED")
        with self.assertRaises(PermissionError):
            backend.resolve("provider.openai")
        backend.close()

    def test_restart_preserves_encrypted_secret_and_metadata(self):
        backend = self.backend()
        backend.put("provider.openai", SECRET, explicit_owner_approval=True, created_at=NOW)
        backend.close()

        reopened = self.backend()
        self.assertEqual(reopened.resolve("provider.openai"), SECRET.encode("utf-8"))
        self.assertEqual(reopened.integrity_report()["state"], "MATCH")
        reopened.close()

    def test_ciphertext_tamper_fails_closed(self):
        backend = self.backend()
        backend.put("provider.openai", SECRET, explicit_owner_approval=True, created_at=NOW)
        row = backend.db.execute(
            """SELECT ciphertext FROM aion_staged_secrets
               WHERE owner=? AND tenant=? AND workspace=? AND secret_id=?""",
            (SCOPE.owner_id, SCOPE.tenant_id, SCOPE.workspace_id, "provider.openai"),
        ).fetchone()
        damaged = bytearray(row["ciphertext"])
        damaged[0] ^= 1
        with backend.db:
            backend.db.execute(
                """UPDATE aion_staged_secrets SET ciphertext=?
                   WHERE owner=? AND tenant=? AND workspace=? AND secret_id=?""",
                (bytes(damaged), SCOPE.owner_id, SCOPE.tenant_id, SCOPE.workspace_id, "provider.openai"),
            )
        with self.assertRaises(SecretBackendIntegrityError):
            backend.resolve("provider.openai")
        self.assertEqual(backend.integrity_report()["state"], "MISMATCH")
        backend.close()

    def test_wrong_key_fails_authentication(self):
        backend = self.backend()
        backend.put("provider.openai", SECRET, explicit_owner_approval=True, created_at=NOW)
        backend.close()

        wrong = KeyRing()
        wrong.add(
            SCOPE.owner_id, SCOPE.tenant_id, SCOPE.workspace_id,
            "master-key", "v1", b"\x99" * 32,
        )
        reopened = self.backend(ring=wrong)
        with self.assertRaises(SecretBackendIntegrityError):
            reopened.resolve("provider.openai")
        self.assertEqual(reopened.integrity_report()["state"], "MISMATCH")
        reopened.close()

    def test_scope_isolation_allows_same_id_without_cross_read(self):
        backend = self.backend()
        backend.put("provider.openai", SECRET, explicit_owner_approval=True, created_at=NOW)
        backend.close()

        other = Scope("owner-b", "tenant-b", "workspace-b")
        self.keys.add(
            other.owner_id, other.tenant_id, other.workspace_id,
            "master-key", "v1", b"\x33" * 32,
        )
        foreign = self.backend(scope=other)
        with self.assertRaises(PermissionError):
            foreign.resolve("provider.openai")
        foreign.put(
            "provider.openai", "TENANT-B-SECRET",
            explicit_owner_approval=True, created_at=NOW,
        )
        self.assertEqual(foreign.resolve("provider.openai"), b"TENANT-B-SECRET")
        foreign.close()

        reopened = self.backend()
        self.assertEqual(reopened.resolve("provider.openai"), SECRET.encode("utf-8"))
        reopened.close()

    def test_attestation_is_verified_staging_not_production(self):
        backend = self.backend()
        backend.put("provider.openai", SECRET, explicit_owner_approval=True, created_at=NOW)
        att = backend.attestation()
        self.assertEqual(att["state"], "VERIFIED_STAGING_BACKEND")
        self.assertTrue(att["backend_connected"])
        self.assertTrue(att["encrypted_at_rest"])
        self.assertFalse(att["plaintext_persisted"])
        self.assertFalse(att["key_material_serialized"])
        self.assertTrue(att["rotation_supported"])
        self.assertTrue(att["revocation_supported"])
        self.assertFalse(att["production_kms_connected"])
        self.assertFalse(att["production_ready"])
        self.assertFalse(att["executes_action"])
        self.assertNotIn(SECRET, repr(att))
        backend.close()

    def test_vault_view_binds_active_external_refs_to_verified_backend(self):
        backend = self.backend()
        backend.put("provider.openai", SECRET, explicit_owner_approval=True, created_at=NOW)

        vault = default_vault()
        vault["entries"] = [
            new_vault_entry(
                "provider-openai-ref",
                kind="SECRET_REF",
                backend="EXTERNAL_VAULT",
                locator_ref="provider.openai",
                allowed_tool_ids=["tool.openai"],
                credential_scopes=["chat:write"],
            )
        ]
        view = verified_vault_backend_view(
            vault,
            backend.attestation(),
            trusted_scope={
                "owner_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
            },
        )
        self.assertEqual(view["state"], "VERIFIED_STAGING_BACKEND")
        self.assertTrue(view["backend_connected"])
        self.assertEqual(view["unresolved_refs"], [])
        self.assertFalse(view["production_kms_connected"])
        self.assertFalse(view["production_ready"])
        self.assertFalse(view["secret_values_exported"])
        backend.close()

    def test_unresolved_vault_reference_blocks_backend_view(self):
        backend = self.backend()
        vault = default_vault()
        vault["entries"] = [
            new_vault_entry(
                "missing-ref",
                kind="SECRET_REF",
                backend="EXTERNAL_VAULT",
                locator_ref="missing.secret",
                allowed_tool_ids=["tool.missing"],
                credential_scopes=["read"],
            )
        ]
        view = verified_vault_backend_view(
            vault,
            backend.attestation(),
            trusted_scope={
                "owner_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
            },
        )
        self.assertEqual(view["state"], "BLOCKED")
        self.assertIn("ACTIVE_VAULT_REFS_UNRESOLVED", view["blockers"])
        backend.close()

    def test_production_environment_is_rejected(self):
        with self.assertRaises(PermissionError):
            EncryptedStagingSecretBackend(
                self.path,
                SCOPE,
                key_resolver=self.keys,
                key_ref="master-key",
                key_version="v1",
                environment="PRODUCTION",
            )


if __name__ == "__main__":
    unittest.main()
