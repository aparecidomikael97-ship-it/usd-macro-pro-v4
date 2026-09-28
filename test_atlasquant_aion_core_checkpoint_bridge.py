import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_core_checkpoint_bridge import (
    AuthenticatedSessionApprovalAdapter,
    CheckpointCoreStore,
    attach_store_to_checkpoint,
    checkpoint_memory_snapshot,
    load_checkpoint_store,
    stage_user_approved_memory,
)
from atlasquant_aion_core_intelligence.adapters import CHECKPOINT_NAMESPACE
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import Origin
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_memory import (
    checkpoint_source_digest,
    ensure_operating_checkpoint,
)


NOW = datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc)


def _access(username="mikael", role="ADMIN", fingerprint="abc123def456"):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": role,
        "session": {
            "username": username,
            "role": role,
            "credential_fingerprint": fingerprint,
            "permissions": (
                ["app:read", "admin:read", "aion:admin"]
                if role == "ADMIN"
                else ["app:read"]
            ),
            "authenticated_at": 10,
            "last_seen": 10,
        },
    }


class CheckpointCoreStoreTests(unittest.TestCase):
    def test_empty_checkpoint_creates_isolated_empty_store(self):
        ctx = authenticated_context(_access(), Domain.ADMIN)
        store, state = load_checkpoint_store(ctx, {})
        self.assertEqual(state["state"], "EMPTY")
        self.assertEqual(store.revision(ctx), 0)
        self.assertEqual(store.read(ctx, NOW), [])

    def test_bundle_round_trip_preserves_records_approvals_events_and_digest(self):
        access = _access()
        result = stage_user_approved_memory(
            access,
            {},
            kind="DECISION",
            text="Manter a Central AION como porta administrativa.",
            confirmation=True,
            now=NOW,
        )
        ctx = authenticated_context(access, Domain.ADMIN)
        store, state = load_checkpoint_store(ctx, result["checkpoint"])
        self.assertEqual(state["state"], "CONNECTED")
        self.assertEqual(store.revision(ctx), 1)
        rows = store.read(ctx, NOW)
        self.assertEqual(rows[0]["origin"], "USER_APPROVED")
        bundle = store.checkpoint(ctx, NOW)
        self.assertTrue(bundle["digest"])
        self.assertGreaterEqual(len(bundle["approvals"]), 1)
        self.assertGreaterEqual(len(bundle["events"]), 1)

    def test_tampered_bundle_fails_closed(self):
        result = stage_user_approved_memory(
            _access(), {}, kind="PRIORITY", text="Validar memória.", confirmation=True, now=NOW
        )
        tampered = deepcopy(result["checkpoint"])
        tampered[CHECKPOINT_NAMESPACE]["records"][0]["text"] = "alterado fora do contrato"
        ctx = authenticated_context(_access(), Domain.ADMIN)
        with self.assertRaisesRegex(ValueError, "DIGEST_MISMATCH"):
            load_checkpoint_store(ctx, tampered)

    def test_cross_actor_context_does_not_leak_memory(self):
        result = stage_user_approved_memory(
            _access(), {}, kind="DECISION", text="Decisão privada.", confirmation=True, now=NOW
        )
        other = _access(username="outro", fingerprint="fff999eee888")
        snapshot = checkpoint_memory_snapshot(other, result["checkpoint"], now=NOW)
        self.assertEqual(snapshot["state"], "CONTEXT_ISOLATED")
        self.assertEqual(snapshot["records"], [])
        with self.assertRaisesRegex(ValueError, "CONTEXT_MISMATCH"):
            stage_user_approved_memory(
                other,
                result["checkpoint"],
                kind="DECISION",
                text="Não deve sobrescrever.",
                confirmation=True,
                now=NOW,
            )

    def test_explicit_human_confirmation_is_required(self):
        result = stage_user_approved_memory(
            _access(),
            {},
            kind="DECISION",
            text="Não registrar sem confirmação.",
            confirmation=False,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn(CHECKPOINT_NAMESPACE, result["checkpoint"])

    def test_non_admin_cannot_stage_approved_memory(self):
        with self.assertRaises(ValueError):
            stage_user_approved_memory(
                _access(role="USER"),
                {},
                kind="DECISION",
                text="Não permitido.",
                confirmation=True,
                now=NOW,
            )

    def test_receipt_is_bound_and_one_shot(self):
        access = _access()
        ctx = authenticated_context(access, Domain.ADMIN)
        adapter = AuthenticatedSessionApprovalAdapter(access)
        receipt = adapter.issue(
            context=ctx,
            approval_id="approval-1",
            subject_digest="subject-1",
            action="MEMORY_DECISION",
            decision="APPROVED",
        )
        principal = adapter.verify(
            context=ctx,
            approval_id="approval-1",
            subject_digest="subject-1",
            action="MEMORY_DECISION",
            decision="APPROVED",
            receipt=receipt,
        )
        self.assertEqual(principal, "mikael")
        self.assertIsNone(adapter.verify(
            context=ctx,
            approval_id="approval-1",
            subject_digest="subject-1",
            action="MEMORY_DECISION",
            decision="APPROVED",
            receipt=receipt,
        ))

    def test_user_approved_record_is_not_execution_authority(self):
        result = stage_user_approved_memory(
            _access(),
            {},
            kind="DECISION",
            text="Decisão humana registrada.",
            confirmation=True,
            now=NOW,
        )
        self.assertEqual(result["status"], "STAGED")
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["external_persisted"])
        self.assertTrue(result["requires_checkpoint_save"])
        self.assertFalse(result["approval"]["execution_authorized"])

    def test_checkpoint_normalization_preserves_core_namespace(self):
        result = stage_user_approved_memory(
            _access(), {}, kind="REQUIREMENT", text="Preservar escopo.", confirmation=True, now=NOW
        )
        normalized = ensure_operating_checkpoint(result["checkpoint"])
        self.assertIn(CHECKPOINT_NAMESPACE, normalized)
        self.assertEqual(
            normalized[CHECKPOINT_NAMESPACE]["records"][0]["text"],
            "Preservar escopo.",
        )

    def test_core_namespace_changes_conflict_digest(self):
        base = ensure_operating_checkpoint({})
        before = checkpoint_source_digest(base)
        result = stage_user_approved_memory(
            _access(), base, kind="PRIORITY", text="Prioridade nova.", confirmation=True, now=NOW
        )
        after = checkpoint_source_digest(result["checkpoint"])
        self.assertNotEqual(before, after)

    def test_existing_checkpoint_history_therefore_carries_core_namespace(self):
        result = stage_user_approved_memory(
            _access(), {}, kind="PENDING_TASK", text="Revalidar bridge.", confirmation=True, now=NOW
        )
        candidate = ensure_operating_checkpoint(result["checkpoint"])
        restored = ensure_operating_checkpoint(deepcopy(candidate))
        self.assertEqual(
            restored[CHECKPOINT_NAMESPACE]["digest"],
            candidate[CHECKPOINT_NAMESPACE]["digest"],
        )

    def test_snapshot_reports_user_approved_decisions_only(self):
        first = stage_user_approved_memory(
            _access(), {}, kind="DECISION", text="Decisão A.", confirmation=True, now=NOW
        )
        second = stage_user_approved_memory(
            _access(), first["checkpoint"], kind="REQUIREMENT", text="Requisito B.", confirmation=True, now=NOW
        )
        snap = checkpoint_memory_snapshot(_access(), second["checkpoint"], now=NOW)
        self.assertEqual(len(snap["records"]), 2)
        self.assertEqual(len(snap["approved_decisions"]), 1)
        self.assertEqual(snap["approved_decisions"][0]["text"], "Decisão A.")

    def test_no_network_or_automatic_checkpoint_save_in_bridge(self):
        source = Path("atlasquant_aion_core_checkpoint_bridge.py").read_text(encoding="utf-8")
        for banned in (
            "import requests",
            "requests.",
            "save_runtime_checkpoint(",
            "restore_checkpoint_revision(",
            "subprocess",
            "urlopen",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
