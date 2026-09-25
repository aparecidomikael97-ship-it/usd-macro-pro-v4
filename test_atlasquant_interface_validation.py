import unittest

from atlasquant_interface_validation import interface_validation_mission


def snapshot(items, build="build-a"):
    return {"current_build": build, "items": items}


class AtlasQuantInterfaceValidationMissionTests(unittest.TestCase):
    def test_missing_build_fails_closed(self):
        result = interface_validation_mission({"items": []})
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["truth_state"], "UNKNOWN")
        self.assertFalse(result["all_confirmed_current_build"])
        self.assertFalse(result["executes_action"])

    def test_all_unknown_is_not_failure(self):
        result = interface_validation_mission(
            snapshot([
                {"id": "home_radar", "label": "Radar principal", "state": "UNKNOWN"},
                {"id": "master_panel", "label": "Painel Mestre", "state": "UNKNOWN"},
                {"id": "advanced_radar", "label": "Radar avançado", "state": "UNKNOWN"},
            ])
        )
        self.assertEqual(result["state"], "NOT_STARTED")
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["unknown"], 3)
        self.assertEqual(result["confirmed"], 0)

    def test_progress_counts_only_ok_from_current_build(self):
        result = interface_validation_mission(
            snapshot([
                {
                    "id": "home_radar",
                    "label": "Radar principal",
                    "state": "OK",
                    "build_id": "build-a",
                },
                {
                    "id": "master_panel",
                    "label": "Painel Mestre",
                    "state": "OK",
                    "build_id": "build-old",
                },
                {
                    "id": "advanced_radar",
                    "label": "Radar avançado",
                    "state": "UNKNOWN",
                },
            ])
        )
        self.assertEqual(result["state"], "IN_PROGRESS")
        self.assertEqual(result["confirmed"], 1)
        self.assertEqual(result["stale"], 1)
        self.assertEqual(result["remaining"], 2)
        self.assertEqual(result["progress_pct"], 33.3)
        self.assertEqual(result["next_surface"], "master_panel")

    def test_confirmed_failure_has_attention_state(self):
        result = interface_validation_mission(
            snapshot([
                {
                    "id": "home_radar",
                    "label": "Radar principal",
                    "state": "OK",
                    "build_id": "build-a",
                },
                {
                    "id": "master_panel",
                    "label": "Painel Mestre",
                    "state": "DEGRADED",
                    "build_id": "build-a",
                    "next_action": "Reabrir Painel Mestre.",
                },
                {
                    "id": "advanced_radar",
                    "label": "Radar avançado",
                    "state": "UNKNOWN",
                },
            ])
        )
        self.assertEqual(result["state"], "ATTENTION")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["next_surface"], "master_panel")
        self.assertIn("Reabrir", result["next_action"])

    def test_complete_requires_three_current_build_confirmations(self):
        items = [
            {
                "id": surface,
                "label": surface,
                "state": "OK",
                "build_id": "build-a",
            }
            for surface in ("home_radar", "master_panel", "advanced_radar")
        ]
        result = interface_validation_mission(snapshot(items))
        self.assertEqual(result["state"], "COMPLETE")
        self.assertEqual(result["confirmed"], 3)
        self.assertEqual(result["remaining"], 0)
        self.assertEqual(result["progress_pct"], 100.0)
        self.assertTrue(result["all_confirmed_current_build"])
        self.assertFalse(result["automatic_repair"])
        self.assertFalse(result["automatic_deploy"])
        self.assertFalse(result["real_orders_enabled"])


if __name__ == "__main__":
    unittest.main()
