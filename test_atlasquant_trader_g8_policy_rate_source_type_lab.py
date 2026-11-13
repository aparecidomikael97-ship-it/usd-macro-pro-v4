"""Synthetic only: eight issuer policy sources and instrument type protection."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_g8_policy_rate_source_type_lab import (
    OFFICIAL_POLICY_CANDIDATES, inspect_g8_policy_rate_candidates_lab as inspect,
)

UTC = timezone.utc
DECISION = datetime(2026, 11, 12, 22, tzinfo=UTC)
NOW = datetime(2026, 11, 12, 23, tzinfo=UTC)


def claimed_sources():
    """Fabricated values and dates: NOT observed bank statements or prices."""
    ret = []
    for currency in CURRENCIES:
        src = OFFICIAL_POLICY_CANDIDATES[currency]
        ret.append({
            "currency": currency,
            "issuer_name_claim": src["issuer"],
            "measure_claim": src["measure"],
            "measure_kind_claim": src["kind"],
            "source_url_claim": src["url"],
            "rate_lower_pct_claim": "3.00" if currency == "USD" else "1.50",
            "rate_upper_pct_claim": "3.25" if currency == "USD" else "1.50",
            "effective_date_claim": "2026-10-30",
            "issuer_published_at_utc_claim": "2026-10-30T16:00:00Z",
            "locally_observed_at_utc_claim": "2026-11-12T17:00:00Z",
        })
    return ret


class G8PolicyRateSourceTypeTests(unittest.TestCase):
    def probe(self, records=None, *, decision=DECISION, now=NOW):
        return inspect(
            claimed_sources() if records is None else records,
            decision_at_utc=decision, inspected_at_utc=now)

    def safety(self, out):
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["live_alert_allowed"])
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["scheduler_enabled"])
        self.assertFalse(out["original_issuer_release_authenticated"])
        self.assertFalse(out["publisher_first_available_timestamp_verified"])
        self.assertFalse(out["point_in_time_policy_vintage_verified"])
        self.assertFalse(out["raw_issuer_response_bytes_present"])
        self.assertFalse(out["http_response_headers_or_tls_authenticated"])
        self.assertFalse(out["official_rates_verified"])
        self.assertFalse(out["policy_rate_measures_economically_comparable"])
        self.assertFalse(out["fx28_bilateral_macro_fully_authenticated"])
        self.assertFalse(out["forecast_publication_witnessed"])
        self.assertFalse(out["fed_range_compressed_to_midpoint"])
        self.assertIsNone(out["calibrated_directional_probability"])
        self.assertIsNone(out["relative_currency_strength_score"])
        self.assertEqual(out["external_calls"], 0)
        self.assertEqual(out["files_written"], 0)
        self.assertEqual(out["new_cost_brl"], 0)

    def test_complete_8_claims_keep_fed_range_separate_from_point_rates(self):
        r = self.probe()
        self.safety(r)
        self.assertEqual(r["currencies_expected"], 8)
        self.assertEqual(r["source_candidates_supplied"], 8)
        self.assertEqual(r["source_url_and_instrument_claim_matches"], 8)
        self.assertEqual(r["rate_ranges_preserved"], 1)
        self.assertEqual(r["point_rate_values_structurally_plausible"], 7)
        self.assertEqual(r["source_candidates_missing"], [])
        self.assertTrue(r["all_8_source_type_claims_locally_consistent"])
        self.assertEqual(
            r["state"], "LAB_G8_POLICY_RATE_8_CANDIDATE_TYPES_LOCAL_ONLY_NO_GO")

    def test_7_of_8_candidates_are_not_28_pair_macro_readiness(self):
        rows = claimed_sources()[:-1]
        r = self.probe(rows)
        self.safety(r)
        self.assertEqual(r["source_candidates_supplied"], 7)
        self.assertEqual(r["source_candidates_missing"], [claimed_sources()[-1]["currency"]])
        self.assertFalse(r["all_8_source_type_claims_locally_consistent"])
        self.assertEqual(r["state"], "LAB_G8_POLICY_RATE_PARTIAL_CANDIDATE_TYPES_NO_GO")

    def test_empty_list_does_not_fabricate_bank_sources(self):
        r = self.probe([])
        self.safety(r)
        self.assertEqual(r["source_candidates_supplied"], 0)
        self.assertEqual(r["source_candidates_missing"], sorted(CURRENCIES))
        self.assertEqual(r["rate_ranges_preserved"], 0)

    def test_issuer_or_instrument_swapped_rejected(self):
        for field, value in (
            ("issuer_name_claim", "Federal Reserve"),
            ("measure_claim", "ECB_MAIN_REFINANCING_RATE"),
            ("measure_kind_claim", "RANGE"),
            ("source_url_claim", "https://www.federalreserve.gov/FOMC/fundsrate.htm"),
        ):
            with self.subTest(field=field):
                rows = claimed_sources()
                eur = next(r for r in rows if r["currency"] == "EUR")
                eur[field] = value
                got = self.probe(rows)
                self.safety(got)
                self.assertEqual(got["reason"],
                                 "POLICY_SOURCE_OR_METRIC_NOT_OFFICIAL_CANDIDATE")

    def test_fake_central_bank_subdomain_url_userinfo_and_redirect_queries_rejected(self):
        base = OFFICIAL_POLICY_CANDIDATES["USD"]["url"]
        for url in (
            base.replace("www.federalreserve.gov", "www.federalreserve.gov.evil.test"),
            base.replace("https://", "http://"),
            base + "?redirect=https://evil.test",
            base + "#new-target",
            "https://www.federalreserve.gov@evil.test/FOMC/fundsrate.htm",
            base.rstrip("/").replace("fundsrate.htm", "openmarket.htm"),
        ):
            with self.subTest(url=url):
                rows = claimed_sources()
                next(row for row in rows if row["currency"] == "USD")[
                    "source_url_claim"] = url
                got = self.probe(rows)
                self.safety(got)
                self.assertEqual(got["reason"],
                                 "POLICY_SOURCE_OR_METRIC_NOT_OFFICIAL_CANDIDATE")

    def test_fed_single_3_25_point_cannot_be_mislabeled_as_target_range(self):
        rows = claimed_sources()
        usd = next(row for row in rows if row["currency"] == "USD")
        usd["rate_lower_pct_claim"] = usd["rate_upper_pct_claim"]
        r = self.probe(rows)
        self.safety(r)
        self.assertEqual(r["reason"], "FED_RANGE_MUST_HAVE_DISTINCT_BOUNDS")

    def test_other_banks_cannot_use_unharmonized_fed_rate_range(self):
        for currency in ("EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF"):
            with self.subTest(currency=currency):
                rows = claimed_sources()
                row = next(row for row in rows if row["currency"] == currency)
                row["rate_upper_pct_claim"] = "1.75"
                got = self.probe(rows)
                self.safety(got)
                self.assertEqual(got["reason"],
                                 "POINT_RATE_CANNOT_BE_FED_RANGE_OR_SPREAD")

    def test_same_day_date_only_effective_rate_must_not_be_lookahead(self):
        rows = claimed_sources()
        rows[0]["effective_date_claim"] = "2026-11-12"
        r = self.probe(rows)
        self.safety(r)
        self.assertEqual(r["reason"],
                         "RATE_VALUE_CLAIM_OR_POINT_IN_TIME_CHRONOLOGY_INVALID")

    def test_new_future_or_backdated_claim_cannot_pass_decision_cutoff(self):
        for field, value in (
            ("issuer_published_at_utc_claim", "2026-11-13T00:00:00Z"),
            ("locally_observed_at_utc_claim", "2026-11-12T23:00:00Z"),
            ("issuer_published_at_utc_claim", "2026-11-12T21:00:00Z"),
            ("effective_date_claim", "2026-11-13"),
        ):
            with self.subTest(field=field, value=value):
                rows = claimed_sources()
                rows[0][field] = value
                if field == "issuer_published_at_utc_claim" and value == "2026-11-12T21:00:00Z":
                    rows[0]["locally_observed_at_utc_claim"] = "2026-11-12T20:00:00Z"
                r = self.probe(rows)
                self.safety(r)
                self.assertEqual(r["reason"],
                                 "RATE_VALUE_CLAIM_OR_POINT_IN_TIME_CHRONOLOGY_INVALID")

    def test_fake_numeric_nan_inf_lookalikes_and_floats_rejected(self):
        for value in ("NaN", "Infinity", "-Inf", "1e3", "999.1234", -0.5, None):
            with self.subTest(value=value):
                rows = claimed_sources()
                rows[0]["rate_lower_pct_claim"] = value
                r = self.probe(rows)
                self.safety(r)
                self.assertEqual(r["reason"],
                                 "RATE_VALUE_CLAIM_OR_POINT_IN_TIME_CHRONOLOGY_INVALID")

    def test_duplicate_currency_or_extra_field_cannot_pass_whitelist(self):
        rows = claimed_sources()
        rows[-1]["currency"] = rows[0]["currency"]
        r = self.probe(rows)
        self.safety(r)
        self.assertEqual(r["reason"], "CURRENCY_MISSING_DUPLICATE_OR_NOT_G8")
        rows = claimed_sources()
        rows[0]["account_number"] = "unsafe"
        r = self.probe(rows)
        self.safety(r)
        self.assertEqual(r["reason"], "POLICY_RATE_CLAIM_SCHEMA_INVALID")

    def test_wrong_currency_universe_future_or_naive_clock_blocks(self):
        rows = claimed_sources()
        for decision, now in (
            (DECISION + timedelta(hours=2), NOW),
            (DECISION.replace(tzinfo=None), NOW),
            (DECISION, NOW.replace(tzinfo=None)),
        ):
            with self.subTest(decision=decision, now=now):
                r = self.probe(rows,decision=decision,now=now)
                self.safety(r)
                self.assertEqual(r["state"],
                                 "LAB_G8_POLICY_RATE_CANDIDATE_ADMISSION_BLOCKED")

    def test_policy_registry_pins_all_8_distinct_official_pages(self):
        self.assertEqual(set(OFFICIAL_POLICY_CANDIDATES), set(CURRENCIES))
        self.assertEqual(len({row["url"] for row in OFFICIAL_POLICY_CANDIDATES.values()}),8)
        self.assertEqual(sum(x["kind"]=="RANGE" for x in OFFICIAL_POLICY_CANDIDATES.values()),1)
        self.assertEqual(sum(x["kind"]=="POINT" for x in OFFICIAL_POLICY_CANDIDATES.values()),7)


if __name__ == "__main__":
    unittest.main()
