import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_authority_verifier import SCHEMA as AUTHORITY_SCHEMA, canonical_statement_bytes
from atlasquant_aion_controlled_execution_handoff_v1 import (
    BLOCKED, READY, build_controlled_handoff, verify_executor_receipt,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-06T22:30:00Z"
ISSUED = "2026-10-06T22:25:00Z"
EXPIRES = "2026-10-06T22:50:00Z"
SCOPE = {
    "subject_id": "aion-developer",
    "tenant_id": "atlasquant-owner",
    "domain": "DEVELOPER",
    "policy_id": "AION_OPERATIONAL_READINESS_V1",
}


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
            "key_id": "authority-root",
            "key_version": 1,
            "algorithm": "Ed25519",
            "public_key_b64": public_key,
            "status": "ACTIVE",
            "not_before": "2026-10-01T00:00:00Z",
            "not_after": "2027-10-01T00:00:00Z",
        }],
        "revoked_key_ids": [],
    })


def statement(nonce="auth-nonce-1", capabilities=None):
    return {
        "schema": AUTHORITY_SCHEMA,
        "statement_id": "stmt-op-readiness-1",
        "authority_id": "owner-control-plane",
        **SCOPE,
        "capabilities": capabilities or ["WRITE_CODE_SANDBOX"],
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "nonce": nonce,
        "key_id": "authority-root",
        "key_version": 1,
        "grant_kind": "CAPABILITY_GRANT",
    }


def sign(private, payload):
    return b64url(private.sign(canonical_statement_bytes(payload)))


class ControlledHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.private, public = keypair()
        self.trust_roots = roots(public)
        self.nonces = PersistentNonceRegistry(Path(self.tmp.name) / "authority.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, **overrides):
        payload = overrides.pop("authority_statement", statement())
        kwargs = {
            "orchestration": {
                "state": "PLANNED",
                "external_action_executed": False,
                "execution_allowed": False,
                "external_ai_direct_tool_control": False,
            },
            "trusted_scope": dict(SCOPE),
            "capability": "WRITE_CODE_SANDBOX",
            "execution_class": "SANDBOX_CODE",
            "executor_id": "aion-dev-sandbox-v1",
            "authority_statement": payload,
            "authority_signature_b64": sign(self.private, payload),
            "trust_roots": self.trust_roots,
            "nonce_registry": self.nonces,
            "now_ts": NOW,
            "evidence_refs": ["plan:1"],
            "expected_input_digest": "sha256:" + "a" * 64,
        }
        kwargs.update(overrides)
        return build_controlled_handoff(**kwargs)

    def test_valid_signed_authority_creates_non_executing_handoff(self):
        out = self.make()
        self.assertEqual(out["state"], READY)
        self.assertTrue(out["authority_nonce_registered"])
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["automatic_merge"])
        self.assertFalse(out["automatic_deploy"])

    def test_replay_of_same_authority_nonce_is_blocked(self):
        payload = statement()
        signature = sign(self.private, payload)
        common = dict(
            orchestration={"state": "PLANNED", "external_action_executed": False, "execution_allowed": False},
            trusted_scope=dict(SCOPE), capability="WRITE_CODE_SANDBOX",
            execution_class="SANDBOX_CODE", executor_id="aion-dev-sandbox-v1",
            authority_statement=payload, authority_signature_b64=signature,
            trust_roots=self.trust_roots, nonce_registry=self.nonces, now_ts=NOW,
            evidence_refs=["plan:1"], expected_input_digest="sha256:" + "a" * 64,
        )
        self.assertEqual(build_controlled_handoff(**common)["state"], READY)
        second = build_controlled_handoff(**common)
        self.assertEqual(second["state"], BLOCKED)
        self.assertTrue(any("TRUSTED_AUTHORITY" in x or "AUTHORITY" in x for x in second["blockers"]))

    def test_tampered_capability_fails_signature(self):
        payload = statement()
        signature = sign(self.private, payload)
        payload = dict(payload)
        payload["capabilities"] = ["DEPLOY_PRODUCTION"]
        out = self.make(authority_statement=payload, authority_signature_b64=signature, capability="DEPLOY_PRODUCTION")
        self.assertEqual(out["state"], BLOCKED)

    def test_non_delegable_capability_is_blocked_without_burning_nonce(self):
        payload = statement(capabilities=["DEPLOY_PRODUCTION"])
        out = self.make(
            authority_statement=payload,
            authority_signature_b64=sign(self.private, payload),
            capability="DEPLOY_PRODUCTION",
        )
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("NON_DELEGABLE_CAPABILITY", out["blockers"])
        self.assertEqual(self.nonces.count(), 0)

    def test_external_ai_direct_tool_control_is_blocked(self):
        out = self.make(orchestration={
            "state": "PLANNED", "external_action_executed": False,
            "execution_allowed": False, "external_ai_direct_tool_control": True,
        })
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("EXTERNAL_AI_DIRECT_TOOL_CONTROL_FORBIDDEN", out["blockers"])
        self.assertEqual(self.nonces.count(), 0)

    def test_wrong_capability_does_not_burn_signed_authority_nonce(self):
        payload = statement(capabilities=["LOCAL_READ"])
        out = self.make(
            authority_statement=payload,
            authority_signature_b64=sign(self.private, payload),
            capability="WRITE_CODE_SANDBOX",
        )
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("CAPABILITY_NOT_REQUESTED_IN_AUTHORITY_STATEMENT", out["blockers"])
        self.assertEqual(self.nonces.count(), 0)

    def test_invalid_input_digest_does_not_burn_nonce(self):
        out = self.make(expected_input_digest="sha256:not-a-real-digest")
        self.assertEqual(out["state"], BLOCKED)
        self.assertEqual(self.nonces.count(), 0)

    def test_success_receipt_requires_output_and_tests(self):
        h = self.make()
        receipt = {
            "handoff_digest": h["handoff_digest"], "executor_id": h["executor_id"],
            "input_digest": h["expected_input_digest"], "state": "CONFIRMED_SUCCESS",
            "attributed": True, "receipt_digest": "sha256:" + "b" * 64,
        }
        result = verify_executor_receipt(h, receipt)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("SUCCESS_OUTPUT_DIGEST_REQUIRED", result["blockers"])
        self.assertIn("SUCCESS_TEST_VERIFICATION_REQUIRED", result["blockers"])

    def test_unknown_outcome_never_becomes_success_or_retry(self):
        h = self.make()
        receipt = {
            "handoff_digest": h["handoff_digest"], "executor_id": h["executor_id"],
            "input_digest": h["expected_input_digest"], "state": "OUTCOME_UNKNOWN",
            "attributed": True, "receipt_digest": "sha256:" + "d" * 64,
        }
        result = verify_executor_receipt(h, receipt)
        self.assertEqual(result["state"], "VERIFIED")
        self.assertEqual(result["outcome"], "OUTCOME_UNKNOWN")
        self.assertFalse(result["automatic_retry_allowed"])


if __name__ == "__main__":
    unittest.main()
