"""Contract tests: joint G8 official releases + pre-event exposure, no signals."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_macro_event_exposure_lab import HORIZONS, INDICES
from atlasquant_trader_macro_joint_dossier_lab import (
    SCHEMA, MISSING, build_macro_joint_dossier_lab,
)

SURVEY_PATH = (
    Path(__file__).resolve().parent / "docs" / "continuidade"
    / "TRADER_POLICY_SURVEY_DOCUMENTARY_CASE_20261103.json"
)
AT = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def build(at=AT, book=None):
    return build_macro_joint_dossier_lab(at=at, policy_survey_book=book)


def survey():
    return json.loads(SURVEY_PATH.read_text(encoding="utf-8"))


def fx(pair, horizon="W1", at=AT):
    return next(x for x in build(at)["fx_by_horizon"]
                if x["pair"] == pair and x["horizon"] == horizon)


def ix(name, horizon="W1", at=AT):
    return next(x for x in build(at)["indices_by_horizon"]
                if x["instrument"] == name and x["horizon"] == horizon)


class MacroJointDossierTests(unittest.TestCase):
    def test_full_macro_joint_schema(self):
        b = build()
        self.assertEqual(b["schema"], SCHEMA)
        self.assertEqual(b["state"], "LAB_MACRO_JOINT_DOCUMENTARY_NO_DIRECTION")

    def test_complete_currencies_and_horizons(self):
        b = build()
        self.assertEqual(set(b["currency_readiness"]), set(CURRENCIES))
        self.assertEqual(b["horizons"], list(HORIZONS))
        self.assertEqual(b["currency_count"], 8)

    def test_complete_fx_rows_84(self):
        b = build()
        self.assertEqual(b["pair_horizon_count"], 84)
        self.assertEqual({x["pair"] for x in b["fx_by_horizon"]},
                         set(OFFICIAL_PAIRS))
        self.assertEqual({x["horizon"] for x in b["fx_by_horizon"]},
                         set(HORIZONS))
        self.assertEqual(len({(x["pair"], x["horizon"])
                              for x in b["fx_by_horizon"]}), 84)

    def test_complete_index_rows_15(self):
        b = build()
        self.assertEqual(b["index_horizon_count"], 15)
        self.assertEqual({x["instrument"] for x in b["indices_by_horizon"]},
                         set(INDICES))
        self.assertEqual(len({(x["instrument"], x["horizon"])
                              for x in b["indices_by_horizon"]}), 15)

    def test_usd_known_inflation_and_announced_policy_range(self):
        c = build()["currency_readiness"]["USD"]
        self.assertEqual(c["inflation"]["headline_yoy_pct"], "3.7")
        self.assertEqual(c["announced_policy"]["announced_low_pct"], "3.75")
        self.assertEqual(c["announced_policy"]["announced_high_pct"], "4.00")

    def test_gbp_known_cpi_and_policy(self):
        c = build()["currency_readiness"]["GBP"]
        self.assertEqual(c["inflation"]["headline_yoy_pct"], "3.5")
        self.assertEqual(c["announced_policy"]["announced_low_pct"], "3.75")

    def test_nzd_is_explicitly_quarterly(self):
        c = build()["currency_readiness"]["NZD"]
        self.assertEqual(c["inflation"]["periodicity"], "QUARTERLY")

    def test_euro_area_hicp_not_national_cpi(self):
        c = build()["currency_readiness"]["EUR"]
        self.assertIn("HICP", c["inflation"]["series_id"])

    def test_swiss_nov3_previous_cpi_vintage(self):
        self.assertEqual(build()["currency_readiness"]["CHF"]
                         ["inflation"]["headline_yoy_pct"], "1.0")

    def test_swiss_nov4_new_cpi_vintage(self):
        at = datetime(2026, 11, 4, 0, tzinfo=timezone.utc)
        self.assertEqual(build(at)["currency_readiness"]["CHF"]
                         ["inflation"]["headline_yoy_pct"], "1.5")

    def test_aud_nov3_new_policy_announced_not_effective(self):
        c = build()["currency_readiness"]["AUD"]
        self.assertEqual(c["announced_policy"]["announced_low_pct"], "4.85")
        self.assertEqual(c["announced_policy"]["availability_state"],
                         "NEW_RATE_ANNOUNCED_EFFECTIVE_NEXT_LOCAL_DATE")

    def test_aud_early_nov3_cannot_see_new_policy(self):
        at = datetime(2026, 11, 3, 3, 30, tzinfo=timezone.utc)
        c = build(at)["currency_readiness"]["AUD"]
        self.assertEqual(c["announced_policy"]["announced_low_pct"], "4.60")

    def test_aud_local_nov4_effective_date_reached(self):
        at = datetime(2026, 11, 3, 13, 15, tzinfo=timezone.utc)
        self.assertEqual(build(at)["currency_readiness"]["AUD"]
                         ["announced_policy"]["availability_state"],
                         "NEW_RATE_LOCAL_EFFECTIVE_DATE_REACHED")

    def test_eur_nov4_flash_requires_refresh(self):
        at = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
        self.assertEqual(build(at)["currency_readiness"]["EUR"]
                         ["inflation"]["freshness_state"],
                         "NEW_RELEASE_DAY_REVIEW_REQUIRED")

    def test_boe_nov5_prior_rate_requires_refresh(self):
        at = datetime(2026, 11, 5, 0, tzinfo=timezone.utc)
        self.assertEqual(build(at)["currency_readiness"]["GBP"]
                         ["announced_policy"]["availability_state"],
                         "KNOWN_NEW_DECISION_DATE_REQUIRES_REFRESH")

    def test_gbpusd_upcoming_boe_and_us_employment_w1(self):
        w = fx("GBP/USD", "W1")
        ids = {x["event_id"] for x in w["curated_upcoming_events"]}
        self.assertIn("BOE_MPC_20261105", ids)
        self.assertIn("BLS_US_EMPLOYMENT_20261106", ids)
        self.assertNotIn("BLS_US_CPI_20261110", ids)
        month = fx("GBP/USD", "MN1")
        self.assertIn("BLS_US_CPI_20261110",
                      {x["event_id"] for x in month["curated_upcoming_events"]})

    def test_gbpusd_no_boe_in_next_24_hours(self):
        d = fx("GBP/USD", "D1")
        self.assertEqual(d["curated_upcoming_events"], [])

    def test_jpychf_no_direct_us_catalysts(self):
        w = fx("CHF/JPY", "W1")
        self.assertEqual(w["curated_upcoming_events"], [])
        self.assertEqual(w["event_coverage_state"],
                         "NO_EVENT_FROM_THIS_PARTIAL_CALENDAR")

    def test_spx_us_catalysts_only(self):
        w = ix("SPX500")
        self.assertTrue(w["curated_upcoming_events"])
        self.assertTrue(all(e["currency"] == "USD"
                            for e in w["curated_upcoming_events"]))

    def test_wdo_brazil_domestic_context_not_replaced_by_usd(self):
        w = ix("WDO")
        self.assertEqual(w["local_market_context_state"],
                         "BRAZIL_DOMESTIC_MACRO_AND_POLICY_MISSING")
        self.assertTrue(all(e["exposure_channel"]
                            == "INDIRECT_US_CONTEXT_UNVERIFIED"
                            for e in w["curated_upcoming_events"]))

    def test_forecast_and_score_are_absent(self):
        for row in build()["fx_by_horizon"]:
            with self.subTest(row=row["pair"], h=row["horizon"]):
                self.assertEqual(row["directional_bias"], "AGUARDAR")
                self.assertIsNone(row["probability_calibrated"])
                self.assertIsNone(row["expected_policy_path_difference_pp"])
                self.assertIsNone(row["fx_strength"])
                self.assertFalse(row["trade_authorized"])

    def test_indices_are_not_fx_signals(self):
        for row in build()["indices_by_horizon"]:
            with self.subTest(symbol=row["instrument"]):
                self.assertEqual(row["directional_bias"], "AGUARDAR")
                self.assertIsNone(row["probability_calibrated"])
                self.assertFalse(row["trade_authorized"])

    def test_no_nominal_policy_gap_or_cpi_gap_as_signal(self):
        for row in build()["fx_by_horizon"]:
            self.assertIsNone(row["nominal_policy_gap_pp"])
            self.assertIsNone(row["inflation_difference_pp"])

    def test_no_promoted_governance(self):
        b = build()
        for key in (
            "calendar_partial", "market_forward_curve_verified",
            "economic_consensus_verified", "micro_geopolitics_verified",
            "independent_sources_attested", "relative_currency_strength_proven",
            "accuracy_90_proven", "real_walk_forward_oos_proven",
            "can_feed_live_radar", "trade_authorized", "worker_enabled",
            "scheduler_enabled",
        ):
            self.assertEqual(b[key], key == "calendar_partial")
        self.assertIn("INDEPENDENT_FX_PRICE_OOS_CALIBRATION_MISSING", MISSING)

    def test_not_pretend_policy_expectations_without_survey(self):
        b = build()
        for c in CURRENCIES:
            x = b["currency_readiness"][c]
            self.assertEqual(x["forward_policy_survey_state"], "NOT_PROVIDED")
            self.assertIsNone(x["market_priced_next_meeting_expectation_pct"])

    def test_canonical_survey_gbp_stale_eur_timetable_usd_missing(self):
        c = build(book=survey())["currency_readiness"]
        self.assertEqual(c["GBP"]["forward_policy_survey_state"],
                         "PRE_EVENT_BUT_STALE")
        self.assertEqual(c["EUR"]["forward_policy_survey_state"],
                         "TIMETABLE_ONLY_NOT_ATTESTED")
        self.assertEqual(c["USD"]["forward_policy_survey_state"],
                         "RESULT_NOT_PUBLICLY_OBSERVED")
        for code in ("JPY", "CHF", "CAD", "AUD", "NZD"):
            self.assertEqual(c[code]["forward_policy_survey_state"],
                             "NOT_DOCUMENTED_IN_PARTIAL_SURVEY_BOOK")

    def test_stale_survey_does_not_become_market_implied_forecast(self):
        c = build(book=survey())["currency_readiness"]["GBP"]
        self.assertFalse(c["independent_survey_receipt_verified"])
        self.assertIsNone(c["market_priced_next_meeting_expectation_pct"])
        self.assertIsNone(c["actual_policy_path_change_prediction"])

    def test_survey_altered_state_rejected(self):
        s = survey()
        s["records"][0]["publication_state"] = "MAGIC_PROVEN"
        with self.assertRaises(ValueError):
            build(book=s)

    def test_survey_duplicate_currency_ambiguous_rejected(self):
        s = survey()
        r = deepcopy(s["records"][0])
        r["record_id"] = "SECOND_GBP_SURVEY"
        s["records"].append(r)
        with self.assertRaises(ValueError):
            build(book=s)

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            build(datetime(2026, 11, 3, 12))

    def test_early_research_clock_rejected(self):
        with self.assertRaises(ValueError):
            build(datetime(2026, 11, 2, 23, 59, tzinfo=timezone.utc))

    def test_offset_clock_converts_to_utc(self):
        at = datetime(2026, 11, 3, 8, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(build(at)["as_of_utc"], AT.isoformat())

    def test_join_source_schemas_declared(self):
        s = build()["source_schemas"]
        self.assertIn("POLICY", s["policy"])
        self.assertIn("INFLATION", s["inflation"])
        self.assertIn("MACRO_EVENT_EXPOSURE", s["calendar"])

    def test_no_network_or_runtime_dependencies_added(self):
        import atlasquant_trader_macro_joint_dossier_lab as module
        self.assertFalse(hasattr(module, "requests"))
        self.assertFalse(hasattr(module, "subprocess"))
        self.assertFalse(hasattr(module, "run_worker"))
