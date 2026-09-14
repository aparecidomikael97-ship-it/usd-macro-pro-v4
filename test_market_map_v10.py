import unittest
from datetime import time
import pandas as pd

from market_map_core_v10 import (
    normalize_ohlc, aggregate_ohlc, market_structure, trend_context,
    prior_period_levels, liquidity_rows, liquidity_kind, nearest_liquidity,
    premium_discount, killzone_state, quarterly_clock, session_range, recent_sweeps,
    alignment_summary, structure_regime, event_risk, macro_regime_summary, setup_readiness,
    adr_context, intraday_open_context,
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
        self.assertEqual(rows[0]['Tipo'], 'BSL')

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


    def test_liquidity_taxonomy_does_not_flip_after_cross(self):
        self.assertEqual(liquidity_kind('PDH'), 'BSL')
        self.assertEqual(liquidity_kind('PWH'), 'BSL')
        self.assertEqual(liquidity_kind('PDL'), 'SSL')
        self.assertEqual(liquidity_kind('Asia Low'), 'SSL')
        rows = liquidity_rows(1.1050, {'PDH':1.1000,'PDL':1.0900}, 'EUR/USD')
        pdh = next(r for r in rows if r['Nível'] == 'PDH')
        self.assertEqual(pdh['Tipo'], 'BSL')
        self.assertIn('ATRÁS', pdh['Status'])

    def test_nearest_liquidity_uses_semantic_side_only(self):
        bsl, ssl = nearest_liquidity(1.1000, {
            'PDH':1.0990,      # BSL already behind, must not become SSL
            'PWH':1.1100,      # available BSL
            'PDL':1.1010,      # SSL already behind above price, must not become BSL
            'PWL':1.0900,      # available SSL
            'NY Midnight Open':1.1005,
        })
        self.assertEqual(bsl[0], 'PWH')
        self.assertEqual(ssl[0], 'PWL')

    def test_premium_discount_flags_expansion_outside_range(self):
        hi = premium_discount(102, 0, 100)
        lo = premium_discount(-2, 0, 100)
        self.assertEqual(hi['zone'], 'ACIMA DO RANGE')
        self.assertAlmostEqual(hi['expansion_pct'], 2.0)
        self.assertEqual(lo['zone'], 'ABAIXO DO RANGE')
        self.assertAlmostEqual(lo['expansion_pct'], 2.0)

    def test_structure_regime_mixed_states(self):
        self.assertEqual(structure_regime('HH','HL')['bias'], 'ALTISTA')
        self.assertEqual(structure_regime('LH','LL')['bias'], 'BAIXISTA')
        self.assertEqual(structure_regime('HH','LL')['regime'], 'EXPANSÃO DOS DOIS LADOS')
        self.assertEqual(structure_regime('LH','HL')['regime'], 'COMPRESSÃO')

    def test_wrong_side_sweep_is_not_invented(self):
        # Price trades below PDH and closes back above: this is NOT an SSL sweep,
        # because PDH is semantically a high-side (BSL) pool.
        df = pd.DataFrame([{'datetime':'2026-09-14 12:00Z','open':1.10,'high':1.11,'low':1.08,'close':1.105}])
        sweeps = recent_sweeps(df, {'PDH':1.09})
        self.assertFalse(any(x['type'] == 'SWEEP SSL' for x in sweeps))

    def test_event_risk_today_high_impact(self):
        r = event_risk({'evento':'FOMC','dias':0,'impacto':'MÁXIMO'})
        self.assertEqual(r['level'], 'ALTO')
        self.assertLess(r['score'], 0.5)

    def test_macro_regime_pair_orientation(self):
        ctx = {
            'usd_score': 70, 'fed_tone': 'Restritivo',
            'trend': {'score': 65}, 'surprise_adjustment': 3,
            'event': {'evento':'CPI','dias':5,'impacto':'ALTO'},
        }
        # Strong USD confirms BUY USD/CHF but would confirm SELL EUR/USD.
        a = macro_regime_summary('USD/CHF','COMPRA USD/CHF',90,85,ctx)
        b = macro_regime_summary('EUR/USD','VENDA EUR/USD',90,85,ctx)
        self.assertGreaterEqual(a['consistency'], 75)
        self.assertGreaterEqual(b['consistency'], 75)

    def test_readiness_is_capped_by_event_risk(self):
        clean = {'bias':'ALTISTA','confirmation':'CONFIRMADA','structure':{'bias':'ALTISTA','regime':'TENDÊNCIA ALTISTA'}}
        out = setup_readiness('COMPRA USD/CHF',95,90,clean,clean,'DESCONTO','SWEEP SSL',True,'ALTO')
        self.assertLessEqual(out['score'], 69)
        self.assertNotEqual(out['grade'], 'A+')

    def test_readiness_a_plus_requires_clean_context(self):
        clean = {'bias':'ALTISTA','confirmation':'CONFIRMADA','structure':{'bias':'ALTISTA','regime':'TENDÊNCIA ALTISTA'}}
        out = setup_readiness('COMPRA USD/CHF',95,90,clean,clean,'DESCONTO','SWEEP SSL',True,'NORMAL')
        self.assertEqual(out['grade'], 'A+')
        self.assertGreaterEqual(out['score'], 88)

    def test_readiness_missing_sweep_is_not_a_plus(self):
        clean = {'bias':'ALTISTA','confirmation':'CONFIRMADA','structure':{'bias':'ALTISTA','regime':'TENDÊNCIA ALTISTA'}}
        out = setup_readiness('COMPRA USD/CHF',95,90,clean,clean,'DESCONTO','',True,'NORMAL')
        self.assertNotEqual(out['grade'], 'A+')
        sweep = next(x for x in out['checks'] if x['name'] == 'Sweep coerente')
        self.assertFalse(sweep['ok'])

    def test_readiness_elevated_event_prevents_a(self):
        clean = {'bias':'ALTISTA','confirmation':'CONFIRMADA','structure':{'bias':'ALTISTA','regime':'TENDÊNCIA ALTISTA'}}
        out = setup_readiness('COMPRA USD/CHF',95,90,clean,clean,'DESCONTO','SWEEP SSL',True,'ELEVADO')
        self.assertLessEqual(out['score'], 77)
        self.assertNotIn(out['grade'], {'A','A+'})

    def test_adr_context_detects_exhaustion(self):
        daily = bars(start='2026-08-01', n=40, step=.001)
        idx = pd.date_range('2026-09-14 04:00Z', periods=20, freq='15min')
        intraday = pd.DataFrame({
            'datetime': idx, 'open': 1.0, 'high': 1.03, 'low': .97, 'close': 1.0
        })
        out = adr_context(daily, intraday, '2026-09-14 04:30:00-04:00', length=14)
        self.assertTrue(out['available'])
        self.assertGreater(out['used_pct'], 100)
        self.assertIn('RANGE', out['state'])

    def test_intraday_open_context(self):
        idx = pd.date_range('2026-09-14 04:00Z', periods=8, freq='15min')
        intraday = pd.DataFrame({
            'datetime': idx, 'open': [1.0]*8, 'high': [1.02]*8, 'low': [.99]*8, 'close': [1.01]*8
        })
        out = intraday_open_context(intraday, '2026-09-14 01:30:00-04:00')
        self.assertTrue(out['available'])
        self.assertAlmostEqual(out['day_open'], 1.0)
        self.assertTrue(out['above_day_open'])

    def test_sweep_contains_rejection_metadata(self):
        df = pd.DataFrame([{
            'datetime':'2026-09-14 12:00Z','open':1.0,'high':1.11,'low':.99,'close':1.09
        }])
        item = recent_sweeps(df, {'PDH':1.10})[0]
        self.assertGreater(item['excess_abs'], 0)
        self.assertIn('abaixo', item['rejection'])

if __name__ == '__main__':
    unittest.main()
