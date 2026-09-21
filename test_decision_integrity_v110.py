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


    def test_unknown_event_risk_fails_closed_even_with_full_stack(self):
        r=evaluate_decision_integrity(
            side="BUY",score=95,quality=95,rank_index=95,
            h4="🟢 CONFIRMA",h1="🟢 PULLBACK OK",m15="🟢 GATILHO",
            ict_readiness=95,institutional_readiness=95,
            gate="A",gate_score=95,adr_used_pct=50,event_risk="",technical_age_min=5,
            data_sufficient=True,data_readiness_score=100,
        )
        self.assertFalse(r["executable"])
        self.assertEqual(r["state"],"🔴 BLOQUEADO")
        self.assertEqual(r["event_level"],"DESCONHECIDO")
        self.assertTrue(any("Risco de evento desconhecido" in x for x in r["hard_blocks"]))

    def test_high_event_risk_never_becomes_executable(self):
        r=evaluate_decision_integrity(
            side="SELL",score=95,quality=95,rank_index=95,
            h4="🟢 CONFIRMA",h1="🟢 PULLBACK OK",m15="🟢 GATILHO",
            ict_readiness=95,institutional_readiness=95,
            gate="A",gate_score=95,adr_used_pct=50,event_risk="ALTO",technical_age_min=5,
            data_sufficient=True,data_readiness_score=100,
        )
        self.assertFalse(r["executable"])
        self.assertNotEqual(r["state"],"🟢 EXECUTÁVEL")
        self.assertEqual(r["event_level"],"ELEVADO")
        self.assertTrue(any("Risco de evento elevado" in x for x in r["soft_blocks"]))

    def test_h1_execution_uses_h1_trigger_and_does_not_require_m15(self):
        r=evaluate_decision_integrity(
            side="BUY",score=92,quality=88,rank_index=82,
            h4="🟢 CONFIRMA",h1="🟢 PULLBACK OK",m15="🔴 SEM GATILHO",
            ict_readiness=82,institutional_readiness=84,
            gate="A",gate_score=82,adr_used_pct=68,event_risk="NORMAL",technical_age_min=12,
            data_sufficient=True,data_readiness_score=100,execution_timeframe="H1",
        )
        self.assertTrue(r["executable"])
        self.assertEqual(r["execution_timeframe"],"H1")
        self.assertEqual(r["trigger_timeframe"],"H1")
        self.assertFalse(any("M15 ainda não confirmou" in x for x in r["soft_blocks"]))

    def test_h1_execution_still_requires_h4_and_h1_alignment(self):
        r=evaluate_decision_integrity(
            side="BUY",score=92,quality=88,rank_index=82,
            h4="🟢 CONFIRMA",h1="🔴 CONTRA",m15="🟢 GATILHO",
            ict_readiness=82,institutional_readiness=84,
            gate="A",gate_score=82,adr_used_pct=68,event_risk="NORMAL",technical_age_min=12,
            data_sufficient=True,data_readiness_score=100,execution_timeframe="H1",
        )
        self.assertFalse(r["executable"])
        self.assertTrue(any("H1 está contra o viés" in x for x in r["hard_blocks"]))

    def test_unsupported_execution_timeframe_fails_closed(self):
        r=evaluate_decision_integrity(
            side="BUY",score=99,quality=99,rank_index=99,
            h4="🟢 CONFIRMA",h1="🟢 PULLBACK OK",m15="🟢 GATILHO",
            ict_readiness=99,institutional_readiness=99,
            gate="A",gate_score=99,adr_used_pct=50,event_risk="NORMAL",technical_age_min=1,
            data_sufficient=True,data_readiness_score=100,execution_timeframe="H4",
        )
        self.assertFalse(r["executable"])
        self.assertTrue(any("Timeframe de execução ainda não suportado" in x for x in r["hard_blocks"]))


if __name__ == "__main__":
    unittest.main()
