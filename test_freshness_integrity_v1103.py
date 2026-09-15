import unittest
import pandas as pd
from data_readiness_v1101 import (
    assess_pair_data_readiness, assess_ict_freshness, display_ict_component_status
)

class FreshnessIntegrityV1103Tests(unittest.TestCase):
    def _bars(self, now, n, freq):
        idx=pd.date_range(end=now,periods=n,freq=freq)
        return [{"datetime":x.isoformat(),"open":1.10,"high":1.11,"low":1.09,"close":1.105} for x in idx]
    def _map(self, now):
        return {"updated_at":now.isoformat(),"readiness_grade":"A","readiness_score":85,"adr_used_pct":60,"event_risk":"NORMAL","w1_bias":"ALTISTA"}
    def _scanner(self, now, m15_age=20, h1_age=60, h4_age=120, m15_bars=40, h1_bars=20):
        return {
            "m15_fetched_at": (now - pd.Timedelta(minutes=m15_age)).isoformat(),
            "h1_fetched_at": (now - pd.Timedelta(minutes=h1_age)).isoformat(),
            "h4_fetched_at": (now - pd.Timedelta(minutes=h4_age)).isoformat(),
            "tecnico": {
                "h4": {"status":"🟢 CONFIRMA"},
                "h1": {"status":"🟢 PULLBACK OK"},
                "m15": {"status":"🟢 GATILHO"},
                "cache_v110": {
                    "m15": self._bars(now,m15_bars,"15min"),
                    "h1": self._bars(now,h1_bars,"1h"),
                },
            },
        }

    def test_fresh_h1_m15_allows_ict(self):
        now=pd.Timestamp('2026-09-15T02:00:00Z')
        dr=assess_pair_data_readiness(self._scanner(now), self._map(now), now=now)
        self.assertTrue(assess_ict_freshness(dr)["ready"])
        s,t,current=display_ict_component_status({"status":"🟢 FVG EM TESTE","text":"ok"},"fvg",dr)
        self.assertTrue(current)
        self.assertEqual(s,"🟢 FVG EM TESTE")

    def test_stale_m15_masks_amd_fvg(self):
        now=pd.Timestamp('2026-09-15T02:00:00Z')
        dr=assess_pair_data_readiness(self._scanner(now,m15_age=113), self._map(now), now=now)
        self.assertFalse(assess_ict_freshness(dr)["ready"])
        for key in ("amd","fvg"):
            s,t,current=display_ict_component_status({"status":"🟢 ANTIGO","text":"old"},key,dr)
            self.assertFalse(current)
            self.assertIn("NÃO USAR",s)

    def test_stale_m15_does_not_mask_h1_crt_ote_if_h1_is_current(self):
        now=pd.Timestamp('2026-09-15T02:00:00Z')
        dr=assess_pair_data_readiness(self._scanner(now,m15_age=113,h1_age=60), self._map(now), now=now)
        for key in ("crt","ote"):
            s,t,current=display_ict_component_status({"status":"🟡 LEITURA H1","text":"h1"},key,dr)
            self.assertTrue(current)
            self.assertNotIn("NÃO USAR",s)

    def test_stale_h1_masks_crt_ote(self):
        now=pd.Timestamp('2026-09-15T02:00:00Z')
        dr=assess_pair_data_readiness(self._scanner(now,h1_age=250), self._map(now), now=now)
        for key in ("crt","ote"):
            s,t,current=display_ict_component_status({"status":"🟢 ANTIGO","text":"old"},key,dr)
            self.assertFalse(current)
            self.assertIn("H1 ANTIGO",s)

if __name__ == '__main__':
    unittest.main()
