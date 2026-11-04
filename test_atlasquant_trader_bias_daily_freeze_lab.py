"""LAB-only scheduled research observation tests: 28 pairs x 3 horizons."""
import copy
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_bias_forecast_bridge_lab import (
    SCHEMA as FORECAST_SCHEMA, FIXED_METHOD,
)
from atlasquant_trader_bias_daily_freeze_lab import (
    PROTOCOL, VETO_POLICY_ID, freeze_daily_bias_observation_lab,
)

ISSUED = datetime(2026, 11, 2, 11, tzinfo=timezone.utc)  # 07:00 Cuiaba
CHECKED = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)


def batch(issued=ISSUED):
    key = "freeze-lab-1"
    forecasts = []
    for pair in OFFICIAL_PAIRS:
        for h in ("D1", "W1", "MN1"):
            forecasts.append({
                "forecast_id": f"{key}-{h}-{pair.replace('/', '')}",
                "state": "LAB_SYNTHETIC_BIAS", "pair": pair, "horizon": h,
                "bias": "ALTA", "method_id": FIXED_METHOD,
                "issued_at_utc": issued.isoformat(),
                "evidence_at_utc": (issued - timedelta(minutes=40)).isoformat(),
                "trade_authorized": False,
            })
    return {
        "schema": FORECAST_SCHEMA, "state": "LAB_SYNTHETIC_ISSUED",
        "method_id": FIXED_METHOD, "batch_key": key,
        "issued_at_utc": issued.isoformat(), "forecasts": forecasts,
    }


def evidence():
    return [
        {"state": "LAB_SYNTHETIC_EVIDENCE",
         "evidence_id": "g8-sample", "kind": "G8_STRENGTH_REFERENCE",
         "source": "Laboratorio apenas",
         "data_as_of_utc": "2026-11-02T10:00:00+00:00",
         "captured_at_utc": "2026-11-02T10:30:00+00:00",
         "currencies": list(CURRENCIES)},
        {"state": "LAB_SYNTHETIC_EVIDENCE",
         "evidence_id": "macro-known", "kind": "MACRO_ACTUAL_RELEASED",
         "source": "Laboratorio apenas",
         "currency": "USD",
         "released_at_utc": "2026-11-02T09:45:00+00:00",
         "data_as_of_utc": "2026-11-02T09:45:00+00:00",
         "captured_at_utc": "2026-11-02T10:15:00+00:00",
         "actual": 2.5},
        {"state": "LAB_SYNTHETIC_EVIDENCE",
         "evidence_id": "macro-coming", "kind": "MACRO_SCHEDULE_ONLY",
         "source": "Laboratorio apenas",
         "released_at_utc": "2026-11-02T14:00:00+00:00",
         "data_as_of_utc": "2026-11-02T09:00:00+00:00",
         "captured_at_utc": "2026-11-02T10:10:00+00:00"},
    ]


def check(b=None, e=None, *, at=CHECKED, vetoes=None):
    return freeze_daily_bias_observation_lab(
        batch() if b is None else b,
        evidence() if e is None else e, checked_at=at,
        macro_vetoes=vetoes,
    )


def macro_plan():
    return [{
        "state": "LAB_SYNTHETIC_MACRO_VETO",
        "policy_id": VETO_POLICY_ID,
        "forecast_id": "freeze-lab-1-D1-USDJPY",
        "decided_at_utc": ISSUED.isoformat(),
        "evidence_ids": ["macro-known"],
        "rationale": "Hipotese anterior: evidencia macro gera risco de contrario",
        "trade_authorized": False,
    }]


class DailyFreezeLabTests(unittest.TestCase):
    def test_exactly_84_precommitted_rows_and_same_source_cutoff(self):
        out = check()
        self.assertEqual(out["state"], "LAB_FROZEN_SYNTHETIC_OBSERVATION")
        self.assertEqual(out["forecast_rows"], 84)
        self.assertEqual(out["covered_pairs"], 28)
        self.assertEqual(out["session_label_lab"], "2026-11-02")
        self.assertEqual(out["research_cutoff_local"], "07:00")
        self.assertEqual(out["protocol_candidate"], PROTOCOL)
        self.assertEqual(out["macro_actuals_before_cutoff"], 1)
        self.assertEqual(out["macro_future_schedules_without_actual"], 1)

    def test_success_never_self_certifies_market_or_trade(self):
        out = check()
        for flag in (
            "protocol_approved_for_live_use", "digest_is_independent_custody",
            "real_market_sources_verified", "real_historical_capture_verified",
            "real_oos_accuracy_proven", "can_feed_live_bias",
            "can_feed_real_backtest", "trade_authorized",
            "worker_enabled", "scheduler_enabled",
        ):
            self.assertFalse(out[flag], flag)

    def test_same_content_has_stable_digest_independent_of_evidence_order(self):
        a = check()
        b = check(e=list(reversed(evidence())))
        self.assertEqual(a["frozen_observation_digest"], b["frozen_observation_digest"])
        c = evidence()
        c[1]["actual"] = 3.0
        self.assertNotEqual(a["frozen_observation_digest"],
                            check(e=c)["frozen_observation_digest"])

    def test_macro_veto_is_in_original_frozen_digest(self):
        original = check()
        planned = check(vetoes=macro_plan())
        self.assertEqual(planned["state"], "LAB_FROZEN_SYNTHETIC_OBSERVATION")
        self.assertEqual(planned["predeclared_macro_vetoes"], 1)
        self.assertEqual(planned["macro_veto_policy_lab"], VETO_POLICY_ID)
        self.assertTrue(planned["macro_plan_included_in_digest"])
        self.assertNotEqual(original["frozen_observation_digest"],
                            planned["frozen_observation_digest"])
        self.assertFalse(planned["digest_is_independent_custody"])

    def test_stable_digest_across_macro_veto_order(self):
        b = batch()
        plan = macro_plan()
        second = dict(plan[0])
        second["forecast_id"] = "freeze-lab-1-D1-EURUSD"
        plan.append(second)
        first = check(b=b, vetoes=plan)
        reordered = check(b=b, vetoes=list(reversed(plan)))
        self.assertEqual(first["state"], "LAB_FROZEN_SYNTHETIC_OBSERVATION")
        self.assertEqual(first["frozen_observation_digest"],
                         reordered["frozen_observation_digest"])

    def test_rewrite_veto_rationale_changes_predeclared_digest(self):
        plan = macro_plan()
        first = check(vetoes=plan)
        plan[0]["rationale"] = "Hipotese macro diversa antes da emissao"
        other = check(vetoes=plan)
        self.assertNotEqual(first["frozen_observation_digest"],
                            other["frozen_observation_digest"])

    def test_unrelated_currency_cannot_support_macro_veto(self):
        e = evidence()
        e[1]["currency"] = "CHF"
        rejected = check(e=e, vetoes=macro_plan())
        self.assertEqual(rejected["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_future_event_schedule_cannot_justify_macro_veto(self):
        plan = macro_plan()
        plan[0]["evidence_ids"] = ["macro-coming"]
        self.assertEqual(check(vetoes=plan)["state"],
                         "LAB_REJECTED_DAILY_OBSERVATION")

    def test_wrong_macro_policy_version_fails_closed(self):
        plan = macro_plan()
        plan[0]["policy_id"] = "LATER_SELECTED_POLICY"
        self.assertEqual(check(vetoes=plan)["state"],
                         "LAB_REJECTED_DAILY_OBSERVATION")

    def test_macro_veto_for_weekly_horizon_is_forbidden(self):
        plan = macro_plan()
        plan[0]["forecast_id"] = "freeze-lab-1-W1-USDJPY"
        self.assertEqual(check(vetoes=plan)["state"],
                         "LAB_REJECTED_DAILY_OBSERVATION")

    def test_veto_cannot_append_hindsight_result_fields(self):
        plan = macro_plan()
        plan[0]["realized_return"] = -100
        self.assertEqual(check(vetoes=plan)["state"],
                         "LAB_REJECTED_DAILY_OBSERVATION")

    def test_duplicate_veto_rejected_before_hashing(self):
        plan = macro_plan()
        plan.append(dict(plan[0]))
        self.assertEqual(check(vetoes=plan)["state"],
                         "LAB_REJECTED_DAILY_OBSERVATION")

    def test_unsafe_evidence_capture_cannot_be_predeclared(self):
        e = evidence()
        e[1]["captured_at_utc"] = "2026-11-02T11:00:01+00:00"
        self.assertEqual(check(e=e, vetoes=macro_plan())["state"],
                         "LAB_REJECTED_DAILY_OBSERVATION")

    def test_issuance_at_wrong_hour_rejected_not_shifted(self):
        for h in (6, 8, 0, 23):
            t = datetime(2026, 11, 2, h + 4 if h < 20 else h - 20,
                         tzinfo=timezone.utc)
            # deliberately not the fixed 11:00 UTC cutoff
            if t == ISSUED:
                continue
            self.assertEqual(check(b=batch(t))["state"],
                             "LAB_REJECTED_DAILY_OBSERVATION")

    def test_issuance_at_wrong_minute_rejected(self):
        t = ISSUED + timedelta(minutes=1)
        self.assertEqual(check(b=batch(t))["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_non_business_day_not_invented_as_daily_fx_session(self):
        saturday = datetime(2026, 10, 31, 11, tzinfo=timezone.utc)
        self.assertEqual(check(b=batch(saturday))["state"],
                         "LAB_REJECTED_DAILY_OBSERVATION")

    def test_issue_after_review_instant_is_rejected(self):
        t = datetime(2026, 11, 3, 11, tzinfo=timezone.utc)
        self.assertEqual(check(b=batch(t))["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_omitting_one_pair_or_horizon_rejects_complete_batch(self):
        b = batch(); b["forecasts"].pop()
        self.assertEqual(check(b=b)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_duplicate_pair_horizon_cannot_fabricate_second_record(self):
        b = batch()
        b["forecasts"][-1] = dict(b["forecasts"][0])
        self.assertEqual(check(b=b)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_invalid_issued_forecast_evidence_cutoff_rejected(self):
        b = batch()
        b["forecasts"][0]["evidence_at_utc"] = "2026-11-02T12:00:00+00:00"
        self.assertEqual(check(b=b)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_invalid_forecast_identity_method_or_side_rejected(self):
        for field, value in (
            ("forecast_id", "not-canonical"),
            ("method_id", "other-method"),
            ("bias", "BUY"),
            ("trade_authorized", True),
            ("pair", "JPY/USD"),
            ("horizon", "M5"),
        ):
            b = batch()
            b["forecasts"][0][field] = value
            self.assertEqual(check(b=b)["state"],
                             "LAB_REJECTED_DAILY_OBSERVATION", field)

    def test_evidence_received_after_cutoff_rejected(self):
        e = evidence()
        e[0]["captured_at_utc"] = "2026-11-02T11:01:00+00:00"
        self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_macroeconomic_actual_released_after_cutoff_rejected(self):
        e = evidence()
        e[1]["released_at_utc"] = "2026-11-02T13:00:00+00:00"
        self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_future_scheduled_release_must_not_contain_actual(self):
        for field in ("actual", "surprise"):
            e = evidence()
            e[2][field] = 99.0
            self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_future_schedule_must_be_future_instead_of_reclassified(self):
        e = evidence()
        e[2]["released_at_utc"] = "2026-11-02T10:00:00+00:00"
        self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_no_g8_or_duplicate_g8_is_rejected(self):
        e = evidence()
        self.assertEqual(check(e=e[1:])["state"], "LAB_REJECTED_DAILY_OBSERVATION")
        e = evidence()
        e.append({**e[0], "evidence_id": "g8-another"})
        self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_missing_extra_and_duplicate_g8_currency_rejected(self):
        for currencies in (list(CURRENCIES)[:-1],
                           list(CURRENCIES) + ["BRL"],
                           ["USD"] * 8, [list(CURRENCIES)]):
            e = evidence()
            e[0]["currencies"] = currencies
            self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_missing_source_or_duplicate_evidence_identity_rejected(self):
        e = evidence()
        e[1]["source"] = ""
        self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")
        e = evidence()
        e[1]["evidence_id"] = e[0]["evidence_id"]
        self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_naive_and_future_capture_rejected(self):
        for when in ("2026-11-02T10:00:00", "2026-11-03T10:00:00+00:00"):
            e = evidence(); e[0]["captured_at_utc"] = when
            self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_invalid_macro_number_bool_nan_and_huge_int_rejected(self):
        for actual in (True, float("nan"), float("inf"), 10**1000, "2.5"):
            e = evidence(); e[1]["actual"] = actual
            self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_unserializable_extra_field_is_safe_rejection(self):
        e = evidence()
        e[0]["untrusted_metadata"] = {"set-is-not-json"}
        self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_self_claims_about_real_capture_cannot_enable_permissions(self):
        e = evidence()
        e[0].update({"license_verified": True, "market_verified": True,
                     "immutable_capture_verified": True})
        out = check(e=e)
        self.assertEqual(out["state"], "LAB_FROZEN_SYNTHETIC_OBSERVATION")
        self.assertFalse(out["real_historical_capture_verified"])

    def test_wrong_batch_schema_or_live_evidence_rejected(self):
        b = batch()
        b["state"] = "LIVE_VERIFIED"
        self.assertEqual(check(b=b)["state"], "LAB_REJECTED_DAILY_OBSERVATION")
        e = evidence()
        e[0]["state"] = "PROVIDER_RESPONSE"
        self.assertEqual(check(e=e)["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_audit_requires_timezone_aware_clock(self):
        with self.assertRaises(ValueError):
            check(at=datetime(2026, 11, 2, 15))


if __name__ == "__main__":
    unittest.main()
