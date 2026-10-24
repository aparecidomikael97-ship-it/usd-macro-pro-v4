"""G43: real SQLite Outbox projection dry-run and conditional one-row LAB.

No external provider, real receipts, bulk migration, replay/sends, trusted root.
Opt-in test-only approval changes ONLY action_outbox.data for ONE row.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import shutil
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 24, 16, tzinfo=timezone.utc)
SCOPE = Scope("g43-owner", "g43-tenant", "g43-workspace")
WORKER = "g43-test-worker"


class NoSend:
    @property
    def send(self):
        raise AssertionError("G43_NO_REAL_PROVIDER_SEND")


class G43ProjectionContract(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="aion-g43-")
        self.addCleanup(temp.cleanup)
        self.file = Path(temp.name) / "outbox.sqlite3"
        self.store = SQLiteChatStore(self.file)
        self.addCleanup(lambda: self.store.close())
        self.base = ExecutionOutbox(self.store, SCOPE)
        row = self.base.enqueue(
            intent_ref="synthetic-business-invoice",
            action="synthetic_no_provider",
            payload={"amount_minor": 1000},
            aggregate_key="synthetic-group",
            policy_version="policy-v1",
            authorization_ref="authority-v1",
            created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
        )
        self.key = row["idempotency_key"]
        self.lab = ExecutionOutbox(self.store, SCOPE, strict_projection_lab=True)

    def raw(self):
        return self.store.db.execute(
            "SELECT data FROM action_outbox WHERE idempotency_key=?",
            (self.key,),
        ).fetchone()["data"]

    def projected(self):
        return json.loads(self.raw())

    def ledger(self):
        return self.store.db.execute(
            "SELECT effect_ref,confirmed_at,data FROM action_effects "
            "WHERE idempotency_key=?", (self.key,),
        ).fetchall()

    def make_uncertain(self):
        claimed = self.base.claim_next(WORKER, now=NOW, lease_seconds=60)
        self.assertEqual(claimed["idempotency_key"], self.key)
        unknown = self.base.dispatch_claimed(
            self.key, worker_id=WORKER,
            authorize=lambda d: {
                "allowed": True, "actor_id": SCOPE.owner_id,
                "policy_version": "policy-v1",
                "authorization_ref": "authority-v1",
            },
            adapter=NoSend(), now=NOW+timedelta(seconds=1),
        )
        self.assertEqual(unknown["state"], "UNCERTAIN")
        return unknown

    def legacy_confirm(self):
        self.make_uncertain()
        return self.base._confirm(self.key, effect_ref="g43-synthetic-effect",
            confirmed_at=NOW+timedelta(seconds=2),
            result={"proof": "SYNTHETIC_NO_PROVIDER"})

    def latest_confirm(self):
        self.make_uncertain()
        return self.lab._confirm(self.key, effect_ref="g43-synthetic-effect",
            confirmed_at=NOW+timedelta(seconds=2),
            result={"proof": "SYNTHETIC_NO_PROVIDER"})

    def test_01_readonly_dryrun_detects_pending_against_claimed(self):
        self.make_uncertain()
        prior = self.raw()
        plan = self.lab.projection_plan_lab(self.key)
        self.assertTrue(plan["changed"])
        self.assertEqual(plan["state"], "UNCERTAIN")
        self.assertEqual(plan["schema"], "AION-A190-G43-PROJECTION-DRYRUN-V1")
        self.assertEqual(self.raw(), prior)
        print("G43_READONLY_PLAN_GREEN=NO_HISTORICAL_WRITE")

    def test_02_explicit_plan_repairs_one_row_only(self):
        self.make_uncertain()
        plan = self.lab.projection_plan_lab(self.key)
        result = self.lab.apply_projection_plan_lab(plan, explicit_approval=True)
        self.assertTrue(result["updated"])
        self.assertEqual(self.projected()["state"], "UNCERTAIN")
        self.assertEqual(self.projected()["attempts"], 1)
        self.assertEqual(self.ledger(), [])
        print("G43_EXPLICIT_ONE_ROW_GREEN=ATOMIC_JSON_COLUMN_CAS")

    def test_03_missing_explicit_approval_denies(self):
        self.make_uncertain()
        plan = self.lab.projection_plan_lab(self.key)
        old = self.raw()
        with self.assertRaisesRegex(RuntimeError, "G43_EXPLICIT_APPROVAL_REQUIRED"):
            self.lab.apply_projection_plan_lab(plan)
        self.assertEqual(self.raw(), old)

    def test_04_wrong_scope_plan_denies(self):
        self.make_uncertain()
        plan = self.lab.projection_plan_lab(self.key)
        plan["tenant"] = "another-tenant"
        with self.assertRaisesRegex(RuntimeError, "G43_PLAN_SCOPE_OR_VERSION_DENIED"):
            self.lab.apply_projection_plan_lab(plan, explicit_approval=True)

    def test_05_wrong_schema_version_denies(self):
        plan = self.lab.projection_plan_lab(self.key)
        plan["schema"] = "G43-UNREVIEWED-V2"
        with self.assertRaisesRegex(RuntimeError, "G43_PLAN_SCOPE_OR_VERSION_DENIED"):
            self.lab.apply_projection_plan_lab(plan, explicit_approval=True)

    def test_06_stale_plan_after_claim_generation_change_denies(self):
        plan = self.lab.projection_plan_lab(self.key)
        self.make_uncertain()
        old = self.raw()
        with self.assertRaisesRegex(RuntimeError, "G43_STALE_DRYRUN_REFUSED"):
            self.lab.apply_projection_plan_lab(plan, explicit_approval=True)
        self.assertEqual(self.raw(), old)
        print("G43_STALE_PLAN_GREEN=CONCURRENT_STATE_CHANGE_DENIED")

    def test_07_reapply_same_approved_plan_is_idempotent(self):
        self.make_uncertain()
        plan = self.lab.projection_plan_lab(self.key)
        once = self.lab.apply_projection_plan_lab(plan, explicit_approval=True)
        twice = self.lab.apply_projection_plan_lab(plan, explicit_approval=True)
        self.assertTrue(once["updated"])
        self.assertFalse(twice["updated"])

    def test_08_new_confirmation_projects_in_same_transaction(self):
        row = self.latest_confirm()
        self.assertEqual(row["state"], "CONFIRMED")
        obj = self.projected()
        self.assertEqual(obj["state"], "CONFIRMED")
        self.assertEqual(obj["confirmed_at"], row["confirmed_at"])
        self.assertEqual(obj["effect_ref"], row["effect_ref"])
        self.assertEqual(obj["lease_owner"], "")
        self.assertEqual(len(self.ledger()), 1)
        print("G43_NEW_CONFIRM_GREEN=PROJECTION_AND_LEDGER_SAME_COMMIT")

    def test_09_legacy_confirm_stays_stale_red(self):
        row = self.legacy_confirm()
        self.assertEqual(row["state"], "CONFIRMED")
        self.assertEqual(self.projected()["state"], "PENDING")
        self.assertTrue(self.lab.projection_plan_lab(self.key)["changed"])
        print("G43_LEGACY_JSON_RED=OLD_WRITER_RETAINS_PENDING_FIELD")

    def test_10_explicit_historical_confirm_projection_preserves_effect(self):
        row = self.legacy_confirm()
        old_ledger = [(x["effect_ref"], x["confirmed_at"], x["data"])
                      for x in self.ledger()]
        plan = self.lab.projection_plan_lab(self.key)
        result = self.lab.apply_projection_plan_lab(plan, explicit_approval=True)
        self.assertTrue(result["updated"])
        self.assertEqual(self.projected()["state"], "CONFIRMED")
        self.assertEqual(self.projected()["confirmed_at"], row["confirmed_at"])
        self.assertEqual([(x["effect_ref"], x["confirmed_at"], x["data"])
                          for x in self.ledger()], old_ledger)
        self.assertEqual(self.lab.get(self.key)["confirmed_at"], row["confirmed_at"])
        print("G43_LEDGER_IMMUTABLE_GREEN=NO_RECEIPT_OR_TIMESTAMP_REWRITE")

    def test_11_invalid_json_denies_and_no_repair(self):
        self.store.db.execute(
            "UPDATE action_outbox SET data='not-json' WHERE idempotency_key=?",
            (self.key,))
        self.store.db.commit()
        with self.assertRaisesRegex(RuntimeError, "G43_PROJECTION_INVALID_JSON_DENY"):
            self.lab.projection_plan_lab(self.key)

    def test_12_nonobject_json_denies(self):
        self.store.db.execute(
            "UPDATE action_outbox SET data='[]' WHERE idempotency_key=?",
            (self.key,))
        self.store.db.commit()
        with self.assertRaisesRegex(RuntimeError, "G43_PROJECTION_NOT_OBJECT_DENY"):
            self.lab.projection_plan_lab(self.key)

    def test_13_tampered_key_denies_without_changing_original(self):
        value = self.projected()
        value["idempotency_key"] = "fabricated-identity"
        self.store.db.execute("UPDATE action_outbox SET data=? WHERE idempotency_key=?",
                              (json.dumps(value),self.key))
        self.store.db.commit()
        old = self.raw()
        with self.assertRaisesRegex(RuntimeError, "G43_PROJECTION_IDENTITY_MISMATCH_DENY"):
            self.lab.projection_plan_lab(self.key)
        self.assertEqual(old, self.raw())
        print("G43_TAMPER_GREEN=FOREIGN_IDENTITY_REFUSED")

    def test_14_tampered_decision_id_denies(self):
        value = self.projected()
        value["decision_id"] = "different-decision"
        self.store.db.execute("UPDATE action_outbox SET data=? WHERE idempotency_key=?",
                              (json.dumps(value),self.key))
        self.store.db.commit()
        with self.assertRaisesRegex(RuntimeError, "G43_PROJECTION_IDENTITY_MISMATCH_DENY"):
            self.lab.projection_plan_lab(self.key)

    def test_15_wrong_state_enum_in_json_denies(self):
        value = self.projected()
        value["state"] = "SENT_AND_CONFIRMED"
        self.store.db.execute("UPDATE action_outbox SET data=? WHERE idempotency_key=?",
                              (json.dumps(value),self.key))
        self.store.db.commit()
        with self.assertRaisesRegex(RuntimeError, "G43_PROJECTION_STATE_INVALID_DENY"):
            self.lab.projection_plan_lab(self.key)

    def test_16_confirmed_without_ledger_denies_dryrun(self):
        self.store.db.execute(
            "UPDATE action_outbox SET state='CONFIRMED', effect_ref='fake',"
            "confirmed_at='synthetic' WHERE idempotency_key=?", (self.key,))
        self.store.db.commit()
        with self.assertRaisesRegex(RuntimeError, "G43_CONFIRMED_LEDGER_INCONSISTENT_DENY"):
            self.lab.projection_plan_lab(self.key)
        self.assertEqual(self.lab.effect_count(), 0)
        print("G43_NO_RECEIPT_RED=CONFIRMED_WITHOUT_LEDGER_REFUSED")

    def test_17_ledger_on_nonconfirmed_row_denies_dryrun(self):
        self.store.db.execute(
            "INSERT INTO action_effects(idempotency_key,owner,tenant,workspace,"
            "effect_ref,confirmed_at,data) VALUES(?,?,?,?,?,?,?)",
            (self.key,SCOPE.owner_id,SCOPE.tenant_id,SCOPE.workspace_id,
             "fake-effect","synthetic-time","{}"))
        self.store.db.commit()
        with self.assertRaisesRegex(RuntimeError, "G43_NONCONFIRMED_HAS_EFFECT_DENY"):
            self.lab.projection_plan_lab(self.key)

    def test_18_legacy_historical_rows_never_automigrated_on_restart(self):
        self.legacy_confirm()
        before = self.raw()
        self.store.close()
        self.store = SQLiteChatStore(self.file)
        self.lab = ExecutionOutbox(self.store,SCOPE,strict_projection_lab=True)
        self.assertEqual(self.raw(),before)
        self.assertTrue(self.lab.projection_plan_lab(self.key)["changed"])
        print("G43_REOPEN_GREEN=NO_IMPLICIT_BACKFILL_OR_TRIGGER")

    def test_19_host_rollback_loses_projection_and_confirm_red(self):
        self.make_uncertain()
        self.store.close()
        saved=self.file.parent/"old-db.sqlite3"
        shutil.copyfile(self.file,saved)
        self.store=SQLiteChatStore(self.file)
        self.lab=ExecutionOutbox(self.store,SCOPE,strict_projection_lab=True)
        self.lab._confirm(self.key,effect_ref="synthetic-effect",
                          confirmed_at=NOW+timedelta(seconds=2))
        self.assertEqual(self.projected()["state"],"CONFIRMED")
        self.store.close()
        shutil.copyfile(saved,self.file)
        self.store=SQLiteChatStore(self.file)
        self.lab=ExecutionOutbox(self.store,SCOPE,strict_projection_lab=True)
        self.assertEqual(self.lab.get(self.key)["state"],"UNCERTAIN")
        self.assertEqual(self.projected()["state"],"PENDING")
        print("G43_HOST_ROLLBACK_RED=NO_EXTERNAL_ANTIROLLBACK_FROM_JSON_SYNC")

    def test_20_default_optout_disallows_migration(self):
        with self.assertRaisesRegex(RuntimeError, "G43_PROJECTION_OPT_IN_REQUIRED"):
            self.base.projection_plan_lab(self.key)
        with self.assertRaisesRegex(RuntimeError, "G43_PROJECTION_OPT_IN_REQUIRED"):
            self.base.apply_projection_plan_lab({"schema":"bad"},explicit_approval=True)

    def test_21_projection_option_must_be_boolean(self):
        with self.assertRaises(TypeError):
            ExecutionOutbox(self.store,SCOPE,strict_projection_lab=1)

    def test_22_projection_schema_remains_trigger_and_view_free(self):
        objs = self.store.db.execute(
            "SELECT type FROM sqlite_schema WHERE type IN ('trigger','view')"
        ).fetchall()
        self.assertEqual(objs, [])
        current = self.store.db.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(current, 0)
        print("G43_SCHEMA_GREEN=NO_UNREVIEWED_TRIGGER_VIEW_OR_USER_VERSION_CHANGE")


if __name__ == "__main__":
    unittest.main()
