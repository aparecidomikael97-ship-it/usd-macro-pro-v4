import unittest
from datetime import datetime, timezone

from atlasquant_aion_source_mesh import (
    age_minutes,
    autopilot_observations,
    calendar_observations,
    fred_macro_observations,
    pair_matrix_observations,
    source_mesh_snapshot,
)


NOW=datetime(2026,9,25,9,0,0,tzinfo=timezone.utc)


class AtlasQuantAionSourceMeshTests(unittest.TestCase):
    def test_age_minutes_is_utc_and_never_negative(self):
        self.assertEqual(
            age_minutes("2026-09-25T08:30:00+00:00",now=NOW),
            30.0,
        )
        self.assertEqual(
            age_minutes("2026-09-25T10:30:00+00:00",now=NOW),
            0.0,
        )
        self.assertIsNone(age_minutes("invalid",now=NOW))

    def test_fred_observation_is_confirmed_but_safety_fallback_is_unknown(self):
        rows=fred_macro_observations({
            "_auditoria":[
                {
                    "Indicador":"IPC anual",
                    "Valor":3.0,
                    "Última observação":"2026-09-01",
                    "Idade (dias)":24,
                    "Status":"OK",
                    "Fonte":"FRED · CPIAUCSL",
                },
                {
                    "Indicador":"Payroll — variação mensal",
                    "Valor":150,
                    "Última observação":"—",
                    "Idade (dias)":"—",
                    "Status":"⚠️ Fallback",
                    "Fonte":"Valor de segurança",
                },
            ]
        })
        self.assertEqual(rows[0]["truth_state"],"CONFIRMED")
        self.assertTrue(rows[0]["available"])
        self.assertTrue(rows[0]["healthy"])
        self.assertEqual(rows[1]["truth_state"],"UNKNOWN")
        self.assertFalse(rows[1]["available"])
        self.assertFalse(rows[1]["healthy"])
        self.assertIn("fallback",rows[1]["detail"].lower())

    def test_calendar_never_claims_event_when_unavailable(self):
        row=calendar_observations({"disponivel":False})[0]
        self.assertEqual(row["truth_state"],"UNKNOWN")
        self.assertFalse(row["available"])
        self.assertFalse(row["healthy"])

    def test_autopilot_maps_twelve_quota_and_news_nowcast(self):
        rows=autopilot_observations({
            "version":"V11",
            "last_run":"2026-09-25T08:30:00+00:00",
            "healthy":True,
            "app_headless_ok":True,
            "forex_market_open":True,
            "scanner_fresh":7,
            "scanner_ready":True,
            "market_map_fresh":7,
            "market_map_ready":True,
            "twelve_daily_blocked":False,
            "twelve_rate_safe":True,
            "twelve_budget":{"limit":800,"remaining":600,"used":200},
            "news_updated_at":"2026-09-25T08:20:00+00:00",
            "news_unique_stories":100,
            "news_nowcast_v1":{
                "runtime_state":"CAPTURED",
                "provider_status":{"ok":True,"reason":"OK"},
                "snapshots":4,
                "events":3,
            },
        },provenance="GitHub:atlasquant-runtime",now=NOW)
        twelve=next(x for x in rows if x["claim"]=="twelve_data_runtime")
        self.assertEqual(twelve["truth_state"],"CONFIRMED")
        self.assertTrue(twelve["healthy"])
        self.assertEqual(twelve["quota_remaining_pct"],75.0)
        eod=next(x for x in rows if x["claim"]=="eodhd_nowcast_runtime")
        self.assertTrue(eod["healthy"])
        self.assertTrue(eod["available"])

    def test_eodhd_auth_error_is_not_healthy(self):
        rows=autopilot_observations({
            "last_run":"2026-09-25T08:30:00+00:00",
            "healthy":True,
            "forex_market_open":True,
            "twelve_daily_blocked":False,
            "twelve_rate_safe":True,
            "news_nowcast_v1":{
                "runtime_state":"AUTH_COOLDOWN",
                "provider_status":{"reason":"AUTH_ERROR"},
                "provider_retry_after_min":120,
            },
        },provenance="GitHub:atlasquant-runtime",now=NOW)
        eod=next(x for x in rows if x["claim"]=="eodhd_nowcast_runtime")
        self.assertFalse(eod["healthy"])
        self.assertFalse(eod["available"])
        self.assertEqual(eod["cost_state"],"CONTROLLED")

    def test_pair_matrix_runtime_snapshot_is_available_but_not_healthy_live(self):
        row=pair_matrix_observations({
            "ready":True,
            "live_ready":False,
            "source":"runtime_snapshot",
            "pairs_expected":7,
            "pairs_built":7,
            "fallback_age_minutes":15,
            "reason":"fallback",
        })[0]
        self.assertTrue(row["available"])
        self.assertFalse(row["healthy"])
        self.assertEqual(row["criticality"],"CRITICAL")
        self.assertEqual(row["age_minutes"],15.0)

    def test_source_mesh_is_read_only_and_combines_runtime_families(self):
        out=source_mesh_snapshot(
            macro_us={"_auditoria":[]},
            next_event={"disponivel":True,"evento":"CPI","fonte":"FRED release 10","impacto":"MÁXIMO"},
            autopilot_status={
                "last_run":"2026-09-25T08:30:00+00:00",
                "healthy":True,
                "forex_market_open":True,
                "scanner_fresh":7,
                "market_map_fresh":7,
                "twelve_daily_blocked":False,
                "twelve_rate_safe":True,
            },
            autopilot_provenance="GitHub:atlasquant-runtime",
            pair_matrix_status={
                "ready":True,"live_ready":True,"source":"live",
                "pairs_expected":7,"pairs_built":7,
            },
            now=NOW,
        )
        self.assertGreaterEqual(out["observation_count"],6)
        self.assertIn("autopilot",out["families"])
        self.assertIn("decision_core",out["families"])
        self.assertFalse(out["performs_network_request"])
        self.assertFalse(out["changes_market_scores"])
        self.assertFalse(out["automatic_source_switch"])
        self.assertFalse(out["real_orders_enabled"])


if __name__=="__main__":
    unittest.main()
