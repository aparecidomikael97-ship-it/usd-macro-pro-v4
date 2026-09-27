import unittest
from pathlib import Path


class AionOrchestratorUiIntegrationTests(unittest.TestCase):
    def test_central_exposes_core_status_plan_truth_and_gates(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("AION ONLINE · ORQUESTRAÇÃO SEGURA", source)
        self.assertIn("orchestrate_aion_core(", source)
        self.assertIn("plan_specialist_dispatch(core_preview)", source)
        self.assertIn("Capability Registry + Truth Gate + Guardian + Critic", source)
        self.assertIn("Builder → Critic → Validator", source)
        self.assertIn("build_aion_result(", source)
        self.assertIn('st.session_state["aion_last_unified_result"]', source)

    def test_ui_does_not_claim_execution_or_cross_persona_memory(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("nenhuma ação é executada nesta prévia", source)
        self.assertIn("read_specialist_evidence(", source)
        self.assertIn("Leitura local do especialista", source)
        self.assertIn("Esta leitura não responde à pergunta.", source)
        self.assertIn("loaded_session_from_checkpoint(checkpoint)", source)
        self.assertIn("observed_at", source)
        self.assertIn("freshness", source)
        self.assertIn("truth_state", source)
        self.assertIn("conflicts", source)
        self.assertIn("answers_user_question", source)
        self.assertIn("acesso entre personas automático: NÃO", source)
        self.assertIn('cols[3].metric("Ordens reais", "BLOQUEADAS")', source)


if __name__ == "__main__":
    unittest.main()
