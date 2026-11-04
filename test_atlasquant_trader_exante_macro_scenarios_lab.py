"""Contract tests: hand-authored SYNTHETIC ex-ante macro scenario fanout only."""
import copy
import unittest
from datetime import datetime, timezone

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_exante_macro_scenarios_lab import (
    HORIZONS, INDICES, METHOD, SCHEMA, issue_macro_scenario_fanout_lab,
)

ISSUED = "2026-11-02T12:00:00Z"
EVALUATED = datetime(2026, 11, 2, 12, 1, tzinfo=timezone.utc)


def sample_book():
    def evidence(ident, category, kind, event, published, captured):
        return {
            "state": "LAB_SYNTHETIC_PREISSUE_EVIDENCE",
            "evidence_id": ident, "category": category, "kind": kind,
            "event_at_utc": event, "published_at_utc": published,
            "captured_at_utc": captured,
            "source_url": "https://example.org/synthetic-calendar",
            "summary": "Fictional test fixture; no real release verified",
        }

    def view(macro):
        return {
            "macro": macro, "micro": "NEUTRO", "geopolitics": "NEUTRO",
            "evidence_by_factor": {"MACRO": ["macro-01"], "MICRO": [], "GEOPOLITICS": []},
            "rationale": "Manual synthetic expectation for contract testing only",
        }

    book = {
        "state": "LAB_SYNTHETIC_SCENARIO_BOOK", "method_id": METHOD,
        "issued_at_utc": ISSUED,
        "evidences": [
            evidence("macro-01", "MACRO", "RELEASED_CONTEXT",
                     "2026-10-30T12:00:00Z", "2026-10-30T13:00:00Z",
                     "2026-11-01T13:00:00Z"),
            evidence("micro-01", "MICRO", "RELEASED_CONTEXT",
                     "2026-10-30T12:00:00Z", "2026-10-30T13:00:00Z",
                     "2026-11-01T13:00:00Z"),
            evidence("geo-01", "GEOPOLITICS", "RELEASED_CONTEXT",
                     "2026-10-30T12:00:00Z", "2026-10-30T13:00:00Z",
                     "2026-11-01T13:00:00Z"),
            evidence("event-01", "MACRO", "SCHEDULED",
                     "2026-11-03T18:00:00Z", "2026-11-01T08:00:00Z",
                     "2026-11-01T08:30:00Z"),
        ],
        "currency_views": {h: {c: view("NEUTRO") for c in CURRENCIES} for h in HORIZONS},
        "index_views": {h: {i: view("NEUTRO") for i in INDICES} for h in HORIZONS},
    }
    return book


def run(book):
    return issue_macro_scenario_fanout_lab(book, evaluated_at=EVALUATED)


def direction(result, horizon, pair):
    return next(x["bias_hypothesis"] for x in result["pair_hypotheses"]
                if x["pair"] == pair and x["horizon"] == horizon)


def pair_of(base, quote):
    return next(p for p in OFFICIAL_PAIRS if split_pair(p) == (base, quote))


class ExAnteMacroScenariosLabTests(unittest.TestCase):
    def test_all_28_fx_five_indices_and_three_horizons(self):
        result = run(sample_book())
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "LAB_EXANTE_CONDITIONAL_HYPOTHESES_ONLY")
        self.assertEqual(len(result["pair_hypotheses"]), 84)
        self.assertEqual(len(result["index_hypotheses"]), 15)
        self.assertEqual({x["horizon"] for x in result["pair_hypotheses"]}, set(HORIZONS))
        self.assertEqual({x["symbol"] for x in result["index_hypotheses"]}, set(INDICES))
        self.assertEqual(len({(x["pair"], x["horizon"]) for x in result["pair_hypotheses"]}), 84)

    def test_currency_base_vs_quote_and_horizon_independence(self):
        book = sample_book()
        book["currency_views"]["D1"]["EUR"]["macro"] = "FORTALECE"
        book["currency_views"]["D1"]["USD"]["macro"] = "ENFRAQUECE"
        book["currency_views"]["W1"]["EUR"]["macro"] = "ENFRAQUECE"
        book["currency_views"]["W1"]["USD"]["macro"] = "FORTALECE"
        p = pair_of("EUR", "USD")
        result = run(book)
        self.assertEqual(direction(result, "D1", p), "ALTA")
        self.assertEqual(direction(result, "W1", p), "BAIXA")
        self.assertEqual(direction(result, "MN1", p), "NEUTRO")

    def test_indices_have_independent_macro_hypotheses(self):
        book = sample_book()
        book["currency_views"]["D1"]["USD"]["macro"] = "FORTALECE"
        book["index_views"]["D1"]["SPX500"]["macro"] = "ALTA"
        book["index_views"]["D1"]["NAS100"]["macro"] = "BAIXA"
        rows = run(book)["index_hypotheses"]
        self.assertEqual(next(x["bias_hypothesis"] for x in rows if x["symbol"] == "SPX500" and x["horizon"] == "D1"), "ALTA")
        self.assertEqual(next(x["bias_hypothesis"] for x in rows if x["symbol"] == "NAS100" and x["horizon"] == "D1"), "BAIXA")
        self.assertEqual(next(x["bias_hypothesis"] for x in rows if x["symbol"] == "SPX500" and x["horizon"] == "W1"), "NEUTRO")

    def test_micro_conflict_vetoes_fx(self):
        book = sample_book()
        row = book["currency_views"]["D1"]["EUR"]
        row["macro"], row["micro"] = "FORTALECE", "CONTRA"
        row["evidence_by_factor"]["MICRO"] = ["micro-01"]
        book["currency_views"]["D1"]["USD"]["macro"] = "ENFRAQUECE"
        self.assertEqual(direction(run(book), "D1", pair_of("EUR", "USD")), "AGUARDAR")

    def test_geopolitical_conflict_vetoes_index(self):
        book = sample_book()
        row = book["index_views"]["D1"]["WIN"]
        row["macro"], row["geopolitics"] = "ALTA", "CONTRA"
        row["evidence_by_factor"]["GEOPOLITICS"] = ["geo-01"]
        result = run(book)
        self.assertEqual(next(x["bias_hypothesis"] for x in result["index_hypotheses"]
                              if x["symbol"] == "WIN" and x["horizon"] == "D1"), "AGUARDAR")

    def test_unknown_factor_vetoes(self):
        book = sample_book()
        book["currency_views"]["D1"]["EUR"]["micro"] = "DESCONHECIDO"
        self.assertEqual(direction(run(book), "D1", pair_of("EUR", "USD")), "AGUARDAR")

    def test_unknown_macro_vetoes(self):
        book = sample_book()
        book["currency_views"]["D1"]["EUR"]["macro"] = "DESCONHECIDO"
        self.assertEqual(direction(run(book), "D1", pair_of("EUR", "USD")), "AGUARDAR")

    def test_bounded_scheduled_evidence_identified(self):
        self.assertEqual(run(sample_book())["scheduled_evidence_ids"], ["event-01"])

    def test_future_published_evidence_rejected(self):
        book = sample_book()
        book["evidences"][0]["published_at_utc"] = "2026-11-02T12:01:00Z"
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_future_capture_rejected(self):
        book = sample_book()
        book["evidences"][0]["captured_at_utc"] = "2026-11-02T12:01:00Z"
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_past_scheduled_event_rejected(self):
        book = sample_book()
        book["evidences"][3]["event_at_utc"] = "2026-11-02T11:00:00Z"
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_out_of_order_context_rejected(self):
        book = sample_book()
        book["evidences"][0]["event_at_utc"] = "2026-11-02T13:00:00Z"
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_retrospective_actual_field_rejected(self):
        book = sample_book()
        book["evidences"][3]["actual"] = 3.5
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_non_https_source_rejected(self):
        book = sample_book()
        book["evidences"][0]["source_url"] = "http://example.org/fake"
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_missing_one_currency_rejected(self):
        book = sample_book()
        del book["currency_views"]["W1"]["CHF"]
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_missing_one_index_rejected(self):
        book = sample_book()
        del book["index_views"]["MN1"]["WIN"]
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_direction_requires_macro_evidence(self):
        book = sample_book()
        book["currency_views"]["D1"]["EUR"]["evidence_by_factor"]["MACRO"] = []
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_wrong_category_reference_rejected(self):
        book = sample_book()
        book["currency_views"]["D1"]["EUR"]["evidence_by_factor"]["MACRO"] = ["geo-01"]
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_micro_opinion_without_source_rejected(self):
        book = sample_book()
        book["index_views"]["MN1"]["US30"]["micro"] = "CONTRA"
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_duplicate_id_rejected(self):
        book = sample_book()
        book["evidences"][1]["evidence_id"] = "macro-01"
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_unhashable_categorical_input_rejected_without_exception(self):
        book = sample_book()
        book["currency_views"]["D1"]["EUR"]["macro"] = []
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_future_issue_rejected(self):
        book = sample_book()
        book["issued_at_utc"] = "2026-11-02T12:02:00Z"
        self.assertEqual(run(book)["state"], "LAB_EXANTE_SCENARIO_REJECTED")

    def test_naive_evaluation_time_rejected(self):
        with self.assertRaises(ValueError):
            issue_macro_scenario_fanout_lab(sample_book(), evaluated_at=datetime(2026, 11, 2, 12, 1))

    def test_no_probability_accuracy_or_trading_claims(self):
        result = run(sample_book())
        self.assertIsNone(result["probability_calibrated"])
        self.assertFalse(result["accuracy_90_proven"])
        for key in ("trade_authorized", "worker_enabled", "scheduler_enabled",
                    "can_feed_live_radar", "actual_market_forecast_verified",
                    "real_macro_sources_verified", "real_oos_verified"):
            self.assertFalse(result[key], key)
        for row in result["pair_hypotheses"] + result["index_hypotheses"]:
            self.assertIsNone(row["probability_calibrated"])
            self.assertFalse(row["trade_authorized"])


if __name__ == "__main__":
    unittest.main()
