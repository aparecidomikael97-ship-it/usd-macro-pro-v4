"""Synthetic claim/price join. NO real forecast witness or MT5 validation."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from zoneinfo import ZoneInfo

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_ny17_forecast_outcome_join_lab import (
    Ny17ForecastClaim, inspect_ny17_full_forecast_outcome_join_lab as join,
)
from atlasquant_trader_mt5_28fx_full_roster_lab import (
    inspect_am12_ny17_full_roster_lab,
)
from test_atlasquant_trader_mt5_28fx_archive_reader_lab import build

NY = ZoneInfo("America/New_York")
UTC = timezone.utc
PLAN = datetime(2026, 11, 8, 18, tzinfo=UTC)
NOW = datetime(2026, 12, 11, 0, tzinfo=UTC)


def ny(day):
    return datetime(2026, 11, day, 17, tzinfo=NY).astimezone(UTC)


def roster(*, horizon="D1", days=(8,), outcome="UP"):
    windows = []
    for ix, day in enumerate(days, 1):
        start = ny(day)
        end = ny(day + (5 if horizon == "W1" else 1))
        bps = "10.0000" if outcome == "UP" else (
            "-10.0000" if outcome == "DOWN" else "0.0000")
        close = "1.0010" if outcome == "UP" else (
            "0.9990" if outcome == "DOWN" else "1.0000")
        windows.append({
            "window_number": ix, "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "local_archive_check_state":
                "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO",
            "pair_checks_complete_claim_only": 28,
            "pair_checks_blocked_or_unverifiable": 0,
            "blocked_pairs": [],
            "unverifiable_pair_reasons": {},
            "price_movements_documentary_by_pair": {
                pair: {
                    "start_open_documentary": "1.0000",
                    "end_close_documentary": close,
                    "change_bps_documentary": bps,
                    "direction_documentary": outcome,
                }
                for pair in OFFICIAL_PAIRS
            },
        })
    return {
        "schema": "ATLASQUANT_TRADER_MT5_FULL_NY17_WINDOW_ROSTER_LAB_V1",
        "state": "LAB_AM12_NY17_FULL_ROSTER_LOCAL_CLAIMS_ONLY_NO_GO",
        "horizon": horizon,
        "all_nominal_windows_locally_checked_complete": True,
        "nominal_window_count": len(windows),
        "complete_local_window_count": len(windows),
        "total_expected_pair_window_checks": len(windows) * 28,
        "local_pair_window_checks_complete": len(windows) * 28,
        "blocked_or_unverifiable_pair_window_checks": 0,
        "windows": windows,
    }


def claims(r):
    out = []
    for w in r["windows"]:
        start, end = (datetime.fromisoformat(w[k]) for k in
                      ("start_utc", "end_utc"))
        for i, pair in enumerate(OFFICIAL_PAIRS):
            out.append(Ny17ForecastClaim(
                opportunity_id=f"FORECAST_{w['window_number']:02d}_{i:02d}",
                pair=pair, horizon=r["horizon"],
                outcome_start_at=start, outcome_end_at=end,
                direction_claim="UP",
                features_cutoff_at=start - timedelta(hours=3),
                forecast_issued_at=start - timedelta(hours=1),
                model_sha256_claim="a" * 64,
                evidence_sha256_claim="b" * 64,
            ))
    return out


def audit(r=None, c=None, *, planned=PLAN, at=NOW):
    r = roster() if r is None else r
    return join(price_roster=r,
                forecast_claims=claims(r) if c is None else c,
                plan_declared_at_utc=planned, evaluated_at_utc=at)


class FullFxForecastPriceJoinTests(unittest.TestCase):
    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertFalse(r["out_of_sample_accuracy_validated"])
        for flag in (
            "price_archive_source_independently_authenticated",
            "broker_session_calendar_independently_authenticated",
            "forecast_pre_event_witness_independently_authenticated",
            "model_and_macro_vintages_authenticated",
            "prediction_market_ex_ante_available_verified",
            "statistical_independence_verified",
            "transaction_costs_checked",
            "publishable", "can_feed_live_radar", "live_alert_allowed",
            "trade_authorized", "worker_enabled", "scheduler_enabled",
        ):
            self.assertFalse(r[flag], flag)
        self.assertEqual((r["http_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))
        self.assertTrue(r["research_only"])

    def test_full_28_pair_one_day_claims_join_without_accuracy(self):
        r = audit()
        self.assertEqual(r["state"],
                         "LAB_NY17_COMPLETE_FORECAST_PRICE_CLAIMS_ONLY_NO_GO")
        self.assertEqual(r["expected_opportunities"], 28)
        self.assertEqual(r["declared_abstentions"], 0)
        self.assertEqual(r["directional_claims"], 28)
        self.assertEqual(r["documentary_same_direction_count"], 28)
        self.assertEqual(r["documentary_opposite_direction_count"], 0)
        self.assertEqual(len(r["rows_documentary"]), 28)
        self.assertTrue(r["full_28fx_all_window_manifest_reconciled"])
        self.assertTrue(all(not v["external_precommit_verified"]
                            for v in r["rows_documentary"]))
        self.safe(r)

    def test_abstention_down_and_flat_are_not_considered_hits(self):
        price = roster()
        data = claims(price)
        data[0] = replace(data[0], direction_claim="ABSTAIN",
                          abstain_reason="UNVERIFIED_SOURCE")
        data[1] = replace(data[1], direction_claim="DOWN")
        price["windows"][0]["price_movements_documentary_by_pair"][
            OFFICIAL_PAIRS[2]] = {
            "start_open_documentary": "1.0000",
            "end_close_documentary": "1.0000",
            "change_bps_documentary": "0.0000",
            "direction_documentary": "FLAT",
        }
        report = audit(price, data)
        self.assertEqual(report["declared_abstentions"], 1)
        self.assertEqual(report["directional_claims"], 27)
        self.assertEqual(report["documentary_same_direction_count"], 25)
        self.assertEqual(report["documentary_opposite_direction_count"], 1)
        self.assertEqual(report["documentary_flat_outcomes_count"], 1)
        self.assertEqual(report["rows_documentary"][0][
            "comparison_documentary_only"], "ABSTENTION_NOT_A_HIT")
        self.assertEqual(report["rows_documentary"][2][
            "comparison_documentary_only"], "FLAT_OUTCOME_NOT_A_HIT")
        self.safe(report)

    def test_missing_one_of_28_claims_blocks_entire_cohort(self):
        data = claims(roster())[:-1]
        r = audit(c=data)
        self.assertEqual(r["reason"],
                         "FULL_28FX_WINDOW_AND_FORECAST_CENSUS_REQUIRED")
        self.assertEqual(r["rows_documentary"], [])
        self.safe(r)

    def test_duplicate_pair_window_claim_blocks_even_with_28_rows(self):
        data = claims(roster())
        data[27] = replace(data[0], opportunity_id="FORECAST_DUP_27")
        r = audit(c=data)
        self.assertEqual(r["reason"], "DUPLICATE_PAIR_WINDOW_FORECAST_CLAIM")
        self.safe(r)

    def test_duplicate_opportunity_id_rejected(self):
        data = claims(roster())
        data[1] = replace(data[1], opportunity_id=data[0].opportunity_id)
        r = audit(c=data)
        self.assertEqual(r["reason"],
                         "FORECAST_INVALID_DUPLICATE_OR_POST_EVENT_CLAIM")
        self.safe(r)

    def test_future_or_last_second_prediction_and_stale_feature_rejected(self):
        price = roster()
        for changed in (
            {"forecast_issued_at": ny(8)},
            {"forecast_issued_at": ny(8) + timedelta(seconds=1)},
            {"features_cutoff_at": ny(8)},
            {"features_cutoff_at": PLAN - timedelta(seconds=1)},
            {"model_sha256_claim": "f" * 60},
        ):
            with self.subTest(changed=changed):
                data = claims(price)
                data[0] = replace(data[0], **changed)
                r = audit(price, data)
                self.assertEqual(r["reason"],
                                 "FORECAST_INVALID_DUPLICATE_OR_POST_EVENT_CLAIM")
                self.safe(r)

    def test_abstention_must_have_reason_nonabstention_must_not(self):
        for side, reason in (("ABSTAIN", None), ("UP", "OTHER")):
            with self.subTest(side=side):
                data = claims(roster())
                data[0] = replace(data[0], direction_claim=side,
                                  abstain_reason=reason)
                r = audit(c=data)
                self.assertEqual(r["state"],
                                 "LAB_NY17_FORECAST_OUTCOME_JOIN_BLOCKED")
                self.safe(r)

    def test_tampered_price_direction_or_bps_blocks_entire_roster(self):
        for field, altered in (
            ("direction_documentary", "DOWN"),
            ("change_bps_documentary", "800.0000"),
            ("start_open_documentary", "1.0005"),
        ):
            with self.subTest(field=field):
                r = roster()
                r["windows"][0]["price_movements_documentary_by_pair"][
                    OFFICIAL_PAIRS[5]][field] = altered
                response = audit(r)
                self.assertEqual(response["reason"],
                                 "DOCUMENTARY_PRICE_DIRECTION_OR_BPS_MISMATCH")
                self.safe(response)

    def test_missing_pair_price_label_or_wrong_week_is_rejected(self):
        r = roster()
        del r["windows"][0]["price_movements_documentary_by_pair"][
            OFFICIAL_PAIRS[2]]
        self.assertEqual(audit(r)["reason"],
                         "MISSING_OR_EXTRA_PRICE_MOVEMENT_SLOTS")
        weekly = roster(horizon="W1")
        weekly["windows"][0]["end_utc"] = ny(15).isoformat()
        self.assertTrue(audit(weekly)["reason"].startswith(
            "INVALID_NY17_WINDOW_"))
        self.safe(audit(r))

    def test_missing_outcome_window_or_census_fails_without_cherry_pick(self):
        data = roster(days=(8, 9))
        data["state"] = "LAB_AM12_NY17_FULL_ROSTER_HAS_GAPS_NO_GO"
        r = audit(data)
        self.assertEqual(r["state"], "LAB_NY17_FORECAST_OUTCOME_JOIN_BLOCKED")
        self.assertEqual(r["rows_documentary"], [])
        self.safe(r)

    def test_two_daily_windows_reconcile_all_56_opportunities(self):
        r = roster(days=(8, 9))
        report = audit(r)
        self.assertEqual(report["declared_window_count"], 2)
        self.assertEqual(report["expected_opportunities"], 56)
        self.assertEqual(len(report["rows_documentary"]), 56)
        self.assertEqual(report["documentary_same_direction_count"], 56)
        self.safe(report)

    def test_weekly_28_forecasts_same_canonical_session(self):
        r = roster(horizon="W1", days=(8,))
        report = audit(r)
        self.assertEqual(report["state"],
                         "LAB_NY17_COMPLETE_FORECAST_PRICE_CLAIMS_ONLY_NO_GO")
        self.assertEqual(report["horizon"], "W1")
        self.assertEqual(len(report["rows_documentary"]), 28)
        self.safe(report)

    def test_real_reader_pipeline_with_only_synthetic_files_and_unwitnessed_claims(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            build(root)
            before = {p.name for p in root.iterdir()}
            result = inspect_am12_ny17_full_roster_lab(
                root=root, horizon="D1",
                range_start_at_utc=ny(8),
                range_end_at_utc=ny(9),
                evaluated_at_utc=NOW,
            )
            self.assertEqual(result["state"],
                             "LAB_AM12_NY17_FULL_ROSTER_LOCAL_CLAIMS_ONLY_NO_GO")
            joined = audit(result)
            self.assertEqual(joined["state"],
                             "LAB_NY17_COMPLETE_FORECAST_PRICE_CLAIMS_ONLY_NO_GO")
            self.assertEqual(joined["documentary_same_direction_count"], 28)
            self.assertEqual({p.name for p in root.iterdir()}, before)
            self.assertFalse(joined["forecast_pre_event_witness_independently_authenticated"])
            self.safe(joined)


if __name__ == "__main__":
    unittest.main()
