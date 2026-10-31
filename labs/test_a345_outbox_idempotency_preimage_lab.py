"""A345 LAB: verify the staged Outbox idempotency key's local preimage.

No provider, adapter, authority proof or real effect exists. Synthetic SQLite
admission checks detect partial/coherent-local-column mutations, but a fully
forged key, decision, owner scope and history still need an independent witness.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)
SCOPE = Scope("a345-owner", "a345-tenant", "a345-workspace")
REASON = "OUTBOX_DECISION_LOCAL_PROJECTION_UNTRUSTED"


class A345OutboxIdempotencyPreimageTests(unittest.TestCase):
    def _enqueue(self, outbox, intent_ref, **overrides):
        args = dict(
            intent_ref=intent_ref,
            action="create_crm_note",
            payload={"test_only": True, "items": [1, 2]},
            aggregate_key="a345-client",
            policy_version="a345-policy",
            authorization_ref="a345-staging-only",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        args.update(overrides)
        return outbox.enqueue(**args)

    def _fixture(self, directory):
        store = SQLiteChatStore(Path(directory) / "a345.sqlite3")
        outbox = ExecutionOutbox(store, SCOPE)
        first = self._enqueue(outbox, "a345-first")
        second = self._enqueue(outbox, "a345-second")
        self.assertEqual((first["aggregate_seq"], second["aggregate_seq"]), (1, 2))
        return store, outbox, first, second

    def _change_json(self, outbox, decision_id, updates, *, delete=()):
        row = outbox.db.execute(
            "SELECT data FROM action_decisions WHERE decision_id=?", (decision_id,)
        ).fetchone()
        self.assertIsNotNone(row)
        decision = json.loads(row["data"])
        decision.update(updates)
        for field in delete:
            decision.pop(field, None)
        with outbox.db:
            cursor = outbox.db.execute(
                "UPDATE action_decisions SET data=? WHERE decision_id=?",
                (json.dumps(decision, sort_keys=True), decision_id),
            )
            self.assertEqual(cursor.rowcount, 1)

    def _assert_denied_without_claim(self, outbox, key):
        before = outbox.db.total_changes
        with self.assertRaisesRegex(PermissionError, REASON):
            outbox.claim_next("a345-worker", now=NOW + timedelta(seconds=2))
        self.assertEqual(outbox.db.total_changes, before)
        row = outbox.db.execute(
            "SELECT state,attempts,dispatch_started_at FROM action_outbox "
            "WHERE idempotency_key=?", (key,)
        ).fetchone()
        self.assertEqual((row["state"], row["attempts"], row["dispatch_started_at"]),
                         ("PENDING", 0, ""))
        self.assertEqual(outbox.effect_count(), 0)

    def test_01_json_only_budget_preimage_edits_cannot_claim(self):
        updates = (
            ("transaction_id", "a345-forged-tx"),
            ("authority_budget_ref", "a345-forged-budget"),
            ("risk_points", 17),
            ("capability_class", "HIGH"),
        )
        for field, forged in updates:
            with self.subTest(field=field):
                with TemporaryDirectory() as directory:
                    store, outbox, first, _second = self._fixture(directory)
                    try:
                        self._change_json(outbox, first["decision_id"], {field: forged})
                        self._assert_denied_without_claim(outbox, first["idempotency_key"])
                    finally:
                        store.close()

    def test_02_missing_or_non_native_budget_fields_cannot_claim(self):
        variants = (
            ({"risk_points": True}, ()),
            ({"risk_points": "0"}, ()),
            ({"transaction_id": None}, ()),
            ({}, ("capability_class",)),
            ({}, ("authority_budget_ref",)),
        )
        for updated, removed in variants:
            with self.subTest(updated=updated, removed=removed):
                with TemporaryDirectory() as directory:
                    store, outbox, first, _second = self._fixture(directory)
                    try:
                        self._change_json(
                            outbox, first["decision_id"], updated, delete=removed,
                        )
                        self._assert_denied_without_claim(outbox, first["idempotency_key"])
                    finally:
                        store.close()

    def test_03_coherent_sql_json_identity_rewrite_still_cannot_reuse_old_key(self):
        variants = (
            ("intent_ref", "a345-forged-intent"),
            ("action", "a345-forged-action"),
            ("aggregate_key", "a345-forged-aggregate"),
        )
        for column, forged in variants:
            with self.subTest(column=column):
                with TemporaryDirectory() as directory:
                    store, outbox, first, _second = self._fixture(directory)
                    try:
                        row = outbox.db.execute(
                            "SELECT data FROM action_decisions WHERE decision_id=?",
                            (first["decision_id"],),
                        ).fetchone()
                        embedded = json.loads(row["data"])
                        embedded[column] = forged
                        # Test fixture only: SQL identifiers are fixed test literals.
                        with outbox.db:
                            cursor = outbox.db.execute(
                                f"UPDATE action_decisions SET {column}=?,data=? "
                                "WHERE decision_id=?",
                                (forged, json.dumps(embedded, sort_keys=True),
                                 first["decision_id"]),
                            )
                            self.assertEqual(cursor.rowcount, 1)
                        self._assert_denied_without_claim(outbox, first["idempotency_key"])
                    finally:
                        store.close()

    def test_04_coherent_payload_and_both_local_digest_rewrites_need_new_key(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, _second = self._fixture(directory)
            try:
                row = outbox.db.execute(
                    "SELECT data FROM action_decisions WHERE decision_id=?",
                    (first["decision_id"],),
                ).fetchone()
                embedded = json.loads(row["data"])
                forged_payload = {"test_only": False, "items": [99]}
                forged_digest = hashlib.sha256(json.dumps(
                    forged_payload, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")).hexdigest()
                embedded["payload"] = forged_payload
                embedded["payload_digest"] = forged_digest
                with outbox.db:
                    cursor = outbox.db.execute(
                        "UPDATE action_decisions SET payload_digest=?,data=? "
                        "WHERE decision_id=?",
                        (forged_digest, json.dumps(embedded, sort_keys=True),
                         first["decision_id"]),
                    )
                    self.assertEqual(cursor.rowcount, 1)
                self._assert_denied_without_claim(outbox, first["idempotency_key"])
            finally:
                store.close()

    def test_05_original_first_intent_claims_locally_without_send(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, second = self._fixture(directory)
            try:
                claimed = outbox.claim_next("a345-worker", now=NOW + timedelta(seconds=1))
                self.assertEqual(claimed["idempotency_key"], first["idempotency_key"])
                self.assertEqual(claimed["state"], "CLAIMED")
                self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_06_intact_transaction_budget_preimage_can_stage_local_claim_only(self):
        with TemporaryDirectory() as directory:
            store = SQLiteChatStore(Path(directory) / "a345-budget.sqlite3")
            outbox = ExecutionOutbox(store, SCOPE)
            try:
                first = self._enqueue(
                    outbox, "a345-legitimate-budget",
                    transaction_id="a345-transaction",
                    authority_budget_ref="a345-budget",
                    risk_points=7,
                    capability_class="LOW_RISK",
                )
                result = outbox.claim_next("a345-worker", now=NOW + timedelta(seconds=1))
                self.assertEqual(result["idempotency_key"], first["idempotency_key"])
                self.assertEqual(result["state"], "CLAIMED")
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_07_other_tenant_remains_independent_of_forged_budget_preimage(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, _second = self._fixture(directory)
            try:
                self._change_json(outbox, first["decision_id"], {"risk_points": 11})
                other = ExecutionOutbox(
                    store, Scope("a345-owner", "a345-other-tenant", "a345-workspace")
                )
                new = self._enqueue(other, "a345-other-first")
                claimed = other.claim_next(
                    "a345-other-worker", now=NOW + timedelta(seconds=1)
                )
                self.assertEqual(claimed["idempotency_key"], new["idempotency_key"])
                self.assertEqual(other.effect_count(), 0)
                self._assert_denied_without_claim(outbox, first["idempotency_key"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
