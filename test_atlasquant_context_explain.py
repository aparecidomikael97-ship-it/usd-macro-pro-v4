import unittest

from atlasquant_context_explain import context_validity, explain_change, pack_snapshot


class AtlasQuantContextExplainTests(unittest.TestCase):
    def base(self):
        return {
            "pair":"EUR/USD","direction":"🟢 COMPRA EUR/USD","state":"🟡 AGUARDAR GATILHO",
            "side":"BUY","priority":80,"quality":75,"gate":"🟡","m15":"AGUARDAR",
            "event":"NORMAL","executable":False,"technical_age":20,
            "data_ready":{"sufficient":True,"score":88},
            "hard_blocks":[],"soft_blocks":[],"next_action":"Aguardar M15","reason":"macro favorece EUR",
            "up":["MSS bullish"],"down":["Evento contrário"]
        }

    def test_blocked_when_data_insufficient(self):
        p=self.base(); p["data_ready"]={"sufficient":False,"score":40}
        v=context_validity(p)
        self.assertEqual(v["status"],"BLOCKED")
        self.assertEqual(v["label"],"NÃO OPERAR")

    def test_active_requires_engine_executable(self):
        p=self.base(); p["executable"]=True
        v=context_validity(p)
        self.assertEqual(v["status"],"ACTIVE")
        self.assertEqual(v["label"],"MOTOR LIBEROU CONTEXTO")

    def test_wait_when_ready_but_not_executable(self):
        v=context_validity(self.base())
        self.assertEqual(v["status"],"WAIT")

    def test_hard_block_always_blocks(self):
        p=self.base(); p["executable"]=True; p["hard_blocks"]=["dados stale"]
        self.assertEqual(context_validity(p)["status"],"BLOCKED")

    def test_explain_material_changes(self):
        old=self.base()
        cur=self.base()
        cur["priority"]=86
        cur["m15"]="CONFIRMADO"
        cur["state"]="🟢 EXECUTÁVEL"
        reasons=explain_change(cur,old)
        joined=" ".join(reasons)
        self.assertIn("Prioridade subiu",joined)
        self.assertIn("M15 mudou",joined)
        self.assertIn("Estado operacional mudou",joined)

    def test_first_read_is_explicit(self):
        reasons=explain_change(self.base(),None)
        self.assertIn("Primeira leitura",reasons[0])

    def test_opposite_evidence_is_reported_as_contradiction(self):
        v=context_validity(self.base())
        self.assertIn("Evento contrário",v["contradictions"])

    def test_snapshot_is_finite_safe(self):
        p=self.base(); p["priority"]=float("nan")
        self.assertEqual(pack_snapshot(p)["priority"],0.0)


    def test_soft_block_prevents_active_context_even_if_executable(self):
        p=self.base(); p["executable"]=True; p["soft_blocks"]=["M15 ainda parcial"]
        v=context_validity(p)
        self.assertEqual(v["status"],"WAIT")
        self.assertEqual(v["label"],"AGUARDAR CONFIRMAÇÃO")



if __name__=="__main__":
    unittest.main()
