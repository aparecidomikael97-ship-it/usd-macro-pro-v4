import json
import socket
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from atlasquant_aion_business import new_product_candidate
from atlasquant_aion_operations import new_task
from atlasquant_aion_session_memory import (
    SESSION_WHITELIST,
    _strip,
    adapt_loaded_memory_to_specialist_snapshot,
    collect_resident_specialist_inputs,
    evidence_scope_label,
)
from atlasquant_aion_specialist_evidence import read_specialist_evidence
from atlasquant_fx_universe import OFFICIAL_PAIRS


NOW = datetime.fromtimestamp(10_000, tz=timezone.utc)
FRESH_AT = NOW.isoformat()
STALE_AT = datetime.fromtimestamp(1_000, tz=timezone.utc).isoformat()
SECRET = "super-secret-token-value"
COOKIE = "session-cookie-value"
HEADER = "Bearer secret-header"


def complete_result(ts=10_000.0, source="Twelve Data", h4="BUY"):
    return {
        "processado_em": ts,
        "source": source,
        "tecnico": {
            "disponivel": True,
            "h4": {"status": h4},
            "h1": {"status": "BUY"},
            "m15": {"status": "WAIT"},
        },
    }


def read(specialist, loaded):
    snapshot = adapt_loaded_memory_to_specialist_snapshot(loaded, now=NOW)
    return snapshot, read_specialist_evidence(specialist, session=snapshot, now=NOW)


class ResidentMemoryAdapterTests(unittest.TestCase):
    def test_loaded_memory_reaches_the_selected_specialist(self):
        task = new_task("Revisar checkpoint", domain="admin", created_at=FRESH_AT)
        task["status"] = "WAITING_APPROVAL"
        task["approval"]["required"] = True
        product = new_product_candidate("Plano local", created_at=FRESH_AT)
        snapshot, market = read("market", {
            "scanner": {
                "observed_at": FRESH_AT,
                "ttl_seconds": 3600,
                "persisted_results": {"EUR/USD": complete_result()},
                "token": SECRET,
                "price": 1.2345,
            },
            "checkpoint": {
                "updated_at": FRESH_AT,
                "ttl_seconds": 3600,
                "operating": {"tasks": [task]},
                "continuity": {"missions": [{"mission_id": "m1", "title": "Continuidade local"}]},
                "business": {"products": [product]},
                "cookie": COOKIE,
                "headers": {"Authorization": HEADER},
            },
            "research_records": {
                "observed_at": FRESH_AT,
                "ttl_seconds": 3600,
                "records": [{"strategy": "FVG", "source": "session", "pair": "EUR/USD"}],
            },
        })
        self.assertEqual(market["input_state"], "VALID")
        self.assertEqual(market["origin"], "PERSISTED_SCANNER")
        self.assertEqual(market["observations"]["observed_pairs"][0]["pair"], "EUR/USD")
        self.assertFalse(market["answers_user_question"])
        self.assertIn("EUR/USD", evidence_scope_label(market))
        admin = read_specialist_evidence("admin", session=snapshot, now=NOW)
        self.assertTrue(admin["observations"]["checkpoint_supplied"])
        self.assertGreater(admin["observations"]["pending_in_this_call"], 0)
        self.assertFalse(admin["observations"]["production_inferred_from_empty"])
        self.assertIn("Continuidade local", json.dumps(snapshot["slices"]["checkpoint"]["payload"], ensure_ascii=False))
        research = read_specialist_evidence("research", session=snapshot, now=NOW)
        self.assertEqual(research["observations"]["records_loaded"], 1)
        self.assertFalse(research["observations"]["web_research_executed"])
        business = read_specialist_evidence("business", session=snapshot, now=NOW)
        self.assertGreater(business["observations"]["total"], 0)
        self.assertFalse(business["observations"]["publication_executed"])
        blob = json.dumps(snapshot, ensure_ascii=False)
        self.assertNotIn(SECRET, blob)
        self.assertNotIn(COOKIE, blob)
        self.assertNotIn(HEADER, blob)
        self.assertNotIn("1.2345", blob)

    def test_resident_list_sanitizer_stops_at_300_items(self):
        class GuardedList(list):
            def __iter__(self):
                for index in range(301):
                    if index>=300:
                        raise AssertionError("resident list consumed past bound")
                    yield {"index":index}

        cleaned=_strip(GuardedList())
        self.assertEqual(len(cleaned),300)
        self.assertEqual(cleaned[0]["index"],0)
        self.assertEqual(cleaned[-1]["index"],299)

    def test_absence_stays_unknown(self):
        for loaded in (None, {}):
            snapshot, reading = read("market", loaded)
            self.assertFalse(snapshot["slices"]["scanner"]["present"])
            self.assertFalse(snapshot["slices"]["radar"]["present"])
            self.assertEqual(reading["input_state"], "ABSENT")
            self.assertEqual(reading["answer_truth"], "UNKNOWN")
            self.assertNotIn("top_10", reading["observations"])
            self.assertFalse(reading["answers_user_question"])

    def test_stale_resident_scanner_is_not_current(self):
        _, reading = read("market", {
            "scanner": {
                "observed_at": STALE_AT,
                "ttl_seconds": 60,
                "persisted_results": {"EUR/USD": complete_result(ts=1_000)},
            },
        })
        self.assertEqual(reading["input_state"], "STALE")
        self.assertEqual(reading["freshness"], "STALE")
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertFalse(reading["used_as_current_fact"])
        self.assertEqual(reading["observations"]["observed_pairs"], [])
        self.assertNotIn("top_10", reading["observations"])

    def test_conflict_keeps_chosen_null(self):
        _, reading = read("market", {
            "scanner": {
                "observed_at": FRESH_AT,
                "ttl_seconds": 3600,
                "persisted_results": {
                    "EUR/USD": [
                        complete_result(h4="BUY"),
                        complete_result(h4="SELL", source="other-feed"),
                    ],
                },
            },
        })
        self.assertEqual(reading["input_state"], "CONFLICTING")
        self.assertTrue(reading["conflicts"])
        self.assertIsNone(reading["conflicts"][0]["chosen"])
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertNotIn("top_10", reading["observations"])

    def test_semester_stamp_stays_unverified(self):
        snapshot, reading = read("macro", {
            "boot": {"generated_at": "1º semestre 2026", "state": "CACHED_SNAPSHOT"},
            "macro_eua": {
                "observed_at": "2026-S1",
                "Juros do Fed": 4.25,
                "IPC anual": 2.9,
            },
        })
        self.assertEqual(reading["freshness"], "UNVERIFIED")
        self.assertEqual(reading["truth_state"], "UNKNOWN")
        self.assertEqual(reading["observed_at"], "")
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertEqual(snapshot["slices"]["macro"]["payload"]["time_mark_state"], "UNVERIFIED")
        blob = json.dumps(snapshot, ensure_ascii=False)
        self.assertNotIn("2026-01-01", blob)
        self.assertNotIn("2026-06-30", blob)

    def test_missing_scanner_and_currency_ranking_do_not_create_top10(self):
        snapshot, reading = read("market", {
            "ranking": [
                {"Código": code, "Pontuação_Final": 80 - index}
                for index, code in enumerate(("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"))
            ],
            "pair_matrix_result": {
                "ready": True,
                "source": "live",
                "live_ready": False,
                "pairs_built": 3,
                "pairs_expected": 7,
            },
        })
        self.assertNotIn("top_10", reading["observations"])
        self.assertFalse(reading["observations"]["ranking_valid"])
        self.assertNotEqual(reading["answer_truth"], "CONFIRMED")
        radar = snapshot["slices"]["radar"]["payload"]
        self.assertTrue(radar["incomplete"])
        self.assertNotIn("ranking", radar)
        self.assertNotIn("price", radar)
        self.assertNotIn("Direção", json.dumps(radar))
        self.assertIn("TOP 10 não gerado", evidence_scope_label(reading))
        frame, frame_reading = read("market", {
            "ranking": pd.DataFrame([
                {"Código": "USD", "Pontuação_Final": 80, "token": SECRET},
                {"Código": "EUR", "Pontuação_Final": 70},
            ]),
        })
        self.assertFalse(frame["slices"]["radar"]["present"])
        self.assertNotIn("top_10", frame_reading["observations"])
        self.assertNotIn(SECRET, json.dumps(frame))

    def test_score_is_not_turned_into_a_probability(self):
        _, reading = read("market", {
            "radar_ranking": {
                "observed_at": FRESH_AT,
                "ttl_seconds": 3600,
                "ranking": [
                    {"pair": "EUR/USD", "data_ready": True, "score": 77},
                ],
            },
        })
        self.assertEqual(reading["observations"]["observed_ranking"][0]["score"], 77)
        self.assertFalse(reading["observations"]["profit_probability"])
        self.assertFalse(reading["observations"]["score_is_profit_probability"])
        self.assertNotIn("probability", reading["observations"])
        self.assertNotIn("top_10", reading["observations"])
        self.assertNotIn("0.77", json.dumps(reading))

    def test_insufficient_macro_stays_insufficient(self):
        _, reading = read("macro", {
            "macro_eua": {"Juros do Fed": 4.25, "IPC anual": 2.9},
            "macro_event": {
                "disponivel": True,
                "evento": "CPI",
                "impacto": "high",
                "data_txt": "horário não confirmado",
            },
            "fed": {"tom": "Neutro", "forca": 0.2},
        })
        self.assertEqual(reading["observations"]["state"], "DADOS INSUFICIENTES")
        self.assertFalse(reading["observations"]["data_sufficient"])
        self.assertFalse(reading["observations"]["live_calendar_consulted"])
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertGreaterEqual(reading["observations"]["supplied_events"], 1)

    def test_ppr_stays_blocked_for_loaded_lab_records(self):
        metrics = {
            "timeframe": "H1",
            "samples": 20,
            "win_rate_pct": 55,
            "expectancy_r": 0.2,
            "profit_factor": 1.2,
            "max_drawdown_r": 3,
            "net_result": 4,
            "source": "resident-backtest",
        }
        snapshot, reading = read("ict", {
            "evidence_rows": {
                "observed_at": FRESH_AT,
                "ttl_seconds": 3600,
                "evidence_rows": [
                    {"setup_id": "fvg", **metrics},
                    {"setup_id": "ppr", **metrics},
                ],
            },
        })
        self.assertTrue(reading["observations"]["ppr_blocked"])
        self.assertIn("ppr", reading["observations"]["blocked_setups"])
        self.assertFalse(reading["observations"]["runs_backtest"])
        self.assertFalse(reading["real_orders_enabled"])
        lab = read_specialist_evidence("lab", session=snapshot, now=NOW)
        self.assertTrue(lab["observations"]["ppr_blocked"])
        self.assertFalse(lab["observations"]["runs_backtest"])
        self.assertFalse(lab["observations"]["web_research_executed"])

    def test_checkpoint_feeds_admin_without_an_external_read(self):
        task = new_task("Missão já carregada", domain="secretary", created_at=FRESH_AT)
        task["status"] = "WAITING_APPROVAL"
        task["approval"]["required"] = True

        def blocked(*_args, **_kwargs):
            raise AssertionError("external checkpoint read")

        with patch("atlasquant_aion_memory.load_runtime_checkpoint", blocked):
            snapshot, reading = read("admin", {
                "checkpoint": {
                    "updated_at": FRESH_AT,
                    "ttl_seconds": 3600,
                    "operating": {"tasks": [task]},
                    "continuity": {"missions": [{"mission_id": "m-local", "title": "Já em memória"}]},
                    "invest": {"records": [{
                        "product": "Tesouro",
                        "asset_class": "Renda fixa",
                        "issuer": "Tesouro",
                        "source": "checkpoint",
                        "timestamp": FRESH_AT,
                    }]},
                },
            })
        self.assertTrue(reading["observations"]["checkpoint_supplied"])
        self.assertGreater(reading["observations"]["pending_in_this_call"], 0)
        self.assertFalse(reading["observations"]["production_inferred_from_empty"])
        self.assertFalse(reading["network_called"])
        invest = read_specialist_evidence("invest", session=snapshot, now=NOW)
        self.assertGreater(invest["observations"]["rows"], 0)
        self.assertFalse(invest["observations"]["automatic_orders"])

    def test_secrets_in_state_never_enter_the_snapshot(self):
        class SelectiveState:
            def get(self, key, default=None):
                if key == "aion_working_checkpoint_v2":
                    return {
                        "updated_at": FRESH_AT,
                        "password": "pw-value",
                        "api_key": "api-key-value",
                        "cookie": COOKIE,
                        "headers": {"Authorization": HEADER},
                    }
                if key not in SESSION_WHITELIST:
                    raise AssertionError(f"unexpected session read: {key}")
                return default

            def __iter__(self):
                raise AssertionError("session scan")

        loaded = collect_resident_specialist_inputs(
            SelectiveState(),
            {
                "GITHUB_TOKEN_HISTORICO": SECRET,
                "macro_eua": {"Juros do Fed": 4.25, "token": SECRET, "api_key": "api-key-value"},
                "carregar_macro_eua": lambda: (_ for _ in ()).throw(AssertionError("remote macro")),
            },
        )
        snapshot = adapt_loaded_memory_to_specialist_snapshot(loaded, now=NOW)
        blob = json.dumps({"loaded": loaded, "snapshot": snapshot}, ensure_ascii=False)
        for forbidden in (SECRET, COOKIE, HEADER, "pw-value", "api-key-value"):
            self.assertNotIn(forbidden, blob)
        self.assertIn("Juros do Fed", blob)

    def test_no_network_acquisition_is_required(self):
        source = Path("atlasquant_aion_session_memory.py").read_text(encoding="utf-8")
        for token in (
            "requests", "urllib", "httpx", "urlopen", "socket", "openai",
            "_github_get_json", "load_home_snapshot", "load_research_evidence",
            "load_runtime_checkpoint", "carregar_macro_eua", "_proximo_evento_macro",
        ):
            self.assertNotIn(token, source)
        app = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        start = app.index("_aion_specialist_snapshot = None")
        end = app.index("render_aion_admin_console(", start)
        block = app[start:end]
        for token in (
            "_github_get_json", "requests.", "_proximo_evento_macro",
            "carregar_macro_eua", "load_home_snapshot", "load_research_evidence",
            "load_runtime_checkpoint", "_build_aion_source_runtime_context",
            "_aion_source_mesh", "_aion_market_context", "_aion_live_events",
        ):
            self.assertNotIn(token, block)
        self.assertIn("specialist_snapshot=_aion_specialist_snapshot", app)
        admin = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("specialist_snapshot: Mapping[str, Any] | None = None", admin)
        self.assertIn("loaded_session_from_checkpoint(checkpoint)", admin)
        self.assertIn("input_state", admin)
        self.assertIn("evidência observada", admin)
        self.assertIn("answers_user_question", admin)

        def blocked(*_args, **_kwargs):
            raise AssertionError("network call")

        original = socket.socket
        socket.socket = blocked
        try:
            with patch("requests.get", blocked), patch("requests.post", blocked), \
                    patch("atlasquant_aion_memory.load_runtime_checkpoint", blocked), \
                    patch("atlasquant_research_evidence_store.load_research_evidence", blocked), \
                    patch("atlasquant_fast_startup.load_home_snapshot", blocked):
                snapshot, reading = read("market", {
                    "scanner": {
                        "observed_at": FRESH_AT,
                        "ttl_seconds": 3600,
                        "persisted_results": {"EUR/USD": complete_result()},
                    },
                })
        finally:
            socket.socket = original
        self.assertFalse(snapshot["network_called"])
        self.assertFalse(reading["network_called"])
        self.assertEqual(reading["observations"]["observed_pairs"][0]["pair"], "EUR/USD")
        self.assertFalse(reading["answers_user_question"])

    def test_runtime_snapshot_fallback_keeps_its_identity(self):
        snapshot, reading = read("market", {
            "pair_matrix_status": {
                "ready": True,
                "source": "runtime_snapshot",
                "live_ready": False,
                "pairs_built": 7,
                "pairs_expected": 7,
            },
            "runtime_snapshot": {
                "generated_at": FRESH_AT,
                "source": "runtime_snapshot",
                "fallback": True,
                "live_ready": False,
                "pair_names": ["EUR/USD", "GBP/USD"],
                "packs_observed": 2,
            },
            "source_mesh": {"market_live_confirmed": True, "market_state": "LIVE_CONFIRMED"},
        })
        radar = snapshot["slices"]["radar"]["payload"]
        self.assertEqual(radar["source"], "runtime_snapshot")
        self.assertTrue(radar["fallback"])
        self.assertFalse(radar["live_ready"])
        self.assertNotIn("ranking", radar)
        self.assertNotIn("top_10", reading["observations"])
        self.assertFalse(reading["used_as_current_fact"])
        self.assertFalse(reading["observations"]["price_invented"])
        self.assertNotIn("price", reading["observations"])

    def test_supplied_snapshot_is_not_rebuilt_from_new_inputs(self):
        original = adapt_loaded_memory_to_specialist_snapshot({
            "scanner": {
                "observed_at": FRESH_AT,
                "ttl_seconds": 3600,
                "persisted_results": {"EUR/USD": complete_result()},
            },
        }, now=NOW)
        again = adapt_loaded_memory_to_specialist_snapshot(original, now=NOW)
        self.assertEqual(again["slices"]["scanner"]["origin"], "PERSISTED_SCANNER")
        self.assertFalse(again["slices"]["macro"]["present"])
        self.assertFalse(again["network_called"])

    def test_exact_resident_ranking_can_be_read_without_padding(self):
        short, short_reading = read("market", {
            "radar_ranking": {
                "observed_at": FRESH_AT,
                "ttl_seconds": 3600,
                "ranking": [
                    {"pair": pair, "data_ready": True, "score": index}
                    for index, pair in enumerate(OFFICIAL_PAIRS[:9])
                ],
            },
        })
        self.assertNotIn("top_10", short_reading["observations"])
        self.assertEqual(len(short_reading["observations"]["observed_ranking"]), 9)
        self.assertFalse(short["slices"]["radar"]["payload"]["score_is_profit_probability"])
        _, ranked = read("market", {
            "radar_ranking": {
                "observed_at": FRESH_AT,
                "ttl_seconds": 3600,
                "ranking": [
                    {"pair": pair, "data_ready": True, "score": index}
                    for index, pair in enumerate(OFFICIAL_PAIRS[:10])
                ],
            },
        })
        self.assertEqual(ranked["observations"]["top_10"], list(OFFICIAL_PAIRS[:10]))
        self.assertFalse(ranked["observations"]["profit_probability"])
        self.assertFalse(ranked["answers_user_question"])


if __name__ == "__main__":
    unittest.main()
