"""A303: pinned-root custody research negatives. 21 lab tests; NEVER GO."""
import copy
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from labs.a302_witness_receipt_contract_lab import _encoded, _hash
from labs.test_a302_witness_receipt_contract_lab import fixtures as a302_fixture
from labs.a303_custody_anchor_chain_lab import (
    SCHEMA, anchor_signing_bytes, assess_custody_anchor,
)


def _public(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def fixture():
    a302 = a302_fixture()
    root = Ed25519PrivateKey.generate()  # host-controlled synthetic root
    args = {k: v for k, v in a302.items() if k != "keys"}
    prev_hash = "e" * 64
    manifest = a302["manifest"]
    anchor = {
        "schema": SCHEMA,
        "root_key_id": "fake-custodian-a303",
        "subject_id": "synthetic-owner-a303",
        "source_id": manifest["source_id"],
        "conversation_id": manifest["conversation_id"],
        "generation": manifest["generation"],
        "incident_epoch": 4, "key_epoch": 3,
        "anchor_sequence": 7,
        "previous_anchor_hash": prev_hash,
        "manifest_sha256": _hash(_encoded(manifest)),
        "witness_keyset_sha256": _hash(_encoded({
            k: v.hex() for k, v in args["pinned_public_keys"].items()
        })),
        "trusted_heads_sha256": _hash(_encoded(args["trusted_heads"])),
        "challenge_nonce": args["challenge_nonce"],
    }
    anchor["signature_hex"] = root.sign(anchor_signing_bytes(anchor)).hex()
    return {
        "a302_inputs": args,
        "anchor": anchor,
        "pinned_root_public_key": _public(root),
        "pinned_root_key_id": anchor["root_key_id"],
        "expected_subject_id": anchor["subject_id"],
        "previous_anchor_sequence": 6,
        "previous_anchor_hash": prev_hash,
        "incident_epoch_floor": 4,
        "key_epoch_floor": 3,
    }, root, a302


def check(f, **changes):
    return assess_custody_anchor(**dict(f, **changes))


def resign(anchor, root, **changes):
    body = dict(anchor, **changes)
    body["signature_hex"] = root.sign(anchor_signing_bytes(body)).hex()
    return body


class A303CustodyTests(unittest.TestCase):
    def setUp(self):
        self.f, self.root, self.a302 = fixture()

    def test_signed_anchor_and_signed_receipts_are_locally_coherent(self):
        r = check(self.f)
        self.assertTrue(r["a302_receipts_verified"])
        self.assertTrue(r["cryptographic_anchor_verified"])
        self.assertTrue(r["local_package_consistent"])
        self.assertEqual(r["issues"], [
            "EXTERNAL_ROOT_AND_ANTIROLLBACK_NOT_ATTESTED"])

    def test_even_three_valid_signatures_never_release_real_effect(self):
        r = check(self.f)
        self.assertFalse(r["independent_root_proven"])
        self.assertFalse(r["off_host_monotonic_floor_verified"])
        self.assertFalse(r["owner_identity_proven"])
        self.assertFalse(r["can_resume"])
        self.assertFalse(r["can_authorize_real_effect"])

    def test_wrong_root_key_rejects_signature(self):
        r = check(self.f,
                  pinned_root_public_key=_public(Ed25519PrivateKey.generate()))
        self.assertIn("ANCHOR_SIGNATURE_INVALID", r["issues"])

    def test_root_key_identifier_swap_is_denied(self):
        r = check(self.f, pinned_root_key_id="unknown-root")
        self.assertIn("ROOT_ID_MISMATCH", r["issues"])

    def test_owner_subject_scope_mismatch_is_denied(self):
        r = check(self.f, expected_subject_id="some-other-owner")
        self.assertIn("SUBJECT_SCOPE_MISMATCH", r["issues"])

    def test_anchor_tampering_without_resign_is_denied(self):
        a = dict(self.f["anchor"], incident_epoch=5)
        r = check(self.f, anchor=a)
        self.assertIn("ANCHOR_SIGNATURE_INVALID", r["issues"])

    def test_anchor_sequence_replay_is_denied(self):
        r = check(self.f, previous_anchor_sequence=7)
        self.assertIn("ANCHOR_SEQUENCE_REPLAY_OR_GAP", r["issues"])

    def test_previous_anchor_hash_mismatch_is_denied(self):
        r = check(self.f, previous_anchor_hash="0" * 64)
        self.assertIn("ANCHOR_CHAIN_DISCONTINUITY", r["issues"])

    def test_reopened_incident_invalidates_old_anchor(self):
        r = check(self.f, incident_epoch_floor=5)
        self.assertIn("INCIDENT_EPOCH_ROLLBACK", r["issues"])

    def test_rotated_key_epoch_invalidates_old_anchor(self):
        r = check(self.f, key_epoch_floor=4)
        self.assertIn("KEY_EPOCH_ROLLBACK", r["issues"])

    def test_manifest_changed_after_anchor_is_denied(self):
        inputs = dict(
            self.f["a302_inputs"],
            manifest=dict(self.f["a302_inputs"]["manifest"], generation=8))
        r = check(self.f, a302_inputs=inputs)
        self.assertIn("MANIFEST_BINDING_MISMATCH", r["issues"])
        self.assertIn("GENERATION_MISMATCH", r["issues"])

    def test_trusted_heads_change_after_anchor_is_denied(self):
        heads = copy.deepcopy(self.f["a302_inputs"]["trusted_heads"])
        heads["witness-a"]["sequence"] = 1
        inputs = dict(self.f["a302_inputs"], trusted_heads=heads)
        r = check(self.f, a302_inputs=inputs)
        self.assertIn("WITNESS_HEADS_BINDING_MISMATCH", r["issues"])
        self.assertIn("A302_RECEIPTS_INVALID", r["issues"])

    def test_unapproved_witness_key_rotation_is_denied(self):
        keys = dict(self.f["a302_inputs"]["pinned_public_keys"])
        keys["witness-b"] = _public(Ed25519PrivateKey.generate())
        inputs = dict(self.f["a302_inputs"], pinned_public_keys=keys)
        r = check(self.f, a302_inputs=inputs)
        self.assertIn("WITNESS_KEYSET_BINDING_MISMATCH", r["issues"])
        self.assertIn("A302_RECEIPTS_INVALID", r["issues"])

    def test_missing_witness_receipt_is_denied(self):
        inputs = dict(self.f["a302_inputs"],
                      receipts=self.f["a302_inputs"]["receipts"][:1])
        r = check(self.f, a302_inputs=inputs)
        self.assertIn("A302_RECEIPTS_INVALID", r["issues"])

    def test_invalid_signature_encoding_is_denied(self):
        a = dict(self.f["anchor"], signature_hex="not-hex")
        r = check(self.f, anchor=a)
        self.assertIn("ANCHOR_SIGNATURE_FORMAT_INVALID", r["issues"])

    def test_malformed_anchor_fields_denied(self):
        a = dict(self.f["anchor"])
        a["extra"] = "GO"
        r = check(self.f, anchor=a)
        self.assertIn("ANCHOR_FIELDS_INVALID", r["issues"])
        self.assertFalse(r["can_resume"])

    def test_invalid_boolean_counter_floor_denied(self):
        r = check(self.f, incident_epoch_floor=True)
        self.assertIn("INCIDENT_EPOCH_FLOOR_INVALID", r["issues"])

    def test_same_key_for_custodian_and_witness_denied(self):
        key = self.a302["keys"]["witness-a"]
        a = resign(self.f["anchor"], key)
        r = check(self.f, anchor=a, pinned_root_public_key=_public(key))
        self.assertIn("ROOT_KEY_EQUALS_WITNESS_KEY", r["issues"])

    def test_challenge_nonce_changed_in_receipt_input_denied(self):
        inputs = dict(self.f["a302_inputs"], challenge_nonce="f" * 64)
        r = check(self.f, a302_inputs=inputs)
        self.assertIn("CHALLENGE_BINDING_MISMATCH", r["issues"])
        self.assertIn("A302_RECEIPTS_INVALID", r["issues"])

    def test_attacker_rebuilds_all_host_controlled_root_and_counters(self):
        # Simulates counterfeit bootstrap of an old-but-coherent state:
        # fake private root + local floor supplied together. Crypto verifies.
        forged, _, _ = fixture()
        r = check(forged)
        self.assertTrue(r["cryptographic_anchor_verified"])
        self.assertTrue(r["a302_receipts_verified"])
        self.assertTrue(r["local_package_consistent"])
        self.assertFalse(r["independent_root_proven"])
        self.assertFalse(r["can_resume"])

    def test_no_new_services_no_auto_retry_and_all_p0_still_open(self):
        for r in (
            check(self.f),
            check(self.f, a302_inputs={}),
            check(self.f, pinned_root_public_key=b"wrong"),
        ):
            self.assertTrue(r["hard_no_go"])
            self.assertTrue(r["zero_auto_resend"])
            self.assertEqual(r["automatic_retries"], 0)
            self.assertEqual(r["p0_homologated"], 0)
            self.assertFalse(r["new_paid_services"])
            self.assertFalse(r["revocation_status_proven"])
            self.assertFalse(r["can_resume"])


if __name__ == "__main__":
    unittest.main()
