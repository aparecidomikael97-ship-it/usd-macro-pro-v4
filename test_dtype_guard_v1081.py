import unittest
from pathlib import Path
import pandas as pd
import numpy as np

class DtypeGuardV1081Tests(unittest.TestCase):
    def test_bool_assignment_after_object_normalization(self):
        df = pd.DataFrame({
            "auto_managed": [np.nan],
            "timing_migrated_v107": [np.nan],
            "hit_1h": [np.nan],
        })
        for c in ("auto_managed", "timing_migrated_v107", "hit_1h"):
            df[c] = df[c].astype("object")
        df.at[0, "auto_managed"] = True
        df.at[0, "timing_migrated_v107"] = True
        df.at[0, "hit_1h"] = False
        self.assertIs(df.at[0, "auto_managed"], True)
        self.assertIs(df.at[0, "timing_migrated_v107"], True)
        self.assertIs(df.at[0, "hit_1h"], False)

    def test_autopilot_source_has_guard_before_migration(self):
        src = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn("def _normalize_news_validation_dtypes_v1081", src)
        self.assertIn("df = _normalize_news_validation_dtypes_v1081(df)", src)
        self.assertIn('"auto_managed", "timing_migrated_v107"', src)

    def test_currency_news_source_has_same_guard(self):
        src = Path("currency_news_v107.py").read_text(encoding="utf-8")
        self.assertIn("def _normalize_validation_dtypes_v1081", src)
        self.assertIn('"hit_1h", "hit_4h", "hit_24h"', src)

if __name__ == "__main__":
    unittest.main()
