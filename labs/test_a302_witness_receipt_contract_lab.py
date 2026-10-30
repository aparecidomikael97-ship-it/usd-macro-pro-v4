"""A302 LAB-only cryptographic negative tests; green is never GO."""
import copy
import unittest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from labs.a302_witness_receipt_contract_lab import (
    SCHEMA, MANIFEST_SCHEMA, GENESIS, _hash, _encoded,
    signing_bytes, assess_signed_witness_receipts,
)


def fixtures():
    # Both private keys are on the SAME test runner: never independent trust.
    keys = {name: Ed25519PrivateKey.generate() for name in
            ("witness-a", "witness-b")}
    public = {
        name: key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ) for name, key in keys.items()
    }
    manifest = {
        "schema": MANIFEST_SCHEMA, "source_id": "synthetic-source",
        "generation": 7, "conversation_id": "synthetic-conversation",
        "db_sha256": "a" * 64, "db_size": 4096,
        "history_sha256": "b" * 64, "intent_sha256": "c" * 64,
        "pending_marker_sha256": None,
    }
    assessment = {
        "schema": MANIFEST_SCHEMA, "locally_consistent_only": True,
        "issues": ["INDEPENDENT_CUSTODY_NOT_AUTHENTICATED"],
        "can_resume": False,
    }
    heads = {name: {"sequence": 0, "receipt_hash": GENESIS} for name in keys}
    nonce = "d" * 64
    digest = _hash(_encoded(manifest))
    receipts = []
    for name, key in keys.items():
        body = {
            "schema": SCHEMA, "witness_id": name, "sequence": 1,
            "previous_receipt_hash": GENESIS, "manifest_sha256": digest,
            "challenge_nonce": nonce,
        }
        body["signature_hex"] = key.sign(signing_bytes(body)).hex()
        receipts.append(body)
    return {
        "keys": keys, "manifest": manifest, "receipts": receipts,
        "pinned_public_keys": public, "trusted_heads": heads,
        "challenge_nonce": nonce, "a301_assessment": assessment,
    }


def verify(f, **changes):
    args = {k: v for k, v in f.items() if k != "keys"}
    args.update(changes)
    return assess_signed_witness_receipts(**args)


class A302WitnessTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()

    def test_real_ed25519_signatures_are_verified_but_no_go(self):
        result = verify(self.f)
        self.assertTrue(result["cryptographic_receipts_verified"])
        self.assertTrue(result["local_recovery_consistency"])
        self.assertEqual(
            result["issues"], ["REAL_INDEPENDENCE_AND_ANTIROLLBACK_NOT_PROVEN"])
        self.assertFalse(result["can_resume"])

    def test_one_witness_is_not_quorum(self):
        result = verify(self.f, receipts=self.f["receipts"][:1])
        self.assertIn("WITNESS_QUORUM_MISSING", result["issues"])

    def test_same_witness_twice_is_denied(self):
        result = verify(self.f, receipts=[self.f["receipts"][0]] * 2)
        self.assertIn("DUPLICATE_WITNESS", result["issues"])

    def test_distinct_names_same_public_key_denied(self):
        keys = self.f["pinned_public_keys"].copy()
        keys["witness-b"] = keys["witness-a"]
        result = verify(self.f, pinned_public_keys=keys)
        self.assertIn("WITNESS_KEYS_NOT_DISTINCT_OR_INVALID", result["issues"])

    def test_fake_self_declared_witness_is_unpinned(self):
        fake = copy.deepcopy(self.f["receipts"])
        fake[1]["witness_id"] = "attacker-controlled"
        result = verify(self.f, receipts=fake)
        self.assertIn("UNPINNED_WITNESS", result["issues"])

    def test_signature_tampered_denied(self):
        fake = copy.deepcopy(self.f["receipts"])
        fake[0]["signature_hex"] = "0" * 128
        result = verify(self.f, receipts=fake)
        self.assertIn("SIGNATURE_VERIFICATION_FAILED", result["issues"])

    def test_changed_manifest_denied_by_digest(self):
        manifest = dict(self.f["manifest"], generation=8)
        result = verify(self.f, manifest=manifest)
        self.assertIn("MANIFEST_BINDING_MISMATCH", result["issues"])

    def test_receipt_challenge_replay_denied(self):
        result = verify(self.f, challenge_nonce="e" * 64)
        self.assertIn("CHALLENGE_BINDING_MISMATCH", result["issues"])

    def test_receipt_against_newer_trusted_heads_denied(self):
        heads = {name: {"sequence": 1, "receipt_hash": "e" * 64}
                 for name in self.f["trusted_heads"]}
        result = verify(self.f, trusted_heads=heads)
        self.assertIn("REPLAY_OR_CHAIN_DISCONTINUITY", result["issues"])

    def test_rollback_everything_including_heads_can_look_cryptographic(self):
        # All signatures verify if the attacker resets both the state and keys.
        result = verify(self.f)
        self.assertTrue(result["cryptographic_receipts_verified"])
        self.assertFalse(result["trusted_heads_off_host_verified"])
        self.assertFalse(result["independent_custody_verified"])
        self.assertFalse(result["can_resume"])

    def test_a301_inconsistent_snapshot_denied(self):
        assessment = dict(
            self.f["a301_assessment"], locally_consistent_only=False,
            issues=["SNAPSHOT_MISMATCH_DB_SHA256"])
        result = verify(self.f, a301_assessment=assessment)
        self.assertIn("A301_LOCAL_EVIDENCE_NOT_COHERENT", result["issues"])

    def test_missing_pinned_trust_roots_denied(self):
        result = verify(self.f, pinned_public_keys={})
        self.assertIn("PINNED_WITNESS_SET_INVALID", result["issues"])

    def test_malformed_receipt_denied(self):
        rec = copy.deepcopy(self.f["receipts"])
        rec[0]["extra_approval"] = True
        result = verify(self.f, receipts=rec)
        self.assertIn("RECEIPT_FIELDS_INVALID", result["issues"])

    def test_missing_or_invalid_manifest_denied(self):
        result = verify(self.f, manifest={})
        self.assertIn("MANIFEST_INVALID", result["issues"])

    def test_missing_head_denied(self):
        heads = dict(self.f["trusted_heads"])
        heads.pop("witness-b")
        result = verify(self.f, trusted_heads=heads)
        self.assertIn("TRUSTED_HEAD_SET_INVALID", result["issues"])

    def test_binary_public_key_is_required(self):
        keys = self.f["pinned_public_keys"].copy()
        keys["witness-b"] = "not-bytes"
        result = verify(self.f, pinned_public_keys=keys)
        self.assertIn("WITNESS_KEYS_NOT_DISTINCT_OR_INVALID", result["issues"])

    def test_deactivated_witness_not_accepted(self):
        keys = self.f["pinned_public_keys"].copy()
        keys.pop("witness-a")
        result = verify(self.f, pinned_public_keys=keys)
        self.assertIn("PINNED_WITNESS_SET_INVALID", result["issues"])

    def test_failure_to_verify_never_activates_anything(self):
        for case in (verify(self.f), verify(self.f, receipts=[])):
            self.assertFalse(case["can_resume"])
            self.assertFalse(case["can_authorize_real_effect"])
            self.assertEqual(case["p0_homologated"], 0)
            self.assertTrue(case["zero_auto_resend"])
            self.assertEqual(case["automatic_retries"], 0)
            self.assertFalse(case["new_paid_services"])
            self.assertTrue(case["hard_no_go"])


if __name__ == "__main__":
    unittest.main()
