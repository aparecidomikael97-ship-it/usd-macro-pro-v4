import unittest
import pandas as pd

from twelve_cache_v1108 import read_series, valid_records


def candle(ts, o=1.0, h=1.1, l=0.9, c=1.0):
    return {"datetime":ts,"open":o,"high":h,"low":l,"close":c}


class TwelveCacheIntegrityTests(unittest.TestCase):
    def test_future_and_invalid_fetch_timestamp_fail_closed(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        rec=[candle("2026-09-18T11:30:00Z")]
        for stamp in ("2026-09-18T12:01:00Z","bad",None):
            with self.subTest(stamp=stamp):
                state={"series":{"EUR/USD|15min":{"fetched_at":stamp,"records":rec}}}
                df,err=read_series(state,"EUR/USD","15min",80,now=now,max_age=55)
                self.assertTrue(df.empty)
                self.assertTrue(err)

    def test_duplicate_candle_timestamp_keeps_last_deterministically(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        rec=[
            candle("2026-09-18T11:30:00Z",c=1.0),
            candle("2026-09-18T11:30:00Z",o=1.2,h=1.3,l=1.1,c=1.25),
        ]
        df=valid_records(rec,"15min",now=now)
        self.assertEqual(len(df),1)
        self.assertAlmostEqual(float(df.iloc[0]["close"]),1.25)

    def test_invalid_ohlc_and_open_candle_are_removed(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        rec=[
            candle("2026-09-18T11:30:00Z"),
            candle("2026-09-18T11:45:00Z",o=1.0,h=0.8,l=0.9,c=1.0),
            candle("2026-09-18T11:50:00Z"),
        ]
        df=valid_records(rec,"15min",now=now)
        self.assertEqual(len(df),1)
        self.assertEqual(df.iloc[0]["datetime"],pd.Timestamp("2026-09-18T11:30:00Z"))

    def test_nonfinite_or_negative_cache_age_limit_fails_closed(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        state={"series":{"EUR/USD|15min":{
            "fetched_at":"2026-09-18T11:50:00Z",
            "records":[candle("2026-09-18T11:30:00Z")],
        }}}
        for limit in (float("nan"),float("inf"),float("-inf"),-1):
            with self.subTest(limit=limit):
                df,err=read_series(state,"EUR/USD","15min",80,now=now,max_age=limit)
                self.assertTrue(df.empty)
                self.assertTrue(err)


if __name__=="__main__":
    unittest.main()
