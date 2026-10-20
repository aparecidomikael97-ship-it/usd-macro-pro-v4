"""P0 LAB: duplicated JSON keys can split SQLite json_extract and Python json.loads.

Uses actual SQLiteChatStore/ExecutionOutbox, scoped disposable SQLite files and
no adapter or external effect. RED is expected before candidate patch.
All tests that pass still do NOT authorize producer, witness, H0 or main merge.
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

NOW = datetime(2026, 10, 20, 17, 0, tzinfo=timezone.utc)
SCOPE = Scope("dupe-key-owner", "dupe-key-tenant", "dupe-key-space")


class RealOutboxJSONSplitViewLAB(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(prefix="aion-json-splitview-")
        self.addCleanup(self.t.cleanup)
        self.store = SQLiteChatStore(Path(self.t.name) / "split.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)

    def add(self, ref="lab-intent"):
        return self.outbox.enqueue(
            intent_ref=ref, action="synthetic-no-provider",
            payload={"actor": "lab", "amount": 1},
            aggregate_key=ref, policy_version="test-only",
            authorization_ref="untrusted-test-authorization",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )

    def tamper_raw(self, key, modifier):
        with self.outbox.db:
            row = self.outbox.db.execute(
                "SELECT d.data FROM action_decisions d "
                "JOIN action_outbox o ON o.decision_id=d.decision_id "
                "WHERE o.idempotency_key=?", (key,),
            ).fetchone()
            after = modifier(row[0])
            self.assertNotEqual(after, row[0])
            self.outbox.db.execute(
                "UPDATE action_decisions SET data=? WHERE decision_id="
                "(SELECT decision_id FROM action_outbox WHERE idempotency_key=?)",
                (after, key),
            )
        return after

    def poison_duplicate(self, key, field, extra_json):
        def inject(raw):
            needle = f'"{field}":'
            pos = raw.index(needle)
            decoder = json.JSONDecoder()
            first, length = decoder.raw_decode(raw[pos + len(needle):])
            offset = pos + len(needle) + length
            # Insert duplicate *after* the original. SQLite json_extract uses
            # the first value; Python json.loads retains the LAST value.
            return raw[:offset] + f',"{field}":{extra_json}' + raw[offset:]
        after = self.tamper_raw(key, inject)
        self.assertEqual(
            self.outbox.db.execute(
                "SELECT json_valid(?)", (after,),
            ).fetchone()[0], 1,
        )
        return after

    def assert_no_local_claim(self, key):
        self.assertIsNone(self.outbox.claim_next("test-not-worker", now=NOW + timedelta(seconds=1)))
        row = self.outbox.db.execute(
            "SELECT state,attempts,lease_owner,lease_until FROM action_outbox "
            "WHERE idempotency_key=?", (key,),
        ).fetchone()
        self.assertEqual(tuple(row), ("PENDING", 0, "", ""))
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_01_duplicate_owner_python_last_differs_from_sqlite_first(self):
        key = self.add()["idempotency_key"]
        raw = self.poison_duplicate(key, "owner_id", '"not-the-real-owner"')
        self.assertEqual(json.loads(raw)["owner_id"], "not-the-real-owner")
        self.assertEqual(self.outbox.db.execute(
            "SELECT json_extract(?,'$.owner_id')", (raw,),
        ).fetchone()[0], SCOPE.owner_id)
        self.assert_no_local_claim(key)

    def test_02_duplicate_valid_until_cannot_shadow_expiration(self):
        key = self.add()["idempotency_key"]
        raw = self.poison_duplicate(key, "valid_until", '"2026-10-20T16:00:00+00:00"')
        self.assertTrue(json.loads(raw)["valid_until"].startswith("2026-10-20T16"))
        self.assert_no_local_claim(key)

    def test_03_duplicate_aggregate_seq_cannot_change_queue_ordinal(self):
        key = self.add()["idempotency_key"]
        raw = self.poison_duplicate(key, "aggregate_seq", "2")
        self.assertEqual(json.loads(raw)["aggregate_seq"], 2)
        self.assert_no_local_claim(key)

    def test_04_duplicate_idempotency_key_cannot_rebind_python_decision(self):
        key = self.add()["idempotency_key"]
        raw = self.poison_duplicate(key, "idempotency_key", '"' + "0"*64 + '"')
        self.assertEqual(json.loads(raw)["idempotency_key"], "0"*64)
        self.assert_no_local_claim(key)

    def test_05_payload_modified_without_digest_update_is_rejected(self):
        key = self.add()["idempotency_key"]
        def alter(raw):
            d = json.loads(raw)
            d["payload"]["amount"] = 900
            return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.tamper_raw(key, alter)
        self.assert_no_local_claim(key)

    def test_06_coordinated_action_column_and_json_change_cannot_rebind_key(self):
        key = self.add()["idempotency_key"]
        def alter(raw):
            d = json.loads(raw)
            d["action"] = "synthetic-other-action"
            return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        after = self.tamper_raw(key, alter)
        with self.outbox.db:
            self.outbox.db.execute(
                "UPDATE action_decisions SET action=? WHERE decision_id="
                "(SELECT decision_id FROM action_outbox WHERE idempotency_key=?)",
                (json.loads(after)["action"], key),
            )
        self.assert_no_local_claim(key)

    def test_07_valid_json_with_extra_noncanonical_whitespace_is_rejected(self):
        key = self.add()["idempotency_key"]
        self.tamper_raw(key, lambda raw: " " + raw)
        self.assert_no_local_claim(key)

    def test_08_canonical_and_intact_decision_remains_locally_claimable(self):
        key = self.add()["idempotency_key"]
        row = self.outbox.claim_next("test-not-worker", now=NOW + timedelta(seconds=1))
        self.assertEqual(row["idempotency_key"], key)
        self.assertEqual(row["state"], "CLAIMED")
        self.assertEqual(row["attempts"], 1)
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
