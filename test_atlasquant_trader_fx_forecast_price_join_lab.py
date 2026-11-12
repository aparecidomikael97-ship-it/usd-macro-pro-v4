"""Synthetic-only join tests; no forecasts or MT5 broker archives accessed."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_fx_forecast_precommit_lab import (
    MacroVintageClaim, ForecastPrecommitClaim, build_fx_precommit_chain_lab,
)
from atlasquant_trader_fx_forecast_price_join_lab import (
    join_fx_forecast_to_next_mt5_bar_lab as join,
)
from test_atlasquant_trader_mt5_forward_label_gate_lab import fixture

UTC = timezone.utc


def setup(*, pair="EUR/USD", horizon="D1", side="UP", shift_from=None,
          shift_intervals=0):
    frame = horizon if horizon != "M1" else "D1"
    manifest, compressed, times = fixture(
        pair=pair, frame=frame,
        overrides={101: {"open": "1.01000"}},
        shift_from=shift_from, shift_intervals=shift_intervals)
    outcome_start = datetime.fromtimestamp(times[101], UTC)
    seconds = {"D1": 86400, "W1": 604800, "M1": 30 * 86400}[horizon]
    forecast_at = outcome_start - timedelta(hours=1)
    refs = tuple(MacroVintageClaim(
        currency=c, issuer_code="OFFICIAL_ISSUER", release_id=f"{c}_DOC_2024",
        published_at=forecast_at - timedelta(days=5),
        captured_at=forecast_at - timedelta(days=4),
        original_sha256_claim="f" * 64,
    ) for c in pair.split("/"))
    row = ForecastPrecommitClaim(
        opportunity_id="JOIN_001", pair=pair, horizon=horizon,
        side=side, abstain_reason="NO_EDGE" if side == "ABSTAIN" else None,
        features_captured_at=forecast_at - timedelta(minutes=20),
        features_sha256_claim="a" * 64,
        model_frozen_at=forecast_at - timedelta(days=1),
        model_sha256_claim="b" * 64,
        prediction_issued_at=forecast_at,
        outcome_start_at=outcome_start,
        outcome_end_at=outcome_start + timedelta(seconds=seconds),
        macro_vintages=refs,
    )
    evaluation = row.outcome_end_at + timedelta(days=1)
    chain = build_fx_precommit_chain_lab([row], evaluated_at_utc=evaluation)
    assert chain["local_hash_chain_self_consistent"]
    return row, chain, manifest, compressed, times, evaluation


def run(row, chain, manifest, compressed, times, evaluation, *,
        selected_id="JOIN_001", head=None):
    return join(
        [row], chain["chain_entries"],
        chain["head_sha256_claim"] if head is None else head,
        opportunity_id=selected_id, manifest_record=manifest,
        compressed_csv_gz=compressed, entry_bar_open_epoch=times[100],
        exit_bar_open_epoch=times[101], evaluated_at_utc=evaluation)


class FxForecastPriceJoinLabTests(unittest.TestCase):
    def no_go(self, r):
        for field in ("external_receipt_timestamp_authenticated",
                      "macro_vintages_independently_authenticated",
                      "mt5_broker_candle_utc_authenticated",
                      "entry_price_known_at_prediction_time",
                      "historical_point_in_time_verified",
                      "costs_spreads_slippage_validated",
                      "can_feed_validated_backtest",
                      "trade_authorized", "publishable", "worker_enabled",
                      "scheduler_enabled"):
            self.assertIs(r[field], False, field)
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["is_hit"])
        self.assertEqual(r["real_accuracy_count_increment"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual((r["http_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))

    def blocked(self, r, reason):
        self.assertEqual(r["state"], "LAB_FORECAST_PRICE_JOIN_BLOCKED")
        self.assertEqual(r["reason"], reason)
        self.assertIsNone(r["forward_body_move_bps_documentary"])
        self.no_go(r)

    def test_daily_documentary_join_is_not_accuracy(self):
        data = setup()
        r = run(*data)
        self.assertEqual(r["state"],
                         "LAB_FORECAST_AND_FUTURE_BAR_DOCUMENTARY_JOIN_UNATTESTED")
        self.assertTrue(r["precommit_receipts_locally_match"])
        self.assertTrue(r["price_source_hash_self_consistent"])
        self.assertEqual(r["forward_body_move_bps_documentary"], "0.9901")
        self.assertEqual(r["observed_body_direction_only"], "UP")
        self.assertEqual(r["outcome_price_reference"],
                         "NEXT_CANDLE_OPEN_TO_CLOSE_NOT_TRADE_FILL")
        self.no_go(r)

    def test_weekly_join_works_as_unattested_documentary_research(self):
        r = run(*setup(pair="GBP/JPY", horizon="W1", side="DOWN"))
        self.assertEqual(r["state"],
                         "LAB_FORECAST_AND_FUTURE_BAR_DOCUMENTARY_JOIN_UNATTESTED")
        # Price went UP but the user-supplied direction is DOWN: no hit scored.
        self.assertEqual(r["side_claim"], "DOWN")
        self.assertEqual(r["observed_body_direction_only"], "UP")
        self.no_go(r)

    def test_abstentions_can_be_documented_without_counting_a_hit(self):
        r = run(*setup(side="ABSTAIN"))
        self.assertEqual(r["state"],
                         "LAB_FORECAST_AND_FUTURE_BAR_DOCUMENTARY_JOIN_UNATTESTED")
        self.assertEqual(r["abstain_reason"], "NO_EDGE")
        self.no_go(r)

    def test_monthly_blocked_without_matching_mt5_m1_price_series(self):
        self.blocked(run(*setup(horizon="M1")),
                     "MONTHLY_HORIZON_HAS_NO_ATTESTED_MT5_M1_LABEL")

    def test_changed_forecast_after_receipt_is_not_joined(self):
        row, chain, m, b, times, evaluation = setup()
        changed = replace(row, side="DOWN")
        self.blocked(run(changed, chain, m, b, times, evaluation),
                     "FORECAST_RECEIPTS_NOT_EVEN_LOCALLY_VERIFIED")

    def test_forged_receipt_head_is_not_joined(self):
        row, chain, m, b, times, evaluation = setup()
        self.blocked(run(row, chain, m, b, times, evaluation, head="e" * 64),
                     "FORECAST_RECEIPTS_NOT_EVEN_LOCALLY_VERIFIED")

    def test_missing_opportunity_id_rejected(self):
        row, chain, m, b, times, evaluation = setup()
        self.blocked(run(row, chain, m, b, times, evaluation, selected_id="NOT_FOUND"),
                     "OPPORTUNITY_ID_NOT_FOUND")

    def test_outcome_start_must_match_next_bar_open_exactly(self):
        row, chain, m, b, times, evaluation = setup()
        altered = replace(row, outcome_start_at=row.outcome_start_at + timedelta(minutes=1),
                          outcome_end_at=row.outcome_end_at + timedelta(minutes=1))
        altered_chain = build_fx_precommit_chain_lab([altered], evaluated_at_utc=evaluation)
        self.blocked(run(altered, altered_chain, m, b, times, evaluation),
                     "FORECAST_WINDOW_OR_RESOLUTION_TIME_MISMATCH")

    def test_unresolved_outcome_cannot_be_matched_in_advance(self):
        row, chain, m, b, times, evaluation = setup()
        too_early = row.outcome_start_at + timedelta(hours=1)
        self.blocked(run(row, chain, m, b, times, too_early),
                     "FORECAST_WINDOW_OR_RESOLUTION_TIME_MISMATCH")

    def test_wrong_series_pair_or_timeframe_rejected(self):
        row, chain, m, b, times, evaluation = setup()
        for altered in ({**m, "symbol": "USDJPY"}, {**m, "timeframe": "W1"}):
            with self.subTest(altered=altered):
                r = run(row, chain, altered, b, times, evaluation)
                self.blocked(r, "MT5_DOCUMENTARY_LABEL_BLOCKED_"
                                "MANIFEST_SERIES_OR_CLOSED_BARS_CLAIM_INVALID")

    def test_gapped_ohlc_history_rejected_before_joining(self):
        self.blocked(run(*setup(shift_from=101, shift_intervals=1)),
                     "MT5_DOCUMENTARY_LABEL_BLOCKED_NON_NOMINAL_TIME_GAP_NO_IMPUTATION")

    def test_modified_price_bytes_rejected_even_with_unmodified_receipts(self):
        row, chain, m, b, times, evaluation = setup()
        self.blocked(run(row, chain, m, b[:-5], times, evaluation),
                     "MT5_DOCUMENTARY_LABEL_BLOCKED_GZIP_DECOMPRESSION_FAILED")

    def test_missing_candle_epoch_rejected(self):
        row, chain, m, b, times, evaluation = setup()
        times[100] += 50
        self.blocked(run(row, chain, m, b, times, evaluation),
                     "MT5_DOCUMENTARY_LABEL_BLOCKED_BAR_NOT_FOUND_OR_NOT_ADJACENT")

    def test_boolean_epoch_rejected(self):
        row, chain, m, b, times, evaluation = setup()
        times[100] = True
        self.blocked(run(row, chain, m, b, times, evaluation),
                     "INVALID_SELECTED_CANDLE_EPOCHS")


if __name__ == "__main__":
    unittest.main()
