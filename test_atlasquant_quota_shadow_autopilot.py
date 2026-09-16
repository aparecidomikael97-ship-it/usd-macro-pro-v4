import pathlib
import unittest


ROOT=pathlib.Path(__file__).resolve().parent


class AtlasQuantQuotaShadowAutopilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=(ROOT/"autopilot_v107.py").read_text(encoding="utf-8")

    def test_autopilot_imports_quota_shadow_helpers(self):
        self.assertIn("from atlasquant_quota_shadow import",self.src)
        self.assertIn("build_quota_shadow_sample",self.src)
        self.assertIn("append_quota_shadow_sample",self.src)
        self.assertIn("summarize_quota_shadow",self.src)

    def test_quota_shadow_has_dedicated_runtime_path(self):
        self.assertIn(
            'QUOTA_SHADOW_PATH = "dados/atlasquant_quota_shadow_v1.json"',
            self.src,
        )

    def test_quota_shadow_is_observational_only(self):
        marker="# Never changes PAIR_ORDER, cadence, quota, API behavior or execution gates."
        self.assertIn(marker,self.src)
        self.assertIn('"automatic_expansion_allowed":False',self.src)

    def test_quota_shadow_is_recorded_before_status_persist(self):
        sample_pos=self.src.index("quota_sample=build_quota_shadow_sample(status)")
        status_pos=self.src.index('gh_put_json(STATUS_PATH,status,"V11.0 Autopilot: status")')
        self.assertLess(sample_pos,status_pos)

    def test_apptest_injects_data_branch(self):
        self.assertIn('"GITHUB_DATA_BRANCH"',self.src)


if __name__=="__main__":
    unittest.main()
