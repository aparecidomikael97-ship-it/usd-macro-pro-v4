import unittest

from atlasquant_navigation_bridge import (
    active_revalidation,
    complete_surface_revalidation,
    consume_navigation_request,
    consume_revalidation_request,
    request_return_to_aion,
    request_surface_revalidation,
    revalidation_result,
    revalidation_target,
)


class AtlasQuantNavigationBridgeTests(unittest.TestCase):
    def test_targets_route_to_correct_page_and_mode(self):
        self.assertEqual(revalidation_target("home_radar")["page"], "🎯 Radar")
        self.assertEqual(revalidation_target("home_radar")["mode"], "Iniciante")
        self.assertEqual(revalidation_target("advanced_radar")["mode"], "Avançado")
        self.assertEqual(revalidation_target("master_panel")["page"], "🧭 Painel mestre")

    def test_request_is_explicit_and_non_executing(self):
        state = {}
        req = request_surface_revalidation(
            state,
            "master_panel",
            build_id="build-a",
        )
        self.assertEqual(req["state"], "REQUESTED")
        self.assertTrue(req["explicit_user_action"])
        self.assertFalse(req["executes_action"])
        self.assertFalse(req["real_orders_enabled"])

    def test_consumption_sets_navigation_before_widget_render(self):
        state = {}
        request_surface_revalidation(
            state,
            "advanced_radar",
            build_id="build-a",
        )
        active = consume_revalidation_request(
            state,
            available_pages=["🎯 Radar", "🧭 Painel mestre", "🧠 AION"],
        )
        self.assertEqual(active["state"], "NAVIGATED")
        self.assertEqual(state["atlasquant_experience_mode"], "Avançado")
        self.assertEqual(state["atlasquant_advanced_area"], "🎯 Radar")
        self.assertEqual(state["atlasquant_stable_nav_fallback"], "🎯 Radar")
        self.assertEqual(active_revalidation(state)["surface"], "advanced_radar")

    def test_missing_target_fails_closed(self):
        state = {}
        request_surface_revalidation(
            state,
            "master_panel",
            build_id="build-a",
        )
        result = consume_revalidation_request(
            state,
            available_pages=["🎯 Radar"],
        )
        self.assertEqual(result["state"], "NAVIGATION_BLOCKED")
        self.assertEqual(result["reason"], "TARGET_PAGE_UNAVAILABLE")
        self.assertNotIn("atlasquant_advanced_area", state)

    def test_completion_requires_same_requested_surface_and_build(self):
        state = {}
        request_surface_revalidation(state, "advanced_radar", build_id="build-a")
        consume_revalidation_request(
            state,
            available_pages=["🎯 Radar", "🧠 AION"],
        )
        self.assertIsNone(
            complete_surface_revalidation(
                state,
                "home_radar",
                build_id="build-a",
                succeeded=True,
            )
        )
        result = complete_surface_revalidation(
            state,
            "advanced_radar",
            build_id="build-a",
            succeeded=True,
        )
        self.assertEqual(result["state"], "CONFIRMED_OK")
        self.assertTrue(result["build_matches"])
        self.assertIsNone(active_revalidation(state))
        self.assertEqual(revalidation_result(state)["state"], "CONFIRMED_OK")

    def test_build_change_never_confirms_old_request(self):
        state = {}
        request_surface_revalidation(state, "master_panel", build_id="build-a")
        consume_revalidation_request(
            state,
            available_pages=["🧭 Painel mestre"],
        )
        result = complete_surface_revalidation(
            state,
            "master_panel",
            build_id="build-b",
            succeeded=True,
        )
        self.assertEqual(result["state"], "BUILD_CHANGED")
        self.assertFalse(result["build_matches"])

    def test_explicit_return_to_aion_sets_advanced_navigation(self):
        state = {}
        request_return_to_aion(state)
        result = consume_navigation_request(
            state,
            available_pages=["🎯 Radar", "🧠 AION"],
        )
        self.assertEqual(result["state"], "RETURN_REQUESTED")
        self.assertEqual(state["atlasquant_experience_mode"], "Avançado")
        self.assertEqual(state["atlasquant_advanced_area"], "🧠 AION")
        self.assertEqual(state["atlasquant_stable_nav_fallback"], "🧠 AION")


    def test_main_app_consumes_request_before_navigation_widgets_and_reports_result(self):
        from pathlib import Path
        src = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        append_aion = src.index('_nav_items.append("🧠 AION")')
        consume = src.index("consume_navigation_request(", append_aion)
        mode_widget = src.index("render_experience_mode_switch()", consume)
        self.assertLess(consume, mode_widget)
        self.assertIn("_aq_complete_guided_revalidation(", src)
        self.assertIn("request_return_to_aion(st.session_state)", src)
        self.assertIn('"guided_revalidation": revalidation_result(st.session_state) or {}', src)

    def test_aion_surface_panel_only_requests_navigation_on_explicit_button(self):
        from pathlib import Path
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Revalidação guiada", src)
        self.assertIn("aion_revalidate_surface_", src)
        self.assertIn("request_surface_revalidation(", src)
        self.assertIn("Cada botão apenas registra um pedido de navegação", src)
        self.assertIn('"guided_revalidation_state"', src)


if __name__ == "__main__":
    unittest.main()
