"""LAB: economic calendar normalization, USD explanations, safe overrides and quota."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from atlasquant_trader_calendar_ui import calendar_html
from atlasquant_trader_economic_calendar import (
    event_identity, explanation, normalize_events, request_eodhd_daily,
)
from atlasquant_trader_opening_collector import (
    INSTRUMENTS, build_opening_snapshot, in_collection_window,
)
from atlasquant_trader_radar_compact_ui import (
    _opening_score, trader_radar_html,
)

BRT = timezone(timedelta(hours=-3))
NOW = datetime(2026, 11, 2, 8, 46, tzinfo=BRT)
RELEASE = datetime(2026, 11, 2, 9, 30, tzinfo=BRT)


def _event(**kw):
    item = {
        "type": "Consumer Price Index CPI", "country": "US",
        "date": RELEASE.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "comparison": "yoy", "period": "October",
        "previous": 3.1, "estimate": 3.2, "actual": None,
    }
    item.update(kw)
    return item


def _quote(kind):
    sym, _, basis = INSTRUMENTS[kind]
    reference = {"vix": 20.0, "iron": 100.0, "oil": 75.0}[kind]
    price = {"vix": 21.0, "iron": 101.0, "oil": 74.0}[kind]
    return {
        "state": "VERIFIED_QUOTE", "instrument_id": sym,
        "reference_type": basis, "source": "Laboratório fictício",
        "price": price, "previous_reference": reference,
        "as_of": NOW.isoformat(), "reference_date": "2026-10-30",
    }


class TraderCalendarTests(unittest.TestCase):
    def test_eodhd_daily_auto_snapshot_requires_real_payload(self):
        snapshot = normalize_events({"ok": True, "data": [_event()]}, at=NOW)
        self.assertEqual(snapshot["state"], "READY")
        self.assertEqual(snapshot["date"], "2026-11-02")
        self.assertEqual(len(snapshot["events"]), 1)
        event = snapshot["events"][0]
        self.assertEqual(event["time_brt"], "09:30")
        self.assertEqual(event["consensus"], 3.2)
        self.assertEqual(event["previous"], 3.1)
        self.assertIsNone(event["actual"])
        self.assertEqual(event["source"], "EODHD Economic Events")
        self.assertIn("CPI", calendar_html(snapshot))
        self.assertIn("Se vier acima do consenso:", calendar_html(snapshot))
        self.assertIn("USD", explanation(event)["above"])

    def test_higher_lower_us_cpi_and_employment_may_move_usd(self):
        above = normalize_events(
            {"ok": True, "data": [_event(actual=3.5)]}, at=RELEASE + timedelta(minutes=10)
        )["events"][0]
        self.assertIn("ACIMA do consenso", explanation(above)["result"])
        self.assertIn("USD", explanation(above)["result"])
        below = normalize_events(
            {"ok": True, "data": [_event(actual=2.9)]}, at=RELEASE + timedelta(minutes=10)
        )["events"][0]
        self.assertIn("ABAIXO do consenso", explanation(below)["result"])
        self.assertIn("USD", explanation(below)["result"])
        unemployed = normalize_events(
            {"ok": True, "data": [_event(type="Unemployment Rate", estimate=4.0)]}, at=NOW
        )["events"][0]
        self.assertIn("emprego", explanation(unemployed)["above"].lower())

    def test_no_consensus_not_invented_and_manual_marked(self):
        item = _event(estimate=None)
        key = event_identity("US", item["type"], "yoy",
                             RELEASE.astimezone(timezone.utc))
        manual = {
            key: {"event_id": key, "source": "Consenso informado pelo ADMIN",
                  "author": "owner", "entered_at": NOW.isoformat(),
                  "value": 3.4}
        }
        snapshot = normalize_events({"ok": True, "data": [item]},
                                    at=NOW, manual=manual)
        event = snapshot["events"][0]
        self.assertEqual(event["consensus"], 3.4)
        self.assertIn("MANUAL", event["consensus_source"])
        self.assertIn("MANUAL", calendar_html(snapshot))
        wrong = normalize_events({"ok": True, "data": [item]}, at=NOW)
        self.assertIsNone(wrong["events"][0]["consensus"])
        manual[key]["entered_at"] = (RELEASE + timedelta(minutes=1)).isoformat()
        after = normalize_events({"ok": True, "data": [item]},
                                 at=RELEASE + timedelta(minutes=2), manual=manual)
        self.assertIsNone(after["events"][0]["consensus"])
        manual[key]["entered_at"] = NOW.isoformat()
        authoritative = normalize_events(
            {"ok": True, "data": [_event(estimate=3.2)]}, at=NOW, manual=manual
        )
        self.assertEqual(authoritative["events"][0]["consensus"], 3.2)
        self.assertEqual(authoritative["events"][0]["consensus_source"], "EODHD Economic Events")

    def test_provider_failure_unsupported_or_truncated_is_fail_closed(self):
        self.assertNotEqual(normalize_events({"ok": False, "data": []}, at=NOW)["state"], "READY")
        self.assertEqual(normalize_events({"ok": True, "data": [_event()]*1000},
                                          at=NOW)["state"], "INCOMPLETE_PROVIDER")
        self.assertEqual(normalize_events({"ok": True, "data": [_event(country="XX")]},
                                          at=NOW)["events"], [])

    def test_html_escapes_remote_strings(self):
        snapshot = normalize_events(
            {"ok": True, "data": [_event(type="CPI <script>alert(1)</script>")]}, at=NOW)
        markup = calendar_html(snapshot)
        self.assertIn("&lt;script&gt;", markup)
        self.assertNotIn("<script>", markup)

    def test_api_reader_no_key_and_single_bounded_request(self):
        calls = []
        def fake_get(url, *, params, timeout):
            calls.append((url, params, timeout))
            return SimpleNamespace(status_code=200, json=lambda: [_event()])
        self.assertEqual(request_eodhd_daily("", at=NOW, request_get=fake_get)["ok"], False)
        self.assertEqual(len(calls), 0)
        result = request_eodhd_daily("test_secret", at=NOW, request_get=fake_get)
        self.assertTrue(result["ok"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["from"], "2026-11-02")
        self.assertEqual(calls[0][1]["to"], "2026-11-03")
        self.assertEqual(calls[0][1]["limit"], 1000)
        self.assertEqual(calls[0][2], 12)

    def test_opening_window_and_validated_three_factor_computation(self):
        self.assertTrue(in_collection_window(NOW))
        self.assertFalse(in_collection_window(NOW.replace(minute=39)))
        self.assertFalse(in_collection_window(NOW.replace(minute=56)))
        self.assertFalse(in_collection_window(NOW + timedelta(days=5)))
        requested = []
        def get_quote(symbol):
            requested.append(symbol)
            return next(_quote(name) for name in INSTRUMENTS if INSTRUMENTS[name][0] == symbol)
        snapshot = build_opening_snapshot(get_quote, at=NOW)
        self.assertIsNotNone(snapshot)
        self.assertEqual(len(requested), 3)
        expected = snapshot["iron_pct"] + snapshot["oil_pct"] - snapshot["vix_pct"]
        score = _opening_score(snapshot, at=NOW)
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score["score"], expected, places=3)
        self.assertEqual(score["side"], "Baixa")
        self.assertIsNone(build_opening_snapshot(get_quote, at=NOW.replace(minute=56)))
        self.assertIsNone(build_opening_snapshot(
            lambda symbol: {**get_quote(symbol), "state": "UNVERIFIED"}, at=NOW))

    def test_ui_master_renders_source_and_conditional_events(self):
        model = normalize_events({"ok": True, "data": [_event()]}, at=NOW)
        html = trader_radar_html(selected="master", calendar_data=model)
        self.assertIn('data-event-id="', html)
        self.assertIn("Consenso", html)
        self.assertIn("Se vier acima do consenso:", html)
        self.assertIn("Fonte identificada", html)
        self.assertIn("USD", html)
        self.assertNotIn("Calendário diário aguardando fonte", html)


if __name__ == "__main__":
    unittest.main()
