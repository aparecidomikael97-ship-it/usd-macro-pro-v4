"""A265: ordinary Outbox cannot query a caller-controlled reconciliation adapter.

The offline LAB fixture intentionally preserves previous synthetic behavior.
This is an API-level fail-closed improvement, not an external-trust system.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
import inspect
import tempfile
import unittest

from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a259_synthetic_outbox_fixture import SyntheticFirstAttemptOutboxLab
from labs.test_a259_synthetic_callback_isolation import (
    NOW, SCOPE, SyntheticAdapter, _authorize, _claimed,
)


class ActiveAdapter:
    def __init__(self):
        self.reconcile_calls = 0
        self.send_calls = 0

    def reconcile(self, key, decision):
        self.reconcile_calls += 1
        return {"found": True, "confirmed": True, "effect_ref": "FORGED"}

    def send(self, decision, key):
        self.send_calls += 1
        return {"accepted": True, "confirmed": True, "effect_ref": "FAKE"}


class RaisingPropertyAdapter:
    def __init__(self):
        self.property_reads = 0

    @property
    def reconcile(self):
        self.property_reads += 1
        raise AssertionError("adapter property access must not occur")


class A265ReconcileIsolationTests(unittest.TestCase):
    def setup_uncertain(self):
        tmp, store, outbox, key = _claimed()
        adapter = ActiveAdapter()
        result = outbox.dispatch_claimed(
            key, worker_id="a259-worker", authorize=_authorize,
            adapter=adapter, now=NOW,
        )
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(adapter.send_calls, 0)
        return tmp, store, outbox, key

    def test_01_positive_claim_never_queries_adapter(self):
        tmp, store, outbox, key = self.setup_uncertain()
        try:
            adapter = ActiveAdapter()
            result = outbox.reconcile(key, adapter=adapter, authorize=_authorize, now=NOW)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(
                result["reconcile_state"],
                "INDEPENDENT_RECEIPT_REQUIRED_NO_ADAPTER_QUERY",
            )
            self.assertEqual(adapter.reconcile_calls, 0)
            self.assertEqual(adapter.send_calls, 0)
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_02_lying_absence_adapter_is_not_queried(self):
        tmp, store, outbox, key = self.setup_uncertain()
        try:
            class Liar:
                calls = 0

                def reconcile(self, key, decision):
                    self.calls += 1
                    return {"found": False, "authoritative_absence": True}
            adapter = Liar()
            result = outbox.reconcile(key, adapter=adapter, authorize=_authorize)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.calls, 0)
            self.assertIsNone(outbox.claim_next("different-worker", now=NOW))
        finally:
            store.close()
            tmp.cleanup()

    def test_03_property_getter_cannot_run(self):
        tmp, store, outbox, key = self.setup_uncertain()
        try:
            adapter = RaisingPropertyAdapter()
            result = outbox.reconcile(
                key, adapter=adapter, authorize=lambda _: 1 / 0, now=NOW
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.property_reads, 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_04_noncallable_and_missing_adapter_are_not_inspected(self):
        tmp, store, outbox, key = self.setup_uncertain()
        try:
            for item in (None, 42, object(), {"verified": True}):
                with self.subTest(item=str(type(item))):
                    result = outbox.reconcile(
                        key, adapter=item, authorize=None, now=NOW
                    )
                    self.assertEqual(result["state"], "UNCERTAIN")
                    self.assertFalse(result["executes_action"])
        finally:
            store.close()
            tmp.cleanup()

    def test_05_sent_state_stays_sent_without_external_callback(self):
        tmp, store, lab, key = _claimed(
            SyntheticFirstAttemptOutboxLab,
            first_attempt_guard=lambda _: True,
        )
        try:
            actual = lab.dispatch_claimed(
                key, worker_id="a259-worker", authorize=_authorize,
                adapter=SyntheticAdapter(), now=NOW,
            )
            self.assertEqual(actual["state"], "SENT")
            normal = ExecutionOutbox(store, SCOPE)
            adapter = ActiveAdapter()
            result = normal.reconcile(
                key, adapter=adapter, authorize=_authorize, now=NOW
            )
            self.assertEqual(result["state"], "SENT")
            self.assertEqual(adapter.reconcile_calls, 0)
            self.assertEqual(normal.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_06_claimed_state_rejected_before_callback_access(self):
        tmp, store, outbox, key = _claimed()
        try:
            adapter = RaisingPropertyAdapter()
            with self.assertRaisesRegex(ValueError, "SENT or UNCERTAIN"):
                outbox.reconcile(key, adapter=adapter, authorize=_authorize)
            self.assertEqual(adapter.property_reads, 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_07_64_concurrent_queries_no_side_effects(self):
        tmp, store, outbox, key = self.setup_uncertain()
        try:
            adapter = ActiveAdapter()
            with ThreadPoolExecutor(max_workers=10) as pool:
                results = list(pool.map(
                    lambda _: outbox.reconcile(
                        key, adapter=adapter, authorize=_authorize, now=NOW,
                    ), range(64),
                ))
            self.assertEqual(len(results), 64)
            self.assertTrue(all(x["state"] == "UNCERTAIN" for x in results))
            self.assertEqual(adapter.reconcile_calls, 0)
            self.assertEqual(adapter.send_calls, 0)
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_08_restart_keeps_unresolved_without_provider_query(self):
        tmp, store, outbox, key = self.setup_uncertain()
        path = Path(tmp.name) / "outbox.db"
        try:
            store.close()
            reopened = SQLiteChatStore(path)
            try:
                normal = ExecutionOutbox(reopened, SCOPE)
                adapter = ActiveAdapter()
                result = normal.reconcile(
                    key, adapter=adapter, authorize=_authorize,
                    now=NOW + timedelta(minutes=2),
                )
                self.assertEqual(result["state"], "UNCERTAIN")
                self.assertEqual(adapter.reconcile_calls, 0)
                self.assertIsNone(normal.claim_next("new-worker", now=NOW + timedelta(hours=2)))
            finally:
                reopened.close()
        finally:
            store.close()
            tmp.cleanup()

    def test_09_legacy_lab_fixture_still_queries_fake_adapter(self):
        tmp, store, lab, key = _claimed(
            SyntheticFirstAttemptOutboxLab,
            first_attempt_guard=lambda _: True,
        )
        try:
            dispatched = lab.dispatch_claimed(
                key, worker_id="a259-worker", authorize=_authorize,
                adapter=SyntheticAdapter(), now=NOW,
            )
            self.assertEqual(dispatched["state"], "SENT")
            fake = ActiveAdapter()
            result = lab.reconcile(
                key, adapter=fake, authorize=_authorize, now=NOW
            )
            self.assertEqual(fake.reconcile_calls, 1)
            self.assertEqual(result["reconcile_state"], "UNTRUSTED_POSITIVE_HARD_NO_GO")
            self.assertEqual(lab.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_10_core_runtime_reconcile_source_has_no_adapter_access(self):
        code = inspect.getsource(ExecutionOutbox.reconcile)
        self.assertNotIn("getattr(adapter", code)
        self.assertNotIn("reconcile(key", code)
        self.assertIn("INDEPENDENT_RECEIPT_REQUIRED_NO_ADAPTER_QUERY", code)
        self.assertNotIn("labs.a259", inspect.getsource(ExecutionOutbox))

    def test_11_lab_override_explicitly_separate_from_core(self):
        self.assertIsNot(
            ExecutionOutbox.reconcile, SyntheticFirstAttemptOutboxLab.reconcile
        )
        self.assertIn("reconcile(key", inspect.getsource(
            SyntheticFirstAttemptOutboxLab.reconcile
        ))
        self.assertTrue(SyntheticFirstAttemptOutboxLab.LAB_ONLY_UNTRUSTED_CALLBACK)

    @unittest.expectedFailure
    def test_12_red_host_can_subclass_or_monkeypatch_runtime(self):
        """Python arbitrary-code host can override a no-send method; P0 OPEN."""
        tmp, store, outbox, key = self.setup_uncertain()
        try:
            original = outbox.reconcile
            adapter = ActiveAdapter()
            outbox.reconcile = lambda key, **kw: {
                "reconcile_state": adapter.reconcile_calls or
                adapter.reconcile(key, {})
            }
            outbox.reconcile(key, adapter=adapter, authorize=_authorize)
            self.assertEqual(adapter.reconcile_calls, 0)
        finally:
            outbox.reconcile = original
            store.close()
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
