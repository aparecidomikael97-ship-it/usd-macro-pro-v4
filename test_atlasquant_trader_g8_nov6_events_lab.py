"""Only documentary as-of gates, using the fixed two-event casebook."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import unittest

from atlasquant_trader_g8_nov6_events_lab import (
    EXPECTED, EVENTS, KIND, SCHEMA,
    inspect_g8_nov6_documentary_events_lab as inspect,
)

RAW = Path(__file__).resolve().parent.joinpath(
    "docs/continuidade/TRADER_G8_NOV6_POST_RELEASE_EVENTOS_LAB_20261106.json"
).read_bytes()
BEFORE_GBP = datetime(2026, 11, 5, 23, 59, tzinfo=timezone.utc)
AFTER_GBP = datetime(2026, 11, 6, 0, 0, tzinfo=timezone.utc)
BEFORE_USD = datetime(2026, 11, 6, 13, 29, 59, tzinfo=timezone.utc)
AFTER_USD = datetime(2026, 11, 6, 13, 30, 0, tzinfo=timezone.utc)


def raw(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def checked(obj=None, *, at=AFTER_USD):
    return inspect(RAW if obj is None else raw(obj), as_of_utc=at)


class G8OfficialDocumentaryCaseTests(unittest.TestCase):
    def assert_hard_no_go(self, r):
        for key in (
            "official_source_bytes_independently_authenticated",
            "historical_source_capture_time_independently_attested",
            "pre_event_market_consensus_verified", "economic_surprise_verified",
            "cross_currency_macro_instruments_comparable",
            "market_reaction_prices_verified", "calibrated_directional_model_verified",
            "can_feed_live_radar", "trade_authorized", "worker_enabled",
            "scheduler_enabled", "publishable",
        ):
            self.assertIs(r[key], False, key)
        for field in ("validated_accuracy", "market_surprise",
                      "relative_currency_strength", "fx_bias"):
            self.assertIsNone(r[field], field)
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))

    def test_casebook_exactly_matches_source_documented_fixed_contract(self):
        self.assertEqual(json.loads(RAW), EXPECTED)
        self.assertEqual(EXPECTED["schema"], SCHEMA)
        self.assertEqual(EXPECTED["data_kind"], KIND)
        self.assertEqual(len(EVENTS), 2)
        self.assertTrue(all(x["pre_event_market_consensus_value"] is None for x in EVENTS))
        self.assertTrue(all(x["source_original_bytes_archived"] is False for x in EVENTS))

    def test_event_values_are_distinct_and_not_generic_fx_impulses(self):
        self.assertEqual(EVENTS[0]["reported_metrics"], {
            "bank_rate_percent_after": "4.00", "bank_rate_percent_before": "3.75",
            "announced_change_percentage_points": "0.25",
        })
        self.assertEqual(EVENTS[1]["reported_metrics"], {
            "nonfarm_payroll_monthly_change_persons_sa": "165000",
            "unemployment_rate_percent_sa": "4.1",
        })
        self.assertNotEqual(EVENTS[0]["factor_family"], EVENTS[1]["factor_family"])

    def test_before_both_release_safe_cutoffs_no_events_counted(self):
        r = checked(at=BEFORE_GBP)
        self.assertEqual(r["pair_count_by_documentary_sides"], {"0": 28, "1": 0, "2": 0})
        self.assertEqual(r["currencies_with_documentary_events"], [])
        self.assertEqual(len(r["not_yet_released_by_asof"]), 2)
        self.assert_hard_no_go(r)

    def test_gbp_date_only_conservative_next_utc_day_not_previous_day(self):
        r = checked(at=AFTER_GBP)
        self.assertEqual(r["currencies_with_documentary_events"], ["GBP"])
        self.assertEqual(r["pair_count_by_documentary_sides"], {"0": 21, "1": 7, "2": 0})
        self.assertEqual(r["documentary_events_not_before_asof"],
                         ["BOE_NOV2026_POLICY_DECISION"])
        self.assert_hard_no_go(r)

    def test_bls_1330_utc_embargo_respected_to_second(self):
        before, after = checked(at=BEFORE_USD), checked(at=AFTER_USD)
        self.assertEqual(before["currencies_with_documentary_events"], ["GBP"])
        self.assertEqual(after["currencies_with_documentary_events"], ["GBP", "USD"])
        self.assertEqual(after["pair_count_by_documentary_sides"], {"0": 15, "1": 12, "2": 1})
        self.assertEqual(after["casebook_sha256"], sha256(RAW).hexdigest())
        self.assert_hard_no_go(after)

    def test_gbpusd_has_two_different_event_types_not_two_comparable_surprises(self):
        r = checked()
        pair = next(p for p in r["pair_documentary_coverage"] if p["pair"] == "GBP/USD")
        self.assertEqual(pair["documented_event_sides_after_release"], 2)
        self.assertIs(pair["common_indicator_surprise_comparison_available"], False)
        self.assertEqual((pair["D1"], pair["W1"]), ("AGUARDAR", "AGUARDAR"))
        self.assertIsNone(pair["fx_bias"])
        self.assertFalse(pair["trade_authorized"])

    def test_all_28_pairs_still_await_with_any_coverage(self):
        r = checked()
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual(sum(r["pair_count_by_documentary_sides"].values()), 28)
        for p in r["pair_documentary_coverage"]:
            self.assertEqual((p["D1"], p["W1"]), ("AGUARDAR", "AGUARDAR"))
        self.assert_hard_no_go(r)

    def test_changed_actual_number_or_fictitious_consensus_rejected(self):
        for path, value in (("nonfarm_payroll_monthly_change_persons_sa", "200000"),
                            ("unemployment_rate_percent_sa", "4.0")):
            obj = deepcopy(EXPECTED)
            obj["events"][1]["reported_metrics"][path] = value
            self.assertEqual(checked(obj)["state"], "LAB_BLOCKED")
        obj = deepcopy(EXPECTED)
        obj["events"][1]["pre_event_market_consensus_value"] = "150000"
        self.assertEqual(checked(obj)["state"], "LAB_BLOCKED")

    def test_changed_publication_time_or_source_url_rejected(self):
        for field, value in (("earliest_conservative_after_release_utc", "2026-11-06T12:00:00Z"),
                             ("publication_time_precision", "EXACT_WITNESSED"),
                             ("source_url", "https://invented.example/data"),
                             ("source_original_bytes_archived", True)):
            obj = deepcopy(EXPECTED)
            obj["events"][1][field] = value
            self.assertEqual(checked(obj)["state"], "LAB_BLOCKED")

    def test_missing_extra_or_reordered_events_rejected(self):
        for transform in (lambda a: a.pop(),
                          lambda a: a.append(deepcopy(a[0])),
                          lambda a: a.reverse()):
            obj = deepcopy(EXPECTED)
            transform(obj["events"])
            self.assertEqual(checked(obj)["state"], "LAB_BLOCKED")

    def test_duplicate_json_keys_invalid_bytes_nan_and_bad_asof_rejected(self):
        for candidate in (b'not json', b'\xff', b'{"schema":NaN}',
                          RAW[:-2] + b',"schema":"OVERRIDE"}'):
            self.assertEqual(inspect(candidate, as_of_utc=AFTER_USD)["state"], "LAB_BLOCKED")
        self.assertEqual(checked(at=datetime(2026, 11, 6, 14))["state"], "LAB_BLOCKED")
        self.assertEqual(inspect(RAW, as_of_utc="2026-11-06")["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
