"""G45 LAB: scoped effect JOIN checks for standalone G43 SQLite auditor.

Disposable SQLite only. No Worker, provider, network send, external authority
or historical mutation. Local integrity is NOT proof of a real-world effect.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from hashlib import sha256
import json
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_outbox_binding_lab import binding_issue_lab
from g43_projection_readonly_auditor_lab import audit_projection_snapshot_readonly_lab

NOW = datetime(2026, 10, 24, 16, tzinfo=timezone.utc)
SCOPE = Scope("g45-owner", "g45-tenant", "g45-space")


class G45EffectScopeReadOnly(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="g45-scope-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "disposable.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(
            self.store, SCOPE, strict_projection_lab=True
        )
        result = self.outbox.enqueue(
            intent_ref="synthetic-request",
            action="synthetic_no_provider",
            payload={"amount_minor": 1000},
            aggregate_key="synthetic-group",
            policy_version="p1",
            authorization_ref="synthetic-only",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        self.key = result["idempotency_key"]
        # G53: synthetic confirmation starts from a recoverable phase,
        # not a fresh PENDING admission.
        self.store.db.execute(
            "UPDATE action_outbox SET state='UNCERTAIN' "
            "WHERE idempotency_key=?", (self.key,))
        self.store.db.commit()
        self.outbox._confirm(
            self.key,
            effect_ref="same-local-synthetic-reference",
            confirmed_at=NOW + timedelta(seconds=2),
        )

    def scan(self):
        return audit_projection_snapshot_readonly_lab(
            self.path,
            owner=SCOPE.owner_id,
            tenant=SCOPE.tenant_id,
            workspace=SCOPE.workspace_id,
        )

    def binding(self):
        return binding_issue_lab(
            self.store.db,
            self.key,
            (SCOPE.owner_id, SCOPE.tenant_id, SCOPE.workspace_id),
        )

    def move_effect(self, column, value):
        # Field names are constants controlled by these tests.
        if column not in {"owner", "tenant", "workspace"}:
            raise ValueError("G45_BAD_TEST_FIELD")
        self.store.db.execute(
            f"UPDATE action_effects SET {column}=? WHERE idempotency_key=?",
            (value, self.key),
        )
        self.store.db.commit()

    def test_01_consistent_local_scope_remains_ok(self):
        self.assertEqual(self.scan()["counts"], {"OK": 1})
        self.assertEqual(self.binding(), "OK")
        print("G45_MATCHING_SCOPE_GREEN=READONLY_CLASSIFICATION")

    def test_02_foreign_effect_owner_denied(self):
        self.move_effect("owner", "foreign-owner")
        self.assertEqual(self.scan()["counts"], {"EFFECT_SCOPE_MISMATCH": 1})
        self.assertEqual(self.binding(), "EFFECT_SCOPE_MISMATCH")
        print("G45_FOREIGN_OWNER_GREEN=NO_FALSE_OK")

    def test_03_foreign_effect_tenant_denied(self):
        self.move_effect("tenant", "foreign-tenant")
        self.assertEqual(self.scan()["counts"], {"EFFECT_SCOPE_MISMATCH": 1})
        self.assertEqual(self.binding(), "EFFECT_SCOPE_MISMATCH")
        print("G45_FOREIGN_TENANT_GREEN=NO_FALSE_OK")

    def test_04_foreign_effect_workspace_denied(self):
        self.move_effect("workspace", "foreign-space")
        self.assertEqual(self.scan()["counts"], {"EFFECT_SCOPE_MISMATCH": 1})
        self.assertEqual(self.binding(), "EFFECT_SCOPE_MISMATCH")
        print("G45_FOREIGN_WORKSPACE_GREEN=NO_FALSE_OK")

    def test_05_matching_receipt_reference_does_not_hide_foreign_owner(self):
        self.move_effect("owner", "foreign-owner")
        row = self.store.db.execute(
            "SELECT o.effect_ref AS a, e.effect_ref AS b, "
            "o.confirmed_at AS c, e.confirmed_at AS d "
            "FROM action_outbox o JOIN action_effects e "
            "ON o.idempotency_key=e.idempotency_key "
            "WHERE o.idempotency_key=?", (self.key,),
        ).fetchone()
        self.assertEqual(row["a"], row["b"])
        self.assertEqual(row["c"], row["d"])
        self.assertEqual(self.scan()["findings"][0]["issue"],
                         "EFFECT_SCOPE_MISMATCH")

    def test_06_readonly_scan_keeps_db_bytes(self):
        self.move_effect("owner", "foreign-owner")
        original = sha256(self.path.read_bytes()).hexdigest()
        report = self.scan()
        current = sha256(self.path.read_bytes()).hexdigest()
        self.assertEqual(original, current)
        self.assertEqual(report["counts"], {"EFFECT_SCOPE_MISMATCH": 1})
        self.assertNotIn("amount_minor", json.dumps(report))
        print("G45_READONLY_GREEN=NO_REPAIR_NO_PAYLOAD")

    def test_07_other_scope_query_leaks_no_rows(self):
        self.move_effect("tenant", "foreign-tenant")
        report = audit_projection_snapshot_readonly_lab(
            self.path,
            owner=SCOPE.owner_id,
            tenant="other-requested-tenant",
            workspace=SCOPE.workspace_id,
        )
        self.assertEqual(report["row_count"], 0)
        self.assertEqual(report["findings"], [])


if __name__ == "__main__":
    unittest.main()
