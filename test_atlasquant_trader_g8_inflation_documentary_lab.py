"""Documentary eight-currency inflation context, no FX signal."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_inflation_documentary_lab import (
    SCHEMA, VINTAGES, build_g8_inflation_documentary_lab,
)

AT = datetime(2026, 11, 3, 15, tzinfo=timezone.utc)


def build(at=AT, observations=None):
    return build_g8_inflation_documentary_lab(at=at, observations=observations)


def row(currency, at=AT):
    return build(at=at)["currency_inflation"][currency]


def pair(name, at=AT):
    return next(x for x in build(at=at)["pair_rows"] if x["pair"] == name)


class G8InflationDocumentaryTests(unittest.TestCase):
    def test_complete_eight_currency_coverage(self):
        r = build()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_G8_HISTORICAL_INFLATION_NO_DIRECTION")
        self.assertEqual(r["visible_currency_count"], 8)
        self.assertEqual(r["currency_count"], 8)
        self.assertEqual(set(r["currency_inflation"]), set(CURRENCIES))

    def test_nine_vintages_two_swiss_publications(self):
        self.assertEqual(len(VINTAGES), 9)
        self.assertEqual(sum(x["currency"] == "CHF" for x in VINTAGES), 2)

    def test_usd_september_cpi_nsa_37(self):
        self.assertEqual(row("USD")["yoy_pct"], "3.7")
        self.assertEqual(row("USD")["series_id"], "US_CPIU_ALL_ITEMS_NSA_YOY")

    def test_eur_final_hicp_38_not_october_flash(self):
        r = row("EUR")
        self.assertEqual(r["yoy_pct"], "3.8")
        self.assertEqual(r["reference_period"], "2026-09")
        self.assertEqual(r["series_id"], "EURO_AREA_HICP_ALL_ITEMS_YOY_FINAL")

    def test_gbp_cpi_35_not_cpih_36(self):
        r = row("GBP")
        self.assertEqual(r["yoy_pct"], "3.5")
        self.assertIn("not CPIH", r["measurement_note"])

    def test_japan_all_items_21_not_core_definition(self):
        r = row("JPY")
        self.assertEqual(r["yoy_pct"], "2.1")
        self.assertEqual(r["series_id"], "JAPAN_CPI_2025_BASE_ALL_ITEMS_YOY")

    def test_chf_nov3_does_not_receive_same_day_unknown_hour(self):
        r = row("CHF")
        self.assertEqual(r["yoy_pct"], "1.0")
        self.assertEqual(r["reference_period"], "2026-09")

    def test_chf_nov4_includes_official_october_publication(self):
        next_day = datetime(2026, 11, 4, 0, tzinfo=timezone.utc)
        r = row("CHF", next_day)
        self.assertEqual(r["yoy_pct"], "1.5")
        self.assertEqual(r["reference_period"], "2026-10")

    def test_chf_before_nov4_cutoff_cannot_see_15(self):
        cutoff_minus = datetime(2026, 11, 3, 23, 59, 59, tzinfo=timezone.utc)
        self.assertEqual(row("CHF", cutoff_minus)["yoy_pct"], "1.0")

    def test_eur_nov4_new_flash_day_requires_refresh(self):
        next_day = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
        r = row("EUR", next_day)
        self.assertEqual(r["freshness_state"], "NEW_RELEASE_DAY_REVIEW_REQUIRED")
        self.assertEqual(r["yoy_pct"], "3.8")

    def test_cad_31_yoy(self):
        self.assertEqual(row("CAD")["yoy_pct"], "3.1")

    def test_aud_43_monthly_cpi_series(self):
        r = row("AUD")
        self.assertEqual(r["yoy_pct"], "4.3")
        self.assertEqual(r["periodicity"], "MONTHLY")

    def test_nzd_37_quarterly_frequency(self):
        r = row("NZD")
        self.assertEqual(r["yoy_pct"], "3.7")
        self.assertEqual(r["periodicity"], "QUARTERLY")
        self.assertEqual(r["reference_period"], "2026-Q3")

    def test_other_currencies_are_monthly(self):
        for c in CURRENCIES:
            if c != "NZD":
                with self.subTest(currency=c):
                    self.assertEqual(row(c)["periodicity"], "MONTHLY")

    def test_all_source_publication_dates_before_nov3_except_chf_oct(self):
        new = [x for x in VINTAGES if x["published_on"] == "2026-11-03"]
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["currency"], "CHF")

    def test_28_canonical_pairs_covered(self):
        r = build()
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual({x["pair"] for x in r["pair_rows"]}, set(OFFICIAL_PAIRS))

    def test_gbpusd_two_sources_but_no_derived_inflation_gap(self):
        r = pair("GBP/USD")
        self.assertEqual((r["base_inflation_reference"], r["quote_inflation_reference"]),
                         ("GBP", "USD"))
        self.assertIsNone(r["numeric_inflation_gap_pp"])

    def test_nzd_cad_cannot_be_treated_as_equivalent_cadence(self):
        r = pair("NZD/CAD")
        self.assertIsNone(r["numeric_inflation_gap_pp"])
        self.assertIsNone(r["currency_strength_gap"])

    def test_no_directions_or_probabilities_in_pair_rows(self):
        for r in build()["pair_rows"]:
            with self.subTest(pair=r["pair"]):
                self.assertEqual(r["bias"], "AGUARDAR")
                self.assertIsNone(r["probability_calibrated"])
                self.assertFalse(r["trade_authorized"])

    def test_research_before_nov3_blocked(self):
        with self.assertRaises(ValueError):
            build(at=datetime(2026, 11, 2, 23, 59, tzinfo=timezone.utc))

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            build(at=datetime(2026, 11, 3, 15))

    def test_wrong_clock_type_rejected(self):
        with self.assertRaises(ValueError):
            build(at="2026-11-03T15:00:00Z")

    def test_timezone_offset_normalized(self):
        offset = timezone(timedelta(hours=-4))
        r = build(at=datetime(2026, 11, 3, 11, tzinfo=offset))
        self.assertEqual(r["as_of_utc"], AT.isoformat())

    def test_valid_exact_copy_accepted(self):
        self.assertEqual(build(observations=deepcopy(list(VINTAGES))), build())

    def test_missing_vintage_rejected(self):
        with self.assertRaises(ValueError):
            build(observations=list(VINTAGES)[:-1])

    def test_duplicate_vintage_rejected(self):
        fake = deepcopy(list(VINTAGES))
        fake[5] = fake[4]
        with self.assertRaises(ValueError):
            build(observations=fake)

    def test_fake_early_chf_october_availability_rejected(self):
        fake = deepcopy(list(VINTAGES))
        fake[5]["conservative_available_from_utc"] = "2026-11-03T00:00:00Z"
        with self.assertRaises(ValueError):
            build(observations=fake)

    def test_wrong_swiss_october_value_rejected(self):
        fake = deepcopy(list(VINTAGES))
        fake[5]["yoy_pct"] = "9.9"
        with self.assertRaises(ValueError):
            build(observations=fake)

    def test_fake_official_host_rejected(self):
        fake = deepcopy(list(VINTAGES))
        fake[0]["source_url"] = "https://www.bls.gov.attack.test/cpi"
        with self.assertRaises(ValueError):
            build(observations=fake)

    def test_uk_cpih_masquerade_rejected(self):
        fake = deepcopy(list(VINTAGES))
        fake[2]["yoy_pct"] = "3.6"
        with self.assertRaises(ValueError):
            build(observations=fake)

    def test_new_zealand_monthly_forgery_rejected(self):
        fake = deepcopy(list(VINTAGES))
        fake[8]["periodicity"] = "MONTHLY"
        with self.assertRaises(ValueError):
            build(observations=fake)

    def test_added_probability_field_rejected(self):
        fake = deepcopy(list(VINTAGES))
        fake[3]["confidence_90"] = True
        with self.assertRaises(ValueError):
            build(observations=fake)

    def test_wrong_document_shapes_rejected(self):
        with self.assertRaises(ValueError):
            build(observations="documents")
        with self.assertRaises(ValueError):
            build(observations=[None] * 9)

    def test_no_independent_receipts_or_live_data_claims(self):
        r = build()
        for flag in ("same_cpi_methodology_verified",
                     "calendar_real_time_refreshed",
                     "source_original_bytes_archived",
                     "independent_receipt_verified",
                     "consensus_pre_event_verified",
                     "forward_policy_path_verified",
                     "relative_fx_inflation_edge_proven",
                     "real_oos_accuracy_proven", "accuracy_90_proven",
                     "can_feed_live_radar", "trade_authorized",
                     "worker_enabled", "scheduler_enabled"):
            with self.subTest(flag=flag):
                self.assertIs(r[flag], False)

    def test_every_currency_snapshot_marks_no_source_attestation(self):
        for item in build()["currency_inflation"].values():
            self.assertFalse(item["original_source_bytes_attested"])
            self.assertFalse(item["economic_surprise_verified"])


if __name__ == "__main__":
    unittest.main()
