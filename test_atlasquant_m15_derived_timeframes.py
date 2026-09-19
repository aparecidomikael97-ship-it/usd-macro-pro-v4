import unittest
import pandas as pd

from atlasquant_m15_derived_timeframes import derive_from_m15, derived_timeframe_health


def bars(start, count):
    idx=pd.date_range(start,periods=count,freq="15min",tz="UTC")
    rows=[]
    for i,ts in enumerate(idx):
        o=1.0+i*0.001
        rows.append({
            "datetime":ts,
            "open":o,
            "high":o+0.002,
            "low":o-0.001,
            "close":o+0.001,
        })
    return pd.DataFrame(rows)


class AtlasQuantM15DerivedTests(unittest.TestCase):
    def test_four_m15_bars_make_one_h1(self):
        d=bars("2026-09-15T12:00:00Z",4)
        h1=derive_from_m15(d,"1h",now_utc="2026-09-15T13:00:00Z")
        self.assertEqual(len(h1),1)
        r=h1.iloc[0]
        self.assertEqual(int(r["m15_count"]),4)
        self.assertAlmostEqual(r["open"],d.iloc[0]["open"])
        self.assertAlmostEqual(r["close"],d.iloc[-1]["close"])
        self.assertAlmostEqual(r["high"],d["high"].max())
        self.assertAlmostEqual(r["low"],d["low"].min())

    def test_sixteen_m15_bars_make_one_h4(self):
        d=bars("2026-09-15T08:00:00Z",16)
        h4=derive_from_m15(d,"4h",now_utc="2026-09-15T12:00:00Z")
        self.assertEqual(len(h4),1)
        self.assertEqual(int(h4.iloc[0]["m15_count"]),16)

    def test_partial_group_is_discarded(self):
        d=bars("2026-09-15T12:00:00Z",3)
        h1=derive_from_m15(d,"1h",now_utc="2026-09-15T13:00:00Z")
        self.assertTrue(h1.empty)

    def test_gap_inside_group_is_discarded(self):
        d=bars("2026-09-15T12:00:00Z",4).drop(index=2).reset_index(drop=True)
        # Add a later candle so count can never masquerade as contiguous completeness.
        later=bars("2026-09-15T13:00:00Z",1)
        d=pd.concat([d,later],ignore_index=True)
        h1=derive_from_m15(d,"1h",now_utc="2026-09-15T14:00:00Z")
        self.assertTrue(h1.empty)

    def test_open_m15_candle_is_excluded(self):
        d=bars("2026-09-15T12:00:00Z",4)
        h1=derive_from_m15(d,"1h",now_utc="2026-09-15T12:59:00Z")
        self.assertTrue(h1.empty)

    def test_future_candles_cannot_leak_into_h1(self):
        closed=bars("2026-09-15T12:00:00Z",4)
        future=bars("2026-09-15T13:00:00Z",4)
        d=pd.concat([closed,future],ignore_index=True)
        h1=derive_from_m15(d,"1h",now_utc="2026-09-15T13:00:00Z")
        self.assertEqual(len(h1),1)
        self.assertEqual(h1.iloc[0]["datetime"],pd.Timestamp("2026-09-15T12:00:00Z"))

    def test_duplicate_m15_timestamp_is_normalized_without_fabricating_extra_bar(self):
        d=bars("2026-09-15T12:00:00Z",4)
        d=pd.concat([d,d.iloc[[0]]],ignore_index=True)
        h1=derive_from_m15(d,"1h",now_utc="2026-09-15T13:00:00Z")
        # normalize_ohlc owns duplicate normalization upstream. The invariant here is
        # that a duplicate can never create an extra derived candle.
        self.assertLessEqual(len(h1),1)
        if not h1.empty:
            self.assertEqual(int(h1.iloc[0]["m15_count"]),4)

    def test_unsupported_timeframe_fails_closed(self):
        with self.assertRaises(ValueError):
            derive_from_m15(bars("2026-09-15T12:00:00Z",4),"2h",now_utc="2026-09-15T13:00:00Z")

    def test_health_requires_enough_complete_bars(self):
        d=bars("2026-09-15T00:00:00Z",64)
        health=derived_timeframe_health(
            d,
            now_utc="2026-09-15T16:00:00Z",
            min_h1_bars=12,
            min_h4_bars=4,
        )
        self.assertTrue(health["h1_ready"])
        self.assertTrue(health["h4_ready"])
        self.assertFalse(health["live_wiring_allowed"])


if __name__=="__main__":
    unittest.main()
