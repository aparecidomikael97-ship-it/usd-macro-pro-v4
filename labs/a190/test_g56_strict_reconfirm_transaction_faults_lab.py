"""G56 LAB: transaction failure matrix on G55 strict idempotent _confirm.

SQLite is disposable. No external provider, send, worker, real receipt or
customer data. These synthetic tests reuse vetted G31/G33/G35 fault proxies.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_g31_transaction_quarantine_lab import FaultDB
from test_g33_outbox_ambiguous_commit_lab import AmbiguousCommit
from test_g35_begin_ack_process_crash_lab import BeginFaultProxy

NOW = datetime(2026,10,25,23,tzinfo=timezone.utc)
SCOPE = Scope("g56-owner","g56-tenant","g56-space")
REF = "g56-synthetic-local-receipt"
AT = NOW+timedelta(minutes=1)


class G56StrictConfirmFailureMatrix(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="a190-g56-")
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"disposable.sqlite3"
        self.store=SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE,strict_projection_lab=True)
        self.key=self.outbox.enqueue(
            intent_ref="g56-disposable",action="synthetic-no-network",
            payload={"amount_minor":1},aggregate_key="g56-test",
            policy_version="p1",authorization_ref="g56-fake",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5)
        )["idempotency_key"]
        self.store.db.execute(
            "UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",
            (self.key,))
        self.store.db.commit()
        self.outbox._confirm(self.key,effect_ref=REF,confirmed_at=AT,
                             result={"receipt":"synthetic"})
        self.raw=self.store.db
        self.clean_snapshot=self._snapshot(self.store.db)
        self.assertEqual(self.clean_snapshot[0][0],"CONFIRMED")

    def _snapshot(self,db):
        row=db.execute(
            "SELECT state,confirmed_at,effect_ref,data FROM action_outbox "
            "WHERE idempotency_key=?",(self.key,)).fetchone()
        effects=db.execute(
            "SELECT effect_ref,confirmed_at,data FROM action_effects "
            "WHERE idempotency_key=?",(self.key,)).fetchall()
        return tuple(row),tuple(tuple(x) for x in effects)

    def _assert_disk_snapshot(self,expected=None):
        other=SQLiteChatStore(self.path)
        try:
            snap=self._snapshot(other.db)
            self.assertEqual(snap,expected or self.clean_snapshot)
            self.assertEqual(len(snap[1]),1)
            return snap
        finally:
            other.close()

    def _confirm_again(self):
        return self.outbox._confirm(
            self.key,effect_ref=REF,confirmed_at=NOW+timedelta(hours=5),
            result={"replay":"synthetic-only"})

    def _assert_quarantine(self):
        self.assertIsNone(self.outbox.db)
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store.storage_health()["state"],"failed")
        with self.assertRaises(StorageUnavailableError):
            self.store.require_healthy()
        with self.assertRaises(StorageUnavailableError):
            ExecutionOutbox(self.store,SCOPE)

    def _inject(self,proxy):
        self.store.db=proxy
        self.outbox.db=proxy
        return proxy

    def _corrupt_projection(self):
        doc=json.loads(self.clean_snapshot[0][3])
        doc["state"]="UNCERTAIN"
        self.raw.execute("UPDATE action_outbox SET data=? WHERE idempotency_key=?",
                         (json.dumps(doc),self.key))
        self.raw.commit()
        return self._snapshot(self.raw)

    def test_01_healthy_strict_idempotent_reconfirm_changes_nothing(self):
        got=self._confirm_again()
        self.assertEqual(got["state"],"CONFIRMED")
        self.assertEqual(got["confirmed_at"],AT.isoformat())
        self.assertEqual(self._snapshot(self.raw),self.clean_snapshot)
        self.assertFalse(self.raw.in_transaction)
        print("G56_HEALTHY_REPLAY_GREEN=ZERO_LEDGER_REWRITE")

    def test_02_commit_error_before_durability_quarantines_without_rollback(self):
        proxy=self._inject(AmbiguousCommit(self.raw,after=False))
        with self.assertRaisesRegex(OSError,"G33_OUTBOX_COMMIT_ACK_UNKNOWN") as c:
            self._confirm_again()
        self.assertEqual(proxy.commits,1)
        self.assertEqual(proxy.rollbacks,0)
        self.assertEqual(proxy.closes,1)
        self._assert_quarantine()
        self.assertTrue(any("COMMIT_OUTCOME_UNCERTAIN" in x
                            for x in getattr(c.exception,"__notes__",[])))
        self._assert_disk_snapshot()
        print("G56_PRECOMMIT_GREEN=QUARANTINE_NO_RETRY")

    def test_03_commit_error_after_durability_quarantines_without_rollback(self):
        proxy=self._inject(AmbiguousCommit(self.raw,after=True))
        with self.assertRaisesRegex(OSError,"G33_OUTBOX_COMMIT_ACK_UNKNOWN") as c:
            self._confirm_again()
        self.assertEqual(proxy.commits,1)
        self.assertEqual(proxy.rollbacks,0)
        self.assertEqual(proxy.closes,1)
        self._assert_quarantine()
        self.assertTrue(any("COMMIT_OUTCOME_UNCERTAIN" in x
                            for x in getattr(c.exception,"__notes__",[])))
        self._assert_disk_snapshot()
        print("G56_POSTCOMMIT_GREEN=ORIGINAL_RECEIPT_STILL_DURABLE")

    def test_04_begin_error_before_lock_quarantines_no_rollback(self):
        proxy=self._inject(BeginFaultProxy(self.raw,after=False))
        with self.assertRaisesRegex(OSError,"G35_BEGIN_ACK_UNKNOWN") as c:
            self._confirm_again()
        self.assertEqual(proxy.begins,1)
        self.assertEqual(proxy.rollbacks,0)
        self.assertEqual(proxy.closes,1)
        self._assert_quarantine()
        self.assertTrue(any("BEGIN_OUTCOME_UNCERTAIN" in x
                            for x in getattr(c.exception,"__notes__",[])))
        self._assert_disk_snapshot()
        print("G56_BEGIN_BEFORE_GREEN=NO_RETRY_NO_REPAIR")

    def test_05_begin_ack_lost_after_lock_quarantines_no_rollback(self):
        proxy=self._inject(BeginFaultProxy(self.raw,after=True))
        with self.assertRaisesRegex(OSError,"G35_BEGIN_ACK_UNKNOWN") as c:
            self._confirm_again()
        self.assertEqual(proxy.begins,1)
        self.assertEqual(proxy.rollbacks,0)
        self.assertEqual(proxy.closes,1)
        self._assert_quarantine()
        self.assertTrue(any("BEGIN_OUTCOME_UNCERTAIN" in x
                            for x in getattr(c.exception,"__notes__",[])))
        self._assert_disk_snapshot()
        print("G56_BEGIN_AFTER_GREEN=NO_FALSE_NEGATIVE")

    def test_06_integrity_error_then_rollback_failure_keeps_primary(self):
        poisoned=self._corrupt_projection()
        proxy=self._inject(FaultDB(
            self.raw,trigger="G56_INTERCEPT_DISABLED",rollback_fails=True))
        with self.assertRaisesRegex(
                RuntimeError,"G55_CONFIRMED_PROJECTION_INTEGRITY_DENY") as c:
            self._confirm_again()
        self.assertEqual(proxy.rollbacks,1)
        self.assertIsInstance(c.exception.__cause__,OSError)
        self.assertIn("G31_SECONDARY_ROLLBACK_FAILURE",
                      str(c.exception.__cause__))
        self.assertTrue(any("ROLLBACK_FAILED_STORE_QUARANTINED" in x
                            for x in getattr(c.exception,"__notes__",[])))
        self._assert_quarantine()
        self._assert_disk_snapshot(poisoned)
        print("G56_ROLLBACK_FAILED_GREEN=PRIMARY_ERROR_AND_QUARANTINE")

    def test_07_integrity_error_then_successful_rollback_keeps_store(self):
        poisoned=self._corrupt_projection()
        proxy=self._inject(FaultDB(
            self.raw,trigger="G56_INTERCEPT_DISABLED",rollback_fails=False))
        with self.assertRaisesRegex(
                RuntimeError,"G55_CONFIRMED_PROJECTION_INTEGRITY_DENY"):
            self._confirm_again()
        self.assertEqual(proxy.rollbacks,1)
        self.assertIs(self.store.db,proxy)
        self.assertIs(self.outbox.db,proxy)
        self.assertFalse(self.raw.in_transaction)
        self.assertEqual(self._snapshot(self.raw),poisoned)
        self.assertEqual(self.store.storage_health()["state"],"healthy")
        print("G56_ROLLBACK_OK_GREEN=INTEGRITY_DENY_NO_REPAIR")

    def test_08_postcommit_reopen_does_not_grant_adapter_authority(self):
        proxy=self._inject(AmbiguousCommit(self.raw,after=True))
        with self.assertRaises(OSError):
            self._confirm_again()
        self._assert_quarantine()
        store=SQLiteChatStore(self.path)
        try:
            outbox=ExecutionOutbox(store,SCOPE)
            self.assertEqual(outbox.get(self.key)["state"],"CONFIRMED")
            self.assertEqual(outbox.effect_count(),1)
            class ForbiddenAdapter:
                @property
                def send(self):
                    raise AssertionError("NO_PROVIDER_SEND_ALLOWED")
                @property
                def reconcile(self):
                    raise AssertionError("NO_PROVIDER_LOOKUP_ALLOWED")
            # Reopening a local store does not automatically invoke callbacks.
            self.assertFalse(outbox._synthetic_lab_callbacks_enabled)
            self.assertEqual(outbox.get(self.key)["effect_ref"],REF)
            self.assertEqual(self._snapshot(store.db),self.clean_snapshot)
            print("G56_REOPEN_GREEN=STILL_NO_EXTERNAL_AUTHORITY")
        finally:
            store.close()

if __name__=="__main__":
    unittest.main()
