import unittest

from atlasquant_branch_drift import (
    RUNTIME_MUTABLE_PATHS,
    audit_branch_drift,
    classify_path,
    drift_release_message,
)


class AtlasQuantBranchDriftTests(unittest.TestCase):
    def test_known_runtime_file(self):
        self.assertEqual(classify_path("dados/autopilot_status_v107.json"),"RUNTIME")

    def test_unknown_data_file_requires_review(self):
        self.assertEqual(classify_path("dados/unknown.csv"),"UNKNOWN_DATA")

    def test_python_file_is_code(self):
        self.assertEqual(classify_path("usd_macro_pro_v4_cloud.py"),"CODE_OR_CONFIG")

    def test_current_main_dev_drift_can_be_runtime_only(self):
        audit=audit_branch_drift([
            "dados/autopilot_inputs_v107.json",
            "dados/autopilot_status_v107.json",
            "dados/configuracoes_completas_v937.csv",
            "dados/currency_news_current_v107.json",
            "dados/currency_news_validation_v1061.csv",
            "dados/master_market_map_v102.json",
            "dados/scanner_tecnico_v934.json",
        ])
        self.assertTrue(audit.runtime_only)
        self.assertFalse(audit.requires_code_reconciliation)

    def test_current_evidence_outputs_are_runtime_mutable(self):
        paths=[
            "dados/atlasquant_flight_recorder.jsonl",
            "dados/atlasquant_quota_shadow_v1.json",
            "dados/atlasquant_shadow_samples.jsonl",
            "dados/paper_trades_v112.csv",
            "dados/paper_trading_summary_v112.json",
            "dados/paper_setup_audit_v114.csv",
            "dados/paper_setup_performance_v114.csv",
            "dados/paper_setup_summary_v114.json",
        ]
        audit=audit_branch_drift(paths)
        self.assertTrue(audit.runtime_only)
        self.assertFalse(audit.requires_code_reconciliation)
        self.assertFalse(audit.unknown_data_files)

    def test_code_change_blocks_runtime_only_label(self):
        audit=audit_branch_drift([
            "dados/autopilot_status_v107.json",
            "autopilot_v107.py",
        ])
        self.assertFalse(audit.runtime_only)
        self.assertTrue(audit.requires_code_reconciliation)

    def test_message_distinguishes_runtime_drift(self):
        audit=audit_branch_drift(["dados/autopilot_status_v107.json"])
        self.assertIn("runtime-data only",drift_release_message(audit))

    def test_allowlist_is_nonempty(self):
        self.assertGreater(len(RUNTIME_MUTABLE_PATHS),5)


    def test_path_normalization_cannot_bypass_runtime_classification(self):
        self.assertEqual(classify_path("./dados/scanner_tecnico_v934.json"),"RUNTIME")
        self.assertEqual(classify_path("dados//scanner_tecnico_v934.json"),"RUNTIME")
        self.assertEqual(classify_path("../dados/scanner_tecnico_v934.json"),"CODE_OR_CONFIG")
        self.assertEqual(classify_path("/dados/scanner_tecnico_v934.json"),"CODE_OR_CONFIG")
        audit=audit_branch_drift(["../dados/scanner_tecnico_v934.json"])
        self.assertFalse(audit.runtime_only)
        self.assertTrue(audit.requires_code_reconciliation)


if __name__=="__main__":
    unittest.main()
