"""Point-in-time firewall between ECB reference moves and macro claims."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_ecb_macro_timing_bridge_lab import (
    SCHEMA, build_ecb_macro_timing_bridge_lab,
)
from test_atlasquant_trader_ecb_three_horizon_matrix_lab import NOW, sample, FIXES, xml_history


def mock_dossier():
    rows = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        frames = {
            horizon: {
                "macro_surprise_claims": [],
                "news_documentary_count": 0,
                "calendar_risk_status_documentary": "SYNTHETIC",
                "operational_bias": "AGUARDAR",
                "base_currency_strength_cause": "NAO_COMPROVADA",
                "quote_currency_strength_cause": "NAO_COMPROVADA",
                "actual_values_source_attested": False,
            } for horizon in ("D1", "W1", "MN1")
        }
        rows.append({"pair": pair, "base": base, "quote": quote,
                     "horizons": frames, "trade_authorized": False})
    return {
        "schema": "ATLASQUANT_TRADER_MACRO_CAUSAL_DOSSIER_LAB_V1",
        "state": "LAB_CAUSAL_EVIDENCE_GAPS_ONLY",
        "pair_count": 28, "currency_count": 8,
        "as_of_utc": NOW.isoformat(), "rows": rows,
        "published_macro_receipts_attested": False,
        "official_news_source_authenticated": False,
        "calendar_realtime_verified": False,
        "strength_causation_proven": False,
        "can_feed_live_radar": False,
        "trade_authorized": False, "publishable": False,
        "scheduler_enabled": False, "worker_enabled": False,
    }


def pair_frame(doc, pair="EUR/USD", frame="W1"):
    row = next(r for r in doc["rows"] if r["pair"] == pair)
    return row["horizons"][frame]


def claim(date="2026-11-02T12:00:00+00:00", event="US_CPI_X"):
    return {
        "currency": "USD", "event_id": event, "indicator": "CPI",
        "surprise_class": "ABOVE_CONSENSUS", "actual_minus_consensus": 0.3,
        "actual_synthetic": 3.3, "consensus_synthetic": 3.0,
        "released_at_utc": date,
        "consensus_captured_at_utc": (datetime.fromisoformat(date)
                                      - timedelta(days=1)).isoformat(),
        "release_verified": False,
        "strength_direction": "AGUARDAR",
    }


def build(report=None, raw=None):
    return build_ecb_macro_timing_bridge_lab(
        sample() if raw is None else raw,
        mock_dossier() if report is None else report, at=NOW,
    )


class ECBMacroTimingBridgeLabTests(unittest.TestCase):
    def test_complete_28x3_bridge_still_waits(self):
        report = mock_dossier()
        original = deepcopy(report)
        out = build(report)
        self.assertEqual(report, original)
        self.assertEqual((out["schema"], out["state"]),
                         (SCHEMA, "LAB_TEMPORAL_CONTEXT_ONLY"))
        self.assertEqual(out["pair_count"], 28)
        self.assertEqual({r["pair"] for r in out["rows"]}, set(OFFICIAL_PAIRS))
        for row in out["rows"]:
            self.assertEqual(row["operational_bias"], "AGUARDAR")
            self.assertFalse(row["trade_authorized"])
            for f in row["horizons"].values():
                self.assertFalse(f["matched_as_market_cause"])
                self.assertEqual(f["conclusion"], "AGUARDAR")

    def test_after_reference_release_cannot_explain_previous_reference(self):
        report = mock_dossier()
        pair_frame(report)["macro_surprise_claims"] = [claim("2026-11-04T12:00:00+00:00")]
        out = build(report)
        a = pair_frame(out)["calendar_alignments"]
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["calendar_relation"],
                         "DIVULGADO_DEPOIS_DA_REFERENCIA_BCE")
        self.assertFalse(a[0]["can_explain_ecb_move"])

    def test_inside_reference_calendar_dates_still_not_causal_proof(self):
        report = mock_dossier()
        pair_frame(report)["macro_surprise_claims"] = [claim()]
        a = pair_frame(build(report))["calendar_alignments"][0]
        self.assertEqual(a["calendar_relation"],
                         "DENTRO_DAS_DATAS_BCE_SEM_PROVA_DE_CAUSALIDADE")
        self.assertEqual(a["surprise_class_unattested"], "ABOVE_CONSENSUS")
        self.assertFalse(a["can_explain_ecb_move"])

    def test_fix_date_both_boundaries_have_unknown_intraday_order(self):
        report = mock_dossier()
        pair_frame(report, frame="D1")["macro_surprise_claims"] = [
            claim("2026-11-02T12:00:00+00:00", "START"),
            claim("2026-11-03T12:00:00+00:00", "END"),
        ]
        align = pair_frame(build(report), frame="D1")["calendar_alignments"]
        self.assertEqual({x["calendar_relation"] for x in align},
                         {"MESMO_DIA_DA_FIXACAO_ORDEM_INTRADIA_DESCONHECIDA"})

    def test_late_utc_news_belongs_to_next_european_calendar_date(self):
        report = mock_dossier()
        # 23:30 UTC on 3 Nov is already 00:30 CET on 4 Nov; the ECB
        # historical fixing ended on 3 Nov and cannot react to this news.
        pair_frame(report)["macro_surprise_claims"] = [
            claim("2026-11-03T23:30:00+00:00")
        ]
        align = pair_frame(build(report))["calendar_alignments"][0]
        self.assertEqual(align["calendar_relation"],
                         "DIVULGADO_DEPOIS_DA_REFERENCIA_BCE")

    def test_before_window_is_not_same_as_inside(self):
        report = mock_dossier()
        pair_frame(report)["macro_surprise_claims"] = [claim("2026-10-26T10:00:00+00:00")]
        a = pair_frame(build(report))["calendar_alignments"][0]
        self.assertEqual(a["calendar_relation"], "DIVULGADO_ANTES_DA_JANELA_BCE")

    def test_missing_ecb_month_history_with_macro_claim_refused(self):
        raw = xml_history([
            ("2026-10-27", FIXES), ("2026-11-02", FIXES),
            ("2026-11-03", {**FIXES, "USD": 1.11}),
        ])
        report = mock_dossier()
        pair_frame(report, frame="MN1")["macro_surprise_claims"] = [claim()]
        out = build(report, raw)
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assertEqual(out["reason"], "NOTICIAS_NAO_REPARAM_HISTORICO_BCE_AUSENTE")

    def test_missing_ecb_month_history_without_claim_is_exposed(self):
        raw = xml_history([
            ("2026-10-27", FIXES), ("2026-11-02", FIXES),
            ("2026-11-03", {**FIXES, "USD": 1.11}),
        ])
        out = build(raw=raw)
        self.assertEqual(pair_frame(out, frame="MN1")["relation"],
                         "HISTORICO_INSUFICIENTE")

    def test_false_authority_duplicate_pair_or_missing_pair_refused(self):
        for kind in ("causal_verified", "bad_as_of", "wrong_schema", "duplicate", "missing"):
            with self.subTest(kind=kind):
                report = mock_dossier()
                if kind == "causal_verified":
                    report["strength_causation_proven"] = True
                elif kind == "bad_as_of":
                    report["as_of_utc"] = (NOW - timedelta(hours=1)).isoformat()
                elif kind == "wrong_schema":
                    report["schema"] = "FUTURE_LIVE"
                elif kind == "duplicate":
                    report["rows"][1]["pair"] = report["rows"][0]["pair"]
                else:
                    report["rows"].pop()
                out = build(report)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertFalse(out["trade_authorized"])

    def test_future_forged_buy_or_duplicate_event_refused(self):
        for kind in ("future", "buy", "duplicate", "wrong_currency", "nan"):
            with self.subTest(kind=kind):
                report = mock_dossier()
                event = claim()
                if kind == "future":
                    event["released_at_utc"] = "2026-11-06T12:00:00+00:00"
                elif kind == "buy":
                    event["strength_direction"] = "BUY"
                elif kind == "wrong_currency":
                    event["currency"] = "GBP"
                elif kind == "nan":
                    event["actual_minus_consensus"] = float("nan")
                items = [event, deepcopy(event)] if kind == "duplicate" else [event]
                pair_frame(report)["macro_surprise_claims"] = items
                self.assertEqual(build(report)["state"], "LAB_BLOCKED")

    def test_post_release_consensus_or_unknown_snapshot_is_refused(self):
        for kind in ("missing", "same_time", "later", "naive", "invalid"):
            with self.subTest(kind=kind):
                report = mock_dossier()
                c = claim()
                if kind == "missing":
                    del c["consensus_captured_at_utc"]
                elif kind == "same_time":
                    c["consensus_captured_at_utc"] = c["released_at_utc"]
                elif kind == "later":
                    c["consensus_captured_at_utc"] = "2026-11-03T00:00:00+00:00"
                elif kind == "naive":
                    c["consensus_captured_at_utc"] = "2026-11-01T00:00:00"
                else:
                    c["consensus_captured_at_utc"] = "not-a-time"
                pair_frame(report)["macro_surprise_claims"] = [c]
                out = build(report)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(out["reason"], "CLAIM_MACRO_INVALIDA_DUPLICADA_OU_FUTURA")

    def test_numeric_difference_and_sign_label_are_not_blindly_trusted(self):
        for kind in ("actual_changed", "consensus_changed", "missing_actual",
                     "missing_consensus", "wrong_above", "wrong_below",
                     "infinite_actual", "boolean_actual"):
            with self.subTest(kind=kind):
                report = mock_dossier()
                c = claim()
                if kind == "actual_changed":
                    c["actual_synthetic"] = 2.8
                elif kind == "consensus_changed":
                    c["consensus_synthetic"] = 4.0
                elif kind == "missing_actual":
                    del c["actual_synthetic"]
                elif kind == "missing_consensus":
                    del c["consensus_synthetic"]
                elif kind == "wrong_above":
                    c["actual_minus_consensus"] = -0.3
                    c["actual_synthetic"] = 2.7
                elif kind == "wrong_below":
                    c["surprise_class"] = "BELOW_CONSENSUS"
                elif kind == "infinite_actual":
                    c["actual_synthetic"] = float("inf")
                else:
                    c["actual_synthetic"] = True
                pair_frame(report)["macro_surprise_claims"] = [c]
                out = build(report)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertFalse(out["trade_authorized"])

    def test_declared_consensus_date_visible_and_still_unattested(self):
        report = mock_dossier()
        c = claim()
        pair_frame(report)["macro_surprise_claims"] = [c]
        out = build(report)
        alignment = pair_frame(out)["calendar_alignments"][0]
        self.assertEqual(alignment["consensus_snapshot_declared_at_utc"],
                         "2026-11-01T12:00:00+00:00")
        self.assertFalse(alignment["consensus_snapshot_origin_authenticated"])
        self.assertFalse(alignment["can_explain_ecb_move"])

    def test_inline_surprise_can_be_nonzero_with_predeclared_deadband(self):
        report = mock_dossier()
        c = claim()
        c["surprise_class"] = "IN_LINE_WITH_CONSENSUS"
        c["actual_synthetic"] = 3.02
        c["actual_minus_consensus"] = 0.02
        pair_frame(report)["macro_surprise_claims"] = [c]
        self.assertEqual(build(report)["state"], "LAB_TEMPORAL_CONTEXT_ONLY")

    def test_same_macro_event_repeated_in_two_pairs_and_horizons_is_consistent(self):
        report = mock_dossier()
        c = claim()
        pair_frame(report, "EUR/USD", "D1")["macro_surprise_claims"] = [deepcopy(c)]
        pair_frame(report, "GBP/USD", "W1")["macro_surprise_claims"] = [deepcopy(c)]
        out = build(report)
        self.assertEqual(out["state"], "LAB_TEMPORAL_CONTEXT_ONLY")
        self.assertEqual(out["distinct_unattested_macro_events"], 1)
        self.assertTrue(out["cross_pair_macro_event_consistency_checked"])
        self.assertTrue(out["repeated_claims_are_not_independent_evidence"])
        self.assertFalse(out["cause_verified"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")

    def test_conflicting_values_of_same_event_are_refused_between_pairs(self):
        report = mock_dossier()
        first, second = claim(), claim()
        second["actual_synthetic"] = 3.5
        second["actual_minus_consensus"] = 0.5
        pair_frame(report, "EUR/USD", "W1")["macro_surprise_claims"] = [first]
        pair_frame(report, "GBP/USD", "W1")["macro_surprise_claims"] = [second]
        out = build(report)
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assertEqual(out["reason"],
                         "EVENTO_MACRO_CONTRADITORIO_ENTRE_PARES_OU_HORIZONTES")
        self.assertFalse(out["trade_authorized"])

    def test_same_event_cannot_change_currency_metadata_or_release_time(self):
        for kind in ("currency", "indicator", "unit", "previous", "release",
                     "consensus_time", "surprise_class"):
            with self.subTest(kind=kind):
                report = mock_dossier()
                first, second = claim(), claim()
                if kind == "currency":
                    second["currency"] = "GBP"
                elif kind == "indicator":
                    second["indicator"] = "NFP"
                elif kind == "unit":
                    second["unit"] = "PERCENT"
                elif kind == "previous":
                    second["previous_synthetic"] = 2.0
                elif kind == "release":
                    second["released_at_utc"] = "2026-11-02T13:00:00+00:00"
                elif kind == "consensus_time":
                    second["consensus_captured_at_utc"] = "2026-11-01T11:00:00+00:00"
                else:
                    second["surprise_class"] = "IN_LINE_WITH_CONSENSUS"
                pair_frame(report, "EUR/USD", "W1")["macro_surprise_claims"] = [first]
                pair_frame(report, "GBP/USD", "MN1")["macro_surprise_claims"] = [second]
                out = build(report)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(out["reason"],
                                 "EVENTO_MACRO_CONTRADITORIO_ENTRE_PARES_OU_HORIZONTES")
                self.assertFalse(out["publishable"])

    def test_same_event_repeated_with_equivalent_timezone_clock_is_allowed(self):
        report = mock_dossier()
        first, second = claim(), claim()
        second["released_at_utc"] = "2026-11-02T09:00:00-03:00"
        second["consensus_captured_at_utc"] = "2026-11-01T09:00:00-03:00"
        pair_frame(report, "EUR/USD", "W1")["macro_surprise_claims"] = [first]
        pair_frame(report, "GBP/USD", "MN1")["macro_surprise_claims"] = [second]
        out = build(report)
        self.assertEqual(out["state"], "LAB_TEMPORAL_CONTEXT_ONLY")
        self.assertEqual(out["distinct_unattested_macro_events"], 1)

    def test_different_event_ids_not_mistaken_for_documentary_conflicts(self):
        report = mock_dossier()
        pair_frame(report, "EUR/USD", "W1")["macro_surprise_claims"] = [claim(event="US_CPI_X")]
        pair_frame(report, "GBP/USD", "W1")["macro_surprise_claims"] = [claim(event="US_CPI_Y")]
        out = build(report)
        self.assertEqual(out["state"], "LAB_TEMPORAL_CONTEXT_ONLY")
        self.assertEqual(out["distinct_unattested_macro_events"], 2)
        self.assertFalse(out["trade_authorized"])

    def test_no_macro_claims_is_unknown_not_neutral(self):
        out = build()
        self.assertEqual(out["state"], "LAB_TEMPORAL_CONTEXT_ONLY")
        self.assertEqual(out["pair_horizons_with_relative_documentary_visibility_gaps"], 0)
        self.assertFalse(out["full_economic_calendar_coverage_verified"])
        self.assertFalse(out["two_sided_economic_explanation_proven"])
        for row in out["rows"]:
            for frame in row["horizons"].values():
                c = frame["macro_documentary_coverage"]
                self.assertEqual(c["state"], "SEM_ALEGACOES_DOCUMENTAIS_NO_DOSSIE")
                self.assertTrue(c["absence_of_claims_does_not_mean_no_real_release"])
                self.assertFalse(c["basis_for_operational_bias"])

    def test_only_usd_macro_evidence_is_not_a_two_currency_explanation(self):
        report = mock_dossier()
        pair_frame(report, "EUR/USD", "W1")["macro_surprise_claims"] = [claim()]
        out = build(report)
        coverage = pair_frame(out, "EUR/USD", "W1")["macro_documentary_coverage"]
        self.assertEqual(coverage["state"], "ALEGACOES_DOCUMENTAIS_APENAS_DE_UMA_MOEDA")
        self.assertEqual(coverage["base_unattested_event_count"], 0)
        self.assertEqual(coverage["quote_unattested_event_count"], 1)
        self.assertFalse(coverage["two_currencies_with_claims"])
        self.assertFalse(out["cause_verified"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")

    def test_both_currency_claims_are_still_unattested(self):
        report = mock_dossier()
        eur = claim(event="EU_CPI_X")
        eur["currency"] = "EUR"
        report_row = pair_frame(report, "EUR/USD", "W1")
        report_row["macro_surprise_claims"] = [claim(), eur]
        out = build(report)
        coverage = pair_frame(out, "EUR/USD", "W1")["macro_documentary_coverage"]
        self.assertEqual(coverage["state"],
                         "ALEGACOES_DOCUMENTAIS_DAS_DUAS_MOEDAS_NAO_AUTENTICADAS")
        self.assertTrue(coverage["two_currencies_with_claims"])
        self.assertFalse(coverage["macro_fundamentals_authenticated"])
        self.assertFalse(coverage["counterevidence_verified"])
        self.assertFalse(coverage["basis_for_operational_bias"])
        self.assertEqual(out["distinct_unattested_macro_events"], 2)

    def test_cross_pair_missing_usd_event_is_reported_not_hidden(self):
        report = mock_dossier()
        pair_frame(report, "EUR/USD", "W1")["macro_surprise_claims"] = [claim()]
        out = build(report)
        self.assertGreater(out["pair_horizons_with_relative_documentary_visibility_gaps"], 0)
        missing = pair_frame(out, "GBP/USD", "W1")["macro_documentary_coverage"]
        self.assertTrue(missing["incomplete_relative_to_supplied_pair_dossier"])
        self.assertEqual(missing["documentary_visibility_gaps"]["USD"]
                         ["missing_count_from_other_pairs_same_horizon"], 1)
        self.assertEqual(missing["documentary_visibility_gaps"]["USD"]
                         ["first_missing_event_ids"], ["US_CPI_X"])
        self.assertFalse(missing["basis_for_operational_bias"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")

    def test_repeated_event_in_two_pairs_does_not_become_two_independent_events(self):
        report = mock_dossier()
        pair_frame(report, "EUR/USD", "D1")["macro_surprise_claims"] = [claim()]
        pair_frame(report, "GBP/USD", "D1")["macro_surprise_claims"] = [claim()]
        out = build(report)
        self.assertEqual(out["state"], "LAB_TEMPORAL_CONTEXT_ONLY")
        self.assertEqual(out["supplied_macro_events_by_currency_and_horizon"]
                         ["D1"]["USD"], 1)
        self.assertEqual(out["distinct_unattested_macro_events"], 1)
        self.assertTrue(out["repeated_claims_are_not_independent_evidence"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")

    def test_missing_ecb_reference_has_no_fabricated_documentary_coverage(self):
        raw = xml_history([
            ("2026-10-27", FIXES), ("2026-11-02", FIXES),
            ("2026-11-03", {**FIXES, "USD": 1.11}),
        ])
        out = build(raw=raw)
        missing = pair_frame(out, "EUR/USD", "MN1")["macro_documentary_coverage"]
        self.assertEqual(missing["state"], "SEM_ALEGACOES_DOCUMENTAIS_NO_DOSSIE")
        self.assertFalse(missing["basis_for_operational_bias"])
        self.assertFalse(missing["incomplete_relative_to_supplied_pair_dossier"])

    def test_no_network_cost_cron_worker_or_deploy(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            out = build()
        self.assertEqual((out["external_http_requests"], out["new_cost_brl"]), (0, 0))
        for flag in ("cause_verified", "trade_authorized", "publishable",
                     "scheduler_enabled", "worker_enabled", "can_feed_live_radar",
                     "intraday_reference_fix_time_verified"):
            self.assertFalse(out[flag])


if __name__ == "__main__":
    unittest.main()
