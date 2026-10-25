"""G55: strict projection must reject a tampered CONFIRMED JSON on re-confirm.

Disposable SQLite, local synthetic receipts only; no worker/provider or money.
Falsifiable tests committed before any candidate source modification.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 25, 20, tzinfo=timezone.utc)
SCOPE = Scope("g55-owner", "g55-tenant", "g55-workspace")
REF = "synthetic-g55-receipt"
TS0 = NOW + timedelta(minutes=1)


class G55StrictProjectionReconfirm(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="g55-projection-")
        self.addCleanup(temp.cleanup)
        self.file = Path(temp.name) / "synthetic.sqlite3"
        self.store = SQLiteChatStore(self.file)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(
            self.store, SCOPE, strict_projection_lab=True,
        )
        self.key = self.outbox.enqueue(
            intent_ref="synthetic-intent-55",
            action="no_external_provider",
            payload={"amount_minor": 55},
            aggregate_key="g55-only",
            policy_version="p1",
            authorization_ref="fake-local-auth",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )["idempotency_key"]
        self.store.db.execute(
            "UPDATE action_outbox SET state='UNCERTAIN' "
            "WHERE idempotency_key=?", (self.key,),
        )
        self.store.db.commit()
        self.outbox._confirm(
            self.key, effect_ref=REF, confirmed_at=TS0,
            result={"synthetic": True},
        )
        self.assertEqual(self.outbox.get(self.key)["state"],"CONFIRMED")

    def snapshot(self):
        row = self.store.db.execute(
            "SELECT data,confirmed_at,effect_ref,state FROM action_outbox "
            "WHERE idempotency_key=?", (self.key,)
        ).fetchone()
        receipts = self.store.db.execute(
            "SELECT effect_ref,confirmed_at,data FROM action_effects "
            "WHERE idempotency_key=?", (self.key,)
        ).fetchall()
        return (tuple(row), tuple(tuple(x) for x in receipts))

    def corrupt(self, update):
        row = self.store.db.execute(
            "SELECT data FROM action_outbox WHERE idempotency_key=?",
            (self.key,),
        ).fetchone()
        data=json.loads(row["data"])
        update(data)
        self.store.db.execute(
            "UPDATE action_outbox SET data=? WHERE idempotency_key=?",
            (json.dumps(data,sort_keys=True,separators=(",",":")),self.key),
        )
        self.store.db.commit()

    def replace_raw(self, raw):
        self.store.db.execute(
            "UPDATE action_outbox SET data=? WHERE idempotency_key=?",
            (raw,self.key),
        )
        self.store.db.commit()

    def repeat(self):
        return self.outbox._confirm(
            self.key, effect_ref=REF, confirmed_at=NOW+timedelta(hours=4),
            result={"synthetic":"reconfirmation-no-write"},
        )

    def assert_denial(self, expected="G55_CONFIRMED_PROJECTION_INTEGRITY_DENY"):
        before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,expected):
            self.repeat()
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(len(before[1]),1)
        self.assertFalse(self.store.db.in_transaction)

    def test_01_clean_projection_reconfirmation_is_idempotent(self):
        before=self.snapshot()
        result=self.repeat()
        self.assertEqual(result["confirmed_at"],TS0.isoformat())
        self.assertEqual(self.snapshot(),before)
        self.assertFalse(self.store.db.in_transaction)
        print("G55_CLEAN_RECONFIRM_GREEN=EXACTLY_ONE_LOCAL_RECEIPT")

    def test_02_forged_confirmed_projection_state_denied_not_repaired(self):
        self.corrupt(lambda d:d.update(state="UNCERTAIN"))
        self.assert_denial()
        print("G55_PROJECTED_STATE_GREEN=DENY_NO_REPAIR")

    def test_03_changed_attempt_generation_denied_not_repaired(self):
        self.corrupt(lambda d:d.update(attempts=99))
        self.assert_denial()

    def test_04_changed_json_identity_denied_not_repaired(self):
        self.corrupt(lambda d:d.update(decision_id="fake-foreign-decision"))
        self.assert_denial("G43_PROJECTION_IDENTITY_MISMATCH_DENY")

    def test_05_malformed_json_denied_and_transaction_closed(self):
        self.replace_raw("{synthetic corrupted json")
        self.assert_denial("G43_PROJECTION_INVALID_JSON_DENY")
        print("G55_INVALID_JSON_GREEN=NO_REPAIR")

    def test_06_duplicated_json_key_denied_not_collapsed(self):
        before=self.snapshot()
        original=before[0][0]
        raw='{"state":"REVOKED",'+original[1:]
        self.replace_raw(raw)
        self.assert_denial()

    def test_07_clean_projection_never_changes_original_ledger_time(self):
        original=self.snapshot()
        self.repeat()
        self.repeat()
        self.assertEqual(self.snapshot(),original)
        self.assertEqual(original[1][0][1],TS0.isoformat())
        print("G55_LOCAL_TIMESTAMP_GREEN=ORIGINAL_PRESERVED")

    def test_08_confirmed_ledger_conflict_still_denied(self):
        self.store.db.execute(
            "UPDATE action_effects SET confirmed_at='1999-01-01T00:00:00+00:00' "
            "WHERE idempotency_key=?",(self.key,),
        )
        self.store.db.commit()
        self.assert_denial("G42_CONFIRMED_LEDGER_INVARIANT_DENY")

if __name__=="__main__":
    unittest.main()
