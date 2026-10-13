"""AION V16-A.44 — real Outbox FIFO with forged local terminal rows.

All SQLite modifications in this suite are deliberately adversarial TEST-ONLY.
No producer send, reconciliation, signed receipt, external witness, account,
network, authority or productive effect is executed or implied.
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


class OutboxLocalTerminalFifoDenialTests(unittest.TestCase):
    def _fixture(self, directory):
        scope = Scope("a44-owner", "a44-tenant", "a44-workspace")
        path = Path(directory) / "outbox.sqlite3"
        store = SQLiteChatStore(path)
        outbox = ExecutionOutbox(store, scope)
        def enqueue(ref, aggregate):
            return outbox.enqueue(
                intent_ref=ref,
                action="create_crm_note",
                payload={"origin": "TEST_ONLY", "intent_ref": ref},
                aggregate_key=aggregate,
                policy_version="a44-policy",
                authorization_ref="a44-local-staging-only",
                created_at=NOW,
                valid_until=NOW + timedelta(minutes=5),
            )
        first = enqueue("a44-first", "a44-same-client")
        second = enqueue("a44-second", "a44-same-client")
        return store, outbox, path, first, second, enqueue

    @staticmethod
    def _forge(outbox, first, state):
        # SQL fields deliberately do NOT represent a genuine external receipt.
        with outbox.db:
            outbox.db.execute(
                """UPDATE action_outbox
                   SET state=?,effect_ref='FAKE_EXTERNAL_EFFECT',
                       confirmed_at='2026-10-13T20:00:01+00:00',
                       last_error='A44_LOCAL_FORGED_STATUS'
                   WHERE idempotency_key=?""",
                (state, first["idempotency_key"]),
            )

    def test_01_all_local_terminal_statuses_cannot_release_followup(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, _, first, second, _ = self._fixture(raw)
            try:
                for state in ("CONFIRMED", "FAILED", "REVOKED", "BLOCKED_REAPPROVAL"):
                    with self.subTest(state=state):
                        self._forge(outbox, first, state)
                        self.assertIsNone(
                            outbox.claim_next("a44-worker", now=NOW + timedelta(seconds=2))
                        )
                        self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
                        self.assertEqual(outbox.get(second["idempotency_key"])["attempts"], 0)
                        self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_02_forged_confirmed_plus_fake_effect_ledger_is_not_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, _, first, second, _ = self._fixture(raw)
            try:
                self._forge(outbox, first, "CONFIRMED")
                with outbox.db:
                    outbox.db.execute(
                        """INSERT INTO action_effects(
                            idempotency_key,owner,tenant,workspace,
                            effect_ref,confirmed_at,data
                        ) VALUES (?,?,?,?,?,?,?)""",
                        (
                            first["idempotency_key"], "a44-owner", "a44-tenant",
                            "a44-workspace", "FAKE_EXTERNAL_EFFECT",
                            "2026-10-13T20:00:01+00:00", '{"A44":"TEST_ONLY"}',
                        ),
                    )
                self.assertEqual(outbox.effect_count(), 1)
                self.assertIsNone(
                    outbox.claim_next("a44-worker", now=NOW + timedelta(seconds=2))
                )
                self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
                self.assertEqual(outbox.get(second["idempotency_key"])["attempts"], 0)
                # Local forged ledger remains untrusted and unmodified.
                self.assertEqual(outbox.effect_count(), 1)
            finally:
                store.close()

    def test_03_unrelated_aggregate_can_still_claim_without_releasing_followup(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, _, first, second, enqueue = self._fixture(raw)
            try:
                other = enqueue("a44-unrelated", "a44-other-client")
                self._forge(outbox, first, "CONFIRMED")
                claimed = outbox.claim_next("a44-worker", now=NOW + timedelta(seconds=2))
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed["idempotency_key"], other["idempotency_key"])
                self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
                self.assertEqual(outbox.get(second["idempotency_key"])["attempts"], 0)
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_04_local_terminal_cannot_release_after_process_style_reopen(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, path, first, second, _ = self._fixture(raw)
            self._forge(outbox, first, "FAILED")
            store.close()
            reopened = SQLiteChatStore(path)
            try:
                recovered = ExecutionOutbox(reopened, Scope("a44-owner", "a44-tenant", "a44-workspace"))
                self.assertIsNone(
                    recovered.claim_next("a44-worker", now=NOW + timedelta(seconds=3))
                )
                self.assertEqual(recovered.get(second["idempotency_key"])["state"], "PENDING")
                self.assertEqual(recovered.get(second["idempotency_key"])["attempts"], 0)
            finally:
                reopened.close()

    def test_05_first_unencumbered_intent_remains_claimable(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, _, first, second, _ = self._fixture(raw)
            try:
                claimed = outbox.claim_next("a44-worker", now=NOW + timedelta(seconds=2))
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed["idempotency_key"], first["idempotency_key"])
                self.assertEqual(claimed["attempts"], 1)
                self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
                self.assertIsNone(
                    outbox.claim_next("a44-other-worker", now=NOW + timedelta(seconds=3))
                )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
