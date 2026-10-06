import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_developer_physical_execution_v1 import (
    BLOCKED, READY, evaluate_physical_executor_readiness,
    expected_executor_receipt_template,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_physical_evidence_attestation_v1 import (
    REQUIRED_PROOFS, SCHEMA as ATTESTATION_SCHEMA, canonical_attestation_bytes,
    physical_evidence_digest, verify_physical_evidence_attestation,
)
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-06T22:30:00Z"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


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


def evidence():
    h = handoff()
    return {
        "platform": "WINDOWS",
        "handoff_digest": h["handoff_digest"],
        "input_digest": h["expected_input_digest"],
        "probe_principal_id": "windows-probe-1",
        "probe_session_id": "session-1",
        "proofs": {
            name: {
                "verified": True,
                "evidence_ref": "probe:" + name.lower(),
                "evidence_digest": "sha256:" + "3" * 64,
                "measured_by": "windows-probe-v1",
            }
            for name in REQUIRED_PROOFS
        },
    }


class PhysicalExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )
        self.roots = TrustRootRegistry.from_mapping({
            "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
            "roots": [{
                "key_id": "probe-root", "key_version": 1, "algorithm": "Ed25519",
                "public_key_b64": b64url(public), "status": "ACTIVE",
                "not_before": "2026-10-01T00:00:00Z",
                "not_after": "2027-10-01T00:00:00Z",
            }],
            "revoked_key_ids": [],
        })
        self.nonces = PersistentNonceRegistry(Path(self.tmp.name) / "physical.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def trusted(self, e):
        payload = {
            "schema": ATTESTATION_SCHEMA,
            "attestation_id": "physical-attestation-1",
            "probe_principal_id": e["probe_principal_id"],
            "probe_session_id": e["probe_session_id"],
            "platform": "WINDOWS",
            "handoff_digest": e["handoff_digest"],
            "input_digest": e["input_digest"],
            "physical_evidence_digest": physical_evidence_digest(e),
            "verified_proofs": sorted(REQUIRED_PROOFS),
            "issued_at": "2026-10-06T22:25:00Z",
            "expires_at": "2026-10-06T22:50:00Z",
            "nonce": "physical-nonce-1",
            "key_id": "probe-root",
            "key_version": 1,
        }
        sig = b64url(self.private.sign(canonical_attestation_bytes(payload)))
        return verify_physical_evidence_attestation(
            payload, signature_b64=sig, trust_roots=self.roots,
            nonce_registry=self.nonces, now_ts=NOW,
            expected_handoff_digest=e["handoff_digest"],
            expected_input_digest=e["input_digest"],
            expected_physical_evidence_digest=physical_evidence_digest(e),
        )

    def evaluate(self, **overrides):
        e = overrides.pop("physical_evidence", evidence())
        trusted = overrides.pop("trusted_attestation", self.trusted(e))
        kwargs = {
            "handoff": handoff(),
            "physical_evidence": e,
            "trusted_attestation": trusted,
            "environment": {},
            "allowed_files": ["module.py", "test_module.py"],
            "current_input_digest": handoff()["expected_input_digest"],
        }
        kwargs.update(overrides)
        return evaluate_physical_executor_readiness(**kwargs)

    def test_signed_attestation_can_make_only_readiness_ready(self):
        out = self.evaluate()
        self.assertEqual(out["state"], READY)
        self.assertFalse(out["commands_executed"])
        self.assertFalse(out["writes_repository"])
        self.assertTrue(out["protected_core_read_only"])
        self.assertTrue(out["production_runtime_read_only"])

    def test_plain_verified_flags_without_attestation_are_blocked(self):
        out = evaluate_physical_executor_readiness(
            handoff=handoff(), physical_evidence=evidence(), trusted_attestation={},
            environment={}, allowed_files=["module.py"],
            current_input_digest=handoff()["expected_input_digest"],
        )
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("TRUSTED_PHYSICAL_ATTESTATION_NOT_VERIFIED", out["blockers"])

    def test_evidence_mutation_after_attestation_is_blocked(self):
        e = evidence()
        trusted = self.trusted(e)
        e["proofs"]["NETWORK_ISOLATION_VERIFIED"]["evidence_digest"] = "sha256:" + "9" * 64
        out = evaluate_physical_executor_readiness(
            handoff=handoff(), physical_evidence=e, trusted_attestation=trusted,
            environment={}, allowed_files=["module.py"],
            current_input_digest=handoff()["expected_input_digest"],
        )
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("PHYSICAL_ATTESTATION_EVIDENCE_MISMATCH", out["blockers"])

    def test_secret_environment_is_blocked(self):
        out = self.evaluate(environment={"GITHUB_TOKEN": "x"})
        self.assertEqual(out["state"], BLOCKED)

    def test_path_escape_is_blocked(self):
        out = self.evaluate(allowed_files=["../outside.py"])
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("UNSAFE_ALLOWED_FILE", out["blockers"])

    def test_receipt_template_starts_unknown_and_no_retry(self):
        ready = self.evaluate()
        receipt = expected_executor_receipt_template(ready)
        self.assertEqual(receipt["state"], "OUTCOME_UNKNOWN")
        self.assertFalse(receipt["automatic_retry_allowed"])
        self.assertFalse(receipt["automatic_merge"])
        self.assertFalse(receipt["automatic_deploy"])


if __name__ == "__main__":
    unittest.main()
