import unittest
from datetime import time
import pandas as pd

from market_map_core_v10 import (
    normalize_ohlc, aggregate_ohlc, market_structure, trend_context,
    prior_period_levels, liquidity_rows, premium_discount, killzone_state,
    quarterly_clock, session_range, recent_sweeps, alignment_summary,
)


def bars(start='2026-08-01', n=80, step=0.01):
    idx = pd.date_range(start, periods=n, freq='D', tz='UTC')
    vals = []
    p = 1.0
    for ts in idx:
        o = p
        c = p + step
        vals.append({'datetime': ts, 'open': o, 'high': max(o,c)+0.005, 'low': min(o,c)-0.005, 'close': c})
        p = c
    return pd.DataFrame(vals)


class MarketMapTests(unittest.TestCase):
    def test_normalize_rejects_bad_geometry(self):
        df = pd.DataFrame([
            {'datetime':'2026-09-01T00:00Z','open':1,'high':2,'low':.5,'close':1.5},
            {'datetime':'2026-09-02T00:00Z','open':1,'high':.8,'low':.5,'close':1.2},
        ])
        self.assertEqual(len(normalize_ohlc(df)), 1)

    def test_weekly_aggregation(self):
        out = aggregate_ohlc(bars(n=14), 'W-FRI')
        self.assertGreaterEqual(len(out), 2)
        self.assertTrue((out['high'] >= out['low']).all())

    def test_trend_detects_clear_uptrend(self):
        ctx = trend_context(bars(n=100, step=.005))
        self.assertEqual(ctx['bias'], 'ALTISTA')
        self.assertGreater(ctx['score'], 50)

    def test_market_structure_has_states(self):
        df = bars(n=30, step=.01)
        ctx = market_structure(df)
        self.assertIn(ctx['bias'], {'ALTISTA','BAIXISTA','NEUTRO'})

    def test_prior_day_levels(self):
        df = bars(start='2026-07-01', n=70, step=.001)
        levels = prior_period_levels(df, '2026-09-09')
        self.assertIn('PDH', levels)
        self.assertIn('PDL', levels)
        self.assertGreater(levels['PDH'], levels['PDL'])

    def test_liquidity_distance(self):
        rows = liquidity_rows(1.1000, {'PDH':1.1010,'PDL':1.0980}, 'EUR/USD')
        self.assertAlmostEqual(rows[0]['Distância (pips)'], 10.0, places=4)
        self.assertIn('BSL', rows[0]['Lado'])

    def test_premium_discount(self):
        self.assertEqual(premium_discount(25, 0, 100)['zone'], 'DESCONTO')
        self.assertEqual(premium_discount(75, 0, 100)['zone'], 'PRÊMIO')
        self.assertEqual(premium_discount(50, 0, 100)['zone'], 'EQUILÍBRIO')

    def test_killzone_london(self):
        state = killzone_state('2026-09-14 03:00:00-04:00')
        self.assertEqual(state['active']['name'], 'London Killzone')

    def test_quarterly_clock(self):
        q = quarterly_clock('2026-09-14 07:40:00-04:00', anchor_hour=0)
        self.assertEqual(q['quarter'], 2)
        self.assertEqual(q['micro'], 2)

    def test_asian_session_crosses_midnight(self):
        idx = pd.date_range('2026-09-14 00:00Z', periods=40, freq='15min')
        df = pd.DataFrame({'datetime':idx,'open':1,'high':1.01,'low':.99,'close':1.0})
        s = session_range(df, '2026-09-13 23:00:00-04:00', start=time(20), end=time(0))
        self.assertTrue(s['available'])
        self.assertTrue(s['active'])

    def test_recent_sweep(self):
        df = pd.DataFrame([
            {'datetime':'2026-09-14 12:00Z','open':1.0,'high':1.11,'low':.99,'close':1.09},
        ])
        sweeps = recent_sweeps(df, {'PDH':1.10})
        self.assertEqual(sweeps[0]['type'], 'SWEEP BSL')

    def test_alignment_not_probability(self):
        a = alignment_summary('COMPRA EUR/USD','ALTISTA','ALTISTA','DESCONTO','SWEEP SSL',True)
        self.assertEqual(a['passed'], 5)
        self.assertEqual(a['label'], 'ALTO')


if __name__ == '__main__':
    unittest.main()
