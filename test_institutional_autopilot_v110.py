import unittest
from pathlib import Path


class InstitutionalAutopilotSourceTests(unittest.TestCase):
    def test_autopilot_imports_institutional_engine(self):
        src=Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn("from institutional_engine_v110 import build_institutional_snapshot, SMT_COMPANIONS",src)

    def test_autopilot_persists_h1_m15_cache(self):
        src=Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn('"cache_v110"',src)
        self.assertIn('_cache_v110["m15"]',src)
        self.assertIn('_cache_v110["h1"]',src)

    def test_autopilot_builds_snapshot_for_all_pairs(self):
        src=Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn('build_institutional_snapshot(',src)
        self.assertIn('SMT_COMPANIONS.get(_pair)',src)
        self.assertIn('V11.0_INSTITUTIONAL_AUTOPILOT',src)


if __name__ == "__main__":
    unittest.main()
