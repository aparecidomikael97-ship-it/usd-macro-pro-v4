"""G99 RED-first: scanner evidence expires at exactly 60 elapsed minutes.

All clock-age outputs are injected at the single _minutes_since boundary;
no network, no trading, no provider, no clock races in the tests.
"""
import unittest
from unittest.mock import patch

import master_panel_v102 as panel


SCOPE = {"resultados": {"EUR/USD": {
    "m15_fetched_at": 1700000000,
    "tecnico": {"disponivel": True},
}}}


class G99ScannerStrictFreshnessBoundary(unittest.TestCase):
    def check(self, *, age, available=True):
        raw = {"resultados": {"EUR/USD": {
            "m15_fetched_at": 1700000000,
            "tecnico": {"disponivel": available},
        }}}
        with patch.object(panel, "_minutes_since", return_value=age) as elapsed:
            result = panel._scanner_for_pair(raw, "EUR/USD")
        elapsed.assert_called_once_with(1700000000)
        return result

    def test_01_just_below_60_minutes_remains_fresh(self):
        got = self.check(age=59.999)
        self.assertTrue(got["fresh"])
        self.assertEqual(got["age_minutes"], 59.999)
        print("G99_JUST_BEFORE_60=FRESH")

    def test_02_exactly_60_minutes_is_expired(self):
        got = self.check(age=60.0)
        self.assertFalse(got["fresh"])
        self.assertEqual(got["age_minutes"], 60.0)
        print("G99_AT_60=EXPIRED")

    def test_03_just_after_60_minutes_is_expired(self):
        got = self.check(age=60.001)
        self.assertFalse(got["fresh"])
        print("G99_AFTER_60=EXPIRED")

    def test_04_unverified_timestamp_fails_closed(self):
        got = self.check(age=None)
        self.assertFalse(got["fresh"])
        self.assertIsNone(got["age_minutes"])
        print("G99_UNVERIFIED=EXPIRED")

    def test_05_unavailable_scan_does_not_become_fresh(self):
        got = self.check(age=1, available=False)
        self.assertFalse(got["fresh"])
        self.assertFalse(got["available"])
        print("G99_UNAVAILABLE=EXPIRED")


if __name__ == "__main__":
    unittest.main()
