"""LAB-only: candidate Outbox must reject mismatched SQLite decision metadata.

These are REAL SQLiteChatStore and ExecutionOutbox calls against disposable files.
Direct SQL corruption is intentional adversarial setup, NOT external provenance.
A passing suite is evidence of local coherence, NOT independent anti-rollback,
a provider receipt, owner enrollment or permission to execute effects.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

T0 = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
SCOPE = Scope("coherence-owner", "coherence-tenant", "coherence-space")


class RealOutboxDecisionCoherenceLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-outbox-decision-coherence-")
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "coherence.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)

    def add(self, ref="first", *, aggregate=None, created=T0,
            expires=T0 + timedelta(minutes=5)):
        return self.outbox.enqueue(
            intent_ref=ref, action="synthetic-not-executable",
            payload={"nonce": ref}, aggregate_key=aggregate or ref,
            policy_version="lab-v1", authorization_ref="non-authoritative",
            created_at=created, valid_until=expires,
        )

    def tamper(self, key: str, sql: str, args=()):
        with self.outbox.db:
            self.outbox.db.execute(sql, (*args, key))

    def raw_state(self, key):
        row = self.outbox.db.execute(
            "SELECT state,attempts,lease_owner,lease_until "
            "FROM action_outbox WHERE idempotency_key=?", (key,),
        ).fetchone()
        return tuple(row)

    def assert_pending(self, key):
        self.assertEqual(self.raw_state(key), ("PENDING", 0, "", ""))
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_01_expiry_column_forged_later_does_not_reclaim_expired_payload(self):
        key = self.add(expires=T0 + timedelta(seconds=30))["idempotency_key"]
        self.tamper(key, """UPDATE action_decisions SET valid_until=?
            WHERE decision_id=(SELECT decision_id FROM action_outbox WHERE idempotency_key=?)""",
            ((T0 + timedelta(minutes=4)).isoformat(),))
        self.assertIsNone(self.outbox.claim_next("lab-only", now=T0 + timedelta(minutes=1)))
        self.assert_pending(key)

    def test_02_creation_column_backdated_does_not_claim_future_decision(self):
        key = self.add(created=T0 + timedelta(minutes=2))["idempotency_key"]
        self.tamper(key, """UPDATE action_decisions SET created_at=?
            WHERE decision_id=(SELECT decision_id FROM action_outbox WHERE idempotency_key=?)""",
            ((T0 - timedelta(seconds=20)).isoformat(),))
        self.assertIsNone(self.outbox.claim_next("lab-only", now=T0))
        self.assert_pending(key)

    def test_03_swapped_decision_pointer_skips_poisoned_candidate(self):
        poisoned = self.add("old")["idempotency_key"]
        healthy = self.add("healthy")["idempotency_key"]
        self.tamper(poisoned, """UPDATE action_outbox SET decision_id=(
            SELECT decision_id FROM action_outbox WHERE idempotency_key=?
            ) WHERE idempotency_key=?""", (healthy,))
        result = self.outbox.claim_next("lab-only", now=T0 + timedelta(seconds=10))
        self.assertIsNotNone(result)
        self.assertEqual(result["idempotency_key"], healthy)
        self.assert_pending(poisoned)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_04_manually_downgraded_aggregate_ordinal_is_not_first(self):
        a = self.add("ordinal-one", aggregate="same")
        b = self.add("ordinal-two", aggregate="same")
        self.assertEqual(b["aggregate_seq"], 2)
        with self.outbox.db:
            self.outbox.db.execute("DELETE FROM action_outbox WHERE idempotency_key=?",
                                   (a["idempotency_key"],))
            self.outbox.db.execute("DELETE FROM action_decisions WHERE decision_id=?",
                                   (a["decision_id"],))
            self.outbox.db.execute("UPDATE action_decisions SET aggregate_seq=1 "
                                   "WHERE decision_id=?", (b["decision_id"],))
        self.assertIsNone(self.outbox.claim_next("lab-only", now=T0 + timedelta(seconds=5)))
        self.assert_pending(b["idempotency_key"])

    def test_05_decision_owner_column_must_match_envelope_and_outbox(self):
        key = self.add()["idempotency_key"]
        self.tamper(key, """UPDATE action_decisions SET owner=?
            WHERE decision_id=(SELECT decision_id FROM action_outbox WHERE idempotency_key=?)""",
            ("forged-other-owner",))
        self.assertIsNone(self.outbox.claim_next("lab-only", now=T0 + timedelta(seconds=1)))
        self.assert_pending(key)

    def test_06_invalid_json_does_not_claim_then_throw_after_commit(self):
        key = self.add()["idempotency_key"]
        self.tamper(key, """UPDATE action_decisions SET data=?
            WHERE decision_id=(SELECT decision_id FROM action_outbox WHERE idempotency_key=?)""",
            ("{malformed",))
        self.assertIsNone(self.outbox.claim_next("lab-only", now=T0 + timedelta(seconds=1)))
        self.assert_pending(key)

    def test_07_forged_json_scope_cannot_claim_even_if_sql_columns_match(self):
        key = self.add()["idempotency_key"]
        with self.outbox.db:
            row = self.outbox.db.execute(
                """SELECT d.data FROM action_decisions d
                   JOIN action_outbox o ON o.decision_id=d.decision_id
                   WHERE o.idempotency_key=?""", (key,),
            ).fetchone()
            claim = json.loads(row[0])
            claim["tenant_id"] = "forged-other-tenant"
            self.outbox.db.execute(
                """UPDATE action_decisions SET data=?
                   WHERE decision_id=(SELECT decision_id FROM action_outbox
                                      WHERE idempotency_key=?)""",
                (json.dumps(claim, sort_keys=True), key),
            )
        self.assertIsNone(self.outbox.claim_next("lab-only", now=T0 + timedelta(seconds=1)))
        self.assert_pending(key)

    def test_08_clean_first_intent_remains_locally_claimable(self):
        key = self.add()["idempotency_key"]
        result = self.outbox.claim_next("lab-only", now=T0 + timedelta(seconds=1))
        self.assertEqual(result["idempotency_key"], key)
        self.assertEqual(result["decision"]["idempotency_key"], key)
        self.assertEqual(result["state"], "CLAIMED")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
