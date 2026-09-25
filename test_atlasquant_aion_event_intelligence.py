import unittest
from datetime import datetime, timezone

from atlasquant_aion_event_intelligence import (
    build_event_intelligence,
    classify_event_text,
    event_intelligence_digest,
    event_intelligence_summary,
    extract_currency_news_events,
    impact_hypotheses,
    merge_alert_journal,
    merge_event_journal,
    structured_calendar_event,
)

NOW=datetime(2026,9,25,10,0,0,tzinfo=timezone.utc)


class AtlasQuantAionEventIntelligenceTests(unittest.TestCase):
    def test_geopolitical_attack_is_classified_as_inference_not_fact(self):
        out=classify_event_text("US launches missile attack on strategic target")
        self.assertEqual(out["category"],"GEOPOLITICAL_ESCALATION")
        self.assertEqual(out["directional_cue"],"ESCALATION")
        self.assertEqual(out["classification_truth"],"INFERENCE")
        self.assertFalse(out["automatic_fact_claim"])

    def test_geopolitical_impact_is_hypothesis_only(self):
        out=impact_hypotheses(
            "GEOPOLITICAL_ESCALATION",
            directional_cue="ESCALATION",
            currencies=["USD","BRL"],
        )
        self.assertFalse(out["is_prediction"])
        self.assertFalse(out["is_trade_signal"])
        self.assertIsNone(out["profit_probability"])
        self.assertTrue(all(x["truth_state"]=="HYPOTHESIS" for x in out["channels"]))
        self.assertTrue(any(x["asset"]=="Brent / petróleo" for x in out["channels"]))
        self.assertTrue(any(x["asset"]=="WDO / USD-BRL" for x in out["channels"]))

    def test_third_party_report_is_not_promoted_to_confirmed_event_fact(self):
        payload={
            "currencies":{
                "USD":{
                    "articles":[{
                        "title":"US launches missile attack on Iran facility",
                        "published_at":"Fri, 25 Sep 2026 09:45:00 GMT",
                        "source":"example-news.com",
                        "provider":"Google News RSS",
                        "story_id":"S1",
                        "theme":"Geopolitics",
                        "relevance_points":10,
                        "weighted_impact":1,
                    }]
                }
            }
        }
        rows=extract_currency_news_events(
            payload,
            provenance="GitHub:runtime",
            now=NOW,
        )
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["report_truth"],"CONFIRMED")
        self.assertEqual(rows[0]["event_truth"],"UNKNOWN")
        self.assertFalse(rows[0]["official_source"])
        self.assertEqual(rows[0]["category"],"GEOPOLITICAL_ESCALATION")

    def test_official_source_can_confirm_event_fact(self):
        payload={
            "currencies":{
                "USD":{
                    "articles":[{
                        "title":"Federal Reserve announces rate hike",
                        "published_at":"Fri, 25 Sep 2026 09:50:00 GMT",
                        "source":"federalreserve.gov",
                        "provider":"RSS",
                        "story_id":"FED1",
                    }]
                }
            }
        }
        row=extract_currency_news_events(
            payload,
            provenance="GitHub:runtime",
            now=NOW,
        )[0]
        self.assertTrue(row["official_source"])
        self.assertEqual(row["event_truth"],"CONFIRMED")
        self.assertEqual(row["category"],"CENTRAL_BANK_HAWKISH")

    def test_single_source_critical_breaking_news_requires_internal_review_not_external_push(self):
        payload={
            "currencies":{
                "USD":{"articles":[{
                    "title":"Missile attack escalates regional conflict",
                    "published_at":"Fri, 25 Sep 2026 09:50:00 GMT",
                    "source":"wire-example.com",
                    "provider":"Google News RSS",
                    "story_id":"GEO1",
                    "relevance_points":10,
                    "weighted_impact":1,
                }]}
            }
        }
        out=build_event_intelligence(
            news_payload=payload,
            news_provenance="GitHub:runtime",
            reliability={"degraded_mode":{"state":"NORMAL"}},
            now=NOW,
        )
        alert=next(x for x in out["alerts"] if x["event_id"]==out["events"][0]["event_id"])
        self.assertEqual(alert["state"],"REVIEW_INTERNAL")
        self.assertFalse(alert["external_notification_allowed"])
        self.assertTrue(alert["requires_channel_integration"])
        self.assertFalse(alert["market_action_authorized"])

    def test_fail_closed_reliability_holds_alert(self):
        payload={
            "currencies":{
                "USD":{"articles":[{
                    "title":"Missile attack escalates regional conflict",
                    "published_at":"Fri, 25 Sep 2026 09:50:00 GMT",
                    "source":"federalreserve.gov",
                    "provider":"RSS",
                    "story_id":"GEO2",
                }]}
            }
        }
        out=build_event_intelligence(
            news_payload=payload,
            news_provenance="GitHub:runtime",
            reliability={"degraded_mode":{"state":"FAIL_CLOSED"}},
            now=NOW,
        )
        self.assertEqual(out["alerts"][0]["state"],"HOLD")
        self.assertFalse(out["external_notification_allowed"])

    def test_calendar_event_requires_source_to_be_confirmed(self):
        unknown=structured_calendar_event({
            "disponivel":True,
            "evento":"CPI",
            "impacto":"MÁXIMO",
        },now=NOW)
        self.assertEqual(unknown["event_truth"],"UNKNOWN")

        confirmed=structured_calendar_event({
            "disponivel":True,
            "evento":"CPI",
            "impacto":"MÁXIMO",
            "fonte":"BLS.gov",
            "moeda":"USD",
        },now=NOW)
        self.assertEqual(confirmed["event_truth"],"CONFIRMED")

    def test_old_news_is_not_loaded_into_current_event_window(self):
        payload={"currencies":{"USD":{"articles":[{
            "title":"Old rate hike story",
            "published_at":"Wed, 23 Sep 2026 08:00:00 GMT",
            "source":"example.com",
            "story_id":"OLD1",
        }]}}}
        rows=extract_currency_news_events(
            payload,
            provenance="GitHub:runtime",
            now=NOW,
            max_age_hours=24,
        )
        self.assertEqual(rows,[])

    def test_journals_dedupe_and_digest_is_stable(self):
        incoming=[{
            "event_id":"EVT-1",
            "headline":"Event",
            "source":"source",
            "category":"GENERAL_MARKET",
            "event_truth":"UNKNOWN",
            "severity_score":50,
        }]
        events=merge_event_journal([],incoming,observed_at="2026-09-25T10:00:00+00:00")
        events2=merge_event_journal(events,incoming,observed_at="2026-09-25T10:05:00+00:00")
        self.assertEqual(len(events2),1)
        self.assertEqual(events2[0]["first_seen_at"],"2026-09-25T10:00:00+00:00")
        self.assertEqual(events2[0]["last_seen_at"],"2026-09-25T10:05:00+00:00")

        alerts=merge_alert_journal([], [{
            "alert_id":"ALT-1","event_id":"EVT-1","state":"WATCH",
            "reason":"watch","severity_score":60,
        }],observed_at="2026-09-25T10:00:00+00:00")
        self.assertEqual(event_intelligence_digest(events2,alerts),event_intelligence_digest(events2,alerts))
        summary=event_intelligence_summary(events2,alerts)
        self.assertEqual(summary["events"],1)
        self.assertEqual(summary["watch"],1)
        self.assertFalse(summary["external_notification_allowed"])
        self.assertFalse(summary["real_orders_enabled"])


if __name__=="__main__":
    unittest.main()
