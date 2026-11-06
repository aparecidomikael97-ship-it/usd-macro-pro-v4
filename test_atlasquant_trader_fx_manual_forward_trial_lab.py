"""All forward-forecast inputs are fictional; no precommits are actually posted."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_premove_lab import FORECAST
from atlasquant_trader_g8_macro_asof_lab import ENVELOPE
from atlasquant_trader_fx_manual_forward_trial_lab import (
    SCHEMA, MIN_LEAD_MINUTES,
    inspect_fx_forward_candidate_lab as candidate,
    plan_next_fx_forward_trial_lab as plan,
)

FRIDAY = datetime(2026, 11, 6, 12, 50, tzinfo=timezone.utc)


def utc_text(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def raw(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def fixtures(*, pair="EUR/USD", horizon="D1", direction="ALTA",
             now=FRIDAY):
    windows = plan(as_of_utc=now)["horizon_windows"]
    a, b = pair.split("/")
    observation = "2026-10"
    records = []
    for currency in (a, b):
        for indicator in ("CPI_YOY", "POLICY_RATE"):
            records.append({
                "currency": currency, "indicator": indicator,
                "observation_period": observation,
                "value": "2.0",
                "published_at_utc": "2026-10-29T12:00:00Z",
                "captured_at_utc": "2026-10-29T12:05:00Z",
                "source_type": ("CENTRAL_BANK" if indicator == "POLICY_RATE"
                                else "OFFICIAL_STATISTICS_OFFICE"),
                "source_sha256": "a" * 64,
            })
    m = {
        "schema": ENVELOPE, "pair": pair,
        "decision_at_utc": utc_text(now), "records": records,
    }
    mr = raw(m)
    target = windows[horizon]
    f = {
        "schema": FORECAST, "pair": pair, "horizon": horizon,
        "model_version": "LAB_TEST_FORWARD_01",
        "direction": direction, "evidence_sha256": sha256(mr).hexdigest(),
        "data_cutoff_utc": utc_text(now - timedelta(minutes=5)),
        "created_at_utc": utc_text(now),
        "target_start_utc": target["start_at_utc"],
        "target_end_utc": target["end_at_utc"],
    }
    return f, m


def call(f, m, now=FRIDAY):
    return candidate(
        forecast_raw=raw(f), macro_raw=raw(m), as_of_utc=now)


class ManualForwardTrialTests(unittest.TestCase):
    def assert_never_operational(self, out):
        self.assertEqual(out["schema"], SCHEMA)
        for key in (
            "candidate_external_precommit_witnessed",
            "candidate_macroeconomic_data_original_source_authenticated",
            "candidate_macro_publication_times_verified",
            "candidate_immutable_algorithm_version_witnessed",
            "candidate_broker_timezone_verified",
            "future_outcome_already_known",
            "future_price_data_verified",
            "trade_authorized", "can_feed_live_radar", "publishable",
            "worker_enabled", "scheduler_enabled",
        ):
            self.assertIs(out[key], False, key)
        self.assertEqual(out["validated_prediction_count"], 0)
        self.assertIsNone(out["validated_accuracy"])
        self.assertIsNone(out["directional_bias"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertIsNone(out["candidate_external_precommit_url"])
        self.assertEqual((out["external_http_requests"], out["new_cost_brl"]), (0, 0))

    def test_friday_plans_next_sunday_d1_and_w1_session(self):
        out = plan(as_of_utc=FRIDAY)
        self.assertEqual(out["state"], "LAB_FUTURE_SESSION_WINDOWS_PLANNED_NO_FORECAST")
        self.assertEqual(out["pairs_covered"], 28)
        self.assertEqual(out["planned_trial_slots"], 56)
        self.assertEqual(set(out["eligible_pairs"]), set(OFFICIAL_PAIRS))
        daily = out["horizon_windows"]["D1"]
        weekly = out["horizon_windows"]["W1"]
        self.assertEqual(daily["start_at_utc"], "2026-11-08T22:00:00Z")
        self.assertEqual(daily["end_at_utc"], "2026-11-09T22:00:00Z")
        self.assertEqual(daily["precommit_deadline_utc"], "2026-11-08T21:00:00Z")
        self.assertEqual(weekly["start_at_utc"], "2026-11-08T22:00:00Z")
        self.assertEqual(weekly["end_at_utc"], "2026-11-13T22:00:00Z")
        self.assertEqual(MIN_LEAD_MINUTES, 60)
        self.assertFalse(daily["prediction_supplied"])
        self.assertFalse(weekly["external_timestamp_witnessed"])
        self.assert_never_operational(out)

    def test_edt_october_rollover_differs_from_est_november(self):
        start = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
        out = plan(as_of_utc=start)
        self.assertEqual(out["horizon_windows"]["D1"]["start_at_utc"],
                         "2026-10-26T21:00:00Z")
        self.assertEqual(out["horizon_windows"]["W1"]["start_at_utc"],
                         "2026-11-01T22:00:00Z")
        self.assert_never_operational(out)

    def test_spring_dst_transition_is_not_fixed_utc_offset(self):
        now = datetime(2027, 3, 12, 13, 0, tzinfo=timezone.utc)
        r = plan(as_of_utc=now)
        self.assertEqual(r["horizon_windows"]["D1"]["start_at_utc"],
                         "2027-03-14T21:00:00Z")
        self.assertEqual(r["horizon_windows"]["W1"]["start_at_utc"],
                         "2027-03-14T21:00:00Z")
        self.assertEqual(r["horizon_windows"]["W1"]["end_at_utc"],
                         "2027-03-19T21:00:00Z")

    def test_one_hour_precommit_margin_skips_close_session(self):
        now = datetime(2026, 11, 8, 21, 30, tzinfo=timezone.utc)
        r = plan(as_of_utc=now)
        self.assertEqual(r["horizon_windows"]["D1"]["start_at_utc"],
                         "2026-11-09T22:00:00Z")
        self.assertEqual(r["horizon_windows"]["W1"]["start_at_utc"],
                         "2026-11-15T22:00:00Z")
        self.assert_never_operational(r)

    def test_exact_one_hour_until_start_is_allowed(self):
        now = datetime(2026, 11, 8, 21, 0, tzinfo=timezone.utc)
        r = plan(as_of_utc=now)
        self.assertEqual(r["horizon_windows"]["D1"]["start_at_utc"],
                         "2026-11-08T22:00:00Z")

    def test_friday_saturday_do_not_create_new_daily_trading_candle(self):
        for now in (
            datetime(2026, 11, 6, 23, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc),
        ):
            r = plan(as_of_utc=now)
            self.assertEqual(r["horizon_windows"]["D1"]["start_at_utc"],
                             "2026-11-08T22:00:00Z")

    def test_naive_and_invalid_now_are_blocked(self):
        for when in (datetime(2026, 11, 6, 12, 50), None, "", 1, {}):
            r = plan(as_of_utc=when)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["planned_trial_slots"], 0)
            self.assert_never_operational(r)

    def test_candidate_hash_binds_exact_macro_bytes_for_manual_review(self):
        f, m = fixtures()
        r = call(f, m)
        self.assertEqual(r["state"],
                         "LAB_FORWARD_CANDIDATE_HASH_BOUND_AWAITING_EXTERNAL_WITNESS")
        self.assertTrue(r["candidate_structurally_preparable"])
        self.assertEqual(r["candidate_pair"], "EUR/USD")
        self.assertEqual(r["candidate_horizon"], "D1")
        self.assertEqual(r["candidate_direction_claim"], "ALTA")
        self.assertFalse(r["candidate_is_abstention"])
        self.assertEqual(r["candidate_forecast_sha256"], sha256(raw(f)).hexdigest())
        self.assertEqual(r["candidate_macro_sha256"], sha256(raw(m)).hexdigest())
        self.assert_never_operational(r)

    def test_each_of_28_pairs_can_make_unwitnessed_lab_candidate(self):
        self.assertEqual(len(OFFICIAL_PAIRS), 28)
        for pair in OFFICIAL_PAIRS:
            f, m = fixtures(pair=pair)
            r = call(f, m)
            self.assertEqual(r["candidate_pair"], pair)
            self.assertEqual(r["state"],
                             "LAB_FORWARD_CANDIDATE_HASH_BOUND_AWAITING_EXTERNAL_WITNESS")
            self.assert_never_operational(r)

    def test_weekly_forward_candidate_is_not_historical_accuracy(self):
        f, m = fixtures(horizon="W1")
        r = call(f, m)
        self.assertEqual(r["candidate_horizon"], "W1")
        self.assertTrue(r["candidate_structurally_preparable"])
        self.assert_never_operational(r)

    def test_neutral_candidate_is_explicit_abstention_not_win(self):
        f, m = fixtures(direction="NEUTRO")
        r = call(f, m)
        self.assertTrue(r["candidate_is_abstention"])
        self.assertEqual(r["candidate_direction_claim"], "NEUTRO")
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assert_never_operational(r)

    def test_wrong_macro_bytes_hash_rejected(self):
        f, m = fixtures()
        m["records"][0]["value"] = "2.7"
        r = call(f, m)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["reason"],
                         "FORECAST_MACRO_EVIDENCE_CHAIN_INCOMPLETE_OR_INCONSISTENT")
        self.assert_never_operational(r)

    def test_macro_from_other_pair_rejected(self):
        f, _ = fixtures(pair="EUR/USD")
        _, m = fixtures(pair="GBP/USD")
        f["evidence_sha256"] = sha256(raw(m)).hexdigest()
        r = call(f, m)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_never_operational(r)

    def test_macro_capture_after_cutoff_must_not_enter_forward_decision(self):
        f, m = fixtures()
        m["records"][0]["published_at_utc"] = "2026-11-06T12:44:00Z"
        m["records"][0]["captured_at_utc"] = "2026-11-06T12:47:00Z"
        f["evidence_sha256"] = sha256(raw(m)).hexdigest()
        r = call(f, m)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_never_operational(r)

    def test_future_macroeconomic_release_is_blocked(self):
        f, m = fixtures()
        m["records"][0]["published_at_utc"] = "2026-11-06T12:51:00Z"
        m["records"][0]["captured_at_utc"] = "2026-11-06T12:52:00Z"
        f["evidence_sha256"] = sha256(raw(m)).hexdigest()
        r = call(f, m)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_never_operational(r)

    def test_missing_macro_indicator_prevents_candidate(self):
        f, m = fixtures()
        m["records"] = [x for x in m["records"]
                        if not (x["currency"] == "USD"
                                and x["indicator"] == "CPI_YOY")]
        f["evidence_sha256"] = sha256(raw(m)).hexdigest()
        r = call(f, m)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_never_operational(r)

    def test_old_claimed_creation_timestamp_rejected_even_if_before_session(self):
        f, m = fixtures()
        f["created_at_utc"] = "2026-11-06T12:44:00Z"
        f["data_cutoff_utc"] = "2026-11-06T12:40:00Z"
        m["decision_at_utc"] = f["created_at_utc"]
        f["evidence_sha256"] = sha256(raw(m)).hexdigest()
        r = call(f, m)
        self.assertEqual(r["reason"],
                         "FORECAST_CREATION_CLAIM_NOT_NEAR_MANUAL_AUDIT")
        self.assert_never_operational(r)

    def test_future_claimed_creation_timestamp_rejected(self):
        f, m = fixtures()
        f["created_at_utc"] = "2026-11-06T12:51:00Z"
        m["decision_at_utc"] = f["created_at_utc"]
        f["evidence_sha256"] = sha256(raw(m)).hexdigest()
        r = call(f, m)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_never_operational(r)

    def test_forecast_for_expired_session_not_next_forward_window(self):
        f, m = fixtures()
        f["target_start_utc"] = "2026-11-01T22:00:00Z"
        f["target_end_utc"] = "2026-11-02T22:00:00Z"
        r = call(f, m)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_never_operational(r)

    def test_invalid_forecast_or_non_utc_asof_rejected(self):
        _, m = fixtures()
        for f in (b"", b"not json", b"{}"):
            r = candidate(forecast_raw=f, macro_raw=raw(m), as_of_utc=FRIDAY)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_never_operational(r)
        f, m = fixtures()
        r = call(f, m, now=FRIDAY.replace(tzinfo=None))
        self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_different_broker_m15_or_future_outcome_never_required_for_precommit(self):
        f, m = fixtures()
        r = call(f, m)
        self.assertFalse(r["future_outcome_already_known"])
        self.assertFalse(r["future_price_data_verified"])
        self.assertIsNone(r["validated_accuracy"])
        self.assert_never_operational(r)

    def test_output_contains_no_real_signals_or_verified_macro_measurement(self):
        f, m = fixtures()
        r = call(f, m)
        serialized = json.dumps(r)
        self.assertNotIn('"value"', serialized)
        self.assertNotIn('"buy"', serialized.lower())
        self.assertNotIn('"sell"', serialized.lower())
        self.assertFalse(r["candidate_macro_publication_times_verified"])
        self.assert_never_operational(r)

    def test_unknown_direction_is_not_accepted_as_strategy(self):
        f, m = fixtures(direction="COMPRAR")
        r = call(f, m)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_never_operational(r)

    def test_forecast_macro_decision_mismatch_blocks_packet(self):
        f, m = fixtures()
        m["decision_at_utc"] = "2026-11-06T12:49:00Z"
        f["evidence_sha256"] = sha256(raw(m)).hexdigest()
        r = call(f, m)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_never_operational(r)


if __name__ == "__main__":
    unittest.main()
