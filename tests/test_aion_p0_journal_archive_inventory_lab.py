"""Negative acceptance tests for evidence inventory ONLY (no P0 closure)."""
from __future__ import annotations
import hashlib
import os
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


    def test_direct_hash_refuses_oversized_stream(self):
        sample = self.root / "oversized.bin"
        sample.write_bytes(b"12345")
        with patch.object(inventory, "MAX_BYTES_PER_FILE", 4):
            with self.assertRaisesRegex(ValueError, "OVERSIZED_EVIDENCE_FILE"):
                inventory.sha256_regular_file(sample)

    def test_named_pipe_is_not_opened_as_blocking_evidence(self):
        if not hasattr(os, "mkfifo") or not hasattr(os, "O_NONBLOCK"):
            self.skipTest("FIFO test only supported on POSIX")
        pipe = self.root / "not-a-regular-file"
        os.mkfifo(pipe)
        with self.assertRaisesRegex(ValueError, "EVIDENCE_NOT_STABLE_REGULAR_FILE"):
            inventory.sha256_regular_file(pipe)

    def test_tree_entry_budget_fails_closed(self):
        self.populate()
        with patch.object(inventory, "MAX_TREE_ENTRIES", 3):
            result = inspect(self.root)
        self.assertEqual(result["status"], "BLOCKED_EVIDENCE_INCOMPLETE")
        self.assertTrue(any("EVIDENCE_TREE_ENTRY_LIMIT_EXCEEDED" in x for x in result["gaps"]))
        self.assertFalse(result["sources_authenticated"])

    def test_deep_tree_fails_closed(self):
        self.populate()
        nested = self.root
        for i in range(inventory.MAX_TREE_DEPTH + 1):
            nested = nested / ("layer_" + str(i))
            nested.mkdir()
        result = inspect(self.root)
        self.assertTrue(any("EVIDENCE_TREE_DEPTH_LIMIT_EXCEEDED" in x for x in result["gaps"]))

    def test_symlink_directory_prevents_false_complete_inventory(self):
        self.populate()
        destination = self.root / "tests"
        link = self.root / "untrusted-link"
        try:
            link.symlink_to(destination, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symlink creation not permitted on this runner: " + str(exc))
        result = inspect(self.root)
        self.assertEqual(result["status"], "BLOCKED_EVIDENCE_INCOMPLETE")
        self.assertTrue(any("EVIDENCE_TREE_LINK_OR_JUNCTION_UNTRUSTED" in x for x in result["gaps"]))

    def test_mutation_after_digest_before_report_is_denied(self):
        self.populate()
        prior_hash = inventory.sha256_regular_file
        def mutate_after_hash(path):
            digest = prior_hash(path)
            if path.name == REQUIRED["original_journal_a"]:
                # Simulates a post-read replacement. A hash alone cannot prove
                # the bytes stayed stable during evidence collection.
                path.write_bytes(path.read_bytes() + b"appended-after-hash")
            return digest
        with patch.object(inventory, "sha256_regular_file", side_effect=mutate_after_hash):
            result = inspect(self.root)
        self.assertEqual(result["files"]["original_journal_a"]["state"], "UNSAFE_OR_UNREADABLE")
        self.assertIn("original_journal_a:UNSAFE_OR_UNREADABLE", result["gaps"])
        self.assertFalse(result["historical_76_result_reproduced"])



if __name__ == "__main__":
    unittest.main()
