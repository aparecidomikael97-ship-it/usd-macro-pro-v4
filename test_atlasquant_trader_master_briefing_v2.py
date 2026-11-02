"""Painel Mestre: cenário diário e semanal sem criar informações de mercado."""
import unittest
from datetime import datetime, timedelta, timezone
from html import unescape

from atlasquant_trader_economic_calendar import normalize_events, request_eodhd_daily
from atlasquant_trader_master_briefing_v2 import build_master_briefing
from atlasquant_trader_master_briefing_ui import (
    master_overview_cards, master_briefing_html, master_week_html,
)
from atlasquant_trader_radar_compact_ui import trader_radar_html


BRT = timezone(timedelta(hours=-3))
NOW = datetime(2026, 11, 2, 9, 10, tzinfo=BRT)


def _event(name="CPI", *, when=None, country="US", consensus=3.2,
           previous=3.1, actual=None):
    moment = when or NOW.replace(hour=9, minute=30)
    return {
        "type": name, "country": country, "period": "Outubro",
        "comparison": "yoy", "estimate": consensus, "previous": previous,
        "actual": actual,
        "date": moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }


def _model(events, *, at=NOW):
    return normalize_events(
        {"ok": True, "data": events, "fetched_at": at.isoformat()},
        at=at,
    )


class MasterBriefingV2Tests(unittest.TestCase):
    def test_no_data_not_assumed_live(self):
        model = build_master_briefing(None, at=NOW)
        self.assertEqual(model["state"], "INDISPONÍVEL")
        self.assertEqual(model["daily_events"], 0)
        self.assertIsNone(model["directional_bias"])
        self.assertFalse(model["trade_authorized"])
        self.assertIn("Briefing indisponível", master_briefing_html(None))
        self.assertIn("Agenda semanal aguardando", master_week_html(None))

    def test_daily_and_week_from_one_provider_response(self):
        events = [
            _event("CPI"),
            _event("Fed Interest Rate Decision", when=NOW.replace(hour=11)),
            _event("Nonfarm Payrolls", when=NOW + timedelta(days=1)),
            _event("GDP", when=NOW + timedelta(days=6)),
            _event("Out of window", when=NOW + timedelta(days=7)),
            _event("Old event", when=NOW - timedelta(days=1)),
        ]
        data = _model(events)
        self.assertEqual(data["state"], "READY")
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["week_total"], 2)
        self.assertEqual(len(data["events"]), 2)
        self.assertEqual(len(data["week_events"]), 2)
        self.assertTrue(all(row["actual"] is None for row in data["week_events"]))
        briefing = build_master_briefing(data, at=NOW)
        self.assertEqual(briefing["state"], "VALIDADO")
        self.assertEqual(briefing["daily_events"], 2)
        self.assertEqual(briefing["week_events"], 2)
        self.assertEqual(briefing["central_bank_events"], 1)
        self.assertEqual(briefing["upcoming_today"], 2)
        self.assertIsNone(briefing["directional_bias"])
        self.assertFalse(briefing["trade_authorized"])
        week_html = master_week_html(data, at=NOW)
        self.assertIn("Nonfarm Payrolls", week_html)
        self.assertIn("GDP", week_html)
        self.assertIn("Acima do consenso", week_html)
        self.assertNotIn("Out of window", week_html)

    def test_briefing_event_window_and_actual_surprise(self):
        after_release = NOW.replace(hour=9, minute=45)
        events = [
            _event("CPI", when=NOW.replace(hour=9, minute=30), actual=3.5),
            _event("Consumer Confidence", when=NOW.replace(hour=10, minute=10)),
        ]
        data = _model(events, at=after_release)
        briefing = build_master_briefing(data, at=after_release)
        self.assertEqual(briefing["published_today"], 1)
        self.assertEqual(briefing["surprises_today"], 1)
        self.assertEqual(briefing["upcoming_today"], 1)
        self.assertGreaterEqual(len(briefing["risk_window"]), 1)
        self.assertIn("DIVULGAÇÃO RECENTE", master_briefing_html(data, at=after_release))

    def test_no_actual_release_count_without_consensus_and_timestamp(self):
        at = NOW.replace(hour=10)
        data = _model([
            _event("CPI", when=NOW.replace(hour=9, minute=30), actual=3.0,
                   consensus=None)
        ], at=at)
        model = build_master_briefing(data, at=at)
        self.assertEqual(model["published_today"], 1)
        self.assertEqual(model["surprises_today"], 0)
        self.assertFalse(model["trade_authorized"])

    def test_stale_future_and_truncated_events_fail_closed(self):
        daily = _model([_event("CPI")])
        bads = [
            {**daily, "fetched_at": (NOW - timedelta(hours=3)).isoformat()},
            {**daily, "fetched_at": (NOW + timedelta(minutes=4)).isoformat()},
            {**daily, "date": "2026-11-01"},
            {**daily, "source": ""},
            {**daily, "truncated": True},
            {**daily, "week_total": 1},
        ]
        for bad in bads:
            with self.subTest(bad=bad):
                model = build_master_briefing(bad, at=NOW)
                self.assertEqual(model["state"], "INDISPONÍVEL")
                self.assertFalse(model["trade_authorized"])

    def test_partial_week_does_not_suppress_verified_today(self):
        data = _model([
            _event("CPI"),
            _event("GDP", when=NOW + timedelta(days=1)),
        ])
        data["week_total"] = 3
        data["week_truncated"] = True
        model = build_master_briefing(data, at=NOW)
        self.assertEqual(model["state"], "VALIDADO")
        self.assertTrue(model["week_partial"])
        self.assertEqual(model["daily_events"], 1)
        self.assertEqual(model["week_events"], 1)
        self.assertEqual(model["week_received_total"], 3)
        self.assertIn("LISTA PARCIAL", master_week_html(data, at=NOW))
        self.assertFalse(model["trade_authorized"])

    def test_unverified_or_misdated_event_refused(self):
        data = _model([_event("CPI")])
        data["events"][0]["release_utc"] = "unknown"
        self.assertEqual(build_master_briefing(data, at=NOW)["state"], "INDISPONÍVEL")
        week = _model([_event("GDP", when=NOW + timedelta(days=3))])
        week["week_events"][0]["release_utc"] = (NOW + timedelta(days=8)).isoformat()
        self.assertEqual(build_master_briefing(week, at=NOW)["state"], "INDISPONÍVEL")

    def test_no_fake_geopolitics_news_or_bank_decisions(self):
        data = _model([_event("CPI")])
        markup = trader_radar_html(selected="master", calendar_data=data)
        self.assertIn("Cenário macro", markup)
        self.assertIn("Bancos centrais", markup)
        self.assertIn("Risco geopolítico", markup)
        self.assertIn("Notícias relevantes", markup)
        self.assertIn("SEM FEED VERIFICADO", markup)
        self.assertIn("Briefing macro do dia", markup)
        self.assertIn("Agenda econômica · próximos 6 dias", markup)
        self.assertIn('data-visual-reference="approved-20261102-v1"', markup)
        self.assertIn('class="aqr-aside"', markup)

    def test_html_escapes_provider_titles_week_and_daily(self):
        malicious = '<img src=x onerror=alert(1)>'
        data = _model([
            _event(malicious),
            _event(malicious, when=NOW + timedelta(days=1)),
        ])
        raw = master_week_html(data, at=NOW) + master_briefing_html(data, at=NOW)
        self.assertNotIn(malicious, raw)
        self.assertIn("&lt;img", raw)

    def test_week_incomplete_api_page_fails_closed(self):
        data = _model([_event("CPI")]*1000)
        self.assertEqual(data["state"], "INCOMPLETE_PROVIDER")
        self.assertEqual(build_master_briefing(data, at=NOW)["state"], "INDISPONÍVEL")

    def test_editors_only_priority_no_market_signal(self):
        data = _model([_event("CPI"), _event("Unemployment Rate")])
        model = build_master_briefing(data, at=NOW)
        self.assertTrue(all(e["editorial_only"] for e in model["priority_events"]))
        self.assertIn("prioridade editorial", master_briefing_html(data, at=NOW))
        self.assertFalse(model["trade_authorized"])


if __name__ == "__main__":
    unittest.main()
