import unittest
from datetime import datetime, timezone

from atlasquant_aion_live_events import (
    live_event_snapshot,
    news_events,
    scheduled_event,
)


NOW=datetime(2026,9,25,10,0,0,tzinfo=timezone.utc)


def _payload(updated_at="2026-09-25T09:30:00+00:00", title="Military strike reported near key oil route"):
    return {
        "updated_at":updated_at,
        "currencies":{
            "USD":{
                "articles":[{
                    "title":title,
                    "published_at":"2026-09-25T09:40:00+00:00",
                    "source":"Reuters",
                    "provider":"Google News RSS",
                    "story_id":"S1",
                    "relevance":"Alta",
                    "theme":"Geopolítica",
                    "weighted_impact":0.8,
                    "direction":"Fortalece",
                    "link":"https://example.invalid/story",
                }]
            },
            "JPY":{
                "articles":[{
                    "title":title,
                    "published_at":"2026-09-25T09:40:00+00:00",
                    "source":"Reuters",
                    "provider":"Google News RSS",
                    "story_id":"S1",
                    "relevance":"Alta",
                    "theme":"Geopolítica",
                    "weighted_impact":0.2,
                    "direction":"Fortalece",
                }]
            },
        },
    }


class AtlasQuantAionLiveEventTests(unittest.TestCase):
    def test_news_event_is_deduplicated_and_impact_is_hypothesis(self):
        out=news_events(
            _payload(),
            provenance="GitHub:atlasquant-runtime",
            now=NOW,
        )
        self.assertEqual(out["source_state"],"FRESH")
        self.assertEqual(len(out["events"]),1)
        event=out["events"][0]
        self.assertEqual(event["category"],"GEOPOLITICAL_ESCALATION")
        self.assertEqual(event["truth_state"],"INFERENCE")
        self.assertEqual(event["impact_truth_state"],"HYPOTHESIS")
        self.assertEqual(event["currencies"],["JPY","USD"])
        self.assertFalse(event["is_trade_signal"])
        self.assertFalse(event["automatic_notification_sent"])

    def test_stale_payload_cannot_create_breaking_alert(self):
        out=news_events(
            _payload(updated_at="2026-09-24T05:00:00+00:00"),
            provenance="GitHub:atlasquant-runtime",
            now=NOW,
        )
        self.assertEqual(out["source_state"],"STALE_OR_UNCONFIRMED")
        event=out["events"][0]
        self.assertFalse(event["fresh"])
        self.assertEqual(event["alert_level"],"NONE")

    def test_unconfirmed_provenance_keeps_news_truth_unknown(self):
        out=news_events(_payload(),provenance="local fallback",now=NOW)
        self.assertEqual(out["events"][0]["truth_state"],"UNKNOWN")
        self.assertEqual(out["events"][0]["alert_level"],"NONE")

    def test_geopolitical_escalation_has_defensive_hypothesis_channels(self):
        event=news_events(
            _payload(),
            provenance="GitHub:atlasquant-runtime",
            now=NOW,
        )["events"][0]
        assets={x["asset"] for x in event["impact_channels"]}
        self.assertIn("Petróleo",assets)
        self.assertIn("Ouro",assets)
        self.assertIn("Índices globais",assets)
        self.assertTrue(all(x["truth_state"]=="HYPOTHESIS" for x in event["impact_channels"]))

    def test_scheduled_macro_is_confirmed_only_with_explicit_source(self):
        confirmed=scheduled_event({
            "disponivel":True,
            "evento":"Payroll",
            "impacto":"MÁXIMO",
            "dias":0,
            "fonte":"EODHD",
            "data_txt":"2026-09-25 12:30 UTC",
        })
        self.assertEqual(confirmed["truth_state"],"CONFIRMED")
        self.assertEqual(confirmed["impact_truth_state"],"HYPOTHESIS")

        unknown=scheduled_event({
            "disponivel":True,
            "evento":"CPI",
            "impacto":"MÁXIMO",
            "dias":0,
        })
        self.assertEqual(unknown["truth_state"],"UNKNOWN")
        self.assertFalse(unknown["fresh"])
        self.assertEqual(unknown["alert_level"],"NONE")

    def test_live_snapshot_never_claims_continuous_runtime(self):
        out=live_event_snapshot(
            news_payload=_payload(),
            news_provenance="GitHub:atlasquant-runtime",
            next_event={"disponivel":False},
            reliability={"degraded_mode":{"state":"NORMAL"}},
            now=NOW,
        )
        self.assertEqual(out["state"],"WATCHING")
        self.assertGreaterEqual(out["alert_count"],1)
        self.assertTrue(out["delivery_ready"])
        self.assertTrue(out["continuous_runtime_required"])
        self.assertFalse(out["continuous_runtime_confirmed"])
        self.assertFalse(out["automatic_notification_sent"])
        self.assertFalse(out["real_orders_enabled"])

    def test_fail_closed_reliability_propagates_to_event_watch(self):
        out=live_event_snapshot(
            news_payload=_payload(),
            news_provenance="GitHub:atlasquant-runtime",
            reliability={"degraded_mode":{"state":"FAIL_CLOSED"}},
            now=NOW,
        )
        self.assertEqual(out["state"],"FAIL_CLOSED")
        self.assertFalse(out["delivery_ready"])

    def test_non_event_headline_stays_low_priority(self):
        payload=_payload(title="Markets open quietly ahead of the weekend")
        out=news_events(payload,provenance="GitHub:atlasquant-runtime",now=NOW)
        event=out["events"][0]
        self.assertEqual(event["category"],"OTHER")
        self.assertNotEqual(event["alert_level"],"URGENT_REVIEW")


if __name__=="__main__":
    unittest.main()
