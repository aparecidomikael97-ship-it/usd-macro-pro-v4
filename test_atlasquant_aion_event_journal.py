import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_aion_event_journal import (
    build_runtime_journal,
    continuity_summary,
    internal_delivery_queue,
    merge_events,
    overlay_journal,
)


NOW=datetime(2026,9,25,12,0,0,tzinfo=timezone.utc)


def event(urgency=80,level="URGENT_REVIEW"):
    return {
        "event_id":"EVT-1",
        "kind":"NEWS_REPORT",
        "category":"GEOPOLITICAL_ESCALATION",
        "headline":"Reported military escalation",
        "reported_at":"2026-09-25T11:50:00+00:00",
        "truth_state":"INFERENCE",
        "truth_note":"report",
        "sources":["Reuters"],
        "source_count":1,
        "currencies":["USD"],
        "urgency_score":urgency,
        "alert_level":level,
        "impact_truth_state":"HYPOTHESIS",
    }


class AtlasQuantAionEventJournalTests(unittest.TestCase):
    def test_event_history_is_deduplicated_and_tracks_peak_urgency(self):
        rows=merge_events([], [event(70,"HIGH_REVIEW")], observed_at="2026-09-25T11:00:00+00:00")
        rows=merge_events(rows, [event(90,"URGENT_REVIEW")], observed_at="2026-09-25T11:30:00+00:00")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["seen_count"],2)
        self.assertEqual(rows[0]["peak_urgency_score"],90)
        self.assertEqual(rows[0]["peak_alert_level"],"URGENT_REVIEW")
        self.assertEqual(rows[0]["first_seen_at"],"2026-09-25T11:00:00+00:00")
        self.assertEqual(rows[0]["last_seen_at"],"2026-09-25T11:30:00+00:00")
        self.assertFalse(rows[0]["is_trade_signal"])
        self.assertFalse(rows[0]["real_orders_enabled"])

    def test_24h_continuity_requires_real_coverage_and_dense_heartbeats(self):
        heartbeats=[]
        start=NOW-timedelta(hours=24)
        for idx in range(49):
            heartbeats.append({
                "observed_at":(start+timedelta(minutes=30*idx)).isoformat(),
                "source_state":"FRESH",
                "event_count":1,
                "alert_count":0,
            })
        out=continuity_summary(heartbeats,now=NOW)
        self.assertEqual(out["state"],"CONTINUOUS_24H")
        self.assertTrue(out["continuous_24h_confirmed"])
        self.assertGreaterEqual(out["heartbeat_count"],40)
        self.assertLessEqual(out["max_gap_minutes"],90)

    def test_few_recent_cycles_never_claim_24h_monitoring(self):
        rows=[
            {"observed_at":(NOW-timedelta(minutes=30*i)).isoformat(),"source_state":"FRESH"}
            for i in range(6)
        ]
        out=continuity_summary(rows,now=NOW)
        self.assertEqual(out["state"],"BUILDING_EVIDENCE")
        self.assertFalse(out["continuous_24h_confirmed"])

    def test_large_gap_blocks_24h_confirmation(self):
        rows=[]
        start=NOW-timedelta(hours=24)
        for idx in range(45):
            minutes=30*idx
            if idx>=20:
                minutes+=180
            rows.append({"observed_at":(start+timedelta(minutes=minutes)).isoformat(),"source_state":"FRESH"})
        out=continuity_summary(rows,now=NOW)
        self.assertFalse(out["continuous_24h_confirmed"])
        self.assertGreater(out["max_gap_minutes"],90)

    def test_internal_delivery_queue_never_allows_external_push(self):
        queue=internal_delivery_queue({"top_alerts":[event()]})
        self.assertEqual(len(queue),1)
        self.assertEqual(queue[0]["state"],"INTERNAL_ONLY")
        self.assertFalse(queue[0]["external_channel_connected"])
        self.assertFalse(queue[0]["external_delivery_allowed"])
        self.assertFalse(queue[0]["automatic_notification_sent"])
        self.assertFalse(queue[0]["market_action_authorized"])

    def test_runtime_journal_has_no_provider_or_execution_side_effects(self):
        live={
            "news_source_state":"FRESH",
            "events":[event()],
            "event_count":1,
            "alert_count":1,
            "top_alerts":[event()],
        }
        out=build_runtime_journal(
            {},
            live,
            observed_at=NOW.isoformat(),
            now=NOW,
        )
        self.assertEqual(out["event_count"],1)
        self.assertEqual(len(out["heartbeats"]),1)
        self.assertFalse(out["performs_provider_request"])
        self.assertFalse(out["external_delivery_allowed"])
        self.assertFalse(out["automatic_notification_sent"])
        self.assertFalse(out["real_orders_enabled"])

    def test_overlay_only_claims_continuity_from_persisted_summary(self):
        live={"continuous_runtime_confirmed":False}
        journal={
            "event_count":3,
            "delivery_candidate_count":1,
            "continuity":{
                "state":"CONTINUOUS_24H",
                "heartbeat_count":48,
                "coverage_minutes":1440,
                "latest_age_minutes":20,
                "max_gap_minutes":30,
                "continuous_24h_confirmed":True,
            },
            "events":[event()],
            "delivery_queue":[],
        }
        out=overlay_journal(live,journal)
        self.assertTrue(out["continuous_runtime_confirmed"])
        self.assertEqual(out["background_watch_state"],"CONTINUOUS_24H")
        self.assertEqual(out["journal_event_count"],3)
        self.assertFalse(out["external_delivery_allowed"])


if __name__=="__main__":
    unittest.main()
