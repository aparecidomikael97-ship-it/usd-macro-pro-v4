"""Synthetic-only adversarial chronology tests; no real historical forecast."""
from datetime import datetime, timedelta, timezone
import json
import unittest
from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_premove_lab import FORECAST, OUTCOME, audit_fx_premove_lab as audit

NOW=datetime(2026,11,5,16,tzinfo=timezone.utc)
F={
    "schema":FORECAST,"pair":"EUR/USD","horizon":"D1",
    "model_version":"LAB_TEST_01","direction":"ALTA","evidence_sha256":"a"*64,
    "data_cutoff_utc":"2026-11-02T09:00:00Z",
    "created_at_utc":"2026-11-02T09:05:00Z",
    "target_start_utc":"2026-11-02T22:00:00Z",
    "target_end_utc":"2026-11-03T22:00:00Z",
}
O={
    "schema":OUTCOME,"pair":"EUR/USD","target_start_utc":F["target_start_utc"],
    "target_end_utc":F["target_end_utc"],
    "captured_at_utc":"2026-11-05T00:10:00Z",
    "source_kind":"ECB_REFERENCE_INDICATIVE","source_sha256":"b"*64,
    "first_price":"1.11","last_price":"1.12",
}


def dump(x):
    return json.dumps(x,separators=(",",":"),ensure_ascii=False).encode()


def run(f=None,o=None,now=NOW):
    return audit(dump(F if f is None else f) if not isinstance(f,bytes) else f,
        as_of_utc=now,
        outcome_raw=(None if o is None else dump(o) if not isinstance(o,bytes) else o))


class ForecastChronologyTests(unittest.TestCase):
    def assert_still_no_go(self,r):
        for key in ("forecast_precommit_independently_verified",
                    "pre_decision_data_availability_verified",
                    "frozen_model_pre_event_verified",
                    "outcome_original_source_authenticated",
                    "broker_m15_execution_verified",
                    "historical_point_in_time_eligible",
                    "trade_authorized","can_feed_live_radar","publishable",
                    "worker_enabled","scheduler_enabled"):
            self.assertIs(r[key],False,key)
        self.assertTrue(r["all_times_caller_claims"])
        self.assertEqual(r["validated_prediction_count"],0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertEqual((r["external_http_requests"],r["new_cost_brl"]),(0,0))

    def test_pre_move_record_is_hash_only_not_historical_proof(self):
        r=run()
        self.assertEqual(r["state"],"LAB_FORECAST_STRUCTURALLY_ACCEPTED_UNATTESTED")
        self.assertEqual(len(r["forecast_sha256"]),64)
        self.assertEqual(r["horizon"],"D1")
        self.assert_still_no_go(r)

    def test_correct_direction_arithmetic_not_real_accuracy(self):
        r=run(o=O)
        self.assertEqual(r["state"],"LAB_RETROSPECTIVE_DIRECTION_MATCH_UNATTESTED")
        self.assertEqual(r["observed_direction"],"ALTA")
        self.assertIs(r["arithmetic_direction_match_unverified"],True)
        self.assertEqual(len(r["outcome_sha256"]),64)
        self.assert_still_no_go(r)

    def test_incorrect_direction_detected_but_not_scored(self):
        o=dict(O,last_price="1.10")
        r=run(o=o)
        self.assertIs(r["arithmetic_direction_match_unverified"],False)
        self.assertEqual(r["observed_direction"],"BAIXA")
        self.assert_still_no_go(r)

    def test_neutral_abstention_is_not_binary_hit(self):
        f=dict(F,direction="NEUTRO")
        r=run(f,o=O)
        self.assertIsNone(r["arithmetic_direction_match_unverified"])
        self.assert_still_no_go(r)

    def test_equal_prices_do_not_mean_alta_or_baixa(self):
        r=run(o=dict(O,last_price="1.11"))
        self.assertEqual(r["observed_direction"],"NEUTRO")
        self.assertIs(r["arithmetic_direction_match_unverified"],False)

    def test_canonical_28_pairs_all_remain_blocked(self):
        for pair in OFFICIAL_PAIRS:
            f=dict(F,pair=pair)
            o=dict(O,pair=pair)
            r=run(f,o)
            self.assertEqual(r["state"],"LAB_RETROSPECTIVE_DIRECTION_MATCH_UNATTESTED")
            self.assert_still_no_go(r)

    def test_w1_fx_sunday_open_to_friday_close_recognized(self):
        f=dict(F,horizon="W1",
               data_cutoff_utc="2026-10-30T09:00:00Z",
               created_at_utc="2026-10-30T09:05:00Z",
               target_start_utc="2026-11-01T22:00:00Z",
               target_end_utc="2026-11-06T22:00:00Z")
        o=dict(O,target_start_utc=f["target_start_utc"],
               target_end_utc=f["target_end_utc"],
               captured_at_utc="2026-11-07T00:00:00Z")
        r=run(f,o,now=NOW+timedelta(days=10))
        self.assertEqual(r["state"],"LAB_RETROSPECTIVE_DIRECTION_MATCH_UNATTESTED")
        self.assert_still_no_go(r)

    def test_w1_with_d1_window_rejected(self):
        self.assertEqual(run(dict(F,horizon="W1"))["state"],"LAB_BLOCKED")

    def test_forecast_after_move_start_is_rejected(self):
        self.assertEqual(run(dict(F,created_at_utc="2026-11-02T23:00:00Z"))["state"],"LAB_BLOCKED")

    def test_future_information_claim_rejected(self):
        self.assertEqual(run(dict(F,data_cutoff_utc="2026-11-02T09:06:00Z"))["state"],"LAB_BLOCKED")

    def test_forecast_created_after_asof_rejected(self):
        self.assertEqual(run(now=datetime(2026,11,2,9,tzinfo=timezone.utc))["state"],"LAB_BLOCKED")

    def test_outcome_before_period_end_rejected(self):
        self.assertEqual(run(o=dict(O,captured_at_utc="2026-11-03T21:59:59Z"))["state"],
                         "LAB_BLOCKED")

    def test_outcome_after_asof_rejected(self):
        self.assertEqual(run(o=O,now=datetime(2026,11,4,tzinfo=timezone.utc))["state"],
                         "LAB_BLOCKED")

    def test_outcome_wrong_pair_rejected(self):
        self.assertEqual(run(o=dict(O,pair="GBP/USD"))["state"],"LAB_BLOCKED")

    def test_outcome_wrong_window_rejected(self):
        self.assertEqual(run(o=dict(O,target_start_utc="2026-11-03T01:00:00Z"))["state"],
                         "LAB_BLOCKED")

    def test_future_unknown_model_and_signals_rejected(self):
        for f in (dict(F,direction="BUY"),dict(F,model_version="LIVE_MODEL"),
                  dict(F,horizon="M15"),dict(F,pair="EUR/EUR")):
            self.assertEqual(run(f)["state"],"LAB_BLOCKED")

    def test_bad_hashes_rejected(self):
        self.assertEqual(run(dict(F,evidence_sha256="foo"))["state"],"LAB_BLOCKED")
        self.assertEqual(run(o=dict(O,source_sha256="foo"))["state"],"LAB_BLOCKED")

    def test_wrong_broker_price_or_invalid_outcome_value_rejected(self):
        for price in (1.1, True, "NaN", "-1", "0", "1e9", None):
            self.assertEqual(run(o=dict(O,last_price=price))["state"],"LAB_BLOCKED")

    def test_unrecognized_outcome_source_not_upgraded(self):
        self.assertEqual(run(o=dict(O,source_kind="SIGNED_REAL_BROKER"))["state"],
                         "LAB_BLOCKED")

    def test_json_duplicates_and_nonfinite_rejected(self):
        f=dump(F)[:-1]+b',"pair":"EUR/USD"}'
        o=dump(O)[:-1]+b',"pair":"EUR/USD"}'
        self.assertEqual(run(f)["state"],"LAB_BLOCKED")
        self.assertEqual(run(o=o)["state"],"LAB_BLOCKED")

    def test_missing_and_unknown_fields_rejected(self):
        f=dict(F)
        del f["evidence_sha256"]
        self.assertEqual(run(f)["state"],"LAB_BLOCKED")
        self.assertEqual(run(o=dict(O,confidence=0.99))["state"],"LAB_BLOCKED")

    def test_bad_utc_clock_types_rejected(self):
        for now in (None,"",datetime(2026,11,5),42):
            self.assertEqual(run(now=now)["state"],"LAB_BLOCKED")
        self.assertEqual(run(dict(F,created_at_utc="2026-11-02T09:05:00-04:00"))["state"],
                         "LAB_BLOCKED")

    def test_forecast_raw_invalid_bytes_rejected(self):
        for b in (b"garbage",b"\xff",b"{}",b"[]",b"null"):
            self.assertEqual(run(f=b)["state"],"LAB_BLOCKED")

    def test_sha_changes_if_direction_changed(self):
        a=run()
        b=run(dict(F,direction="BAIXA"))
        self.assertNotEqual(a["forecast_sha256"],b["forecast_sha256"])
        self.assert_still_no_go(a)
        self.assert_still_no_go(b)

    def test_utc_midnight_fake_daily_window_denied(self):
        f=dict(F,target_start_utc="2026-11-03T00:00:00Z",
               target_end_utc="2026-11-04T00:00:00Z")
        r=run(f)
        self.assertEqual(r["state"],"LAB_BLOCKED")
        self.assertEqual(r["reason"],"FORECAST_NOT_A_CANONICAL_NY_FX_D1_W1_SESSION")

    def test_friday_to_sunday_is_not_a_forex_daily_session(self):
        f=dict(F,created_at_utc="2026-10-29T09:05:00Z",
               data_cutoff_utc="2026-10-29T09:00:00Z",
               target_start_utc="2026-10-30T21:00:00Z",
               target_end_utc="2026-11-01T22:00:00Z")
        self.assertEqual(run(f)["state"],"LAB_BLOCKED")

    def test_edt_ny_close_session_is_21_utc_not_fixed_est(self):
        f=dict(F,created_at_utc="2026-10-26T09:05:00Z",
               data_cutoff_utc="2026-10-26T09:00:00Z",
               target_start_utc="2026-10-26T21:00:00Z",
               target_end_utc="2026-10-27T21:00:00Z")
        self.assertEqual(run(f)["state"],"LAB_FORECAST_STRUCTURALLY_ACCEPTED_UNATTESTED")
        f["target_start_utc"]="2026-10-26T22:00:00Z"
        f["target_end_utc"]="2026-10-27T22:00:00Z"
        self.assertEqual(run(f)["state"],"LAB_BLOCKED")

    def test_broker_market_hours_not_attested_by_timezone_check(self):
        r=run(o=O)
        self.assertFalse(r["broker_calendar_independently_verified"])
        self.assertIn("FX_NY_1700_ROLLOVER",r["fx_ny_rollover_convention"])
        self.assert_still_no_go(r)


if __name__ == "__main__":
    unittest.main()
