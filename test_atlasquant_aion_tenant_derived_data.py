from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_aion_tenant_derived_data import (
    ARTIFACT_KINDS,
    acknowledge_derived_purge,
    create_deletion_tombstone,
    default_derived_registry,
    derived_cache_key,
    derived_data_summary,
    derived_namespace,
    register_derived_artifact,
    resolve_derived_artifact,
    scope_binding,
    validate_derived_registry,
)


NOW = datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc)


def scope(tenant="tenant-a", workspace="workspace-a", owner="mikael"):
    return {
        "owner_id": owner,
        "tenant_id": tenant,
        "workspace_id": workspace,
    }


class AionTenantDerivedDataIsolationTests(unittest.TestCase):
    def _register(
        self,
        registry,
        *,
        kind,
        ref,
        trusted=None,
        policy="policy-v1",
        data="data-v1",
        producer="producer-v1",
        retention_until="",
    ):
        return register_derived_artifact(
            registry,
            kind=kind,
            artifact_ref=ref,
            trusted_context=trusted or scope(),
            source_digest="sha256:source",
            policy_version=policy,
            data_version=data,
            producer_version=producer,
            purpose="tenant-derived-test",
            query_digest="sha256:query",
            retention_until=retention_until,
            created_at=NOW,
        )

    def test_same_payload_different_tenant_gets_different_namespace_and_cache_key(self):
        a = scope("tenant-a", "workspace-a")
        b = scope("tenant-b", "workspace-a")
        self.assertNotEqual(
            scope_binding(a)["scope_digest"],
            scope_binding(b)["scope_digest"],
        )
        self.assertNotEqual(
            derived_namespace("CACHE", a),
            derived_namespace("CACHE", b),
        )
        key_a = derived_cache_key(
            trusted_context=a,
            purpose="search",
            source_digest="sha256:same",
            policy_version="p1",
            data_version="d1",
            producer_version="v1",
            query_digest="q1",
        )
        key_b = derived_cache_key(
            trusted_context=b,
            purpose="search",
            source_digest="sha256:same",
            policy_version="p1",
            data_version="d1",
            producer_version="v1",
            query_digest="q1",
        )
        self.assertNotEqual(key_a, key_b)

    def test_workspace_change_also_changes_storage_boundary(self):
        a = scope("tenant-a", "workspace-a")
        b = scope("tenant-a", "workspace-b")
        self.assertNotEqual(
            scope_binding(a)["scope_digest"],
            scope_binding(b)["scope_digest"],
        )

    def test_cache_key_binds_policy_data_and_producer_versions(self):
        base = dict(
            trusted_context=scope(),
            purpose="answer",
            source_digest="sha256:s",
            data_version="d1",
            producer_version="v1",
            query_digest="q",
        )
        p1 = derived_cache_key(policy_version="p1", **base)
        p2 = derived_cache_key(policy_version="p2", **base)
        self.assertNotEqual(p1, p2)

        d2 = derived_cache_key(
            trusted_context=scope(),
            purpose="answer",
            source_digest="sha256:s",
            policy_version="p1",
            data_version="d2",
            producer_version="v1",
            query_digest="q",
        )
        self.assertNotEqual(p1, d2)

        v2 = derived_cache_key(
            trusted_context=scope(),
            purpose="answer",
            source_digest="sha256:s",
            policy_version="p1",
            data_version="d1",
            producer_version="v2",
            query_digest="q",
        )
        self.assertNotEqual(p1, v2)

    def test_cache_key_refuses_missing_version_binding(self):
        with self.assertRaisesRegex(ValueError, "requires"):
            derived_cache_key(
                trusted_context=scope(),
                purpose="answer",
                source_digest="sha256:s",
                policy_version="",
                data_version="d1",
                producer_version="v1",
            )

    def test_registered_index_is_rebuildable_projection_never_canonical(self):
        registry = default_derived_registry(scope())
        result = self._register(
            registry,
            kind="INDEX",
            ref="library-index:1",
        )
        row = result["artifact"]
        self.assertTrue(row["rebuildable_projection"])
        self.assertFalse(row["canonical_source"])
        self.assertFalse(row["payload_content_stored_in_registry"])
        self.assertEqual(
            validate_derived_registry(
                result["registry"],
                trusted_context=scope(),
            )["state"],
            "CONFIRMED",
        )

    def test_all_derived_classes_are_namespace_bound_and_noncanonical(self):
        registry = default_derived_registry(scope())
        for kind in ARTIFACT_KINDS:
            registered = self._register(
                registry,
                kind=kind,
                ref=f"{kind.lower()}:1",
                retention_until=(
                    (NOW + timedelta(days=30)).isoformat()
                    if kind == "BACKUP"
                    else ""
                ),
            )
            registry = registered["registry"]
            row = registered["artifact"]
            self.assertEqual(
                row["namespace"],
                derived_namespace(kind, scope()),
            )
            self.assertFalse(row["canonical_source"])
        summary = derived_data_summary(registry, trusted_context=scope())
        self.assertEqual(summary["state"], "CONFIRMED")
        self.assertEqual(summary["artifacts"], len(ARTIFACT_KINDS))
        self.assertFalse(summary["canonical_source"])
        self.assertTrue(summary["index_is_rebuildable_projection"])

    def test_registry_from_other_tenant_is_rejected_not_filtered(self):
        registry = default_derived_registry(scope("tenant-a"))
        registered = self._register(
            registry,
            kind="CACHE",
            ref="cache:1",
            trusted=scope("tenant-a"),
        )
        audit = validate_derived_registry(
            registered["registry"],
            trusted_context=scope("tenant-b"),
        )
        self.assertEqual(audit["state"], "BLOCK")
        self.assertIn("REGISTRY_SCOPE_MISMATCH", audit["blockers"])
        read = resolve_derived_artifact(
            registered["registry"],
            registered["artifact"]["artifact_id"],
            trusted_context=scope("tenant-b"),
        )
        self.assertEqual(read["state"], "BLOCK")

    def test_registry_digest_detects_metadata_tamper(self):
        registry = default_derived_registry(scope())
        registered = self._register(
            registry,
            kind="TRACE",
            ref="trace:1",
        )
        tampered = deepcopy(registered["registry"])
        tampered["artifacts"][0]["tenant_id"] = "tenant-b"
        audit = validate_derived_registry(tampered, trusted_context=scope())
        self.assertEqual(audit["state"], "BLOCK")
        self.assertIn("ARTIFACT_TENANT_MISMATCH", audit["blockers"])
        self.assertIn("REGISTRY_DIGEST_MISMATCH", audit["blockers"])

    def test_artifact_resolution_marks_changed_policy_as_stale(self):
        registry = default_derived_registry(scope())
        registered = self._register(
            registry,
            kind="CACHE",
            ref="cache:1",
        )
        aid = registered["artifact"]["artifact_id"]
        ready = resolve_derived_artifact(
            registered["registry"],
            aid,
            trusted_context=scope(),
            policy_version="policy-v1",
            data_version="data-v1",
            producer_version="producer-v1",
        )
        self.assertEqual(ready["state"], "READY")
        stale = resolve_derived_artifact(
            registered["registry"],
            aid,
            trusted_context=scope(),
            policy_version="policy-v2",
            data_version="data-v1",
            producer_version="producer-v1",
        )
        self.assertEqual(stale["state"], "STALE")
        self.assertIn("policy_version", stale["mismatches"])

    def test_deletion_tombstone_targets_all_registered_derived_data(self):
        registry = default_derived_registry(scope())
        for kind in ("CACHE", "INDEX", "LOG", "TRACE"):
            registry = self._register(
                registry,
                kind=kind,
                ref=f"{kind.lower()}:1",
            )["registry"]
        tomb = create_deletion_tombstone(
            registry,
            request_id="delete-1",
            trusted_context=scope(),
            created_at=NOW,
        )
        self.assertEqual(tomb["state"], "PENDING_DERIVED_PURGE")
        self.assertEqual(len(tomb["tombstone"]["target_artifact_ids"]), 4)
        self.assertFalse(tomb["tombstone"]["canonical_delete_executed"])
        self.assertFalse(tomb["tombstone"]["deletion_complete_claimed"])
        self.assertTrue(
            all(row["state"] == "PURGE_REQUIRED" for row in tomb["registry"]["artifacts"])
        )

    def test_backup_retention_blocks_deletion_completion_claim(self):
        registry = default_derived_registry(scope())
        backup = self._register(
            registry,
            kind="BACKUP",
            ref="backup:1",
            retention_until=(NOW + timedelta(days=30)).isoformat(),
        )
        tomb = create_deletion_tombstone(
            backup["registry"],
            request_id="delete-backup",
            trusted_context=scope(),
            created_at=NOW,
        )
        result = acknowledge_derived_purge(
            tomb["registry"],
            tomb["tombstone"]["tombstone_id"],
            backup["artifact"]["artifact_id"],
            trusted_context=scope(),
            purge_evidence_ref="audit:purge-requested",
            now=NOW + timedelta(days=1),
        )
        self.assertEqual(result["state"], "ERASURE_PENDING_RETENTION")
        self.assertEqual(
            result["artifact"]["state"],
            "ERASURE_PENDING_RETENTION",
        )
        self.assertFalse(result["deletion_complete_claimed"])
        self.assertFalse(result["tombstone"]["canonical_delete_executed"])

    def test_after_retention_derived_purge_can_confirm_but_not_claim_canonical_deletion(self):
        registry = default_derived_registry(scope())
        cache = self._register(registry, kind="CACHE", ref="cache:1")
        backup = self._register(
            cache["registry"],
            kind="BACKUP",
            ref="backup:1",
            retention_until=(NOW + timedelta(days=2)).isoformat(),
        )
        tomb = create_deletion_tombstone(
            backup["registry"],
            request_id="delete-2",
            trusted_context=scope(),
            created_at=NOW,
        )
        state = acknowledge_derived_purge(
            tomb["registry"],
            tomb["tombstone"]["tombstone_id"],
            cache["artifact"]["artifact_id"],
            trusted_context=scope(),
            purge_evidence_ref="audit:cache-purged",
            now=NOW + timedelta(hours=1),
        )
        self.assertEqual(state["state"], "PENDING_DERIVED_PURGE")
        state = acknowledge_derived_purge(
            state["registry"],
            state["tombstone"]["tombstone_id"],
            backup["artifact"]["artifact_id"],
            trusted_context=scope(),
            purge_evidence_ref="audit:backup-purged",
            now=NOW + timedelta(days=3),
        )
        self.assertEqual(state["state"], "DERIVED_PURGE_CONFIRMED")
        self.assertEqual(state["tombstone"]["pending_artifact_ids"], [])
        self.assertFalse(state["tombstone"]["canonical_delete_executed"])
        self.assertFalse(state["tombstone"]["deletion_complete_claimed"])

    def test_tombstone_is_idempotent_by_request_id(self):
        registry = default_derived_registry(scope())
        registered = self._register(
            registry,
            kind="CACHE",
            ref="cache:1",
        )
        first = create_deletion_tombstone(
            registered["registry"],
            request_id="delete-idempotent",
            trusted_context=scope(),
            created_at=NOW,
        )
        second = create_deletion_tombstone(
            first["registry"],
            request_id="delete-idempotent",
            trusted_context=scope(),
            created_at=NOW,
        )
        self.assertEqual(second["state"], "IDEMPOTENT")
        self.assertEqual(
            second["tombstone"]["tombstone_id"],
            first["tombstone"]["tombstone_id"],
        )
        self.assertEqual(len(second["registry"]["tombstones"]), 1)

    def test_registry_never_claims_production_encryption_or_tenant_kms(self):
        registry = default_derived_registry(scope())
        self.assertFalse(registry["production_encryption_claimed"])
        self.assertFalse(registry["tenant_key_management_implemented"])
        summary = derived_data_summary(registry, trusted_context=scope())
        self.assertFalse(summary["production_encryption_claimed"])
        self.assertFalse(summary["tenant_key_management_implemented"])


if __name__ == "__main__":
    unittest.main()
