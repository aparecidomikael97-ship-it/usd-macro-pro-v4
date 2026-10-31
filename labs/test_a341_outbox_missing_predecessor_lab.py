"""A341 LAB: missing local Outbox predecessor must not release aggregate FIFO.

Only temporary SQLite test rows are deleted/modified. This proves no producer
effect, independent antirollback witness, HUMAN_OWNER approval, or real send.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 31, 16, 0, tzinfo=timezone.utc)
SCOPE = Scope("a341-owner", "a341-tenant", "a341-workspace")
AGGREGATE = "a341-client"


class A341MissingOutboxPredecessorTests(unittest.TestCase):
    def _enqueue(self, outbox, name, aggregate=AGGREGATE):
        return outbox.enqueue(
            intent_ref=name,
            action="create_crm_note",
            payload={"test_only": True, "intent_ref": name},
            aggregate_key=aggregate,
            policy_version="a341-policy",
            authorization_ref="a341-local-staging-only",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def _fixture(self, directory):
        path = Path(directory) / "a341.sqlite3"
        store = SQLiteChatStore(path)
        outbox = ExecutionOutbox(store, SCOPE)
        first = self._enqueue(outbox, "a341-first")
        second = self._enqueue(outbox, "a341-second")
        self.assertEqual((first["aggregate_seq"], second["aggregate_seq"]), (1, 2))
        return store, outbox, path, first, second

    def _delete_prior_outbox(self, outbox, first):
        # Adversarial same-SQLite local deletion, no real action.
        with outbox.db:
            cursor = outbox.db.execute(
                "DELETE FROM action_outbox WHERE idempotency_key=?",
                (first["idempotency_key"],),
            )
            self.assertEqual(cursor.rowcount, 1)

    def _assert_second_blocked(self, outbox, second, *, state="PENDING"):
        self.assertIsNone(
            outbox.claim_next("a341-worker", now=NOW + timedelta(seconds=2))
        )
        row = outbox.get(second["idempotency_key"])
        self.assertEqual(row["aggregate_seq"], 2)
        self.assertEqual(row["state"], state)
        self.assertEqual(row["attempts"], 0)
        self.assertEqual(outbox.effect_count(), 0)

    def test_01_missing_predecessor_outbox_row_cannot_release_sequence_two(self):
        with TemporaryDirectory() as directory:
            store, outbox, _, first, second = self._fixture(directory)
            try:
                self._delete_prior_outbox(outbox, first)
                self.assertEqual(
                    outbox.db.execute(
                        "SELECT count(*) FROM action_decisions WHERE decision_id=?",
                        (first["decision_id"],),
                    ).fetchone()[0], 1,
                )
                self._assert_second_blocked(outbox, second)
            finally:
                store.close()

    def test_02_missing_outbox_and_decision_still_cannot_release_second(self):
        with TemporaryDirectory() as directory:
            store, outbox, _, first, second = self._fixture(directory)
            try:
                self._delete_prior_outbox(outbox, first)
                with outbox.db:
                    cursor = outbox.db.execute(
                        "DELETE FROM action_decisions WHERE decision_id=?",
                        (first["decision_id"],),
                    )
                    self.assertEqual(cursor.rowcount, 1)
                self.assertEqual(
                    outbox.db.execute(
                        "SELECT count(*) FROM action_decisions WHERE aggregate_key=?",
                        (AGGREGATE,),
                    ).fetchone()[0], 1,
                )
                self._assert_second_blocked(outbox, second)
            finally:
                store.close()

    def test_03_missing_prior_row_stays_blocked_after_store_reopen(self):
        with TemporaryDirectory() as directory:
            store, outbox, path, first, second = self._fixture(directory)
            self._delete_prior_outbox(outbox, first)
            store.close()
            reopened = SQLiteChatStore(path)
            try:
                recovered = ExecutionOutbox(reopened, SCOPE)
                self._assert_second_blocked(recovered, second)
            finally:
                reopened.close()

    def test_04_unrelated_aggregate_first_intent_still_claims(self):
        with TemporaryDirectory() as directory:
            store, outbox, _, first, second = self._fixture(directory)
            try:
                other = self._enqueue(outbox, "a341-unrelated", "a341-other-client")
                self.assertEqual(other["aggregate_seq"], 1)
                self._delete_prior_outbox(outbox, first)
                result = outbox.claim_next(
                    "a341-worker", now=NOW + timedelta(seconds=2)
                )
                self.assertIsNotNone(result)
                self.assertEqual(result["idempotency_key"], other["idempotency_key"])
                self.assertEqual(result["state"], "CLAIMED")
                self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
                self.assertEqual(outbox.get(second["idempotency_key"])["attempts"], 0)
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_05_other_tenant_first_intent_remains_independent(self):
        with TemporaryDirectory() as directory:
            store, outbox, _, first, second = self._fixture(directory)
            try:
                other_scope = Scope("a341-owner", "a341-other-tenant", "a341-workspace")
                other = ExecutionOutbox(store, other_scope)
                other_first = self._enqueue(other, "a341-other-tenant-intent")
                self.assertEqual(other_first["aggregate_seq"], 1)
                self._delete_prior_outbox(outbox, first)
                self._assert_second_blocked(outbox, second)
                result = other.claim_next(
                    "other-worker", now=NOW + timedelta(seconds=3)
                )
                self.assertIsNotNone(result)
                self.assertEqual(result["idempotency_key"], other_first["idempotency_key"])
                self.assertEqual(outbox.effect_count(), 0)
                self.assertEqual(other.effect_count(), 0)
            finally:
                store.close()

    def test_06_retry_label_without_predecessor_cannot_overtake(self):
        with TemporaryDirectory() as directory:
            store, outbox, _, first, second = self._fixture(directory)
            try:
                self._delete_prior_outbox(outbox, first)
                with outbox.db:
                    cursor = outbox.db.execute(
                        """UPDATE action_outbox SET state='RETRY',
                           last_error='A341_LOCAL_RETRY'
                           WHERE idempotency_key=?""",
                        (second["idempotency_key"],),
                    )
                    self.assertEqual(cursor.rowcount, 1)
                self._assert_second_blocked(outbox, second, state="RETRY")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
