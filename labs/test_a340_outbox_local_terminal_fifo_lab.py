"""A340 LAB: forged local Outbox terminal states cannot release aggregate FIFO.

Each mutation below is a test-owned temporary SQLite forgery, never a
producer receipt, provider callback, real send, terminal fence or owner proof.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 31, 15, 0, tzinfo=timezone.utc)
SCOPE = Scope("a340-owner", "a340-tenant", "a340-workspace")
AGGREGATE = "a340-client-one"


class A340ForgedTerminalFifoTests(unittest.TestCase):
    def _fixture(self, directory):
        path = Path(directory) / "outbox.sqlite3"
        store = SQLiteChatStore(path)
        outbox = ExecutionOutbox(store, SCOPE)
        first = self._enqueue(outbox, "a340-first", AGGREGATE)
        second = self._enqueue(outbox, "a340-second", AGGREGATE)
        self.assertEqual(first["aggregate_seq"], 1)
        self.assertEqual(second["aggregate_seq"], 2)
        return store, outbox, path, first, second

    def _enqueue(self, outbox, ref, aggregate):
        return outbox.enqueue(
            intent_ref=ref,
            action="create_crm_note",
            payload={"test_only": True, "intent_ref": ref},
            aggregate_key=aggregate,
            policy_version="a340-policy",
            authorization_ref="a340-local-staging-only",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def _forge(self, outbox, first, state):
        # The row is locally forged and contains NO independently verified proof.
        with outbox.db:
            cursor = outbox.db.execute(
                """UPDATE action_outbox
                   SET state=?,effect_ref='LOCAL_FORGED_EFFECT',
                       confirmed_at='2026-10-31T15:00:01+00:00',
                       last_error='A340_LOCAL_SQLITE_CLAIM'
                   WHERE idempotency_key=?""",
                (state, first["idempotency_key"]),
            )
            self.assertEqual(cursor.rowcount, 1)

    def _assert_second_unclaimed(self, outbox, second):
        row = outbox.get(second["idempotency_key"])
        self.assertEqual(row["state"], "PENDING")
        self.assertEqual(row["attempts"], 0)
        self.assertFalse(row.get("dispatch_started_at"))

    def test_01_all_four_forged_terminal_labels_fail_closed_independently(self):
        for state in ("CONFIRMED", "FAILED", "REVOKED", "BLOCKED_REAPPROVAL"):
            with self.subTest(state=state):
                # Separate SQLite per label: unsafe claims cannot pollute
                # later subcases and hide a second bypass.
                with TemporaryDirectory() as directory:
                    store, outbox, _, first, second = self._fixture(directory)
                    try:
                        self._forge(outbox, first, state)
                        self.assertIsNone(outbox.claim_next(
                            "a340-worker", now=NOW + timedelta(seconds=2)
                        ))
                        self._assert_second_unclaimed(outbox, second)
                        self.assertEqual(outbox.effect_count(), 0)
                    finally:
                        store.close()

    def test_02_fake_confirmed_row_plus_fake_effect_ledger_never_unlocks_fifo(self):
        with TemporaryDirectory() as directory:
            store, outbox, _, first, second = self._fixture(directory)
            try:
                self._forge(outbox, first, "CONFIRMED")
                with outbox.db:
                    outbox.db.execute(
                        """INSERT INTO action_effects(
                           idempotency_key,owner,tenant,workspace,
                           effect_ref,confirmed_at,data
                           ) VALUES (?,?,?,?,?,?,?)""",
                        (
                            first["idempotency_key"], SCOPE.owner_id,
                            SCOPE.tenant_id, SCOPE.workspace_id,
                            "LOCAL_FORGED_EFFECT", NOW.isoformat(),
                            '{"test_only":true,"external_proof":false}',
                        ),
                    )
                self.assertEqual(outbox.effect_count(), 1)
                self.assertIsNone(outbox.claim_next(
                    "a340-worker", now=NOW + timedelta(seconds=2)
                ))
                self._assert_second_unclaimed(outbox, second)
                self.assertEqual(outbox.effect_count(), 1)
            finally:
                store.close()

    def test_03_unrelated_aggregate_remains_locally_claimable(self):
        with TemporaryDirectory() as directory:
            store, outbox, _, first, second = self._fixture(directory)
            try:
                other = self._enqueue(outbox, "a340-unrelated", "a340-other-client")
                self._forge(outbox, first, "CONFIRMED")
                result = outbox.claim_next(
                    "a340-worker", now=NOW + timedelta(seconds=2)
                )
                self.assertIsNotNone(result)
                self.assertEqual(result["idempotency_key"], other["idempotency_key"])
                self.assertEqual(result["state"], "CLAIMED")
                self._assert_second_unclaimed(outbox, second)
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_04_forged_terminal_denial_survives_store_reopen(self):
        with TemporaryDirectory() as directory:
            store, outbox, path, first, second = self._fixture(directory)
            self._forge(outbox, first, "FAILED")
            store.close()
            reopened = SQLiteChatStore(path)
            try:
                recovered = ExecutionOutbox(reopened, SCOPE)
                self.assertIsNone(recovered.claim_next(
                    "a340-worker", now=NOW + timedelta(seconds=3)
                ))
                self._assert_second_unclaimed(recovered, second)
            finally:
                reopened.close()

    def test_05_first_staged_intent_can_claim_without_unlocking_next(self):
        with TemporaryDirectory() as directory:
            store, outbox, _, first, second = self._fixture(directory)
            try:
                claimed = outbox.claim_next(
                    "a340-worker", now=NOW + timedelta(seconds=1)
                )
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed["idempotency_key"], first["idempotency_key"])
                self.assertEqual(claimed["attempts"], 1)
                self._assert_second_unclaimed(outbox, second)
                self.assertIsNone(outbox.claim_next(
                    "a340-other-worker", now=NOW + timedelta(seconds=2)
                ))
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_06_scope_isolation_keeps_other_tenant_locally_claimable(self):
        with TemporaryDirectory() as directory:
            store, outbox, _, first, second = self._fixture(directory)
            try:
                self._forge(outbox, first, "CONFIRMED")
                foreign_scope = Scope("a340-owner", "a340-other-tenant", "a340-workspace")
                foreign = ExecutionOutbox(store, foreign_scope)
                candidate = self._enqueue(foreign, "foreign-one", AGGREGATE)
                claimed = foreign.claim_next(
                    "foreign-worker", now=NOW + timedelta(seconds=2)
                )
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed["idempotency_key"], candidate["idempotency_key"])
                self.assertIsNone(outbox.claim_next(
                    "a340-worker", now=NOW + timedelta(seconds=2)
                ))
                self._assert_second_unclaimed(outbox, second)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
