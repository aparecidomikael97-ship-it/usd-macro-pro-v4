"""Preselected synthetic G8 macro research policy: 8x4, no post-hoc changes."""
import copy
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_macro_context_lab import GROUPS
from atlasquant_trader_g8_macro_selection_lab import (
    METHOD, freeze_g8_macro_indicator_policy_lab,
    compare_preselected_g8_macro_lab,
)

REGISTERED = datetime(2026, 8, 28, 12, tzinfo=timezone.utc)
FROZEN_AT = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
START = datetime(2026, 9, 1, tzinfo=timezone.utc)
ISSUED = datetime(2026, 11, 2, 11, tzinfo=timezone.utc)
EVALUATED = datetime(2026, 11, 2, 18, tzinfo=timezone.utc)
PICKS = {
    "INFLATION": ("CPI", "PERCENT"),
    "EMPLOYMENT": ("UNEMPLOYMENT", "PERCENT"),
    "POLICY": ("POLICY_RATE", "PERCENT"),
    "ACTIVITY": ("PMI", "INDEX"),
}


def policy():
    return {
        "state": "LAB_SYNTHETIC_G8_MACRO_POLICY",
        "method_id": METHOD, "policy_id": "g8-experiment-001",
        "registered_at_utc": REGISTERED.isoformat(),
        "experiment_start_at_utc": START.isoformat(),
        "selections": [
            {"currency": c, "group": group,
             "indicator_id": PICKS[group][0], "unit": PICKS[group][1],
             "rationale": f"Laboratorio: usar apenas {PICKS[group][0]} para {c} "
                          "antes de conhecer retornos de mercado"}
            for c in CURRENCIES for group in GROUPS
        ],
    }


def event(currency="USD", group="INFLATION", *, pending=False, actual=3.2,
          indicator=None, unit=None):
    name, measured = PICKS[group]
    name = indicator if indicator is not None else name
    measured = unit if unit is not None else measured
    ident = f"{currency}-{name}-research-001"
    pre = {
        "state": "LAB_SYNTHETIC_MACRO_PRE", "event_id": ident,
        "currency": currency, "indicator_id": name, "unit": measured,
        "source": "Calendario inteiramente sintetico",
        "previous": 2.8, "previous_captured_at_utc": "2026-10-29T11:00:00+00:00",
        "consensus": 3.0, "consensus_captured_at_utc": "2026-10-30T12:00:00+00:00",
        "scheduled_release_at_utc": (
            "2026-11-02T14:00:00+00:00" if pending
            else "2026-10-30T14:00:00+00:00"
        ),
        "deadband_predeclared": 0.1,
    }
    release = None if pending else {
        "state": "LAB_SYNTHETIC_MACRO_ACTUAL",
        "event_id": ident, "actual": actual,
        "released_at_utc": "2026-10-30T14:00:00+00:00",
        "captured_at_utc": "2026-10-30T14:05:00+00:00",
        "source": "Boletim apenas sintetico",
    }
    return {"preliminary": pre, "actual_release": release}


def seal(p=None, *, at=FROZEN_AT):
    return freeze_g8_macro_indicator_policy_lab(policy() if p is None else p,
                                                 research_at=at)


def compare(rows, frozen=None, **kwargs):
    return compare_preselected_g8_macro_lab(
        seal() if frozen is None else frozen, rows,
        forecast_issued_at=ISSUED, evaluated_at=EVALUATED, **kwargs,
    )


class PreselectedG8MacroPolicyTests(unittest.TestCase):
    def test_valid_policy_has_32_unique_selections_and_hash(self):
        out = seal()
        self.assertEqual(out["state"], "LAB_SYNTHETIC_POLICY_CONTENT_FROZEN")
        self.assertEqual(len(out["policy_document"]["selections"]), 32)
        self.assertEqual(len(out["policy_digest"]), 64)
        self.assertFalse(out["real_precommit_time_verified"])

    def test_policy_order_does_not_change_digest(self):
        p = policy()
        a = seal(p)
        p["selections"].reverse()
        b = seal(p)
        self.assertEqual(a["policy_digest"], b["policy_digest"])

    def test_rewriting_prior_selection_changes_digest(self):
        p = policy()
        original = seal(p)
        p["selections"][0]["rationale"] += " hipotese modificada"
        changed = seal(p)
        self.assertNotEqual(original["policy_digest"], changed["policy_digest"])

    def test_complete_macro_evidence_matrix_for_eight_currencies(self):
        rows = [event(c, g) for c in CURRENCIES for g in GROUPS]
        out = compare(rows)
        self.assertEqual(out["state"], "LAB_PRESELECTED_G8_CONTEXT_ONLY")
        self.assertEqual(out["currency_count"], 8)
        self.assertEqual(out["pair_count"], 28)
        self.assertEqual(out["predeclared_indicator_slots"], 32)
        self.assertEqual(out["reported_synthetic_events"], 32)
        self.assertEqual(set(out["pair_comparisons"]), set(OFFICIAL_PAIRS))
        for ccy in CURRENCIES:
            self.assertEqual(set(out["currency_selection_matrix"][ccy]), set(GROUPS))

    def test_missing_preselected_release_does_not_switch_indicators(self):
        out = compare([event("USD")])
        self.assertEqual(out["state"], "LAB_PRESELECTED_G8_CONTEXT_ONLY")
        self.assertEqual(
            out["currency_selection_matrix"]["EUR"]["INFLATION"]["evidence_state"],
            "SELECTED_INDICATOR_NOT_REPORTED")
        self.assertEqual(
            out["currency_selection_matrix"]["USD"]["INFLATION"]["indicator_id"],
            "CPI")
        self.assertEqual(out["pair_comparisons"]["EUR/USD"]
                         ["fundamental_groups"]["INFLATION"]["status"],
                         "INSUFFICIENT_BILATERAL_COVERAGE")

    def test_unplanned_indicator_is_not_a_fallback(self):
        out = compare([event("USD", indicator="CORE_CPI")])
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")
        self.assertIn("original policy", out["reason"])

    def test_different_unit_from_policy_fails_closed(self):
        out = compare([event("USD", unit="BPS")])
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_duplicated_release_even_with_different_values_rejected(self):
        out = compare([event("USD"), event("USD", actual=4.8)])
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_changed_predeclared_indicator_cannot_reuse_old_digest(self):
        frozen = seal()
        frozen["policy_document"]["selections"][0]["indicator_id"] = "CORE_CPI"
        out = compare([event("USD")], frozen)
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_changed_policy_rationale_cannot_reuse_old_digest(self):
        frozen = seal()
        frozen["policy_document"]["selections"][0]["rationale"] += " after result"
        out = compare([event("USD")], frozen)
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")
        self.assertIn("hash", out["reason"])

    def test_replaced_policy_digest_is_rejected(self):
        frozen = seal()
        frozen["policy_digest"] = "0" * 64
        self.assertEqual(compare([event("USD")], frozen)["state"],
                         "LAB_MACRO_POLICY_REJECTED")

    def test_policy_requires_exactly_32_selections(self):
        p = policy()
        p["selections"].pop()
        self.assertEqual(seal(p)["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_policy_duplicate_currency_group_rejected(self):
        p = policy()
        p["selections"][-1] = dict(p["selections"][0])
        self.assertEqual(seal(p)["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_wrong_group_indicator_mapping_refused(self):
        p = policy()
        p["selections"][0]["indicator_id"] = "NFP"
        self.assertEqual(seal(p)["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_policy_does_not_accept_extra_hindsight_field(self):
        p = policy()
        p["best_test_hit_rate_pct"] = 98.5
        self.assertEqual(seal(p)["state"], "LAB_MACRO_POLICY_REJECTED")
        p = policy()
        p["selections"][0]["future_pair_return"] = 100
        self.assertEqual(seal(p)["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_policy_requires_explicit_experiment_start_and_registration(self):
        for field in ("registered_at_utc", "experiment_start_at_utc"):
            p = policy()
            del p[field]
            self.assertEqual(seal(p)["state"], "LAB_MACRO_POLICY_REJECTED")
        p = policy()
        p["experiment_start_at_utc"] = REGISTERED.isoformat()
        self.assertEqual(seal(p)["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_cannot_first_freeze_plan_after_experiment_has_started(self):
        out = seal(at=START + timedelta(days=7))
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_cannot_freeze_before_declared_registration(self):
        out = seal(at=REGISTERED-timedelta(minutes=1))
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_forecast_before_experiment_start_is_blocked(self):
        frozen = seal()
        out = compare_preselected_g8_macro_lab(
            frozen, [event("USD")],
            forecast_issued_at=START-timedelta(days=1),
            evaluated_at=EVALUATED)
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_future_event_is_schedule_only_not_actual(self):
        out = compare([event("USD", pending=True)])
        self.assertEqual(out["state"], "LAB_PRESELECTED_G8_CONTEXT_ONLY")
        usd = out["currency_selection_matrix"]["USD"]["INFLATION"]
        self.assertEqual(usd["evidence_state"], "SCHEDULED_NOT_RELEASED")
        self.assertEqual(out["synthetic_freeze_evidences"][0]["kind"],
                         "MACRO_SCHEDULE_ONLY")
        self.assertNotIn("actual", out["synthetic_freeze_evidences"][0])

    def test_actual_published_after_forecast_cannot_be_backfilled(self):
        item = event("USD")
        item["actual_release"]["released_at_utc"] = "2026-11-02T14:00:00+00:00"
        item["actual_release"]["captured_at_utc"] = "2026-11-02T14:01:00+00:00"
        out = compare([item])
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_pre_snapshot_with_future_actual_field_rejected(self):
        item = event("USD")
        item["preliminary"]["actual"] = 3.9
        self.assertEqual(compare([item])["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_macro_inference_and_trade_permissions_remain_disabled(self):
        out = compare([event("USD")])
        self.assertEqual(out["market_direction"], "UNDETERMINED")
        self.assertEqual(out["automatic_macro_vetoes"], [])
        for flag in ("real_precommit_time_verified",
                     "real_historical_data_verified",
                     "actual_macro_predictive_uplift_proven",
                     "currency_direction_inferred", "trade_authorized",
                     "worker_enabled", "scheduler_enabled"):
            self.assertFalse(out[flag], flag)

    def test_no_candidate_events_cannot_invent_market_data(self):
        out = compare([])
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")
        self.assertEqual(out["currency_selection_matrix"], {})

    def test_unknown_currency_or_unapproved_group_blocked(self):
        p = policy()
        p["selections"][0]["currency"] = "BRL"
        self.assertEqual(seal(p)["state"], "LAB_MACRO_POLICY_REJECTED")
        p = policy()
        p["selections"][0]["group"] = "GEOPOLITICS"
        self.assertEqual(seal(p)["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_unbounded_event_list_and_invalid_envelope_rejected(self):
        self.assertEqual(compare([event("USD")] * 33)["state"],
                         "LAB_MACRO_POLICY_REJECTED")
        bad = event("USD")
        bad["future_market_direction"] = "BUY_USD"
        self.assertEqual(compare([bad])["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_missing_or_forged_frozen_policy_rejected(self):
        self.assertEqual(compare([event("USD")], {})["state"],
                         "LAB_MACRO_POLICY_REJECTED")
        frozen = seal()
        frozen["custody_independent_verified"] = True
        self.assertEqual(compare([event("USD")], frozen)["state"],
                         "LAB_MACRO_POLICY_REJECTED")

    def test_preselection_does_not_claim_immutable_external_custody(self):
        frozen = seal()
        self.assertFalse(frozen["custody_independent_verified"])
        self.assertFalse(frozen["real_precommit_time_verified"])
        p = compare([event("USD")], frozen)
        self.assertEqual(p["predeclared_policy_digest"], frozen["policy_digest"])
        self.assertFalse(p["real_precommit_time_verified"])

    def test_cutoff_and_evaluation_must_have_timezone(self):
        frozen = seal()
        with self.assertRaises(ValueError):
            compare_preselected_g8_macro_lab(
                frozen, [event("USD")], forecast_issued_at=datetime(2026, 11, 2, 11),
                evaluated_at=EVALUATED)
        with self.assertRaises(ValueError):
            compare_preselected_g8_macro_lab(
                frozen, [event("USD")], forecast_issued_at=ISSUED,
                evaluated_at=datetime(2026, 11, 2, 18))
        with self.assertRaises(ValueError):
            seal(at=datetime(2026, 8, 30, 12))


if __name__ == "__main__":
    unittest.main()
