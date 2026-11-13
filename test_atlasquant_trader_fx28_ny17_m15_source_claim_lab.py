"""Exact documentary M15 source declaration guard for frozen NY17 windows."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_fx28_ny17_m15_source_claim_lab import (
    expected_ny17_m15_endpoint_claim_lab as expected,
    has_exact_ny17_m15_endpoint_claim_lab as valid,
)

UTC = timezone.utc
D1_START = datetime(2026, 11, 15, 22, tzinfo=UTC)
W1_START = datetime(2026, 11, 15, 22, tzinfo=UTC)


class Fx28FrozenEndpointSourceTests(unittest.TestCase):
    def test_daily_exact_closed_m15_reference_claim_only(self):
        end = D1_START + timedelta(days=1)
        doc = expected(start_at_utc=D1_START, end_at_utc=end)
        self.assertEqual(doc["source_timeframe_claim"], "M15")
        self.assertEqual(doc["price_window_basis_claim"], "NY17_17_ET_FROZEN")
        self.assertEqual(doc["expected_first_m15_open_utc"], D1_START.isoformat())
        self.assertEqual(doc["expected_last_m15_open_utc"],
                         (end-timedelta(minutes=15)).isoformat())
        self.assertEqual(doc["expected_last_m15_close_utc"], end.isoformat())
        self.assertFalse(doc["native_mt5_d1_or_w1_used_as_endpoint"])
        self.assertTrue(valid(doc, start_at_utc=D1_START, end_at_utc=end))

    def test_weekly_exact_m15_boundary_is_friday_2145_or_2245_utc(self):
        start = datetime(2026, 10, 25, 21, tzinfo=UTC)
        end = start + timedelta(days=5)
        doc = expected(start_at_utc=start, end_at_utc=end)
        self.assertEqual(doc["expected_last_m15_open_utc"],
                         "2026-10-30T20:45:00+00:00")
        self.assertTrue(valid(doc, start_at_utc=start, end_at_utc=end))
        start = datetime(2026, 11, 1, 22, tzinfo=UTC)
        end = start + timedelta(days=5)
        doc = expected(start_at_utc=start, end_at_utc=end)
        self.assertEqual(doc["expected_last_m15_open_utc"],
                         "2026-11-06T21:45:00+00:00")

    def test_naive_clock_wrong_span_and_subbar_seconds_rejected(self):
        start = D1_START
        for s, e in (
            (start.replace(tzinfo=None), start+timedelta(days=1)),
            (start, start+timedelta(hours=23)),
            (start, start+timedelta(days=7)),
            (start, start+timedelta(days=1,seconds=1)),
            (start+timedelta(microseconds=1), start+timedelta(days=1)),
        ):
            with self.subTest(s=s,e=e):
                with self.assertRaises(ValueError):
                    expected(start_at_utc=s,end_at_utc=e)
                self.assertFalse(valid({},start_at_utc=s,end_at_utc=e))

    def test_native_w1_price_claim_is_rejected_even_if_numeric_close_matches(self):
        start = W1_START
        end = start + timedelta(days=5)
        for k, bad in (
            ("source_timeframe_claim","W1"),
            ("source_timeframe_claim","D1"),
            ("price_window_basis_claim","MT5_W1_SERVER_CLOSE"),
            ("native_mt5_d1_or_w1_used_as_endpoint",True),
            ("native_mt5_d1_or_w1_used_as_endpoint",0),
            ("expected_last_m15_open_utc","2026-11-20T23:45:00+00:00"),
            ("expected_last_m15_close_utc","2026-11-21T00:00:00+00:00"),
        ):
            with self.subTest(k=k,bad=bad):
                doc = expected(start_at_utc=start,end_at_utc=end)
                doc[k] = bad
                self.assertFalse(valid(doc,start_at_utc=start,end_at_utc=end))
        doc = expected(start_at_utc=start,end_at_utc=end)
        doc.pop("source_timeframe_claim")
        self.assertFalse(valid(doc,start_at_utc=start,end_at_utc=end))

    def test_no_claim_is_independent_broker_authentication_or_price(self):
        doc = expected(start_at_utc=D1_START,
                       end_at_utc=D1_START+timedelta(days=1))
        self.assertNotIn("price", doc["source_timeframe_claim"].lower())
        self.assertNotIn("close_price", doc)
        self.assertNotIn("broker_source_authenticated", doc)
        self.assertEqual(len(doc),6)


if __name__ == "__main__":
    unittest.main()
