"""LAB-only matched policy path revisions: 8 currencies, 28 pairs, 3 horizons."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_relative_policy_repricing_lab import (
    SCHEMA, METHOD, HORIZONS, build_matched_policy_repricing_lab,
)

AT = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
CHANGES = {
    "USD": "15", "EUR": "-5", "GBP": "10", "JPY": "-10",
    "CHF": "-2", "AUD": "4", "CAD": "2", "NZD": "-7",
}
TARGET = {"D1": 1, "W1": 7, "MN1": 30}


def utc(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def fixture():
    rows = []
    for h in HORIZONS:
        for c in CURRENCIES:
            rows.append({
                "currency": c, "horizon": h,
                "measure": "EXPECTED_POLICY_PATH_REVISION",
                "unit": "BASIS_POINTS",
                "data_state": "LAB_SYNTHETIC_UNVERIFIED",
                "window_start_utc": utc(AT - timedelta(hours=2)),
                "window_end_utc": utc(AT - timedelta(hours=1)),
                "target_at_utc": utc(AT + timedelta(days=TARGET[h])),
                "captured_at_utc": utc(AT - timedelta(minutes=55)),
                "path_revision_bp": CHANGES[c],
                "macro_rationale": "Contrafactual: revisão de trajetória implícita.",
                "micro": "ALINHADO", "geopolitics": "ALINHADO",
            })
    return {
        "state": "LAB_SYNTHETIC_POLICY_REPRICING_BOOK",
        "method_id": METHOD, "issued_at_utc": utc(AT),
        "observations": rows,
    }


def research(book=None, evaluated_at=AT):
    return build_matched_policy_repricing_lab(
        fixture() if book is None else book, evaluated_at=evaluated_at,
    )


def pair(rows, symbol, horizon):
    return next(r for r in rows if r["pair"] == symbol and r["horizon"] == horizon)


class RelativePolicyRepricingLabTests(unittest.TestCase):
    def test_covers_canonical_eight_currency_28_pair_three_horizon(self):
        result = research()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["currency_count"], 8)
        self.assertEqual(result["pair_count"], 28)
        self.assertEqual(result["hypothesis_count"], 84)
        self.assertEqual(len(result["pair_hypotheses"]), 84)
        for h in HORIZONS:
            self.assertEqual(set(result["currency_horizons"][h]), set(CURRENCIES))
            self.assertEqual({r["pair"] for r in result["pair_hypotheses"]
                              if r["horizon"] == h}, set(OFFICIAL_PAIRS))

    def test_real_trading_bias_always_wait(self):
        result = research()
        self.assertEqual(result["state"], "LAB_SYNTHETIC_MATCHED_POLICY_REPRICING_ONLY")
        for row in result["pair_hypotheses"]:
            self.assertEqual(row["directional_bias"], "AGUARDAR")
            self.assertIsNone(row["probability_calibrated"])
            self.assertFalse(row["trade_authorized"])
            self.assertFalse(row["real_prices_verified"])

    def test_usdjpy_positive_repricing_gap_is_not_fx_prediction(self):
        row = pair(research()["pair_hypotheses"], "USD/JPY", "D1")
        self.assertEqual(row["synthetic_relative_revision_bp"], "25")
        self.assertEqual(row["research_mechanism"], "PRESSAO_RELATIVA_POSITIVA_HIPOTETICA")
        self.assertEqual(row["directional_bias"], "AGUARDAR")

    def test_eurusd_negative_repricing_gap_is_not_trade(self):
        row = pair(research()["pair_hypotheses"], "EUR/USD", "D1")
        self.assertEqual(row["synthetic_relative_revision_bp"], "-20")
        self.assertEqual(row["research_mechanism"], "PRESSAO_RELATIVA_NEGATIVA_HIPOTETICA")

    def test_eurgbp_base_quote_order_preserved(self):
        row = pair(research()["pair_hypotheses"], "EUR/GBP", "D1")
        self.assertEqual(row["synthetic_relative_revision_bp"], "-15")

    def test_no_duplicate_reverse_pair_output(self):
        rows = research()["pair_hypotheses"]
        for h in HORIZONS:
            subset = [r for r in rows if r["horizon"] == h]
            self.assertEqual(len({frozenset((r["base"], r["quote"])) for r in subset}), 28)

    def test_independent_horizons(self):
        b = fixture()
        next(x for x in b["observations"] if x["currency"] == "USD" and x["horizon"] == "MN1")["path_revision_bp"] = "-25"
        rows = research(b)["pair_hypotheses"]
        self.assertEqual(pair(rows, "USD/JPY", "D1")["synthetic_relative_revision_bp"], "25")
        self.assertEqual(pair(rows, "USD/JPY", "MN1")["synthetic_relative_revision_bp"], "-15")

    def test_exact_neutral_boundary(self):
        b = fixture()
        for r in b["observations"]:
            if r["currency"] == "USD":
                r["path_revision_bp"] = "0"
            if r["currency"] == "EUR":
                r["path_revision_bp"] = "-5"
        p = pair(research(b)["pair_hypotheses"], "EUR/USD", "D1")
        self.assertEqual(p["research_mechanism"], "PRESSAO_RELATIVA_NEUTRA_HIPOTETICA")

    def test_micro_contra_is_veto(self):
        b = fixture()
        next(x for x in b["observations"] if x["currency"] == "USD" and x["horizon"] == "D1")["micro"] = "CONTRA"
        self.assertEqual(pair(research(b)["pair_hypotheses"], "USD/JPY", "D1")["research_mechanism"],
                         "VETO_MICRO_GEOPOLITICO")

    def test_geopolitical_unknown_is_veto(self):
        b = fixture()
        next(x for x in b["observations"] if x["currency"] == "JPY" and x["horizon"] == "W1")["geopolitics"] = "DESCONHECIDO"
        self.assertEqual(pair(research(b)["pair_hypotheses"], "USD/JPY", "W1")["research_mechanism"],
                         "VETO_EVIDENCIA_INCOMPLETA")

    def test_conflict_precedes_unknown(self):
        b = fixture()
        next(x for x in b["observations"] if x["currency"] == "JPY" and x["horizon"] == "W1")["geopolitics"] = "DESCONHECIDO"
        next(x for x in b["observations"] if x["currency"] == "USD" and x["horizon"] == "W1")["micro"] = "CONTRA"
        self.assertEqual(pair(research(b)["pair_hypotheses"], "USD/JPY", "W1")["research_mechanism"],
                         "VETO_MICRO_GEOPOLITICO")

    def test_missing_slot_refused(self):
        b = fixture()
        b["observations"].pop()
        self.assertEqual(research(b)["pair_hypotheses"], [])

    def test_duplicate_slot_refused(self):
        b = fixture()
        b["observations"][-1] = deepcopy(b["observations"][0])
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_extra_field_direction_forbidden(self):
        b = fixture()
        b["observations"][0]["directional_bias"] = "ALTA"
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_unverified_only_no_fake_quote_authentication(self):
        b = fixture()
        b["observations"][0]["data_state"] = "OFFICIAL_VERIFIED"
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_nominal_policy_level_rejected(self):
        b = fixture()
        b["observations"][0]["measure"] = "NOMINAL_CENTRAL_BANK_RATE"
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_unit_percentage_not_basis_points_rejected(self):
        b = fixture()
        b["observations"][0]["unit"] = "PCT"
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_mismatched_target_date_rejected(self):
        b = fixture()
        b["observations"][1]["target_at_utc"] = utc(AT + timedelta(days=2))
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_mismatched_measurement_window_rejected(self):
        b = fixture()
        b["observations"][1]["window_start_utc"] = utc(AT - timedelta(hours=3))
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_future_capture_leakage_rejected(self):
        b = fixture()
        b["observations"][0]["captured_at_utc"] = utc(AT + timedelta(minutes=1))
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_future_market_window_leakage_rejected(self):
        b = fixture()
        b["observations"][0]["window_end_utc"] = utc(AT + timedelta(seconds=1))
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_stale_market_window_rejected(self):
        b = fixture()
        for r in b["observations"]:
            r["window_start_utc"] = utc(AT - timedelta(hours=27))
            r["window_end_utc"] = utc(AT - timedelta(hours=25))
            r["captured_at_utc"] = utc(AT - timedelta(hours=24))
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_capture_before_observation_end_rejected(self):
        b = fixture()
        b["observations"][0]["captured_at_utc"] = utc(AT - timedelta(hours=2))
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_target_in_past_refused(self):
        b = fixture()
        b["observations"][0]["target_at_utc"] = utc(AT - timedelta(days=1))
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_non_utc_claims_refused(self):
        b = fixture()
        b["observations"][0]["window_start_utc"] = "2026-11-03T10:00:00+00:00"
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_naive_evaluated_clock_raises(self):
        with self.assertRaises(ValueError):
            research(evaluated_at=datetime(2026, 11, 3, 12))

    def test_issue_after_evaluation_refused(self):
        self.assertEqual(research(evaluated_at=AT - timedelta(seconds=1))["state"],
                         "LAB_POLICY_REPRICING_REFUSED")

    def test_invalid_decimal_and_nonfinite_rejected(self):
        for v in ("NaN", "Inf", "-Infinity", "3e2", "300", "9999999999", 10.0, True):
            b = fixture()
            b["observations"][0]["path_revision_bp"] = v
            with self.subTest(v=v):
                self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_unknown_currency_and_horizon_rejected(self):
        for key, value in (("currency", "BRL"), ("horizon", "H4")):
            b = fixture()
            b["observations"][0][key] = value
            with self.subTest(key=key):
                self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_invalid_micro_geopolitical_tags_refused(self):
        for key in ("micro", "geopolitics"):
            b = fixture()
            b["observations"][0][key] = "POSITIVO"
            with self.subTest(key=key):
                self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")

    def test_source_and_return_never_claim_90_percent(self):
        r = research()
        for flag in ("market_quotes_verified", "independent_receipts_verified",
                     "directional_accuracy_oos_proven", "accuracy_90_proven",
                     "can_feed_live_radar", "trade_authorized", "worker_enabled",
                     "scheduler_enabled", "nominal_rate_level_comparison_used"):
            with self.subTest(flag=flag):
                self.assertIs(r[flag], False)
        self.assertIsNone(r["probability_calibrated"])

    def test_caller_cannot_forge_calibration_field(self):
        b = fixture()
        b["accuracy_90_proven"] = True
        self.assertEqual(research(b)["state"], "LAB_POLICY_REPRICING_REFUSED")


if __name__ == "__main__":
    unittest.main()
