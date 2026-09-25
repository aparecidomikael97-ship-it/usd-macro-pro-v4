import unittest

from atlasquant_aion_validation_center import (
    validation_center_rows,
    validation_center_snapshot,
)


def _system(states, *, build="build-a", production=None):
    items = []
    for surface, state in states.items():
        items.append({
            "id": surface,
            "state": state,
            "build_id": build,
            "current_build": build,
            "build_matches": True,
            "next_action": f"Revalidar {surface}.",
        })
    out = {
        "truth_state": "CONFIRMED",
        "source_build": build,
        "critical_surfaces": {"items": items},
    }
    if production is not None:
        out["production_validation"] = production
    return out


class AtlasQuantAionValidationCenterTests(unittest.TestCase):
    def test_local_session_requires_all_three_surfaces_on_current_build(self):
        snap = validation_center_snapshot(
            _system({
                "home_radar": "OK",
                "advanced_radar": "OK",
                "master_panel": "OK",
            }),
            runtime_status="CONFIRMED",
        )
        self.assertTrue(snap["local_session_validated"])
        self.assertEqual(snap["critical_confirmed"], 3)
        self.assertEqual(snap["local_state"], "LOCAL_SESSION_VALIDATED")
        self.assertFalse(snap["production_confirmed"])
        self.assertFalse(snap["deploy_allowed"])
        self.assertFalse(snap["real_orders_enabled"])

    def test_local_evidence_never_confirms_production(self):
        snap = validation_center_snapshot(
            _system({
                "home_radar": "OK",
                "advanced_radar": "OK",
                "master_panel": "OK",
            }),
            runtime_status="CONFIRMED",
        )
        self.assertEqual(snap["production_state"], "NOT_CONFIRMED")
        self.assertIn("deploy de produção", " ".join(snap["next_actions"]))

    def test_production_confirmation_requires_same_build(self):
        snap = validation_center_snapshot(
            _system(
                {
                    "home_radar": "OK",
                    "advanced_radar": "OK",
                    "master_panel": "OK",
                },
                build="build-new",
                production={"state": "CONFIRMED", "build_id": "build-old"},
            ),
            runtime_status="CONFIRMED",
        )
        self.assertFalse(snap["production_confirmed"])

        snap2 = validation_center_snapshot(
            _system(
                {
                    "home_radar": "OK",
                    "advanced_radar": "OK",
                    "master_panel": "OK",
                },
                build="build-new",
                production={"state": "CONFIRMED", "build_id": "build-new"},
            ),
            runtime_status="CONFIRMED",
        )
        self.assertTrue(snap2["production_confirmed"])

    def test_stale_or_unknown_surface_keeps_local_session_incomplete(self):
        snap = validation_center_snapshot(
            _system({
                "home_radar": "OK",
                "advanced_radar": "STALE_BUILD",
                "master_panel": "UNKNOWN",
            }),
            runtime_status="UNKNOWN",
        )
        self.assertFalse(snap["local_session_validated"])
        self.assertEqual(snap["critical_confirmed"], 1)
        self.assertTrue(snap["next_actions"])
        rows = validation_center_rows(snap)
        self.assertEqual(len(rows), 3)

    def test_surface_build_mismatch_fails_closed_even_if_state_says_ok(self):
        system = _system({
            "home_radar": "OK",
            "advanced_radar": "OK",
            "master_panel": "OK",
        }, build="build-new")
        system["critical_surfaces"]["items"][0]["build_id"] = "build-old"
        system["critical_surfaces"]["items"][0]["build_matches"] = False
        snap = validation_center_snapshot(system, runtime_status="CONFIRMED")
        self.assertFalse(snap["local_session_validated"])
        self.assertEqual(snap["critical_confirmed"], 2)


if __name__ == "__main__":
    unittest.main()
