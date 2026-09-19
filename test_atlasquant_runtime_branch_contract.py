import pathlib
import unittest


ROOT=pathlib.Path(__file__).resolve().parent


class AtlasQuantRuntimeBranchContractTests(unittest.TestCase):
    def test_autopilot_workflow_targets_dedicated_runtime_branch(self):
        src=(ROOT/".github/workflows/autopilot-v107.yml").read_text(encoding="utf-8")
        self.assertIn('GITHUB_DATA_BRANCH: "atlasquant-runtime"',src)
        self.assertIn('GITHUB_BRANCH_HISTORICO: "atlasquant-runtime"',src)
        self.assertNotIn('GITHUB_BRANCH_HISTORICO: "main"',src)

    def test_scheduled_workflow_checks_out_runtime_code_explicitly(self):
        src=(ROOT/".github/workflows/autopilot-v107.yml").read_text(encoding="utf-8")
        normalized=src.replace('"',"")
        self.assertIn("actions/checkout@",src)
        self.assertIn("ref: atlasquant-runtime",normalized)
        self.assertIn("CHAVE_TWELVE_DATA:",src)
        self.assertIn("secrets.CHAVE_TWELVE_DATA",src)

    def test_autopilot_python_uses_runtime_policy(self):
        src=(ROOT/"autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn("resolve_runtime_branch",src)
        self.assertIn("require_runtime_branch",src)
        self.assertNotIn('BRANCH = os.getenv("GITHUB_BRANCH_HISTORICO", "main")',src)

    def test_streamlit_persistence_uses_runtime_resolver(self):
        src=(ROOT/"usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("from atlasquant_runtime_store import resolve_runtime_branch",src)
        self.assertGreaterEqual(src.count("resolve_runtime_branch("),4)

    def test_runtime_branch_policy_never_defaults_to_main(self):
        src=(ROOT/"atlasquant_runtime_store.py").read_text(encoding="utf-8")
        self.assertIn('DEFAULT_RUNTIME_BRANCH = "atlasquant-runtime"',src)


    def test_runtime_consumers_use_resolver(self):
        paths=[
            "pair_intelligence_v110.py",
            "market_map_v10.py",
            "master_panel_v102.py",
            "autopilot_panel_v107.py",
            "currency_news_v107.py",
        ]
        for path in paths:
            with self.subTest(path=path):
                src=(ROOT/path).read_text(encoding="utf-8")
                self.assertIn("resolve_runtime_branch",src)
                self.assertNotIn('GITHUB_BRANCH_HISTORICO", "main"',src)
                self.assertNotIn('GITHUB_BRANCH_HISTORICO","main"',src)

    def test_flight_recorder_persistence_targets_runtime_policy(self):
        src=(ROOT/"atlasquant_flight_recorder_panel.py").read_text(encoding="utf-8")
        self.assertIn("resolve_runtime_branch",src)
        store=(ROOT/"atlasquant_flight_recorder_store.py").read_text(encoding="utf-8")
        self.assertIn("require_runtime_branch",store)

    def test_pair_captures_flight_recorder_before_basic_return(self):
        src=(ROOT/"pair_intelligence_v110.py").read_text(encoding="utf-8")
        capture_pos=src.index("_flight_capture = capture_flight_recorder")
        basic_pos=src.index("if not _is_pro:")
        self.assertLess(capture_pos,basic_pos)

    def test_all_packaged_workflows_avoid_main_runtime_writes(self):
        paths=[
            ROOT/".github/workflows/autopilot-v107.yml",
            ROOT/".github/workflows/coleta_automatica.yml",
        ]
        for path in paths:
            with self.subTest(path=str(path)):
                src=path.read_text(encoding="utf-8")
                self.assertIn("atlasquant-runtime",src)
                self.assertNotIn('GITHUB_BRANCH_HISTORICO: "main"',src)
                self.assertNotIn('GITHUB_BRANCH_HISTORICO = "main"',src)

    def test_legacy_news_modules_use_runtime_resolver(self):
        for name in ("currency_news_v1061.py","currency_news_v1062.py"):
            with self.subTest(name=name):
                src=(ROOT/name).read_text(encoding="utf-8")
                self.assertIn("resolve_runtime_branch",src)
                self.assertNotIn('GITHUB_BRANCH_HISTORICO", os.getenv("GITHUB_BRANCH_HISTORICO", "main")',src)


if __name__=="__main__":
    unittest.main()
