import unittest
from pathlib import Path

from atlasquant_aion_admin import AION_ADMIN_CSS


class AtlasQuantAionAdminTests(unittest.TestCase):
    def test_futuristic_ui_is_css_only_and_mobile_safe(self):
        self.assertIn("perspective", AION_ADMIN_CSS)
        self.assertIn("radial-gradient", AION_ADMIN_CSS)
        self.assertIn("@media(max-width:760px)", AION_ADMIN_CSS)
        self.assertIn("prefers-reduced-motion", AION_ADMIN_CSS)
        self.assertNotIn("MutationObserver", AION_ADMIN_CSS)
        self.assertNotIn("document.querySelector", AION_ADMIN_CSS)

    def test_admin_console_requires_admin_and_keeps_external_actions_guarded(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("if not is_admin(access_map):", src)
        self.assertIn("guardian_decision(", src)
        self.assertIn("feature_flag_snapshot", src)
        self.assertIn("save_runtime_checkpoint(", src)
        self.assertIn("approved=True", src)
        self.assertIn("real_orders_enabled", src)

    def test_admin_console_contains_all_approved_workspaces(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        for label in (
            "🧠 Central",
            "🗂️ Secretaria",
            "📈 Trading",
            "🎬 Studio",
            "💼 Negócios",
            "🧪 Laboratório",
            "🛠️ Desenvolvimento",
            "🎟️ Promoções",
        ):
            self.assertIn(label, src)

    def test_secretary_uses_working_checkpoint_and_audit_events(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("_working_checkpoint(", src)
        self.assertIn("_set_working_checkpoint(", src)
        self.assertIn("_render_secretary(", src)
        self.assertIn("new_task(", src)
        self.assertIn("approve_task(", src)
        self.assertIn("_record_working_event(", src)
        self.assertIn("Observabilidade / auditoria", src)

    def test_checkpoint_save_clears_dirty_only_after_confirmed_save(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        success = src.index('if result.get("saved"):')
        block = src[success:success+700]
        self.assertIn('_set_working_checkpoint(saved_checkpoint, dirty=False)', block)
        self.assertIn("Checkpoint Mestre salvo e confirmado no runtime.", block)

    def test_dirty_checkpoint_detects_runtime_conflict_before_save(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("_WORKING_CONFLICT_KEY", src)
        self.assertIn("Conflito detectado:", src)
        self.assertIn("disabled=conflict", src)
        self.assertIn("não vai sobrescrever a versão nova automaticamente", src)
        self.assertIn("Descartar alterações locais e recarregar runtime", src)

    def test_laboratory_exposes_budget_router_without_enabling_billing(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Roteador de inteligência / orçamento", src)
        self.assertIn("Teto mensal máximo para IA externa (USD)", src)
        self.assertIn("Permitir solicitações pagas dentro do teto", src)
        self.assertIn("set_budget_policy(", src)
        self.assertIn("route_intelligence(", src)
        self.assertIn("Definir teto não gera cobrança", src)

    def test_central_records_router_decision_before_local_answer(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        route=src.index("route = route_intelligence(")
        answer=src.index("answer = local_answer(",route)
        self.assertLess(route,answer)
        self.assertIn('st.session_state["aion_last_route"] = route',src)
        self.assertIn("Roteamento:",src)

    def test_contextual_voice_exists_for_all_aion_workspaces(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        for area in (
            "Central","Secretaria","Trading","Studio",
            "Negócios","Laboratório","Desenvolvimento","Promoções",
        ):
            self.assertIn(f'_context_voice("{area}"', src)
        self.assertIn("nunca toca sozinha", src)
        self.assertIn("pode consumir esse serviço", src)

    def test_external_model_path_is_opt_in_and_cost_guarded(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Usar inteligência externa nesta pergunta", src)
        self.assertIn("Aprovo esta solicitação externa dentro do teto informado", src)
        self.assertIn("execute_openai_answer(", src)
        self.assertIn("estimated_request_cost_usd=estimated_cost", src)
        self.assertIn("record_model_spend_estimate(", src)
        self.assertIn("MODEL_OUTPUT_UNVERIFIED", Path("atlasquant_aion_provider.py").read_text(encoding="utf-8"))
        self.assertIn("nenhuma chamada paga será feita", src)

    def test_business_panel_labels_unconnected_sales_as_unconfirmed(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("não representam vendas confirmadas", src)
        self.assertIn("integrações não estiverem conectadas", src)


if __name__ == "__main__":
    unittest.main()
