"""G59 LAB: reject tampered historical event identity and an orphan Outbox.

Tests first, before patch. Synthetic disposable SQLite, no provider, SEND,
Worker, customer information, credentials, funds or external authority.
"""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,25,22,tzinfo=timezone.utc)
SCOPE=Scope("g59-owner","g59-tenant","g59-space")
E="g59-declared-synthetic-event"


class G59HistoricalBindingOrphans(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(prefix="a190-g59-")
        self.addCleanup(folder.cleanup)
        self.store=SQLiteChatStore(Path(folder.name)/"ephemeral.sqlite3")
        self.addCleanup(self.store.close)
        self.box=ExecutionOutbox(self.store,SCOPE)

    def stage(self,request="req-A",event=E,outbox=None):
        return (outbox or self.box).enqueue(
            intent_ref=request,action="synthetic_only",
            payload={"business_event_id":event,"amount_minor":123},
            aggregate_key="g59-aggregate",policy_version="p1",
            authorization_ref="g59-fake-local",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=event)

    def missing_lock(self):
        self.store.db.execute(
            "DELETE FROM semantic_reservations_lab WHERE tenant=?",(SCOPE.tenant_id,))
        self.store.db.commit()

    def snapshot(self):
        return tuple(
            tuple(tuple(row) for row in
                  self.store.db.execute("SELECT * FROM "+tbl+" ORDER BY 1"))
            for tbl in ("action_decisions","action_outbox","semantic_reservations_lab","action_effects")
        )

    def deny(self,code="G59_HISTORICAL_BINDING_DENY",event=E):
        old=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,code):
            self.stage("req-B",event=event)
        self.assertEqual(self.snapshot(),old)
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(
            self.store.db.execute("SELECT COUNT(*) FROM action_effects").fetchone()[0],0)

    def modify_decision_json(self,mutate):
        row=self.store.db.execute("SELECT decision_id,data FROM action_decisions").fetchone()
        doc=json.loads(row["data"])
        mutate(doc)
        self.store.db.execute(
            "UPDATE action_decisions SET data=? WHERE decision_id=?",
            (json.dumps(doc,sort_keys=True,separators=(",",":")),row["decision_id"]))
        self.store.db.commit()

    def test_01_genuine_same_event_with_missing_lock_remains_denied(self):
        self.stage()
        self.missing_lock()
        self.deny("G58_HISTORICAL_SEMANTIC_CUSTODY_DENY")

    def test_02_tamper_event_to_other_valid_token_cannot_hide_original(self):
        self.stage()
        self.missing_lock()
        self.modify_decision_json(
            lambda d:d["payload"].update(business_event_id="g59-forged-other-event"))
        self.deny()
        print("G59_TAMPER_RENAME_GREEN=HISTORICAL_DIGEST_MUST_BIND")

    def test_03_remove_event_field_cannot_hide_original(self):
        self.stage()
        self.missing_lock()
        self.modify_decision_json(lambda d:d["payload"].pop("business_event_id"))
        self.deny()
        print("G59_TAMPER_REMOVE_GREEN=HISTORICAL_DIGEST_MUST_BIND")

    def test_04_tamper_historical_idempotency_key_cannot_pass_scan(self):
        self.stage()
        self.missing_lock()
        self.modify_decision_json(lambda d:d.update(idempotency_key="a"*64))
        self.deny(event="other-independent-event")

    def test_05_payload_digest_column_mismatch_cannot_pass_scan(self):
        self.stage()
        self.missing_lock()
        self.store.db.execute(
            "UPDATE action_decisions SET payload_digest=? WHERE tenant=?",
            ("0"*64,SCOPE.tenant_id))
        self.store.db.commit()
        self.deny(event="other-independent-event")

    def test_06_outbox_survives_missing_decision_is_rejected(self):
        self.stage()
        self.missing_lock()
        # Emulate a previously corrupted store. The real operational path is
        # not allowed to delete linked decisions; never use this in production.
        self.store.db.execute("PRAGMA foreign_keys=OFF")
        self.store.db.execute(
            "DELETE FROM action_decisions WHERE tenant=?",(SCOPE.tenant_id,))
        self.store.db.commit()
        self.store.db.execute("PRAGMA foreign_keys=ON")
        self.assertEqual(
            self.store.db.execute("SELECT COUNT(*) FROM action_outbox").fetchone()[0],1)
        self.assertEqual(
            self.store.db.execute("SELECT COUNT(*) FROM action_decisions").fetchone()[0],0)
        before=self.snapshot()
        with self.assertRaises(StorageUnavailableError):
            self.stage("req-B")
        self.assertEqual(self.snapshot(),before)
        print("G59_ORPHAN_OUTBOX_GREEN=STORAGE_FOREIGN_KEY_GATE_ALREADY_DENIES")

    def test_07_legitimate_new_event_from_different_tenant_still_allowed(self):
        self.stage()
        self.missing_lock()
        other=ExecutionOutbox(self.store,Scope("g59-owner","other-tenant","other-workspace"))
        out=self.stage("req-B",outbox=other)
        self.assertEqual(out["enqueue_state"],"ENQUEUED")
        self.assertEqual(
            self.store.db.execute("SELECT COUNT(*) FROM action_outbox").fetchone()[0],2)

    def test_08_same_event_replay_with_intact_lock_preserved(self):
        a=self.stage()
        b=self.stage()
        self.assertEqual(a["idempotency_key"],b["idempotency_key"])
        self.assertEqual(b["enqueue_state"],"IDEMPOTENT")

    def test_09_historical_different_event_with_valid_binding_preserved(self):
        self.stage()
        self.missing_lock()
        b=self.stage("req-B",event="independent-declared-event")
        self.assertEqual(b["enqueue_state"],"ENQUEUED")
        self.assertEqual(
            self.store.db.execute("SELECT COUNT(*) FROM action_outbox").fetchone()[0],2)

    def test_10_corruption_of_other_tenant_does_not_block_isolated_event(self):
        foreign=ExecutionOutbox(self.store,Scope("foreign-owner","foreign-tenant","foreign-space"))
        self.stage(outbox=foreign)
        self.store.db.execute(
            "UPDATE action_decisions SET data=? WHERE tenant=?",
            ("broken-json","foreign-tenant"))
        self.store.db.commit()
        out=self.stage("req-B")
        self.assertEqual(out["enqueue_state"],"ENQUEUED")


    def coordinated_history_edit(self, *, change_semantic=False):
        from atlasquant_aion_execution_outbox import _digest
        row=self.store.db.execute(
            "SELECT decision_id,data FROM action_decisions").fetchone()
        d=json.loads(row["data"])
        d["payload"]["business_event_id"]="g59-forged-other-event"
        d["payload_digest"]=_digest(d["payload"])
        if change_semantic:
            d["semantic_event_id_lab"]="g59-forged-other-event"
        self.store.db.execute(
            "UPDATE action_decisions SET payload_digest=?,data=? WHERE decision_id=?",
            (d["payload_digest"],json.dumps(d,sort_keys=True,separators=(",",":")),
             row["decision_id"]))
        self.store.db.commit()

    def test_11_coordinated_digest_rewrite_without_semantic_change_denied(self):
        self.stage()
        self.missing_lock()
        self.coordinated_history_edit(change_semantic=False)
        self.deny(event=E)
        print("G59_COORDINATED_DIGEST_GREEN=SEMANTIC_FIELD_MUST_BIND")

    def test_12_coordinated_digest_and_semantic_rewrite_denied_by_key(self):
        self.stage()
        self.missing_lock()
        self.coordinated_history_edit(change_semantic=True)
        self.deny(event=E)
        print("G59_COORDINATED_SEMANTIC_GREEN=ORIGINAL_KEY_MUST_BIND")


if __name__=="__main__":
    unittest.main()
