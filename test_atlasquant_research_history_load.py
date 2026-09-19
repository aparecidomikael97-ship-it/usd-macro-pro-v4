import pathlib
import unittest


ROOT=pathlib.Path(__file__).resolve().parent


class AtlasQuantResearchHistoryLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src=(ROOT/"usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        start=src.index("# AtlasQuant research history snapshot")
        end=src.index("# ABA 13 — V10.6.2 FRESH-PRICE SNAPSHOT RECOVERY")
        cls.segment=src[start:end]

    def test_improvements_reads_persistent_history_once(self):
        self.assertEqual(self.segment.count("_config_ler_v937()"),1)

    def test_all_four_research_labs_receive_shared_snapshot_copy(self):
        self.assertGreaterEqual(self.segment.count("_aq_research_df.copy()"),4)
        for renderer in (
            "render_calibration_lab(",
            "render_performance_lab(",
            "render_stability_lab(",
            "render_validation_readiness(",
        ):
            self.assertIn(renderer,self.segment)

    def test_old_duplicate_lab_load_variables_are_gone(self):
        for old in (
            "_aq_calib_df",
            "_aq_perf_df",
            "_aq_stability_df",
            "_aq_validation_df",
        ):
            self.assertNotIn(old,self.segment)

    def test_shared_load_error_is_fail_safe(self):
        self.assertIn("_aq_research_err",self.segment)
        self.assertIn("except Exception as _aq_research_load_exc",self.segment)

    def test_snapshot_is_copied_before_each_lab(self):
        expected=[
            "render_calibration_lab(\n                    _aq_research_df.copy(),",
            "render_performance_lab(\n                    _aq_research_df.copy(),",
            "render_stability_lab(\n                    _aq_research_df.copy(),",
            "render_validation_readiness(\n                    _aq_research_df.copy(),",
        ]
        for snippet in expected:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet,self.segment)


if __name__=="__main__":
    unittest.main()
