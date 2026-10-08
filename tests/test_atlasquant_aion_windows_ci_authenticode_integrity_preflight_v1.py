"""CI Windows genuine Authenticode and negative-tamper evidence tests.

Positive signature proves only the CI OS executable, NOT AION publisher.
The edited scratch binary is NEVER launched.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from atlasquant_aion_windows_ci_authenticode_integrity_preflight_v1 import (
    SCHEMA, READY, RELEASE_READY, RELEASE_FIELDS, BLOCKED, KEYS, RECORD,
    evaluate_ci_authenticode_fixture, build_future_aion_release_signer_pin_plan,
    ci_authenticode_policy,
)

D = lambda c: "sha256:" + c * 64

class WindowsCIAuthenticodeIntegrityV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("RUNNER_OS") != "Windows"
            or os.environ.get("GITHUB_EVENT_NAME") != "pull_request"
            or os.environ.get("AION_CI_AUTHENTICODE_FIXTURE") != "1"):
            raise RuntimeError("CI_WINDOWS_SIGNER_FIXTURE_REQUIRED")
        file = Path(os.environ["AION_AUTHENTICODE_FIXTURE_FILE"])
        temp = Path(os.environ["RUNNER_TEMP"]).resolve()
        if not file.is_file() or not file.resolve().is_relative_to(temp):
            raise RuntimeError("SIGNER_FIXTURE_OUTSIDE_CI_TEMP")
        cls.fixture = json.loads(file.read_text(encoding="utf-8"))
        cls.challenge = D("a")
        cls.policy = D("b")
        cls.source = D("c")

    def evaluate(self, evidence=None, **kw):
        return evaluate_ci_authenticode_fixture(
            self.fixture if evidence is None else evidence,
            expected_challenge_digest=kw.get("challenge", self.challenge),
            expected_policy_digest=kw.get("policy", self.policy),
            expected_verifier_source_digest=kw.get("source", self.source),
        )

    def edited(self, **changes):
        x = deepcopy(self.fixture)
        x.update(changes)
        return x

    def signed_record(self, **changes):
        x = deepcopy(self.fixture)
        x["baseline"].update(changes)
        return x

    def tampered_record(self, **changes):
        x = deepcopy(self.fixture)
        x["tampered"].update(changes)
        return x

    def test_native_windows_ci_signature_is_valid_for_os_binary(self):
        f = self.fixture
        self.assertEqual(f["schema"], SCHEMA)
        self.assertEqual(f["ci_scope"], "EPHEMERAL_WINDOWS_GITHUB_PR_RUNNER")
        self.assertEqual(f["baseline"]["signature_status"], "Valid")
        self.assertTrue(f["baseline"]["signer_cert_present"])
        self.assertTrue(f["baseline"]["pe_magic_mz"])
        self.assertGreaterEqual(f["baseline"]["byte_count"], 512)

    def test_ci_tampered_copy_is_not_signed_valid(self):
        f = self.fixture
        self.assertNotEqual(f["tampered"]["signature_status"], "Valid")
        self.assertNotEqual(f["tampered"]["binary_sha256"], f["baseline"]["binary_sha256"])
        self.assertEqual(f["tampered"]["byte_count"], f["baseline"]["byte_count"])
        self.assertFalse(f["tampered_copy_executed"])

    def test_ci_observation_passes_but_is_never_aion_attestation(self):
        result = self.evaluate()
        self.assertEqual(result["state"], READY, result)
        self.assertTrue(result["ci_tampered_copy_rejected_shape_only"])
        self.assertFalse(result["real_aion_binary_checked"])
        self.assertFalse(result["real_aion_publisher_verified"])
        self.assertFalse(result["release_signature_authoritatively_pinned"])
        self.assertFalse(result["trusted_independent_attestor_used"])
        self.assertFalse(result["install_ready"])

    def test_no_raw_path_or_signer_subject_in_observation(self):
        f = self.fixture
        self.assertEqual(set(f), set(KEYS))
        self.assertEqual(set(f["baseline"]), set(RECORD))
        self.assertEqual(set(f["tampered"]), set(RECORD))
        forbidden = ("file_path", "filename", "signer_subject", "subject_name",
                     "windows_user", "username", "owner_sid", "raw_certificate",
                     "thumbprint_sha1", "registry_value", "private_key")
        for key in forbidden:
            self.assertNotIn(key, f)
            self.assertNotIn(key, f["baseline"])
            self.assertNotIn(key, f["tampered"])

    def test_missing_or_extra_fixture_field_blocks(self):
        x = deepcopy(self.fixture)
        del x["owner_device_accessed"]
        self.assertIn("EXACT_CI_ENVELOPE_KEYS_REQUIRED", self.evaluate(x)["blockers"])
        y = self.edited(raw_path=r"C:\Windows\example.exe")
        self.assertEqual(self.evaluate(y)["state"], BLOCKED)

    def test_raw_signer_certificate_injected_into_row_blocks(self):
        x = self.signed_record(cert_raw="untrusted bytes")
        self.assertEqual(self.evaluate(x)["state"], BLOCKED)

    def test_challenge_replay_blocks(self):
        self.assertEqual(self.evaluate(challenge=D("f"))["state"], BLOCKED)

    def test_fixture_challenge_tamper_blocks(self):
        self.assertEqual(self.evaluate(self.edited(challenge_digest=D("e")))["state"], BLOCKED)

    def test_wrong_expected_publisher_policy_blocks(self):
        self.assertEqual(self.evaluate(policy=D("f"))["state"], BLOCKED)

    def test_wrong_verifier_source_blocks(self):
        self.assertEqual(self.evaluate(source=D("f"))["state"], BLOCKED)

    def test_invalid_sha_policy_blocks(self):
        self.assertEqual(self.evaluate(policy="f"*64)["state"], BLOCKED)

    def test_ci_scope_escalation_to_owner_pc_blocks(self):
        self.assertEqual(self.evaluate(self.edited(ci_scope="HUMAN_OWNER_WINDOWS_PC"))["state"], BLOCKED)

    def test_artifact_role_escalation_to_aion_blocks(self):
        self.assertEqual(self.evaluate(self.edited(artifact_role="AION_RELEASE"))["state"], BLOCKED)

    def test_claim_that_ci_signature_is_aion_release_blocks(self):
        for key in ("aion_binary_examined", "aion_release_signer_verified",
                    "owner_device_accessed", "signed_artifact_installed"):
            self.assertEqual(self.evaluate(self.edited(**{key: True}))["state"], BLOCKED, key)

    def test_tampered_copy_execution_claim_blocks(self):
        self.assertEqual(self.evaluate(self.edited(tampered_copy_executed=True))["state"], BLOCKED)

    def test_tamper_operation_mismatch_blocks(self):
        self.assertEqual(self.evaluate(self.edited(tamper_operation="ACTUALLY_EXECUTED"))["state"], BLOCKED)

    def test_unsigned_baseline_blocks(self):
        self.assertEqual(self.evaluate(self.signed_record(signature_status="NotSigned"))["state"], BLOCKED)

    def test_expired_or_untrusted_baseline_blocks(self):
        for status in ("NotTrusted", "UnknownError", "HashMismatch", "NotTimeValid"):
            self.assertEqual(self.evaluate(self.signed_record(signature_status=status))["state"], BLOCKED)

    def test_valid_tampered_binary_is_not_accepted(self):
        self.assertEqual(self.evaluate(self.tampered_record(signature_status="Valid"))["state"], BLOCKED)

    def test_identical_baseline_and_modified_hash_blocks(self):
        self.assertEqual(self.evaluate(self.tampered_record(
            binary_sha256=self.fixture["baseline"]["binary_sha256"]
        ))["state"], BLOCKED)

    def test_modified_copy_size_change_blocks(self):
        self.assertEqual(self.evaluate(self.tampered_record(
            byte_count=self.fixture["baseline"]["byte_count"] + 1
        ))["state"], BLOCKED)

    def test_modified_copy_invalid_pe_header_blocks(self):
        self.assertEqual(self.evaluate(self.tampered_record(pe_magic_mz=False))["state"], BLOCKED)

    def test_missing_baseline_signer_cert_blocks(self):
        self.assertEqual(self.evaluate(self.signed_record(
            signer_cert_sha256="", signer_cert_present=False
        ))["state"], BLOCKED)

    def test_wrong_baseline_cert_hash_format_blocks(self):
        self.assertEqual(self.evaluate(self.signed_record(signer_cert_sha256=D("Z")))["state"], BLOCKED)

    def test_conflicting_cert_presence_fingerprint_blocks(self):
        self.assertEqual(self.evaluate(self.tampered_record(
            signer_cert_present=False, signer_cert_sha256=D("a")
        ))["state"], BLOCKED)

    def test_no_negative_signer_status_blocks(self):
        self.assertEqual(self.evaluate(self.tampered_record(signature_status=""))["state"], BLOCKED)

    def test_future_aion_signer_pin_plan_is_only_shape(self):
        data = {
            "installation_id": "aion-ci-design-install-001",
            "expected_aion_binary_sha256": D("1"),
            "pinned_aion_signer_certificate_sha256": D("2"),
            "trusted_publisher_policy_digest": D("3"),
            "release_manifest_digest": D("4"),
            "owner_device_binding_digest": D("5"),
            "owner_challenge_digest": D("6"),
            "canonical_path_policy_digest": D("7"),
            "revocation_policy_digest": D("8"),
            "verifier_binary_manifest_digest": D("9"),
        }
        self.assertEqual(set(data), set(RELEASE_FIELDS))
        self.release_fields = data
        p = build_future_aion_release_signer_pin_plan(**data)
        self.assertEqual(p["state"], RELEASE_READY, p)
        for k in ("publisher_pin_independently_attested", "pin_source_provenance_trusted",
                  "revocation_checked_with_trusted_policy", "owner_identity_attested",
                  "aion_binary_measured", "aion_signature_verified",
                  "signed_release_authorized_to_install", "owner_authorization_consumed"):
            self.assertFalse(p[k], k)

    def test_missing_required_publisher_pin_blocks(self):
        f = {k: D("a") for k in RELEASE_FIELDS}
        f["installation_id"] = "aion-design-install-002"
        f["pinned_aion_signer_certificate_sha256"] = ""
        self.assertEqual(build_future_aion_release_signer_pin_plan(**f)["state"], BLOCKED)

    def test_release_pin_same_as_binary_hash_blocks(self):
        f = {k: D("a") for k in RELEASE_FIELDS}
        f["installation_id"] = "aion-design-install-002"
        self.assertEqual(build_future_aion_release_signer_pin_plan(**f)["state"], BLOCKED)

    def test_extra_release_pin_field_blocks(self):
        f = {k: D("a") for k in RELEASE_FIELDS}
        f["installation_id"] = "aion-design-install-002"
        f["pinned_aion_signer_certificate_sha256"] = D("b")
        f["owner_approval_implicitly_granted"] = True
        self.assertEqual(build_future_aion_release_signer_pin_plan(**f)["state"], BLOCKED)

    def test_policy_permanently_denies_aion_install_inference(self):
        p = ci_authenticode_policy()
        self.assertTrue(p["ci_only"])
        for key, val in p.items():
            if val is False:
                self.assertIs(val, False, key)
        self.assertFalse(p["ci_signer_is_aion_publisher"])
        self.assertFalse(p["physical_aion_signature_verified"])
        self.assertFalse(p["owner_device_accessed"])
        self.assertFalse(p["worker_activated"])
        self.assertFalse(p["deploy_executed"])

if __name__ == "__main__":
    unittest.main()
