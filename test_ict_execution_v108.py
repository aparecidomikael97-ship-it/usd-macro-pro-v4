import unittest
import pandas as pd
from ict_execution_v108 import detect_crt, detect_amd, detect_fvg

class ICTExecutionV108Tests(unittest.TestCase):
    def _df(self, rows, freq="h"):
        d=pd.DataFrame(rows,columns=["open","high","low","close"])
        d["datetime"]=pd.date_range("2026-09-14",periods=len(d),freq=freq,tz="UTC")
        return d[["datetime","open","high","low","close"]]

    def test_bullish_crt(self):
        d=self._df([(1.00,1.10,.90,1.02),(1.02,1.05,.88,.96),(.96,1.08,.95,1.06)])
        x=detect_crt(d,"BUY")
        self.assertIn("CONFIRMADO",x["status"])
        self.assertEqual(x["raid_side"],"SSL")

    def test_amd_detects_manipulation_or_distribution(self):
        rows=[(1.00,1.02,.98,1.00)]*8
        rows += [(1.00,1.01,.96,.99),(0.99,1.02,.98,1.01),(1.01,1.04,1.00,1.03),(1.03,1.06,1.02,1.05)]
        x=detect_amd(self._df(rows,"15min"),"BUY")
        self.assertGreaterEqual(x["score"],70)

    def test_fvg(self):
        d=self._df([(1,1.01,.99,1),(1,1.02,.995,1.015),(1.03,1.04,1.025,1.035)],"15min")
        x=detect_fvg(d,"BUY")
        self.assertGreaterEqual(x["score"],65)

if __name__=="__main__": unittest.main()
