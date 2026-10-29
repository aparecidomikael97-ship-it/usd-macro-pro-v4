"""A267: ordinary Outbox never invokes caller-controlled authorizer or budget.

All effects are synthetic in-memory counters. No provider/Worker/network.
LAB subclass retains historical callback-enabled tests and remains unsafe
under arbitrary host Python execution. HARD NO-GO, P0 zero of six.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a259_synthetic_outbox_fixture import SyntheticFirstAttemptOutboxLab
from labs.test_a259_synthetic_callback_isolation import (
    NOW, SCOPE, SyntheticAdapter, _authorize, _claimed,
)


class SpyCallback:
    def __init__(self, answer=None):
        self.calls = 0
        self.answer = answer

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.answer is None:
            raise AssertionError("host callback must not be called")
        return self.answer


def _risk_claimed(typ=ExecutionOutbox, **kw):
    temp = TemporaryDirectory(prefix="a267-budget-")
    store = SQLiteChatStore(Path(temp.name) / "chat.sqlite3")
    outbox = typ(store, SCOPE, **kw)
    item = outbox.enqueue(
        intent_ref="a267-risk", action="synthetic-trade-guard",
        payload={"mock": True}, aggregate_key="a267-account",
        policy_version="lab", authorization_ref="lab-authorization",
        created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        transaction_id="a267-txn", authority_budget_ref="a267-budget",
        risk_points=5, capability_class="TRADER_READ_ONLY",
    )
    outbox.claim_next("a267-worker", now=NOW, lease_seconds=90)
    return temp, store, outbox, item["idempotency_key"]


class A267HostCallbackIsolationTests(unittest.TestCase):
    def test_01_authorizer_with_possible_effect_is_never_called(self):
        tmp, store, outbox, key = _claimed()
        try:
            auth, adapter = SpyCallback(), SyntheticAdapter()
            result = outbox.dispatch_claimed(
                key, worker_id="a259-worker", authorize=auth,
                adapter=adapter, now=NOW,
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(result["dispatch_state"],
                             "UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED")
            self.assertEqual(result["last_error"],
                             "NO_INDEPENDENT_AUTHORITY_NO_CALLBACK_NO_SEND")
            self.assertEqual((auth.calls, adapter.calls, outbox.effect_count()),
                             (0, 0, 0))
        finally:
            store.close()
            tmp.cleanup()

    def test_02_budget_callback_also_untouched_when_risk_ref_present(self):
        tmp, store, outbox, key = _risk_claimed()
        try:
            auth, budget, adapter = SpyCallback(), SpyCallback(), SyntheticAdapter()
            result = outbox.dispatch_claimed(
                key, worker_id="a267-worker", authorize=auth,
                cumulative_authority_guard=budget, adapter=adapter, now=NOW,
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual((auth.calls, budget.calls, adapter.calls), (0, 0, 0))
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_03_forged_positive_authorizer_and_budget_cannot_trigger(self):
        tmp, store, outbox, key = _risk_claimed()
        try:
            auth = SpyCallback({"allowed": True, "p0_homologated": 6})
            budget = SpyCallback({"allowed": True, "authority_budget_ref": "a267-budget"})
            adapter = SyntheticAdapter()
            result = outbox.dispatch_claimed(
                key, worker_id="a267-worker", authorize=auth,
                cumulative_authority_guard=budget, adapter=adapter, now=NOW,
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual((auth.calls, budget.calls, adapter.calls), (0, 0, 0))
        finally:
            store.close()
            tmp.cleanup()

    def test_04_callable_like_objects_and_none_not_inspected(self):
        for auth, budget, adapter in (
            (None, None, None),
            (object(), object(), object()),
            ({"approved": True}, {"budget": "GO"}, {"send": True}),
            (True, True, True),
        ):
            with self.subTest(authority=type(auth).__name__):
                tmp, store, outbox, key = _risk_claimed()
                try:
                    result = outbox.dispatch_claimed(
                        key, worker_id="a267-worker",
                        authorize=auth, cumulative_authority_guard=budget,
                        adapter=adapter, now=NOW,
                    )
                    self.assertEqual(result["state"], "UNCERTAIN")
                    self.assertEqual(result["reconcile_state"] if "reconcile_state" in result else result["dispatch_state"],
                                     "UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED")
                finally:
                    store.close()
                    tmp.cleanup()

    def test_05_expired_authority_blocked_without_callback(self):
        tmp = TemporaryDirectory(prefix="a267-expiry-")
        store = SQLiteChatStore(Path(tmp.name) / "outbox.db")
        try:
            outbox = ExecutionOutbox(store, SCOPE)
            item = outbox.enqueue(
                intent_ref="a267-expiry", action="lab-only",
                payload={"mock": True}, aggregate_key="expiry",
                policy_version="lab", authorization_ref="lab-auth",
                created_at=NOW, valid_until=NOW + timedelta(seconds=40),
            )
            outbox.claim_next("expiry-worker", now=NOW, lease_seconds=90)
            spy = SpyCallback()
            result = outbox.dispatch_claimed(
                item["idempotency_key"], worker_id="expiry-worker",
                authorize=spy, adapter=object(),
                now=NOW + timedelta(seconds=41),
            )
            self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
            self.assertEqual(result["last_error"], "AUTHORITY_EXPIRED")
            self.assertEqual(spy.calls, 0)
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_06_lease_owner_mismatch_never_calls_callbacks(self):
        tmp, store, outbox, key = _claimed()
        try:
            a, b = SpyCallback(), SpyCallback()
            with self.assertRaises(PermissionError):
                outbox.dispatch_claimed(
                    key, worker_id="other", authorize=a,
                    cumulative_authority_guard=b, adapter=object(), now=NOW,
                )
            self.assertEqual((a.calls, b.calls), (0, 0))
        finally:
            store.close()
            tmp.cleanup()

    def test_07_repeated_dispatch_is_no_auto_resend(self):
        tmp, store, outbox, key = _claimed()
        try:
            auth, budget = SpyCallback(), SpyCallback()
            outbox.dispatch_claimed(
                key, worker_id="a259-worker", authorize=auth,
                cumulative_authority_guard=budget, adapter=object(), now=NOW,
            )
            with self.assertRaises(ValueError):
                outbox.dispatch_claimed(
                    key, worker_id="a259-worker", authorize=auth,
                    cumulative_authority_guard=budget, adapter=object(), now=NOW,
                )
            self.assertEqual((auth.calls, budget.calls, outbox.effect_count()), (0, 0, 0))
            self.assertIsNone(outbox.claim_next("again", now=NOW + timedelta(hours=1)))
        finally:
            store.close()
            tmp.cleanup()

    def test_08_restart_retains_no_callbacks_and_uncertainty(self):
        tmp, store, outbox, key = _claimed()
        path = Path(tmp.name) / "outbox.db"
        try:
            spy = SpyCallback()
            result = outbox.dispatch_claimed(
                key, worker_id="a259-worker", authorize=spy, adapter=object(), now=NOW,
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            store.close()
            reopened = SQLiteChatStore(path)
            try:
                fresh = ExecutionOutbox(reopened, SCOPE)
                self.assertEqual(fresh.get(key)["state"], "UNCERTAIN")
                self.assertIsNone(fresh.claim_next("again", now=NOW+timedelta(hours=1)))
                self.assertEqual(spy.calls, 0)
            finally:
                reopened.close()
        finally:
            store.close()
            tmp.cleanup()

    def test_09_40_concurrent_separate_sqlite_handles_only_one_cas(self):
        tmp, store, outbox, key = _claimed()
        path = Path(tmp.name) / "outbox.db"
        try:
            auth = SpyCallback()
            def attempt(_):
                local_store = SQLiteChatStore(path)
                try:
                    local = ExecutionOutbox(local_store, SCOPE)
                    try:
                        return local.dispatch_claimed(
                            key, worker_id="a259-worker", authorize=auth,
                            adapter=object(), now=NOW,
                        )["dispatch_state"]
                    except ValueError:
                        return "ALREADY_UNCERTAIN"
                finally:
                    local_store.close()
            with ThreadPoolExecutor(max_workers=8) as pool:
                statuses = list(pool.map(attempt, range(40)))
            self.assertEqual(statuses.count("UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED"), 1)
            self.assertTrue(all(item in {
                "UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED",
                "NOT_DISPATCHED_STATE_CHANGED", "ALREADY_UNCERTAIN",
            } for item in statuses))
            self.assertEqual(auth.calls, 0)
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()
            tmp.cleanup()

    def test_10_synthetic_lab_preserves_legacy_callback_semantics(self):
        tmp, store, outbox, key = _claimed(
            SyntheticFirstAttemptOutboxLab, first_attempt_guard=lambda _: True,
        )
        try:
            auth = SpyCallback(_authorize(outbox.get(key)["decision"]))
            adapter = SyntheticAdapter()
            result = outbox.dispatch_claimed(
                key, worker_id="a259-worker", authorize=auth,
                adapter=adapter, now=NOW,
            )
            self.assertEqual(result["state"], "SENT")
            self.assertEqual((auth.calls, adapter.calls), (1, 1))
        finally:
            store.close()
            tmp.cleanup()

    def test_11_code_regular_dispatch_has_no_host_callback_calls(self):
        production = inspect.getsource(ExecutionOutbox.dispatch_claimed)
        legacy = inspect.getsource(SyntheticFirstAttemptOutboxLab.dispatch_claimed)
        self.assertNotIn("self._authorization_gate(", production)
        self.assertNotIn("cumulative_authority_guard(", production)
        self.assertNotIn("getattr(adapter", production)
        self.assertNotIn("send(dict(", production)
        self.assertIn("NO_INDEPENDENT_AUTHORITY_NO_CALLBACK_NO_SEND", production)
        self.assertIn("self._authorization_gate(", legacy)
        self.assertIn("cumulative_authority_guard(", legacy)

    def test_12_lab_is_not_automatically_imported_into_normal_outbox(self):
        src = inspect.getsource(ExecutionOutbox)
        self.assertNotIn("SyntheticFirstAttemptOutboxLab", src)
        self.assertTrue(SyntheticFirstAttemptOutboxLab.LAB_ONLY_UNTRUSTED_CALLBACK)

    @unittest.expectedFailure
    def test_13_red_host_with_arbitrary_python_can_use_unsafe_lab_subclass(self):
        tmp, store, outbox, key = _claimed(
            SyntheticFirstAttemptOutboxLab, first_attempt_guard=lambda _: True,
        )
        try:
            a = SpyCallback(_authorize(outbox.get(key)["decision"]))
            outbox.dispatch_claimed(
                key, worker_id="a259-worker", authorize=a,
                adapter=SyntheticAdapter(), now=NOW,
            )
            # Desired independent invariant but NOT achieved by Python-only
            # isolation when host can import arbitrary labs.
            self.assertEqual(a.calls, 0)
        finally:
            store.close()
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
