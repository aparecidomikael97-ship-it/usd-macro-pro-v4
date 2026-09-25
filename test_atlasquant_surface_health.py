import unittest
from pathlib import Path

from atlasquant_surface_health import (
    mark_surface_error,
    mark_surface_ok,
    surface_health_snapshot,
)


class AtlasQuantSurfaceHealthTests(unittest.TestCase):
    def test_unknown_until_surface_is_observed(self):
        snap = surface_health_snapshot({}, current_build="build-new")
        self.assertEqual(snap["counts"]["UNKNOWN"], 3)
        self.assertTrue(snap["has_unresolved"])
        self.assertFalse(snap["real_orders_enabled"])

    def test_success_replaces_previous_error_in_same_build(self):
        state = {}
        mark_surface_error(
            state,
            "home_radar",
            {"type": "RuntimeError"},
            build_id="build-a",
        )
        self.assertEqual(
            surface_health_snapshot(state, current_build="build-a")["items"][0]["state"],
            "DEGRADED",
        )
        mark_surface_ok(state, "home_radar", build_id="build-a")
        home = surface_health_snapshot(state, current_build="build-a")["items"][0]
        self.assertEqual(home["state"], "OK")
        self.assertEqual(home["error_type"], "")
        self.assertTrue(home["build_matches"])

    def test_old_build_evidence_never_proves_current_build_is_healthy(self):
        state = {}
        mark_surface_ok(state, "home_radar", build_id="build-old")
        home = surface_health_snapshot(state, current_build="build-new")["items"][0]
        self.assertEqual(home["state"], "STALE_BUILD")
        self.assertFalse(home["build_matches"])
        self.assertIn("build atual", home["next_action"])
        self.assertTrue(
            surface_health_snapshot(state, current_build="build-new")["has_unresolved"]
        )

    def test_legacy_observation_without_build_fails_closed_when_build_is_known(self):
        state = {
            "atlasquant_critical_surface_health": {
                "home_radar": {
                    "state": "OK",
                    "label": "Radar principal",
                    "detail": "legacy",
                    "error_type": "",
                }
            }
        }
        home = surface_health_snapshot(state, current_build="build-new")["items"][0]
        self.assertEqual(home["state"], "STALE_BUILD")

    def test_runtime_exception_exposes_type_not_message(self):
        state = {}
        mark_surface_error(
            state,
            "home_radar",
            RuntimeError("secret/path detail must not reach the UI"),
            build_id="build-a",
        )
        home = surface_health_snapshot(state, current_build="build-a")["items"][0]
        self.assertEqual(home["error_type"], "RuntimeError")
        self.assertNotIn("secret", home["error_type"])

    def test_unavailable_is_distinct_from_runtime_degraded(self):
        state = {}
        mark_surface_error(
            state,
            "advanced_radar",
            "ImportError",
            build_id="build-a",
            unavailable=True,
        )
        snap = surface_health_snapshot(state, current_build="build-a")
        advanced = next(x for x in snap["items"] if x["id"] == "advanced_radar")
        self.assertEqual(advanced["state"], "UNAVAILABLE")
        self.assertEqual(advanced["error_type"], "ImportError")
        self.assertIn("empacotamento", advanced["next_action"])

    def test_main_runtime_binds_surface_evidence_to_current_source_build(self):
        src = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(src.count("build_id=_ATLASQUANT_SOURCE_BUILD"), 6)
        self.assertIn(
            "current_build=_ATLASQUANT_SOURCE_BUILD",
            src,
        )
        self.assertIn('st.session_state.pop("atlasquant_master_panel_error", None)', src)
        self.assertIn('st.session_state.pop("aq_radar_advanced_error", None)', src)

    def test_all_ok_requires_every_critical_surface_on_current_build(self):
        state = {}
        for surface in ("home_radar", "advanced_radar", "master_panel"):
            mark_surface_ok(state, surface, build_id="build-a")
        snap = surface_health_snapshot(state, current_build="build-a")
        self.assertTrue(snap["all_ok"])
        self.assertEqual(snap["counts"]["OK"], 3)
        self.assertEqual(snap["counts"]["STALE_BUILD"], 0)
        self.assertFalse(snap["has_unresolved"])


if __name__ == "__main__":
    unittest.main()
