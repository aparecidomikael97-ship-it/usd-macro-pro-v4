"""A242 — first-attempt reservation must precede any synthetic SEND.

Caller-injected callbacks here are fake LAB witnesses. No external authority.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 29, 11, 0, tzinfo=timezone.utc)
SCOPE = Scope("owner-a242", "tenant-a242", "workspace-a242")
WORKER = "worker-a242"


class Adapter:
    def __init__(self):
        self.calls = 0

    def send(self, decision, key):
        self.calls += 1
        return {"accepted": True, "confirmed": False, "effect_ref": "synthetic-a242"}


def _auth(decision):
    return {
        "allowed": True,
        "actor_id": SCOPE.owner_id,
        "tenant_id": SCOPE.tenant_id,
        "workspace_id": SCOPE.workspace_id,
        "policy_version": decision["policy_version"],
        "authorization_ref": decision["authorization_ref"],
    }


def _fixture(root, guard=None):
    path = Path(root) / "outbox.db"
    store = SQLiteChatStore(path)
    outbox = ExecutionOutbox(store, SCOPE, first_attempt_guard=guard)
    item = outbox.enqueue(
        intent_ref="synthetic-first-attempt", action="fake-effect",
        payload={"never_network": True}, aggregate_key="a242-aggregate",
        policy_version="synthetic-policy", authorization_ref="synthetic-owner",
        created_at=NOW, valid_until=NOW + timedelta(minutes=5),
    )
    key = item["idempotency_key"]
    outbox.claim_next(WORKER, now=NOW, lease_seconds=90)
    return path, store, outbox, key


def _dispatch(outbox, key, adapter, authorize=_auth):
    return outbox.dispatch_claimed(
        key, worker_id=WORKER, authorize=authorize,
        adapter=adapter, now=NOW,
    )


class A242FirstAttemptGuardTests(unittest.TestCase):
    def test_01_default_missing_witness_denies_send(self):
        with TemporaryDirectory(prefix="a242-") as raw:
            path, store, outbox, key = _fixture(raw)
            adapter = Adapter()
            try:
                result = _dispatch(outbox, key, adapter)
                self.assertEqual(adapter.calls, 0)
                self.assertEqual(result["state"], "UNCERTAIN")
                self.assertEqual(result["dispatch_state"], "UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED")
                self.assertEqual(result["last_error"], "FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND")
            finally:
                store.close()

    def test_02_false_none_and_truthy_integer_are_denied(self):
        for response in (False, None, 1):
            with self.subTest(response=response), TemporaryDirectory(prefix="a242-") as raw:
                path, store, outbox, key = _fixture(raw, lambda _: response)
                adapter = Adapter()
                try:
                    self.assertEqual(_dispatch(outbox, key, adapter)["state"], "UNCERTAIN")
                    self.assertEqual(adapter.calls, 0)
                finally:
                    store.close()

    def test_03_lost_witness_ack_denies_send(self):
        with TemporaryDirectory(prefix="a242-") as raw:
            def lost(_):
                raise TimeoutError("synthetic lost witness ACK")
            path, store, outbox, key = _fixture(raw, lost)
            adapter = Adapter()
            try:
                self.assertEqual(_dispatch(outbox, key, adapter)["state"], "UNCERTAIN")
                self.assertEqual(adapter.calls, 0)
            finally:
                store.close()

    def test_04_explicit_synthetic_true_permits_lab_send_only(self):
        with TemporaryDirectory(prefix="a242-") as raw:
            path, store, outbox, key = _fixture(raw, lambda _: True)
            adapter = Adapter()
            try:
                result = _dispatch(outbox, key, adapter)
                self.assertEqual(adapter.calls, 1)
                self.assertEqual(result["state"], "SENT")
                self.assertEqual(result["dispatch_state"], "SENT_RECONCILE_REQUIRED")
            finally:
                store.close()

    def test_05_witness_called_after_durable_uncertain_transition(self):
        with TemporaryDirectory(prefix="a242-") as raw:
            observed = []
            outbox_ref = []
            key_ref = []
            def observer(intent):
                observed.append(outbox_ref[0].get(key_ref[0])["state"])
                return True
            path, store, outbox, key = _fixture(raw, observer)
            outbox_ref.append(outbox)
            key_ref.append(key)
            adapter = Adapter()
            try:
                _dispatch(outbox, key, adapter)
                self.assertEqual(observed, ["UNCERTAIN"])
                self.assertEqual(adapter.calls, 1)
            finally:
                store.close()

    def test_06_denied_witness_survives_restart_without_auto_retry(self):
        with TemporaryDirectory(prefix="a242-") as raw:
            path, store, outbox, key = _fixture(raw)
            adapter = Adapter()
            _dispatch(outbox, key, adapter)
            store.close()
            reopened = SQLiteChatStore(path)
            try:
                fresh = ExecutionOutbox(reopened, SCOPE)
                self.assertEqual(fresh.get(key)["state"], "UNCERTAIN")
                self.assertIsNone(fresh.claim_next("other-worker", now=NOW+timedelta(hours=2)))
                self.assertEqual(adapter.calls, 0)
            finally:
                reopened.close()

    def test_07_second_dispatch_of_uncertain_never_sends(self):
        with TemporaryDirectory(prefix="a242-") as raw:
            path, store, outbox, key = _fixture(raw)
            adapter = Adapter()
            try:
                _dispatch(outbox, key, adapter)
                with self.assertRaisesRegex(ValueError, "must be CLAIMED"):
                    _dispatch(outbox, key, adapter)
                self.assertEqual(adapter.calls, 0)
            finally:
                store.close()

    def test_08_invalid_callback_type_rejected_at_construction(self):
        with TemporaryDirectory(prefix="a242-") as raw:
            store = SQLiteChatStore(Path(raw) / "outbox.db")
            try:
                for value in (True, 1, "yes"):
                    with self.subTest(value=value):
                        with self.assertRaises(TypeError):
                            ExecutionOutbox(store, SCOPE, first_attempt_guard=value)
            finally:
                store.close()

    def test_09_late_true_guard_cannot_send_after_state_changed(self):
        with TemporaryDirectory(prefix="a242-") as raw:
            refs = []
            def changing_guard(intent):
                outbox, key = refs
                outbox.db.execute(
                    "UPDATE action_outbox SET state='SENT' WHERE idempotency_key=?", (key,),
                )
                outbox.db.commit()
                return True
            path, store, outbox, key = _fixture(raw, changing_guard)
            refs.extend((outbox, key))
            adapter = Adapter()
            try:
                result = _dispatch(outbox, key, adapter)
                self.assertEqual(adapter.calls, 0)
                self.assertEqual(result["dispatch_state"], "NOT_DISPATCHED_STATE_CHANGED")
            finally:
                store.close()

    def test_10_pathname_failure_during_guard_blocks_send(self):
        with TemporaryDirectory(prefix="a242-") as raw:
            holders = []
            def path_changed(_):
                holders[0]._pathname_identity = (-1, -1)
                return True
            path, store, outbox, key = _fixture(raw, path_changed)
            holders.append(store)
            adapter = Adapter()
            try:
                with self.assertRaises(StorageUnavailableError):
                    _dispatch(outbox, key, adapter)
                self.assertEqual(adapter.calls, 0)
            finally:
                store.close()

    def test_11_denied_authorization_never_contacts_guard(self):
        with TemporaryDirectory(prefix="a242-") as raw:
            calls = []
            def guard(_):
                calls.append("called")
                return True
            path, store, outbox, key = _fixture(raw, guard)
            adapter = Adapter()
            try:
                result = _dispatch(outbox, key, adapter, authorize=lambda d: {**_auth(d), "allowed": False})
                self.assertEqual(calls, [])
                self.assertEqual(adapter.calls, 0)
                self.assertIn(result["state"], ("REVOKED", "BLOCKED_REAPPROVAL"))
            finally:
                store.close()

    def test_12_caller_injected_true_is_not_independent_authority(self):
        # A literal True from a local caller can still cross the test boundary.
        # This counterexample must remain explicit; P0-1/3/4 are NOT closed.
        with TemporaryDirectory(prefix="a242-") as raw:
            path, store, outbox, key = _fixture(raw, lambda _: True)
            adapter = Adapter()
            try:
                result = _dispatch(outbox, key, adapter)
                self.assertEqual(adapter.calls, 1)
                self.assertNotEqual(result["state"], "CONFIRMED")
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()
