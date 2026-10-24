"""G43 read-only auditor no store construction, no repair or customer content."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from g43_projection_readonly_auditor_lab import audit_projection_snapshot_readonly_lab

SCOPE=Scope("g43-audit-owner","g43-audit-tenant","g43-audit-space")
NOW=datetime(2026,10,24,17,tzinfo=timezone.utc)

class G43ReadOnlyAuditor(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g43-readonly-")
        self.addCleanup(tmp.cleanup)
        self.file=Path(tmp.name)/"storage.sqlite3"
        self.store=SQLiteChatStore(self.file)
        self.addCleanup(lambda:self.store.close())
        self.outbox=ExecutionOutbox(self.store,SCOPE)
        item=self.outbox.enqueue(
            intent_ref="synthetic-request",
            action="synthetic_no_provider",
            payload={"amount_minor":1000,"private_data":"not-in-report"},
            aggregate_key="synthetic-aggregate",
            policy_version="p1",authorization_ref="a1",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5))
        self.key=item["idempotency_key"]

    def scan(self,**scope):
        s={"owner":SCOPE.owner_id,"tenant":SCOPE.tenant_id,
           "workspace":SCOPE.workspace_id}
        s.update(scope)
        return audit_projection_snapshot_readonly_lab(self.file,**s)

    def code(self):
        return self.scan()["findings"][0]["issue"]

    def update(self,expr,args=()):
        self.store.db.execute(
            "UPDATE action_outbox SET "+expr+" WHERE idempotency_key=?",
            (*args,self.key))
        self.store.db.commit()

    def test_01_mode_ro_does_not_change_database_bytes(self):
        before=sha256(self.file.read_bytes()).hexdigest()
        found=self.scan()
        after=sha256(self.file.read_bytes()).hexdigest()
        self.assertEqual(before,after)
        self.assertEqual(found["row_count"],1)
        self.assertEqual(self.code(),"OK")
        self.assertNotIn("private_data",json.dumps(found))
        print("G43_STANDALONE_RO_GREEN=READONLY_OPEN_NO_STORE_BOOTSTRAP")

    def test_02_pure_state_drift_classified_not_repaired(self):
        self.update("state='UNCERTAIN'")
        old=self.store.db.execute(
            "SELECT data FROM action_outbox WHERE idempotency_key=?",
            (self.key,)).fetchone()[0]
        self.assertEqual(self.code(),"PROJECTION_DRIFT")
        self.assertEqual(self.store.db.execute(
            "SELECT data FROM action_outbox WHERE idempotency_key=?",
            (self.key,)).fetchone()[0],old)
        print("G43_STANDALONE_DRIFT_GREEN=ANOMALY_CLASSIFIED_NO_MUTATION")

    def test_03_malformed_json_classified(self):
        self.update("data='synthetic-not-json'")
        self.assertEqual(self.code(),"INVALID_JSON")

    def test_04_json_array_classified(self):
        self.update("data='[]'")
        self.assertEqual(self.code(),"JSON_NOT_OBJECT")

    def test_05_forged_identity_classified(self):
        doc=json.loads(self.store.db.execute(
            "SELECT data FROM action_outbox WHERE idempotency_key=?",
            (self.key,)).fetchone()[0])
        doc["decision_id"]="forged-id"
        self.update("data=?", (json.dumps(doc),))
        self.assertEqual(self.code(),"JSON_IDENTITY_MISMATCH")

    def test_06_confirmed_without_ledger_classified(self):
        self.update("state='CONFIRMED',effect_ref='synthetic-ref',confirmed_at='test'")
        self.assertEqual(self.code(),"CONFIRMED_LEDGER_INCONSISTENT")

    def test_07_wrong_scope_returns_no_rows(self):
        result=self.scan(workspace="unrelated-workspace")
        self.assertEqual(result["row_count"],0)
        self.assertEqual(result["findings"],[])

    def test_08_missing_file_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,"G43_AUDIT_FILE_ABSENT"):
            audit_projection_snapshot_readonly_lab(
                self.file.parent/"missing.sqlite3",owner=SCOPE.owner_id,
                tenant=SCOPE.tenant_id,workspace=SCOPE.workspace_id)

    def test_09_nonconfirmed_effect_is_classified(self):
        self.store.db.execute(
            """INSERT INTO action_effects
               (idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data)
               VALUES(?,?,?,?,?,?,?)""",
            (self.key,SCOPE.owner_id,SCOPE.tenant_id,SCOPE.workspace_id,
             "synthetic-effect","synthetic-at","{}"))
        self.store.db.commit()
        self.assertEqual(self.code(),"NONCONFIRMED_HAS_EFFECT")

    def test_10_scan_does_not_repair_after_reopen(self):
        self.update("state='UNCERTAIN'")
        self.store.close()
        self.store=SQLiteChatStore(self.file)
        self.assertEqual(self.code(),"PROJECTION_DRIFT")
        self.assertEqual(self.scan()["schema"],
                         "AION-A190-G43-READONLY-AUDIT-V1")

if __name__=="__main__":
    unittest.main()
