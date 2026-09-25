import unittest
from pathlib import Path

from atlasquant_surface_health import (
    mark_surface_error,
    mark_surface_ok,
    surface_health_snapshot,
)


class AtlasQuantSurfaceHealthTests(unittest.TestCase):
    def test_unknown_until_surface_is_observed(self):
        snap = surface_health_snapshot({})
        self.assertEqual(snap["counts"]["UNKNOWN"], 3)
        self.assertTrue(snap["has_unresolved"])
        self.assertFalse(snap["real_orders_enabled"])

    def test_success_replaces_previous_error(self):
        state = {}
        mark_surface_error(state, "home_radar", {"type": "RuntimeError"})
        self.assertEqual(
            surface_health_snapshot(state)["items"][0]["state"],
            "DEGRADED",
        )
        mark_surface_ok(state, "home_radar")
        home = surface_health_snapshot(state)["items"][0]
        self.assertEqual(home["state"], "OK")
        self.assertEqual(home["error_type"], "")

    def test_unavailable_is_distinct_from_runtime_degraded(self):
        state = {}
        mark_surface_error(
            state,
            "advanced_radar",
            "ImportError",
            unavailable=True,
        )
        snap = surface_health_snapshot(state)
        advanced = next(x for x in snap["items"] if x["id"] == "advanced_radar")
        self.assertEqual(advanced["state"], "UNAVAILABLE")
        self.assertEqual(advanced["error_type"], "ImportError")

    def test_main_runtime_records_and_clears_critical_surface_failures(self):
        src = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn('mark_surface_ok(st.session_state, "home_radar")', src)
        self.assertIn('mark_surface_error(st.session_state, "home_radar"', src)
        self.assertIn('mark_surface_ok(st.session_state, "advanced_radar")', src)
        self.assertIn('mark_surface_error(\n                        st.session_state,\n                        "advanced_radar"', src)
        self.assertIn('mark_surface_ok(st.session_state, "master_panel")', src)
        self.assertIn('st.session_state.pop("atlasquant_master_panel_error", None)', src)
        self.assertIn('"critical_surfaces": surface_health_snapshot(st.session_state)', src)

    def test_all_ok_requires_every_critical_surface_observed_ok(self):
        state = {}
        for surface in ("home_radar", "advanced_radar", "master_panel"):
            mark_surface_ok(state, surface)
        snap = surface_health_snapshot(state)
        self.assertTrue(snap["all_ok"])
        self.assertEqual(snap["counts"]["OK"], 3)
        self.assertFalse(snap["has_unresolved"])


if __name__ == "__main__":
    unittest.main()
