"""Offline fixture-only checks for inert Journal source static review."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from aion_p0_journal_migration_static_review_lab import inspect, CASES


class JournalMigrationStaticReviewLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion_p0_static_review_")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def populate(self, mod="original", a_assert="self.assertTrue(True)", b_assert="self.assertEqual(1, 1)"):
        for i, (_, original, migrated, method) in enumerate(CASES):
            base = f"class Example:\n    def {method}(self):\n        {a_assert if i == 0 else b_assert}\n"
            (self.root / original).write_text(base, encoding="utf-8")
            if mod == "original":
                migrated_text = base
            elif mod == "benign":
                migrated_text = base.replace("        self.assert", "        pass\n        self.assert")
            elif mod == "assertion":
                migrated_text = base.replace("assertTrue(True)", "assertTrue(False)").replace("assertEqual(1, 1)", "assertEqual(1, 2)")
            else:
                migrated_text = "def not_the_test():\n    return True\n"
            (self.root / migrated).write_text(migrated_text, encoding="utf-8")

    def test_missing_root_blocks(self):
        r = inspect(self.root / "missing")
        self.assertEqual(r["status"], "HARD_NO_GO_REVIEW_REQUIRED")
        self.assertTrue(all(x["original_sha256"] is None for x in r["rows"]))

    def test_all_files_still_no_homologation(self):
        self.populate()
        r = inspect(self.root)
        self.assertEqual(r["journal_p0_homologated"], 0)
        self.assertFalse(r["historical_76_tests_executed"])
        self.assertFalse(r["production_allowed"])
        self.assertFalse(r["worker_allowed"])
        self.assertEqual(len(r["rows"]), 2)

    def test_unchanged_test_not_called_migrated(self):
        self.populate()
        r = inspect(self.root)
        for row in r["rows"]:
            self.assertIn("TEST_BODY_AST_UNCHANGED_NO_MIGRATION_PROVEN", row["findings"])

    def test_assertion_preserving_body_change_still_review(self):
        self.populate(mod="benign")
        r = inspect(self.root)
        for row in r["rows"]:
            self.assertIn("ASSERTION_AST_MATCHES_BUT_RUNTIME_EQUIVALENCE_UNPROVEN", row["findings"])
            self.assertFalse(row["migrated_behavior_proven"])

    def test_assertion_changed_flagged(self):
        self.populate(mod="assertion")
        r = inspect(self.root)
        for row in r["rows"]:
            self.assertIn("ASSERTION_AST_CHANGED_REQUIRES_HUMAN_DIFF", row["findings"])

    def test_missing_method_flagged(self):
        self.populate(mod="missing")
        r = inspect(self.root)
        self.assertTrue(all(any("METHOD_MISSING" in f for f in row["findings"]) for row in r["rows"]))

    def test_source_looks_executable_but_never_run(self):
        self.populate()
        for _, orig, _, _ in CASES:
            p = self.root / orig
            p.write_text('raise RuntimeError("DANGEROUS_IMPORT_SIDE_EFFECT")\n' + p.read_text())
        r = inspect(self.root)
        self.assertEqual(len(r["rows"]), 2)
        self.assertFalse(r["historical_76_tests_executed"])

    def test_invalid_syntax_rejected(self):
        self.populate()
        p = self.root / CASES[0][1]
        p.write_text("this is : invalid syntax")
        self.assertTrue(any("STATIC_READ_OR_PARSE_BLOCKED" in f for f in inspect(self.root)["rows"][0]["findings"]))

    def test_duplicate_sources_rejected(self):
        self.populate()
        other = self.root / "other"
        other.mkdir()
        (other / CASES[0][1]).write_text("class Empty: pass")
        self.assertIn("ORIGINAL:AMBIGUOUS_DUPLICATES", inspect(self.root)["rows"][0]["findings"])

    def test_source_oversize_rejected(self):
        self.populate()
        (self.root / CASES[0][1]).write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        self.assertIn("ORIGINAL:UNSAFE_SIZE_OR_TYPE", inspect(self.root)["rows"][0]["findings"])

    def test_case_list_tracks_only_two_original_errors(self):
        self.assertEqual({x[3] for x in CASES}, {
            "test_readback_rejects_forged_content",
            "test_direct_SQL_still_bypasses_limit_characterization",
        })


if __name__ == "__main__":
    unittest.main()
