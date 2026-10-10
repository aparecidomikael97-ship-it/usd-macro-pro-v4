"""Adversarial source-only tests. No Autopilot imports or network access."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from atlasquant_aion_v2_autopilot_write_inventory_audit import (
    EXPECTED, audit, find_sinks,
)

ROOT = Path(__file__).resolve().parents[1]


class InventoryTests(unittest.TestCase):
    def test_exact_twelve_sinks(self):
        r = audit(ROOT)
        self.assertTrue(r["inventory_consistent"], r)
        self.assertEqual(r["generic_sink_count"], 12)
        self.assertEqual({tuple(x) for x in r["generic_sinks"]}, EXPECTED)

    def test_inventory_match_does_not_mean_safe(self):
        r = audit(ROOT)
        self.assertEqual(r["state"], "KNOWN_RISK_REVIEW_REQUIRED")
        self.assertFalse(r["remote_durability_certified"])
        self.assertFalse(r["cross_process_cas_certified"])
        self.assertFalse(r["safe_to_deploy"])

    def test_two_actual_guarded_evidence_sinks(self):
        self.assertEqual(audit(ROOT)["shadow_flight_guard_calls"], 2)

    def test_generic_success_without_readback_shape_detected(self):
        self.assertTrue(audit(ROOT)["generic_http_success_without_readback_shape"])

    def test_budget_retry_shape_detected_in_this_ancestry(self):
        self.assertTrue(audit(ROOT)["budget_reported_conflict_retry_shape"])

    def test_zero_exit_recorded_without_claiming_green_write(self):
        self.assertTrue(audit(ROOT)["main_has_zero_exit"])

    def test_new_dynamic_sink_cannot_be_hidden(self):
        src=(ROOT/"autopilot_v107.py").read_text("utf-8")
        src=src.replace("def main() -> int:",
                        'def main() -> int:\n    gh_put_json("fixture", {}, "test")',1)
        found=find_sinks(src)
        self.assertIn(("gh_put_json","DYNAMIC_OR_MISSING_TARGET"),found)
        self.assertEqual(len(found),13)

    def test_duplicate_sink_is_visible(self):
        src=(ROOT/"autopilot_v107.py").read_text("utf-8")
        src=src.replace("def main() -> int:",
                        'def main() -> int:\n    gh_put_json(SCANNER_PATH, {}, "test")',1)
        self.assertEqual(find_sinks(src).count(("gh_put_json","SCANNER_PATH")),2)

    def test_removed_known_sink_is_visible(self):
        src=(ROOT/"autopilot_v107.py").read_text("utf-8")
        src=src.replace("gh_put_json(SERIES_PATH,_TD_SERIES,",
                        "gh_put_other(SERIES_PATH,_TD_SERIES,",1)
        self.assertNotIn(("gh_put_json","SERIES_PATH"),find_sinks(src))

    def test_does_not_import_actual_autopilot(self):
        sys.modules.pop("autopilot_v107",None)
        self.assertTrue(audit(ROOT)["source_only"])
        self.assertNotIn("autopilot_v107",sys.modules)


if __name__ == "__main__":
    unittest.main()
