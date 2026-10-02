import json
import shutil
import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_tenant_evidence_bundle import SUBJECT_FILES
from atlasquant_aion_tenant_persistence_review import (
    build_tenant_persistence_admin_review,
)

ROOT = Path(__file__).resolve().parent


def _admin():
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": "mikael",
            "role": "ADMIN",
            "credential_fingerprint": "a" * 32,
            "permissions": ["app:read", "admin:read", "aion:admin"],
            "authenticated_at": 10,
            "last_seen": 10,
        },
    }


class TenantPersistenceAdminReviewTests(unittest.TestCase):
    def test_current_bundle_is_ready_for_review_but_never_activation(self):
        result = build_tenant_persistence_admin_review(
            _admin(),
            repository_root=ROOT,
        )
        self.assertEqual(result["state"], "READY_FOR_ADMIN_REVIEW")
        self.assertTrue(result["bundle_valid"])
        self.assertEqual(result["bundle_reasons"], [])
        self.assertEqual(result["gate_state"], "READY_FOR_ADMIN_REVIEW")
        self.assertTrue(result["code_ready"])
        self.assertTrue(result["evidence_ready"])
        self.assertGreaterEqual(len(result["evidence_rows"]), 6)
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["production_persistence_activated"])
        self.assertFalse(result["automatic_activation"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["network_called"])
        self.assertTrue(result["review_only"])

    def test_incomplete_admin_context_is_blocked(self):
        result = build_tenant_persistence_admin_review(
            {"role": "ADMIN", "session": {"username": "mikael", "role": "ADMIN"}},
            repository_root=ROOT,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["production_persistence_activated"])

    def test_path_outside_repository_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "evidence.json"
            outside.write_text("{}", encoding="utf-8")
            result = build_tenant_persistence_admin_review(
                _admin(),
                repository_root=ROOT,
                evidence_path=outside,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "EVIDENCE_PATH_OUTSIDE_REPOSITORY")
        self.assertFalse(result["activation_authorized"])

    def test_tampered_bundle_is_blocked_fail_closed(self):
        source_bundle = (
            ROOT / "docs" / "aion" / "evidence" /
            "tenant_persistence_local_evidence.json"
        )
        bundle = json.loads(source_bundle.read_text(encoding="utf-8"))
        unique_files = sorted({
            relative
            for files in SUBJECT_FILES.values()
            for relative in files
        })
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for relative in unique_files:
                target = base / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            evidence = base / "docs" / "aion" / "evidence" / source_bundle.name
            evidence.parent.mkdir(parents=True, exist_ok=True)
            bundle["test_count"] = int(bundle.get("test_count") or 0) + 1
            evidence.write_text(
                json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = build_tenant_persistence_admin_review(
                _admin(),
                repository_root=base,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["bundle_valid"])
        self.assertIn("BUNDLE_DIGEST_MISMATCH", result["bundle_reasons"])
        self.assertFalse(result["activation_authorized"])


if __name__ == "__main__":
    unittest.main()
