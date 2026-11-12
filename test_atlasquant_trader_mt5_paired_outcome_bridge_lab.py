"""Synthetic tests only: pair a fixed forecast ledger with MT5 archive labels."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import csv
import gzip
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_trader_mt5_paired_outcome_bridge_lab import (
    RecordedFxHypothesis, evaluate_paired_mt5_outcomes_lab as evaluate,
)
from atlasquant_trader_regime_increment_benchmark_lab import PredeclaredWindow
from atlasquant_trader_mt5_closedbar_outcome_lab import COLUMNS, MT5_SCHEMA

UTC = timezone.utc
NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)
CAPTURED = datetime(2026, 11, 7, 10, tzinfo=UTC)


class PairedArchiveFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.asset = "EUR/USD"
        self.horizon = "D1"
        self.start = datetime(2025, 4, 1, tzinfo=UTC)
        self.step = timedelta(days=1)
        self.count = 500
        self.rows = []
        self.generate_archive()
        self.setup_cohort()

    def generate_archive(self):
        self.rows = []
        for i in range(self.count):
            started = self.start + self.step * i
            o = 100 + i / 10
            # Deliberate alternating fictional outcomes; no market inference.
            c = o + (0.25 if i % 4 else -0.25)
            self.rows.append({
                "time_utc_epoch": str(int(started.timestamp())),
                "open": str(o), "high": str(o + 1), "low": str(o - 1),
                "close": str(c), "tick_volume": "10", "spread": "2",
                "real_volume": "0",
            })
        self.write_archive()

    def write_archive(self):
        payload = StringIO(newline="")
        writer = csv.DictWriter(payload, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(self.rows)
        raw = payload.getvalue().encode()
        symbol = self.asset.replace("/", "")
        file = self.root / f"{symbol}_{self.horizon}_closedbar.csv.gz"
        with file.open("wb") as output:
            with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as archive:
                archive.write(raw)
        record = {
            "symbol": symbol, "timeframe": self.horizon,
            "requested": self.count, "returned": self.count,
            "bar_position_start": 1,
            "observed_at_utc": CAPTURED.isoformat(),
            "earliest_open_utc": datetime.fromtimestamp(int(self.rows[0]["time_utc_epoch"]), UTC).isoformat(),
            "latest_open_utc": datetime.fromtimestamp(int(self.rows[-1]["time_utc_epoch"]), UTC).isoformat(),
            "validation_errors": [], "sha256_uncompressed_csv": sha256(raw).hexdigest(),
            "snapshot_file": file.name,
        }
        for i in range(7):
            manifest = {
                "schema": MT5_SCHEMA, "research_only": True,
                "trade_authorized": False, "prediction_available": False,
                "broker_identity_independently_verified": False,
                "historical_point_in_time_verified": False,
                "records": [record] if i == 0 else [],
            }
            (self.root / f"batch_{i*4:02d}_manifest.json").write_text(json.dumps(manifest))

    def setup_cohort(self):
        # Three disjoint predeclared windows with 40 examples each.
        self.indices = [list(range(x, x+40)) for x in (30, 120, 300)]
        self.windows = []
        self.hypotheses = []
        for widx, indices in enumerate(self.indices):
            start_open = self.start + indices[0]*self.step
            end_open = self.start + (indices[-1]+1)*self.step
            self.windows.append(PredeclaredWindow(start_open-self.step, end_open))
            for idx in indices:
                opened = self.start + idx * self.step
                self.hypotheses.append(RecordedFxHypothesis(
                    opportunity_id=f"FX_{self.horizon}_W{widx}_{idx:04d}",
                    asset=self.asset, horizon=self.horizon,
                    candidate_direction="ALTA", prediction_locked_at=opened-timedelta(hours=6),
                    decided_at=opened-timedelta(hours=4),
                    regime_observed_at=opened-timedelta(hours=7),
                    target_open_epoch=int(opened.timestamp()),
                    baseline_eligible=True, regime_veto=(idx%4==0),
                    decision_sha256_claim="a"*64,
                    regime_source_sha256_claim="b"*64,
                ))
        self.ids = [h.opportunity_id for h in self.hypotheses]

    def run_bridge(self, hypotheses=None, ids=None, windows=None, **overrides):
        kwargs = {
            "hypotheses": self.hypotheses if hypotheses is None else hypotheses,
            "expected_opportunity_ids": self.ids if ids is None else ids,
            "predeclared_windows": self.windows if windows is None else windows,
            "archive_root": self.root, "as_of_utc": NOW,
        }
        kwargs.update(overrides)
        return evaluate(**kwargs)

    def no_live(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["original_source_broker_verified"])
        self.assertFalse(r["historical_price_available_at_prediction_verified"])
        self.assertFalse(r["predictions_externally_precommitted"])
        self.assertFalse(r["opportunity_manifest_externally_precommitted"])
        self.assertFalse(r["regime_rules_precommitted"])
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertEqual((r["http_requests"], r["file_writes"], r["new_cost_brl"]), (0, 0, 0))

    def test_full_paired_cohort_resolves_from_archived_prices(self):
        r = self.run_bridge()
        self.assertEqual(r["state"], "LAB_MATCHED_MT5_OUTCOMES_DOCUMENTARY_NO_GO")
        self.assertEqual((r["expected_opportunities"], r["resolved_outcomes"]), (120, 120))
        self.assertTrue(r["per_target_local_snapshot_hash_checked"])
        self.assertTrue(r["full_declared_manifest_reconciled"])
        b = r["benchmark"]
        self.assertEqual((b["baseline_issued"], b["filtered_issued"], b["filtered_rejected"]), (120, 90, 30))
        self.assertEqual((b["baseline_correct"], b["filtered_correct"], b["rejected_correct"]), (90, 90, 0))
        self.assertEqual(b["baseline_hit_rate_documentary"], 75)
        self.assertEqual(b["filtered_hit_rate_documentary"], 100)
        self.assertFalse(b["incremental_accuracy_validated"])
        self.assertFalse(b["real_market_data_loaded"])
        self.no_live(r)

    def test_no_silent_omission_even_one_missing_trial(self):
        r = self.run_bridge(hypotheses=self.hypotheses[:-1])
        self.assertEqual(r["reason"], "INVALID_MANIFEST_OR_INPUT")
        self.no_live(r)

    def test_missing_archive_target_blocks_all_even_when_119_valid(self):
        h = self.hypotheses[-1]
        amended = [*self.hypotheses[:-1], replace(h, target_open_epoch=h.target_open_epoch+3600)]
        r = self.run_bridge(hypotheses=amended)
        self.assertEqual(r["reason"], "UNRESOLVED_DECLARED_OUTCOME_NO_SUBSETTING")
        self.assertEqual(r["resolved_outcomes"], 0)
        self.no_live(r)

    def test_altered_csv_hash_blocks_everything(self):
        self.rows[400]["close"] = "3333"
        self.write_archive()
        # Header and manifest updated together is caller controlled, not external proof.
        # Detect direct tamper by changing archive AFTER the manifest snapshot.
        path = self.root / "EURUSD_D1_closedbar.csv.gz"
        path.write_bytes(path.read_bytes()[:-3])
        r = self.run_bridge()
        self.assertEqual(r["reason"], "UNRESOLVED_DECLARED_OUTCOME_NO_SUBSETTING")
        self.no_live(r)

    def test_duplicate_target_under_new_identifier_is_rejected(self):
        edited = list(self.hypotheses)
        edited[1] = replace(edited[1], target_open_epoch=edited[0].target_open_epoch)
        self.assertEqual(self.run_bridge(hypotheses=edited)["reason"], "DUPLICATE_TARGET_CANDLE")

    def test_forecast_after_target_blocks(self):
        edited = list(self.hypotheses)
        edited[0] = replace(edited[0], prediction_locked_at=edited[0].decided_at + timedelta(days=1))
        r = self.run_bridge(hypotheses=edited)
        self.assertEqual(r["reason"], "INVALID_OR_FUTURE_PREDICTION_TIMESTAMPS")
        self.no_live(r)

    def test_post_decision_regime_observation_blocks(self):
        edited = list(self.hypotheses)
        edited[0] = replace(edited[0], regime_observed_at=edited[0].decided_at+timedelta(minutes=1))
        r = self.run_bridge(hypotheses=edited)
        self.assertEqual(r["reason"], "INVALID_OR_FUTURE_PREDICTION_TIMESTAMPS")
        self.no_live(r)

    def test_prediction_locked_before_regime_observation_blocks(self):
        edited = list(self.hypotheses)
        edited[0] = replace(edited[0], prediction_locked_at=edited[0].regime_observed_at-timedelta(minutes=1))
        self.assertEqual(self.run_bridge(hypotheses=edited)["reason"], "INVALID_OR_FUTURE_PREDICTION_TIMESTAMPS")

    def test_bad_claimed_hash_is_rejected(self):
        edited = list(self.hypotheses)
        edited[0] = replace(edited[0], decision_sha256_claim="bad")
        self.assertEqual(self.run_bridge(hypotheses=edited)["reason"], "INVALID_FROZEN_HYPOTHESIS_SEMANTICS")

    def test_mixed_pair_cannot_be_pooled(self):
        edited = list(self.hypotheses)
        edited[0] = replace(edited[0], asset="GBP/USD")
        self.assertEqual(self.run_bridge(hypotheses=edited)["reason"], "MIXED_OR_UNSUPPORTED_ASSET_HORIZON")

    def test_missing_forecast_id_replaced_with_fake_must_block(self):
        ids = self.ids[:];ids[-1]="OTHER_MISSING_ID"
        self.assertEqual(self.run_bridge(ids=ids)["reason"], "MANIFEST_MISMATCH_NO_SILENT_OMISSION")

    def test_benchmark_does_not_employ_just_early_cohort(self):
        trimmed = self.hypotheses[:30]
        r = self.run_bridge(hypotheses=trimmed, ids=[x.opportunity_id for x in trimmed])
        self.assertEqual(r["state"], "LAB_MATCHED_MT5_OUTCOMES_DOCUMENTARY_NO_GO")
        self.assertEqual(r["resolved_outcomes"], 30)
        self.assertEqual(r["benchmark"]["state"], "LAB_SAMPLE_INSUFFICIENT_FOR_DESCRIPTIVE_COMPARISON")
        self.assertIsNone(r["benchmark"]["baseline_hit_rate_documentary"])
        self.assertIsNone(r["benchmark"]["filtered_hit_rate_documentary"])
        self.no_live(r)

    def test_no_future_evaluation_date(self):
        r = self.run_bridge(as_of_utc=datetime(2025, 1, 1, tzinfo=UTC))
        self.assertEqual(r["reason"], "INVALID_OR_FUTURE_PREDICTION_TIMESTAMPS")

    def test_naive_clock_is_invalid(self):
        self.assertEqual(self.run_bridge(as_of_utc=datetime(2026, 11, 8))["reason"], "INVALID_MANIFEST_OR_INPUT")

    def test_baseline_abstentions_stay_in_manifest_and_denominator(self):
        edited = list(self.hypotheses)
        edited[0] = replace(edited[0], baseline_eligible=False)
        r = self.run_bridge(hypotheses=edited)
        self.assertEqual((r["expected_opportunities"], r["resolved_outcomes"]), (120, 120))
        self.assertEqual(r["benchmark"]["baseline_abstained"], 1)
        self.assertEqual(r["benchmark"]["baseline_issued"], 119)
        self.no_live(r)

    def test_rejected_opportunities_still_have_outcomes(self):
        edited = [replace(h, regime_veto=True) for h in self.hypotheses]
        r = self.run_bridge(hypotheses=edited)
        self.assertEqual((r["expected_opportunities"], r["resolved_outcomes"]), (120, 120))
        self.assertEqual(r["benchmark"]["filtered_rejected"], 120)
        self.assertEqual(r["benchmark"]["filtered_issued"], 0)
        self.assertIsNone(r["benchmark"]["filtered_hit_rate_documentary"])
        self.no_live(r)

    def test_missing_single_candle_blocks_entire_cohort(self):
        missing_epoch = self.hypotheses[0].target_open_epoch
        self.rows = [r for r in self.rows if int(r["time_utc_epoch"]) != missing_epoch]
        # Keep a 500-row file and its declared hash consistent (one future bar
        # appended), so absence isn't masked as a malformed archive size.
        last = dict(self.rows[-1])
        last["time_utc_epoch"] = str(int(last["time_utc_epoch"]) + 86400)
        self.rows.append(last)
        self.write_archive()
        r = self.run_bridge()
        self.assertEqual(r["reason"], "UNRESOLVED_DECLARED_OUTCOME_NO_SUBSETTING")
        self.assertEqual(r["detail_documentary"], "TARGET_BAR_NOT_IN_ARCHIVE")
        self.assertEqual(r["resolved_outcomes"], 0)
        self.no_live(r)

    def test_weekly_cadence_without_d1_reinterpretation(self):
        self.asset="EUR/USD";self.horizon="W1";self.start=datetime(2022,10,2,tzinfo=UTC)
        self.step=timedelta(days=7);self.count=200
        self.generate_archive()
        self.indices=[list(range(x,x+40)) for x in (10, 65, 120)]
        # rebuild windows and matching weekly opportunities
        self.windows=[];self.hypotheses=[]
        for w, group in enumerate(self.indices):
            self.windows.append(PredeclaredWindow(self.start+group[0]*self.step-self.step,
                                                   self.start+(group[-1]+1)*self.step))
            for i in group:
                opened=self.start+i*self.step
                self.hypotheses.append(RecordedFxHypothesis(
                    opportunity_id=f"FX_W1_W{w}_{i:04d}",asset=self.asset,
                    horizon="W1",candidate_direction="ALTA",
                    prediction_locked_at=opened-timedelta(hours=6),
                    decided_at=opened-timedelta(hours=4),
                    regime_observed_at=opened-timedelta(hours=7),
                    target_open_epoch=int(opened.timestamp()),
                    baseline_eligible=True,regime_veto=(i%4==0),
                    decision_sha256_claim="a"*64,regime_source_sha256_claim="b"*64))
        self.ids=[h.opportunity_id for h in self.hypotheses]
        r=self.run_bridge()
        self.assertEqual(r["state"], "LAB_MATCHED_MT5_OUTCOMES_DOCUMENTARY_NO_GO")
        self.assertEqual(r["resolved_outcomes"],120)
        self.assertEqual(r["benchmark"]["horizon"],"W1")
        self.no_live(r)


    def test_w1_ny17_dst_uncertainty_blocks_full_paired_scoring(self):
        opened = datetime(2026, 3, 1, 22, tzinfo=UTC)
        cases = [replace(h, horizon="W1") for h in self.hypotheses]
        cases[0] = replace(cases[0], target_open_epoch=int(opened.timestamp()),
                           prediction_locked_at=opened-timedelta(hours=6),
                           decided_at=opened-timedelta(hours=4),
                           regime_observed_at=opened-timedelta(hours=7))
        result = self.run_bridge(hypotheses=cases)
        self.assertEqual(result["reason"], "UNRESOLVED_DECLARED_OUTCOME_NO_SUBSETTING")
        self.assertEqual(result["detail_documentary"],
                         "W1_NY17_DST_CLOSE_REQUIRES_BROKER_VERIFICATION")
        self.assertIsNone(result["benchmark"])
        self.assertEqual(result["resolved_outcomes"], 0)
        self.no_live(result)


if __name__=="__main__":
    unittest.main()
