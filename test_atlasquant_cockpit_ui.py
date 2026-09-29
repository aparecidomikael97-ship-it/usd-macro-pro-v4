import unittest

from atlasquant_cockpit_ui import (
    FLOATING_TABS,
    FLOATING_PANELS,
    LAYOUT_ZONES,
    MODULE_CARDS,
    MOTTO,
    VIDEO_SURFACES,
    cockpit_contract,
    cockpit_html,
)


class AtlasQuantCockpitUiTests(unittest.TestCase):
    def test_motto_is_visible_and_exact(self):
        self.assertEqual(MOTTO, "Poderoso por dentro. Simples por fora.")
        self.assertIn(MOTTO, cockpit_html())

    def test_core_ecosystem_modules_are_present(self):
        ids={row["id"] for row in MODULE_CARDS}
        required={
            "radar","macro","micro","geopolitica","fundamentalista","ict_smc",
            "calendario","pre_noticia","laboratorio","paper","risco","investimentos",
            "aion","admin","videos","negocios","memoria","seguranca","academy","treasury",
        }
        self.assertTrue(required.issubset(ids))

    def test_every_module_has_unique_direct_route(self):
        routes=[row["route"] for row in MODULE_CARDS]
        self.assertEqual(len(routes),len(set(routes)))
        self.assertTrue(all(route.startswith("/") for route in routes))
        by_id={row["id"]:row["route"] for row in MODULE_CARDS}
        self.assertEqual(by_id["geopolitica"],"/geopolitica")
        self.assertEqual(by_id["videos"],"/videos")
        self.assertEqual(by_id["aion"],"/aion")

    def test_combined_cockpit_layout_has_required_zones(self):
        self.assertEqual(
            tuple(LAYOUT_ZONES),
            (
                "identity_and_status",
                "market_ticker",
                "floating_context_tabs",
                "video_command_deck",
                "ecosystem_module_grid",
                "holographic_global_core",
                "intelligence_panels",
                "bottom_action_dock",
            ),
        )
        panel_ids={row["id"] for row in FLOATING_PANELS}
        self.assertTrue(
            {"risk_map","market_bias","economic_calendar","live_news","aion_voice"}.issubset(panel_ids)
        )
        html=cockpit_html()
        self.assertIn("aq-video-deck",html)
        self.assertIn('data-route="/geopolitica"',html)

    def test_video_cycle_preserves_transparent_weekly_protocol(self):
        by_id={row["id"]:row for row in VIDEO_SURFACES}
        self.assertEqual(by_id["weekly_outlook"]["schedule"],"segunda_cedo")
        self.assertEqual(by_id["daily_outlook"]["schedule"],"segunda_a_sexta_cedo")
        self.assertEqual(by_id["daily_close"]["schedule"],"segunda_a_sexta_fim_do_dia")
        self.assertEqual(by_id["weekly_close"]["schedule"],"sexta_fim_do_dia")
        self.assertEqual(by_id["weekly_close"]["transparency"],"sem_maquiar_resultado")

    def test_floating_tabs_include_video_workflow(self):
        self.assertEqual(
            tuple(FLOATING_TABS),
            (
                "Visão Geral","Análise da Semana","Análise do Dia",
                "Fechamento do Dia","Fechamento Semanal",
            ),
        )

    def test_shell_is_not_implicitly_wired_to_production(self):
        contract=cockpit_contract()
        self.assertFalse(contract["production_wired"])
        self.assertEqual(contract["style"],"spaceship_cockpit_hangar_digital")


if __name__=="__main__":
    unittest.main()
