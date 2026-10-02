import json
import shutil
import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_tenant_evidence_binding import EVIDENCE_KINDS
from atlasquant_aion_tenant_evidence_bundle import (
    SUBJECT_FILES,
    build_local_evidence_bundle,
    normalized_file_digest,
    verify_local_evidence_bundle,
)

ROOT = Path(__file__).resolve().parent
RESULT = "sha256:" + ("d" * 64)
HEAD = "e" * 40
STAMP = "2026-10-02T10:00:00+00:00"

class TenantEvidenceBundleTests(unittest.TestCase):
    def test_current_sources_build_verifiable_bundle(self):
        bundle = build_local_evidence_bundle(
            ROOT,
            result_digest=RESULT,
            test_count=51,
            source_head_sha=HEAD,
            generated_at=STAMP,
        )
        checked = verify_local_evidence_bundle(ROOT, bundle)
        self.assertTrue(checked["valid"])
        self.assertEqual(set(bundle["records"]), set(EVIDENCE_KINDS))
        self.assertFalse(bundle["controls"]["automatic_activation"])

    def test_bundle_tamper_is_detected(self):
        bundle = build_local_evidence_bundle(
            ROOT,
            result_digest=RESULT,
            test_count=51,
            source_head_sha=HEAD,
            generated_at=STAMP,
        )
        bundle["test_count"] = 999
        checked = verify_local_evidence_bundle(ROOT, bundle)
        self.assertFalse(checked["valid"])
        self.assertIn("BUNDLE_DIGEST_MISMATCH", checked["reasons"])

    def test_line_endings_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            lf = base / "lf.py"
            crlf = base / "crlf.py"
            lf.write_bytes(b"x = 1\ny = 2\n")
            crlf.write_bytes(b"x = 1\r\ny = 2\r\n")
            self.assertEqual(
                normalized_file_digest(base, "lf.py"),
                normalized_file_digest(base, "crlf.py"),
            )

    def test_source_change_makes_bundle_stale(self):
        unique = sorted({
            path
            for files in SUBJECT_FILES.values()
            for path in files
        })
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for relative in unique:
                shutil.copy2(ROOT / relative, base / relative)
            bundle = build_local_evidence_bundle(
                base,
                result_digest=RESULT,
                test_count=51,
                source_head_sha=HEAD,
                generated_at=STAMP,
            )
            target = base / "atlasquant_aion_tenant_durable_store.py"
            target.write_text(
                target.read_text(encoding="utf-8") + "\n# drift\n",
                encoding="utf-8",
            )
            checked = verify_local_evidence_bundle(base, bundle)
            self.assertFalse(checked["valid"])
            self.assertTrue(
                any(reason.endswith("_SUBJECT_STALE") for reason in checked["reasons"])
            )

    def test_committed_local_evidence_matches_current_sources(self):
        path = ROOT / "docs" / "aion" / "evidence" / "tenant_persistence_local_evidence.json"
        if not path.exists():
            self.skipTest("local evidence bundle not generated yet")
        bundle = json.loads(path.read_text(encoding="utf-8"))
        checked = verify_local_evidence_bundle(ROOT, bundle)
        self.assertTrue(checked["valid"], checked["reasons"])
        self.assertFalse(bundle["controls"]["evidence_is_authority"])
        self.assertFalse(bundle["controls"]["production_persistence_activated"])

    def test_real_bundle_reaches_admin_review_but_never_activation(self):
        from atlasquant_aion_tenant_persistence_gate import tenant_persistence_readiness
        path = ROOT / "docs" / "aion" / "evidence" / "tenant_persistence_local_evidence.json"
        if not path.exists():
            self.skipTest("local evidence bundle not generated yet")
        bundle = json.loads(path.read_text(encoding="utf-8"))
        result = tenant_persistence_readiness(bundle["records"])
        self.assertEqual(result["state"], "READY_FOR_ADMIN_REVIEW")
        self.assertTrue(result["evidence_ready"])
        self.assertFalse(result["persistence_activation_authorized"])
        self.assertFalse(result["automatic_activation"])
        self.assertFalse(result["external_action_executed"])

if __name__ == "__main__":
    unittest.main()
