"""Protect the core Trader priority: macro vs strength D1/W1/MN1, LAB only."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, evaluate_pair
from atlasquant_trader_bias_priority_bridge_lab import (
    SCHEMA, HORIZONS, build_bias_priority_bridge_lab,
)

AT = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
STAMP = AT.isoformat()


def books() -> tuple[dict, dict]:
    scores = {c: (85.0 if c == "USD" else 15.0 if c == "JPY" else 50.0)
              for c in CURRENCIES}
    order = sorted(CURRENCIES, key=lambda c: (-scores[c], c))
    relative = {
        "schema": "ATLASQUANT_TRADER_BIAS_HORIZONS_LAB_V1",
        "state": "LAB_SIMULACAO_NAO_HOMOLOGADA", "at_utc": STAMP,
        "real_data_verified": False, "trade_authorized": False,
        "pair_count": 28,
        "periods": {
            h: {"state": "LAB_PRONTO", "as_of": STAMP,
                "scores": deepcopy(scores),
                "strongest": order[0], "weakest": order[-1]} for h in HORIZONS
        },
        "rows": [
            {"pair": pair, "entry_signal": False, "trade_authorized": False,
             "horizons": {h: {"bias": {
                 "BUY": "ALTA", "SELL": "BAIXA", "NEUTRAL": "NEUTRO"
             }[evaluate_pair(pair, scores).side]} for h in HORIZONS}}
            for pair in OFFICIAL_PAIRS
        ],
    }
    macro = {
        "schema": "ATLASQUANT_TRADER_EXANTE_MACRO_SCENARIOS_LAB_V1",
        "state": "LAB_EXANTE_CONDITIONAL_HYPOTHESES_ONLY",
        "issued_at_utc": STAMP,
        "actual_market_forecast_verified": False,
        "real_macro_sources_verified": False,
        "real_historical_receipt_verified": False,
        "trade_authorized": False, "can_feed_live_radar": False,
        "pair_hypotheses": [
            {"pair": pair, "horizon": h, "bias_hypothesis": {
                "BUY": "ALTA", "SELL": "BAIXA", "NEUTRAL": "NEUTRO"
            }[evaluate_pair(pair, scores).side],
             "trade_authorized": False, "issued_at_utc": STAMP}
            for pair in OFFICIAL_PAIRS for h in HORIZONS
        ],
    }
    return relative, macro


def study(relative: dict, macro: dict, *, at: datetime = AT) -> dict:
    return build_bias_priority_bridge_lab(relative, macro, evaluated_at=at)


class BiasPriorityBridgeLabTests(unittest.TestCase):
    def test_28_pairs_three_horizons_and_no_operational_bias(self) -> None:
        a, b = books()
        original = deepcopy((a, b))
        out = study(a, b)
        self.assertEqual((a, b), original)
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "LAB_EXPLANATION_ONLY")
        self.assertEqual(len(out["rows"]), 28)
        self.assertEqual({r["pair"] for r in out["rows"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(out["relative_currency_rankings"]["MN1"]["strongest"], "USD")
        self.assertEqual(out["relative_currency_rankings"]["D1"]["weakest"], "JPY")
        for row in out["rows"]:
            self.assertEqual(set(row["horizons"]), set(HORIZONS))
            self.assertFalse(row["trade_authorized"])
            for h in HORIZONS:
                expected = ("NEUTRALIDADE_OU_DIVERGENCIA" if
                            row["horizons"][h]["relative_strength_hypothesis"] == "NEUTRO"
                            else "HIPOTESES_SINTETICAS_CONCORDAM")
                self.assertEqual(row["horizons"][h]["comparison"], expected)
                self.assertEqual(row["horizons"][h]["operational_bias"], "AGUARDAR")
                self.assertFalse(any(row["horizons"][h]["evidence_ready"].values()))
        self.assertFalse(out["real_sources_attested"])
        self.assertFalse(out["historical_vintage_attested"])
        self.assertFalse(out["market_forecast_verified"])
        self.assertIsNone(out["probability_calibrated"])
        self.assertFalse(out["accuracy_90_proven"])
        self.assertFalse(out["can_feed_live_radar"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["trade_authorized"])

    def test_macro_opposes_strength_and_monthly_illustrates_conflict(self) -> None:
        a, b = books()
        target = next(x for x in b["pair_hypotheses"]
                      if x["pair"] == "USD/JPY" and x["horizon"] == "MN1")
        target["bias_hypothesis"] = "BAIXA"
        out = study(a, b)
        row = next(r for r in out["rows"] if r["pair"] == "USD/JPY")
        self.assertEqual(row["horizons"]["D1"]["comparison"],
                         "HIPOTESES_SINTETICAS_CONCORDAM")
        self.assertEqual(row["horizons"]["MN1"]["comparison"],
                         "CONFLITO_ENTRE_HIPOTESES")
        self.assertEqual(row["horizons"]["MN1"]["operational_bias"], "AGUARDAR")

    def test_missing_macro_information_never_fabricates_direction(self) -> None:
        a, b = books()
        b["pair_hypotheses"][0]["bias_hypothesis"] = "AGUARDAR"
        out = study(a, b)
        pair = b["pair_hypotheses"][0]["pair"]
        row = next(x for x in out["rows"] if x["pair"] == pair)
        self.assertEqual(row["horizons"]["D1"]["comparison"], "DADOS_INCOMPLETOS")

    def test_weekly_period_absent_stays_aguardar(self) -> None:
        a, b = books()
        a["periods"]["W1"] = {"state": "INDISPONIVEL"}
        for row in a["rows"]:
            row["horizons"]["W1"]["bias"] = "AGUARDAR"
        out = study(a, b)
        self.assertEqual(out["state"], "LAB_EXPLANATION_ONLY")
        self.assertIsNone(out["relative_currency_rankings"]["W1"]["strongest"])
        self.assertTrue(all(x["horizons"]["W1"]["comparison"] == "DADOS_INCOMPLETOS"
                            for x in out["rows"]))

    def test_future_strength_relative_to_issued_macro_refused(self) -> None:
        a, b = books()
        a["at_utc"] = (AT + timedelta(minutes=15)).isoformat()
        self.assertEqual(study(a, b)["reason"], "CLOCK_OR_HINDSIGHT_CONFLICT")

    def test_forged_real_data_or_authority_blocked(self) -> None:
        for path, value in [
            (("relative", "real_data_verified"), True),
            (("relative", "trade_authorized"), True),
            (("macro", "actual_market_forecast_verified"), True),
            (("macro", "real_macro_sources_verified"), True),
            (("macro", "can_feed_live_radar"), True),
        ]:
            with self.subTest(path=path):
                a, b = books()
                target = a if path[0] == "relative" else b
                target[path[1]] = value
                out = study(a, b)
                self.assertEqual(out["reason"], "FORGED_OR_UNSUPPORTED_AUTHORITY")
                self.assertFalse(out["trade_authorized"])

    def test_missing_duplicate_pair_or_horizon_refused(self) -> None:
        a, b = books()
        b["pair_hypotheses"].pop()
        self.assertEqual(study(a, b)["reason"], "INCOMPLETE_PAIR_COVERAGE")
        a, b = books()
        b["pair_hypotheses"][1]["pair"] = b["pair_hypotheses"][0]["pair"]
        b["pair_hypotheses"][1]["horizon"] = b["pair_hypotheses"][0]["horizon"]
        self.assertEqual(study(a, b)["reason"], "PAIR_OR_HORIZON_DUPLICATED_OR_MISSING")
        a, b = books()
        a["rows"][1]["pair"] = a["rows"][0]["pair"]
        self.assertEqual(study(a, b)["reason"], "PAIR_OR_HORIZON_DUPLICATED_OR_MISSING")

    def test_future_period_data_and_stale_books_refused(self) -> None:
        a, b = books()
        a["periods"]["MN1"]["as_of"] = (AT + timedelta(days=2)).isoformat()
        self.assertEqual(study(a, b)["reason"], "PERIOD_POSTDATES_FROZEN_STRENGTH")
        a, b = books()
        self.assertEqual(study(a, b, at=AT + timedelta(days=46))["reason"],
                         "CLOCK_OR_HINDSIGHT_CONFLICT")

    def test_invalid_bias_and_timestamp_injected_into_macro_refused(self) -> None:
        a, b = books()
        b["pair_hypotheses"][0]["bias_hypothesis"] = "BUY_NOW"
        self.assertEqual(study(a, b)["reason"], "UNSAFE_MACRO_HYPOTHESIS")

    def test_strength_label_or_ranking_must_match_scores(self) -> None:
        a, b = books()
        a["periods"]["MN1"]["strongest"] = "JPY"
        self.assertEqual(study(a, b)["reason"], "RANKING_NOT_REPRODUCIBLE")
        a, b = books()
        row = next(r for r in a["rows"] if r["pair"] == "USD/JPY")
        row["horizons"]["MN1"]["bias"] = "BAIXA"
        self.assertEqual(study(a, b)["reason"], "STRENGTH_BIAS_CONTRADICTS_SCORES")
        a, b = books()
        a["periods"]["MN1"]["scores"]["USD"] = 10 ** 1000
        self.assertEqual(study(a, b)["reason"], "RANKING_NOT_REPRODUCIBLE")

    def test_unhashable_pair_or_horizon_is_rejected(self) -> None:
        a, b = books()
        a["rows"][0]["pair"] = ["USD/JPY"]
        self.assertEqual(study(a, b)["reason"], "PAIR_OR_HORIZON_DUPLICATED_OR_MISSING")
        a, b = books()
        b["pair_hypotheses"][0]["horizon"] = ["MN1"]
        self.assertEqual(study(a, b)["reason"], "PAIR_OR_HORIZON_DUPLICATED_OR_MISSING")
        a, b = books()
        b["pair_hypotheses"][0]["issued_at_utc"] = (AT + timedelta(days=1)).isoformat()
        self.assertEqual(study(a, b)["reason"], "UNSAFE_MACRO_HYPOTHESIS")

    def test_unsupported_live_books_are_refused(self) -> None:
        a, b = books()
        b["state"] = "LIVE"
        self.assertEqual(study(a, b)["reason"], "ONLY_UNPROMOTED_LAB_BOOKS_SUPPORTED")

    def test_naive_evaluation_clock_is_not_accepted(self) -> None:
        a, b = books()
        with self.assertRaises(ValueError):
            study(a, b, at=AT.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
