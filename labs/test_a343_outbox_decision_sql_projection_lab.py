"""A343 LAB: reject partial SQL/JSON divergence in remaining Outbox decision fields.

Tests use only temporary SQLite, synthetic local claims and no adapter/network.
Both copies live in one mutable DB: coherent dual-copy tampering, rollback, and
trusted external authority remain UNPROVEN. HARD NO-GO / Worker OFF.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 31, 18, 0, tzinfo=timezone.utc)
SCOPE = Scope("a343-owner", "a343-tenant", "a343-workspace")
REASON = "OUTBOX_DECISION_LOCAL_PROJECTION_UNTRUSTED"


class A343OutboxDecisionSqlProjectionTests(unittest.TestCase):
    def _enqueue(self, outbox, intent_ref):
        return outbox.enqueue(
            intent_ref=intent_ref,
            action="create_crm_note",
            payload={"test_only": True, "intent_ref": intent_ref},
            aggregate_key="a343-client",
            policy_version="a343-policy",
            authorization_ref="a343-staging-only",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def _fixture(self, directory):
        store = SQLiteChatStore(Path(directory) / "a343.sqlite3")
        outbox = ExecutionOutbox(store, SCOPE)
        first = self._enqueue(outbox, "a343-first")
        second = self._enqueue(outbox, "a343-second")
        self.assertEqual((first["aggregate_seq"], second["aggregate_seq"]), (1, 2))
        return store, outbox, first, second

    def _change_sql(self, outbox, decision_id, column, forged):
        # Test fixture only: column names come from hard-coded test cases.
        with outbox.db:
            cursor = outbox.db.execute(
                f"UPDATE action_decisions SET {column}=? WHERE decision_id=?",
                (forged, decision_id),
            )
            self.assertEqual(cursor.rowcount, 1)

    def _change_json(self, outbox, decision_id, field, forged):
        row = outbox.db.execute(
            "SELECT data FROM action_decisions WHERE decision_id=?", (decision_id,)
        ).fetchone()
        self.assertIsNotNone(row)
        embedded = json.loads(row["data"])
        embedded[field] = forged
        with outbox.db:
            cursor = outbox.db.execute(
                "UPDATE action_decisions SET data=? WHERE decision_id=?",
                (json.dumps(embedded, sort_keys=True), decision_id),
            )
            self.assertEqual(cursor.rowcount, 1)

    def _assert_denied_without_claim(self, outbox, key):
        before_changes = outbox.db.total_changes
        with self.assertRaisesRegex(PermissionError, REASON):
            outbox.claim_next("a343-local-only", now=NOW + timedelta(seconds=2))
        self.assertEqual(outbox.db.total_changes, before_changes)
        row = outbox.db.execute(
            "SELECT state,attempts,dispatch_started_at FROM action_outbox "
            "WHERE idempotency_key=?", (key,)
        ).fetchone()
        self.assertEqual((row["state"], row["attempts"], row["dispatch_started_at"]),
                         ("PENDING", 0, ""))
        self.assertEqual(outbox.effect_count(), 0)

    def test_01_sql_only_decision_fields_cannot_change_before_claim(self):
        tampered = {
            "intent_ref": "a343-forged-intent",
            "action": "a343-forged-action",
            "payload_digest": "0" * 64,
            "policy_version": "a343-forged-policy",
            "authorization_ref": "a343-forged-authority",
            "valid_until": (NOW + timedelta(minutes=20)).isoformat(),
            "created_at": (NOW + timedelta(days=1)).isoformat(),
        }
        for column, forged in tampered.items():
            with self.subTest(column=column):
                with TemporaryDirectory() as directory:
                    store, outbox, first, _second = self._fixture(directory)
                    try:
                        self._change_sql(outbox, first["decision_id"], column, forged)
                        self._assert_denied_without_claim(outbox, first["idempotency_key"])
                    finally:
                        store.close()

    def test_02_json_only_decision_fields_cannot_change_before_claim(self):
        tampered = {
            "intent_ref": "a343-forged-intent",
            "action": "a343-forged-action",
            "payload_digest": "0" * 64,
            "policy_version": "a343-forged-policy",
            "authorization_ref": "a343-forged-authority",
            "valid_until": (NOW + timedelta(minutes=20)).isoformat(),
            "created_at": (NOW + timedelta(days=1)).isoformat(),
        }
        for field, forged in tampered.items():
            with self.subTest(field=field):
                with TemporaryDirectory() as directory:
                    store, outbox, first, _second = self._fixture(directory)
                    try:
                        self._change_json(outbox, first["decision_id"], field, forged)
                        self._assert_denied_without_claim(outbox, first["idempotency_key"])
                    finally:
                        store.close()

    def test_03_sql_only_decision_scope_change_cannot_claim_outbox_row(self):
        tampered = {
            "owner": "a343-foreign-owner",
            "tenant": "a343-foreign-tenant",
            "workspace": "a343-foreign-workspace",
        }
        for column, forged in tampered.items():
            with self.subTest(column=column):
                with TemporaryDirectory() as directory:
                    store, outbox, first, _second = self._fixture(directory)
                    try:
                        self._change_sql(outbox, first["decision_id"], column, forged)
                        self._assert_denied_without_claim(outbox, first["idempotency_key"])
                    finally:
                        store.close()

    def test_04_original_first_ordinal_remains_locally_claimable_only(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, second = self._fixture(directory)
            try:
                result = outbox.claim_next("a343-local-only", now=NOW + timedelta(seconds=1))
                self.assertEqual(result["idempotency_key"], first["idempotency_key"])
                self.assertEqual(result["state"], "CLAIMED")
                self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_05_independent_tenant_not_blocked_by_different_tenant_mismatch(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, _second = self._fixture(directory)
            try:
                self._change_sql(outbox, first["decision_id"], "policy_version",
                                 "a343-foreign-policy")
                independent = ExecutionOutbox(
                    store, Scope("a343-owner", "a343-other-tenant", "a343-workspace")
                )
                other = self._enqueue(independent, "a343-independent-first")
                result = independent.claim_next(
                    "a343-other-worker", now=NOW + timedelta(seconds=1)
                )
                self.assertEqual(result["idempotency_key"], other["idempotency_key"])
                self.assertEqual(independent.effect_count(), 0)
                self._assert_denied_without_claim(outbox, first["idempotency_key"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
