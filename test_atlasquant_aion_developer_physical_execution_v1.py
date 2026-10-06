import unittest

from atlasquant_aion_developer_physical_execution_v1 import (
    BLOCKED,
    READY,
    REQUIRED_PROOFS,
    evaluate_physical_executor_readiness,
    expected_executor_receipt_template,
    physical_evidence_digest,
)


def handoff():
    return {
        "state": "READY_FOR_CAPABILITY_EXECUTOR",
        "execution_class": "SANDBOX_CODE",
        "handoff_digest": "sha256:" + "1" * 64,
        "expected_input_digest": "sha256:" + "2" * 64,
        "automatic_merge": False,
        "automatic_deploy": False,
        "handoff_grants_authority": False,
    }


def physical_evidence(**overrides):
    proofs = {
        name: {
            "verified": True,
            "evidence_ref": "probe:" + name.lower(),
            "evidence_digest": "sha256:" + "3" * 64,
            "measured_by": "windows-probe-v1",
        }
        for name in REQUIRED_PROOFS
    }
    row = {
        "platform": "WINDOWS",
        "independent": True,
        "handoff_digest": handoff()["handoff_digest"],
        "input_digest": handoff()["expected_input_digest"],
        "probe_principal_id": "probe-principal-1",
        "probe_session_id": "probe-session-1",
        "proofs": proofs,
    }
    row.update(overrides)
    row["physical_evidence_digest"] = physical_evidence_digest(row)
    return row


def evidence_verifier(row):
    return {
        "state": "VERIFIED",
        "handoff_digest": row.get("handoff_digest"),
        "input_digest": row.get("input_digest"),
        "physical_evidence_digest": row.get("physical_evidence_digest"),
        "verified_proofs": list(REQUIRED_PROOFS),
        "cryptographically_verified": True,
        "independent": True,
        "verifier_ref": "physical-evidence-verifier-v1",
    }


def evaluate(**overrides):
    kwargs = {
        "handoff": handoff(),
        "physical_evidence": physical_evidence(),
        "evidence_verifier": evidence_verifier,
        "environment": {},
        "allowed_files": ["module.py", "test_module.py"],
        "current_input_digest": handoff()["expected_input_digest"],
    }
    kwargs.update(overrides)
    return evaluate_physical_executor_readiness(**kwargs)


class PhysicalExecutionV1Tests(unittest.TestCase):
    def test_missing_physical_proofs_fail_closed(self):
        evidence = physical_evidence()
        evidence["proofs"] = {}
        evidence["physical_evidence_digest"] = physical_evidence_digest(evidence)
        out = evaluate(physical_evidence=evidence)
        self.assertEqual(out["state"], BLOCKED)
        self.assertTrue(any(x.endswith("_REQUIRED") for x in out["blockers"]))
        self.assertFalse(out["executes_action"])

    def test_caller_flags_without_independent_verifier_are_blocked(self):
        out = evaluate(evidence_verifier=None)
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("INDEPENDENT_PHYSICAL_EVIDENCE_VERIFIER_REQUIRED", out["blockers"])

    def test_forged_evidence_digest_is_blocked(self):
        evidence = physical_evidence()
        evidence["physical_evidence_digest"] = "sha256:" + "9" * 64
        out = evaluate(physical_evidence=evidence)
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("PHYSICAL_EVIDENCE_DIGEST_MISMATCH", out["blockers"])

    def test_verifier_must_bind_exact_handoff(self):
        def bad_verifier(row):
            verdict = evidence_verifier(row)
            verdict["handoff_digest"] = "sha256:" + "8" * 64
            return verdict
        out = evaluate(evidence_verifier=bad_verifier)
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("PHYSICAL_VERIFIER_HANDOFF_MISMATCH", out["blockers"])

    def test_verifier_must_bind_every_required_proof(self):
        def incomplete_verifier(row):
            verdict = evidence_verifier(row)
            verdict["verified_proofs"] = list(REQUIRED_PROOFS[:-1])
            return verdict
        out = evaluate(evidence_verifier=incomplete_verifier)
        self.assertEqual(out["state"], BLOCKED)
        self.assertTrue(any(x.endswith("_NOT_BOUND_BY_VERIFIER") for x in out["blockers"]))

    def test_all_bound_proofs_make_only_readiness_ready(self):
        out = evaluate(environment={"PYTHONHASHSEED": "0"})
        self.assertEqual(out["state"], READY)
        self.assertTrue(out["physical_evidence_cryptographically_verified"])
        self.assertFalse(out["commands_executed"])
        self.assertFalse(out["writes_repository"])
        self.assertTrue(out["protected_core_read_only"])
        self.assertTrue(out["production_runtime_read_only"])

    def test_wrong_input_digest_blocks(self):
        out = evaluate(current_input_digest="sha256:" + "9" * 64)
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("INPUT_DIGEST_MISMATCH", out["blockers"])

    def test_secret_environment_is_rejected(self):
        out = evaluate(environment={"GITHUB_TOKEN": "x"})
        self.assertEqual(out["state"], BLOCKED)
        self.assertTrue(any(x.startswith("SECRET_ENVIRONMENT_KEY_FORBIDDEN") for x in out["blockers"]))

    def test_pythonpath_override_is_rejected(self):
        out = evaluate(environment={"PYTHONPATH": "evil"})
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("PYTHONPATH_OVERRIDE_FORBIDDEN", out["blockers"])

    def test_path_escape_is_rejected(self):
        out = evaluate(allowed_files=["../outside.py"])
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("UNSAFE_ALLOWED_FILE", out["blockers"])

    def test_receipt_template_starts_unknown_not_success_and_no_retry(self):
        ready = evaluate()
        receipt = expected_executor_receipt_template(ready)
        self.assertEqual(receipt["state"], "OUTCOME_UNKNOWN")
        self.assertFalse(receipt["attributed"])
        self.assertFalse(receipt["automatic_retry_allowed"])
        self.assertFalse(receipt["automatic_merge"])
        self.assertFalse(receipt["automatic_deploy"])


if __name__ == "__main__":
    unittest.main()
