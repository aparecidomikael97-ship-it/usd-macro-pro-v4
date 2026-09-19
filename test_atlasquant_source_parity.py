import unittest

from atlasquant_source_parity import (
    compare_source_trees,
    is_runtime_data_path,
    parse_ls_tree,
)


class AtlasQuantSourceParityTests(unittest.TestCase):
    def test_identical_source_with_different_runtime_data_passes(self):
        integration={
            "app.py":"a"*40,
            "docs/readme.md":"b"*40,
            "dados/autopilot_status_v107.json":"c"*40,
        }
        runtime={
            "app.py":"a"*40,
            "docs/readme.md":"b"*40,
            "dados/autopilot_status_v107.json":"d"*40,
            "dados/paper_trades_v112.csv":"e"*40,
        }
        out=compare_source_trees(integration,runtime)
        self.assertEqual(out["status"],"SOURCE_PARITY_OK")
        self.assertEqual(out["checked_files"],2)
        self.assertTrue(out["runtime_data_ignored"])
        self.assertFalse(out["automatic_merge_allowed"])
        self.assertFalse(out["automatic_runtime_overwrite_allowed"])

    def test_source_blob_mismatch_fails_closed(self):
        out=compare_source_trees({"a.py":"a"*40},{"a.py":"b"*40})
        self.assertEqual(out["status"],"SOURCE_PARITY_MISMATCH")
        self.assertEqual(out["mismatched"],["a.py"])
        self.assertTrue(out["manual_reconciliation_required"])

    def test_unknown_dados_file_is_not_hidden_by_runtime_allowlist(self):
        out=compare_source_trees(
            {"dados/unexpected.json":"a"*40},
            {"dados/unexpected.json":"b"*40},
        )
        self.assertEqual(out["status"],"SOURCE_PARITY_MISMATCH")
        self.assertEqual(out["mismatched"],["dados/unexpected.json"])

    def test_source_file_missing_on_either_side_fails(self):
        left=compare_source_trees({"a.py":"a"*40},{})
        right=compare_source_trees({},{"a.py":"a"*40})
        self.assertEqual(left["only_integration"],["a.py"])
        self.assertEqual(right["only_runtime"],["a.py"])

    def test_runtime_data_prefix_is_explicit(self):
        self.assertTrue(is_runtime_data_path("dados/autopilot_status_v107.json"))
        self.assertTrue(is_runtime_data_path("./dados/autopilot_status_v107.json"))
        self.assertFalse(is_runtime_data_path("dados/unexpected.json"))
        self.assertFalse(is_runtime_data_path("docs/dados/x.md"))
        self.assertFalse(is_runtime_data_path("atlasquant.py"))

    def test_ls_tree_parser_is_strict(self):
        raw=(
            "100644 blob "+"a"*40+"\tapp.py\n"
            "100644 blob "+"b"*40+"\tdocs/readme.md\n"
        )
        out=parse_ls_tree(raw)
        self.assertEqual(out["app.py"],"a"*40)
        self.assertEqual(out["docs/readme.md"],"b"*40)
        for bad in (
            "bad line",
            "100644 blob xyz\tapp.py",
            "100644 blob "+"a"*40+"\t../escape.py",
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_ls_tree(bad)


if __name__=="__main__":
    unittest.main()
