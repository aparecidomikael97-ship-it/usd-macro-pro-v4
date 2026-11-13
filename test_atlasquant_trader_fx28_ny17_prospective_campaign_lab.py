"""Synthetic tests for frozen 672 nominal slots; NO broker or genuine forecasts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_m15_source_claim_lab import (
    expected_ny17_m15_endpoint_claim_lab,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_START_UTC, FROZEN_END_UTC, EXPECTED_PAIR_HORIZON_SLOTS,
    CALENDAR_ISSUE, _nominal_windows, inspect_frozen_fx28_ny17_campaign_lab as inspect,
)

NOW = datetime(2026, 12, 12, 0, tzinfo=timezone.utc)
PASS = "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO"
FULL = "LAB_AM12_NY17_FULL_ROSTER_LOCAL_CLAIMS_ONLY_NO_GO"
GAPS = "LAB_AM12_NY17_FULL_ROSTER_HAS_GAPS_NO_GO"


def make_roster(horizon: str, *, missing: dict[int, set[str]] | None = None):
    missing = missing or {}
    nominal = _nominal_windows(horizon)
    window_records = []
    missing_counts = {pair: 0 for pair in OFFICIAL_PAIRS}
    complete_counts = {pair: 0 for pair in OFFICIAL_PAIRS}
    complete_windows = 0
    complete_pair_slots = 0
    for ix, (start, end) in enumerate(nominal, 1):
        blocked = sorted(missing.get(ix, set()))
        for pair in OFFICIAL_PAIRS:
            if pair in blocked:
                missing_counts[pair] += 1
            else:
                complete_counts[pair] += 1
        checked = 28 - len(blocked)
        complete_pair_slots += checked
        is_full = checked == 28
        complete_windows += int(is_full)
        window_records.append({
            "window_number": ix,
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "local_archive_check_state": PASS if is_full else "LAB_GAPS_NO_GO",
            "pair_checks_complete_claim_only": checked,
            "pair_checks_blocked_or_unverifiable": len(blocked),
            "blocked_pairs": blocked,
            "unverifiable_pair_reasons": {pair: "MISSING_M15_LOCAL_FILE" for pair in blocked},
            "price_movements_documentary_by_pair": {
                pair: {
                    "start_open_documentary": "1.0000",
                    "end_close_documentary": "1.0010",
                    "change_bps_documentary": "10.0000",
                    "direction_documentary": "UP",
                    **expected_ny17_m15_endpoint_claim_lab(
                        start_at_utc=start, end_at_utc=end),
                } for pair in OFFICIAL_PAIRS if pair not in blocked
            },
        })
    n = len(nominal)
    return {
        "schema": "ATLASQUANT_TRADER_MT5_FULL_NY17_WINDOW_ROSTER_LAB_V1",
        "state": FULL if complete_windows == n else GAPS,
        "horizon": horizon,
        "range_start_utc": FROZEN_START_UTC.isoformat(),
        "range_end_utc": FROZEN_END_UTC.isoformat(),
        "nominal_window_count": n,
        "total_expected_pair_window_checks": n * 28,
        "complete_local_window_count": complete_windows,
        "blocked_or_incomplete_window_count": n - complete_windows,
        "local_pair_window_checks_complete": complete_pair_slots,
        "blocked_or_unverifiable_pair_window_checks": n * 28 - complete_pair_slots,
        "all_nominal_windows_locally_checked_complete": complete_windows == n,
        "unverifiable_window_counts_by_pair": missing_counts,
        "complete_window_counts_by_pair": complete_counts,
        "windows": window_records,
    }


class Ny17FrozenCampaignBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.d = make_roster("D1")
        self.w = make_roster("W1")

    def audit(self, d=None, w=None, at=NOW):
        return inspect(daily_price_roster=self.d if d is None else d,
                       weekly_price_roster=self.w if w is None else w,
                       inspected_at_utc=at)

    def safe(self, value):
        self.assertEqual(value["operational_bias"], "AGUARDAR")
        self.assertEqual(value["calendar_issue_url"], CALENDAR_ISSUE)
        self.assertEqual(value["expected_pair_horizon_slots"], 672)
        self.assertIsNone(value["calibrated_direction_probability"])
        self.assertIsNone(value["validated_directional_accuracy"])
        for key in (
            "calendar_github_timestamp_independently_verified_here",
            "pre_event_forecasts_witnessed",
            "broker_price_provenance_authenticated",
            "broker_trading_calendar_authenticated",
            "point_in_time_macro_authenticated",
            "out_of_sample_accuracy_validated",
            "independent_trial_count_validated",
            "publishable", "live_alert_allowed", "trade_authorized",
            "scheduler_enabled", "worker_enabled",
        ):
            self.assertFalse(value[key], key)
        self.assertEqual((value["http_requests"], value["file_writes"],
                          value["new_cost_brl"]), (0, 0, 0))
        self.assertTrue(value["research_only"])

    def test_frozen_calendar_has_twenty_daily_and_four_weekly_sessions(self):
        days = _nominal_windows("D1")
        weeks = _nominal_windows("W1")
        self.assertEqual((len(days), len(weeks)), (20, 4))
        self.assertEqual((days[0][0], days[-1][1]), (FROZEN_START_UTC, FROZEN_END_UTC))
        self.assertEqual((weeks[0][0], weeks[-1][1]), (FROZEN_START_UTC, FROZEN_END_UTC))
        self.assertEqual(EXPECTED_PAIR_HORIZON_SLOTS, 20 * 28 + 4 * 28)

    def test_synthetic_full_pair_census_is_not_market_validation(self):
        report = self.audit()
        self.assertEqual(report["state"],
                         "LAB_NY17_FROZEN_CAMPAIGN_LOCAL_ROSTER_ONLY_NO_GO")
        self.assertEqual(report["reconciled_pair_horizon_slots"], 672)
        self.assertEqual(report["unverifiable_pair_horizon_slots"], 0)
        self.assertTrue(report["frozen_calendar_scope_matched_locally"])
        self.assertEqual(report["per_horizon"]["D1"]["nominal_sessions"], 20)
        self.assertEqual(report["per_horizon"]["W1"]["nominal_sessions"], 4)
        self.safe(report)

    def test_broker_data_missing_one_pair_one_day_is_reported_not_hidden(self):
        r = make_roster("D1", missing={6: {OFFICIAL_PAIRS[0]}})
        report = self.audit(d=r)
        self.assertEqual(report["state"], "LAB_NY17_FROZEN_CAMPAIGN_HAS_GAPS_NO_GO")
        self.assertEqual(report["reconciled_pair_horizon_slots"], 671)
        self.assertEqual(report["unverifiable_pair_horizon_slots"], 1)
        self.assertEqual(report["per_horizon"]["D1"]["sessions_with_gaps"], 1)
        self.assertEqual(report["per_horizon"]["D1"]["documentary_unverifiable_pair_slots"], 1)
        self.safe(report)

    def test_all_prices_missing_in_one_session_keep_28_unverifiable_slots(self):
        r = make_roster("D1", missing={12: set(OFFICIAL_PAIRS)})
        report = self.audit(d=r)
        self.assertEqual(report["unverifiable_pair_horizon_slots"], 28)
        self.assertEqual(report["reconciled_pair_horizon_slots"], 644)
        self.safe(report)

    def test_shortened_range_veto_even_when_internal_totals_match(self):
        d = deepcopy(self.d)
        d["range_end_utc"] = (FROZEN_END_UTC - timedelta(days=7)).isoformat()
        report = self.audit(d=d)
        self.assertEqual(report["reason"], "D1_CAMPAIGN_BOUNDS_MISMATCH")
        self.assertFalse(report["frozen_calendar_scope_matched_locally"])
        self.safe(report)

    def test_missing_middle_session_veto_without_cherry_pick(self):
        d = deepcopy(self.d)
        del d["windows"][7]
        report = self.audit(d=d)
        self.assertEqual(report["reason"], "D1_NOMINAL_SESSION_OR_PAIR_SLOT_CENSUS_MISMATCH")
        self.safe(report)

    def test_swapped_weekly_window_with_same_count_is_blocked(self):
        w = deepcopy(self.w)
        w["windows"][2], w["windows"][3] = w["windows"][3], w["windows"][2]
        report = self.audit(w=w)
        self.assertEqual(report["reason"], "W1_MISSING_SWAPPED_OR_NONCANONICAL_SESSION")
        self.safe(report)

    def test_native_w1_or_d1_source_claim_cannot_be_used_in_campaign(self):
        for violation in ("W1", "D1", "missing", "native_true", "ny17_wrong_close"):
            with self.subTest(violation=violation):
                w = deepcopy(self.w)
                v = w["windows"][0]["price_movements_documentary_by_pair"][
                    OFFICIAL_PAIRS[0]]
                if violation in ("W1", "D1"):
                    v["source_timeframe_claim"] = violation
                elif violation == "missing":
                    v.pop("source_timeframe_claim")
                elif violation == "native_true":
                    v["native_mt5_d1_or_w1_used_as_endpoint"] = True
                else:
                    v["expected_last_m15_open_utc"] = (
                        datetime.fromisoformat(v["expected_last_m15_open_utc"])
                        + timedelta(hours=2)).isoformat()
                result = self.audit(w=w)
                self.safe(result)
                self.assertEqual(
                    result["reason"], "W1_PER_PAIR_MISSING_PRICE_DIAGNOSTICS")
                self.assertFalse(
                    result["all_documentary_completed_slots_claim_exact_m15_ny17_endpoints"])

    def test_d1_endpoints_also_required_to_avoid_mixed_denominators(self):
        d = deepcopy(self.d)
        row = d["windows"][0]["price_movements_documentary_by_pair"][
            OFFICIAL_PAIRS[0]]
        row["expected_first_m15_open_utc"] = (
            datetime.fromisoformat(row["expected_first_m15_open_utc"])
            + timedelta(minutes=15)).isoformat()
        result = self.audit(d=d)
        self.safe(result)
        self.assertEqual(result["reason"], "D1_PER_PAIR_MISSING_PRICE_DIAGNOSTICS")

    def test_corrupted_movement_direction_must_not_count_even_with_672_claimed(self):
        d = deepcopy(self.d)
        d["windows"][0]["price_movements_documentary_by_pair"][
            OFFICIAL_PAIRS[0]]["direction_documentary"] = "DOWN"
        report = self.audit(d=d)
        self.assertEqual(report["reason"], "D1_PER_PAIR_MISSING_PRICE_DIAGNOSTICS")
        self.assertEqual(report["reconciled_pair_horizon_slots"], 0)
        self.safe(report)

    def test_corrupted_price_bps_must_not_count_as_complete(self):
        d = deepcopy(self.d)
        d["windows"][0]["price_movements_documentary_by_pair"][
            OFFICIAL_PAIRS[0]]["change_bps_documentary"] = "20.0000"
        report = self.audit(d=d)
        self.assertEqual(report["reason"], "D1_PER_PAIR_MISSING_PRICE_DIAGNOSTICS")
        self.safe(report)

    def test_bad_aggregate_count_blocks_instead_of_claiming_672(self):
        d = deepcopy(self.d)
        d["local_pair_window_checks_complete"] = 559
        report = self.audit(d=d)
        self.assertEqual(report["reason"], "D1_AGGREGATE_PAIR_WINDOW_TOTALS_INCONSISTENT")
        self.safe(report)

    def test_missing_d1_or_w1_is_not_a_partial_success(self):
        for missing_day in (True, False):
            with self.subTest(missing_day=missing_day):
                report = self.audit(d={} if missing_day else None,
                                    w={} if not missing_day else None)
                self.assertEqual(report["state"], "LAB_NY17_PROSPECTIVE_BOUNDARY_BLOCKED")
                self.safe(report)

    def test_future_campaign_cannot_be_claimed_completed_now(self):
        report = self.audit(at=datetime(2026, 11, 12, 18, 30, tzinfo=timezone.utc))
        self.assertEqual(report["reason"], "INVALID_CLOCK_OR_CAMPAIGN_NOT_FINISHED")
        self.safe(report)


if __name__ == "__main__":
    unittest.main()
