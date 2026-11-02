"""Billable-unit LAB ledger: weighted budget, concurrency, and crash safety."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_trader_master_quota_units_lab import (
    BillableUnitsLab, SCHEMA, PROVIDER,
)

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


class BillableUnitsLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "units_lab.db"
        self.ledger = BillableUnitsLab(self.path)
        self.ledger.initialize()
        self.assertEqual(self.ledger.declare_daily_policy(
            NOW.date(), cap_units=10, demand_reserve_units=2,
            lab_approved=True), "DECLARED_LAB_ONLY")

    def tearDown(self):
        self.tmp.cleanup()

    def reserve(self, key, units=1, *, purpose="SCHEDULED", at=NOW,
                confirmed=True):
        return self.ledger.reserve(key, units, purpose=purpose,
                                   at=at, entitlement_confirmed=confirmed)

    def test_no_auto_database_creation_on_construction(self):
        p = Path(self.tmp.name) / "never_created.db"
        BillableUnitsLab(p)
        self.assertFalse(p.exists())
        self.assertEqual(SCHEMA, "ATLASQUANT_MASTER_BILLABLE_UNITS_LAB_V1")

    def test_entitlement_gate_is_disabled_by_default(self):
        r = self.ledger.reserve("request:a", 1, purpose="SCHEDULED", at=NOW)
        self.assertEqual(r["state"], "PROVIDER_NOT_AUTHORIZED")
        self.assertEqual(self.ledger.snapshot(NOW.date())["units_reserved_lab"], 0)

    def test_unknown_or_non_integer_cost_refused(self):
        for cost in (None, 0, -1, True, 1.5, "1", 10001):
            with self.subTest(cost=cost):
                with self.assertRaises(ValueError):
                    self.reserve("request:invalid", cost)
        self.assertEqual(self.ledger.snapshot(NOW.date())["units_reserved_lab"], 0)

    def test_weighted_scheduled_budget_protects_demand_reserve(self):
        self.assertEqual(self.reserve("s:1", 3)["state"], "RESERVED_LAB_ONLY")
        self.assertEqual(self.reserve("s:2", 3)["state"], "RESERVED_LAB_ONLY")
        self.assertEqual(self.reserve("s:3", 3)["state"], "DEMAND_RESERVE_PROTECTED")
        self.assertEqual(self.reserve("d:1", 2, purpose="ON_DEMAND")["state"],
                         "RESERVED_LAB_ONLY")
        snap = self.ledger.snapshot(NOW.date())
        self.assertEqual(snap["scheduled_units_lab"], 6)
        self.assertEqual(snap["units_reserved_lab"], 8)
        self.assertEqual(snap["remaining_units_lab"], 2)

    def test_total_cap_blocks_demand_even_if_scheduled_reserve_exists(self):
        self.reserve("s:1", 8)
        self.reserve("d:1", 2, purpose="ON_DEMAND")
        self.assertEqual(self.reserve("d:2", 1, purpose="ON_DEMAND")["state"],
                         "DAILY_UNITS_EXHAUSTED")

    def test_replay_request_key_never_reserves_twice(self):
        self.assertTrue(self.reserve("s:unique", 4)["reserved"])
        duplicate = self.reserve("s:unique", 4)
        self.assertEqual(duplicate["state"], "DUPLICATE")
        self.assertEqual(self.ledger.snapshot(NOW.date())["units_reserved_lab"], 4)

    def test_restart_does_not_reset_units(self):
        self.reserve("s:spent", 8)
        restarted = BillableUnitsLab(self.path)
        out = restarted.reserve("s:restart", 1, purpose="SCHEDULED",
                                at=NOW, entitlement_confirmed=True)
        self.assertEqual(out["state"], "DEMAND_RESERVE_PROTECTED")

    def test_failed_request_consumes_full_estimated_units(self):
        self.reserve("s:failure", 4)
        self.assertEqual(self.ledger.finish(
            "s:failure", succeeded=False, error_code="HTTP_429"), "FAILED")
        self.assertEqual(self.reserve("s:another", 5)["state"],
                         "DEMAND_RESERVE_PROTECTED")
        self.assertEqual(self.ledger.snapshot(NOW.date())["units_reserved_lab"], 4)

    def test_crashed_or_unfinished_reservation_is_conservative(self):
        self.reserve("s:crash", 8)
        new = BillableUnitsLab(self.path)
        self.assertEqual(new.reserve("s:new", 1, purpose="SCHEDULED",
                                     at=NOW, entitlement_confirmed=True)["state"],
                         "DEMAND_RESERVE_PROTECTED")
        self.assertEqual(self.ledger.finish("s:crash", succeeded=True), "SUCCEEDED")
        self.assertEqual(self.ledger.finish("s:crash", succeeded=False),
                         "ALREADY_FINALIZED")

    def test_separate_clients_cannot_overspend_under_concurrency(self):
        def reserve_once(i):
            replica = BillableUnitsLab(self.path)
            return replica.reserve(f"s:parallel:{i}", 3,
                                   purpose="SCHEDULED", at=NOW,
                                   entitlement_confirmed=True)["state"]
        with ThreadPoolExecutor(max_workers=16) as pool:
            states = list(pool.map(reserve_once, range(20)))
        self.assertEqual(states.count("RESERVED_LAB_ONLY"), 2)
        self.assertEqual(states.count("DEMAND_RESERVE_PROTECTED"), 18)
        self.assertEqual(self.ledger.snapshot(NOW.date())["units_reserved_lab"], 6)

    def test_policy_cannot_be_silently_raised(self):
        self.assertEqual(self.ledger.declare_daily_policy(
            NOW.date(), cap_units=10, demand_reserve_units=2,
            lab_approved=True), "UNCHANGED")
        self.assertEqual(self.ledger.declare_daily_policy(
            NOW.date(), cap_units=100, demand_reserve_units=2,
            lab_approved=True), "POLICY_CONFLICT")
        self.assertEqual(self.ledger.snapshot(NOW.date())["cap_units_lab"], 10)

    def test_new_day_requires_new_policy_and_utc_reset(self):
        later = NOW + timedelta(days=1)
        self.assertEqual(self.reserve("next:without:policy", 1, at=later)["state"],
                         "NO_APPROVED_LAB_POLICY")
        self.assertEqual(self.ledger.declare_daily_policy(
            later.date(), cap_units=10, demand_reserve_units=2,
            lab_approved=True), "DECLARED_LAB_ONLY")
        self.assertEqual(self.reserve("next:with:policy", 3, at=later)["state"],
                         "RESERVED_LAB_ONLY")
        self.assertEqual(self.ledger.snapshot(NOW.date())["units_reserved_lab"], 0)

    def test_unapproved_daily_policy_never_exists(self):
        tomorrow = NOW.date() + timedelta(days=1)
        self.assertEqual(self.ledger.declare_daily_policy(
            tomorrow, cap_units=10, demand_reserve_units=2), "DISABLED")
        self.assertIsNone(self.ledger.snapshot(tomorrow)["cap_units_lab"])

    def test_status_never_claims_provider_balance_or_live_activation(self):
        snap = self.ledger.snapshot(NOW.date())
        self.assertEqual(snap["provider"], PROVIDER)
        self.assertFalse(snap["provider_meter_verified"])
        self.assertFalse(snap["global_multi_host_quota_proven"])
        self.assertFalse(snap["scheduler_enabled"])
        self.assertFalse(snap["aion_worker_enabled"])
        self.assertFalse(snap["trade_authorized"])

    def test_secret_not_returned_by_status_or_errors(self):
        self.reserve("no_secret_in_key", 1)
        self.assertNotIn("MY_PRIVATE_TOKEN", str(self.ledger.snapshot(NOW.date())))
        with self.assertRaises(ValueError):
            self.reserve("contains space MY_PRIVATE_TOKEN", 1)


if __name__ == "__main__":
    unittest.main()
