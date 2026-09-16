import unittest
import pandas as pd
import numpy as np

from institutional_engine_v110 import (
    detect_displacement, detect_mss, detect_dealing_range,
    detect_smt, build_institutional_snapshot,
)


def frame(prices, start="2026-09-14T00:00:00Z", freq="15min"):
    idx=pd.date_range(start, periods=len(prices), freq=freq, tz="UTC")
    rows=[]
    prev=prices[0]
    for i,c in enumerate(prices):
        o=prev if i else c
        h=max(o,c)+0.00035
        l=min(o,c)-0.00035
        rows.append({"datetime":idx[i],"open":o,"high":h,"low":l,"close":c})
        prev=c
    return pd.DataFrame(rows)


class InstitutionalEngineTests(unittest.TestCase):
    def test_displacement_detects_large_bull_candle(self):
        p=[1.1000 + 0.00005*i for i in range(28)]
        p += [1.1015,1.1016,1.1045]
        d=frame(p)
        # force last candle large bullish body
        d.loc[d.index[-1],"open"]=1.1016
        d.loc[d.index[-1],"low"]=1.1014
        d.loc[d.index[-1],"high"]=1.1050
        r=detect_displacement(d,"BUY")
        self.assertGreaterEqual(r["score"],60)

    def test_mss_bullish_break(self):
        p=[1.1000,1.1010,1.1020,1.1010,1.1002,1.1010,1.1022,1.1012,1.1005,
           1.1010,1.1015,1.1010,1.1008,1.1014,1.1020,1.1038,1.1042,1.1045,
           1.1047,1.1050,1.1052,1.1055,1.1057,1.1060]
        d=frame(p)
        r=detect_mss(d,"BUY")
        self.assertIn("MSS",r["status"])
        self.assertGreaterEqual(r["score"],45)

    def test_dealing_range_favors_buy_in_discount(self):
        p=np.linspace(1.1000,1.1200,30).tolist()+np.linspace(1.1200,1.1060,20).tolist()
        d=frame(p,freq="1h")
        r=detect_dealing_range(d,"BUY")
        self.assertIn(r["zone"],("DESCONTO","EQUILÍBRIO","PRÊMIO"))
        self.assertGreaterEqual(r["score"],0)

    def test_smt_bullish_primary_sweeps_only(self):
        base=[1.1000+0.0001*np.sin(i/2) for i in range(30)]
        a=frame(base)
        b=frame([1.2000+0.0001*np.sin(i/2) for i in range(30)])
        # primary creates new low in last window, companion does not
        a.loc[a.index[-2],"low"]=a.iloc[:22]["low"].min()-0.0010
        a.loc[a.index[-2],"close"]=a.loc[a.index[-2],"low"]+0.0004
        r=detect_smt(a,b,"EUR/USD","GBP/USD","BUY")
        self.assertIn("SMT",r["status"])
        self.assertGreaterEqual(r["score"],40)

    def test_snapshot_never_claims_probability(self):
        d=frame([1.1+0.0001*i for i in range(80)])
        r=build_institutional_snapshot("EUR/USD",d,d,"BUY",d,"GBP/USD")
        self.assertIn("readiness",r)
        self.assertIn("structure",r)
        self.assertIn("order_block",r)
        self.assertIn("não é probabilidade",r["algorithm_note"])


if __name__ == "__main__":
    unittest.main()
