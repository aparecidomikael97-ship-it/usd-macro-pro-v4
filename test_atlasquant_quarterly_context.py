import unittest
import pandas as pd

from atlasquant_quarterly_context import build_quarterly_snapshot


def candles_for_day(*, sweep="none"):
    # 15-minute candles spanning 00:00-12:00 New York on 2026-09-18.
    idx = pd.date_range("2026-09-18 04:00:00+00:00", periods=41, freq="15min")
    rows=[]
    px=1.1000
    for i,ts in enumerate(idx):
        o=px
        h=px+0.0004
        l=px-0.0004
        c=px+0.0001
        rows.append({"datetime":ts,"open":o,"high":h,"low":l,"close":c})
        px=c
    df=pd.DataFrame(rows)
    # NY 00:00-06:00 corresponds to first 24 candles here.
    prev=df.iloc[:24]
    prev_high=float(prev["high"].max())
    prev_low=float(prev["low"].min())
    # Current Q2 begins at index 24.
    if sweep=="low_reclaim":
        df.loc[28,"low"]=prev_low-0.0010
        df.loc[28,"close"]=prev_low+0.0003
        df.loc[df.index[-1],"close"]=prev_low+0.0005
    elif sweep=="high_reclaim":
        df.loc[28,"high"]=prev_high+0.0010
        df.loc[28,"close"]=prev_high-0.0003
        df.loc[df.index[-1],"close"]=prev_high-0.0005
    elif sweep=="both":
        df.loc[28,"low"]=prev_low-0.0010
        df.loc[32,"high"]=prev_high+0.0010
        df.loc[df.index[-1],"close"]=(prev_high+prev_low)/2
    return df


class QuarterlyContextTests(unittest.TestCase):
    def test_missing_data_is_unavailable(self):
        out=build_quarterly_snapshot(None,"BUY")
        self.assertFalse(out["available"])
        self.assertEqual(out["direction"],"INDISPONÍVEL")
        self.assertFalse(out["decision_effect"])

    def test_low_sweep_and_reclaim_is_buy_observation(self):
        out=build_quarterly_snapshot(candles_for_day(sweep="low_reclaim"),"BUY")
        self.assertTrue(out["available"])
        self.assertEqual(out["quarter"],2)
        self.assertEqual(out["direction"],"COMPRA")
        self.assertEqual(out["side_alignment"],"ALINHADO")
        self.assertTrue(out["reclaim_low"])
        self.assertFalse(out["changes_gate"])
        self.assertFalse(out["changes_score_mestre"])

    def test_high_sweep_and_reclaim_is_sell_observation(self):
        out=build_quarterly_snapshot(candles_for_day(sweep="high_reclaim"),"SELL")
        self.assertEqual(out["direction"],"VENDA")
        self.assertEqual(out["side_alignment"],"ALINHADO")
        self.assertTrue(out["reclaim_high"])

    def test_two_sided_sweep_is_neutral_not_forced(self):
        out=build_quarterly_snapshot(candles_for_day(sweep="both"),"BUY")
        self.assertEqual(out["direction"],"NEUTRO")
        self.assertEqual(out["event"],"VARREDURA DOS DOIS LADOS")
        self.assertEqual(out["direction_vote"],0)

    def test_phase_hint_is_not_predictive(self):
        out=build_quarterly_snapshot(candles_for_day(),"WAIT")
        self.assertFalse(out["phase_is_predictive"])
        self.assertIn("Quarterly",out["detail"])


if __name__=="__main__":
    unittest.main()