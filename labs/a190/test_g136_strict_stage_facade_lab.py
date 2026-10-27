"""G136 boundary tests — actual Outbox staging, synthetic signer and local process.

PASS means LAB facade checks are well-behaved; it is NOT trusted identity,
native SQLite custody, production SEND authorization, or closure of P0.
Intentional RED bypass case shows any same-host caller can instantiate an
unguarded real ExecutionOutbox and call enqueue directly.
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
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a190.g135_pinned_original_claim_lab import PinnedOriginalClaimLab
from labs.a190.g136_strict_stage_facade_lab import (
    G136StrictStagingFacadeLab, STAGED, DENY_IDENTITY, DENY_SCOPE,
    DENY_REF, DENY_USED, DENY_UNCERTAIN, DENY_OUTBOX,
)
from labs.a190.test_g135_signed_original_to_actual_outbox_lab import (
    ORIGINAL, EFFECT, NOW, lab_keys, signer, verifier_for,
)


class G136StrictStageActualAionOutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g136-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.aion = self.root / "aion" / "aion.sqlite3"
        self.aion.parent.mkdir()
        self.custody = self.root / "other-local-process" / "witness.sqlite3"
        self.baseline = self.root / "aion-pre-intent.sqlite3"
        self.scope = Scope("synthetic-owner", "synthetic-tenant", "synthetic-workspace")
        self.private, self.pins = lab_keys()
        self.handles = []
        self.addCleanup(self._close_all)
        self._worker("bootstrap", self.custody)
        store, _ = self._open()
        self._close(store)
        with closing(sqlite3.connect(self.aion)) as src, closing(sqlite3.connect(self.baseline)) as dst:
            src.backup(dst)

    def _worker(self, *args):
        return subprocess.run(
            [sys.executable, "-B", "-m", "labs.a190.g134_process_custody_lab",
             *map(str, args)],
            capture_output=True, text=True, check=True, timeout=12,
        ).stdout.strip()

    def _open(self, scope=None):
        store = SQLiteChatStore(self.aion)
        self.handles.append(store)
        return store, ExecutionOutbox(store, scope or self.scope)

    def _close(self, store):
        if store in self.handles:
            self.handles.remove(store)
            store.close()

    def _close_all(self):
        while self.handles:
            self.handles.pop().close()

    def _facade(self, outbox, original=None, effect=None, pins=None):
        original = deepcopy(original if original is not None else ORIGINAL)
        effect = deepcopy(effect if effect is not None else EFFECT)
        return G136StrictStagingFacadeLab(
            outbox=outbox,
            claim=PinnedOriginalClaimLab(
                original_event=original,
                economic_effect=effect,
                identity_verifier=verifier_for(pins if pins is not None else self.pins),
            ),
            custody_path=self.custody,
        )

    def _stage(self, facade, *, original=None, effect=None, query=None,
               ref="synthetic-request-A"):
        return facade.stage(
            claimed_original=deepcopy(original if original is not None else ORIGINAL),
            economic_effect=deepcopy(effect if effect is not None else EFFECT),
            evidence_query=query if query is not None else signer(self.private, self.pins),
            technical_ref=ref,
        )

    def _count_custody(self):
        with closing(sqlite3.connect(self.custody)) as db:
            return db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]

    def _rollback_aion(self):
        self.assertFalse(self.handles)
        for p in (self.aion, Path(str(self.aion) + "-wal"),
                  Path(str(self.aion) + "-shm")):
            p.unlink(missing_ok=True)
        shutil.copy2(self.baseline, self.aion)

    def test_01_legitimate_synthetic_stage_once_through_strict_facade(self):
        store, outbox = self._open()
        result, item = self._stage(self._facade(outbox))
        self.assertEqual(result, STAGED)
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self.assertEqual(len(outbox.list()), 1)
        self.assertEqual(self._count_custody(), 1)
        self._close(store)
        print("G136_STRICT_FACADE_SIGNED_AND_RESERVED=REAL_OUTBOX_LAB_STAGE_NO_SEND")

    def test_02_no_proof_denies_before_custody_and_before_outbox(self):
        store, outbox = self._open()
        facade = self._facade(outbox)
        status, item = self._stage(facade, query=lambda *_: None)
        self.assertEqual(status, DENY_IDENTITY)
        self.assertIsNone(item)
        self.assertEqual(outbox.list(), [])
        self.assertEqual(self._count_custody(), 0)
        self._close(store)

    def test_03_relabelled_original_refuses_even_with_good_synthetic_signer(self):
        store, outbox = self._open()
        fake = {**ORIGINAL, "event_id": "claimed-alternate-economic-original"}
        self.assertEqual(self._stage(self._facade(outbox), original=fake)[0], DENY_IDENTITY)
        self.assertEqual(self._count_custody(), 0)
        self.assertEqual(outbox.list(), [])
        self._close(store)

    def test_04_altered_target_amount_or_currency_refused(self):
        store, outbox = self._open()
        for key, value in (("target", "different-account"), ("amount_minor", "99999"),
                           ("currency", "EUR")):
            with self.subTest(key=key):
                status, item = self._stage(
                    self._facade(outbox), effect={**EFFECT, key: value})
                self.assertEqual(status, DENY_IDENTITY)
                self.assertIsNone(item)
        self.assertEqual(self._count_custody(), 0)
        self._close(store)

    def test_05_signed_original_scope_cannot_stage_in_other_tenant(self):
        store, wrong_outbox = self._open(Scope("synthetic-owner", "different-tenant", "synthetic-workspace"))
        status, item = self._stage(self._facade(wrong_outbox))
        self.assertEqual(status, DENY_SCOPE)
        self.assertIsNone(item)
        self.assertEqual(wrong_outbox.list(), [])
        self.assertEqual(self._count_custody(), 0)
        self._close(store)

    def test_06_missing_local_custody_refuses_without_self_bootstrap(self):
        store, outbox = self._open()
        self.custody.unlink()
        status, item = self._stage(self._facade(outbox))
        self.assertEqual(status, DENY_UNCERTAIN)
        self.assertIsNone(item)
        self.assertFalse(self.custody.exists())
        self.assertEqual(outbox.list(), [])
        self._close(store)

    def test_07_corrupt_custody_refuses_without_outbox_rows(self):
        store, outbox = self._open()
        self.custody.write_bytes(b"not sqlite")
        status, item = self._stage(self._facade(outbox))
        self.assertEqual(status, DENY_UNCERTAIN)
        self.assertIsNone(item)
        self.assertEqual(outbox.list(), [])
        self._close(store)

    def test_08_one_facade_is_single_use_and_cannot_auto_retry(self):
        store, outbox = self._open()
        facade = self._facade(outbox)
        self.assertEqual(self._stage(facade)[0], STAGED)
        self.assertEqual(self._stage(facade, ref="different-request")[0], DENY_USED)
        self.assertEqual(self._count_custody(), 1)
        self._close(store)

    def test_09_new_facade_different_request_same_original_denied_in_local_custody(self):
        store, outbox = self._open()
        self.assertEqual(self._stage(self._facade(outbox))[0], STAGED)
        status, item = self._stage(self._facade(outbox), ref="renamed-request")
        self.assertEqual(status, DENY_UNCERTAIN)
        self.assertIsNone(item)
        self.assertEqual(len(outbox.list()), 1)
        self._close(store)

    def test_10_actual_aion_only_rollback_keeps_original_local_custody(self):
        store, outbox = self._open()
        self.assertEqual(self._stage(self._facade(outbox))[0], STAGED)
        self._close(store)
        self._rollback_aion()
        store, outbox = self._open()
        status, item = self._stage(self._facade(outbox), ref="retry-after-rollback")
        self.assertEqual(status, DENY_UNCERTAIN)
        self.assertIsNone(item)
        self.assertEqual(outbox.list(), [])
        self._close(store)
        print("G136_ACTUAL_OUTBOX_HOST_ROLLBACK=LOCAL_CUSTODY_PREVENTS_RESTAGE_NOT_P0")

    def test_11_invalid_reference_fails_without_consuming_identity(self):
        store, outbox = self._open()
        facade = self._facade(outbox)
        self.assertEqual(self._stage(facade, ref="../bad-ref")[0], DENY_REF)
        self.assertEqual(self._stage(facade)[0], STAGED)
        self._close(store)

    def test_12_subprocess_exception_or_lost_ack_does_not_restage(self):
        store, outbox = self._open()
        facade = self._facade(outbox)
        with patch("labs.a190.g136_strict_stage_facade_lab.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="local-child", timeout=12)):
            status, item = self._stage(facade)
        self.assertEqual(status, DENY_UNCERTAIN)
        self.assertIsNone(item)
        self.assertEqual(self._stage(facade)[0], DENY_USED)
        self.assertEqual(outbox.list(), [])
        self._close(store)

    def test_13_malformed_fake_subprocess_success_text_never_authorizes_staging(self):
        store, outbox = self._open()
        facade = self._facade(outbox)
        fake = subprocess.CompletedProcess(args=["lab"], returncode=0,
                                           stdout="ADMITTED_LOCAL_PROCESS_LAB_NOT_AUTHORITY_EXTRA\n",
                                           stderr="")
        with patch("labs.a190.g136_strict_stage_facade_lab.subprocess.run", return_value=fake):
            status, item = self._stage(facade)
        self.assertEqual(status, DENY_UNCERTAIN)
        self.assertIsNone(item)
        self.assertEqual(outbox.list(), [])
        self._close(store)

    def test_14_failure_after_custody_commit_must_not_auto_retry(self):
        store, outbox = self._open()
        facade = self._facade(outbox)
        with patch.object(outbox, "enqueue", side_effect=RuntimeError("synthetic-db-error")):
            status, item = self._stage(facade)
        self.assertEqual(status, DENY_OUTBOX)
        self.assertIsNone(item)
        self.assertEqual(self._count_custody(), 1)
        self.assertEqual(self._stage(facade)[0], DENY_USED)
        self.assertEqual(self._stage(self._facade(outbox), ref="retry-after-failed-stage")[0],
                         DENY_UNCERTAIN)
        self._close(store)
        print("G136_CUSTODY_COMMIT_BUT_OUTBOX_STAGE_FAIL=UNCERTAIN_ZERO_AUTO_RETRY")

    def test_15_default_outbox_dispatch_still_denies_adapter_send(self):
        store, outbox = self._open()
        status, item = self._stage(self._facade(outbox))
        self.assertEqual(status, STAGED)
        self.assertIsNotNone(outbox.claim_next("synthetic-worker", now=NOW, lease_seconds=30))
        class FailOnSend:
            count = 0
            def send(self, *_):
                self.count += 1
                raise AssertionError("send must be blocked")
            def reconcile(self, *_):
                raise AssertionError("reconcile must be blocked")
        adapter = FailOnSend()
        def policy(d):
            return {"allowed":True, "actor_id":self.scope.owner_id,
                    "tenant_id":self.scope.tenant_id,
                    "workspace_id":self.scope.workspace_id,
                    "policy_version":d["policy_version"],
                    "authorization_ref":d["authorization_ref"],
                    "reauthenticated":True}
        dispatched = outbox.dispatch_claimed(
            item["idempotency_key"], worker_id="synthetic-worker",
            authorize=policy, adapter=adapter, now=NOW+timedelta(seconds=1))
        self.assertEqual(dispatched["state"], "UNCERTAIN")
        self.assertEqual(adapter.count, 0)
        self._close(store)

    def test_16_base_execution_outbox_still_has_direct_enqueue_bypass_red(self):
        store, outbox = self._open()
        # Real dangerous scope gap: the LAB facade cannot force all callers
        # of an unmodified ExecutionOutbox to use it.
        bypass = outbox.enqueue(
            intent_ref="direct-unguarded", action=EFFECT["action"],
            payload={"business_event_id":"attacker-event-relabelled", **EFFECT},
            semantic_event_id_lab="attacker-event-relabelled",
            aggregate_key="g136-direct-bypass",
            policy_version="NOT_EXTERNAL_AUTHORITY",
            authorization_ref="NOT_AUTHENTICATED_OWNER",
            created_at=NOW, valid_until=NOW+timedelta(minutes=5))
        self.assertEqual(bypass["enqueue_state"], "ENQUEUED")
        self.assertEqual(self._count_custody(), 0)
        self.assertEqual(len(outbox.list()), 1)
        self._close(store)
        print("G136_UNMODIFIED_EXECUTION_OUTBOX_DIRECT_ENQUEUE=LOCAL_STAGE_BYPASS_RED_NO_SEND")


if __name__ == "__main__":
    unittest.main()
