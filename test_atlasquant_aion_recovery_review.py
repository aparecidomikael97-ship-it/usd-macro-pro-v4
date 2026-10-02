import unittest
from copy import deepcopy

from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    default_checkpoint,
)
from atlasquant_aion_recovery_review import build_recovery_review


def _admin():
    return {
        "role": "ADMIN",
        "session": {
            "username": "mikael",
            "role": "ADMIN",
            "credential_fingerprint": "a" * 32,
        },
    }


def _user():
    return {
        "role": "USER",
        "session": {
            "username": "cliente",
            "role": "USER",
            "credential_fingerprint": "b" * 32,
        },
    }


def _current():
    checkpoint = default_checkpoint()
    return {
        "status": "CONFIRMED",
        "sha": "1" * 40,
        "checkpoint": checkpoint,
        "integrity": checkpoint_integrity_report(checkpoint),
    }


def _candidate():
    checkpoint = default_checkpoint()
    checkpoint["aion"]["priority"] = "recovery candidate"
    return {
        "status": "CONFIRMED",
        "revision": "2" * 40,
        "checkpoint": checkpoint,
        "integrity": checkpoint_integrity_report(checkpoint),
        "digest": checkpoint_source_digest(checkpoint),
    }


class RecoveryReviewTests(unittest.TestCase):
    def test_clean_admin_review_is_ready_but_never_authorized(self):
        result = build_recovery_review(
            _admin(),
            _current(),
            _candidate(),
            authenticated_admin=True,
        )
        self.assertEqual(result["state"], "READY_FOR_ADMIN_REVIEW")
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["checkpoint_execution_state"], "SUCCESS")
        self.assertEqual(result["checkpoint_integrity_state"], "CONFIRMED")
        self.assertEqual(result["traceability_security"], "SAFE_LOCAL")
        self.assertEqual(result["source_keys"], ["checkpoint_master"])
        self.assertTrue(result["trace_refs"])
        self.assertTrue(result["receipt_digest"].startswith("sha256:"))
        self.assertFalse(result["restore_authorized"])
        self.assertFalse(result["automatic_restore"])
        self.assertFalse(result["automatic_retry"])
        self.assertFalse(result["checkpoint_saved"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["network_called"])
        self.assertFalse(result["tool_output_is_authority"])

    def test_non_admin_is_blocked_and_does_not_restore(self):
        result = build_recovery_review(
            _user(),
            _current(),
            _candidate(),
            authenticated_admin=False,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("CHECKPOINT_INSPECTION_NOT_SUCCESSFUL", result["blockers"])
        self.assertFalse(result["restore_authorized"])
        self.assertFalse(result["external_action_executed"])

    def test_tampered_candidate_is_blocked(self):
        candidate = _candidate()
        candidate["digest"] = "sha256:" + ("0" * 64)
        result = build_recovery_review(
            _admin(),
            _current(),
            candidate,
            authenticated_admin=True,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("RECOVERY_PREFLIGHT_BLOCKED", result["blockers"])
        self.assertFalse(result["restore_authorized"])

    def test_same_content_candidate_is_blocked(self):
        current = _current()
        same = {
            "status": "CONFIRMED",
            "revision": "3" * 40,
            "checkpoint": deepcopy(current["checkpoint"]),
            "integrity": checkpoint_integrity_report(current["checkpoint"]),
            "digest": checkpoint_source_digest(current["checkpoint"]),
        }
        result = build_recovery_review(
            _admin(),
            current,
            same,
            authenticated_admin=True,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("RECOVERY_PREFLIGHT_BLOCKED", result["blockers"])


if __name__ == "__main__":
    unittest.main()
