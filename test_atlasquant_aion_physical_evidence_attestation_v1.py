import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_physical_evidence_attestation_v1 import (
    REQUIRED_PROOFS, SCHEMA, canonical_attestation_bytes,
    physical_evidence_digest, verify_physical_evidence_attestation,
)
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-06T22:30:00Z"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def keypair():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    return private, b64url(public)


def roots(public_key: str):
    return TrustRootRegistry.from_mapping({
        "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
        "roots": [{
            "key_id": "probe-root", "key_version": 1, "algorithm": "Ed25519",
            "public_key_b64": public_key, "status": "ACTIVE",
            "not_before": "2026-10-01T00:00:00Z",
            "not_after": "2027-10-01T00:00:00Z",
        }],
        "revoked_key_ids": [],
    })


def evidence():
    return {
        "platform": "WINDOWS",
        "handoff_digest": "sha256:" + "1" * 64,
        "input_digest": "sha256:" + "2" * 64,
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


def statement(e, nonce="physical-nonce-1"):
    return {
        "schema": SCHEMA,
        "attestation_id": "physical-attestation-1",
        "probe_principal_id": e["probe_principal_id"],
        "probe_session_id": e["probe_session_id"],
        "platform": "WINDOWS",
        "handoff_digest": e["handoff_digest"],
        "input_digest": e["input_digest"],
        "physical_evidence_digest": physical_evidence_digest(e),
        "verified_proofs": sorted(REQUIRED_PROOFS),
        "issued_at": "2026-10-06T22:29:00Z",
        "expires_at": "2026-10-06T22:32:00Z",
        "nonce": nonce,
        "key_id": "probe-root",
        "key_version": 1,
    }


def sign(private, payload):
    return b64url(private.sign(canonical_attestation_bytes(payload)))


class PhysicalAttestationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.private, public = keypair()
        self.roots = roots(public)
        self.nonces = PersistentNonceRegistry(Path(self.tmp.name) / "physical.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self, payload, signature):
        return verify_physical_evidence_attestation(
            payload, signature_b64=signature, trust_roots=self.roots,
            nonce_registry=self.nonces, now_ts=NOW,
            expected_handoff_digest=payload["handoff_digest"],
            expected_input_digest=payload["input_digest"],
            expected_physical_evidence_digest=payload["physical_evidence_digest"],
        )

    def test_valid_attestation_is_verified_but_non_executing(self):
        e = evidence()
        payload = statement(e)
        result = self.verify(payload, sign(self.private, payload))
        self.assertEqual(result["state"], "VERIFIED")
        self.assertTrue(result["signature_verified"])
        self.assertTrue(result["nonce_registered"])
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["executes_action"])
        self.assertFalse(result["private_key_used"])

    def test_tampered_evidence_digest_fails_signature(self):
        e = evidence()
        payload = statement(e)
        signature = sign(self.private, payload)
        payload = dict(payload)
        payload["physical_evidence_digest"] = "sha256:" + "9" * 64
        result = self.verify(payload, signature)
        self.assertEqual(result["state"], "BLOCKED")

    def test_replay_is_blocked(self):
        e = evidence()
        payload = statement(e)
        signature = sign(self.private, payload)
        self.assertEqual(self.verify(payload, signature)["state"], "VERIFIED")
        second = self.verify(payload, signature)
        self.assertEqual(second["state"], "BLOCKED")
        self.assertIn("PHYSICAL_ATTESTATION_NONCE_REPLAYED", second["blockers"])

    def test_malformed_non_string_proof_fails_closed_not_exception(self):
        e = evidence()
        payload = statement(e)
        payload["verified_proofs"] = [{"fake": True}]
        signature = sign(self.private, payload)
        result = self.verify(payload, signature)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("PHYSICAL_ATTESTATION_PROOF_SET_INVALID", result["blockers"])

    def test_oversized_time_window_is_blocked(self):
        e = evidence()
        payload = statement(e)
        payload["issued_at"] = "2026-10-06T22:20:00Z"
        payload["expires_at"] = "2026-10-06T22:40:00Z"
        signature = sign(self.private, payload)
        result = self.verify(payload, signature)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("PHYSICAL_ATTESTATION_WINDOW_TOO_LARGE", result["blockers"])

    def test_incomplete_proof_set_is_blocked(self):
        e = evidence()
        payload = statement(e)
        payload["verified_proofs"] = sorted(REQUIRED_PROOFS[:-1])
        signature = sign(self.private, payload)
        result = self.verify(payload, signature)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("PHYSICAL_ATTESTATION_PROOF_SET_INVALID", result["blockers"])


if __name__ == "__main__":
    unittest.main()
