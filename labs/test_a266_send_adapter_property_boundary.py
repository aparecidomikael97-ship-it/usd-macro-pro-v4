"""A266: no premature adapter.send attribute access on ordinary Outbox.

All adapter 'effects' in this suite are simulated Python counters, no network.
The LAB subclass deliberately exercises an unsafe synthetic reservation.
"""
import inspect
from pathlib import Path
import tempfile
import unittest

from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a259_synthetic_outbox_fixture import SyntheticFirstAttemptOutboxLab
from labs.test_a259_synthetic_callback_isolation import (
    NOW, SCOPE, _authorize, _claimed,
)


class GetterAdapter:
    def __init__(self, *, raise_on_get=False):
        self.accesses = 0
        self.calls = 0
        self.raise_on_get = raise_on_get

    @property
    def send(self):
        self.accesses += 1
        if self.raise_on_get:
            raise RuntimeError("synthetic getter attempted unsafe operation")

        def fake_send(decision, key):
            self.calls += 1
            return {
                "accepted": True,
                "confirmed": False,
                "effect_ref": "LAB-SYNTHETIC-NOT-REAL",
            }

        return fake_send


class WatchAllAttributes:
    def __init__(self):
        object.__setattr__(self, "reads", [])

    def __getattribute__(self, name):
        if name == "send":
            object.__getattribute__(self, "reads").append("send")
            raise AssertionError("unsafe adapter.send attribute read")
        return object.__getattribute__(self, name)


class A266AdapterGetterIsolationTests(unittest.TestCase):
    @staticmethod
    def _no_send_normal(adapter):
        tmp, store, outbox, key = _claimed()
        try:
            outcome = outbox.dispatch_claimed(
                key, worker_id="a259-worker",
                authorize=_authorize, adapter=adapter, now=NOW,
            )
            assert outcome["state"] == "UNCERTAIN", outcome
            assert outbox.effect_count() == 0
            assert outbox.claim_next("another-worker", now=NOW) is None
            return outcome
        finally:
            store.close()
            tmp.cleanup()

    def test_01_normal_outbox_never_reads_positive_getter(self):
        adapter = GetterAdapter()
        result = self._no_send_normal(adapter)
        self.assertEqual(adapter.accesses, 0)
        self.assertEqual(adapter.calls, 0)
        self.assertEqual(
            result["dispatch_state"], "UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED"
        )

    def test_02_normal_outbox_never_reads_throwing_property(self):
        adapter = GetterAdapter(raise_on_get=True)
        result = self._no_send_normal(adapter)
        self.assertEqual(adapter.accesses, 0)
        self.assertEqual(result["state"], "UNCERTAIN")

    def test_03_normal_outbox_never_reads_custom_getattribute(self):
        adapter = WatchAllAttributes()
        self._no_send_normal(adapter)
        self.assertEqual(adapter.reads, [])

    def test_04_adapter_absent_or_not_callable_cannot_reach_send_gate(self):
        for adapter in (None, 11, object(), {"send": True}):
            with self.subTest(type=type(adapter).__name__):
                result = self._no_send_normal(adapter)
                self.assertEqual(result["state"], "UNCERTAIN")

    def test_05_normal_outbox_does_not_reopen_after_uncertain(self):
        tmp, store, outbox, key = _claimed()
        try:
            adapter = GetterAdapter()
            first = outbox.dispatch_claimed(
                key, worker_id="a259-worker",
                authorize=_authorize, adapter=adapter, now=NOW,
            )
            self.assertEqual(first["state"], "UNCERTAIN")
            with self.assertRaisesRegex(ValueError, "CLAIMED"):
                outbox.dispatch_claimed(
                    key, worker_id="a259-worker", authorize=_authorize,
                    adapter=adapter, now=NOW,
                )
            self.assertEqual(adapter.accesses, 0)
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_06_lab_positive_reservation_getter_called_once_after_cas(self):
        tmp, store, outbox, key = _claimed(
            SyntheticFirstAttemptOutboxLab,
            first_attempt_guard=lambda _: True,
        )
        try:
            adapter = GetterAdapter()
            result = outbox.dispatch_claimed(
                key, worker_id="a259-worker",
                authorize=_authorize, adapter=adapter, now=NOW,
            )
            self.assertEqual(result["state"], "SENT")
            self.assertEqual(adapter.accesses, 1)
            self.assertEqual(adapter.calls, 1)
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_07_lab_getter_exception_preserves_uncertainty_and_no_resend(self):
        tmp, store, outbox, key = _claimed(
            SyntheticFirstAttemptOutboxLab,
            first_attempt_guard=lambda _: True,
        )
        try:
            adapter = GetterAdapter(raise_on_get=True)
            result = outbox.dispatch_claimed(
                key, worker_id="a259-worker",
                authorize=_authorize, adapter=adapter, now=NOW,
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(result["dispatch_state"], "UNCERTAIN_RECONCILE_REQUIRED")
            self.assertIn("RuntimeError", result["last_error"])
            self.assertEqual(adapter.accesses, 1)
            self.assertEqual(adapter.calls, 0)
            self.assertIsNone(outbox.claim_next("again", now=NOW))
        finally:
            store.close()
            tmp.cleanup()

    def test_08_lab_missing_send_method_is_conservative_uncertain(self):
        tmp, store, outbox, key = _claimed(
            SyntheticFirstAttemptOutboxLab,
            first_attempt_guard=lambda _: True,
        )
        try:
            result = outbox.dispatch_claimed(
                key, worker_id="a259-worker",
                authorize=_authorize, adapter=object(), now=NOW,
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertIn("TypeError", result["last_error"])
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_09_source_resolves_send_only_after_reservation_cas(self):
        # A267 moved the full callback-enabled dispatch into the explicit
        # LAB-only subclass. Ordinary Outbox has no adapter access at all.
        ordinary = inspect.getsource(ExecutionOutbox.dispatch_claimed)
        self.assertNotIn('getattr(adapter, "send", None)', ordinary)
        code = inspect.getsource(SyntheticFirstAttemptOutboxLab.dispatch_claimed)
        self.assertEqual(code.count('getattr(adapter, "send", None)'), 1)
        self.assertLess(
            code.index("reservation_ok = self._reserved_first_attempt(intent)"),
            code.index('getattr(adapter, "send", None)'),
        )
        self.assertLess(
            code.index("reservation_admitted = cursor.rowcount == 1"),
            code.index('getattr(adapter, "send", None)'),
        )
        self.assertLess(
            code.index("self._require_bound_store()\n        try:\n"),
            code.index('getattr(adapter, "send", None)'),
        )

    def test_10_restarted_normal_outbox_keeps_getter_quarantined(self):
        tmp, store, outbox, key = _claimed()
        path = Path(tmp.name) / "outbox.db"
        try:
            getter = GetterAdapter(raise_on_get=True)
            first = outbox.dispatch_claimed(
                key, worker_id="a259-worker",
                authorize=_authorize, adapter=getter, now=NOW,
            )
            self.assertEqual(first["state"], "UNCERTAIN")
            store.close()
            reopened = SQLiteChatStore(path)
            try:
                again = ExecutionOutbox(reopened, SCOPE)
                self.assertEqual(again.get(key)["state"], "UNCERTAIN")
                self.assertIsNone(again.claim_next("worker-again", now=NOW))
                self.assertEqual(getter.accesses, 0)
            finally:
                reopened.close()
        finally:
            store.close()
            tmp.cleanup()

    @unittest.expectedFailure
    def test_11_red_host_python_can_inject_synthetic_reserved_subclass(self):
        """Import/monkeypatch authority remains unsolved without trusted build."""
        tmp, store, outbox, key = _claimed(
            SyntheticFirstAttemptOutboxLab,
            first_attempt_guard=lambda _: True,
        )
        try:
            getter = GetterAdapter()
            outbox.dispatch_claimed(
                key, worker_id="a259-worker",
                authorize=_authorize, adapter=getter, now=NOW,
            )
            self.assertEqual(getter.accesses, 0)
        finally:
            store.close()
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
