"""Real SQLite H0 read-only boot observation: blocked in ALL local states.

This suite DOES NOT demonstrate external high-water or rollback detection.
It documents that after a manual rollback a valid old DB becomes locally
indistinguishable from an originally clean DB; both require external custody.
All fixtures are temporary; no Worker/adapter/network/real provider.
"""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_p0_h0_sqlite_startup_observer_lab import (
    observe_h0_sqlite_first_effect_lab as probe,
)

SCOPE = Scope("fixture-owner", "fixture-tenant", "fixture-space")
NOW = datetime(2026, 10, 19, 21, 0, tzinfo=timezone.utc)
FALSE_FLAGS = (
    "local_rollback_detected", "local_rollback_ruled_out",
    "independent_witness_source_enrolled", "independent_witness_authenticated",
    "external_highwater_compared", "monotonic_epoch_verified",
    "producer_receipt_authenticated", "first_attempt_cleared",
    "unknown_outcome_cleared", "automatic_retry_allowed",
    "claim_release_authorized", "worker_arming_allowed",
    "external_action_executed", "database_written_by_this_check",
)


class H0SQLiteStartupObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p0-h0-boot-lab-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def check(self, path, claim=None, observed=None):
        before_claim = None
        if type(claim) is dict:
            before_claim = deepcopy(claim)
        result = probe(path, claim)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["blocker"], "INDEPENDENT_H0_WITNESS_NOT_ENROLLED")
        for key in FALSE_FLAGS:
            self.assertIs(result[key], False, key)
        if observed is not None:
            self.assertEqual(result["local_observation"], observed)
        if before_claim is not None:
            self.assertEqual(claim, before_claim)
        self.assertNotIn("owner", json.dumps(result).lower())
        self.assertNotIn("tenant", json.dumps(result).lower())
        return result

    def create_store(self, name="live.sqlite3"):
        path = self.root / name
        store = SQLiteChatStore(path)
        self.addCleanup(store.close)
        return path, store

    def create_outbox(self, *, name="outbox.sqlite3", state="PENDING"):
        path, store = self.create_store(name)
        box = ExecutionOutbox(store, SCOPE)
        key = box.enqueue(
            intent_ref="H0-synthetic-intent",
            action="synthetic_only_no_provider",
            payload={"fixture": True},
            aggregate_key="H0-test-aggregate",
            authorization_ref="fake-lab-approval",
            policy_version="lab",
            created_at=NOW,
            valid_until=NOW + timedelta(hours=1),
        )["idempotency_key"]
        if state != "PENDING":
            with store.db:
                store.db.execute(
                    "UPDATE action_outbox SET state=?,dispatch_started_at=? "
                    "WHERE idempotency_key=?",
                    (state, NOW.isoformat(), key),
                )
        return path, store, box, key

    def test_01_missing_db_stays_blocked(self):
        self.check(self.root / "none.sqlite3", observed="DATABASE_MISSING_OR_NOT_REGULAR")

    def test_02_directory_not_a_db_stays_blocked(self):
        self.check(self.root, observed="DATABASE_MISSING_OR_NOT_REGULAR")

    def test_03_chat_only_healthy_db_is_not_first_effect_proof(self):
        path, store = self.create_store()
        store.create_conversation(SCOPE, "fixture conversation")
        report = self.check(path, observed="NO_EXECUTION_SCHEMA_LOCALLY")
        self.assertTrue(report["sqlite_quick_check_observed"])
        self.assertFalse(report["execution_schema_present"])

    def test_04_real_pending_outbox_is_not_fenced_against_older_backup(self):
        path, store, box, key = self.create_outbox()
        report = self.check(path, observed="OUTBOX_PRESENT_LOCAL_ONLY")
        self.assertEqual(report["outbox_states_observed"]["PENDING"], 1)
        self.assertEqual(report["outbox_rows_observed"], 1)

    def test_05_uncertain_remains_unknown_and_no_retry(self):
        path, _, _, _ = self.create_outbox(state="UNCERTAIN")
        report = self.check(path, observed="OUTBOX_UNCERTAIN_LOCALLY")
        self.assertEqual(report["outbox_states_observed"]["UNCERTAIN"], 1)
        self.assertFalse(report["unknown_outcome_cleared"])

    def test_06_locally_blocked_producer_does_not_prove_custody(self):
        path, _, _, _ = self.create_outbox(state="BLOCKED_PRODUCER")
        self.check(path, observed="OUTBOX_PRESENT_LOCAL_ONLY")

    def test_07_malformed_outbox_unknown_state_is_not_trusted(self):
        path, _, _, _ = self.create_outbox(state="READY")
        report = self.check(path, observed="OUTBOX_UNKNOWN_STATE_LOCALLY")
        self.assertEqual(report["unrecognized_outbox_states"], 1)

    def test_08_partial_outbox_schema_fails_closed(self):
        path, store = self.create_store()
        with store.db:
            store.db.execute("CREATE TABLE action_outbox(no_state TEXT)")
        report = self.check(path, observed="OUTBOX_SCHEMA_INCOMPLETE")
        self.assertTrue(report["execution_schema_present"])

    def test_09_budget_only_schema_is_local_not_verified(self):
        path, store = self.create_store()
        with store.db:
            store.db.execute("CREATE TABLE aion_authority_spend(dummy INTEGER)")
        report = self.check(path, observed="EXECUTION_SCHEMA_WITHOUT_OUTBOX")
        self.assertTrue(report["execution_schema_present"])

    def test_10_corrupt_sqlite_blocks_without_recreating(self):
        path = self.root / "corrupt.sqlite3"
        path.write_bytes(b"NOT SQLITE")
        before = path.read_bytes()
        self.check(path, observed="DATABASE_READ_UNVERIFIABLE")
        self.assertEqual(path.read_bytes(), before)

    def test_11_fake_verified_witness_claim_never_enrolls(self):
        path, _, _, _ = self.create_outbox()
        claim = {
            "authenticated": True, "independent_witness": True,
            "highwater": 999999, "READY": True, "signed": True
        }
        report = self.check(path, claim=claim, observed="OUTBOX_PRESENT_LOCAL_ONLY")
        self.assertFalse(report["independent_witness_authenticated"])

    def test_12_hostile_claim_is_not_inspected(self):
        path, _, _, _ = self.create_outbox()
        class Hostile:
            def __bool__(self):
                raise AssertionError("H0 must not inspect untrusted claim")
            def __getattribute__(self, field):
                raise AssertionError("H0 must not access untrusted claim")
        self.check(path, claim=Hostile(), observed="OUTBOX_PRESENT_LOCAL_ONLY")

    def test_13_local_hash_is_not_an_authoritative_witness(self):
        path, _, _, _ = self.create_outbox()
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        report = self.check(path, claim={"local_sha256": before, "verified": True})
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.assertFalse(report["external_highwater_compared"])

    def test_14_manual_restore_of_old_valid_outbox_cannot_be_declared_safe(self):
        # This is deliberate test-only manual file replacement, bypassing the
        # official restore API hardstop. It PROVES that the H0 observer itself
        # CANNOT DETECT historical loss without an independent witness.
        path, store, box, key = self.create_outbox()
        backup = self.root / "earlier-snapshot.sqlite3"
        with closing(sqlite3.connect(str(path))) as source, closing(sqlite3.connect(str(backup))) as dest:
            source.backup(dest)
        self.assertEqual(box.get(key)["state"], "PENDING")
        with store.db:
            store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN',dispatch_started_at=? "
                "WHERE idempotency_key=?",
                (NOW.isoformat(), key),
            )
        before = self.check(path, observed="OUTBOX_UNCERTAIN_LOCALLY")
        self.assertEqual(before["outbox_states_observed"]["UNCERTAIN"], 1)
        store.close()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        shutil.copyfile(backup, path)
        after = self.check(path, observed="OUTBOX_PRESENT_LOCAL_ONLY")
        self.assertEqual(after["outbox_states_observed"]["PENDING"], 1)
        self.assertFalse(after["local_rollback_detected"])
        self.assertFalse(after["local_rollback_ruled_out"])
        with SQLiteChatStore(path) as _unused:
            pass

    def test_15_cli_exit_code_never_reports_ready(self):
        path, store, _, _ = self.create_outbox()
        module = Path(__file__).with_name("atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py")
        result = subprocess.run(
            [sys.executable, "-B", str(module), str(path)],
            capture_output=True, text=True, timeout=20
        )
        self.assertEqual(result.returncode, 2)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["state"], "BLOCKED")
        self.assertFalse(parsed["first_attempt_cleared"])

    def test_16_unrecognized_local_witness_table_does_not_grant_anything(self):
        path, store = self.create_store()
        with store.db:
            store.db.execute(
                "CREATE TABLE h0_external_witness_claim(verified INTEGER, epoch INTEGER)"
            )
            store.db.execute(
                "INSERT INTO h0_external_witness_claim VALUES (1, 999999)"
            )
        report = self.check(path, observed="NO_EXECUTION_SCHEMA_LOCALLY")
        self.assertFalse(report["monotonic_epoch_verified"])


if __name__ == "__main__":
    unittest.main()
