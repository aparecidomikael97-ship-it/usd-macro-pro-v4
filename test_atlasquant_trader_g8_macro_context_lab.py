"""Synthetic 8-currency / 28-pair macro coverage laboratory, no FX trade signals."""
from datetime import datetime, timedelta, timezone
import copy
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_bias_daily_freeze_lab import (
    freeze_daily_bias_observation_lab,
)
from atlasquant_trader_bias_forecast_bridge_lab import (
    FIXED_METHOD, SCHEMA as FORECAST_SCHEMA,
)
from atlasquant_trader_g8_macro_context_lab import (
    GROUPS, compare_g8_macro_coverage_lab,
)

ISSUED = datetime(2026, 11, 2, 11, tzinfo=timezone.utc)
AUDIT = datetime(2026, 11, 2, 18, tzinfo=timezone.utc)
INDICATOR = {
    "INFLATION": ("CPI", "PERCENT"),
    "EMPLOYMENT": ("UNEMPLOYMENT", "PERCENT"),
    "POLICY": ("POLICY_RATE", "PERCENT"),
    "ACTIVITY": ("PMI", "INDEX"),
}


def event(currency="USD", group="INFLATION", *, actual=3.3, indicator=None,
          unit=None):
    specified, standard_unit = INDICATOR[group]
    name = indicator or specified
    unit = unit or standard_unit
    identity = f"{currency}-{name}-202610"
    pending = actual is None
    pre = {
        "state": "LAB_SYNTHETIC_MACRO_PRE",
        "event_id": identity,
        "currency": currency, "indicator_id": name, "unit": unit,
        "source": "Fonte macro sintetica",
        "previous": 2.8, "consensus": 3.0,
        "previous_captured_at_utc": "2026-10-29T11:00:00+00:00",
        "consensus_captured_at_utc": "2026-10-30T12:00:00+00:00",
        "scheduled_release_at_utc": (
            "2026-11-02T14:00:00+00:00" if pending
            else "2026-10-30T14:00:00+00:00"
        ),
        "deadband_predeclared": 0.1,
    }
    result = None if pending else {
        "state": "LAB_SYNTHETIC_MACRO_ACTUAL",
        "event_id": identity, "actual": actual,
        "released_at_utc": "2026-10-30T14:00:00+00:00",
        "captured_at_utc": "2026-10-30T14:05:00+00:00",
        "source": "Boletim sintetico",
    }
    return {"preliminary": pre, "actual_release": result}


def compare(rows, **kwargs):
    return compare_g8_macro_coverage_lab(
        rows, forecast_issued_at=ISSUED, evaluated_at=AUDIT, **kwargs
    )


def full():
    return [
        event(currency, category)
        for currency in CURRENCIES
        for category in GROUPS
    ]


def batch():
    key = "g8-macro-lab"
    return {
        "schema": FORECAST_SCHEMA, "state": "LAB_SYNTHETIC_ISSUED",
        "batch_key": key, "method_id": FIXED_METHOD,
        "issued_at_utc": ISSUED.isoformat(),
        "forecasts": [
            {"forecast_id": f"{key}-{horizon}-{pair.replace('/', '')}",
             "pair": pair, "horizon": horizon, "state": "LAB_SYNTHETIC_BIAS",
             "bias": "AGUARDAR", "method_id": FIXED_METHOD,
             "issued_at_utc": ISSUED.isoformat(),
             "evidence_at_utc": (ISSUED-timedelta(minutes=10)).isoformat(),
             "trade_authorized": False}
            for pair in OFFICIAL_PAIRS
            for horizon in ("D1", "W1", "MN1")
        ],
    }


def strengths():
    return {
        "state": "LAB_SYNTHETIC_EVIDENCE",
        "kind": "G8_STRENGTH_REFERENCE", "evidence_id": "g8-strength-synthetic",
        "source": "Laboratorio sintético",
        "currencies": list(CURRENCIES),
        "data_as_of_utc": "2026-11-02T10:00:00+00:00",
        "captured_at_utc": "2026-11-02T10:30:00+00:00",
    }


class G8MacroComparisonLabTests(unittest.TestCase):
    def test_all_g8_currencies_28_pairs_four_groups_with_full_fixture(self):
        out = compare(full())
        self.assertEqual(out["state"], "LAB_SYNTHETIC_G8_MACRO_CONTEXT_ONLY")
        self.assertEqual(out["currency_count"], 8)
        self.assertEqual(out["pair_count"], 28)
        self.assertEqual(set(out["currency_matrix"]), set(CURRENCIES))
        self.assertEqual(set(out["pair_comparisons"]), set(OFFICIAL_PAIRS))
        self.assertEqual(out["synthetic_event_count"], 32)
        self.assertEqual(out["groups"], list(GROUPS))
        for pair in OFFICIAL_PAIRS:
            self.assertEqual(out["pair_comparisons"][pair]["bilateral_fresh_groups"], 4)

    def test_sparse_calendar_does_not_fake_missing_macro_context(self):
        out = compare([event("USD")])
        self.assertEqual(out["currency_matrix"]["USD"]["fresh_released_groups"], 1)
        self.assertEqual(len(out["currency_matrix"]["EUR"]["missing_groups"]), 4)
        self.assertEqual(out["pair_comparisons"]["EUR/USD"]["bilateral_fresh_groups"], 0)
        self.assertEqual(out["pair_comparisons"]["EUR/USD"]["fundamental_groups"]
                         ["INFLATION"]["status"], "INSUFFICIENT_BILATERAL_COVERAGE")

    def test_eurusd_base_quote_has_distinct_surprise_relations(self):
        out = compare([event("EUR", actual=2.5), event("USD", actual=3.3)])
        v = out["pair_comparisons"]["EUR/USD"]["fundamental_groups"]["INFLATION"]
        self.assertEqual(v["status"], "BOTH_RELEASED_FRESH")
        self.assertEqual(v["surprise_relation"], "DIFFERENT_RELEASE_RELATION")
        self.assertEqual(v["base"]["surprise_comparison"], "BELOW_CONSENSUS")
        self.assertEqual(v["quote"]["surprise_comparison"], "ABOVE_CONSENSUS")
        self.assertEqual(v["bullish_or_bearish_currency_inference"], "UNDETERMINED")

    def test_same_surprise_relation_does_not_assert_same_macro_policy(self):
        out = compare([event("EUR", actual=3.3), event("USD", actual=3.4)])
        v = out["pair_comparisons"]["EUR/USD"]["fundamental_groups"]["INFLATION"]
        self.assertEqual(v["surprise_relation"], "SAME_RELEASE_RELATION")
        self.assertIsNone(out["pair_comparisons"]["EUR/USD"]["macro_strength_score"])
        self.assertFalse(out["pair_comparisons"]["EUR/USD"]["rankable_as_signal"])

    def test_same_category_different_indicator_is_not_false_equivalence(self):
        out = compare([event("EUR", actual=3.3),
                       event("USD", actual=3.3, indicator="CORE_CPI")])
        v = out["pair_comparisons"]["EUR/USD"]["fundamental_groups"]["INFLATION"]
        self.assertEqual(v["status"], "BOTH_RELEASED_FRESH")
        self.assertFalse(v["matching_indicator_and_unit"])
        self.assertEqual(v["surprise_relation"], "NOT_COMPARABLE")

    def test_same_indicator_different_units_not_comparable(self):
        out = compare([event("EUR", actual=3.3, unit="BPS"),
                       event("USD", actual=3.3, unit="PERCENT")])
        v = out["pair_comparisons"]["EUR/USD"]["fundamental_groups"]["INFLATION"]
        self.assertFalse(v["matching_indicator_and_unit"])
        self.assertEqual(v["surprise_relation"], "NOT_COMPARABLE")

    def test_future_schedule_keeps_actual_and_surprise_absent(self):
        out = compare([event("USD", actual=None), event("EUR", actual=3.4)])
        pair = out["pair_comparisons"]["EUR/USD"]
        self.assertEqual(pair["fundamental_groups"]["INFLATION"]["status"],
                         "UNRELEASED_EVENT_PENDING")
        self.assertEqual(pair["bilateral_pending_groups"], 1)
        future = out["currency_matrix"]["USD"]["groups"]["INFLATION"]
        self.assertEqual(future["state"], "SCHEDULED_NOT_RELEASED")
        self.assertIsNone(future["actual"])
        self.assertIsNone(future["surprise"])
        self.assertFalse(future["fresh_for_context_only"])

    def test_expired_release_is_stale_not_recast_as_current(self):
        out = compare([event("EUR"), event("USD")], freshness_days=1)
        x = out["pair_comparisons"]["EUR/USD"]["fundamental_groups"]["INFLATION"]
        self.assertEqual(x["status"], "STALE_BILATERAL_CONTEXT")
        self.assertEqual(x["surprise_relation"], "NOT_COMPARABLE")
        self.assertEqual(x["base"]["state"], "STALE_RELEASE")

    def test_full_all_inflation_shows_other_three_groups_missing(self):
        out = compare([event(currency) for currency in CURRENCIES])
        for pair in OFFICIAL_PAIRS:
            self.assertEqual(out["pair_comparisons"][pair]["bilateral_fresh_groups"], 1)
        for currency in CURRENCIES:
            self.assertEqual(out["currency_matrix"][currency]["missing_groups"],
                             ["EMPLOYMENT", "POLICY", "ACTIVITY"])

    def test_duplicate_event_for_same_currency_group_is_rejected(self):
        rows = [event("USD", actual=3.3), event("USD", actual=3.4)]
        self.assertEqual(compare(rows)["state"], "LAB_REJECTED_MACRO_COMPARISON")

    def test_two_indicators_in_same_currency_group_cannot_be_cherry_picked(self):
        rows = [event("USD", indicator="CPI"),
                event("USD", indicator="CORE_CPI")]
        out = compare(rows)
        self.assertEqual(out["state"], "LAB_REJECTED_MACRO_COMPARISON")
        self.assertIn("Duplicate currency/group", out["reason"])

    def test_same_event_id_across_currencies_is_rejected(self):
        rows = [event("EUR"), event("USD")]
        rows[1]["preliminary"]["event_id"] = rows[0]["preliminary"]["event_id"]
        rows[1]["actual_release"]["event_id"] = rows[0]["actual_release"]["event_id"]
        self.assertEqual(compare(rows)["state"], "LAB_REJECTED_MACRO_COMPARISON")

    def test_different_groups_same_currency_are_allowed(self):
        out = compare([event("USD", "INFLATION"),
                       event("USD", "EMPLOYMENT"),
                       event("USD", "POLICY"),
                       event("USD", "ACTIVITY")])
        self.assertEqual(out["state"], "LAB_SYNTHETIC_G8_MACRO_CONTEXT_ONLY")
        self.assertEqual(out["currency_matrix"]["USD"]["fresh_released_groups"], 4)

    def test_released_data_after_cutoff_is_not_backfilled(self):
        item = event("USD")
        item["actual_release"]["released_at_utc"] = "2026-11-02T14:00:00+00:00"
        item["actual_release"]["captured_at_utc"] = "2026-11-02T14:01:00+00:00"
        out = compare([item])
        self.assertEqual(out["state"], "LAB_REJECTED_MACRO_COMPARISON")

    def test_consensus_captured_after_cutoff_is_rejected(self):
        item = event("USD")
        item["preliminary"]["consensus_captured_at_utc"] = (
            "2026-11-02T11:01:00+00:00")
        self.assertEqual(compare([item])["state"], "LAB_REJECTED_MACRO_COMPARISON")

    def test_future_release_beyond_research_calendar_is_rejected(self):
        item = event("USD", actual=None)
        item["preliminary"]["scheduled_release_at_utc"] = (
            "2027-02-01T14:00:00+00:00")
        self.assertEqual(compare([item])["state"], "LAB_REJECTED_MACRO_COMPARISON")

    def test_invalid_currency_or_indicator_is_rejected(self):
        for key, value in (("currency", "BRL"), ("indicator_id", "UNKNOWN"),
                           ("currency", []), ("indicator_id", [])):
            item = event()
            item["preliminary"][key] = value
            self.assertEqual(compare([item])["state"],
                             "LAB_REJECTED_MACRO_COMPARISON")

    def test_extra_future_fields_in_envelope_are_rejected(self):
        item = event("USD")
        item["future_return"] = 0.05
        self.assertEqual(compare([item])["state"], "LAB_REJECTED_MACRO_COMPARISON")

    def test_empty_missing_or_oversized_list_fails_closed(self):
        for values in (None, [], {}, [event()] * 33):
            self.assertEqual(compare(values)["state"], "LAB_REJECTED_MACRO_COMPARISON")

    def test_missing_actual_with_past_release_is_never_invented(self):
        item = event("USD")
        item["actual_release"] = None
        self.assertEqual(compare([item])["state"], "LAB_REJECTED_MACRO_COMPARISON")

    def test_no_automatic_veto_or_macro_direction_on_full_context(self):
        out = compare(full())
        self.assertEqual(out["automatic_macro_vetoes"], [])
        for name in CURRENCIES:
            self.assertEqual(out["currency_matrix"][name]["currency_macro_side"],
                             "UNDETERMINED")
        for pair in OFFICIAL_PAIRS:
            self.assertEqual(out["pair_comparisons"][pair]["macro_direction"],
                             "UNDETERMINED")

    def test_real_data_accuracy_authorizations_never_true(self):
        out = compare(full())
        for flag in ("independent_provider_validation", "real_historical_proven",
                     "macro_relative_strength_proven", "statistical_edge_proven",
                     "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(out[flag], flag)

    def test_synthetic_released_records_can_feed_existing_freeze_contract(self):
        out = compare([event("EUR"), event("USD")])
        evidences = [strengths()] + out["synthetic_freeze_evidences"]
        self.assertEqual(len(evidences), 3)
        frozen = freeze_daily_bias_observation_lab(
            batch(), evidences, checked_at=AUDIT)
        self.assertEqual(frozen["state"], "LAB_FROZEN_SYNTHETIC_OBSERVATION")
        self.assertEqual(frozen["macro_actuals_before_cutoff"], 2)
        self.assertFalse(frozen["real_market_sources_verified"])

    def test_synthetic_pending_event_freezes_without_actual(self):
        out = compare([event("USD", actual=None)])
        evidences = [strengths()] + out["synthetic_freeze_evidences"]
        frozen = freeze_daily_bias_observation_lab(
            batch(), evidences, checked_at=AUDIT)
        self.assertEqual(frozen["state"], "LAB_FROZEN_SYNTHETIC_OBSERVATION")
        self.assertEqual(frozen["macro_actuals_before_cutoff"], 0)
        self.assertEqual(frozen["macro_future_schedules_without_actual"], 1)

    def test_timezone_aware_cutoff_and_evaluation_required(self):
        with self.assertRaises(ValueError):
            compare_g8_macro_coverage_lab([event()], forecast_issued_at=
                datetime(2026, 11, 2, 11), evaluated_at=AUDIT)
        with self.assertRaises(ValueError):
            compare_g8_macro_coverage_lab([event()], forecast_issued_at=
                ISSUED, evaluated_at=datetime(2026, 11, 2, 18))

    def test_cutoff_after_evaluation_fails_closed(self):
        out = compare_g8_macro_coverage_lab(
            [event()], forecast_issued_at=AUDIT + timedelta(seconds=1),
            evaluated_at=AUDIT)
        self.assertEqual(out["state"], "LAB_REJECTED_MACRO_COMPARISON")

    def test_unbounded_or_boolean_freshness_refused(self):
        for x in (0, -1, 91, True, 2.5, "7"):
            with self.assertRaises(ValueError):
                compare([event()], freshness_days=x)

    def test_removing_actual_is_not_equal_to_preexisting_schedule(self):
        existing = event("USD")
        existing["actual_release"] = None
        self.assertEqual(compare([existing])["state"], "LAB_REJECTED_MACRO_COMPARISON")
        future = event("USD", actual=None)
        out = compare([future])
        self.assertEqual(out["state"], "LAB_SYNTHETIC_G8_MACRO_CONTEXT_ONLY")
        self.assertIsNone(out["currency_matrix"]["USD"]["groups"]["INFLATION"]["actual"])


if __name__ == "__main__":
    unittest.main()
