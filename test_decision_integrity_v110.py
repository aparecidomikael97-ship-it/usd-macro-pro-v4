import unittest
from decision_integrity_v110 import evaluate_decision_integrity


class DecisionIntegrityTests(unittest.TestCase):
    def test_wait_gate_prevents_executable(self):
        r=evaluate_decision_integrity(
            side="BUY",score=93,quality=84,rank_index=80,
            h4="🟢 CONFIRMA",h1="🟢 PULLBACK OK",m15="🟢 GATILHO",
            ict_readiness=85,institutional_readiness=85,
            gate="WAIT",gate_score=50,adr_used_pct=60,event_risk="NORMAL",technical_age_min=10,
        )
        self.assertFalse(r["executable"])
        self.assertNotEqual(r["state"],"🟢 EXECUTÁVEL")

    def test_adr_over_115_is_hard_block(self):
        r=evaluate_decision_integrity(
            side="SELL",score=90,quality=84,rank_index=80,
            h4="🟢 CONFIRMA",h1="🟢 PULLBACK OK",m15="🟢 GATILHO",
            ict_readiness=90,institutional_readiness=90,
            gate="A",gate_score=85,adr_used_pct=120,event_risk="NORMAL",technical_age_min=10,
        )
        self.assertEqual(r["state"],"🔴 BLOQUEADO")


    def test_macro_wait_is_not_red_block(self):
        r=evaluate_decision_integrity(
            side="WAIT",score=58,quality=84,rank_index=58,
            h4="⚪ MACRO AGUARDAR",h1="⚪ MACRO AGUARDAR",m15="⚪ MACRO AGUARDAR",
            ict_readiness=0,institutional_readiness=0,
            gate="B",gate_score=70,adr_used_pct=40,event_risk="NORMAL",technical_age_min=10,
        )
        self.assertEqual(r["state"],"⚪ AGUARDAR DIREÇÃO")

    def test_full_stack_can_be_executable(self):
        r=evaluate_decision_integrity(
            side="BUY",score=92,quality=88,rank_index=82,
            h4="🟢 CONFIRMA",h1="🟢 PULLBACK OK",m15="🟢 GATILHO",
            ict_readiness=82,institutional_readiness=84,
            gate="A",gate_score=82,adr_used_pct=68,event_risk="NORMAL",technical_age_min=12,
            data_sufficient=True,data_readiness_score=100,
        )
        self.assertTrue(r["executable"])
        self.assertEqual(r["state"],"🟢 EXECUTÁVEL")

    def test_insufficient_data_is_hard_block(self):
        r=evaluate_decision_integrity(
            side="BUY",score=93,quality=84,rank_index=80,
            h4="🟢 CONFIRMA",h1="🟢 PULLBACK OK",m15="🟢 GATILHO",
            ict_readiness=85,institutional_readiness=85,
            gate="A",gate_score=85,adr_used_pct=60,event_risk="NORMAL",technical_age_min=10,
            data_sufficient=False,data_readiness_score=42,
        )
        self.assertEqual(r["state"],"🔴 BLOQUEADO")
        self.assertTrue(any("Dados técnicos insuficientes" in x for x in r["hard_blocks"]))


    def test_invalid_temporal_and_readiness_inputs_fail_closed(self):
        for bad in (float("nan"),float("inf"),float("-inf"),-1):
            with self.subTest(age=bad):
                r=evaluate_decision_integrity(
                    side="BUY",score=92,quality=88,rank_index=82,
                    h4="🟢 CONFIRMA",h1="🟢 PULLBACK OK",m15="🟢 GATILHO",
                    ict_readiness=82,institutional_readiness=84,
                    gate="A",gate_score=82,adr_used_pct=68,event_risk="NORMAL",
                    technical_age_min=bad,data_sufficient=True,data_readiness_score=100,
                )
                self.assertFalse(r["executable"])
                self.assertEqual(r["state"],"🔴 BLOQUEADO")
        for bad in (float("nan"),float("inf"),float("-inf")):
            with self.subTest(readiness=bad):
                r=evaluate_decision_integrity(
                    side="BUY",score=92,quality=88,rank_index=82,
                    h4="🟢 CONFIRMA",h1="🟢 PULLBACK OK",m15="🟢 GATILHO",
                    ict_readiness=82,institutional_readiness=84,
                    gate="A",gate_score=82,adr_used_pct=68,event_risk="NORMAL",
                    technical_age_min=10,data_sufficient=True,data_readiness_score=bad,
                )
                self.assertFalse(r["executable"])
                self.assertEqual(r["state"],"🔴 BLOQUEADO")


if __name__ == "__main__":
    unittest.main()
