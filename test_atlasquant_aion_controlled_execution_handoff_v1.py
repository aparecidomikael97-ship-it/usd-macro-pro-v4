import unittest

from atlasquant_aion_controlled_execution_handoff_v1 import (
    BLOCKED,
    READY,
    build_controlled_handoff,
    verify_executor_receipt,
)


def authority(**overrides):
    row = {
        "state": "VERIFIED",
        "owner_id": "owner",
        "tenant_id": "tenant",
        "workspace_id": "workspace",
        "allowed_capabilities": ["WRITE_CODE_SANDBOX"],
        "authority_ref": "auth:1",
        "authority_digest": "sha256:" + "e" * 64,
        "grants_root_authority": False,
        "tool_output_is_authority": False,
    }
    row.update(overrides)
    return row


def authority_verifier(row):
    return {
        "state": "VERIFIED",
        "owner_id": row.get("owner_id"),
        "tenant_id": row.get("tenant_id"),
        "workspace_id": row.get("workspace_id"),
        "allowed_capabilities": list(row.get("allowed_capabilities") or []),
        "authority_digest": row.get("authority_digest"),
        "cryptographically_verified": True,
        "verifier_ref": "trusted-authority-verifier-v1",
    }


def handoff(**overrides):
    kwargs = {
        "orchestration": {
            "state": "PLANNED",
            "external_action_executed": False,
            "execution_allowed": False,
            "external_ai_direct_tool_control": False,
        },
        "trusted_scope": {"owner_id": "owner", "tenant_id": "tenant", "workspace_id": "workspace"},
        "capability": "WRITE_CODE_SANDBOX",
        "execution_class": "SANDBOX_CODE",
        "executor_id": "aion-dev-sandbox-v1",
        "authority_evidence": authority(),
        "authority_verifier": authority_verifier,
        "evidence_refs": ["plan:1"],
        "expected_input_digest": "sha256:" + "a" * 64,
    }
    kwargs.update(overrides)
    return build_controlled_handoff(**kwargs)


class ControlledHandoffTests(unittest.TestCase):
    def test_ready_handoff_never_executes(self):
        out = handoff()
        self.assertEqual(out["state"], READY)
        self.assertTrue(out["authority_cryptographically_verified"])
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["automatic_merge"])
        self.assertFalse(out["automatic_deploy"])
        self.assertFalse(out["handoff_grants_authority"])

    def test_non_delegable_capability_is_blocked(self):
        out = handoff(capability="DEPLOY_PRODUCTION")
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("NON_DELEGABLE_CAPABILITY", out["blockers"])

    def test_missing_independent_verifier_is_blocked(self):
        out = handoff(authority_verifier=None)
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("INDEPENDENT_AUTHORITY_VERIFIER_REQUIRED", out["blockers"])

    def test_forged_verifier_binding_is_blocked(self):
        def bad_verifier(row):
            verdict = authority_verifier(row)
            verdict["workspace_id"] = "other"
            return verdict
        out = handoff(authority_verifier=bad_verifier)
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("AUTHORITY_VERIFIER_WORKSPACE_MISMATCH", out["blockers"])

    def test_external_ai_or_tool_output_cannot_be_authority(self):
        out = handoff(authority_evidence=authority(tool_output_is_authority=True))
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("TOOL_OUTPUT_AUTHORITY_FORBIDDEN", out["blockers"])

    def test_external_ai_direct_tool_control_is_blocked(self):
        out = handoff(orchestration={
            "state": "PLANNED",
            "external_action_executed": False,
            "execution_allowed": False,
            "external_ai_direct_tool_control": True,
        })
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("EXTERNAL_AI_DIRECT_TOOL_CONTROL_FORBIDDEN", out["blockers"])

    def test_scope_mismatch_blocks(self):
        out = handoff(authority_evidence=authority(workspace_id="other"))
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("AUTHORITY_WORKSPACE_MISMATCH", out["blockers"])

    def test_orchestration_cannot_self_authorize(self):
        out = handoff(orchestration={
            "state": "PLANNED",
            "external_action_executed": False,
            "execution_allowed": True,
        })
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("ORCHESTRATION_CANNOT_SELF_AUTHORIZE_EXECUTION", out["blockers"])

    def test_success_receipt_requires_tests_and_output_digest(self):
        h = handoff()
        receipt = {
            "handoff_digest": h["handoff_digest"],
            "executor_id": h["executor_id"],
            "input_digest": h["expected_input_digest"],
            "state": "CONFIRMED_SUCCESS",
            "attributed": True,
            "receipt_digest": "sha256:" + "b" * 64,
        }
        verified = verify_executor_receipt(h, receipt)
        self.assertEqual(verified["state"], "BLOCKED")
        self.assertIn("SUCCESS_OUTPUT_DIGEST_REQUIRED", verified["blockers"])
        self.assertIn("SUCCESS_TEST_VERIFICATION_REQUIRED", verified["blockers"])

    def test_exact_success_receipt_can_verify(self):
        h = handoff()
        receipt = {
            "handoff_digest": h["handoff_digest"],
            "executor_id": h["executor_id"],
            "input_digest": h["expected_input_digest"],
            "state": "CONFIRMED_SUCCESS",
            "attributed": True,
            "receipt_digest": "sha256:" + "b" * 64,
            "output_digest": "sha256:" + "c" * 64,
            "tests_verified": True,
            "test_receipts": ["test:1"],
        }
        verified = verify_executor_receipt(h, receipt)
        self.assertEqual(verified["state"], "VERIFIED")

    def test_unknown_outcome_is_valid_not_inferred_success_and_no_retry(self):
        h = handoff()
        receipt = {
            "handoff_digest": h["handoff_digest"],
            "executor_id": h["executor_id"],
            "input_digest": h["expected_input_digest"],
            "state": "OUTCOME_UNKNOWN",
            "attributed": True,
            "receipt_digest": "sha256:" + "d" * 64,
        }
        verified = verify_executor_receipt(h, receipt)
        self.assertEqual(verified["state"], "VERIFIED")
        self.assertEqual(verified["outcome"], "OUTCOME_UNKNOWN")
        self.assertFalse(verified["automatic_retry_allowed"])

    def test_receipt_lineage_mismatch_blocks(self):
        h = handoff()
        receipt = {
            "handoff_digest": h["handoff_digest"],
            "executor_id": h["executor_id"],
            "input_digest": "sha256:" + "c" * 64,
            "state": "OUTCOME_UNKNOWN",
            "attributed": True,
            "receipt_digest": "sha256:" + "d" * 64,
        }
        self.assertEqual(verify_executor_receipt(h, receipt)["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
