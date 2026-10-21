"""P0/H0 real SQLite Outbox cross-scope JOIN integrity regression (LAB).

RED-FIRST contract. If a local outbox row's decision_id is retargeted to
another owner's / tenant's / workspace's valid action_decisions primary key,
read-only get/list MUST NOT return that foreign decision payload or metadata.
Reads must fail closed, without changing the SQLite database, action_effects,
leases, claims, producer gates, or main. This does not prove external trust or
detect whole-database rollback.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,21,14,0,0,tzinfo=timezone.utc)
A=Scope("owner-alpha","tenant-alpha","workspace-alpha")
SCOPE_VARIANTS=(
    ("owner",Scope("owner-beta","tenant-alpha","workspace-alpha")),
    ("tenant",Scope("owner-alpha","tenant-beta","workspace-alpha")),
    ("workspace",Scope("owner-alpha","tenant-alpha","workspace-beta")),
)


class P0OutboxCrossScopeJoinFenceLab(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="aion-h0-cross-scope-join-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"scope-join.sqlite3")
        self.addCleanup(self.store.close)
        self.own=ExecutionOutbox(self.store,A)

    def enqueue(self,outbox,name):
        return outbox.enqueue(
            intent_ref="intent-"+name,
            action="LAB_NO_PROVIDER",
            payload={"notice":"payload-for-"+name,"test_only":True},
            aggregate_key="aggregate-"+name,
            policy_version="policy-lab",
            authorization_ref="authorization-not-real",
            created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
        )

    def _poison(self,variant):
        other=ExecutionOutbox(self.store,variant)
        own=self.enqueue(self.own,"alpha")
        foreign=self.enqueue(other,"beta")
        self.assertNotEqual(own["idempotency_key"],foreign["idempotency_key"])
        self.assertNotEqual(own["decision_id"],foreign["decision_id"])
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET decision_id=? WHERE idempotency_key=?",
                (foreign["decision_id"],own["idempotency_key"]),
            )
        return own,foreign,other

    def test_01_owner_scope_swap_get_does_not_leak_foreign_decision(self):
        own,_,_=self._poison(SCOPE_VARIANTS[0][1])
        with self.assertRaises(LookupError):
            self.own.get(own["idempotency_key"])

    def test_02_owner_scope_swap_list_does_not_leak_foreign_decision(self):
        self._poison(SCOPE_VARIANTS[0][1])
        self.assertEqual(self.own.list(),[])

    def test_03_tenant_scope_swap_get_does_not_leak_foreign_decision(self):
        own,_,_=self._poison(SCOPE_VARIANTS[1][1])
        with self.assertRaises(LookupError):
            self.own.get(own["idempotency_key"])

    def test_04_tenant_scope_swap_list_does_not_leak_foreign_decision(self):
        self._poison(SCOPE_VARIANTS[1][1])
        self.assertEqual(self.own.list(),[])

    def test_05_workspace_scope_swap_get_does_not_leak_foreign_decision(self):
        own,_,_=self._poison(SCOPE_VARIANTS[2][1])
        with self.assertRaises(LookupError):
            self.own.get(own["idempotency_key"])

    def test_06_workspace_scope_swap_list_does_not_leak_foreign_decision(self):
        self._poison(SCOPE_VARIANTS[2][1])
        self.assertEqual(self.own.list(),[])

    def test_07_filtered_state_list_also_must_not_leak(self):
        self._poison(SCOPE_VARIANTS[1][1])
        self.assertEqual(self.own.list(state="PENDING"),[])

    def test_08_foreign_own_row_remains_visible_only_to_own_scope(self):
        own,foreign,other=self._poison(SCOPE_VARIANTS[1][1])
        self.assertEqual(other.get(foreign["idempotency_key"])["decision"]["payload"]["notice"],"payload-for-beta")
        self.assertEqual(len(other.list()),1)
        with self.assertRaises(LookupError):
            self.own.get(own["idempotency_key"])

    def test_09_normal_scope_read_and_list_are_preserved(self):
        own=self.enqueue(self.own,"alpha")
        self.assertEqual(self.own.get(own["idempotency_key"])["decision"]["payload"]["notice"],"payload-for-alpha")
        self.assertEqual([item["idempotency_key"] for item in self.own.list()],[own["idempotency_key"]])
        self.assertEqual(len(self.own.list(state="PENDING")),1)

    def test_10_read_rejection_has_zero_sqlite_side_effects(self):
        own,foreign,_=self._poison(SCOPE_VARIANTS[0][1])
        before=tuple(self.store.db.iterdump())
        with self.assertRaises(LookupError):
            self.own.get(own["idempotency_key"])
        self.assertEqual(self.own.list(),[])
        self.assertEqual(before,tuple(self.store.db.iterdump()))
        self.assertEqual(self.own.effect_count(),0)

    def test_11_poisoned_pending_row_cannot_claim_or_dispatch(self):
        own,_,_=self._poison(SCOPE_VARIANTS[1][1])
        before=tuple(self.store.db.iterdump())
        self.assertIsNone(self.own.claim_next("lab-worker",now=NOW))
        self.assertEqual(self.own.effect_count(),0)
        # claim_next is permitted to perform its own clean-up transaction,
        # but cannot rewrite the forged cross-scope row or invoke provider.
        raw=self.store.db.execute(
            "SELECT state,attempts FROM action_outbox WHERE idempotency_key=?",
            (own["idempotency_key"],),
        ).fetchone()
        self.assertEqual(tuple(raw),("PENDING",0))
        self.assertEqual(tuple(self.store.db.iterdump()),before)


if __name__=="__main__":
    unittest.main()
