from __future__ import annotations

import unittest

from atlasquant_reference_ui import (
    business_reference_home_html,
    reference_html,
)


class AtlasQuantNegociosReferenceFidelityTests(unittest.TestCase):
    def test_desktop_home_uses_approved_art_as_active_canvas(self):
        html = business_reference_home_html(
            mode="Avançado",
            name="Mikael",
            show_central=True,
        )
        self.assertIn('data-approved-art-active="true"', html)
        self.assertIn('data-workspace="negocios"', html)
        self.assertIn(
            "background-image:url(data:image/webp;base64,",
            html,
        )
        self.assertIn(
            'aria-label="Negócios · cockpit aprovado AtlasQuant"',
            html,
        )

    def test_generic_business_shell_no_longer_replaces_approved_home(self):
        html = business_reference_home_html()
        for forbidden in (
            "aq-ws-business-canvas",
            'class="aq-ws-shell"',
            'class="aq-ws-hero"',
            'class="aq-ws-modules"',
            "Operação & gestão",
        ):
            self.assertNotIn(forbidden, html)

    def test_approved_sidebar_and_cards_bridge_to_current_b2b_routes(self):
        html = business_reference_home_html()
        expected_routes = {
            "overview",
            "leads",
            "revenue",
            "companies",
            "proposals",
            "international",
            "followup",
            "finops",
            "crm",
            "success",
            "b2b",
        }
        for route in expected_routes:
            with self.subTest(route=route):
                self.assertIn(
                    f'data-route="{route}"',
                    html,
                )

    def test_approved_painted_labels_remain_accessible(self):
        html = business_reference_home_html()
        for label in (
            "Visão Geral",
            "Oportunidades",
            "Setores",
            "Empresas",
            "M&A",
            "Mercado Global",
            "Notícias Corporativas",
            "Próximos Eventos",
        ):
            with self.subTest(label=label):
                self.assertIn(
                    f'aria-label="{label}"',
                    html,
                )

    def test_current_b2b_capabilities_do_not_visually_replace_canvas(self):
        html = business_reference_home_html()
        canvas_index = html.index(
            'aria-label="Negócios · cockpit aprovado AtlasQuant"'
        )
        extended_index = html.index(
            '<details class="ref-business-extended">'
        )
        self.assertLess(canvas_index, extended_index)
        self.assertIn("Mais funções B2B", html)

    def test_mobile_cards_are_crops_from_approved_art(self):
        html = business_reference_home_html()
        self.assertIn("ref-mobile-header-negocios", html)
        self.assertGreaterEqual(
            html.count("data-mobile-crop="),
            7,
        )
        self.assertNotIn(
            "radial-gradient(circle at 72% 28%",
            html,
        )
        self.assertNotIn(
            "linear-gradient(145deg,#07172b,#0c2340",
            html,
        )

    def test_reference_html_routes_empty_negocios_to_approved_home(self):
        html = reference_html(
            "negocios",
            selected="",
            name="Mikael",
        )
        self.assertIn('data-approved-art-active="true"', html)
        self.assertIn("Mikael", html)
        self.assertNotIn('class="aq-ws-shell"', html)

    def test_selected_business_route_still_uses_functional_detail_surface(self):
        html = reference_html(
            "negocios",
            selected="proposals",
            name="Mikael",
        )
        self.assertIn("Propostas", html)
        self.assertIn("EXECUÇÃO", html)
        self.assertIn("BLOQUEADA", html)
        self.assertNotIn('data-approved-art-active="true"', html)

    def test_desktop_home_keeps_critical_execution_boundary_text(self):
        html = business_reference_home_html()
        self.assertIn(
            "sem execução automática",
            html.lower(),
        )

    def test_return_to_central_remains_available(self):
        html = business_reference_home_html(show_central=True)
        self.assertIn('data-route="central"', html)
        self.assertIn("← Central", html)

    def test_central_control_can_be_hidden_without_changing_approved_canvas(self):
        html = business_reference_home_html(show_central=False)
        self.assertNotIn('data-route="central"', html)
        self.assertIn('data-approved-art-active="true"', html)


if __name__ == "__main__":
    unittest.main()
