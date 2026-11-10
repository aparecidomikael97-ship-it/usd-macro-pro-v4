"""Synthetic as-of release receipts. No authenticated data or backtest accuracy."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_macro_asof_lab import (
    ENVELOPE, EXPECTED, inspect_g8_pair_macro_asof_lab as inspect,
)

NOW = datetime(2026, 11, 6, 14, tzinfo=timezone.utc)
DECISION = "2026-11-05T12:00:00Z"


def record(currency, indicator, *, published="2026-10-29T12:00:00Z",
           captured="2026-10-29T12:05:00Z", period="2026-09", value="2.0"):
    return {
        "currency": currency, "indicator": indicator,
        "observation_period": period, "value": value,
        "published_at_utc": published, "captured_at_utc": captured,
        "source_type": ("CENTRAL_BANK" if indicator == "POLICY_RATE"
                        else "OFFICIAL_STATISTICS_OFFICE"),
        "source_sha256": "a" * 64,
    }


def sample(pair="EUR/USD"):
    a, b = pair.split("/")
    return {"schema": ENVELOPE, "pair": pair, "decision_at_utc": DECISION,
            "records": [record(c, i) for c in (a, b) for i in EXPECTED]}


def raw(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def run(obj=None, *, as_of=NOW):
    return inspect(raw(sample() if obj is None else obj) if not isinstance(obj, bytes) else obj,
                   as_of_utc=as_of)


class G8PairMacroAsOfTests(unittest.TestCase):
    def assert_no_go(self, r):
        for key in (
            "independent_release_time_attested", "source_origin_authenticated",
            "source_raw_bytes_independently_verified",
            "point_in_time_vintage_independently_verified",
            "macro_values_verified_by_issuer",
            "independent_broker_m15_prices_verified", "trade_authorized",
            "can_feed_live_radar", "worker_enabled", "scheduler_enabled", "publishable",
        ):
            self.assertIs(r[key], False, key)
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))

    def test_complete_two_sided_macro_receipts_are_still_unattested(self):
        data = sample()
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED")
        self.assertEqual(r["pair_currencies"], ["EUR", "USD"])
        self.assertEqual(r["records_seen"], 4)
        self.assertTrue(r["all_metadata_chronological"])
        self.assertTrue(r["all_required_indicators_present"])
        self.assertEqual(r["missing_or_stale"], [])
        self.assertEqual(r["input_sha256"], sha256(raw(data)).hexdigest())
        for c in ("EUR", "USD"):
            self.assertEqual(set(r["selected_observations"][c]), set(EXPECTED))
            for obs in r["selected_observations"][c].values():
                self.assertFalse(obs["measurement_verified"])
                self.assertNotIn("value", obs)
        self.assert_no_go(r)

    def test_works_for_every_canonical_forex_pair_no_bias(self):
        self.assertEqual(len(OFFICIAL_PAIRS), 28)
        for pair in OFFICIAL_PAIRS:
            r = run(sample(pair))
            self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED")
            self.assertEqual(r["pair"], pair)
            self.assert_no_go(r)

    def test_one_missing_currency_indicator_is_explicitly_incomplete(self):
        data = sample()
        data["records"] = [x for x in data["records"]
                           if not (x["currency"] == "USD" and x["indicator"] == "CPI_YOY")]
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_INCOMPLETE_UNATTESTED")
        self.assertEqual(r["missing_or_stale"], ["USD:CPI_YOY:MISSING"])
        self.assert_no_go(r)

    def test_predecision_publication_after_decision_is_blocked(self):
        data = sample()
        data["records"][0]["published_at_utc"] = "2026-11-05T12:00:01Z"
        data["records"][0]["captured_at_utc"] = "2026-11-05T12:00:02Z"
        r = run(data)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["reason"], "RELEASE_LOOKAHEAD_OR_CHRONOLOGY_INVALID")
        self.assert_no_go(r)

    def test_capture_after_decision_cannot_retroactively_join(self):
        data = sample()
        data["records"][1]["captured_at_utc"] = "2026-11-05T12:00:01Z"
        self.assertEqual(run(data)["state"], "LAB_BLOCKED")

    def test_capture_before_release_rejected(self):
        data = sample()
        data["records"][0]["captured_at_utc"] = "2026-10-29T11:59:59Z"
        self.assertEqual(run(data)["state"], "LAB_BLOCKED")

    def test_exact_decision_boundary_is_allowed_but_not_attested(self):
        data = sample()
        data["records"][0]["captured_at_utc"] = DECISION
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED")
        self.assert_no_go(r)

    def test_stale_cpi_is_missing_not_forward_filled(self):
        data = sample()
        data["records"][0]["published_at_utc"] = "2026-08-01T12:00:00Z"
        data["records"][0]["captured_at_utc"] = "2026-08-01T12:01:00Z"
        data["records"][0]["observation_period"] = "2026-07"
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_INCOMPLETE_UNATTESTED")
        self.assertEqual(r["missing_or_stale"], ["EUR:CPI_YOY:STALE"])
        self.assert_no_go(r)

    def test_nzd_quarterly_cpi_can_cover_until_next_quarterly_release(self):
        data = sample("GBP/NZD")
        data["decision_at_utc"] = "2026-12-30T12:00:00Z"
        for row in data["records"]:
            if row["currency"] == "NZD" and row["indicator"] == "CPI_YOY":
                row.update(observation_period="2026-Q3", published_at_utc="2026-10-21T21:45:00Z",
                           captured_at_utc="2026-10-21T21:45:01Z", value="3.7")
            elif row["indicator"] == "CPI_YOY":
                row.update(observation_period="2026-11", published_at_utc="2026-12-10T07:00:00Z",
                           captured_at_utc="2026-12-10T07:00:01Z")
        r = run(data, as_of=datetime(2026, 12, 30, 12, tzinfo=timezone.utc))
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED")
        self.assertEqual(r["selected_observations"]["NZD"]["CPI_YOY"]["observation_frequency"], "QUARTERLY")
        self.assertEqual(r["selected_observations"]["NZD"]["CPI_YOY"]["freshness_limit_days"], 120)
        self.assert_no_go(r)

    def test_monthly_cpi_does_not_inherit_quarterly_freshness(self):
        data = sample()
        data["decision_at_utc"] = "2026-12-30T12:00:00Z"
        for row in data["records"]:
            if row["indicator"] == "POLICY_RATE":
                row.update(published_at_utc="2026-11-02T12:00:00Z",
                           captured_at_utc="2026-11-02T12:01:00Z")
            elif row["currency"] == "EUR":
                row.update(observation_period="2026-09", published_at_utc="2026-10-21T06:00:00Z",
                           captured_at_utc="2026-10-21T06:00:01Z")
            else:
                row.update(observation_period="2026-11", published_at_utc="2026-12-10T12:00:00Z",
                           captured_at_utc="2026-12-10T12:01:00Z")
        r = run(data, as_of=datetime(2026, 12, 30, 12, tzinfo=timezone.utc))
        self.assertEqual(r["missing_or_stale"], ["EUR:CPI_YOY:STALE"])
        self.assert_no_go(r)

    def test_future_quarter_is_rejected_even_when_same_year(self):
        data = sample("GBP/NZD")
        data["records"][0]["observation_period"] = "2026-Q4"
        self.assertEqual(run(data)["reason"], "RELEASE_LOOKAHEAD_OR_CHRONOLOGY_INVALID")

    def test_quarterly_policy_rate_is_refused(self):
        data = sample("GBP/NZD")
        data["records"][1]["observation_period"] = "2026-Q3"
        self.assertEqual(run(data)["reason"], "RELEASE_LOOKAHEAD_OR_CHRONOLOGY_INVALID")

    def test_quarter_must_end_before_publication(self):
        data = sample("GBP/NZD")
        data["records"][0]["observation_period"] = "2026-Q3"
        data["records"][0]["published_at_utc"] = "2026-09-29T12:00:00Z"
        data["records"][0]["captured_at_utc"] = "2026-09-29T12:01:00Z"
        self.assertEqual(run(data)["reason"], "RELEASE_LOOKAHEAD_OR_CHRONOLOGY_INVALID")

    def test_invalid_quarter_format_refused(self):
        for period in ("2026-Q0", "2026-Q5", "2026-Q03", "Q3-2026", "2026-q3"):
            data = sample("GBP/NZD")
            data["records"][0]["observation_period"] = period
            self.assertEqual(run(data)["state"], "LAB_BLOCKED", period)

    def test_stale_previous_period_is_not_selected_over_fresh_one(self):
        data = sample()
        stale = record("EUR", "CPI_YOY", published="2026-08-01T12:00:00Z",
                       captured="2026-08-01T12:01:00Z", period="2026-07")
        data["records"].append(stale)
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED")
        self.assertEqual(r["records_seen"], 5)

    def test_later_republication_of_older_month_cannot_replace_newer_observation(self):
        data = sample()
        data["records"].append(record(
            "EUR", "CPI_YOY", published="2026-10-31T12:00:00Z",
            captured="2026-10-31T12:01:00Z", period="2026-07", value="2.5"))
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED")
        self.assertEqual(r["selected_observations"]["EUR"]["CPI_YOY"]["observation_period"],
                         "2026-09")
        self.assertEqual(r["selected_observations"]["EUR"]["CPI_YOY"]["published_at_utc_claim"],
                         "2026-10-29T12:00:00Z")
        self.assert_no_go(r)

    def test_obsolete_monthly_cpi_republished_now_is_not_fresh_data(self):
        data = sample()
        data["records"][0]["observation_period"] = "2025-09"
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_INCOMPLETE_UNATTESTED")
        self.assertEqual(r["missing_or_stale"], ["EUR:CPI_YOY:STALE"])
        self.assert_no_go(r)

    def test_obsolete_policy_rate_observation_republished_now_is_not_fresh(self):
        data = sample()
        data["records"][1]["observation_period"] = "2025-07"
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_INCOMPLETE_UNATTESTED")
        self.assertEqual(r["missing_or_stale"], ["EUR:POLICY_RATE:STALE"])
        self.assert_no_go(r)

    def test_obsolete_quarterly_cpi_republished_now_is_not_fresh_data(self):
        data = sample("GBP/NZD")
        for row in data["records"]:
            if row["currency"] == "NZD" and row["indicator"] == "CPI_YOY":
                row["observation_period"] = "2025-Q3"
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_INCOMPLETE_UNATTESTED")
        self.assertEqual(r["missing_or_stale"], ["NZD:CPI_YOY:STALE"])
        self.assert_no_go(r)

    def test_observation_period_age_cutoff_has_no_off_by_one(self):
        data = sample()
        data["records"][0]["observation_period"] = "2026-07"
        data["decision_at_utc"] = "2026-11-03T12:00:00Z"  # July 31 + 95 days
        boundary = run(data)
        self.assertEqual(boundary["state"], "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED")
        row = boundary["selected_observations"]["EUR"]["CPI_YOY"]
        self.assertEqual(row["observation_period_age_days"], 95)
        self.assertEqual(row["observation_period_age_limit_days"], 95)
        self.assert_no_go(boundary)
        data["decision_at_utc"] = "2026-11-04T12:00:00Z"
        expired = run(data)
        self.assertEqual(expired["missing_or_stale"], ["EUR:CPI_YOY:STALE"])
        self.assert_no_go(expired)

    def test_later_republication_of_older_quarter_cannot_replace_newer_quarter(self):
        data = sample("GBP/NZD")
        for row in data["records"]:
            if row["currency"] == "NZD" and row["indicator"] == "CPI_YOY":
                row.update(observation_period="2026-Q3", published_at_utc="2026-10-21T12:00:00Z",
                           captured_at_utc="2026-10-21T12:01:00Z")
        data["records"].append(record(
            "NZD", "CPI_YOY", published="2026-10-31T12:00:00Z",
            captured="2026-10-31T12:01:00Z", period="2026-Q2"))
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED")
        self.assertEqual(r["selected_observations"]["NZD"]["CPI_YOY"]["observation_period"],
                         "2026-Q3")
        self.assert_no_go(r)

    def test_mixed_monthly_quarterly_for_same_currency_cpi_fails_closed(self):
        data = sample("GBP/NZD")
        data["records"].append(record(
            "NZD", "CPI_YOY", published="2026-10-31T12:00:00Z",
            captured="2026-10-31T12:01:00Z", period="2026-Q3"))
        r = run(data)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["reason"], "MIXED_INDICATOR_OBSERVATION_FREQUENCIES")
        self.assert_no_go(r)

    def test_duplicate_same_indicator_period_revision_is_blocked(self):
        data = sample()
        data["records"].append(dict(data["records"][0], value="2.3"))
        r = run(data)
        self.assertEqual(r["reason"], "DUPLICATE_INDICATOR_PERIOD_REVISION_AMBIGUOUS")
        self.assert_no_go(r)

    def test_other_currency_cannot_be_sneaked_into_pair(self):
        data = sample()
        data["records"].append(record("GBP", "CPI_YOY"))
        self.assertEqual(run(data)["state"], "LAB_BLOCKED")

    def test_future_observation_period_not_allowed(self):
        data = sample()
        data["records"][0]["observation_period"] = "2026-12"
        self.assertEqual(run(data)["state"], "LAB_BLOCKED")

    def test_unknown_indicator_source_and_hash_rejected(self):
        for column, bad in (("indicator", "PREDICTION"),
                            ("source_type", "RUMOR"),
                            ("source_sha256", "fake"),
                            ("observation_period", "Sep-2026")):
            data = sample()
            data["records"][0][column] = bad
            self.assertEqual(run(data)["state"], "LAB_BLOCKED", column)

    def test_cpi_and_policy_original_issuer_categories_cannot_be_swapped(self):
        for indicator, wrong_type in (("CPI_YOY", "CENTRAL_BANK"),
                                      ("POLICY_RATE", "OFFICIAL_STATISTICS_OFFICE")):
            for pair in OFFICIAL_PAIRS:
                with self.subTest(pair=pair, indicator=indicator):
                    data = sample(pair)
                    row = next(x for x in data["records"] if x["indicator"] == indicator)
                    row["source_type"] = wrong_type
                    r = run(data)
                    self.assertEqual(r["state"], "LAB_BLOCKED")
                    self.assertEqual(r["reason"],
                                     "INDICATOR_ORIGINAL_ISSUER_CATEGORY_MISMATCH")
                    self.assert_no_go(r)

    def test_numeric_economic_value_is_never_sent_to_bias_engine(self):
        for bad in ("NaN", "Infinity", "1e9", 2.0, True, "1,4", "-100", "999", None):
            data = sample()
            data["records"][0]["value"] = bad
            self.assertEqual(run(data)["state"], "LAB_BLOCKED", str(bad))

    def test_negative_inflation_is_valid_but_not_a_short_signal(self):
        data = sample()
        data["records"][0]["value"] = "-0.3"
        r = run(data)
        self.assertEqual(r["state"], "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED")
        self.assert_no_go(r)

    def test_unsupported_pair_rejected(self):
        for pair in ("EUR/EUR", "XAU/USD", "EURUSD", "USD/EUR", ""):
            data = sample()
            data["pair"] = pair
            self.assertEqual(run(data)["state"], "LAB_BLOCKED", pair)

    def test_wrong_clock_type_or_future_decision_rejected(self):
        for as_of in (datetime(2026, 11, 6), None, "2026-11-06"):
            self.assertEqual(run(as_of=as_of)["state"], "LAB_BLOCKED")
        data = sample()
        data["decision_at_utc"] = "2026-11-07T12:00:00Z"
        self.assertEqual(run(data)["state"], "LAB_BLOCKED")

    def test_timestamp_offset_not_silently_normalized(self):
        data = sample()
        data["records"][0]["published_at_utc"] = "2026-10-29T08:00:00-04:00"
        self.assertEqual(run(data)["state"], "LAB_BLOCKED")

    def test_duplicate_json_keys_and_unknown_fields_rejected(self):
        duplicate = raw(sample())[:-1] + b',"pair":"EUR/USD"}'
        self.assertEqual(run(duplicate)["state"], "LAB_BLOCKED")
        data = sample()
        data["confidence"] = "95%"
        self.assertEqual(run(data)["state"], "LAB_BLOCKED")

    def test_malformed_bytes_or_list_object_rejected(self):
        for bad in (b"", b"not json", b"\xff", b"[]", b"null", b"a" * 48001):
            self.assertEqual(run(bad)["state"], "LAB_BLOCKED")

    def test_all_data_still_caller_asserted_even_if_complete(self):
        r = run()
        self.assertEqual(r["timestamp_source"], "CALLER_ASSERTED_NOT_INDEPENDENT")
        self.assertFalse(r["independent_release_time_attested"])
        self.assertFalse(r["source_origin_authenticated"])
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
