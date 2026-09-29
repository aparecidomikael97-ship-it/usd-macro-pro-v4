import unittest

from atlasquant_cockpit_ui import (
    FLOATING_TABS,
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
