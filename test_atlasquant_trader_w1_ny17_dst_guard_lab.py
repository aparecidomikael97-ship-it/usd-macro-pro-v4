"""Synthetic calendar regression only, not broker evidence or FX price data."""
from datetime import datetime, timedelta, timezone
import unittest
from atlasquant_trader_w1_ny17_dst_guard_lab import w1_ny17_dst_crossing_lab as risk
UTC=timezone.utc

def u(iso):
    return datetime.fromisoformat(iso.replace('Z','+00:00'))

class WeeklyNyDstSafetyTests(unittest.TestCase):
    def test_spring_forward_weekly_nominal_168h_is_unsafe(self):
        first=u('2026-03-01T22:00:00Z')
        self.assertTrue(risk(first,first+timedelta(days=7)))
    def test_fall_back_weekly_nominal_168h_is_unsafe(self):
        first=u('2026-10-25T21:00:00Z')
        self.assertTrue(risk(first,first+timedelta(days=7)))
    def test_ordinary_sunday_17h_week_not_flagged(self):
        first=u('2026-11-08T22:00:00Z')
        self.assertFalse(risk(first,first+timedelta(days=7)))
    def test_non_ny17_weekly_open_is_not_authenticated_or_rewritten(self):
        first=u('2026-03-01T00:00:00Z')
        self.assertFalse(risk(first,first+timedelta(days=7)))
        self.assertEqual(first,u('2026-03-01T00:00:00Z'))
    def test_bad_or_unordered_inputs_block(self):
        first=u('2026-03-01T22:00:00Z')
        self.assertIsNone(risk(first.replace(tzinfo=None),first+timedelta(days=7)))
        self.assertIsNone(risk(first,first))
        self.assertIsNone(risk('2026-03-01T22:00:00Z',first+timedelta(days=7)))

if __name__=='__main__': unittest.main()
