"""Alerts from documentary snapshots may not impersonate actual live feeds."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_official_change_detection_lab import (
    SCHEMA, detect_official_calendar_changes_lab,
)

AT = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
URL = ("https://www.rbnz.govt.nz/news-and-events/news/2026/10/"
       "updates-to-the-october-mpr-and-november-fsr")


def event(when="2026-11-10T20:00:00Z", *, digest="a" * 64,
          status="SCHEDULED", updated="2026-11-03T12:00:00Z"):
    return {
        "event_id": "RBNZ_NZ_FSR_NOV26", "event_kind": "FINANCIAL_STABILITY",
        "scheduled_at_utc": when, "status": status,
        "source_url": URL, "publisher_updated_at_utc": updated,
        "claimed_document_sha256": digest,
    }


def snapshot(*, observed="2026-11-04T11:00:00Z", events=None):
    return {
        "source_id": "RBNZ_OFFICIAL_NEWS", "currency": "NZD",
        "observed_at_utc": observed, "coverage": "PARTIAL_OFFICIAL_MONITOR",
        "events": [event()] if events is None else events,
        "original_source_bytes_attested": False,
        "live_feed_latency_proven": False,
    }


def detect(prev, curr, *, at=AT):
    return detect_official_calendar_changes_lab(prev, curr, at=at)


class DocumentaryChangeDetectionLabTests(unittest.TestCase):
    def test_reschedule_alert_has_source_and_all_seven_relevant_pairs(self):
        old = snapshot()
        new = snapshot(observed="2026-11-04T11:55:00Z",
                       events=[event("2026-11-16T20:00:00Z", digest="b" * 64,
                                     updated="2026-11-04T11:00:00Z")])
        originals = deepcopy((old, new))
        r = detect(old, new)
        self.assertEqual((old, new), originals)
        self.assertEqual((r["schema"], r["state"]),
                         (SCHEMA, "LAB_CHANGE_REVIEW_ONLY"))
        self.assertEqual(r["changed_event_count"], 1)
        change = r["changed_events"][0]
        self.assertIn("DATE_RESCHEDULED", change["changed_fields"])
        self.assertIn("DOCUMENT_REVISED", change["changed_fields"])
        self.assertEqual(change["official_reference_url"], URL)
        self.assertEqual(change["previous_scheduled_at_utc"],
                         "2026-11-10T20:00:00Z")
        self.assertEqual(change["latest_scheduled_at_utc"],
                         "2026-11-16T20:00:00Z")
        self.assertEqual(change["priority"], "REVISAR_IMEDIATAMENTE")
        self.assertEqual(len(change["affected_pairs"]), 7)
        self.assertIn("EUR/NZD", change["affected_pairs"])
        self.assertTrue(change["human_confirmation_required"])
        self.assertEqual(r["observation_age_seconds"], 300)
        self.assertEqual(r["freshness_state"],
                         "RECENT_OBSERVATION_NOT_PROOF_OF_LIVE_FEED")
        for name in ("source_authenticity_attested", "data_current",
                     "live_news", "realtime_delivery_verified",
                     "notification_sent", "can_feed_live_radar",
                     "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(r[name], name)
        self.assertIsNone(r["directional_forecast"])
        self.assertEqual(r["new_external_requests"], 0)
        self.assertEqual(r["new_cost_brl"], 0)

    def test_unmodified_dossier_has_no_unnecessary_alert(self):
        old = snapshot()
        cur = snapshot(observed="2026-11-04T11:55:00Z")
        r = detect(old, cur)
        self.assertEqual(r["changed_events"], [])
        self.assertEqual(r["affected_pairs"], [])
        self.assertFalse(r["notification_sent"])

    def test_partial_feed_omission_is_not_cancelled(self):
        r = detect(snapshot(), snapshot(observed="2026-11-04T11:55:00Z",
                                        events=[]))
        self.assertEqual(r["changed_events"], [])
        self.assertEqual(r["missing_from_partial_current"],
                         ["RBNZ_NZ_FSR_NOV26"])
        self.assertFalse(r["notification_sent"])

    def test_explicit_cancellation_only_enables_human_review(self):
        current = snapshot(observed="2026-11-04T11:55:00Z",
                           events=[event(status="CANCELLED")])
        r = detect(snapshot(), current)
        self.assertEqual(r["changed_event_count"], 1)
        self.assertIn("STATUS_CHANGED", r["changed_events"][0]["changed_fields"])
        self.assertEqual(r["changed_events"][0]["priority"],
                         "REVISAR_IMEDIATAMENTE")
        self.assertFalse(r["notification_sent"])

    def test_added_event_always_retains_unverified_status(self):
        old = snapshot(events=[])
        cur = snapshot(observed="2026-11-04T11:55:00Z")
        r = detect(old, cur)
        self.assertEqual(r["changed_events"][0]["changed_fields"], ["ADDED"])
        self.assertEqual(r["state"], "LAB_CHANGE_REVIEW_ONLY")

    def test_official_url_subdomain_spoof_and_ip_are_rejected(self):
        for fake in ("https://www.rbnz.govt.nz.evil.test/news",
                     "http://www.rbnz.govt.nz/news",
                     "https://127.0.0.1/news",
                     "https://user:pass@www.rbnz.govt.nz/news",
                     "https://www.rbnz.govt.nz:8443/news"):
            with self.subTest(fake=fake):
                old = snapshot()
                new = snapshot(observed="2026-11-04T11:55:00Z")
                new["events"][0]["source_url"] = fake
                self.assertEqual(detect(old, new)["state"], "LAB_REJECTED")

    def test_invalid_claims_forged_timestamps_and_duplicates_refused(self):
        changes = [
            ("original_source_bytes_attested", True),
            ("live_feed_latency_proven", True),
            ("coverage", "COMPLETE"),
            ("observed_at_utc", "2026-11-05T00:00:00Z"),
            ("observed_at_utc", "2026-11-04"),
            ("source_id", "DIFFERENT_SOURCE"),
            ("currency", "USD"),
        ]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                new = snapshot(observed="2026-11-04T11:55:00Z")
                new[field] = value
                self.assertEqual(detect(snapshot(), new)["state"], "LAB_REJECTED")
        current = snapshot(observed="2026-11-04T11:55:00Z")
        current["events"].append(deepcopy(current["events"][0]))
        self.assertEqual(detect(snapshot(), current)["state"], "LAB_REJECTED")

    def test_unhashable_fields_or_forged_actuals_never_throw(self):
        for k, value in (("event_kind", []), ("status", []),
                         ("claimed_document_sha256", "bad"),
                         ("publisher_updated_at_utc", "2026-11-04T14:00:00Z")):
            with self.subTest(k=k):
                c = snapshot(observed="2026-11-04T11:55:00Z")
                c["events"][0][k] = value
                self.assertEqual(detect(snapshot(), c)["state"], "LAB_REJECTED")
        c = snapshot(observed="2026-11-04T11:55:00Z")
        c["events"][0]["actual"] = "1.5"
        self.assertEqual(detect(snapshot(), c)["state"], "LAB_REJECTED")

    def test_missing_invalid_snapshot_and_backward_clock_refused(self):
        good = snapshot()
        for invalid in (None, {}, [], "LIVE"):
            with self.subTest(invalid=invalid):
                self.assertEqual(detect(invalid, good)["state"], "LAB_REJECTED")
        same = snapshot(observed="2026-11-04T11:00:00Z")
        self.assertEqual(detect(good, same)["reason"],
                         "SNAPSHOT_CLOCK_NOT_STRICTLY_INCREASING")
        earlier = snapshot(observed="2026-11-04T10:00:00Z")
        self.assertEqual(detect(good, earlier)["state"], "LAB_REJECTED")

    def test_stale_observation_cannot_be_reported_as_live(self):
        current = snapshot(observed="2026-11-04T11:20:00Z")
        r = detect(snapshot(observed="2026-11-04T11:00:00Z"), current)
        self.assertEqual(r["freshness_state"], "STALE_OBSERVATION")
        self.assertFalse(r["data_current"])

    def test_naive_clock_refused(self):
        with self.assertRaises(ValueError):
            detect(snapshot(), snapshot(), at=AT.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
