"""G54 synthetic SQLite: inconsistent preexisting effects must not be adopted.

This file contains no external provider, network, financial effect or real identity.
The tests intentionally precede any candidate implementation change.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 25, 19, tzinfo=timezone.utc)
SCOPE = Scope("g54-owner", "g54-tenant", "g54-space")
WORKER = "g54-local-worker"
EFFECT = "local-synthetic-reference"


class G54FencedLedgerConsistency(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="g54-local-")
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "synthetic.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.base = ExecutionOutbox(self.store, SCOPE)
        self.key = self.base.enqueue(
            intent_ref="g54-synthetic", action="no_external_adapter",
            payload={"amount_minor": 10}, aggregate_key="g54-group",
            policy_version="p1", authorization_ref="g54-local-auth",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )["idempotency_key"]
        self.transition_to_uncertain()

    def transition_to_uncertain(self):
        self.store.db.execute(
            """UPDATE action_outbox SET state='UNCERTAIN',
                      attempts=1,lease_owner=?,lease_until=?
                WHERE idempotency_key=?""",
            (WORKER,(NOW + timedelta(minutes=2)).isoformat(),self.key),
        )
        self.store.db.commit()

    def scoped_ledger(self):
        return self.store.db.execute(
            """SELECT effect_ref,confirmed_at,data FROM action_effects
               WHERE owner=? AND tenant=? AND workspace=? AND idempotency_key=?""",
            (*self.scope(),self.key),
        ).fetchall()

    def scope(self):
        return (SCOPE.owner_id, SCOPE.tenant_id, SCOPE.workspace_id)

    def poison_ledger(self, ref=EFFECT, at=None):
        self.store.db.execute(
            """INSERT INTO action_effects
               (idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data)
               VALUES (?,?,?,?,?,?,?)""",
            (self.key,*self.scope(),ref,
             (at or NOW - timedelta(hours=2)).isoformat(),
             '{"lab":"contradictory-orphan"}'),
        )
        self.store.db.commit()

    def snapshot(self):
        return self.base._g42_reconcile_snapshot_lab(self.base.get(self.key))

    def confirm(self, **kwargs):
        return self.base._confirm(
            self.key, effect_ref=EFFECT,
            confirmed_at=NOW+timedelta(minutes=1),
            result={"source":"synthetic-g54"},
            **kwargs,
        )

    def assert_unchanged(self, before_row, before_ledger):
        self.assertEqual(self.base.get(self.key),before_row)
        self.assertEqual([tuple(x) for x in self.scoped_ledger()],before_ledger)
        self.assertFalse(self.store.db.in_transaction)

    def test_01_clean_direct_confirmation_still_allowed(self):
        got=self.confirm()
        self.assertEqual(got["state"],"CONFIRMED")
        self.assertEqual(len(self.scoped_ledger()),1)

    def test_02_clean_fenced_confirmation_still_allowed(self):
        got=self.confirm(fence_lab=(WORKER,1))
        self.assertEqual(got["state"],"CONFIRMED")
        self.assertEqual(len(self.scoped_ledger()),1)
        print("G54_FENCE_NORMAL_GREEN=ONE_LOCAL_EFFECT")

    def test_03_clean_snapshot_confirmation_still_allowed(self):
        got=self.confirm(reconcile_snapshot_lab=self.snapshot())
        self.assertEqual(got["state"],"CONFIRMED")
        self.assertEqual(len(self.scoped_ledger()),1)
        print("G54_SNAPSHOT_NORMAL_GREEN=ONE_LOCAL_EFFECT")

    def test_04_direct_poison_same_ref_remains_denied(self):
        self.poison_ledger()
        before_row=self.base.get(self.key)
        before_ledger=[tuple(x) for x in self.scoped_ledger()]
        with self.assertRaisesRegex(RuntimeError,"G53_NONCONFIRMED_HAS_EFFECT_DENY"):
            self.confirm()
        self.assert_unchanged(before_row,before_ledger)

    def test_05_fenced_poison_same_ref_does_not_adopt_old_effect(self):
        self.poison_ledger()
        before_row=self.base.get(self.key)
        before_ledger=[tuple(x) for x in self.scoped_ledger()]
        with self.assertRaisesRegex(RuntimeError,"G54_NONCONFIRMED_LEDGER_INCONSISTENT_DENY"):
            self.confirm(fence_lab=(WORKER,1))
        self.assert_unchanged(before_row,before_ledger)
        print("G54_FENCED_ORPHAN_GREEN=NO_ADOPTED_LEDGER")

    def test_06_snapshot_poison_same_ref_does_not_adopt_old_effect(self):
        self.poison_ledger()
        before_row=self.base.get(self.key)
        before_ledger=[tuple(x) for x in self.scoped_ledger()]
        with self.assertRaisesRegex(RuntimeError,"G54_NONCONFIRMED_LEDGER_INCONSISTENT_DENY"):
            self.confirm(reconcile_snapshot_lab=self.snapshot())
        self.assert_unchanged(before_row,before_ledger)
        print("G54_SNAPSHOT_ORPHAN_GREEN=NO_ADOPTED_LEDGER")

    def test_07_fenced_poison_different_ref_preserves_collision_contract(self):
        self.poison_ledger(ref="another-synthetic-effect")
        before_row=self.base.get(self.key)
        before_ledger=[tuple(x) for x in self.scoped_ledger()]
        with self.assertRaisesRegex(ValueError,"effect ledger idempotency collision"):
            self.confirm(fence_lab=(WORKER,1))
        self.assert_unchanged(before_row,before_ledger)

    def test_08_snapshot_poison_different_ref_preserves_collision_contract(self):
        self.poison_ledger(ref="another-synthetic-effect")
        before_row=self.base.get(self.key)
        before_ledger=[tuple(x) for x in self.scoped_ledger()]
        with self.assertRaisesRegex(ValueError,"effect ledger idempotency collision"):
            self.confirm(reconcile_snapshot_lab=self.snapshot())
        self.assert_unchanged(before_row,before_ledger)

    def test_09_direct_revoked_without_ledger_stays_terminal(self):
        self.store.db.execute(
            "UPDATE action_outbox SET state='REVOKED' WHERE idempotency_key=?",
            (self.key,),
        )
        self.store.db.commit()
        before=self.base.get(self.key)
        with self.assertRaisesRegex(RuntimeError,"G42_UNSAFE_PRECONFIRM_PHASE_DENY"):
            self.confirm()
        self.assertEqual(self.base.get(self.key),before)
        self.assertEqual(len(self.scoped_ledger()),0)


if __name__ == "__main__":
    unittest.main()
