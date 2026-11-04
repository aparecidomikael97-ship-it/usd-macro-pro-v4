"""Synthetic PIT macro surprise tests; no claim of real market prediction."""
import copy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_bias_forecast_bridge_lab import (
    SCHEMA as BATCH_SCHEMA, FIXED_METHOD,
)
from atlasquant_trader_bias_daily_freeze_lab import (
    freeze_daily_bias_observation_lab,
    VETO_POLICY_ID,
)
from atlasquant_trader_macro_surprise_pit_lab import (
    SCHEMA, build_macro_point_in_time_evidence_lab,
)

FORECAST = datetime(2026, 11, 2, 11, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 2, 18, tzinfo=timezone.utc)
EXPECTED = "2026-10-30T12:00:00+00:00"
RELEASED = "2026-10-30T14:00:00+00:00"


def pre(*, future=False):
    return {
        "state": "LAB_SYNTHETIC_MACRO_PRE",
        "event_id": "US-CPI-202610", "currency": "USD",
        "indicator_id": "CPI", "unit": "PERCENT",
        "source": "Sintetico Calendario",
        "previous": 2.8, "previous_captured_at_utc": "2026-10-29T11:00:00+00:00",
        "consensus": 3.0, "consensus_captured_at_utc": EXPECTED,
        "scheduled_release_at_utc": (
            "2026-11-02T14:00:00+00:00" if future else RELEASED
        ),
        "deadband_predeclared": 0.1,
    }


def actual(*, value=3.3):
    return {
        "state": "LAB_SYNTHETIC_MACRO_ACTUAL",
        "event_id": "US-CPI-202610", "actual": value,
        "released_at_utc": RELEASED,
        "captured_at_utc": "2026-10-30T14:05:00+00:00",
        "source": "Sintetico Boletim",
    }


def evaluate(snapshot=None, result=None, *, forecast_at=FORECAST, eval_at=NOW):
    return build_macro_point_in_time_evidence_lab(
        pre() if snapshot is None else snapshot, result,
        forecast_issued_at=forecast_at, evaluated_at=eval_at,
    )


def canonical_batch():
    key = "macro-surprise-1"
    forecasts = []
    for pair in OFFICIAL_PAIRS:
        for horizon in ("D1", "W1", "MN1"):
            forecasts.append({
                "forecast_id": f"{key}-{horizon}-{pair.replace('/', '')}",
                "state": "LAB_SYNTHETIC_BIAS", "pair": pair,
                "horizon": horizon, "bias": "ALTA",
                "method_id": FIXED_METHOD,
                "issued_at_utc": FORECAST.isoformat(),
                "evidence_at_utc": "2026-11-02T10:30:00+00:00",
                "trade_authorized": False,
            })
    return {
        "schema": BATCH_SCHEMA, "state": "LAB_SYNTHETIC_ISSUED",
        "method_id": FIXED_METHOD,
        "batch_key": key, "issued_at_utc": FORECAST.isoformat(),
        "forecasts": forecasts,
    }


def strength_evidence():
    return {
        "state": "LAB_SYNTHETIC_EVIDENCE", "kind": "G8_STRENGTH_REFERENCE",
        "evidence_id": "g8-strength", "source": "Sintetico Referencia",
        "currencies": list(CURRENCIES),
        "data_as_of_utc": "2026-11-02T10:00:00+00:00",
        "captured_at_utc": "2026-11-02T10:30:00+00:00",
    }


class MacroSurprisePointInTimeLabTests(unittest.TestCase):
    def test_released_event_splits_previous_consensus_actual(self):
        out = evaluate(result=actual())
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "LAB_MACRO_RELEASED_SYNTHETIC")
        ev = out["freeze_evidence"]
        self.assertEqual(ev["previous"], 2.8)
        self.assertEqual(ev["consensus"], 3.0)
        self.assertEqual(ev["actual"], 3.3)
        self.assertEqual(ev["kind"], "MACRO_ACTUAL_RELEASED")
        self.assertAlmostEqual(out["surprise"], 0.3)
        self.assertEqual(out["surprise_comparison"], "ABOVE_CONSENSUS")

    def test_below_and_inline_classification_does_not_pick_currency_direction(self):
        below = evaluate(result=actual(value=2.4))
        inline = evaluate(result=actual(value=3.05))
        self.assertEqual(below["surprise_comparison"], "BELOW_CONSENSUS")
        self.assertEqual(inline["surprise_comparison"], "IN_LINE_WITH_CONSENSUS")
        self.assertEqual(below["macro_currency_direction"], "UNDETERMINED")
        self.assertEqual(inline["freeze_evidence"]["market_impact_direction"], "UNDETERMINED")

    def test_deadband_changes_only_when_committed_pre_release(self):
        s = pre(); s["deadband_predeclared"] = 0.35
        self.assertEqual(evaluate(s, actual())["surprise_comparison"],
                         "IN_LINE_WITH_CONSENSUS")
        self.assertFalse(evaluate(s, actual())["predictive_edge_proven"])

    def test_actual_absent_before_release_only_schedule_is_permitted(self):
        out = evaluate(snapshot=pre(future=True))
        self.assertEqual(out["state"], "LAB_MACRO_FUTURE_SCHEDULE_ONLY")
        self.assertIsNone(out["surprise"])
        self.assertNotIn("actual", out["freeze_evidence"])
        self.assertNotIn("surprise", out["freeze_evidence"])
        self.assertEqual(out["freeze_evidence"]["kind"], "MACRO_SCHEDULE_ONLY")

    def test_actual_absent_after_planned_release_is_not_fabricated(self):
        out = evaluate(snapshot=pre())
        self.assertEqual(out["state"], "LAB_MACRO_EVENT_REJECTED")
        self.assertIsNone(out["freeze_evidence"])

    def test_future_actual_supplied_for_morning_issue_is_rejected(self):
        snapshot = pre(future=True)
        a = actual()
        a["released_at_utc"] = "2026-11-02T14:00:00+00:00"
        a["captured_at_utc"] = "2026-11-02T14:01:00+00:00"
        out = evaluate(snapshot, a)
        self.assertEqual(out["state"], "LAB_MACRO_EVENT_REJECTED")
        self.assertIsNone(out["freeze_evidence"])

    def test_release_known_but_captured_after_forecast_cannot_enter(self):
        a = actual()
        a["captured_at_utc"] = "2026-11-02T11:00:01+00:00"
        self.assertEqual(evaluate(result=a)["state"], "LAB_MACRO_EVENT_REJECTED")

    def test_previous_captured_after_consensus_rejected(self):
        snapshot = pre()
        snapshot["previous_captured_at_utc"] = "2026-10-30T13:00:00+00:00"
        self.assertEqual(evaluate(snapshot, actual())["state"], "LAB_MACRO_EVENT_REJECTED")

    def test_consensus_capture_after_release_rejected(self):
        snapshot = pre()
        snapshot["consensus_captured_at_utc"] = "2026-10-30T14:01:00+00:00"
        self.assertEqual(evaluate(snapshot, actual())["state"], "LAB_MACRO_EVENT_REJECTED")

    def test_consensus_capture_after_forecast_rejected(self):
        snapshot = pre(future=True)
        snapshot["consensus_captured_at_utc"] = "2026-11-02T11:00:01+00:00"
        self.assertEqual(evaluate(snapshot)["state"], "LAB_MACRO_EVENT_REJECTED")

    def test_released_actual_must_not_precede_consensus_capture(self):
        a = actual()
        a["released_at_utc"] = "2026-10-30T11:59:00+00:00"
        self.assertEqual(evaluate(result=a)["state"], "LAB_MACRO_EVENT_REJECTED")

    def test_release_materially_changed_from_schedule_is_quarantined(self):
        a = actual()
        a["released_at_utc"] = "2026-10-28T14:00:00+00:00"
        self.assertEqual(evaluate(result=a)["state"], "LAB_MACRO_EVENT_REJECTED")
        a = actual()
        a["released_at_utc"] = "2026-11-02T14:00:00+00:00"
        self.assertEqual(evaluate(result=a)["state"], "LAB_MACRO_EVENT_REJECTED")

    def test_wrong_event_id_does_not_match_consensus_snapshot(self):
        a = actual()
        a["event_id"] = "JPY-NFP-OTHER"
        self.assertEqual(evaluate(result=a)["state"], "LAB_MACRO_EVENT_REJECTED")

    def test_forecast_after_evaluation_is_invalid(self):
        early = datetime(2026, 11, 1, 11, tzinfo=timezone.utc)
        self.assertEqual(evaluate(result=actual(), eval_at=early)["state"],
                         "LAB_MACRO_EVENT_REJECTED")

    def test_forecast_and_evaluation_require_timezone(self):
        with self.assertRaises(ValueError):
            evaluate(result=actual(), forecast_at=datetime(2026, 11, 2, 11))
        with self.assertRaises(ValueError):
            evaluate(result=actual(), eval_at=datetime(2026, 11, 2, 18))

    def test_invalid_currency_indicator_or_unit_is_rejected(self):
        for field, value in (
            ("currency", "BRL"), ("currency", []),
            ("indicator_id", "MYSTERY"), ("indicator_id", {"x": 1}),
            ("unit", "FLORINS"), ("unit", []),
            ("event_id", "bad/unsafe"),
        ):
            snapshot = pre()
            snapshot[field] = value
            self.assertEqual(evaluate(snapshot, actual())["state"],
                             "LAB_MACRO_EVENT_REJECTED", field)

    def test_numeric_boolean_nonfinite_overflow_and_string_rejected(self):
        for field in ("previous", "consensus", "deadband_predeclared"):
            for value in (True, float("nan"), float("inf"), 10**2000, "3.0"):
                snapshot = pre(); snapshot[field] = value
                self.assertEqual(evaluate(snapshot, actual())["state"],
                                 "LAB_MACRO_EVENT_REJECTED")
        for value in (True, float("nan"), float("-inf"), 10**2000, "3.3"):
            self.assertEqual(evaluate(result=actual(value=value))["state"],
                             "LAB_MACRO_EVENT_REJECTED")

    def test_negative_deadband_is_not_permitted(self):
        snapshot = pre()
        snapshot["deadband_predeclared"] = -0.1
        self.assertEqual(evaluate(snapshot, actual())["state"],
                         "LAB_MACRO_EVENT_REJECTED")

    def test_extra_future_fields_in_consensus_are_blocked(self):
        snapshot = pre()
        snapshot["actual"] = 3.3
        self.assertEqual(evaluate(snapshot, actual())["state"],
                         "LAB_MACRO_EVENT_REJECTED")

    def test_extra_forecast_direction_field_in_release_is_blocked(self):
        a = actual()
        a["buy_usd"] = True
        self.assertEqual(evaluate(result=a)["state"], "LAB_MACRO_EVENT_REJECTED")

    def test_missing_or_wrong_state_is_refused(self):
        self.assertEqual(evaluate({})["state"], "LAB_MACRO_EVENT_REJECTED")
        snapshot = pre()
        snapshot["state"] = "REAL_PROVIDER_MACRO"
        self.assertEqual(evaluate(snapshot, actual())["state"],
                         "LAB_MACRO_EVENT_REJECTED")

    def test_no_real_data_or_trade_authorization_even_when_valid(self):
        for out in (evaluate(result=actual()),
                    evaluate(snapshot=pre(future=True))):
            for field in ("provider_attested", "immutable_receipt_attested",
                          "real_macro_history_verified", "predictive_edge_proven",
                          "trade_authorized", "worker_enabled", "scheduler_enabled"):
                self.assertFalse(out[field], field)

    def test_released_evidence_is_accepted_by_existing_daily_freeze(self):
        macro = evaluate(result=actual())
        ev = [strength_evidence(), macro["freeze_evidence"]]
        frozen = freeze_daily_bias_observation_lab(
            canonical_batch(), ev, checked_at=NOW)
        self.assertEqual(frozen["state"], "LAB_FROZEN_SYNTHETIC_OBSERVATION")
        self.assertEqual(frozen["macro_actuals_before_cutoff"], 1)
        self.assertFalse(frozen["real_historical_capture_verified"])

    def test_future_schedule_is_accepted_without_actual_in_daily_freeze(self):
        ev = [strength_evidence(),
              evaluate(snapshot=pre(future=True))["freeze_evidence"]]
        frozen = freeze_daily_bias_observation_lab(
            canonical_batch(), ev, checked_at=NOW)
        self.assertEqual(frozen["state"], "LAB_FROZEN_SYNTHETIC_OBSERVATION")
        self.assertEqual(frozen["macro_future_schedules_without_actual"], 1)
        self.assertEqual(frozen["macro_actuals_before_cutoff"], 0)

    def test_released_macro_can_support_only_predeclared_d1_veto(self):
        macro_ev = evaluate(result=actual())["freeze_evidence"]
        plan = [{
            "state": "LAB_SYNTHETIC_MACRO_VETO",
            "policy_id": VETO_POLICY_ID,
            "forecast_id": "macro-surprise-1-D1-USDJPY",
            "decided_at_utc": FORECAST.isoformat(),
            "evidence_ids": [macro_ev["evidence_id"]],
            "rationale": "Risco hipotetico USD antes do corte, nao sinal de compra",
            "trade_authorized": False,
        }]
        frozen = freeze_daily_bias_observation_lab(
            canonical_batch(), [strength_evidence(), macro_ev],
            checked_at=NOW, macro_vetoes=plan)
        self.assertEqual(frozen["state"], "LAB_FROZEN_SYNTHETIC_OBSERVATION")
        self.assertEqual(frozen["predeclared_macro_vetoes"], 1)
        self.assertFalse(frozen["digest_is_independent_custody"])

    def test_future_scheduled_macro_cannot_support_actual_veto(self):
        ev = evaluate(snapshot=pre(future=True))["freeze_evidence"]
        plan = [{
            "state": "LAB_SYNTHETIC_MACRO_VETO",
            "policy_id": VETO_POLICY_ID,
            "forecast_id": "macro-surprise-1-D1-USDJPY",
            "decided_at_utc": FORECAST.isoformat(),
            "evidence_ids": [ev["evidence_id"]],
            "rationale": "Risco hipotetico USD antes do corte, nao sinal de compra",
            "trade_authorized": False,
        }]
        frozen = freeze_daily_bias_observation_lab(
            canonical_batch(), [strength_evidence(), ev], checked_at=NOW,
            macro_vetoes=plan)
        self.assertEqual(frozen["state"], "LAB_REJECTED_DAILY_OBSERVATION")


if __name__ == "__main__":
    unittest.main()
