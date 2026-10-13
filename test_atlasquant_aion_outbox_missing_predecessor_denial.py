"""AION V16-A.45 — missing predecessor local Outbox/decision must not free FIFO.

These tests deliberately mutate only local SQLite. They prove neither an
external producer effect nor a signed, monotonic independent witness.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc)
SCOPE = Scope("a45-owner", "a45-tenant", "a45-workspace")


class MissingPredecessorFifoDenialTests(unittest.TestCase):
    def _enqueue(self, outbox, name, aggregate="a45-client"):
        return outbox.enqueue(
            intent_ref=name,
            action="create_crm_note",
            payload={"intent_ref": name, "test_only": True},
            aggregate_key=aggregate,
            policy_version="a45-policy",
            authorization_ref="a45-staging-only",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def _setup(self, raw):
        path = Path(raw) / "a45.sqlite3"
        store = SQLiteChatStore(path)
        outbox = ExecutionOutbox(store, SCOPE)
        first = self._enqueue(outbox, "a45-first")
        second = self._enqueue(outbox, "a45-second")
        self.assertEqual((first["aggregate_seq"], second["aggregate_seq"]), (1, 2))
        return store, outbox, path, first, second

    def _delete_first_outbox(self, outbox, first):
        with outbox.db:
            result = outbox.db.execute(
                "DELETE FROM action_outbox WHERE idempotency_key=?",
                (first["idempotency_key"],),
            )
            self.assertEqual(result.rowcount, 1)

    def _assert_second_blocked(self, outbox, second):
        self.assertIsNone(
            outbox.claim_next("a45-worker", now=NOW + timedelta(seconds=2))
        )
        remaining = outbox.get(second["idempotency_key"])
        self.assertEqual(remaining["state"], "PENDING")
        self.assertEqual(remaining["attempts"], 0)
        self.assertEqual(outbox.effect_count(), 0)

    def test_01_missing_predecessor_outbox_row_does_not_unblock_later_intent(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, _, first, second = self._setup(raw)
            try:
                self._delete_first_outbox(outbox, first)
                self.assertEqual(outbox.get(second["idempotency_key"])["aggregate_seq"], 2)
                self.assertEqual(
                    outbox.db.execute(
                        "SELECT count(*) FROM action_decisions WHERE decision_id=?",
                        (first["decision_id"],),
                    ).fetchone()[0], 1,
                )
                self._assert_second_blocked(outbox, second)
            finally:
                store.close()

    def test_02_missing_predecessor_outbox_and_decision_still_block_sequence_two(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, _, first, second = self._setup(raw)
            try:
                self._delete_first_outbox(outbox, first)
                with outbox.db:
                    result = outbox.db.execute(
                        "DELETE FROM action_decisions WHERE decision_id=?",
                        (first["decision_id"],),
                    )
                    self.assertEqual(result.rowcount, 1)
                self.assertEqual(
                    outbox.db.execute(
                        "SELECT count(*) FROM action_decisions WHERE aggregate_key=?",
                        ("a45-client",),
                    ).fetchone()[0], 1,
                )
                self._assert_second_blocked(outbox, second)
            finally:
                store.close()

    def test_03_missing_predecessor_remains_blocked_after_store_reopen(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, path, first, second = self._setup(raw)
            self._delete_first_outbox(outbox, first)
            store.close()
            reopened = SQLiteChatStore(path)
            try:
                recovered = ExecutionOutbox(reopened, SCOPE)
                self._assert_second_blocked(recovered, second)
            finally:
                reopened.close()

    def test_04_unrelated_aggregate_still_claims_after_predecessor_deletion(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, _, first, second = self._setup(raw)
            try:
                unrelated = self._enqueue(outbox, "a45-unrelated", "a45-other-client")
                self.assertEqual(unrelated["aggregate_seq"], 1)
                self._delete_first_outbox(outbox, first)
                claimed = outbox.claim_next("a45-worker", now=NOW + timedelta(seconds=2))
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed["idempotency_key"], unrelated["idempotency_key"])
                self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
                self.assertEqual(outbox.get(second["idempotency_key"])["attempts"], 0)
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_05_distinct_tenant_same_aggregate_is_independently_first(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, _, first, second = self._setup(raw)
            try:
                other_scope = Scope("a45-owner", "a45-other-tenant", "a45-workspace")
                independent = ExecutionOutbox(store, other_scope)
                other_first = self._enqueue(independent, "a45-tenant-other")
                self.assertEqual(other_first["aggregate_seq"], 1)
                self._delete_first_outbox(outbox, first)
                self._assert_second_blocked(outbox, second)
                claimed = independent.claim_next("other-worker", now=NOW + timedelta(seconds=3))
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed["idempotency_key"], other_first["idempotency_key"])
                self.assertEqual(outbox.effect_count(), 0)
                self.assertEqual(independent.effect_count(), 0)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
