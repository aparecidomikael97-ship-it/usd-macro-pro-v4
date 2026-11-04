"""Point-in-time firewall between ECB reference moves and macro claims."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
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
        "released_at_utc": date, "release_verified": False,
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
