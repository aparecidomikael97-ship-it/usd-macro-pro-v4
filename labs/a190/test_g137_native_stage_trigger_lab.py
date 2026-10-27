"""G137: actual Outbox native SQLite INSERT trigger, RED local authority bypass.

The trigger protects a single local staging DB while installed. It is NOT
off-host custody; a privileged caller can mint a permit, drop the trigger,
open another DB or roll back local authority. No real SEND.
"""
from contextlib import closing
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox, _digest
from labs.a190.g135_pinned_original_claim_lab import PinnedOriginalClaimLab
from labs.a190.g137_native_stage_trigger_lab import (
    DENIED, STAGED, install_local_tripwire_lab,
    reserve_and_stage_lab, _record_local_permit,
)
from labs.a190.test_g135_signed_original_to_actual_outbox_lab import (
    ORIGINAL, EFFECT, NOW, lab_keys, signer, verifier_for,
)


class G137NativeSqliteTripwireActualOutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g137-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.root = root
        self.aion = root / "aion" / "real-outbox.sqlite3"
        self.aion.parent.mkdir()
        self.custody = root / "separate-same-host" / "custody.sqlite3"
        self.custody.parent.mkdir()
        self.original_aion = root / "snapshot-aion.sqlite3"
        self.original_custody = root / "snapshot-custody.sqlite3"
        self.scope = Scope("synthetic-owner", "synthetic-tenant", "synthetic-workspace")
        self.private, self.pins = lab_keys()
        self.handles = []
        self.addCleanup(self._close_all)
        result = self._bootstrap()
        self.assertEqual(result, "G134_EXPLICIT_LOCAL_FIXTURE_BOOTSTRAP")
        store, outbox = self._open()
        install_local_tripwire_lab(outbox)
        self._close(store)
        with closing(sqlite3.connect(self.aion)) as source, closing(sqlite3.connect(self.original_aion)) as target:
            source.backup(target)
        shutil.copy2(self.custody, self.original_custody)

    def _bootstrap(self):
        return subprocess.run([
            sys.executable, "-B", "-m",
            "labs.a190.g134_process_custody_lab", "bootstrap", str(self.custody),
        ], check=True, capture_output=True, text=True, timeout=12).stdout.strip()

    def _open(self, *, other_scope=None, extra_db=None):
        store = SQLiteChatStore(extra_db or self.aion)
        self.handles.append(store)
        return store, ExecutionOutbox(store, other_scope or self.scope)

    def _close(self, store):
        if store in self.handles:
            self.handles.remove(store)
            store.close()

    def _close_all(self):
        while self.handles:
            self.handles.pop().close()

    def _claim(self, *, original=None, effect=None, pins=None):
        return PinnedOriginalClaimLab(
            original_event=deepcopy(original if original is not None else ORIGINAL),
            economic_effect=deepcopy(effect if effect is not None else EFFECT),
            identity_verifier=verifier_for(pins if pins is not None else self.pins),
        )

    def _stage(self, outbox, *, original=None, effect=None, ref="g137-request-A",
               claim=None, query=None):
        return reserve_and_stage_lab(
            outbox=outbox,
            claim=claim if claim is not None else self._claim(),
            custody_path=self.custody,
            original=deepcopy(original if original is not None else ORIGINAL),
            economic_effect=deepcopy(effect if effect is not None else EFFECT),
            evidence_query=query if query is not None else signer(self.private, self.pins),
            technical_ref=ref,
        )

    def _direct(self, outbox, *, ref="g137-direct", event=None, payload=None):
        real_payload = deepcopy(payload if payload is not None else EFFECT)
        if event is not None:
            real_payload["business_event_id"] = event
        kwargs = {
            "intent_ref": ref, "action": EFFECT["action"],
            "payload": real_payload,
            "aggregate_key": "g137-raw-entry",
            "policy_version": "LAB-NOT-AUTHORITY",
            "authorization_ref": "NOT-AN-AUTHENTICATED-OWNER",
            "created_at": NOW, "valid_until": NOW + timedelta(minutes=5),
        }
        if event is not None:
            kwargs["semantic_event_id_lab"] = event
        return outbox.enqueue(**kwargs)

    def _permits(self):
        with closing(sqlite3.connect(self.aion)) as db:
            return db.execute(
                "SELECT intent_ref, consumed FROM g137_local_stage_permits_lab"
                " ORDER BY intent_ref"
            ).fetchall()

    def _restore(self, path, old):
        for p in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
            p.unlink(missing_ok=True)
        shutil.copy2(old, path)

    def test_01_verified_original_and_custody_permit_real_outbox_stage(self):
        store, outbox = self._open()
        status, item = self._stage(outbox)
        self.assertEqual(status, STAGED)
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self.assertEqual(self._permits(), [("g137-request-A", 1)])
        self._close(store)
        print("G137_SIGNED_CUSTODY_PERMIT=REAL_SQLITE_OUTBOX_INSERT_LOCAL_ONLY")

    def test_02_direct_original_semantic_event_without_permit_denied_by_sqlite(self):
        store, outbox = self._open()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "G137_MISSING_LOCAL_STAGE_PERMIT"):
            self._direct(outbox, event=ORIGINAL["event_id"])
        self.assertEqual(outbox.list(), [])
        self._close(store)
        print("G137_DIRECT_ENQUEUE_WITHOUT_PERMIT=SQLITE_INSERT_DENIED_LOCAL_LAB")

    def test_03_direct_enqueues_without_semantic_event_also_denied(self):
        store, outbox = self._open()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "G137_MISSING_LOCAL_STAGE_PERMIT"):
            self._direct(outbox)
        self.assertEqual(outbox.list(), [])
        self._close(store)
        print("G137_DIRECT_ENQUEUE_NO_SEMANTIC_ID=SQLITE_INSERT_DENIED_LOCAL_LAB")

    def test_04_wrong_payload_digest_ticket_does_not_stage(self):
        store, outbox = self._open()
        payload = {"business_event_id": ORIGINAL["event_id"], **EFFECT}
        tampered = {**payload, "target": "evil-recipient"}
        _record_local_permit(outbox.db, self.scope,
                             "g137-direct", EFFECT["action"], ORIGINAL["event_id"], tampered)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "G137_MISSING_LOCAL_STAGE_PERMIT"):
            self._direct(outbox, event=ORIGINAL["event_id"])
        self.assertEqual(self._permits(), [("g137-direct", 0)])
        self._close(store)

    def test_05_other_tenant_ticket_does_not_stage(self):
        store, outbox = self._open()
        other = Scope("synthetic-owner", "other-tenant", "synthetic-workspace")
        payload = {"business_event_id": ORIGINAL["event_id"], **EFFECT}
        _record_local_permit(outbox.db, other, "g137-direct", EFFECT["action"],
                             ORIGINAL["event_id"], payload)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "G137_MISSING_LOCAL_STAGE_PERMIT"):
            self._direct(outbox, event=ORIGINAL["event_id"])
        self._close(store)

    def test_06_other_request_ref_ticket_does_not_stage(self):
        store, outbox = self._open()
        payload = {"business_event_id": ORIGINAL["event_id"], **EFFECT}
        _record_local_permit(outbox.db, self.scope, "original-request",
                             EFFECT["action"], ORIGINAL["event_id"], payload)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "G137_MISSING_LOCAL_STAGE_PERMIT"):
            self._direct(outbox, ref="g137-direct", event=ORIGINAL["event_id"])
        self._close(store)

    def test_07_consumed_permit_matches_committed_outbox_transaction(self):
        store, outbox = self._open()
        self.assertEqual(self._stage(outbox)[0], STAGED)
        self.assertEqual(self._permits(), [("g137-request-A", 1)])
        with closing(sqlite3.connect(self.aion)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM action_decisions").fetchone()[0], 1)
        self._close(store)

    def test_08_bad_original_or_economic_effect_denied_before_local_ticket(self):
        store, outbox = self._open()
        altered = {**ORIGINAL, "event_id": "attacker-relabel-B"}
        self.assertEqual(self._stage(outbox, original=altered)[0], DENIED)
        self.assertEqual(self._stage(outbox, effect={**EFFECT, "amount_minor": "19000"})[0], DENIED)
        self.assertEqual(self._permits(), [])
        self.assertEqual(outbox.list(), [])
        self._close(store)

    def test_09_aion_db_only_rollback_custodian_intact_blocks_second_stage(self):
        store, outbox = self._open()
        self.assertEqual(self._stage(outbox)[0], STAGED)
        self._close(store)
        self._restore(self.aion, self.original_aion)
        store, outbox = self._open()
        status, item = self._stage(outbox, ref="g137-renamed-technical-id")
        self.assertEqual(status, DENIED)
        self.assertIsNone(item)
        self.assertEqual(self._permits(), [])
        self._close(store)

    def test_10_lost_custody_ack_denied_no_restage_and_no_ticket(self):
        store, outbox = self._open()
        with patch("labs.a190.g137_native_stage_trigger_lab.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="custody", timeout=12)):
            status, item = self._stage(outbox)
        self.assertEqual(status, DENIED)
        self.assertIsNone(item)
        self.assertEqual(self._permits(), [])
        self.assertEqual(outbox.list(), [])
        self._close(store)

    def test_11_attacker_self_mints_permit_using_same_local_db_red(self):
        store, outbox = self._open()
        payload = {"business_event_id": "forged-claimed-event", **EFFECT}
        _record_local_permit(outbox.db, self.scope, "g137-direct", EFFECT["action"],
                             "forged-claimed-event", payload)
        item = self._direct(outbox, event="forged-claimed-event")
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self.assertEqual(self._permits(), [("g137-direct", 1)])
        self._close(store)
        print("G137_FORGED_LOCAL_PERMIT_SELF_MINT=UNAUTHORIZED_STAGE_RED_NOT_P0")

    def test_12_attacker_drops_trigger_then_direct_enqueues_red(self):
        store, outbox = self._open()
        with outbox.db:
            outbox.db.execute("DROP TRIGGER g137_require_stage_permit_lab")
        item = self._direct(outbox, event="unverified-event-C")
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self.assertEqual(self._permits(), [])
        self._close(store)
        print("G137_HOST_CAN_DROP_NATIVE_TRIGGER=DIRECT_STAGE_RED_NOT_P0")

    def test_13_without_explicit_trigger_install_new_db_has_direct_stage_red(self):
        path = self.root / "unguarded-second-database.sqlite3"
        store, outbox = self._open(extra_db=path)
        item = self._direct(outbox, event="unguarded-separate-db")
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self._close(store)
        print("G137_NEW_UNGUARDED_NATIVE_DB=STAGE_BYPASS_RED_NOT_P0")

    def test_14_host_and_custody_joint_rollback_reaccepts_semantics_red(self):
        store, outbox = self._open()
        self.assertEqual(self._stage(outbox)[0], STAGED)
        self._close(store)
        self._restore(self.aion, self.original_aion)
        self._restore(self.custody, self.original_custody)
        store, outbox = self._open()
        status, item = self._stage(outbox, ref="new-request-after-joint-restore")
        self.assertEqual(status, STAGED)
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self._close(store)
        print("G137_JOINT_ROLLBACK_READMITS_LOCAL_EFFECT=RED_NOT_P0")

    def test_15_real_outbox_default_dispatch_still_never_calls_adapter_send(self):
        store, outbox = self._open()
        status, item = self._stage(outbox)
        self.assertEqual(status, STAGED)
        self.assertIsNotNone(outbox.claim_next("synthetic-worker", now=NOW, lease_seconds=30))
        class NoSend:
            count = 0
            def send(self, *_):
                self.count += 1
                raise AssertionError("SEND_NOT_ALLOWED")
            def reconcile(self, *_):
                raise AssertionError("RECONCILIATION_NOT_ALLOWED")
        adapter = NoSend()
        def policy(d):
            return {"allowed": True, "actor_id": self.scope.owner_id,
                    "tenant_id": self.scope.tenant_id,
                    "workspace_id": self.scope.workspace_id,
                    "policy_version": d["policy_version"],
                    "authorization_ref": d["authorization_ref"],
                    "reauthenticated": True}
        result = outbox.dispatch_claimed(
            item["idempotency_key"], worker_id="synthetic-worker",
            authorize=policy, adapter=adapter, now=NOW + timedelta(seconds=1))
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(adapter.count, 0)
        self._close(store)
        print("G137_ACTUAL_OUTBOX_DEFAULT_ADAPTER_SEND=ZERO_NO_REAL_EFFECT")


if __name__ == "__main__":
    unittest.main()
