"""A259: ordinary ExecutionOutbox rejects caller-controlled witness booleans.

The only remaining synthetic True path is explicitly in labs/ fixtures.
Nothing here authenticates independent witness custody or authorizes runtime.
"""
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a259_synthetic_outbox_fixture import SyntheticFirstAttemptOutboxLab
from labs.test_a243_signed_first_attempt import _attempt


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
SCOPE = Scope("owner-a259", "tenant-a259", "workspace-a259")


class SyntheticAdapter:
    def __init__(self):
        self.calls = 0

    def send(self, decision, key):
        self.calls += 1
        return {"accepted": True, "confirmed": False, "effect_ref": "lab-only"}


def _authorize(decision):
    return {
        "allowed": True, "actor_id": SCOPE.owner_id,
        "tenant_id": SCOPE.tenant_id, "workspace_id": SCOPE.workspace_id,
        "policy_version": decision["policy_version"],
        "authorization_ref": decision["authorization_ref"],
    }


def _claimed(typ=ExecutionOutbox, **kwargs):
    tmp = TemporaryDirectory(prefix="a259-")
    store = SQLiteChatStore(Path(tmp.name) / "outbox.db")
    outbox = typ(store, SCOPE, **kwargs)
    item = outbox.enqueue(
        intent_ref="a259-synthetic", action="test-action",
        payload={"lab_only": True}, aggregate_key="a259-aggregate",
        policy_version="lab-policy", authorization_ref="lab-approval",
        created_at=NOW, valid_until=NOW + timedelta(minutes=5),
    )
    key = item["idempotency_key"]
    outbox.claim_next("a259-worker", now=NOW, lease_seconds=90)
    return tmp, store, outbox, key


class A259IsolationTests(unittest.TestCase):
    def test_01_ordinary_constructor_rejects_local_true_callback(self):
        with TemporaryDirectory(prefix="a259-deny-") as raw:
            store = SQLiteChatStore(Path(raw) / "outbox.db")
            try:
                with self.assertRaises(TypeError):
                    ExecutionOutbox(store, SCOPE, first_attempt_guard=lambda _: True)
            finally:
                store.close()

    def test_02_ordinary_constructor_rejects_any_callback_even_false(self):
        with TemporaryDirectory(prefix="a259-deny-all-") as raw:
            store = SQLiteChatStore(Path(raw) / "outbox.db")
            try:
                for guard in (lambda _: False, lambda _: True, 1, "yes"):
                    with self.subTest(guard=str(guard)[:18]):
                        with self.assertRaises(TypeError):
                            ExecutionOutbox(store, SCOPE, first_attempt_guard=guard)
            finally:
                store.close()

    def test_03_ordinary_outbox_denies_send_with_no_connected_witness(self):
        tmp, store, outbox, key = _claimed()
        adapter = SyntheticAdapter()
        try:
            result = outbox.dispatch_claimed(
                key, worker_id="a259-worker", authorize=_authorize,
                adapter=adapter, now=NOW,
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.calls, 0)
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_04_mutating_legacy_callback_attribute_cannot_enable_send(self):
        tmp, store, outbox, key = _claimed()
        # This attribute was formerly consulted by ExecutionOutbox.
        outbox._first_attempt_guard = lambda _: True
        adapter = SyntheticAdapter()
        try:
            result = outbox.dispatch_claimed(
                key, worker_id="a259-worker", authorize=_authorize,
                adapter=adapter, now=NOW,
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.calls, 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_05_explicit_labs_fixture_keeps_synthetic_compatibility(self):
        result, sends, effects = _attempt(lambda _: True)
        self.assertEqual((result["state"], sends, effects), ("SENT", 1, 0))
        # SENT with a fake adapter is not proof of a real external effect.

    def test_06_labs_fixture_false_does_not_send(self):
        result, sends, effects = _attempt(lambda _: False)
        self.assertEqual((result["state"], sends, effects), ("UNCERTAIN", 0, 0))

    def test_07_type_signature_has_no_first_attempt_guard_parameter(self):
        self.assertNotIn(
            "first_attempt_guard", inspect.signature(ExecutionOutbox).parameters
        )
        self.assertIn(
            "return False",
            inspect.getsource(ExecutionOutbox._reserved_first_attempt),
        )
        self.assertNotIn(
            "_first_attempt_guard(",
            inspect.getsource(ExecutionOutbox._reserved_first_attempt),
        )

    def test_08_labs_fixture_is_explicit_subclass_not_runtime_default(self):
        self.assertIsNot(SyntheticFirstAttemptOutboxLab, ExecutionOutbox)
        self.assertTrue(issubclass(SyntheticFirstAttemptOutboxLab, ExecutionOutbox))
        self.assertIs(SyntheticFirstAttemptOutboxLab.LAB_ONLY_UNTRUSTED_CALLBACK, True)
        self.assertNotIn(
            "SyntheticFirstAttemptOutboxLab",
            inspect.getsource(ExecutionOutbox),
        )

    def test_09_lab_class_still_rejects_noncallable_guard(self):
        with TemporaryDirectory(prefix="a259-lab-type-") as raw:
            store = SQLiteChatStore(Path(raw) / "outbox.db")
            try:
                with self.assertRaises(TypeError):
                    SyntheticFirstAttemptOutboxLab(
                        store, SCOPE, first_attempt_guard=1
                    )
            finally:
                store.close()

    def test_10_without_callback_production_stays_no_send_after_restart(self):
        tmp, store, outbox, key = _claimed()
        path = Path(tmp.name) / "outbox.db"
        try:
            adapter = SyntheticAdapter()
            outbox.dispatch_claimed(
                key, worker_id="a259-worker", authorize=_authorize,
                adapter=adapter, now=NOW,
            )
            store.close()
            reopened = SQLiteChatStore(path)
            try:
                fresh = ExecutionOutbox(reopened, SCOPE)
                self.assertEqual(fresh.get(key)["state"], "UNCERTAIN")
                self.assertIsNone(
                    fresh.claim_next("other-worker", now=NOW + timedelta(hours=1))
                )
                self.assertEqual(adapter.calls, 0)
            finally:
                reopened.close()
        finally:
            store.close()
            tmp.cleanup()

    @unittest.expectedFailure
    def test_11_red_host_can_import_lab_fixture_and_force_synthetic_send(self):
        """LAB tests are not a runtime security sandbox against host code.

        A host that can execute arbitrary Python and import labs/ can still
        instantiate a permissive LAB subclass; deployment isolation,
        independent receipts and native authority remain prerequisites.
        """
        result, sends, effects = _attempt(lambda _: True)
        self.assertEqual((result["state"], sends, effects), ("UNCERTAIN", 0, 0))


if __name__ == "__main__":
    unittest.main()
