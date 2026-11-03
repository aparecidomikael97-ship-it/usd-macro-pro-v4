"""Unknown-commit and client coordination tests; fake only, never external."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from atlasquant_trader_master_shared_quota_fake import (
    SCHEMA, FakeCentralQuotaBackend, SharedQuotaClientLab,
)

NOW = datetime(2026, 11, 2, 13, tzinfo=timezone.utc)


class SharedQuotaFakeTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeCentralQuotaBackend()
        self.assertEqual(self.backend.declare_policy(NOW.date(), 10, 2),
                         "DECLARED_LAB_ONLY")
        self.first = SharedQuotaClientLab(self.backend)
        self.second = SharedQuotaClientLab(self.backend)

    def call(self, key, cost=1, *, client=None, purpose="SCHEDULED", at=NOW,
             entitled=True):
        return (client or self.first).reserve(
            key, cost, at=at, purpose=purpose, entitlement_confirmed=entitled)

    def test_default_denial_is_side_effect_free(self):
        denied = self.first.reserve("s:1", 3, at=NOW, purpose="SCHEDULED")
        self.assertEqual(denied["state"], "PROVIDER_NOT_AUTHORIZED")
        self.assertEqual(self.backend.snapshot(NOW.date())["used_units_lab"], 0)

    def test_two_clients_share_one_weighted_budget(self):
        self.assertEqual(self.call("s:1", 4)["state"], "RESERVED_LAB_ONLY")
        self.assertEqual(self.call("s:2", 4, client=self.second)["state"],
                         "RESERVED_LAB_ONLY")
        self.assertEqual(self.call("s:3", 1)["state"], "DEMAND_RESERVE_PROTECTED")
        self.assertEqual(self.call("d:1", 2, client=self.second,
                                   purpose="ON_DEMAND")["state"],
                         "RESERVED_LAB_ONLY")
        self.assertEqual(self.backend.snapshot(NOW.date())["used_units_lab"], 10)

    def test_concurrent_clients_cannot_overbook(self):
        def attempt(i):
            client = SharedQuotaClientLab(self.backend)
            return client.reserve(f"s:parallel:{i}", 3, purpose="SCHEDULED",
                                  at=NOW, entitlement_confirmed=True)["state"]
        with ThreadPoolExecutor(max_workers=16) as pool:
            states = list(pool.map(attempt, range(20)))
        self.assertEqual(states.count("RESERVED_LAB_ONLY"), 2)
        self.assertEqual(states.count("DEMAND_RESERVE_PROTECTED"), 18)
        self.assertEqual(self.backend.snapshot(NOW.date())["used_units_lab"], 6)

    def test_same_key_idempotent_from_second_client(self):
        self.call("s:one", 3)
        result = self.call("s:one", 3, client=self.second)
        self.assertEqual(result["state"], "DUPLICATE")
        self.assertEqual(self.backend.snapshot(NOW.date())["used_units_lab"], 3)

    def test_commit_outcome_unknown_consumes_units_and_requires_reconcile(self):
        self.backend.commit_outcome_unknown_once = True
        first = self.call("s:uncertain", 5)
        self.assertEqual(first["state"], "COMMIT_OUTCOME_UNKNOWN_RECONCILE")
        self.assertFalse(first["retry_allowed"])
        self.assertEqual(self.backend.snapshot(NOW.date())["used_units_lab"], 5)
        inspected = self.second.reconcile("s:uncertain")
        self.assertEqual(inspected["state"], "RESERVATION_FOUND")
        self.assertEqual(inspected["attempt_state"], "RESERVED")
        self.assertEqual(inspected["cost_units"], 5)
        self.assertFalse(inspected["retry_allowed"])

    def test_uncertain_commit_without_visible_record_still_not_retriable(self):
        state = self.second.reconcile("not:found")
        self.assertEqual(state["state"], "NO_DURABLE_PROOF")
        self.assertFalse(state["retry_allowed"])

    def test_backend_unavailable_does_not_create_new_reservation(self):
        self.backend.available = False
        r = self.call("s:offline", 4)
        self.assertEqual(r["state"], "BACKEND_UNAVAILABLE")
        rec = self.first.reconcile("s:offline")
        self.assertEqual(rec["state"], "BACKEND_UNAVAILABLE")
        self.assertFalse(rec["retry_allowed"])
        self.assertEqual(self.backend.snapshot(NOW.date())["used_units_lab"], 0)

    def test_failed_provider_call_never_refunds_budget(self):
        self.call("s:failure", 5)
        self.assertEqual(self.backend.finish("s:failure", succeeded=False), "FAILED")
        self.assertEqual(self.backend.snapshot(NOW.date())["used_units_lab"], 5)
        self.assertEqual(self.backend.finish("s:failure", succeeded=True),
                         "ALREADY_FINALIZED")

    def test_unknown_policy_or_missing_day_blocks(self):
        day2 = NOW + timedelta(days=1)
        self.assertEqual(self.call("s:newday", 1, at=day2)["state"], "NO_POLICY")
        self.assertEqual(self.backend.snapshot(day2.date())["cap_units_lab"], None)

    def test_immutable_policy_conflict(self):
        self.assertEqual(self.backend.declare_policy(NOW.date(), 10, 2),
                         "UNCHANGED")
        self.assertEqual(self.backend.declare_policy(NOW.date(), 100, 2),
                         "POLICY_CONFLICT")
        self.assertEqual(self.backend.snapshot(NOW.date())["cap_units_lab"], 10)

    def test_invalid_cost_and_unaware_instant_rejected(self):
        for amount in (0, True, -1, None, 1.5, "1"):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    self.call("s:bad", amount)
        with self.assertRaises(ValueError):
            self.call("s:naive", at=datetime(2026, 11, 2, 13))

    def test_snapshots_never_claim_real_distributed_proof(self):
        s = self.backend.snapshot(NOW.date())
        self.assertEqual(s["schema"], SCHEMA)
        self.assertFalse(s["provider_counter_verified"])
        self.assertFalse(s["multi_host_verified"])
        self.assertFalse(s["scheduler_enabled"])
        self.assertFalse(s["aion_worker_enabled"])


if __name__ == "__main__":
    unittest.main()
