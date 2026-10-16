"""A118 LAB RED: an inconsistent CLAIMED row is not clean pre-dispatch.

Only synthetic SQLite tampering; no producer, adapter call, Worker, network,
real receipt, effect or runtime deployment. This suite proves a local fence,
NOT independent H0/F1/T1/owner attestation.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc)


class ForbiddenAdapter:
    @property
    def send(self):
        raise AssertionError("A118_ADAPTER_DESCRIPTOR_MUST_NOT_BE_READ")


class A118ClaimedDispatchLocalEvidenceFence(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = SQLiteChatStore(Path(self.folder.name) / "a118.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("A118_OWNER", "A118_TENANT", "A118_WORKSPACE")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        item = self.outbox.enqueue(
            intent_ref="A118_SAFETY", action="SYNTHETIC_INERT",
            payload={"test_only": True}, aggregate_key="A118_AGGREGATE",
            policy_version="A118_POLICY", authorization_ref="A118_APPROVAL",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )
        self.key = item["idempotency_key"]
        self.worker = "A118_SAFE_WORKER"
        claimed = self.outbox.claim_next(
            self.worker, now=NOW + timedelta(seconds=1), lease_seconds=60
        )
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["state"], "CLAIMED")
        self.adapter = ForbiddenAdapter()

    def authorize(self, decision):
        return {
            "allowed": True, "actor_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "policy_version": decision["policy_version"],
            "authorization_ref": decision["authorization_ref"],
            "reauthenticated": True, "reauth_ref": decision["reauth_ref"],
        }

    def dispatch(self):
        return self.outbox.dispatch_claimed(
            self.key, worker_id=self.worker, authorize=self.authorize,
            adapter=self.adapter, now=NOW + timedelta(seconds=2)
        )

    def set_metadata(self, **values):
        self.assertTrue(values)
        allowed = {"dispatch_started_at", "sent_at", "confirmed_at", "effect_ref"}
        self.assertTrue(set(values).issubset(allowed))
        sql = ", ".join(name + "=?" for name in values)
        with self.outbox.db:
            self.outbox.db.execute(
                "UPDATE action_outbox SET " + sql + " WHERE idempotency_key=?",
                (*values.values(), self.key),
            )

    def insert_untrusted_effect(self):
        with self.outbox.db:
            self.outbox.db.execute(
                """INSERT INTO action_effects(
                    idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data
                ) VALUES (?,?,?,?,?,?,?)""",
                (self.key, self.scope.owner_id, self.scope.tenant_id,
                 self.scope.workspace_id, "A118_LOCALLY_FORGED_EFFECT",
                 NOW.isoformat(), "{}"),
            )

    def assert_denied_without_reclassification(self):
        before = self.outbox.get(self.key)
        self.assertEqual(before["state"], "CLAIMED")
        effects_before = self.outbox.effect_count()
        with self.assertRaisesRegex(
            TimeoutError, "claim/deadline changed before send; dispatch blocked"
        ):
            self.dispatch()
        self.assertEqual(self.outbox.get(self.key), before)
        self.assertEqual(self.outbox.effect_count(), effects_before)

    def test_01_claimed_with_dispatch_started_does_not_become_blocked_producer(self):
        self.set_metadata(dispatch_started_at=NOW.isoformat())
        self.assert_denied_without_reclassification()

    def test_02_claimed_with_sent_and_effect_metadata_does_not_erase_uncertainty(self):
        self.set_metadata(sent_at=NOW.isoformat(), effect_ref="A118_UNTRUSTED_REF")
        self.assert_denied_without_reclassification()

    def test_03_claimed_with_locally_forged_effect_ledger_cannot_downgrade(self):
        self.insert_untrusted_effect()
        self.assert_denied_without_reclassification()

    def test_04_clean_pre_dispatch_claim_still_blocks_without_adapter_access(self):
        before = self.outbox.get(self.key)
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED"
        ):
            self.dispatch()
        after = self.outbox.get(self.key)
        self.assertEqual(after["state"], "BLOCKED_PRODUCER")
        self.assertEqual(after["attempts"], before["attempts"])
        self.assertEqual(after["last_error"], "INDEPENDENT_PRODUCER_NOT_ENROLLED")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(after["dispatch_started_at"], "")
        self.assertEqual(after["sent_at"], "")
        self.assertEqual(after["confirmed_at"], "")
        self.assertEqual(after["effect_ref"], "")


if __name__ == "__main__":
    unittest.main()
