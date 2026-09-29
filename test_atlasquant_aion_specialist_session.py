import json
import socket
import unittest
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_specialist_evidence import read_specialist_evidence
from atlasquant_aion_specialist_session import (
    ORIGINS,
    _NORMALIZATION_NODE_BUDGET,
    _PROVIDER_FLAGS,
    build_specialist_session_snapshot,
)
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


class CountingMap(Mapping):
    """Mapping whose iteration count is observable. Values are not pre-materialized."""

    def __init__(self, count, value=1, first_key=None, first_value=None):
        self.count = count
        self.value = value
        self.first_key = first_key
        self.first_value = first_value
        self.yielded = 0

    def __iter__(self):
        if self.first_key is not None:
            self.yielded += 1
            yield self.first_key
            remaining = self.count - 1
        else:
            remaining = self.count
        for index in range(remaining):
            self.yielded += 1
            yield f"k{index}"

    def __getitem__(self, key):
        if self.first_key is not None and key == self.first_key:
            return self.first_value
        return self.value

    def __len__(self):
        return self.count


class BranchMap(Mapping):
    def __init__(self, children):
        self.children = children

    def __iter__(self):
        yield from self.children

    def __getitem__(self, key):
        return self.children[key]

    def __len__(self):
        return len(self.children)


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
        self.assertEqual(absent["origin"], "SESSION")
        self.assertEqual(absent["observations"]["state"], "DADOS INSUFICIENTES")
        checkpoint = read_specialist_evidence(
            "market",
            session=fresh_session(origin="CHECKPOINT"),
            now=NOW,
        )
        self.assertEqual(checkpoint["origin"], "CHECKPOINT")
        self.assertEqual(checkpoint["answer_truth"], "UNKNOWN")

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

    def test_wide_mapping_stops_inside_budget_and_is_not_current_fact(self):
        wide = CountingMap(
            10_000,
            value=complete_result(h4="BUY"),
            first_key="EUR/USD",
            first_value=complete_result(h4="BUY"),
        )
        session = fresh_session(
            origin="PERSISTED_SCANNER",
            scanner={"persisted_results": wide},
        )
        snapshot = build_specialist_session_snapshot(session)
        scanner = snapshot["slices"]["scanner"]
        stored = scanner["payload"]["persisted_results"]
        self.assertEqual(scanner["normalization_state"], "INCOMPLETE")
        self.assertLess(wide.yielded, wide.count)
        self.assertLessEqual(wide.yielded, _NORMALIZATION_NODE_BUDGET + 1)
        self.assertLess(len(stored), wide.count)
        self.assertLessEqual(len(stored), _NORMALIZATION_NODE_BUDGET)
        reading = read_specialist_evidence("market", session=snapshot, now=NOW)
        self.assertEqual(reading["observations"]["normalization_state"], "INCOMPLETE")
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertEqual(reading["input_state"], "UNVERIFIED")
        self.assertFalse(reading["used_as_current_fact"])
        self.assertNotIn("BUY", reading["summary"])
        self.assertEqual(reading["observations"].get("observed_pairs", []), [])
        self.assertFalse(reading["network_called"])
        self.assertFalse(reading["provider_called"])

    def test_branched_mapping_shares_one_budget(self):
        left = CountingMap(4_000, value=1)
        right = CountingMap(4_000, value=1)
        session = fresh_session(
            origin="PERSISTED_SCANNER",
            scanner={
                "persisted_results": {
                    "EUR/USD": complete_result(h4="BUY"),
                    "overflow": BranchMap({"left": left, "right": right}),
                }
            },
        )
        snapshot = build_specialist_session_snapshot(session)
        self.assertEqual(snapshot["slices"]["scanner"]["normalization_state"], "INCOMPLETE")
        self.assertLess(left.yielded, left.count)
        self.assertLess(right.yielded, right.count)
        self.assertGreater(left.yielded, 0)
        self.assertLessEqual(left.yielded + right.yielded, _NORMALIZATION_NODE_BUDGET + 3)
        self.assertLess(left.yielded + right.yielded, _NORMALIZATION_NODE_BUDGET * 2)
        reading = read_specialist_evidence("market", session=snapshot, now=NOW)
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertEqual(reading["input_state"], "UNVERIFIED")
        self.assertFalse(reading["used_as_current_fact"])
        self.assertNotIn("BUY", reading["summary"])
        for conflict in reading["conflicts"]:
            self.assertIsNone(conflict.get("chosen"))

    def test_version_301_conflict_does_not_confirm_the_buy_prefix(self):
        versions = [complete_result(h4="BUY") for _ in range(300)]
        versions.append(complete_result(h4="SELL", source="other-feed"))
        session = fresh_session(
            origin="PERSISTED_SCANNER",
            scanner={"persisted_results": {"EUR/USD": versions}},
        )
        snapshot = build_specialist_session_snapshot(session)
        self.assertEqual(snapshot["slices"]["scanner"]["normalization_state"], "INCOMPLETE")
        reading = read_specialist_evidence("market", session=session, now=NOW)
        self.assertFalse(reading["used_as_current_fact"])
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertEqual(reading["input_state"], "UNVERIFIED")
        self.assertNotEqual(reading["input_state"], "VALID")
        self.assertNotIn("BUY", reading["summary"])
        self.assertNotIn("SELL", reading["summary"])
        self.assertEqual(reading["observations"].get("observed_pairs", []), [])
        self.assertEqual(reading["observations"]["normalization_state"], "INCOMPLETE")
        for conflict in reading["conflicts"]:
            self.assertIsNone(conflict.get("chosen"))
        blob = json.dumps(reading, ensure_ascii=False)
        self.assertNotIn('"chosen": "BUY"', blob)
        self.assertNotIn('"chosen": "SELL"', blob)
        replayed = read_specialist_evidence("market", session=snapshot, now=NOW)
        self.assertFalse(replayed["used_as_current_fact"])
        self.assertEqual(replayed["answer_truth"], "UNKNOWN")
        self.assertEqual(replayed["input_state"], "UNVERIFIED")
        self.assertFalse(replayed["network_called"])
        self.assertFalse(replayed["provider_called"])

    def test_studio_provider_matrix_accepts_only_real_bools(self):
        invalid_values = ("false", "UNKNOWN", "STALE", None, 0, 1, "")
        for value in (True, False, *invalid_values):
            reading = read_specialist_evidence(
                "studio",
                session=fresh_session(
                    origin="LOCAL_STATE",
                    studio={"origin": "LOCAL_STATE", "providers": {"transcription": value}},
                ),
                now=NOW,
            )
            providers = reading["observations"]["providers"]
            self.assertFalse(reading["observations"]["publishing_executed"])
            self.assertFalse(reading["observations"]["executes_external_call"])
            self.assertFalse(reading["observations"]["providers_inferred"])
            self.assertFalse(reading["network_called"])
            self.assertFalse(reading["provider_called"])
            if value is True:
                self.assertEqual(providers.get("transcription"), "CONFIGURED")
                self.assertTrue(reading["used_as_current_fact"])
                self.assertEqual(reading["answer_truth"], "CONFIRMED")
            elif value is False:
                self.assertEqual(providers.get("transcription"), "NOT_CONFIGURED")
                self.assertTrue(reading["used_as_current_fact"])
                self.assertEqual(reading["answer_truth"], "CONFIRMED")
            else:
                self.assertNotIn("transcription", providers)
                self.assertNotEqual(providers.get("transcription"), "CONFIGURED")
                self.assertNotEqual(providers.get("transcription"), "NOT_CONFIGURED")
                self.assertFalse(reading["used_as_current_fact"])
                self.assertEqual(reading["answer_truth"], "UNKNOWN")
                blob = json.dumps(reading, ensure_ascii=False)
                self.assertNotIn("CONFIGURED", blob)
                self.assertNotIn("NOT_CONFIGURED", blob)

        partial = read_specialist_evidence(
            "studio",
            session=fresh_session(
                origin="LOCAL_STATE",
                studio={
                    "origin": "LOCAL_STATE",
                    "providers": {"transcription": True, "image": False},
                },
            ),
            now=NOW,
        )
        partial_providers = partial["observations"]["providers"]
        self.assertEqual(partial_providers.get("transcription"), "CONFIGURED")
        self.assertEqual(partial_providers.get("image"), "NOT_CONFIGURED")
        for name in _PROVIDER_FLAGS:
            if name not in {"transcription", "image"}:
                self.assertNotIn(name, partial_providers)
        self.assertFalse(partial["observations"]["publishing_executed"])
        self.assertFalse(partial["observations"]["executes_external_call"])
        self.assertLess(len(partial_providers), len(_PROVIDER_FLAGS))

        mixed = read_specialist_evidence(
            "studio",
            session=fresh_session(
                origin="LOCAL_STATE",
                studio={
                    "origin": "LOCAL_STATE",
                    "providers": {"transcription": True, "video_render": "false"},
                },
            ),
            now=NOW,
        )
        self.assertNotIn("video_render", mixed["observations"]["providers"])
        self.assertNotEqual(mixed["observations"]["providers"].get("video_render"), "CONFIGURED")
        self.assertNotEqual(mixed["observations"]["providers"].get("video_render"), "NOT_CONFIGURED")
        self.assertFalse(mixed["used_as_current_fact"])
        self.assertEqual(mixed["answer_truth"], "UNKNOWN")
        self.assertFalse(mixed["observations"]["publishing_executed"])
        self.assertFalse(mixed["observations"]["executes_external_call"])

        ready_flags = {name: True for name in _PROVIDER_FLAGS}
        full = read_specialist_evidence(
            "studio",
            session=fresh_session(
                origin="LOCAL_STATE",
                studio={"origin": "LOCAL_STATE", "providers": ready_flags},
            ),
            now=NOW,
        )
        for name in ("transcription", "video_render", "image", "aion_voice", "mikael_voice"):
            self.assertEqual(full["observations"]["providers"].get(name), "CONFIGURED")
        self.assertTrue(full["used_as_current_fact"])
        self.assertEqual(full["answer_truth"], "CONFIRMED")
        self.assertFalse(full["observations"]["publishing_executed"])
        self.assertFalse(full["observations"]["executes_external_call"])

        consent_blocked = dict(ready_flags)
        consent_blocked["mikael_consent"] = False
        consented = read_specialist_evidence(
            "studio",
            session=fresh_session(
                origin="LOCAL_STATE",
                studio={"origin": "LOCAL_STATE", "providers": consent_blocked},
            ),
            now=NOW,
        )
        self.assertEqual(consented["observations"]["providers"].get("mikael_voice"), "NOT_CONFIGURED")
        self.assertEqual(consented["observations"]["providers"].get("transcription"), "CONFIGURED")
        self.assertFalse(consented["observations"]["publishing_executed"])

        stale_flag = dict(ready_flags)
        stale_flag["transcription"] = "STALE"
        blocked = read_specialist_evidence(
            "studio",
            session=fresh_session(
                origin="LOCAL_STATE",
                studio={"origin": "LOCAL_STATE", "providers": stale_flag},
            ),
            now=NOW,
        )
        self.assertNotEqual(blocked["observations"]["providers"].get("transcription"), "CONFIGURED")
        self.assertNotEqual(blocked["observations"]["providers"].get("transcription"), "NOT_CONFIGURED")
        self.assertFalse(blocked["used_as_current_fact"])
        self.assertEqual(blocked["answer_truth"], "UNKNOWN")
        self.assertFalse(blocked["observations"]["publishing_executed"])
        self.assertFalse(blocked["observations"]["executes_external_call"])
        self.assertFalse(blocked["provider_called"])


if __name__ == "__main__":
    unittest.main()
