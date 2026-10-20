"""Negative acceptance tests for evidence inventory ONLY (no P0 closure)."""
from __future__ import annotations
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import aion_p0_journal_archive_inventory_lab as inventory
from aion_p0_journal_archive_inventory_lab import inspect, REQUIRED


class JournalEvidenceInventoryLAB(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aion_journal_evidence_lab_")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def populate(self, excluded=()):
        for label, basename in REQUIRED.items():
            if label in excluded:
                continue
            target = self.root / ("tests_migrated" if label.startswith("migrated_journal") else "logs" if label.endswith("_log") else "tests" if label.startswith("original_journal") else "") / basename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((label + "\n").encode())

    def test_even_matching_claimed_manifest_is_not_proof(self):
        self.populate()
        expected = hashlib.sha256(b"manifest\n").hexdigest()
        with patch.object(inventory, "PUBLISHED_MANIFEST_SHA256", expected):
            r = inspect(self.root)
        self.assertEqual(r["status"], "FILES_CAPTURED_REQUIRE_INDEPENDENT_COMPARISON_AND_REEXECUTION")
        self.assertTrue(r["files"]["manifest"]["matches_published_checkpoint_digest"])
        self.assertFalse(r["sources_authenticated"])
        self.assertFalse(r["historical_76_result_reproduced"])

    def test_missing_folder_never_passes(self):
        r = inspect(self.root / "nonexistent")
        self.assertEqual(r["status"], "BLOCKED_EVIDENCE_INCOMPLETE")
        self.assertIn("EVIDENCE_ROOT_MISSING_OR_SYMLINK", r["gaps"])

    def test_missing_original_source_never_passes(self):
        self.populate(excluded={"original_journal_b"})
        r = inspect(self.root)
        self.assertIn("original_journal_b:NOT_FOUND", r["gaps"])
        self.assertFalse(r["historical_tests_executed"])

    def test_duplicate_original_source_never_selects_one(self):
        self.populate()
        duplicate = self.root / "other" / REQUIRED["original_journal_a"]
        duplicate.parent.mkdir()
        duplicate.write_bytes(b"old")
        r = inspect(self.root)
        self.assertEqual(r["files"]["original_journal_a"]["state"], "AMBIGUOUS_MULTIPLE_COPIES")
        self.assertNotEqual(r["status"], "FILES_CAPTURED_REQUIRE_INDEPENDENT_COMPARISON_AND_REEXECUTION")

    def test_mismatched_published_manifest_hash_never_passes(self):
        self.populate()
        r = inspect(self.root)
        self.assertIn("MANIFEST_DIGEST_MISMATCH", r["gaps"])
        self.assertFalse(r["sources_authenticated"])

    def test_all_sources_are_hashes_not_authorization(self):
        self.populate()
        r = inspect(self.root)
        self.assertEqual(len(r["files"]), len(REQUIRED))
        self.assertEqual(r["files"]["original_journal_a"]["sha256"], hashlib.sha256(b"original_journal_a\n").hexdigest())
        self.assertFalse(r["production_allowed"])
        self.assertFalse(r["automatic_retry_authorized"])
        self.assertEqual(r["case_homologation"], "ZERO_OF_SIX")

    def test_missing_log_never_passes(self):
        self.populate(excluded={"migrated_run_log"})
        self.assertIn("migrated_run_log:NOT_FOUND", inspect(self.root)["gaps"])

    def test_empty_existing_root_never_passes(self):
        self.assertEqual(len(inspect(self.root)["gaps"]),len(REQUIRED))

    def test_hash_content_changes_are_visible(self):
        self.populate()
        p = self.root / "tests" / REQUIRED["original_journal_a"]
        first = inspect(self.root)["files"]["original_journal_a"]["sha256"]
        p.write_bytes(b"new distinct bytes")
        second = inspect(self.root)["files"]["original_journal_a"]["sha256"]
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
