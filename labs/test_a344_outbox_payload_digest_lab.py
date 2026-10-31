"""A344 LAB: serialized Outbox payload must match its staged digest.

Only synthetic local SQLite claims are exercised; no adapter, callback, provider,
network or effect. Digest is same-database partial integrity, never an independent
producer receipt, antirollback witness or HUMAN_OWNER authorization.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 31, 19, 0, tzinfo=timezone.utc)
SCOPE = Scope("a344-owner", "a344-tenant", "a344-workspace")
REASON = "OUTBOX_DECISION_LOCAL_PROJECTION_UNTRUSTED"


class A344OutboxPayloadDigestTests(unittest.TestCase):
    def _enqueue(self, outbox, intent_ref, *, payload=None):
        return outbox.enqueue(
            intent_ref=intent_ref,
            action="create_crm_note",
            payload=payload if payload is not None else {
                "test_only": True,
                "nested": {"priority": "low", "items": [1, 2]},
            },
            aggregate_key="a344-client",
            policy_version="a344-policy",
            authorization_ref="a344-local-staging-only",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def _fixture(self, directory):
        store = SQLiteChatStore(Path(directory) / "a344.sqlite3")
        outbox = ExecutionOutbox(store, SCOPE)
        first = self._enqueue(outbox, "a344-first")
        second = self._enqueue(outbox, "a344-second")
        self.assertEqual((first["aggregate_seq"], second["aggregate_seq"]), (1, 2))
        return store, outbox, first, second

    def _rewrite_embedded_payload(self, outbox, decision_id, forged, *, remove=False):
        row = outbox.db.execute(
            "SELECT data FROM action_decisions WHERE decision_id=?", (decision_id,)
        ).fetchone()
        self.assertIsNotNone(row)
        decision = json.loads(row["data"])
        if remove:
            decision.pop("payload", None)
        else:
            decision["payload"] = forged
        with outbox.db:
            cursor = outbox.db.execute(
                "UPDATE action_decisions SET data=? WHERE decision_id=?",
                (json.dumps(decision, sort_keys=True), decision_id),
            )
            self.assertEqual(cursor.rowcount, 1)

    def _assert_denied_without_claim(self, outbox, key):
        before = outbox.db.total_changes
        with self.assertRaisesRegex(PermissionError, REASON):
            outbox.claim_next("a344-local-only", now=NOW + timedelta(seconds=2))
        self.assertEqual(outbox.db.total_changes, before)
        row = outbox.db.execute(
            "SELECT state,attempts,dispatch_started_at FROM action_outbox "
            "WHERE idempotency_key=?", (key,)
        ).fetchone()
        self.assertEqual((row["state"], row["attempts"], row["dispatch_started_at"]),
                         ("PENDING", 0, ""))
        self.assertEqual(outbox.effect_count(), 0)

    def test_01_changed_embedded_payload_does_not_claim_with_original_digest(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, _second = self._fixture(directory)
            try:
                self._rewrite_embedded_payload(
                    outbox, first["decision_id"],
                    {"test_only": False, "nested": {"priority": "high", "items": [1, 2]}},
                )
                self._assert_denied_without_claim(outbox, first["idempotency_key"])
            finally:
                store.close()

    def test_02_nested_payload_mutations_each_fail_without_claim(self):
        variants = [
            {"test_only": True, "nested": {"priority": "low", "items": [1, 99]}},
            {"test_only": True, "nested": {"priority": "low", "items": [1, 2, 3]}},
            {"test_only": True, "nested": {"priority": "low", "items": [1, 2]},
             "forged_extra": True},
            {"test_only": True, "nested": {"priority": "low"}},
        ]
        for index, forged in enumerate(variants):
            with self.subTest(index=index):
                with TemporaryDirectory() as directory:
                    store, outbox, first, _second = self._fixture(directory)
                    try:
                        self._rewrite_embedded_payload(
                            outbox, first["decision_id"], forged,
                        )
                        self._assert_denied_without_claim(
                            outbox, first["idempotency_key"]
                        )
                    finally:
                        store.close()

    def test_03_absent_or_non_object_payload_never_claims(self):
        variants = [(False, None), (False, []), (False, "forged"), (True, None)]
        for remove, forged in variants:
            with self.subTest(remove=remove, forged=forged):
                with TemporaryDirectory() as directory:
                    store, outbox, first, _second = self._fixture(directory)
                    try:
                        self._rewrite_embedded_payload(
                            outbox, first["decision_id"], forged, remove=remove,
                        )
                        self._assert_denied_without_claim(
                            outbox, first["idempotency_key"]
                        )
                    finally:
                        store.close()

    def test_04_intact_nested_payload_still_claims_locally_only(self):
        with TemporaryDirectory() as directory:
            store = SQLiteChatStore(Path(directory) / "a344-nested.sqlite3")
            outbox = ExecutionOutbox(store, SCOPE)
            try:
                first = self._enqueue(
                    outbox, "a344-legitimate-nested",
                    payload={
                        "nested": {"steps": ["one", "two"], "metrics": {"count": 2}},
                        "tuple_normalized_to_json_list": ("x", "y"),
                        "null_value": None,
                    },
                )
                claimed = outbox.claim_next(
                    "a344-local-only", now=NOW + timedelta(seconds=1)
                )
                self.assertEqual(claimed["idempotency_key"], first["idempotency_key"])
                self.assertEqual(claimed["state"], "CLAIMED")
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_05_independent_tenant_can_claim_while_tampered_tenant_denied(self):
        with TemporaryDirectory() as directory:
            store, outbox, first, _second = self._fixture(directory)
            try:
                self._rewrite_embedded_payload(
                    outbox, first["decision_id"], {"test_only": False},
                )
                other = ExecutionOutbox(
                    store, Scope("a344-owner", "a344-other-tenant", "a344-workspace")
                )
                independent = self._enqueue(other, "a344-other-tenant-first")
                claimed = other.claim_next(
                    "a344-other-worker", now=NOW + timedelta(seconds=1)
                )
                self.assertEqual(claimed["idempotency_key"], independent["idempotency_key"])
                self.assertEqual(other.effect_count(), 0)
                self._assert_denied_without_claim(outbox, first["idempotency_key"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
