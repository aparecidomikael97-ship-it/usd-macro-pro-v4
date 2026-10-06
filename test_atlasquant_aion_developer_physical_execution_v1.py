import unittest

from atlasquant_aion_developer_physical_execution_v1 import (
    BLOCKED,
    READY,
    REQUIRED_PROOFS,
    evaluate_physical_executor_readiness,
    expected_executor_receipt_template,
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
        "proofs": proofs,
    }
    row.update(overrides)
    return row


class PhysicalExecutionV1Tests(unittest.TestCase):
    def test_missing_physical_proofs_fail_closed(self):
        out = evaluate_physical_executor_readiness(
            handoff=handoff(),
            physical_evidence={"platform": "WINDOWS", "independent": True},
            environment={},
            allowed_files=["module.py"],
            current_input_digest=handoff()["expected_input_digest"],
        )
        self.assertEqual(out["state"], BLOCKED)
        self.assertTrue(any(x.endswith("_REQUIRED") for x in out["blockers"]))
        self.assertFalse(out["executes_action"])

    def test_all_bound_proofs_make_only_readiness_ready(self):
        out = evaluate_physical_executor_readiness(
            handoff=handoff(),
            physical_evidence=physical_evidence(),
            environment={"PYTHONHASHSEED": "0"},
            allowed_files=["module.py", "test_module.py"],
            current_input_digest=handoff()["expected_input_digest"],
        )
        self.assertEqual(out["state"], READY)
        self.assertFalse(out["commands_executed"])
        self.assertFalse(out["writes_repository"])
        self.assertTrue(out["protected_core_read_only"])
        self.assertTrue(out["production_runtime_read_only"])

    def test_wrong_input_digest_blocks(self):
        out = evaluate_physical_executor_readiness(
            handoff=handoff(),
            physical_evidence=physical_evidence(),
            environment={},
            allowed_files=["module.py"],
            current_input_digest="sha256:" + "9" * 64,
        )
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("INPUT_DIGEST_MISMATCH", out["blockers"])

    def test_secret_environment_is_rejected(self):
        out = evaluate_physical_executor_readiness(
            handoff=handoff(),
            physical_evidence=physical_evidence(),
            environment={"GITHUB_TOKEN": "x"},
            allowed_files=["module.py"],
            current_input_digest=handoff()["expected_input_digest"],
        )
        self.assertEqual(out["state"], BLOCKED)
        self.assertTrue(any(x.startswith("SECRET_ENVIRONMENT_KEY_FORBIDDEN") for x in out["blockers"]))

    def test_path_escape_is_rejected(self):
        out = evaluate_physical_executor_readiness(
            handoff=handoff(),
            physical_evidence=physical_evidence(),
            environment={},
            allowed_files=["../outside.py"],
            current_input_digest=handoff()["expected_input_digest"],
        )
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("UNSAFE_ALLOWED_FILE", out["blockers"])

    def test_receipt_template_starts_unknown_not_success(self):
        ready = evaluate_physical_executor_readiness(
            handoff=handoff(),
            physical_evidence=physical_evidence(),
            environment={},
            allowed_files=["module.py"],
            current_input_digest=handoff()["expected_input_digest"],
        )
        receipt = expected_executor_receipt_template(ready)
        self.assertEqual(receipt["state"], "OUTCOME_UNKNOWN")
        self.assertFalse(receipt["attributed"])
        self.assertFalse(receipt["automatic_merge"])
        self.assertFalse(receipt["automatic_deploy"])


if __name__ == "__main__":
    unittest.main()
