"""Synthetic B3 WIN/WDO sessions around Copom; no genuine futures tape."""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_trader_copom_b3_session_reaction_lab import (
    PENDING, SYNTHETIC, DENIED, SCHEDULE, PRE_EVENT_BLOB,
    build_copom_b3_session_reaction_lab as build,
)

ROOT = Path(__file__).resolve().parent
FROZEN = ROOT / "docs/continuidade/TRADER_COPOM_20261104_FROZEN_PRE_EVENT_20261103.json"
PRE_EVENT = datetime(2026, 11, 3, 18, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 5, 13, tzinfo=timezone.utc)


def raw():
    return FROZEN.read_bytes()


def fixture(instrument="WIN"):
    pre = ("2026-11-04T21:24:00Z" if instrument == "WIN"
           else "2026-11-04T21:29:00Z")
    return {
        "instrument": instrument,
        "contract_symbol": "SIM_" + instrument,
        "fixture_mode": "SYNTHETIC_TEST_ONLY",
        "pre_price_points": "160000" if instrument == "WIN" else "5500",
        "post_price_points": "162000" if instrument == "WIN" else "5540",
        "pre_trade_at_utc": pre,
        "post_trade_at_utc": "2026-11-05T12:03:00Z",
        "original_b3_quotes_verified": False,
        "market_data_use_rights_verified": False,
    }


def run(samples=None, *, at=PRE_EVENT, frozen=None):
    return build(raw() if frozen is None else frozen,
                 evaluated_at=at, synthetic_observations=samples)


class B3SessionReactionLabTests(unittest.TestCase):
    def test_pre_event_plan_is_pending_no_future_prices(self):
        r = run()
        self.assertEqual(r["state"], PENDING)
        self.assertTrue(r["pre_event_original_bytes_matched"])
        self.assertEqual(r["price_rows"], [])
        self.assertFalse(r["real_market_reaction_measured"])

    def test_frozen_original_pre_copom_blob_is_exactly_pinned(self):
        self.assertEqual(len(PRE_EVENT_BLOB), 40)
        self.assertEqual(run()["pre_event_blob"], PRE_EVENT_BLOB)
        altered = json.loads(raw())
        altered["reuters_poll_hold_responses"] = 48
        changed = (json.dumps(altered, indent=2) + "\n").encode()
        self.assertEqual(run(frozen=changed)["state"], DENIED)

    def test_reformatting_old_json_does_not_rewrite_pre_event_history(self):
        content = json.loads(raw())
        other_bytes = json.dumps(content, sort_keys=True, indent=4).encode()
        self.assertEqual(run(frozen=other_bytes)["state"], DENIED)

    def test_win_closes_five_minutes_before_earliest_bcb_release(self):
        r = run()
        win = next(x for x in r["schedule_rows"] if x["instrument"] == "WIN")
        self.assertEqual(win["normal_regular_session_end_brt"], "18:25")
        self.assertEqual(win["pre_event_session_close_utc"], "2026-11-04T21:25:00+00:00")
        self.assertTrue(r["announcement_after_win_close"])

    def test_wdo_closes_exactly_at_earliest_bcb_release(self):
        r = run()
        wdo = next(x for x in r["schedule_rows"] if x["instrument"] == "WDO")
        self.assertEqual(wdo["normal_regular_session_end_brt"], "18:30")
        self.assertEqual(wdo["pre_event_session_close_utc"], "2026-11-04T21:30:00+00:00")
        self.assertTrue(r["announcement_at_or_after_wdo_close"])

    def test_next_open_is_only_unverified_candidate(self):
        r = run()
        self.assertEqual(r["reaction_session_date_candidate"], "2026-11-05")
        self.assertEqual(r["first_regular_next_session_open_candidate_utc"],
                         "2026-11-05T12:00:00+00:00")
        self.assertFalse(r["b3_holiday_and_exception_calendar_verified"])
        self.assertFalse(r["next_business_session_guaranteed"])

    def test_b3_official_circular_and_explicit_contract_types(self):
        r = run()
        self.assertIn("050-2026", r["b3_schedule_source_url"])
        self.assertEqual({x["b3_ticker"] for x in r["schedule_rows"]}, {"FUT WIN", "FUT WDO"})

    def test_two_synthetic_next_session_gap_examples(self):
        r = run([fixture("WIN"), fixture("WDO")], at=AFTER)
        self.assertEqual(r["state"], SYNTHETIC)
        self.assertEqual(r["synthetic_observations_count"], 2)
        d = {x["instrument"]: x for x in r["price_rows"]}
        self.assertEqual(d["WIN"]["synthetic_percent_change"], "1.2500")
        self.assertEqual(d["WDO"]["synthetic_percent_change"], "0.7273")
        self.assertTrue(all(x["synthetic_price_direction"] == "ALTA" for x in d.values()))
        self.assertTrue(all(not x["is_real_market_price"] for x in d.values()))

    def test_synthetic_fall_and_unchanged_are_arithmetic_only(self):
        w = fixture("WIN")
        w["post_price_points"] = "158000"
        r = run([w], at=AFTER)
        self.assertEqual(r["state"], SYNTHETIC)
        self.assertEqual(r["price_rows"][0]["synthetic_price_direction"], "BAIXA")
        w["post_price_points"] = w["pre_price_points"]
        r = run([w], at=AFTER)
        self.assertEqual(r["price_rows"][0]["synthetic_price_direction"], "NEUTRO")

    def test_synthetic_observation_before_next_session_is_refused(self):
        self.assertEqual(
            run([fixture("WIN")], at=datetime(2026,11,5,11,59,tzinfo=timezone.utc))["state"],
            DENIED)

    def test_pre_event_price_cannot_be_taken_after_win_close(self):
        x=fixture("WIN");x["pre_trade_at_utc"]="2026-11-04T21:27:00Z"
        self.assertEqual(run([x],at=AFTER)["state"], DENIED)

    def test_pre_event_price_cannot_be_taken_at_wdo_close(self):
        x=fixture("WDO");x["pre_trade_at_utc"]="2026-11-04T21:30:00Z"
        self.assertEqual(run([x],at=AFTER)["state"], DENIED)

    def test_pre_price_cannot_be_taken_before_session_open(self):
        x=fixture("WIN");x["pre_trade_at_utc"]="2026-11-04T11:59:00Z"
        self.assertEqual(run([x],at=AFTER)["state"], DENIED)

    def test_post_observation_not_allowed_before_candidate_next_open(self):
        x=fixture("WIN");x["post_trade_at_utc"]="2026-11-05T11:59:59Z"
        self.assertEqual(run([x],at=AFTER)["state"], DENIED)

    def test_post_observation_not_allowed_at_or_after_regular_close(self):
        x=fixture("WDO");x["post_trade_at_utc"]="2026-11-05T21:30:00Z"
        self.assertEqual(run([x],at=datetime(2026,11,5,22,tzinfo=timezone.utc))["state"], DENIED)

    def test_post_observation_in_future_relative_to_evaluation_denied(self):
        x=fixture("WDO");x["post_trade_at_utc"]="2026-11-05T12:15:00Z"
        self.assertEqual(run([x],at=datetime(2026,11,5,12,10,tzinfo=timezone.utc))["state"], DENIED)

    def test_no_real_source_can_be_sneaked_in_as_fixture(self):
        for field,value in (("fixture_mode","REAL_B3"),("original_b3_quotes_verified",True),
                            ("market_data_use_rights_verified",True)):
            x=fixture("WIN");x[field]=value
            self.assertEqual(run([x],at=AFTER)["state"], DENIED)

    def test_only_identical_fake_contract_identifier_admitted(self):
        for value in ("WINZ26","WDOX26","SIM_WDO","",None):
            x=fixture("WIN");x["contract_symbol"]=value
            self.assertEqual(run([x],at=AFTER)["state"], DENIED)

    def test_invalid_instrument_type_is_refused_not_crashed(self):
        for value in ([],{},None,True,123):
            x=fixture("WIN");x["instrument"]=value
            self.assertEqual(run([x],at=AFTER)["state"], DENIED)

    def test_no_duplicate_instrument_or_extra_fields(self):
        self.assertEqual(run([fixture("WIN"),fixture("WIN")],at=AFTER)["state"], DENIED)
        x=fixture("WDO");x["live_quote"]=True
        self.assertEqual(run([x],at=AFTER)["state"], DENIED)

    def test_prices_must_be_finite_positive_decimal_strings(self):
        for value in ("0","-1","NaN","Infinity","1,25","1e6","=160000",0,True,None):
            with self.subTest(value=value):
                x=fixture("WIN");x["pre_price_points"]=value
                self.assertEqual(run([x],at=AFTER)["state"], DENIED)

    def test_no_out_of_range_price_or_noncanonical_utc(self):
        for value in ("99999999999","0.00001"):
            x=fixture("WIN");x["post_price_points"]=value
            self.assertEqual(run([x],at=AFTER)["state"], DENIED)
        for value in ("2026-11-05T09:03:00-03:00","2026-11-05T12:03:00",None):
            x=fixture("WIN");x["post_trade_at_utc"]=value
            self.assertEqual(run([x],at=AFTER)["state"], DENIED)

    def test_empty_oversized_or_malformed_synthetic_collection_refused(self):
        for samples in ([],[fixture("WIN")]*3,{},[{}],"synthetic"):
            self.assertEqual(run(samples,at=AFTER)["state"], DENIED)

    def test_cannot_backdate_schedule_research_before_nov3(self):
        r=run(at=datetime(2026,11,2,23,tzinfo=timezone.utc))
        self.assertEqual(r["state"],DENIED)

    def test_naive_evaluation_instant_refused(self):
        with self.assertRaises(ValueError):
            run(at=datetime(2026,11,3,18))

    def test_no_real_market_reaction_or_proven_prediction_even_with_fixture(self):
        for r in (run(),run([fixture("WIN")],at=AFTER)):
            self.assertEqual(r["fx_win_wdo_bias"],"AGUARDAR")
            self.assertFalse(r["real_market_reaction_measured"])
            self.assertFalse(r["trade_pnl_measured"])
            self.assertFalse(r["predictive_accuracy_proven"])
            self.assertFalse(r["pre_event_directional_forecast_found"])
            self.assertIsNone(r["probability_calibrated"])
            for flag in ("b3_raw_quotes_archived","b3_quotes_origins_verified",
                         "announcement_actual_timestamp_verified","can_feed_live_radar",
                         "trading_authorized","worker_enabled","scheduler_enabled",
                         "paid_provider_approved","render_configuration_changed"):
                self.assertFalse(r[flag],flag)


if __name__ == "__main__":
    unittest.main()
