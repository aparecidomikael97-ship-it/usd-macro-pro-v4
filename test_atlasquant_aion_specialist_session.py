import json
import socket
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_specialist_evidence import read_specialist_evidence
from atlasquant_aion_specialist_session import ORIGINS, build_specialist_session_snapshot
from atlasquant_aion_specialists import SPECIALIST_MODULES
from atlasquant_fx_universe import OFFICIAL_PAIRS


NOW = datetime.fromtimestamp(10_000, tz=timezone.utc)
FRESH_AT = NOW.isoformat()
STALE_AT = datetime.fromtimestamp(1_000, tz=timezone.utc).isoformat()


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


def fresh_session(**slices):
    payload = {
        "origin": "SESSION",
        "observed_at": FRESH_AT,
        "ttl_seconds": 3600,
    }
    payload.update(slices)
    return payload


class SpecialistSessionSnapshotTests(unittest.TestCase):
    def test_missing_snapshot_stays_unknown(self):
        for session in (None, {}):
            if session is None:
                reading = read_specialist_evidence("market")
            else:
                reading = read_specialist_evidence("market", session=session, now=NOW)
            self.assertEqual(reading["answer_truth"], "UNKNOWN")
            self.assertFalse(reading["answers_user_question"])
            self.assertNotIn("top_10", reading["observations"])
            self.assertNotIn("price", reading["observations"])
        absent = read_specialist_evidence("macro", session=fresh_session(), now=NOW)
        self.assertEqual(absent["answer_truth"], "UNKNOWN")
        self.assertEqual(absent["input_state"], "ABSENT")
        self.assertEqual(absent["observations"]["state"], "DADOS INSUFICIENTES")

    def test_valid_scanner_is_readable_without_price_or_top10(self):
        raw = complete_result()
        raw["price"] = 1.9876
        raw["token"] = "super-secret-token-value"
        reading = read_specialist_evidence(
            "market",
            session=fresh_session(
                origin="PERSISTED_SCANNER",
                scanner={"persisted_results": {"EUR/USD": raw}},
            ),
            now=NOW,
        )
        blob = json.dumps(reading, ensure_ascii=False)
        self.assertEqual(reading["input_state"], "VALID")
        self.assertEqual(reading["answer_truth"], "CONFIRMED")
        self.assertEqual(reading["truth_state"], "CONFIRMED")
        self.assertEqual(reading["freshness"], "FRESH")
        self.assertEqual(reading["origin"], "PERSISTED_SCANNER")
        self.assertTrue(reading["used_as_current_fact"])
        self.assertFalse(reading["answers_user_question"])
        self.assertEqual(reading["observations"]["observed_pairs"][0]["pair"], "EUR/USD")
        self.assertEqual(reading["observations"]["observed_pairs"][0]["queue_status"], "FRESH")
        self.assertFalse(reading["observations"]["profit_probability"])
        self.assertFalse(reading["observations"]["score_is_profit_probability"])
        self.assertNotIn("top_10", reading["observations"])
        self.assertNotIn("price", reading["observations"])
        self.assertNotIn("1.9876", blob)
        self.assertNotIn("super-secret-token-value", blob)
        self.assertFalse(reading["network_called"])
        self.assertFalse(reading["real_orders_enabled"])

    def test_stale_scanner_is_not_current_truth(self):
        reading = read_specialist_evidence(
            "market",
            session={
                "origin": "PERSISTED_SCANNER",
                "observed_at": STALE_AT,
                "ttl_seconds": 60,
                "scanner": {"persisted_results": {"EUR/USD": complete_result(ts=1_000)}},
            },
            now=NOW,
        )
        self.assertEqual(reading["input_state"], "STALE")
        self.assertEqual(reading["freshness"], "STALE")
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertEqual(reading["truth_state"], "UNKNOWN")
        self.assertFalse(reading["used_as_current_fact"])
        self.assertEqual(reading["observations"]["observed_pairs"], [])
        self.assertNotIn("BUY", reading["summary"])
        self.assertNotIn("top_10", reading["observations"])

    def test_conflicting_scanner_keeps_both_sides(self):
        reading = read_specialist_evidence(
            "market",
            session=fresh_session(
                origin="PERSISTED_SCANNER",
                scanner={
                    "persisted_results": {
                        "EUR/USD": [
                            complete_result(h4="BUY"),
                            complete_result(h4="SELL", source="other-feed"),
                        ]
                    }
                },
            ),
            now=NOW,
        )
        blob = json.dumps(reading["conflicts"], ensure_ascii=False)
        self.assertEqual(reading["input_state"], "CONFLICTING")
        self.assertEqual(reading["conflict_state"], "CONFLICT")
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertFalse(reading["used_as_current_fact"])
        self.assertIn("BUY", blob)
        self.assertIn("SELL", blob)
        self.assertTrue(reading["conflicts"])
        self.assertIsNone(reading["conflicts"][0]["chosen"])
        self.assertNotIn("top_10", reading["observations"])

    def test_ranking_absence_does_not_create_top10_and_exact_ten_can_be_read(self):
        missing = read_specialist_evidence(
            "market",
            session=fresh_session(
                scanner={"persisted_results": {"EUR/USD": complete_result()}},
            ),
            now=NOW,
        )
        self.assertNotIn("top_10", missing["observations"])
        short = read_specialist_evidence(
            "market",
            session=fresh_session(
                origin="RADAR",
                radar={
                    "origin": "RADAR",
                    "ranking": [
                        {"pair": pair, "data_ready": True, "score": 50}
                        for pair in OFFICIAL_PAIRS[:9]
                    ],
                },
            ),
            now=NOW,
        )
        self.assertNotIn("top_10", short["observations"])
        self.assertEqual(len(short["observations"]["observed_ranking"]), 9)
        ranked = read_specialist_evidence(
            "market",
            session=fresh_session(
                origin="RADAR",
                radar={
                    "origin": "RADAR",
                    "ranking": [
                        {"pair": pair, "data_ready": True, "score": index}
                        for index, pair in enumerate(OFFICIAL_PAIRS[:10])
                    ],
                },
            ),
            now=NOW,
        )
        self.assertEqual(ranked["observations"]["top_10"], list(OFFICIAL_PAIRS[:10]))
        self.assertEqual(len(ranked["observations"]["top_10"]), 10)
        self.assertFalse(ranked["observations"]["profit_probability"])

    def test_macro_insufficient_and_conflict_do_not_invent_a_bias(self):
        insufficient = read_specialist_evidence(
            "macro",
            session=fresh_session(
                macro={"currency_rows": [], "events": [{"event": "CPI", "impact": "high", "currency": "USD"}]},
                calendar={"events": [{"event": "Payroll", "currency": "USD", "time": "12:30"}]},
            ),
            now=NOW,
        )
        self.assertEqual(insufficient["observations"]["state"], "DADOS INSUFICIENTES")
        self.assertFalse(insufficient["observations"]["data_sufficient"])
        self.assertEqual(insufficient["answer_truth"], "UNKNOWN")
        self.assertFalse(insufficient["observations"]["live_calendar_consulted"])
        conflict = read_specialist_evidence(
            "macro",
            session=fresh_session(macro={
                "currency_rows": [
                    {"currency": "USD", "score": 80, "source": "a"},
                    {"currency": "USD", "score": 40, "source": "b"},
                    {"currency": "EUR", "score": 55, "source": "a"},
                ],
            }),
            now=NOW,
        )
        blob = json.dumps(conflict["conflicts"])
        self.assertEqual(conflict["input_state"], "CONFLICTING")
        self.assertEqual(conflict["observations"]["state"], "DADOS INSUFICIENTES")
        self.assertIn("80", blob)
        self.assertIn("40", blob)
        self.assertIsNone(conflict["conflicts"][0]["chosen"])
        self.assertNotIn("mais fortes", conflict["summary"])

    def test_stale_macro_is_not_current(self):
        reading = read_specialist_evidence(
            "macro",
            session={
                "origin": "SESSION",
                "observed_at": STALE_AT,
                "ttl_seconds": 60,
                "macro": {"currency_rows": [{"currency": "USD", "score": 80}, {"currency": "EUR", "score": 20}]},
            },
            now=NOW,
        )
        self.assertEqual(reading["freshness"], "STALE")
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertFalse(reading["used_as_current_fact"])
        self.assertNotIn("INFORMATIVO", reading["summary"])

    def test_ict_reads_recorded_evidence_and_keeps_ppr_blocked(self):
        metrics = {
            "timeframe": "H1",
            "samples": 20,
            "win_rate_pct": 55,
            "expectancy_r": 0.2,
            "profit_factor": 1.2,
            "max_drawdown_r": 3,
            "net_result": 4,
            "source": "session-backtest",
        }
        reading = read_specialist_evidence(
            "ict",
            session=fresh_session(ict={
                "evidence_rows": [
                    {"setup_id": "fvg", **metrics},
                    {"setup_id": "ppr", **metrics},
                ],
            }),
            now=NOW,
        )
        self.assertEqual(reading["input_state"], "VALID")
        self.assertIn("ppr", reading["observations"]["blocked_setups"])
        self.assertTrue(reading["observations"]["ppr_blocked"])
        self.assertGreater(reading["observations"]["recorded_setups"], 0)
        self.assertFalse(reading["observations"]["runs_backtest"])
        self.assertFalse(reading["real_orders_enabled"])

    def test_admin_does_not_infer_production_from_empty_checkpoint(self):
        absent = read_specialist_evidence("admin", session=fresh_session(), now=NOW)
        self.assertEqual(absent["answer_truth"], "UNKNOWN")
        self.assertFalse(absent["observations"]["checkpoint_supplied"])
        self.assertFalse(absent["observations"]["production_inferred_from_empty"])
        supplied = read_specialist_evidence(
            "admin",
            session=fresh_session(origin="CHECKPOINT", checkpoint={}),
            now=NOW,
        )
        self.assertTrue(supplied["observations"]["checkpoint_supplied"])
        self.assertFalse(supplied["observations"]["production_inferred_from_empty"])
        self.assertIn("não infere", supplied["summary"])
        self.assertFalse(supplied["observations"]["automatic_approval"])

    def test_real_trade_stays_denied_for_every_specialist(self):
        session = fresh_session(real_trade=True, approved=True)
        for specialist in SPECIALIST_MODULES:
            reading = read_specialist_evidence(specialist, session=session, now=NOW)
            self.assertFalse(reading["real_orders_enabled"])
            self.assertFalse(reading["permissions_expanded"])
            self.assertFalse(reading["executes_action"])
            self.assertFalse(reading["answers_user_question"])
        core = read_specialist_evidence("core", session=session, now=NOW)
        self.assertFalse(core["observations"]["real_trade_allowed"])
        self.assertEqual(core["observations"]["risk"], "REAL_TRADING")

    def test_no_network_or_provider_is_called(self):
        source = Path("atlasquant_aion_specialist_session.py").read_text(encoding="utf-8")
        for token in ("requests", "urllib", "httpx", "urlopen", "load_research_evidence", "openai", "socket"):
            self.assertNotIn(token, source)
        self.assertEqual(
            set(ORIGINS),
            {"SESSION", "CHECKPOINT", "PERSISTED_SCANNER", "RESEARCH_EVIDENCE", "RADAR", "LOCAL_STATE"},
        )

        def blocked(*_args, **_kwargs):
            raise AssertionError("network call")

        original = socket.socket
        socket.socket = blocked
        try:
            session = fresh_session(
                origin="RESEARCH_EVIDENCE",
                scanner={"persisted_results": {"EUR/USD": complete_result()}},
                research={"records": [{"strategy": "FVG", "source": "session", "pair": "EUR/USD"}]},
                studio={"providers": {"transcription": True}},
            )
            for specialist in SPECIALIST_MODULES:
                reading = read_specialist_evidence(specialist, session=session, now=NOW)
                self.assertFalse(reading["network_called"])
                self.assertFalse(reading["provider_called"])
                self.assertFalse(reading["tool_called"])
        finally:
            socket.socket = original
        research = read_specialist_evidence(
            "research",
            session=fresh_session(
                origin="RESEARCH_EVIDENCE",
                research={"origin": "RESEARCH_EVIDENCE", "records": [{"strategy": "FVG", "source": "session"}]},
            ),
            now=NOW,
        )
        self.assertEqual(research["origin"], "RESEARCH_EVIDENCE")
        self.assertEqual(research["observations"]["records_loaded"], 1)
        self.assertFalse(research["observations"]["web_research_executed"])
        self.assertFalse(research["observations"]["external_model_executed"])
        self.assertFalse(research["observations"]["remote_store_consulted"])

    def test_studio_absence_is_not_a_not_configured_fact(self):
        reading = read_specialist_evidence("studio", session=fresh_session(), now=NOW)
        self.assertEqual(reading["input_state"], "ABSENT")
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertNotIn("NOT_CONFIGURED", json.dumps(reading))
        self.assertFalse(reading["observations"]["providers_inferred"])

    def test_snapshot_contract_reuses_loaded_checkpoint_without_adding_origin(self):
        snapshot = build_specialist_session_snapshot(None)
        self.assertFalse(snapshot["present"])
        self.assertFalse(snapshot["network_called"])
        built = build_specialist_session_snapshot(fresh_session(checkpoint={"updated_at": FRESH_AT}))
        self.assertTrue(built["present"])
        self.assertTrue(built["slices"]["checkpoint"]["present"])
        self.assertFalse(built["slices"]["scanner"]["present"])


if __name__ == "__main__":
    unittest.main()
