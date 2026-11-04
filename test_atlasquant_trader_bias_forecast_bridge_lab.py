"""Synthetic-only integration tests: G8 strength -> 84 forecast stamps -> OOS."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from math import exp

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_bias_forecast_bridge_lab import (
    SCHEMA, FIXED_METHOD, issue_synthetic_bias_batch_lab,
    evaluate_synthetic_bias_batches_lab,
)

AT = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)
SPLIT = datetime(2026, 8, 1, tzinfo=timezone.utc)
SCORING_AT = AT


def books(at=AT, monthly_reverse=False, weekly_reverse=False):
    out = {}
    for h, days in (("D1", 1), ("W1", 7), ("MN1", 30)):
        observed = at - timedelta(hours=1)
        end = at - timedelta(hours=2)
        start = end - timedelta(days=days)
        factors = {code: 0.0 for code in CURRENCIES}
        factors["USD"], factors["JPY"] = (
            (80.0, -80.0) if h == "D1" else
            (220.0, -200.0) if h == "W1" else (450.0, -400.0))
        if (h == "MN1" and monthly_reverse) or (h == "W1" and weekly_reverse):
            factors["USD"] *= -1
            factors["JPY"] *= -1
        pairs = {}
        for p in OFFICIAL_PAIRS:
            base, quote = split_pair(p)
            pairs[p] = {
                "start": 100.0, "end": 100.0 * exp((factors[base] - factors[quote]) / 10000.0),
                "source": "LAB-fixtures", "start_at": start.isoformat(),
                "end_at": end.isoformat(),
            }
        out[h] = {
            "state": "LAB_SYNTHETIC_SPOT", "data_kind": "SYNTHETIC_FX_SPOT_CLOSES",
            "source": "LAB-fixtures", "as_of": observed.isoformat(),
            "period_end": end.date().isoformat(), "pairs": pairs,
        }
    return out


def issue(at=AT, key="lab-run-1", data=None):
    return issue_synthetic_bias_batch_lab(books(at) if data is None else data,
                                          at=at, batch_key=key)


def forecast(batch, pair="USD/JPY", horizon="D1"):
    return next(x for x in batch["forecasts"]
                if x["pair"] == pair and x["horizon"] == horizon)


def settlements_for(batch):
    out = []
    for forecast_row in batch["forecasts"]:
        time = datetime.fromisoformat(forecast_row["issued_at_utc"])
        entry = time + timedelta(days=1)
        exit_at = entry + timedelta(days={"D1": 1, "W1": 7, "MN1": 30}[forecast_row["horizon"]])
        out.append({
            "state": "LAB_SYNTHETIC_SPOT_OUTCOME",
            "forecast_id": forecast_row["forecast_id"],
            "pair": forecast_row["pair"], "entry_at_utc": entry.isoformat(),
            "exit_at_utc": exit_at.isoformat(), "entry_price": 100.0,
            "exit_price": 100.0 * exp(10 / 10000),
        })
    return out


def chron_batches():
    times = [
        datetime(2026, 6, 1, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 5, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 10, 12, tzinfo=timezone.utc),
        datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
        datetime(2026, 9, 5, 12, tzinfo=timezone.utc),
        datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
    ]
    return [issue(at=t, key=f"batch-{i+1}") for i, t in enumerate(times)]


class BiasBridgeLabTests(unittest.TestCase):
    def test_issues_84_without_future_outcome_input(self):
        b = issue()
        self.assertEqual(b["schema"], SCHEMA)
        self.assertEqual(len(b["forecasts"]), 84)
        self.assertEqual(len({f["forecast_id"] for f in b["forecasts"]}), 84)
        self.assertEqual({f["pair"] for f in b["forecasts"]}, set(OFFICIAL_PAIRS))
        self.assertEqual({f["horizon"] for f in b["forecasts"]}, {"D1", "W1", "MN1"})
        self.assertTrue(b["no_settlements_seen_by_issuer"])
        self.assertFalse(b["durable_provenance_verified"])

    def test_daily_priority_uses_weekly_confirmation(self):
        b = issue()
        d = forecast(b)
        self.assertEqual(d["bias"], "ALTA")
        self.assertEqual(forecast(b, horizon="W1")["bias"], "ALTA")
        self.assertEqual(forecast(b, horizon="MN1")["bias"], "ALTA")
        self.assertEqual(d["method_id"], FIXED_METHOD)
        self.assertEqual(d["evidence_kind"], "SYNTHETIC_INPUT")

    def test_weekly_conflict_stops_daily_but_keeps_weekly_as_own_horizon(self):
        b = issue(data=books(weekly_reverse=True))
        self.assertEqual(forecast(b)["bias"], "AGUARDAR")
        self.assertEqual(forecast(b, horizon="W1")["bias"], "BAIXA")
        self.assertFalse(forecast(b)["trade_authorized"])

    def test_monthly_opposition_keeps_daily_and_weekly_and_exposes_monthly(self):
        b = issue(data=books(monthly_reverse=True))
        self.assertEqual(forecast(b)["bias"], "ALTA")
        self.assertEqual(forecast(b, horizon="MN1")["bias"], "BAIXA")

    def test_missing_weekly_abstains_daily_without_fabricating_evidence(self):
        data = books()
        del data["W1"]
        b = issue(data=data)
        d = forecast(b)
        self.assertEqual(d["bias"], "AGUARDAR")
        self.assertEqual(forecast(b, horizon="W1")["bias"], "AGUARDAR")
        self.assertEqual(d["evidence_kind"], "SYNTHETIC_INPUT")
        self.assertEqual(forecast(b, horizon="W1")["evidence_kind"], "ABSENT_POLICY")

    def test_missing_daily_cannot_issue_d1_direction(self):
        data = books()
        del data["D1"]
        b = issue(data=data)
        self.assertEqual(forecast(b)["bias"], "AGUARDAR")
        self.assertEqual(forecast(b)["evidence_kind"], "ABSENT_POLICY")
        self.assertEqual(forecast(b, horizon="W1")["bias"], "ALTA")

    def test_entirely_missing_market_data_is_all_wait_not_random_side(self):
        b = issue(data={})
        self.assertEqual(b["counts"]["D1"]["AGUARDAR"], 28)
        self.assertEqual(b["counts"]["W1"]["AGUARDAR"], 28)
        self.assertEqual(b["counts"]["MN1"]["AGUARDAR"], 28)

    def test_future_weekly_stamp_cannot_be_used_for_daily(self):
        data = books()
        data["W1"]["as_of"] = (AT + timedelta(minutes=2)).isoformat()
        b = issue(data=data)
        self.assertEqual(forecast(b)["bias"], "AGUARDAR")

    def test_evidence_is_before_or_equal_issuance_for_all_forecasts(self):
        b = issue()
        for row in b["forecasts"]:
            self.assertLessEqual(
                datetime.fromisoformat(row["evidence_at_utc"]),
                datetime.fromisoformat(row["issued_at_utc"]))
            self.assertEqual(row["state"], "LAB_SYNTHETIC_BIAS")

    def test_duplicate_batch_key_is_rejected_before_scoring(self):
        b = issue()
        with self.assertRaises(ValueError):
            evaluate_synthetic_bias_batches_lab(
                [b, b], [], split_at=SPLIT, at=SCORING_AT,
                min_train=3, min_test=3, min_test_days=3)

    def test_same_instant_cannot_be_counted_twice_under_different_keys(self):
        first, second = issue(key="first"), issue(key="second")
        with self.assertRaises(ValueError):
            evaluate_synthetic_bias_batches_lab(
                [first, second], [], split_at=SPLIT, at=SCORING_AT,
                min_train=3, min_test=3, min_test_days=3)

    def test_out_of_order_batches_rejected(self):
        batch = chron_batches()
        with self.assertRaises(ValueError):
            evaluate_synthetic_bias_batches_lab(
                list(reversed(batch)), [], split_at=SPLIT, at=SCORING_AT,
                min_train=3, min_test=3, min_test_days=3)

    def test_missing_pair_horizon_in_batch_rejected(self):
        batch = issue()
        batch["forecasts"].pop()
        with self.assertRaises(ValueError):
            evaluate_synthetic_bias_batches_lab(
                [batch], [], split_at=SPLIT, at=SCORING_AT,
                min_train=3, min_test=3, min_test_days=3)

    def test_renamed_forecast_id_rejected(self):
        batch = issue()
        batch["forecasts"][0]["forecast_id"] = "renamed-fake"
        with self.assertRaises(ValueError):
            evaluate_synthetic_bias_batches_lab(
                [batch], [], split_at=SPLIT, at=SCORING_AT,
                min_train=3, min_test=3, min_test_days=3)

    def test_reject_naive_issue_time_and_wrong_key(self):
        with self.assertRaises(ValueError):
            issue(at=datetime(2026, 11, 2, 15))
        with self.assertRaises(ValueError):
            issue(key="../../unsafe")

    def test_e2e_synthetic_oos_keeps_real_proof_flags_false(self):
        batches = chron_batches()
        settlements = [item for batch in batches for item in settlements_for(batch)]
        out = evaluate_synthetic_bias_batches_lab(
            batches, settlements, split_at=SPLIT, at=SCORING_AT,
            min_train=3, min_test=3, min_test_days=3)
        self.assertEqual(out["state"], "LAB_SYNTHETIC_EVALUATION_ONLY")
        self.assertEqual(out["batch_count"], 6)
        self.assertEqual(out["forecast_count"], 504)
        self.assertEqual(out["evaluation"]["state"], "LAB_SYNTHETIC_HOLDOUT_ONLY")
        self.assertEqual(len(out["evaluation"]["pair_metrics"]), 28)
        self.assertFalse(out["oos_real_proven"])
        self.assertFalse(out["historical_prices_verified"])
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["scheduler_enabled"])

    def test_e2e_missing_settlement_rejected_instead_of_cherry_picking(self):
        batches = chron_batches()
        settlements = [item for batch in batches for item in settlements_for(batch)]
        settlements.pop()
        out = evaluate_synthetic_bias_batches_lab(
            batches, settlements, split_at=SPLIT, at=SCORING_AT,
            min_train=3, min_test=3, min_test_days=3)
        self.assertEqual(out["evaluation"]["state"], "INVALID_OR_INCOMPLETE_FIXTURE")
        self.assertFalse(out["oos_real_proven"])

    def test_e2e_future_entry_is_rejected(self):
        batches = chron_batches()
        settlements = [item for batch in batches for item in settlements_for(batch)]
        settlements[0]["entry_at_utc"] = "2026-11-10T00:00:00+00:00"
        out = evaluate_synthetic_bias_batches_lab(
            batches, settlements, split_at=SPLIT, at=SCORING_AT,
            min_train=3, min_test=3, min_test_days=3)
        self.assertEqual(out["evaluation"]["state"], "INVALID_OR_INCOMPLETE_FIXTURE")


class BridgeBatchAuthenticityTests(unittest.TestCase):
    """Caller-controlled result batches may not claim verified market evidence."""

    def assert_rejected(self, b):
        with self.assertRaises(ValueError):
            evaluate_synthetic_bias_batches_lab(
                [b], [], split_at=SPLIT, at=SCORING_AT,
                min_train=3, min_test=3, min_test_days=3,
            )

    def test_normal_issuer_fields_still_accepted(self):
        out = evaluate_synthetic_bias_batches_lab(
            [issue()], [], split_at=SPLIT, at=SCORING_AT,
            min_train=3, min_test=3, min_test_days=3,
        )
        self.assertEqual(out["state"], "LAB_SYNTHETIC_EVALUATION_ONLY")
        self.assertFalse(out["oos_real_proven"])

    def test_forged_batch_market_verified_blocked(self):
        b = issue()
        b["market_data_verified"] = True
        self.assert_rejected(b)

    def test_forged_batch_durable_provenance_blocked(self):
        b = issue()
        b["durable_provenance_verified"] = True
        self.assert_rejected(b)

    def test_forged_batch_worker_blocked(self):
        b = issue()
        b["worker_enabled"] = True
        self.assert_rejected(b)

    def test_forged_batch_scheduler_blocked(self):
        b = issue()
        b["scheduler_enabled"] = True
        self.assert_rejected(b)

    def test_batch_false_no_settlement_flag_blocked(self):
        b = issue()
        b["no_settlements_seen_by_issuer"] = False
        self.assert_rejected(b)

    def test_extra_batch_probability_field_blocked(self):
        b = issue()
        b["claimed_accuracy_probability"] = 0.99
        self.assert_rejected(b)

    def test_missing_batch_counts_blocked(self):
        b = issue()
        del b["counts"]
        self.assert_rejected(b)

    def test_forged_batch_counts_blocked(self):
        b = issue()
        b["counts"]["D1"]["ALTA"] += 1
        self.assert_rejected(b)

    def test_forged_row_market_verified_blocked(self):
        b = issue()
        b["forecasts"][0]["market_verified"] = True
        self.assert_rejected(b)

    def test_extra_row_probability_field_blocked(self):
        b = issue()
        b["forecasts"][0]["probability_90_pct"] = 0.9
        self.assert_rejected(b)

    def test_row_missing_provenance_field_blocked(self):
        b = issue()
        del b["forecasts"][0]["market_verified"]
        self.assert_rejected(b)

    def test_row_fake_evidence_kind_blocked(self):
        b = issue()
        b["forecasts"][0]["evidence_kind"] = "LIVE_BROKER_CERTIFIED"
        self.assert_rejected(b)

    def test_row_future_evidence_time_blocked(self):
        b = issue()
        b["forecasts"][0]["evidence_at_utc"] = (
            AT + timedelta(days=1)).isoformat()
        self.assert_rejected(b)

    def test_absent_evidence_cannot_have_direction(self):
        b = issue()
        b["forecasts"][0]["evidence_kind"] = "ABSENT_POLICY"
        self.assert_rejected(b)

    def test_absent_evidence_must_be_issue_time_abstention(self):
        b = issue(data={})
        b["forecasts"][0]["evidence_at_utc"] = (
            AT - timedelta(seconds=1)).isoformat()
        self.assert_rejected(b)

    def test_missing_reason_rejected(self):
        b = issue()
        b["forecasts"][0]["reason"] = ""
        self.assert_rejected(b)

    def test_long_reason_rejected(self):
        b = issue()
        b["forecasts"][0]["reason"] = "x" * 401
        self.assert_rejected(b)



if __name__ == "__main__":
    unittest.main()
