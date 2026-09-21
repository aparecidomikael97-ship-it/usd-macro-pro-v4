import unittest
import pandas as pd

from atlasquant_research_timeframes import (
    SCHEMA,
    build_research_timeframe_cache,
    completed_d1,
    completed_w1_from_d1,
    exact_m30_from_m15,
)


def bar(ts,o=1.0,h=1.2,l=.8,c=1.1):
    return {"datetime":ts,"open":o,"high":h,"low":l,"close":c}


class ResearchTimeframeCacheTests(unittest.TestCase):
    def test_m30_requires_two_exact_contiguous_closed_m15_bars(self):
        rows=[
            bar("2026-09-21T12:00:00Z",1.0,1.2,.9,1.1),
            bar("2026-09-21T12:15:00Z",1.1,1.3,1.0,1.2),
            bar("2026-09-21T12:30:00Z",1.2,1.4,1.1,1.3),
        ]
        out=exact_m30_from_m15(rows,now="2026-09-21T13:00:00Z")
        self.assertEqual(len(out),1)
        self.assertEqual(pd.Timestamp(out.iloc[0]["datetime"]),pd.Timestamp("2026-09-21T12:00:00Z"))
        self.assertEqual(float(out.iloc[0]["open"]),1.0)
        self.assertEqual(float(out.iloc[0]["close"]),1.2)

    def test_m30_drops_gap_and_still_open_bucket(self):
        rows=[
            bar("2026-09-21T12:00:00Z"),
            bar("2026-09-21T12:30:00Z"),
            bar("2026-09-21T12:45:00Z"),
        ]
        gap=exact_m30_from_m15(rows,now="2026-09-21T12:50:00Z")
        self.assertTrue(gap.empty)
        closed=exact_m30_from_m15(rows,now="2026-09-21T13:00:00Z")
        self.assertEqual(len(closed),1)
        self.assertEqual(pd.Timestamp(closed.iloc[0]["datetime"]),pd.Timestamp("2026-09-21T12:30:00Z"))

    def test_d1_excludes_current_new_york_day(self):
        rows=[
            bar("2026-09-18T00:00:00Z"),
            bar("2026-09-21T00:00:00Z"),
        ]
        out=completed_d1(rows,now="2026-09-21T16:00:00Z")
        self.assertEqual(len(out),1)
        self.assertEqual(pd.Timestamp(out.iloc[0]["datetime"]),pd.Timestamp("2026-09-18T00:00:00Z"))

    def test_w1_excludes_current_week(self):
        rows=[
            bar("2026-09-14T00:00:00Z"),bar("2026-09-15T00:00:00Z"),
            bar("2026-09-16T00:00:00Z"),bar("2026-09-17T00:00:00Z"),
            bar("2026-09-18T00:00:00Z"),bar("2026-09-21T00:00:00Z"),
        ]
        out=completed_w1_from_d1(rows,now="2026-09-21T16:00:00Z")
        self.assertEqual(len(out),1)
        self.assertEqual(pd.Timestamp(out.iloc[0]["datetime"]),pd.Timestamp("2026-09-18T00:00:00Z"))


    def test_d1_and_w1_exclude_weekend_provider_artifacts(self):
        rows=[
            bar("2026-09-18T00:00:00Z",1.0,1.3,.9,1.2),
            bar("2026-09-19T00:00:00Z",9.0,9.5,8.5,9.1),
            bar("2026-09-20T00:00:00Z",8.0,8.5,7.5,8.1),
            bar("2026-09-21T00:00:00Z",1.2,1.4,1.1,1.3),
        ]
        d1=completed_d1(rows,now="2026-09-22T16:00:00Z")
        self.assertTrue(all(pd.Timestamp(x).dayofweek < 5 for x in d1["datetime"]))
        self.assertNotIn(9.5,set(float(x) for x in d1["high"]))
        w1=completed_w1_from_d1(rows,now="2026-09-28T16:00:00Z")
        self.assertTrue(w1.empty or float(w1.iloc[-1]["high"]) < 9.0)

    def test_cache_is_research_only_and_adds_no_provider_call_contract(self):
        scanner={"resultados":{"EUR/USD":{"tecnico":{"cache_v110":{"m15":[
            bar("2026-09-21T12:00:00Z"),bar("2026-09-21T12:15:00Z"),
        ]}}}}}
        daily={"pairs":{"EUR/USD":{"records":[bar("2026-09-18T00:00:00Z")]}}}
        out=build_research_timeframe_cache(scanner,daily,now="2026-09-21T13:00:00Z")
        self.assertEqual(out["schema"],SCHEMA)
        self.assertIn("EUR/USD",out["pairs"])
        self.assertEqual(len(out["pairs"]["EUR/USD"]["M30"]),1)
        self.assertTrue(out["safety"]["research_only"])
        self.assertFalse(out["safety"]["provider_calls_added"])
        self.assertFalse(out["safety"]["real_orders"])
        self.assertFalse(out["safety"]["automatic_execution"])


if __name__=="__main__":
    unittest.main()
