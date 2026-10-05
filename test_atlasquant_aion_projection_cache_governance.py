from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_aion_projection_governance import (
    delete_source_projection,
    empty_projection,
    rebuild_projection,
    validate_projection_hit,
)
from atlasquant_aion_scoped_cache import (
    cache_get,
    cache_put,
    empty_cache,
    invalidate_scope,
    invalidate_sources,
)
from atlasquant_aion_library_foundation import ingest_document, review_document
from atlasquant_aion_library_index import (
    delete_document_projection,
    empty_library_index,
    index_document,
    search_library_index,
)

NOW = datetime(2026, 10, 5, 6, 30, tzinfo=timezone.utc)


def scope(tenant="tenant-a", workspace="workspace-a"):
    return {"tenant_id": tenant, "workspace_id": workspace, "role": "ADMIN"}


def source(
    *,
    source_id="memory-1",
    tenant="tenant-a",
    workspace="workspace-a",
    version="v1",
    digest="sha256:source-v1",
    state="PROMOTED",
    truth="CONFIRMED",
    taint=None,
    text="Payroll cresceu 100 mil vagas.",
):
    return {
        "source_id": source_id,
        "tenant_id": tenant,
        "workspace_id": workspace,
        "source_version": version,
        "content_digest": digest,
        "canonical_state": state,
        "truth_state": truth,
        "provenance_refs": ["source:primary:payroll"],
        "taint_labels": list(taint or []),
        "chunks": [{"text": text, "source_content_digest": digest}],
    }


def reviewed_document(tenant="tenant-a", workspace="workspace-a"):
    base = ingest_document(
        tenant_id=tenant,
        workspace_id=workspace,
        title="Manual Payroll",
        source_reference="file://payroll.pdf",
        checksum="sha256:payroll",
        source_type="INTERNAL_DOCUMENT",
        evidence_refs=["EV-PAYROLL"],
    )["record"]
    return review_document(
        base,
        trusted_context={
            "tenant_id": tenant,
            "workspace_id": workspace,
            "role": "ADMIN",
            "review_approved": True,
        },
        decision="VALIDATED",
        evidence_refs=["EV-PAYROLL"],
        reason="reviewed",
    )["record"]


class ProjectionGovernanceTests(unittest.TestCase):
    def test_rebuild_creates_projection_not_canonical_truth(self):
        projection = rebuild_projection(
            [source()],
            trusted_context=scope(),
            projection_version="pv1",
        )
        self.assertTrue(projection["projection_only"])
        self.assertFalse(projection["canonical_source"])
        self.assertTrue(projection["rebuildable"])
        self.assertTrue(projection["retrieval_does_not_validate"])
        self.assertFalse(projection["vector_provider_connected"])
        self.assertEqual(len(projection["sources"]), 1)
        self.assertEqual(len(projection["chunks"]), 1)

    def test_cross_tenant_canonical_source_is_rejected(self):
        with self.assertRaises(PermissionError):
            rebuild_projection(
                [source(tenant="tenant-b")],
                trusted_context=scope(),
                projection_version="pv1",
            )

    def test_promoted_source_with_unresolved_taint_cannot_enter_projection(self):
        with self.assertRaisesRegex(ValueError, "unresolved taint"):
            rebuild_projection(
                [source(taint=["UNTRUSTED_EXTERNAL_SOURCE"])],
                trusted_context=scope(),
                projection_version="pv1",
            )

    def test_chunk_must_bind_exact_source_digest(self):
        broken = source()
        broken["chunks"][0]["source_content_digest"] = "sha256:old"
        with self.assertRaisesRegex(ValueError, "chunk source digest mismatch"):
            rebuild_projection(
                [broken],
                trusted_context=scope(),
                projection_version="pv1",
            )

    def test_retrieval_hit_must_rebind_to_current_canonical_source(self):
        canonical = source()
        projection = rebuild_projection(
            [canonical],
            trusted_context=scope(),
            projection_version="pv1",
        )
        hit = projection["chunks"][0]

        current = validate_projection_hit(
            hit,
            trusted_context=scope(),
            canonical_resolver=lambda source_id: canonical,
        )
        self.assertEqual(current["state"], "BOUND_CURRENT")
        self.assertTrue(current["usable_as_evidence"])
        self.assertTrue(current["usable_as_confirmed_fact"])
        self.assertFalse(current["ranking_elevates_confidence"])

        changed = source(version="v2", digest="sha256:source-v2")
        stale = validate_projection_hit(
            hit,
            trusted_context=scope(),
            canonical_resolver=lambda source_id: changed,
        )
        self.assertEqual(stale["state"], "BLOCK_STALE_PROJECTION")
        self.assertIn("SOURCE_VERSION_CHANGED", stale["blockers"])
        self.assertIn("SOURCE_DIGEST_CHANGED", stale["blockers"])
        self.assertFalse(stale["usable_as_evidence"])

    def test_deleted_canonical_source_makes_old_projection_hit_unusable(self):
        projection = rebuild_projection(
            [source()],
            trusted_context=scope(),
            projection_version="pv1",
        )
        hit = projection["chunks"][0]
        result = validate_projection_hit(
            hit,
            trusted_context=scope(),
            canonical_resolver=lambda source_id: None,
        )
        self.assertEqual(result["state"], "BLOCK_STALE_PROJECTION")
        self.assertIn("CANONICAL_SOURCE_MISSING", result["blockers"])

    def test_projection_delete_removes_all_source_chunks(self):
        projection = rebuild_projection(
            [
                source(source_id="a"),
                source(
                    source_id="b",
                    digest="sha256:b",
                    text="Second canonical source.",
                ),
            ],
            trusted_context=scope(),
            projection_version="pv1",
        )
        deleted = delete_source_projection(
            projection,
            "a",
            trusted_context=scope(),
        )
        self.assertEqual(deleted["deletion"]["removed_sources"], 1)
        self.assertEqual(deleted["deletion"]["removed_chunks"], 1)
        self.assertEqual([row["source_id"] for row in deleted["sources"]], ["b"])

    def test_library_index_is_explicit_projection_and_supports_deletion(self):
        doc = reviewed_document()
        indexed = index_document(
            empty_library_index(),
            doc,
            passages=["Payroll passage one.", "Payroll passage two."],
            trusted_context=scope(),
        )["index"]
        self.assertTrue(indexed["projection_only"])
        result = search_library_index(
            indexed,
            "payroll",
            trusted_context=scope(),
        )
        self.assertTrue(result["hits"][0]["projection_only"])
        self.assertTrue(result["hits"][0]["retrieval_does_not_validate"])
        self.assertFalse(result["hits"][0]["ranking_elevates_confidence"])

        deleted = delete_document_projection(
            indexed,
            doc["document_id"],
            trusted_context=scope(),
        )
        self.assertEqual(deleted["status"], "DELETED_FROM_PROJECTION")
        self.assertEqual(deleted["removed_documents"], 1)
        self.assertEqual(deleted["removed_passages"], 2)
        self.assertEqual(deleted["index"]["documents"], [])
        self.assertEqual(deleted["index"]["passages"], [])

    def test_cross_scope_library_projection_delete_is_blocked(self):
        doc = reviewed_document()
        indexed = index_document(
            empty_library_index(),
            doc,
            passages=["Payroll passage."],
            trusted_context=scope(),
        )["index"]
        blocked = delete_document_projection(
            indexed,
            doc["document_id"],
            trusted_context=scope("tenant-b", "workspace-b"),
        )
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("SCOPE_MISMATCH", blocked["blockers"])


class ScopedCacheTests(unittest.TestCase):
    def _put(self, cache=None, **kwargs):
        return cache_put(
            cache or empty_cache(),
            query=kwargs.get("query", "payroll outlook"),
            value=kwargs.get("value", "cached result"),
            cache_class=kwargs.get("cache_class", "RETRIEVAL"),
            policy_version=kwargs.get("policy_version", "policy-v1"),
            data_version=kwargs.get("data_version", "data-v1"),
            source_refs=kwargs.get("source_refs", ["source:a"]),
            requested_ttl_seconds=kwargs.get("ttl", 300),
            source_valid_until=kwargs.get(
                "source_valid_until",
                NOW + timedelta(minutes=10),
            ),
            trusted_context=kwargs.get("trusted_context", scope()),
            now=kwargs.get("now", NOW),
        )

    def test_cache_key_binds_tenant_workspace_policy_and_data_version(self):
        put = self._put()
        cache = put["cache"]
        hit = cache_get(
            cache,
            query="payroll outlook",
            cache_class="RETRIEVAL",
            policy_version="policy-v1",
            data_version="data-v1",
            trusted_context=scope(),
            now=NOW + timedelta(seconds=1),
        )
        self.assertTrue(hit["hit"])

        for context, policy, data in [
            (scope("tenant-b", "workspace-a"), "policy-v1", "data-v1"),
            (scope(), "policy-v2", "data-v1"),
            (scope(), "policy-v1", "data-v2"),
        ]:
            miss = cache_get(
                cache,
                query="payroll outlook",
                cache_class="RETRIEVAL",
                policy_version=policy,
                data_version=data,
                trusted_context=context,
                now=NOW + timedelta(seconds=1),
            )
            self.assertFalse(miss["hit"])

    def test_ttl_never_outlives_source_validity(self):
        put = self._put(
            ttl=3600,
            source_valid_until=NOW + timedelta(seconds=45),
        )
        self.assertEqual(put["ttl_seconds"], 45)
        expired = cache_get(
            put["cache"],
            query="payroll outlook",
            cache_class="RETRIEVAL",
            policy_version="policy-v1",
            data_version="data-v1",
            trusted_context=scope(),
            now=NOW + timedelta(seconds=46),
        )
        self.assertFalse(expired["hit"])
        self.assertEqual(expired["reason"], "EXPIRED")

    def test_live_authority_secret_payment_and_trading_classes_never_cache(self):
        for cls in (
            "LIVE_MARKET",
            "AUTHORITY",
            "CREDENTIAL",
            "SECRET",
            "PAYMENT",
            "TRADING_EXECUTION",
            "PERSONAL_DATA_SENSITIVE",
        ):
            with self.subTest(cache_class=cls):
                result = self._put(cache_class=cls)
                self.assertFalse(result["cached"])
                self.assertEqual(result["reason"], "CACHE_CLASS_FORBIDDEN")
                self.assertEqual(result["cache"]["entries"], {})

    def test_secret_like_value_is_not_cached(self):
        synthetic = "token=" + "s" + "k-" + "synthetic-cache-secret"
        result = self._put(value=synthetic)
        self.assertFalse(result["cached"])
        self.assertEqual(result["reason"], "SECRET_LIKE_VALUE")

    def test_source_event_invalidation_removes_only_same_scope_dependencies(self):
        first = self._put(query="q1", source_refs=["source:a"])
        second = self._put(
            first["cache"],
            query="q2",
            source_refs=["source:b"],
        )
        third = self._put(
            second["cache"],
            query="q3",
            source_refs=["source:a"],
            trusted_context=scope("tenant-b", "workspace-b"),
        )
        invalidated = invalidate_sources(
            third["cache"],
            ["source:a"],
            trusted_context=scope(),
        )
        self.assertEqual(invalidated["removed"], 1)
        entries = list(invalidated["cache"]["entries"].values())
        self.assertEqual(len(entries), 2)
        self.assertTrue(any(row["tenant_id"] == "tenant-b" for row in entries))
        self.assertTrue(any(row["source_refs"] == ["source:b"] for row in entries))

    def test_scope_invalidation_cannot_flush_other_tenant(self):
        first = self._put(query="a")
        second = self._put(
            first["cache"],
            query="b",
            trusted_context=scope("tenant-b", "workspace-b"),
        )
        result = invalidate_scope(
            second["cache"],
            trusted_context=scope(),
        )
        self.assertEqual(result["removed"], 1)
        remaining = list(result["cache"]["entries"].values())
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["tenant_id"], "tenant-b")

    def test_cache_declares_provider_prompt_cache_untrusted(self):
        state = empty_cache()
        self.assertFalse(state["provider_prompt_cache_trusted"])
        self.assertFalse(state["cross_tenant_sharing"])
        self.assertFalse(state["canonical_source"])


if __name__ == "__main__":
    unittest.main()
