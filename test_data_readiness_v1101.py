import unittest
import pandas as pd
from data_readiness_v1101 import assess_pair_data_readiness, premium_discount_operational, display_component_status

class DataReadinessTests(unittest.TestCase):
    def _bars(self, now, n, freq):
        idx=pd.date_range(end=now,periods=n,freq=freq)
        return [{"datetime":x.isoformat(),"open":1.10,"high":1.11,"low":1.09,"close":1.105} for x in idx]
    def _map(self, now):
        return {"updated_at":now.isoformat(),"readiness_grade":"A","readiness_score":85,"adr_used_pct":60,"event_risk":"NORMAL","w1_bias":"ALTISTA"}
    def _row(self, now, age_m15=20, age_h1=50, age_h4=120, m15_bars=64, h1_bars=40):
        return {
            "m15_fetched_at": (now-pd.Timedelta(minutes=age_m15)).isoformat(),
            "h1_fetched_at": (now-pd.Timedelta(minutes=age_h1)).isoformat(),
            "h4_fetched_at": (now-pd.Timedelta(minutes=age_h4)).isoformat(),
            "tecnico": {
                "h4":{"status":"🟢 CONFIRMA"},"h1":{"status":"🟢 PULLBACK OK"},"m15":{"status":"🟢 GATILHO"},
                "cache_v110":{"m15":self._bars(now,m15_bars,"15min"),"h1":self._bars(now,h1_bars,"1h")},
            },
        }

    def test_fresh_complete_data_is_sufficient(self):
        now=pd.Timestamp("2026-09-15T00:00:00Z")
        r=assess_pair_data_readiness(self._row(now),self._map(now),now=now)
        self.assertTrue(r["sufficient"])
        self.assertGreaterEqual(r["score"],85)

    def test_stale_m15_blocks_sufficiency(self):
        now=pd.Timestamp("2026-09-15T00:00:00Z")
        r=assess_pair_data_readiness(self._row(now,age_m15=80),self._map(now),now=now)
        self.assertFalse(r["sufficient"])
        self.assertEqual(r["timeframes"]["m15"]["state"],"🟡 ENVELHECENDO")

    def test_missing_cache_blocks_institutional_data(self):
        now=pd.Timestamp("2026-09-15T00:00:00Z")
        r=assess_pair_data_readiness(self._row(now,m15_bars=5,h1_bars=3),{},now=now)
        self.assertFalse(r["institutional_data_ready"])
        s,_=display_component_status({"status":"⚪ SEM MSS","score":0,"text":"MSS aguarda estrutura válida."},"mss",r)
        self.assertIn("DADOS",s)

    def test_new_structure_components_are_masked_when_m15_is_stale(self):
        now=pd.Timestamp("2026-09-15T00:00:00Z")
        r=assess_pair_data_readiness(self._row(now,age_m15=80),self._map(now),now=now)
        for key in ("structure","order_block"):
            s,_=display_component_status(
                {"status":"🟢 CONFIRMADO","score":100,"text":"leitura anterior"},
                key,
                r,
            )
            self.assertIn("DADOS M15 INSUFICIENTES",s)

    def test_new_structure_components_are_visible_with_fresh_m15(self):
        now=pd.Timestamp("2026-09-15T00:00:00Z")
        r=assess_pair_data_readiness(self._row(now),self._map(now),now=now)
        for key in ("structure","order_block"):
            s,_=display_component_status(
                {"status":"🟢 CONFIRMADO","score":100,"text":"leitura atual"},
                key,
                r,
            )
            self.assertEqual(s,"🟢 CONFIRMADO")

    def test_premium_discount_is_operational(self):
        ready={"institutional_data_ready":True}
        x=premium_discount_operational("BUY",{"zone":"PRÊMIO","position_pct":75},ready)
        self.assertTrue(x["status"].startswith("🔴"))
        y=premium_discount_operational("SELL",{"zone":"PRÊMIO","position_pct":75},ready)
        self.assertTrue(y["status"].startswith("🟢"))

if __name__=='__main__': unittest.main()
