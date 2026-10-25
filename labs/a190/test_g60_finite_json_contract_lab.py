"""G60 synthetic LAB: finite JSON contract at admission and history parsing.

Tests committed before any candidate Outbox code change, disposable SQLite.
No provider/Worker/external receipts/customers/credentials/money or SEND.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json, math, tempfile, unittest
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,25,23,tzinfo=timezone.utc)
SCOPE=Scope("g60-owner","g60-tenant","g60-workspace")


class G60FiniteJSON(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g60-local-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"synthetic.sqlite3")
        self.addCleanup(self.store.close)
        self.box=ExecutionOutbox(self.store,SCOPE)

    def stage(self, *, name="g60-request", event="g60-event", extra=None, box=None):
        payload={"amount_minor":23, "business_event_id":event} if event else {"amount_minor":23}
        if extra:
            payload.update(extra)
        return (box or self.box).enqueue(
            intent_ref=name, action="synthetic_no_provider",
            payload=payload, aggregate_key="g60-aggregate",
            policy_version="p1", authorization_ref="local-only",
            created_at=NOW, valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=event or "")

    def count(self):
        return self.store.db.execute("SELECT COUNT(*) FROM action_outbox").fetchone()[0]

    def lock_count(self):
        return self.store.db.execute("SELECT COUNT(*) FROM semantic_reservations_lab").fetchone()[0]

    def assert_reject_new(self, *, extra, event="g60-event"):
        before=(self.count(),self.lock_count())
        with self.assertRaisesRegex(ValueError,"G60_NONFINITE_PAYLOAD_DENY"):
            self.stage(extra=extra,event=event)
        self.assertEqual((self.count(),self.lock_count()),before)
        self.assertFalse(self.store.db.in_transaction)

    def test_01_nan_with_semantic_event_denied_before_write(self):
        self.assert_reject_new(extra={"score":float("nan")})
        print("G60_NAN_GREEN=NO_ADMISSION")

    def test_02_positive_infinity_with_event_denied(self):
        self.assert_reject_new(extra={"ratio":float("inf")})
        print("G60_POS_INF_GREEN=NO_ADMISSION")

    def test_03_negative_infinity_nested_denied(self):
        self.assert_reject_new(extra={"nested":[{"p":-float("inf")}]})
        print("G60_NEG_INF_GREEN=NO_ADMISSION")

    def test_04_nan_without_event_also_denied(self):
        self.assert_reject_new(extra={"unlabeled":float("nan")},event=None)
        print("G60_LEGACY_NAN_GREEN=NO_UNSAFE_WRITE")

    def test_05_ordinary_finite_nested_floats_remain_allowed(self):
        a=self.stage(extra={"scores":[0.0,1.25,-2.5,1.0e25]})
        self.assertEqual(a["enqueue_state"],"ENQUEUED")
        b=self.stage(extra={"scores":[0.0,1.25,-2.5,1.0e25]})
        self.assertEqual(b["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(self.count(),1)
        self.assertEqual(self.lock_count(),1)
        print("G60_FINITE_GREEN=STILL_IDEMPOTENT")

    def test_06_string_nan_is_not_numeric_nan(self):
        got=self.stage(extra={"code":"NaN","display":"Infinity"})
        self.assertEqual(got["enqueue_state"],"ENQUEUED")

    def poison_historical(self,field):
        self.stage()
        row=self.store.db.execute("SELECT decision_id,data FROM action_decisions").fetchone()
        raw='{"'+field+'":1e999,'+row["data"][1:]
        self.store.db.execute(
            "UPDATE action_decisions SET data=? WHERE decision_id=?",
            (raw,row["decision_id"]))
        self.store.db.commit()
        return raw

    def deny_historical(self, *, field="auxiliary"):
        raw=self.poison_historical(field)
        self.assertIn("1e999",raw)
        old=(self.count(),self.lock_count())
        with self.assertRaisesRegex(RuntimeError,"G58_HISTORICAL_JSON_UNTRUSTED_DENY"):
            self.stage(name="unrelated-request",event="independent-event")
        self.assertEqual((self.count(),self.lock_count()),old)
        self.assertFalse(self.store.db.in_transaction)

    def test_07_historical_exponent_overflow_denied(self):
        self.deny_historical()
        print("G60_OVERFLOW_HISTORY_GREEN=NO_SILENT_INF")

    def test_08_historical_negative_exponent_overflow_denied(self):
        self.stage()
        row=self.store.db.execute("SELECT decision_id,data FROM action_decisions").fetchone()
        raw='{"overflow":-1e999,'+row["data"][1:]
        self.store.db.execute(
            "UPDATE action_decisions SET data=? WHERE decision_id=?",
            (raw,row["decision_id"]))
        self.store.db.commit()
        with self.assertRaisesRegex(RuntimeError,"G58_HISTORICAL_JSON_UNTRUSTED_DENY"):
            self.stage(name="new-request",event="independent-event")
        self.assertEqual(self.count(),1)

    def test_09_historical_small_exponent_is_finite(self):
        self.stage()
        row=self.store.db.execute("SELECT decision_id,data FROM action_decisions").fetchone()
        raw='{"finite_auxiliary":1e-100,'+row["data"][1:]
        self.store.db.execute(
            "UPDATE action_decisions SET data=? WHERE decision_id=?",
            (raw,row["decision_id"]))
        self.store.db.commit()
        got=self.stage(name="new-request",event="independent-event")
        self.assertEqual(got["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.count(),2)

    def test_10_existing_legacy_nan_history_still_denied(self):
        self.stage()
        row=self.store.db.execute("SELECT decision_id,data FROM action_decisions").fetchone()
        raw='{"legacy_nan":NaN,'+row["data"][1:]
        self.store.db.execute(
            "UPDATE action_decisions SET data=? WHERE decision_id=?",
            (raw,row["decision_id"]))
        self.store.db.commit()
        with self.assertRaisesRegex(RuntimeError,"G58_HISTORICAL_JSON_UNTRUSTED_DENY"):
            self.stage(name="new-request",event="independent-event")
        self.assertEqual(self.count(),1)
        print("G60_LEGACY_BAD_GREEN=QUARANTINE_NOT_REPAIR")

    def test_11_foreign_tenant_overflow_not_read_for_this_tenant(self):
        foreign=ExecutionOutbox(self.store,Scope("foreign","other-tenant","other-space"))
        self.stage(box=foreign)
        row=self.store.db.execute(
            "SELECT decision_id,data FROM action_decisions WHERE tenant='other-tenant'").fetchone()
        raw='{"foreign_aux":1e999,'+row["data"][1:]
        self.store.db.execute(
            "UPDATE action_decisions SET data=? WHERE decision_id=?",
            (raw,row["decision_id"]))
        self.store.db.commit()
        got=self.stage(name="new-local-request")
        self.assertEqual(got["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.count(),2)
        print("G60_TENANT_ISOLATION_GREEN=NO_FOREIGN_SCAN")


if __name__=="__main__":
    unittest.main()
