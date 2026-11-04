"""Cleveland Fed pre-event CPI model: NOT a market consensus or USD bias."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import unittest

from atlasquant_trader_us_cpi_cleveland_nowcast_lab import (
    SCHEMA, MEASURES, inspect_us_cpi_pre_event_nowcast_lab,
)

CASE = Path(__file__).resolve().parent / "docs" / "continuidade" / "TRADER_CLEVELAND_US_CPI_NOWCAST_20261102.json"
ISSUED = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
EVALUATED = datetime(2026, 11, 3, 12, 1, tzinfo=timezone.utc)


def data():
    return json.loads(CASE.read_text(encoding="utf-8"))


def claimed():
    return {
        "state": "LAB_SYNTHETIC_CONSENSUS_UNATTESTED",
        "source_name": "SYNTHETIC test consensus only",
        "reference_month": "2026-10",
        "captured_at_utc": "2026-11-03T11:00:00Z",
        "cpi_mom_sa_pct": 0.20,
        "core_cpi_mom_sa_pct": 0.25,
    }


def run(book=None, consensus=None, issued=ISSUED, evaluated=EVALUATED):
    return inspect_us_cpi_pre_event_nowcast_lab(
        data() if book is None else book,
        issued_at=issued, evaluated_at=evaluated, claimed_consensus=consensus)


class ClevelandNowcastResearchLabTests(unittest.TestCase):
    def test_real_public_model_numbers_and_correct_measure_names(self):
        m = data()
        self.assertEqual(m["schema"], SCHEMA)
        self.assertEqual(set(m["measures"]), set(MEASURES))
        self.assertEqual(m["measures"], {
            "CPI_MOM_SA_PCT": 0.24, "CORE_CPI_MOM_SA_PCT": 0.21,
            "CPI_YOY_NSA_PCT": 3.74, "CORE_CPI_YOY_NSA_PCT": 2.48,
        })
        self.assertEqual(m["source_updated_day"], "2026-11-02")

    def test_no_consensus_stays_model_only_and_wait(self):
        result = run()
        self.assertEqual(result["state"], "LAB_PRE_EVENT_NOWCAST_MODEL_ONLY")
        self.assertEqual(result["directional_bias"], "AGUARDAR")
        self.assertIsNone(result["model_minus_consensus_pp"])
        self.assertIsNone(result["actual_cpi"])

    def test_correct_future_cpi_release_after_us_dst_switch(self):
        self.assertEqual(run()["official_cpi_scheduled_utc"], "2026-11-10T13:30:00+00:00")

    def test_synthetic_consensus_gap_is_arithmetic_not_surprise(self):
        out = run(consensus=claimed())
        self.assertEqual(out["state"], "LAB_MODEL_VS_SYNTHETIC_CONSENSUS_ONLY")
        self.assertEqual(out["model_minus_consensus_pp"], {
            "CPI_MOM_SA_PP": 0.04, "CORE_CPI_MOM_SA_PP": -0.04,
        })
        self.assertIsNone(out["actual_cpi"])
        self.assertEqual(out["directional_bias"], "AGUARDAR")

    def test_gap_sign_changes_without_direction(self):
        c = claimed()
        c["cpi_mom_sa_pct"] = 0.28
        c["core_cpi_mom_sa_pct"] = 0.15
        out = run(consensus=c)
        self.assertEqual(out["model_minus_consensus_pp"],
                         {"CPI_MOM_SA_PP": -0.04, "CORE_CPI_MOM_SA_PP": 0.06})
        self.assertEqual(out["directional_bias"], "AGUARDAR")

    def test_yoy_nsa_never_compared_to_mom_sa_consensus(self):
        out = run(consensus=claimed())
        self.assertEqual(set(out["model_minus_consensus_pp"]),
                         {"CPI_MOM_SA_PP", "CORE_CPI_MOM_SA_PP"})
        self.assertEqual(out["model_nowcast"]["CPI_YOY_NSA_PCT"], 3.74)

    def test_historical_asof_before_research_denied(self):
        out = run(issued=datetime(2026, 10, 30, 12, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_research_day_not_exact_receipt(self):
        out = run(issued=datetime(2026, 11, 2, 23, 59, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_past_due_not_auto_actual(self):
        out = run(issued=datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc),
                  evaluated=datetime(2026, 11, 10, 14, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_CPI_CALENDAR_PAST_DUE_REQUIRES_NEW_ACTUAL")
        self.assertIsNone(out["actual_cpi"])

    def test_no_90_percent_or_trading_authority(self):
        for out in (run(), run(consensus=claimed())):
            self.assertIsNone(out["probability_calibrated"])
            for key in ("accuracy_90_proven", "market_consensus_verified",
                        "original_intraday_capture_attested",
                        "real_historical_backtest_authorized",
                        "can_feed_live_radar", "trade_authorized",
                        "worker_enabled", "scheduler_enabled"):
                self.assertFalse(out[key], key)

    def test_never_allow_actual_on_pre_event_case(self):
        m = data()
        m["actual_release"] = 0.24
        self.assertEqual(run(book=m)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_real_consensus_cannot_be_claimed_from_page(self):
        m = data()
        m["market_consensus"] = 0.25
        self.assertEqual(run(book=m)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_fake_source_archive_attestation_refused(self):
        for flag in ("source_value_vintage_archived",
                     "original_intraday_capture_attested",
                     "market_consensus_verified",
                     "source_redistribution_rights_verified",
                     "real_historical_backtest_authorized"):
            with self.subTest(flag=flag):
                m = data()
                m[flag] = True
                self.assertEqual(run(book=m)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_future_page_update_claim_rejected(self):
        m = data()
        m["source_updated_day"] = "2026-11-05"
        self.assertEqual(run(book=m)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_manifest_backdate_research_rejected(self):
        m = data()
        m["earliest_structural_research_asof_utc"] = "2026-11-02T00:00:00Z"
        self.assertEqual(run(book=m)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_wrong_portal_rejected(self):
        m = data()
        m["source_url"] = "https://www.clevelandfed.org.evil.example/indicators-and-data/inflation-nowcasting"
        self.assertEqual(run(book=m)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_wrong_calendar_rejected(self):
        m = data()
        m["schedule_url"] = "https://www.bls.gov/fake"
        self.assertEqual(run(book=m)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_missing_or_extra_unit_is_rejected(self):
        for action in ("del", "extra"):
            with self.subTest(action=action):
                m = data()
                if action == "del":
                    del m["measures"]["CORE_CPI_MOM_SA_PCT"]
                else:
                    m["measures"]["CPI_QOQ_PCT"] = 0.4
                self.assertEqual(run(book=m)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_nonfinite_or_boolean_model_value_rejected(self):
        for bad in (float("nan"), float("inf"), True, "0.24"):
            with self.subTest(bad=str(bad)):
                m = data()
                m["measures"]["CPI_MOM_SA_PCT"] = bad
                self.assertEqual(run(book=m)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_unverified_consensus_contract_required(self):
        c = claimed()
        c["state"] = "OFFICIAL_CONSENSUS_VERIFIED"
        self.assertEqual(run(consensus=c)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_late_claimed_consensus_rejected(self):
        c = claimed()
        c["captured_at_utc"] = "2026-11-10T13:30:00Z"
        self.assertEqual(run(consensus=c)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_mismatched_month_rejected(self):
        c = claimed()
        c["reference_month"] = "2026-09"
        self.assertEqual(run(consensus=c)["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")

    def test_naive_issue_rejected(self):
        with self.assertRaises(ValueError):
            run(issued=datetime(2026, 11, 3, 12, 0))

    def test_evaluation_before_issue_rejected(self):
        out = run(evaluated=datetime(2026, 11, 3, 11, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_CLEVELAND_NOWCAST_REFUSED")


if __name__ == "__main__":
    unittest.main()
