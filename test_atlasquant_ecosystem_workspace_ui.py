from pathlib import Path
import unittest

from atlasquant_ecosystem_workspace_ui import (
    WORKSPACE_CSS,
    central_reference_card_html,
    workspace_cockpit_html,
    workspace_modules,
    workspace_spec,
)


class EcosystemWorkspaceUiTests(unittest.TestCase):
    def test_four_canonical_specs_have_distinct_visual_identity(self):
        self.assertEqual(workspace_spec("trader")["title"], "Trader")
        self.assertEqual(workspace_spec("negocios")["title"], "Negócios")
        self.assertEqual(workspace_spec("investimentos")["title"], "Investimentos")
        self.assertEqual(workspace_spec("aion")["title"], "AION")
        self.assertEqual(workspace_spec("business")["title"], "Negócios")
        self.assertEqual(workspace_spec("ia")["title"], "AION")

    def test_central_cards_follow_reference_and_never_restore_legacy_business_scope(self):
        html="".join(
            central_reference_card_html(area, "<svg></svg>")
            for area in ("trader","negocios","investimentos","aion")
        )
        for expected in (
            "ACESSAR TRADER",
            "ACESSAR NEGÓCIOS",
            "ACESSAR INVESTIMENTOS",
            "ACESSAR AION",
        ):
            self.assertIn(expected,html)
        self.assertIn("Automação B2B",html)
        self.assertIn("Revenue Ops",html)
        self.assertIn("Micro-SaaS",html)
        self.assertNotIn("Dropshipping",html)
        self.assertNotIn("Mercado Livre",html)
        self.assertNotIn("TikTok Shop",html)
        self.assertNotIn("Renda Fixa / Investimentos",html)
        self.assertNotIn("AION IA",html)

    def test_business_cockpit_contains_five_approved_fronts_and_governance(self):
        html=workspace_cockpit_html("negocios")
        expected=(
            "Automação empresarial B2B",
            "Captação / Revenue Ops",
            "Micro-SaaS próprio",
            "Serviços internacionais de IA",
            "Produtos digitais próprios",
            "Central Financeira / FinOps",
            "Saúde do Cliente",
            "Suporte / SLA",
            "Hub de Integrações",
            "Auditoria / LGPD",
            "Equipe &amp; Acessos",
            "Demo / Sandbox",
            "AION Negócios",
        )
        for label in expected:
            self.assertIn(label,html)
        for banned in ("Dropshipping","Mercado Livre","TikTok Shop","Afiliados"):
            self.assertNotIn(banned,html)
        self.assertIn('data-workspace="negocios"',html)
        self.assertIn("TENANT",html.upper())

    def test_investments_cockpit_is_truthful_and_non_executing(self):
        html=workspace_cockpit_html("investimentos")
        for label in (
            "Renda Fixa","Renda Variável","Fundos e Produtos","Carteira &amp; Alocação",
            "Análise de Risco","Planejamento","Renda &amp; Dividendos","Crescimento",
            "Relatórios Patrimoniais","Educação Financeira","AION Investimentos",
        ):
            self.assertIn(label,html)
        self.assertIn("SEM EXECUÇÃO AUTOMÁTICA",html)
        self.assertNotIn("rentabilidade garantida",html.casefold())
        self.assertNotIn("ordem automática habilitada",html.casefold())

    def test_aion_cockpit_prepares_chat_library_checkpoint_and_english_without_fake_readiness(self):
        html=workspace_cockpit_html("aion")
        for label in (
            "Chat do AION","Histórico","Memória","Tarefas &amp; Execução","Biblioteca AION",
            "Pesquisa &amp; Inteligência","Checkpoint Mestre","Núcleo / Orquestração",
            "8 Papéis Internos","Auditoria / Guardião","Academy","AION English",
        ):
            self.assertIn(label,html)
        self.assertIn('data-feature-state="PRÉVIA"',html)
        self.assertIn('data-feature-state="PLANEJADO"',html)
        self.assertIn("#537",html)
        self.assertIn("#483",html)

    def test_cards_float_discretely_and_reduced_motion_disables_movement(self):
        self.assertIn(".aq-ws-card:hover{transform:translateY(-5px)",WORKSPACE_CSS)
        self.assertIn(".aq-central-reference-card:hover{transform:translateY(-5px)",WORKSPACE_CSS)
        self.assertIn("@media (prefers-reduced-motion:reduce)",WORKSPACE_CSS)
        self.assertIn(".aq-ws-card:hover,.aq-central-reference-card:hover{transform:none}",WORKSPACE_CSS)

    def test_mobile_breakpoints_keep_single_column_at_phone_width(self):
        self.assertIn("@media (max-width:800px)",WORKSPACE_CSS)
        self.assertIn("@media (max-width:520px)",WORKSPACE_CSS)
        self.assertIn(".aq-central-reference-grid,.aq-ws-modules{grid-template-columns:1fr}",WORKSPACE_CSS)

    def test_business_admin_renderer_no_longer_exposes_legacy_marketplace_surface(self):
        src=Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        start=src.index("def _render_business(")
        end=src.index("\ndef _render_laboratory(",start)
        body=src[start:end]
        for expected in (
            "Automação empresarial B2B",
            "Revenue Ops",
            "Micro-SaaS",
            "Serviços Internacionais",
            "Produtos Digitais",
            "LGPD / Auditoria",
        ):
            self.assertIn(expected,body)
        for banned in (
            "Mercado Livre",
            "TikTok Shop",
            "Candidato de produto",
            "Afiliados/comissões",
            "marketplace_preflight(",
        ):
            self.assertNotIn(banned,body)

    def test_cloud_preserves_selected_ecosystem_area_on_aion_backed_workspace(self):
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        start=src.index("def _central_request_for_render")
        end=src.index("\ndef _hold_admin_before_trader_shell",start)
        body=src[start:end]
        self.assertIn('stored_choice in {"trader", "negocios", "investimentos", "aion"}',body)
        self.assertIn("requested = stored_choice",body)


if __name__ == "__main__":
    unittest.main()
