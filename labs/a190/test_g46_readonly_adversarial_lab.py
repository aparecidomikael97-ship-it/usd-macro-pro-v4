"""G46 LAB: independent G43 read-only audit must not conceal anomalies.

Only synthetic disposable SQLite, no provider, Worker or external identity.
These tests reproduce old G43 false OK; no historical rewriting.
"""
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

NOW = datetime(2026,10,24,18,tzinfo=timezone.utc)
SCOPE = Scope("g46-owner","g46-tenant","g46-space")


class G46ReadOnlyAdversarial(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="a190-g46-")
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "synthetic.sqlite3"
        self.store = SQLiteChatStore(self.file)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE,
                                      strict_projection_lab=True)
        result = self.outbox.enqueue(
            intent_ref="synthetic-request", action="synthetic_no_provider",
            payload={"amount_minor":1000, "private_value":"do-not-emit"},
            aggregate_key="synthetic-group",policy_version="p1",
            authorization_ref="synthetic-approval",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
        )
        self.key = result["idempotency_key"]
        # G53: the synthetic receipt fixture must first be in a genuinely
        # reconcilable local phase. Never confirm directly from PENDING.
        self.store.db.execute(
            "UPDATE action_outbox SET state='UNCERTAIN' "
            "WHERE idempotency_key=?", (self.key,))
        self.store.db.commit()
        self.outbox._confirm(
            self.key,effect_ref="local-synthetic-reference",
            confirmed_at=NOW+timedelta(seconds=1),
        )

    def scan(self):
        return audit_projection_snapshot_readonly_lab(
            self.file, owner=SCOPE.owner_id, tenant=SCOPE.tenant_id,
            workspace=SCOPE.workspace_id)

    def document(self):
        row = self.store.db.execute(
            "SELECT data FROM action_outbox WHERE idempotency_key=?",
            (self.key,)).fetchone()
        return json.loads(row["data"])

    def replace_json(self, raw):
        self.store.db.execute(
            "UPDATE action_outbox SET data=? WHERE idempotency_key=?",
            (raw,self.key))
        self.store.db.commit()

    def cross_scope_outbox(self, column, value):
        if column not in ("owner","tenant","workspace"):
            raise ValueError("BAD_TEST_COLUMN")
        self.store.db.execute(
            "UPDATE action_outbox SET "+column+"=? "
            "WHERE idempotency_key=?", (value,self.key))
        self.store.db.commit()

    def test_01_valid_scoped_local_receipt_stays_ok(self):
        self.assertEqual(self.scan()["counts"], {"OK":1})

    def test_02_effect_is_orphan_when_outbox_owner_foreign(self):
        self.cross_scope_outbox("owner","foreign-owner")
        report=self.scan()
        self.assertEqual(report["row_count"],0)
        self.assertEqual(report["counts"],{"ORPHAN_EFFECT_ROWS":1})
        print("G46_ORPHAN_OWNER_GREEN=SCOPED_JOIN")

    def test_03_effect_is_orphan_when_outbox_tenant_foreign(self):
        self.cross_scope_outbox("tenant","foreign-tenant")
        self.assertEqual(self.scan()["counts"],{"ORPHAN_EFFECT_ROWS":1})
        print("G46_ORPHAN_TENANT_GREEN=SCOPED_JOIN")

    def test_04_effect_is_orphan_when_outbox_workspace_foreign(self):
        self.cross_scope_outbox("workspace","foreign-workspace")
        self.assertEqual(self.scan()["counts"],{"ORPHAN_EFFECT_ROWS":1})
        print("G46_ORPHAN_WORKSPACE_GREEN=SCOPED_JOIN")

    def test_05_duplicate_state_before_real_state_is_rejected(self):
        raw='{"state":"FAILED",'+json.dumps(self.document())[1:]
        self.replace_json(raw)
        self.assertEqual(self.scan()["counts"],{"JSON_DUPLICATE_KEY":1})
        print("G46_DUPLICATE_STATE_GREEN=AMBIGUOUS_JSON_DENIED")

    def test_06_duplicate_idempotency_key_before_real_key_denied(self):
        raw='{"idempotency_key":"foreign",'+json.dumps(self.document())[1:]
        self.replace_json(raw)
        self.assertEqual(self.scan()["counts"],{"JSON_DUPLICATE_KEY":1})

    def test_07_nested_duplicate_json_key_denied(self):
        raw=json.dumps(self.document())[:-1]+', "probe":{"a":1,"a":2}}'
        self.replace_json(raw)
        self.assertEqual(self.scan()["counts"],{"JSON_DUPLICATE_KEY":1})

    def test_08_negative_sql_attempts_even_without_json_attempts(self):
        doc=self.document()
        doc.pop("attempts",None)  # Deliberate legacy-field omission.
        self.store.db.execute(
            "UPDATE action_outbox SET attempts=-1,data=? "
            "WHERE idempotency_key=?",(json.dumps(doc),self.key))
        self.store.db.commit()
        self.assertEqual(self.scan()["counts"],{"OUTBOX_ATTEMPTS_INVALID":1})
        print("G46_NEGATIVE_ATTEMPTS_GREEN=SQL_INVARIANT_INDEPENDENT")

    def test_09_json_boolean_attempts_not_treated_as_integer(self):
        doc=self.document()
        doc["attempts"]=True
        self.store.db.execute(
            "UPDATE action_outbox SET attempts=1,data=? "
            "WHERE idempotency_key=?",(json.dumps(doc),self.key))
        self.store.db.commit()
        self.assertEqual(self.scan()["counts"],{"JSON_ATTEMPTS_INVALID":1})
        print("G46_BOOL_ATTEMPTS_GREEN=STRICT_TYPE")

    def test_10_audit_cannot_modify_sqlite_or_leak_payload(self):
        self.cross_scope_outbox("owner","foreign-owner")
        before=sha256(self.file.read_bytes()).hexdigest()
        report=self.scan()
        after=sha256(self.file.read_bytes()).hexdigest()
        self.assertEqual(before,after)
        self.assertEqual(report["counts"],{"ORPHAN_EFFECT_ROWS":1})
        self.assertNotIn("do-not-emit",json.dumps(report))
        print("G46_READONLY_GREEN=NO_REPAIR_NO_PAYLOAD")


if __name__ == "__main__":
    unittest.main()
