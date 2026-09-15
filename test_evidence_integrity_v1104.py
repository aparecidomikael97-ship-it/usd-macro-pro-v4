import unittest
from datetime import datetime, timezone, timedelta
from evidence_integrity_v1104 import (
    masked_technical_status, sweep_freshness, select_operational_context
)

class EvidenceIntegrityV1104Tests(unittest.TestCase):
    def test_old_m15_does_not_count_current(self):
        r={"timeframes":{"m15":{"fresh":False}}}
        status,current=masked_technical_status("🟢 GATILHO","M15",r)
        self.assertFalse(current)
        self.assertIn("NÃO USAR",status)

    def test_fresh_h1_remains_current(self):
        r={"timeframes":{"h1":{"fresh":True}}}
        status,current=masked_technical_status("🟢 PULLBACK OK","H1",r)
        self.assertTrue(current)
        self.assertIn("PULLBACK",status)

    def test_old_sweep_is_history(self):
        now=datetime(2026,9,15,2,0,tzinfo=timezone.utc)
        old=now-timedelta(hours=8)
        out=sweep_freshness(old.isoformat(),now=now,max_age_min=360)
        self.assertFalse(out["current"])
        self.assertIn("ANTIGO",out["label"])

    def test_all_blocked_becomes_no_trade(self):
        packs=[
            {"pair":"EUR/USD","state":"🔴 BLOQUEADO","side":"SELL","priority":0,"executable":False},
            {"pair":"USD/CHF","state":"🔴 BLOQUEADO","side":"BUY","priority":0,"executable":False},
        ]
        out=select_operational_context(packs)
        self.assertTrue(out["no_trade"])
        self.assertEqual(out["label"],"NENHUM SETUP")

if __name__=="__main__":
    unittest.main()
