"""Date-gated official documentary cases; NO historical PIT/source attestation."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import unittest

from atlasquant_trader_eurusd_sep2026_policy_inflation_timeline_lab import (
    PINNED_POLICY_SHA256,
    inspect_eurusd_sep2026_policy_inflation_timeline_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
POLICY = (DOCS / "TRADER_EURUSD_POLICY_DECISIONS_SEPOCT2026_LAB_20261106.json").read_bytes()
CPI = (DOCS / "TRADER_EURUSD_SEP2026_OFFICIAL_HEADLINE_CONTEXT_LAB_20261106.json").read_bytes()
UTC = timezone.utc
NOW = datetime(2026, 11, 6, 19, tzinfo=UTC)


def at(month, day, hour=0, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


class EurUsdPolicyInflationTimelineTests(unittest.TestCase):
    def run_case(self, when=NOW, policy=POLICY, cpi=CPI):
        return inspect(policy, inflation_casebook_raw=cpi, as_of_utc=when)

    def assert_no_trade(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual(r["validated_forward_prediction_count"], 0)
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))
        self.assertIsNone(r["cross_currency_rate_spread_bps"])
        self.assertIsNone(r["cpi_surprise_percent"])
        for key in ("historical_original_policy_pages_attested",
                    "historical_original_inflation_pages_attested",
                    "independent_exact_release_times_attested",
                    "pre_meeting_expectations_verified", "pre_cpi_consensus_verified",
                    "policy_rate_instruments_directly_comparable",
                    "can_feed_live_radar", "trade_authorized", "publishable",
                    "worker_enabled", "scheduler_enabled"):
            self.assertFalse(r[key], key)

    def test_november_documentary_policy_and_cpi_context_both_present(self):
        r = self.run_case()
        self.assertEqual(r["state"],
                         "LAB_BOTH_POLICY_AND_SEP_CPI_DOCUMENTARY_CONTEXT_ONLY")
        self.assertTrue(r["inflation_and_policy_context_documentarily_present_for_both"])
        self.assertEqual(r["policy_casebook_sha256"], PINNED_POLICY_SHA256)
        self.assertEqual(len(r["known_policy_announcements"]), 4)
        self.assertEqual(r["inflation_visible_currencies"], ["USD", "EUR"])
        self.assert_no_trade(r)

    def test_before_september_ecb_decision_no_future_policy(self):
        r = self.run_case(at(9, 10, 23, 59))
        self.assertEqual(r["known_policy_announcements"], [])
        self.assertEqual(r["latest_effective_policy_level_by_currency"], {})
        self.assert_no_trade(r)

    def test_ecb_decision_known_before_effective_date_only_announced(self):
        r = self.run_case(at(9, 11))
        self.assertEqual(len(r["known_policy_announcements"]), 1)
        self.assertEqual(r["known_policy_announcements"][0]["currency"], "EUR")
        self.assertFalse(r["known_policy_announcements"][0][
            "announced_rate_or_range_in_effect_asof"])
        self.assertEqual(r["latest_effective_policy_level_by_currency"], {})
        self.assert_no_trade(r)

    def test_ecb_effective_sep16_without_leaking_fed_announcement(self):
        r = self.run_case(at(9, 16, 21))
        self.assertEqual(len(r["known_policy_announcements"]), 1)
        self.assertEqual(set(r["latest_effective_policy_level_by_currency"]), {"EUR"})
        self.assertEqual(r["latest_effective_policy_level_by_currency"]["EUR"]["level_percent"], 2.5)
        self.assert_no_trade(r)

    def test_both_september_rate_hikes_available_before_september_cpi(self):
        r = self.run_case(at(9, 17))
        self.assertEqual(len(r["known_policy_announcements"]), 2)
        self.assertEqual(set(r["latest_effective_policy_level_by_currency"]),
                         {"EUR", "USD"})
        self.assertEqual(r["latest_effective_policy_level_by_currency"]["USD"][
            "range_lower_percent"], 3.75)
        self.assertEqual(r["inflation_visible_currencies"], [])
        self.assert_no_trade(r)

    def test_oct15_us_cpi_but_eurostat_september_full_still_unknown(self):
        r = self.run_case(at(10, 15))
        self.assertEqual(r["inflation_visible_currencies"], ["USD"])
        self.assertFalse(r["inflation_and_policy_context_documentarily_present_for_both"])
        self.assertEqual(r["state"], "LAB_PARTIAL_DOCUMENTARY_CONTEXT_NO_DIRECTION")
        self.assertEqual(len(r["known_policy_announcements"]), 2)
        self.assert_no_trade(r)

    def test_oct17_after_both_full_cpi_but_not_october_policy_meetings(self):
        r = self.run_case(at(10, 17))
        self.assertTrue(r["inflation_and_policy_context_documentarily_present_for_both"])
        self.assertEqual(r["inflation_visible_currencies"], ["USD", "EUR"])
        self.assertEqual(len(r["known_policy_announcements"]), 2)
        self.assert_no_trade(r)

    def test_oct28_fed_hold_not_visible_until_oct29_and_ecb_until_oct30(self):
        r28 = self.run_case(at(10, 28, 23, 59))
        self.assertEqual(len(r28["known_policy_announcements"]), 2)
        r29 = self.run_case(at(10, 29))
        self.assertEqual(len(r29["known_policy_announcements"]), 3)
        self.assertEqual(r29["known_policy_announcements"][-1]["decision_action"], "HOLD")
        r30 = self.run_case(at(10, 30))
        self.assertEqual(len(r30["known_policy_announcements"]), 4)
        self.assert_no_trade(r28)
        self.assert_no_trade(r29)
        self.assert_no_trade(r30)

    def test_no_direct_cross_instrument_spread_even_after_all_documents(self):
        r = self.run_case()
        eur = r["latest_effective_policy_level_by_currency"]["EUR"]
        usd = r["latest_effective_policy_level_by_currency"]["USD"]
        self.assertEqual(eur["instrument"], "DEPOSIT_FACILITY_RATE")
        self.assertEqual(usd["instrument"], "FEDERAL_FUNDS_TARGET_RANGE")
        self.assertEqual(eur["level_percent"], 2.5)
        self.assertEqual((usd["range_lower_percent"], usd["range_upper_percent"]),
                         (3.75, 4.0))
        self.assert_no_trade(r)

    def test_timezone_aware_asof_normalizes_to_utc(self):
        d = datetime(2026, 10, 16, 16,
                     tzinfo=timezone(timedelta(hours=-4)))
        r = self.run_case(d)
        self.assertEqual(r["inflation_visible_currencies"], ["USD"])
        self.assert_no_trade(r)

    def test_tamper_any_policy_or_cpi_metadata_is_blocked(self):
        obj = json.loads(POLICY)
        obj["decisions"][1]["range_lower_percent"] = 3.5
        self.assertEqual(self.run_case(policy=json.dumps(obj).encode())["state"],
                         "LAB_BLOCKED")
        self.assertEqual(self.run_case(policy=POLICY + b" ")["state"], "LAB_BLOCKED")
        self.assertEqual(self.run_case(cpi=CPI + b" ")["state"], "LAB_BLOCKED")
        self.assert_no_trade(self.run_case(policy=POLICY + b" "))

    def test_bad_clock_and_invalid_raw_inputs_fail_closed(self):
        for when in (None, "2026-11-06", datetime(2026, 11, 6)):
            self.assertEqual(self.run_case(when)["state"], "LAB_BLOCKED")
        for item in (b"", None, "not bytes", {}, b"not JSON"):
            self.assertEqual(self.run_case(policy=item)["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
