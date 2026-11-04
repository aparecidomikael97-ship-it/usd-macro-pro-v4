"""Guards the priority D1/W1/MN1 FX bias against partial-calendar promotion."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_bias_calendar_exposure_link_lab import (
    SCHEMA, build_bias_calendar_exposure_link_lab,
)
from atlasquant_trader_bias_priority_bridge_lab import build_bias_priority_bridge_lab
from atlasquant_trader_macro_event_exposure_lab import build_macro_event_exposure_lab
from atlasquant_trader_macro_event_exposure_v2_lab import build_macro_event_exposure_v2_lab
from test_atlasquant_trader_bias_priority_bridge_lab import AT, books


def reports(at: datetime = AT) -> tuple[dict, dict]:
    relative, macro = books()
    return (build_bias_priority_bridge_lab(relative, macro, evaluated_at=at),
            build_macro_event_exposure_lab(at=at))


def link(bias: dict, calendar: dict, at: datetime = AT) -> dict:
    return build_bias_calendar_exposure_link_lab(bias, calendar, at=at)


def row(report: dict, pair: str, horizon: str) -> dict:
    return next(x for x in report["rows"] if x["pair"] == pair)["horizons"][horizon]


class BiasCalendarExposureLabTests(unittest.TestCase):
    def test_second_vintage_links_10_events_without_rewriting_first(self) -> None:
        b, old = reports()
        new = build_macro_event_exposure_v2_lab(at=AT)
        report = link(b, new)
        self.assertEqual(report["state"], "LAB_EXPLANATION_ONLY")
        self.assertEqual(report["curated_event_count"], 10)
        self.assertEqual(report["calendar_version"], "V2_OFFICIAL_PAGE_REVIEW")
        self.assertIn("STATCAN_CA_LFS_20261106",
                      [x["event_id"] for x in row(report, "USD/CAD", "W1")
                       ["event_exposures"]])
        self.assertIn("ABS_AU_LABOR_20261119",
                      [x["event_id"] for x in row(report, "EUR/AUD", "MN1")
                       ["event_exposures"]])
        self.assertEqual(link(b, old)["curated_event_count"], 3)
        self.assertEqual(report["rows"][0]["horizons"]["D1"]["operational_bias"],
                         "AGUARDAR")

    def test_v2_modified_event_or_forged_authority_fails_closed(self) -> None:
        b, _ = reports()
        for kind in ("reschedule", "remove_event", "claim_attested"):
            with self.subTest(kind=kind):
                c = build_macro_event_exposure_v2_lab(at=AT)
                if kind == "reschedule":
                    c["events"][7]["earliest_at_utc"] = "2026-11-10T20:00:00Z"
                elif kind == "remove_event":
                    c["events"].pop(7)
                else:
                    c["independent_source_receipt_verified"] = True
                self.assertEqual(link(b, c)["state"], "LAB_BLOCKED")

    def test_all_28_pairs_3_horizons_are_wait_only_and_partial(self) -> None:
        b, c = reports()
        pristine = deepcopy((b, c))
        out = link(b, c)
        self.assertEqual((b, c), pristine)
        self.assertEqual((out["schema"], out["state"]),
                         (SCHEMA, "LAB_EXPLANATION_ONLY"))
        self.assertEqual(out["pair_count"], 28)
        self.assertEqual({p["pair"] for p in out["rows"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(out["curated_event_count"], 3)
        self.assertEqual(out["bias_horizons"], ["D1", "W1", "MN1"])
        self.assertEqual(out["event_exposure_windows_seconds"],
                         {"D1": 86400, "W1": 604800, "MN1": 2592000})
        self.assertEqual(out["relative_currency_rankings"]["D1"]["strongest"], "USD")
        self.assertEqual(out["relative_currency_rankings"]["MN1"]["weakest"], "JPY")
        for p in out["rows"]:
            self.assertFalse(p["trade_authorized"])
            self.assertEqual(set(p["horizons"]), {"D1", "W1", "MN1"})
            for horizon in ("D1", "W1", "MN1"):
                r = p["horizons"][horizon]
                self.assertEqual(r["operational_bias"], "AGUARDAR")
                self.assertTrue(r["event_exposure_is_not_direction"])
                self.assertTrue(r["no_event_from_partial_calendar_is_not_no_risk"])
                self.assertTrue(r["windows_are_rolling_not_price_candles"])
        for prohibited in ("calendar_complete", "real_sources_attested",
                           "live_prices_verified", "source_original_bytes_archived",
                           "real_direction_inferred", "no_event_means_no_risk",
                           "can_feed_live_radar", "trade_authorized",
                           "worker_enabled", "scheduler_enabled", "publishable"):
            self.assertFalse(out[prohibited], prohibited)
        self.assertIsNone(out["probability_calibrated"])

    def test_gbp_boe_exposure_and_usd_nfp_cpi_are_horizon_specific(self) -> None:
        out = link(*reports())
        gbp_d1 = row(out, "GBP/JPY", "D1")
        self.assertEqual([x["event_id"] for x in gbp_d1["event_exposures"]],
                         ["BOE_MPC_20261105"])
        self.assertEqual(gbp_d1["event_exposures"][0]["timing_state"],
                         "WINDOW_EDGE_TIME_UNCERTAIN")
        gbp_w1 = row(out, "GBP/JPY", "W1")
        self.assertEqual([x["event_id"] for x in gbp_w1["event_exposures"]],
                         ["BOE_MPC_20261105"])
        self.assertEqual(gbp_w1["event_exposures"][0]["timing_state"],
                         "SCHEDULED_WITHIN_WINDOW")
        usd_w1 = row(out, "USD/JPY", "W1")
        self.assertEqual([x["event_id"] for x in usd_w1["event_exposures"]],
                         ["BLS_US_EMPLOYMENT_20261106", "BLS_US_CPI_20261110"])
        usd_d1 = row(out, "USD/JPY", "D1")
        self.assertEqual(usd_d1["event_exposures"], [])
        gbpusd_w1 = row(out, "GBP/USD", "W1")
        self.assertEqual(len(gbpusd_w1["event_exposures"]), 3)

    def test_no_curated_event_does_not_mean_no_market_risk(self) -> None:
        out = link(*reports())
        for horizon in ("D1", "W1", "MN1"):
            r = row(out, "EUR/JPY", horizon)
            self.assertEqual(r["event_risk_status"],
                             "NO_EVENT_FROM_THIS_PARTIAL_CALENDAR")
            self.assertEqual(r["event_exposures"], [])
            self.assertTrue(r["no_event_from_partial_calendar_is_not_no_risk"])

    def test_date_only_uncertainty_is_preserved(self) -> None:
        at = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
        b, c = reports(at)
        # Synthetic comparison input has a frozen earlier issuance time; the
        # safe join must refuse pretending it was refreshed at this later time.
        self.assertEqual(link(b, c, at)["reason"],
                         "BIAS_TIMESTAMP_NOT_FROZEN_AT_EVALUATION")
        documentary = build_macro_event_exposure_lab(at=at)
        gbp = next(x for x in documentary["fx_rows"]
                   if x["pair"] == "GBP/USD" and x["horizon"] == "D1")
        boe = next(x for x in gbp["event_exposures"]
                   if x["event_id"] == "BOE_MPC_20261105")
        self.assertEqual(boe["timing_state"],
                         "DATE_ONLY_MAY_ALREADY_HAVE_OCCURRED")

    def test_calendar_injection_or_omission_fails_closed(self) -> None:
        for action in ("remove_fx_row", "remove_event", "invent_actual",
                       "reschedule", "mark_complete", "claim_live"):
            with self.subTest(action=action):
                b, c = reports()
                if action == "remove_fx_row":
                    c["fx_rows"].pop()
                elif action == "remove_event":
                    c["events"].pop()
                elif action == "invent_actual":
                    c["actual_releases_verified"] = True
                elif action == "reschedule":
                    c["events"][0]["earliest_at_utc"] = "2026-11-05T13:00:00Z"
                elif action == "mark_complete":
                    c["calendar_complete"] = True
                else:
                    c["can_feed_live_radar"] = True
                out = link(b, c)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertFalse(out["trade_authorized"])

    def test_bias_spoofing_and_duplicate_pair_fail_closed(self) -> None:
        for action in ("live_bias", "fake_comparison", "shift_base",
                       "duplicate_pair", "missing_horizon", "future_clock",
                       "forged_rank", "removed_evidence", "fake_90"):
            with self.subTest(action=action):
                b, c = reports()
                if action == "live_bias":
                    b["rows"][0]["horizons"]["D1"]["operational_bias"] = "ALTA"
                elif action == "fake_comparison":
                    b["rows"][0]["horizons"]["D1"]["comparison"] = "CONFLITO_ENTRE_HIPOTESES"
                elif action == "shift_base":
                    b["rows"][0]["base"] = "USD" if b["rows"][0]["base"] != "USD" else "JPY"
                elif action == "duplicate_pair":
                    b["rows"][1]["pair"] = b["rows"][0]["pair"]
                elif action == "missing_horizon":
                    b["rows"][0]["horizons"].pop("W1")
                elif action == "future_clock":
                    b["issued_at_utc"] = (AT + timedelta(minutes=1)).isoformat()
                elif action == "forged_rank":
                    b["relative_currency_rankings"]["D1"]["strongest"] = ["BUY"]
                elif action == "removed_evidence":
                    b["rows"][0]["horizons"]["D1"]["evidence_ready"] = {}
                else:
                    b["accuracy_90_proven"] = True
                out = link(b, c)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(out["rows"], [])

    def test_bad_inputs_never_throw_or_promote(self) -> None:
        b, c = reports()
        for argument in (None, "LIVE", [], {}):
            with self.subTest(argument=argument):
                self.assertEqual(link(argument, c)["state"], "LAB_BLOCKED")
                self.assertEqual(link(b, argument)["state"], "LAB_BLOCKED")
        b, c = reports()
        b["rows"][0]["horizons"]["D1"]["comparison"] = []
        self.assertEqual(link(b, c)["state"], "LAB_BLOCKED")

    def test_naive_clock_and_pre_research_date_are_refused(self) -> None:
        b, c = reports()
        with self.assertRaises(ValueError):
            link(b, c, AT.replace(tzinfo=None))
        at = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
        out = link(b, c, at)
        self.assertEqual(out["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
