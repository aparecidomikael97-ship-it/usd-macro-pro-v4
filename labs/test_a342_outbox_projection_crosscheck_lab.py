"""A342 LAB: local SQL columns and serialized Outbox decision must agree.

These are only partial-tamper checks within temporary SQLite. A privileged
writer can rewrite both copies, so no independent antirollback or producer
proof is claimed; no callback, adapter or real action is exercised.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 31, 17, 0, tzinfo=timezone.utc)
SCOPE = Scope("a342-owner", "a342-tenant", "a342-workspace")
REASON = "OUTBOX_DECISION_LOCAL_PROJECTION_UNTRUSTED"


class A342OutboxProjectionCrosscheckTests(unittest.TestCase):
    def _enqueue(self, outbox, name, aggregate="a342-client"):
        return outbox.enqueue(
            intent_ref=name,
            action="create_crm_note",
            payload={"test_only": True, "intent_ref": name},
            aggregate_key=aggregate,
            policy_version="a342-policy",
            authorization_ref="a342-local-staging-only",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def _fixture(self, directory):
        store = SQLiteChatStore(Path(directory) / "a342.sqlite3")
        outbox = ExecutionOutbox(store, SCOPE)
        first = self._enqueue(outbox, "a342-first")
        second = self._enqueue(outbox, "a342-second")
        self.assertEqual((first["aggregate_seq"], second["aggregate_seq"]), (1, 2))
        return store, outbox, first, second

    def _change_json(self, outbox, decision_id, **overrides):
        row = outbox.db.execute(
            "SELECT data FROM action_decisions WHERE decision_id=?", (decision_id,)
        ).fetchone()
        self.assertIsNotNone(row)
        value = json.loads(row["data"])
        value.update(overrides)
        with outbox.db:
            cursor = outbox.db.execute(
                "UPDATE action_decisions SET data=? WHERE decision_id=?",
                (json.dumps(value, sort_keys=True), decision_id),
            )
            self.assertEqual(cursor.rowcount, 1)

    def _assert_denied_without_claim(self, outbox, key, *, state="PENDING"):
        before = outbox.db.total_changes
        with self.assertRaisesRegex(PermissionError, REASON):
            outbox.claim_next("a342-worker", now=NOW + timedelta(seconds=2))
        self.assertEqual(outbox.db.total_changes, before)
        row = outbox.db.execute(
            "SELECT state,attempts FROM action_outbox WHERE idempotency_key=?", (key,)
        ).fetchone()
        self.assertEqual(row["state"], state)
        self.assertEqual(row["attempts"], 0)
        self.assertEqual(outbox.effect_count(), 0)

    def test_01_rewritten_ordinal_one_with_embedded_two_does_not_claim(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, second = self._fixture(directory)
            try:
                with outbox.db:
                    outbox.db.execute(
                        "DELETE FROM action_outbox WHERE idempotency_key=?",
                        (first["idempotency_key"],),
                    )
                    outbox.db.execute(
                        "DELETE FROM action_decisions WHERE decision_id=?",
                        (first["decision_id"],),
                    )
                    cursor = outbox.db.execute(
                        "UPDATE action_decisions SET aggregate_seq=1 WHERE decision_id=?",
                        (second["decision_id"],),
                    )
                    self.assertEqual(cursor.rowcount, 1)
                view = outbox.get(second["idempotency_key"])
                self.assertEqual(view["aggregate_seq"], 1)
                self.assertEqual(view["decision"]["aggregate_seq"], 2)
                self._assert_denied_without_claim(outbox, second["idempotency_key"])
            finally:
                store.close()

    def test_02_mutated_embedded_ordinal_cannot_claim_original_first(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, _second = self._fixture(directory)
            try:
                self._change_json(outbox, first["decision_id"], aggregate_seq=2)
                self._assert_denied_without_claim(outbox, first["idempotency_key"])
            finally:
                store.close()

    def test_03_malformed_stored_decision_json_cannot_claim(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, _second = self._fixture(directory)
            try:
                with outbox.db:
                    outbox.db.execute(
                        "UPDATE action_decisions SET data=? WHERE decision_id=?",
                        ("{broken-local-json", first["decision_id"]),
                    )
                self._assert_denied_without_claim(outbox, first["idempotency_key"])
            finally:
                store.close()

    def test_04_wrong_embedded_idempotency_key_cannot_claim(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, _second = self._fixture(directory)
            try:
                self._change_json(
                    outbox, first["decision_id"],
                    idempotency_key="FORGED_DIFFERENT_LOCAL_KEY",
                )
                self._assert_denied_without_claim(outbox, first["idempotency_key"])
            finally:
                store.close()

    def test_05_owner_tenant_aggregate_or_decision_mismatch_cannot_claim(self):
        for field, forged in (
            ("owner_id", "a342-other-owner"),
            ("tenant_id", "a342-other-tenant"),
            ("workspace_id", "a342-other-workspace"),
            ("aggregate_key", "a342-other-client"),
            ("decision_id", "FORGED_DECISION"),
        ):
            with self.subTest(field=field):
                with TemporaryDirectory() as directory:
                    store, outbox, first, _second = self._fixture(directory)
                    try:
                        self._change_json(outbox, first["decision_id"], **{field: forged})
                        self._assert_denied_without_claim(
                            outbox, first["idempotency_key"]
                        )
                    finally:
                        store.close()

    def test_06_intact_first_ordinal_can_still_claim_only_locally(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, second = self._fixture(directory)
            try:
                claimed = outbox.claim_next(
                    "a342-worker", now=NOW + timedelta(seconds=1)
                )
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed["idempotency_key"], first["idempotency_key"])
                self.assertEqual(claimed["state"], "CLAIMED")
                self.assertIsNone(outbox.claim_next(
                    "a342-second-worker", now=NOW + timedelta(seconds=2)
                ))
                self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_07_other_tenant_remains_claimable_despite_local_projection_mismatch(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, _second = self._fixture(directory)
            try:
                self._change_json(outbox, first["decision_id"], aggregate_seq=2)
                other_scope = Scope("a342-owner", "a342-other-tenant", "a342-workspace")
                independent = ExecutionOutbox(store, other_scope)
                new = self._enqueue(independent, "a342-other-tenant-first")
                result = independent.claim_next(
                    "other-worker", now=NOW + timedelta(seconds=2)
                )
                self.assertIsNotNone(result)
                self.assertEqual(result["idempotency_key"], new["idempotency_key"])
                self.assertEqual(independent.effect_count(), 0)
                self._assert_denied_without_claim(outbox, first["idempotency_key"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
