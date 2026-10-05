from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_entitlements import (
    approve_entitlement_request,
    mark_entitlement_from_provider_evidence,
    new_entitlement_request,
)
from atlasquant_aion_library_foundation import ingest_document, review_document
from atlasquant_aion_library_index import (
    empty_library_index,
    index_document,
    projection_manifest,
    purge_document_projection,
    purge_scope_projection,
    rebuild_scope_projection,
    search_library_index,
)
from atlasquant_aion_tenant import PERSONAL_SCOPE
from atlasquant_aion_tenant_crypto import (
    SCHEMA as CRYPTO_SCHEMA,
    crypto_policy,
)
from atlasquant_aion_tenant_durable_store import (
    DurableTenantStore,
    durable_store_policy,
    tenant_workspace_paths,
)
from atlasquant_aion_tenant_privacy import tenant_deletion_plan


NOW = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)


class KeyRing:
    """Test-only injected key resolver; never persisted by the store."""

    def __init__(self):
        self.keys = {}

    def add(self, tenant_id, workspace_id, key_ref, key_version, key_bytes):
        self.keys[(tenant_id, workspace_id, key_ref, key_version)] = key_bytes

    def retire(self, tenant_id, workspace_id, key_ref, key_version):
        self.keys.pop((tenant_id, workspace_id, key_ref, key_version), None)

    def __call__(self, request):
        key = (
            request["tenant_id"],
            request["workspace_id"],
            request["key_ref"],
            request["key_version"],
        )
        if key not in self.keys:
            raise KeyError("key unavailable")
        return {
            **dict(request),
            "key_bytes": self.keys[key],
        }


def access(username, fingerprint):
    return {
        "session": {
            "username": username,
            "role": "USER",
            "credential_fingerprint": fingerprint,
        }
    }


def active_entitlement(subject, external_id):
    admin = {"role": "ADMIN", "username": "admin.01"}
    row = new_entitlement_request(
        subject,
        scope=PERSONAL_SCOPE,
        source_kind="MANUAL_GRANT",
        created_at="2026-10-05T06:00:00Z",
    )
    row = approve_entitlement_request(row, admin)
    return mark_entitlement_from_provider_evidence(
        row,
        {
            "confirmed": True,
            "provider": "test_registry",
            "external_id": external_id,
        },
    )


def reviewed_document(*, tenant, workspace, title, checksum):
    context = {
        "tenant_id": tenant,
        "workspace_id": workspace,
        "role": "ADMIN",
        "review_approved": True,
    }
    base = ingest_document(
        tenant_id=tenant,
        workspace_id=workspace,
        title=title,
        source_reference="file://" + title.lower().replace(" ", "-") + ".pdf",
        checksum=checksum,
        source_type="INTERNAL_DOCUMENT",
        author="Equipe AION",
        publisher="AtlasQuant",
        published_at="2026-10-01T00:00:00+00:00",
        retrieved_at="2026-10-05T06:00:00+00:00",
        document_version="1",
        rights_status="OWNED",
        summary="Documento revisado para teste de projecao derivada.",
        evidence_refs=["EV-" + checksum],
    )["record"]
    return review_document(
        base,
        trusted_context=context,
        decision="VALIDATED",
        evidence_refs=["EV-" + checksum],
        reason="reviewed source",
    )["record"]


class TenantCryptoDurableStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.user = access("cliente.01", "a" * 32)
        self.other = access("cliente.02", "b" * 32)
        self.entitlement = active_entitlement("cliente.01", "ent-crypto-a")
        self.other_entitlement = active_entitlement("cliente.02", "ent-crypto-b")
        self.paths = tenant_workspace_paths(self.user, self.tmp.name)
        self.other_paths = tenant_workspace_paths(self.other, self.tmp.name)
        self.ring = KeyRing()
        self.ring.add(
            self.paths["tenant_id"],
            "default",
            "tenant-memory-key",
            "v1",
            b"\x11" * 32,
        )
        self.ring.add(
            self.paths["tenant_id"],
            "default",
            "tenant-memory-key",
            "v2",
            b"\x22" * 32,
        )
        self.ring.add(
            self.other_paths["tenant_id"],
            "default",
            "tenant-memory-key",
            "v1",
            b"\x33" * 32,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def store(self, *, version="v1", ring=None, required=True):
        return DurableTenantStore(
            self.tmp.name,
            key_resolver=ring or self.ring,
            key_ref="tenant-memory-key",
            key_version=version,
            require_encryption=required,
        )

    def test_policy_requires_encryption_for_production_without_claiming_kms(self):
        crypto = crypto_policy()
        durable = durable_store_policy()
        self.assertEqual(crypto["algorithm"], "AES-256-GCM")
        self.assertTrue(crypto["encryption_required_for_production"])
        self.assertFalse(crypto["production_kms_connected"])
        self.assertFalse(crypto["key_material_serialized"])
        self.assertTrue(durable["aes256_gcm_supported"])
        self.assertTrue(durable["tenant_workspace_aad_binding"])
        self.assertTrue(durable["encryption_required_for_production"])
        self.assertFalse(durable["production_persistence_activated"])

    def test_encrypted_live_file_and_backup_contain_no_plaintext_memory(self):
        store = self.store()
        marker = "PROFILE-MARKER-ONLY-IN-PLAINTEXT"
        written = store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": marker}},
            approved=True,
            now=NOW,
        )
        self.assertTrue(written["stored"])
        self.assertTrue(written["encrypted_at_rest"])

        raw_text = Path(self.paths["memory"]).read_text(encoding="utf-8")
        outer = json.loads(raw_text)
        self.assertEqual(outer["schema"], CRYPTO_SCHEMA)
        self.assertNotIn(marker, raw_text)
        self.assertNotIn("memory", outer)
        self.assertNotIn("key_bytes", raw_text)

        loaded = store.read(self.user, [self.entitlement], now=NOW)
        self.assertTrue(loaded["loaded"])
        self.assertEqual(loaded["memory"]["profile"]["display_name"], marker)
        self.assertTrue(loaded["encrypted_at_rest"])

        backup = store.backup(
            self.user,
            [self.entitlement],
            approved=True,
            now=NOW,
        )
        self.assertTrue(backup["backed_up"])
        self.assertTrue(backup["encrypted_at_rest"])
        backup_text = Path(backup["backup_path"]).read_text(encoding="utf-8")
        self.assertNotIn(marker, backup_text)
        self.assertEqual(json.loads(backup_text)["schema"], CRYPTO_SCHEMA)

    def test_audit_metadata_does_not_repeat_encrypted_payload_plaintext(self):
        store = self.store()
        marker = "PRIVATE-MEMORY-MARKER-NOT-FOR-AUDIT"
        self.assertTrue(store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": marker}},
            approved=True,
            now=NOW,
        )["stored"])
        self.assertTrue(store.backup(
            self.user,
            [self.entitlement],
            approved=True,
            now=NOW,
        )["backed_up"])
        audit_text = Path(self.paths["audit"]).read_text(encoding="utf-8")
        self.assertNotIn(marker, audit_text)
        self.assertNotIn("key_bytes", audit_text)
        for file_path in Path(self.paths["folder"]).rglob("*.json"):
            self.assertNotIn(marker, file_path.read_text(encoding="utf-8"))

    def test_deletion_plan_covers_live_backup_projection_cache_and_key_surfaces(self):
        memory = {
            "tenant_id": self.paths["tenant_id"],
            "schema": "ATLASQUANT_AION_TENANT_V1",
            "namespace": "tenant:" + self.paths["tenant_id"],
            "created_at": NOW.isoformat(),
            "updated_at": NOW.isoformat(),
            "profile": {},
            "conversation_notes": [],
            "academy_progress": {},
            "watchlist": [],
            "truth_policy": "never_invent",
            "privacy": {},
            "permissions": {},
        }
        plan = tenant_deletion_plan(
            memory,
            self.user,
            explicit_request=True,
        )
        self.assertEqual(plan["status"], "PLAN_READY")
        self.assertEqual(
            set(plan["surfaces"]),
            {
                "LIVE_TENANT_STORE",
                "TENANT_BACKUPS",
                "DERIVED_INDEXES",
                "CACHES",
                "TENANT_DATA_KEY",
                "MINIMAL_AUDIT_METADATA",
            },
        )
        self.assertTrue(plan["derived_projection_purge_required"])
        self.assertTrue(plan["backup_reconciliation_required"])
        self.assertTrue(plan["tenant_key_retirement_review_required"])
        self.assertTrue(plan["crypto_shredding_is_not_sole_deletion_proof"])
        self.assertFalse(plan["deletion_executed"])
        self.assertFalse(plan["executes_action"])

    def test_same_plaintext_rewrite_uses_fresh_nonce_and_ciphertext(self):
        store = self.store()
        first = store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Same"}},
            approved=True,
            now=NOW,
        )
        one = json.loads(Path(self.paths["memory"]).read_text(encoding="utf-8"))
        second = store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Same"}},
            approved=True,
            expected_revision=first["revision"],
            now=NOW,
        )
        self.assertTrue(second["stored"])
        two = json.loads(Path(self.paths["memory"]).read_text(encoding="utf-8"))
        self.assertEqual(first["revision"], second["revision"])
        self.assertNotEqual(one["nonce"], two["nonce"])
        self.assertNotEqual(one["ciphertext"], two["ciphertext"])

    def test_ciphertext_tamper_and_wrong_key_fail_closed(self):
        store = self.store()
        store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Integrity"}},
            approved=True,
            now=NOW,
        )
        path = Path(self.paths["memory"])
        original = json.loads(path.read_text(encoding="utf-8"))
        tampered = deepcopy(original)
        value = tampered["ciphertext"]
        tampered["ciphertext"] = ("A" if value[0] != "A" else "B") + value[1:]
        path.write_text(json.dumps(tampered), encoding="utf-8")
        loaded = store.read(self.user, [self.entitlement], now=NOW)
        self.assertFalse(loaded["loaded"])
        self.assertIn(
            loaded["reason"],
            {"AUTHENTICATION_TAG_INVALID", "DECRYPTION_FAILED"},
        )

        path.write_text(json.dumps(original), encoding="utf-8")
        wrong = KeyRing()
        wrong.add(
            self.paths["tenant_id"],
            "default",
            "tenant-memory-key",
            "v1",
            b"\x99" * 32,
        )
        wrong_store = self.store(ring=wrong)
        loaded = wrong_store.read(self.user, [self.entitlement], now=NOW)
        self.assertFalse(loaded["loaded"])
        self.assertEqual(loaded["reason"], "AUTHENTICATION_TAG_INVALID")

    def test_plaintext_legacy_file_is_rejected_when_encryption_is_required(self):
        legacy = DurableTenantStore(self.tmp.name)
        written = legacy.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Legacy"}},
            approved=True,
            now=NOW,
        )
        self.assertTrue(written["stored"])
        encrypted = self.store()
        loaded = encrypted.read(self.user, [self.entitlement], now=NOW)
        self.assertFalse(loaded["loaded"])
        self.assertEqual(loaded["reason"], "ENCRYPTION_REQUIRED")

    def test_cross_tenant_ciphertext_transplant_is_rejected_before_key_use(self):
        first = self.store()
        self.assertTrue(first.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Tenant A"}},
            approved=True,
            now=NOW,
        )["stored"])

        other_store = DurableTenantStore(
            self.tmp.name,
            key_resolver=self.ring,
            key_ref="tenant-memory-key",
            key_version="v1",
            require_encryption=True,
        )
        self.assertTrue(other_store.write(
            self.other,
            [self.other_entitlement],
            {"profile": {"display_name": "Tenant B"}},
            approved=True,
            now=NOW,
        )["stored"])
        Path(self.other_paths["memory"]).write_bytes(
            Path(self.paths["memory"]).read_bytes()
        )
        loaded = other_store.read(
            self.other,
            [self.other_entitlement],
            now=NOW,
        )
        self.assertFalse(loaded["loaded"])
        self.assertEqual(loaded["reason"], "CRYPTO_TENANT_MISMATCH")

    def test_key_resolver_scope_mismatch_fails_closed(self):
        def mismatched(request):
            return {
                **dict(request),
                "tenant_id": "foreign-tenant",
                "key_bytes": b"\x44" * 32,
            }

        store = DurableTenantStore(
            self.tmp.name,
            key_resolver=mismatched,
            key_ref="tenant-memory-key",
            key_version="v1",
            require_encryption=True,
        )
        result = store.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Blocked"}},
            approved=True,
            now=NOW,
        )
        self.assertFalse(result["stored"])
        self.assertEqual(result["reason"], "KEY_SCOPE_MISMATCH:TENANT_ID")

    def test_encrypted_backup_restore_and_explicit_key_rotation(self):
        store_v1 = self.store(version="v1")
        first = store_v1.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "V1"}},
            approved=True,
            now=NOW,
        )
        backup = store_v1.backup(
            self.user,
            [self.entitlement],
            approved=True,
            now=NOW,
        )
        self.assertTrue(backup["backed_up"])
        self.assertEqual(
            json.loads(Path(backup["backup_path"]).read_text(encoding="utf-8"))["key_version"],
            "v1",
        )

        store_v1.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "V2-data"}},
            approved=True,
            expected_revision=first["revision"],
            now=NOW,
        )

        store_v2 = self.store(version="v2")
        rotated = store_v2.rotate_encryption_key(
            self.user,
            [self.entitlement],
            approved=True,
            now=NOW,
        )
        self.assertTrue(rotated["rotated"])
        self.assertEqual(rotated["previous_key_version"], "v1")
        self.assertEqual(rotated["key_version"], "v2")
        live_outer = json.loads(Path(self.paths["memory"]).read_text(encoding="utf-8"))
        self.assertEqual(live_outer["key_version"], "v2")

        current = store_v2.read(self.user, [self.entitlement], now=NOW)
        restore = store_v2.restore(
            self.user,
            [self.entitlement],
            backup["revision"],
            approved=True,
            expected_revision=current["revision"],
            now=NOW,
        )
        self.assertTrue(restore["restored"])
        self.assertTrue(restore["source_backup_encrypted"])
        self.assertEqual(restore["key_version"], "v2")
        loaded = store_v2.read(self.user, [self.entitlement], now=NOW)
        self.assertEqual(loaded["memory"]["profile"]["display_name"], "V1")

    def test_retired_test_key_makes_old_backup_unreadable_without_deleting_data(self):
        store_v1 = self.store(version="v1")
        first = store_v1.write(
            self.user,
            [self.entitlement],
            {"profile": {"display_name": "Old-key-data"}},
            approved=True,
            now=NOW,
        )
        backup = store_v1.backup(
            self.user,
            [self.entitlement],
            approved=True,
            now=NOW,
        )
        store_v2 = self.store(version="v2")
        self.assertTrue(store_v2.rotate_encryption_key(
            self.user,
            [self.entitlement],
            approved=True,
            now=NOW,
        )["rotated"])

        self.ring.retire(
            self.paths["tenant_id"],
            "default",
            "tenant-memory-key",
            "v1",
        )
        live = store_v2.read(self.user, [self.entitlement], now=NOW)
        self.assertTrue(live["loaded"])
        refused = store_v2.restore(
            self.user,
            [self.entitlement],
            backup["revision"],
            approved=True,
            expected_revision=first["revision"],
            now=NOW,
        )
        self.assertFalse(refused["restored"])
        self.assertEqual(refused["reason"], "KEY_RESOLUTION_FAILED")
        self.assertTrue(Path(backup["backup_path"]).exists())


class DerivedProjectionIsolationTests(unittest.TestCase):
    def setUp(self):
        self.a = {"tenant_id":"tenant:a","workspace_id":"workspace:a","role":"ADMIN","review_approved":True}
        self.b = {"tenant_id":"tenant:b","workspace_id":"workspace:b","role":"ADMIN","review_approved":True}
        self.doc_a = reviewed_document(
            tenant="tenant:a",
            workspace="workspace:a",
            title="Shared Id A",
            checksum="shared-a",
        )
        self.doc_b = reviewed_document(
            tenant="tenant:b",
            workspace="workspace:b",
            title="Shared Id B",
            checksum="shared-b",
        )
        self.doc_b["document_id"] = self.doc_a["document_id"]

    def combined_index(self):
        first = index_document(
            empty_library_index(),
            self.doc_a,
            passages=["alpha payroll projection"],
            trusted_context=self.a,
        )["index"]
        return index_document(
            first,
            self.doc_b,
            passages=["beta payroll projection"],
            trusted_context=self.b,
        )["index"]

    def test_same_document_id_can_coexist_across_scopes_without_reindex_clobber(self):
        state = self.combined_index()
        self.assertEqual(len(state["documents"]), 2)
        self.assertEqual(len(state["passages"]), 2)
        hit_a = search_library_index(
            state,
            "alpha payroll",
            trusted_context=self.a,
        )
        hit_b = search_library_index(
            state,
            "beta payroll",
            trusted_context=self.b,
        )
        self.assertEqual(len(hit_a["hits"]), 1)
        self.assertEqual(len(hit_b["hits"]), 1)
        self.assertIn("alpha", hit_a["hits"][0]["text"])
        self.assertIn("beta", hit_b["hits"][0]["text"])

    def test_document_purge_removes_only_exact_scope_projection(self):
        state = self.combined_index()
        purged = purge_document_projection(
            state,
            self.doc_a["document_id"],
            trusted_context=self.a,
        )
        self.assertEqual(purged["status"], "PURGED")
        self.assertEqual(purged["removed_documents"], 1)
        self.assertEqual(purged["removed_passages"], 1)
        self.assertEqual(
            search_library_index(
                purged["index"],
                "alpha payroll",
                trusted_context=self.a,
            )["hits"],
            [],
        )
        self.assertEqual(
            len(search_library_index(
                purged["index"],
                "beta payroll",
                trusted_context=self.b,
            )["hits"]),
            1,
        )

    def test_foreign_scope_cannot_purge_document_projection(self):
        only_a = index_document(
            empty_library_index(),
            self.doc_a,
            passages=["alpha payroll projection"],
            trusted_context=self.a,
        )["index"]
        denied = purge_document_projection(
            only_a,
            self.doc_a["document_id"],
            trusted_context=self.b,
        )
        self.assertEqual(denied["status"], "BLOCKED")
        self.assertIn("CROSS_SCOPE_DOCUMENT_PURGE_DENIED", denied["blockers"])
        self.assertEqual(denied["index"], only_a)

    def test_scope_purge_preserves_other_tenant_and_projection_is_disposable(self):
        state = self.combined_index()
        manifest = projection_manifest(state)
        self.assertFalse(manifest["source_of_truth"])
        self.assertTrue(manifest["disposable"])
        self.assertTrue(manifest["rebuild_requires_source_documents"])
        self.assertTrue(manifest["projection_digest"].startswith("sha256:"))

        purged = purge_scope_projection(state, trusted_context=self.a)
        self.assertEqual(purged["removed_documents"], 1)
        self.assertEqual(purged["removed_passages"], 1)
        self.assertEqual(
            search_library_index(
                purged["index"],
                "alpha payroll",
                trusted_context=self.a,
            )["hits"],
            [],
        )
        self.assertEqual(
            len(search_library_index(
                purged["index"],
                "beta payroll",
                trusted_context=self.b,
            )["hits"]),
            1,
        )

    def test_rebuild_requires_exact_scope_sources(self):
        rebuilt = rebuild_scope_projection(
            [self.doc_a],
            {self.doc_a["document_id"]: ["alpha rebuilt payroll"]},
            trusted_context=self.a,
        )
        self.assertEqual(rebuilt["status"], "REBUILT")
        self.assertFalse(rebuilt["manifest"]["source_of_truth"])
        self.assertEqual(rebuilt["manifest"]["documents"], 1)
        self.assertEqual(
            len(search_library_index(
                rebuilt["index"],
                "rebuilt payroll",
                trusted_context=self.a,
            )["hits"]),
            1,
        )

        denied = rebuild_scope_projection(
            [self.doc_b],
            {self.doc_b["document_id"]: ["foreign"]},
            trusted_context=self.a,
        )
        self.assertEqual(denied["status"], "BLOCKED")
        self.assertIn("CROSS_SCOPE_REBUILD_SOURCE_DENIED", denied["blockers"])


if __name__ == "__main__":
    unittest.main()
