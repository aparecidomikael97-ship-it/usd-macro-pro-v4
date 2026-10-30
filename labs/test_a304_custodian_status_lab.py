"""A304 LAB negative checks for signed custodian status. Never GO."""
import unittest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from labs.a302_witness_receipt_contract_lab import _encoded, _hash
from labs.a303_custody_anchor_chain_lab import assess_custody_anchor
from labs.test_a303_custody_anchor_chain_lab import fixture as a303_fixture
from labs.a304_custodian_status_lab import (
    SCHEMA, MAX_STATUS_TTL, status_signing_bytes, assess_custodian_status,
)


def _public(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def fixture():
    f, root_key, _ = a303_fixture()
    status_key = Ed25519PrivateKey.generate()
    head = {"sequence": 9, "status_hash": "b" * 64}
    now = 10_000
    status = {
        "schema": SCHEMA,
        "status_key_id": "synthetic-status-key-a304",
        "root_key_id": f["anchor"]["root_key_id"],
        "subject_id": f["anchor"]["subject_id"],
        "source_id": f["anchor"]["source_id"],
        "anchor_sha256": _hash(_encoded(f["anchor"])),
        "key_epoch": f["anchor"]["key_epoch"],
        "incident_epoch": f["anchor"]["incident_epoch"],
        "status_sequence": 10,
        "previous_status_hash": head["status_hash"],
        "valid_from": now - 100,
        "expires_at": now + 100,
        "decision": "ACTIVE",
    }
    status["signature_hex"] = status_key.sign(status_signing_bytes(status)).hex()
    args = {
        "a303_inputs": f,
        "statuses": [status],
        "pinned_status_public_key": _public(status_key),
        "pinned_status_key_id": status["status_key_id"],
        "trusted_status_head": head,
        "now_epoch": now,
        "custodian_online": True,
    }
    return args, status_key, root_key


def sign(existing, key, **changes):
    status = dict(existing, **changes)
    status["signature_hex"] = key.sign(status_signing_bytes(status)).hex()
    return status


def assess(f, **updates):
    return assess_custodian_status(**dict(f, **updates))


class A304CustodyStatusTests(unittest.TestCase):
    def setUp(self):
        self.f, self.key, self.root = fixture()

    def test_valid_active_signature_is_local_only(self):
        r = assess(self.f)
        self.assertTrue(r["a303_local_package_consistent"])
        self.assertEqual(r["cryptographic_status_count"], 1)
        self.assertTrue(r["local_status_consistent"])
        self.assertEqual(r["issues"], [
            "EXTERNAL_REVOCATION_AND_CUSTODY_NOT_ATTESTED"
        ])
        self.assertFalse(r["can_resume"])

    def test_offline_custodian_denied_even_with_valid_cached_signature(self):
        r = assess(self.f, custodian_online=False)
        self.assertEqual(r["cryptographic_status_count"], 1)
        self.assertIn("CUSTODIAN_OFFLINE_OR_UNVERIFIED", r["issues"])
        self.assertFalse(r["local_status_consistent"])

    def test_missing_status_on_outage_denied(self):
        r = assess(self.f, statuses=[], custodian_online=False)
        self.assertIn("STATUS_NOT_AVAILABLE_OR_TOO_MANY", r["issues"])
        self.assertFalse(r["can_resume"])

    def test_signed_revoked_status_denied(self):
        st = sign(self.f["statuses"][0], self.key, decision="REVOKED")
        r = assess(self.f, statuses=[st])
        self.assertIn("CUSTODIAN_KEY_REVOKED", r["issues"])
        self.assertEqual(r["cryptographic_status_count"], 1)

    def test_signed_suspended_status_denied(self):
        st = sign(self.f["statuses"][0], self.key, decision="SUSPENDED")
        r = assess(self.f, statuses=[st])
        self.assertIn("CUSTODIAN_SUSPENDED", r["issues"])

    def test_expired_active_status_denied(self):
        r = assess(self.f, now_epoch=10_100)
        self.assertIn("STATUS_STALE_OR_NOT_YET_VALID", r["issues"])

    def test_future_active_status_denied(self):
        r = assess(self.f, now_epoch=9_899)
        self.assertIn("STATUS_STALE_OR_NOT_YET_VALID", r["issues"])

    def test_overlong_status_validity_denied(self):
        st = sign(
            self.f["statuses"][0], self.key, expires_at=9_900 + MAX_STATUS_TTL + 1
        )
        r = assess(self.f, statuses=[st])
        self.assertIn("STATUS_TIME_WINDOW_INVALID", r["issues"])

    def test_wrong_status_key_denied(self):
        r = assess(
            self.f, pinned_status_public_key=_public(
                Ed25519PrivateKey.generate()
            )
        )
        self.assertIn("STATUS_SIGNATURE_INVALID", r["issues"])

    def test_status_key_id_swap_denied(self):
        r = assess(self.f, pinned_status_key_id="swapped-status-key")
        self.assertIn("STATUS_KEY_ID_MISMATCH", r["issues"])

    def test_reused_anchor_root_key_denied(self):
        st = sign(self.f["statuses"][0], self.root)
        r = assess(self.f, statuses=[st],
                   pinned_status_public_key=_public(self.root))
        self.assertIn("STATUS_KEY_REUSES_ROOT_KEY", r["issues"])

    def test_stale_head_sequence_denied(self):
        h = {"sequence": 10, "status_hash": "b" * 64}
        r = assess(self.f, trusted_status_head=h)
        self.assertIn("STATUS_REPLAY_OR_HEAD_DISCONTINUITY", r["issues"])

    def test_different_head_hash_denied(self):
        h = {"sequence": 9, "status_hash": "0" * 64}
        r = assess(self.f, trusted_status_head=h)
        self.assertIn("STATUS_REPLAY_OR_HEAD_DISCONTINUITY", r["issues"])

    def test_reopened_incident_invalidates_current_status(self):
        f = dict(self.f["a303_inputs"], incident_epoch_floor=5)
        r = assess(self.f, a303_inputs=f)
        self.assertIn("A303_ANCHOR_OR_RECEIPTS_INVALID", r["issues"])

    def test_changed_anchor_hash_denied(self):
        f = dict(self.f["a303_inputs"],
                 anchor=dict(self.f["a303_inputs"]["anchor"], key_epoch=4))
        r = assess(self.f, a303_inputs=f)
        self.assertIn("ANCHOR_BINDING_MISMATCH", r["issues"])

    def test_signed_active_and_revoked_at_same_sequence_are_fork(self):
        revoked = sign(self.f["statuses"][0], self.key, decision="REVOKED")
        r = assess(self.f, statuses=self.f["statuses"] + [revoked])
        self.assertEqual(r["cryptographic_status_count"], 2)
        self.assertIn("SIGNED_EQUIVOCATION_AT_SAME_STATUS_SEQUENCE", r["issues"])
        self.assertIn("CUSTODIAN_KEY_REVOKED", r["issues"])
        self.assertFalse(r["can_resume"])

    def test_signed_two_active_variants_are_still_fork(self):
        active2 = sign(
            self.f["statuses"][0], self.key, expires_at=10_200
        )
        r = assess(self.f, statuses=self.f["statuses"] + [active2])
        self.assertIn("SIGNED_EQUIVOCATION_AT_SAME_STATUS_SEQUENCE", r["issues"])

    def test_duplicate_identical_status_detected(self):
        r = assess(self.f, statuses=self.f["statuses"] * 2)
        self.assertIn("DUPLICATE_STATUS_RECEIPT", r["issues"])

    def test_signature_bitflip_detected(self):
        fake = dict(self.f["statuses"][0], signature_hex="0" * 128)
        r = assess(self.f, statuses=[fake])
        self.assertIn("STATUS_SIGNATURE_INVALID", r["issues"])

    def test_bad_status_fields_denied(self):
        fake = dict(self.f["statuses"][0], approval="real-world")
        r = assess(self.f, statuses=[fake])
        self.assertIn("STATUS_FIELDS_INVALID", r["issues"])

    def test_untrusted_clock_boolean_denied(self):
        r = assess(self.f, now_epoch=True)
        self.assertIn("UNTRUSTED_CLOCK_FORMAT", r["issues"])

    def test_status_expiry_equal_to_start_is_invalid(self):
        st = sign(self.f["statuses"][0], self.key, expires_at=9_900)
        r = assess(self.f, statuses=[st])
        self.assertIn("STATUS_TIME_WINDOW_INVALID", r["issues"])

    def test_attacker_can_replace_local_pin_and_heads_but_never_go(self):
        forged, _, _ = fixture()
        r = assess(forged)
        self.assertTrue(r["local_status_consistent"])
        self.assertFalse(r["independent_status_proven"])
        self.assertFalse(r["off_host_head_proven"])
        self.assertFalse(r["can_resume"])

    def test_every_scenario_stays_hard_no_go_and_zero_auto_resend(self):
        for r in (
            assess(self.f),
            assess(self.f, custodian_online=False),
            assess(self.f, statuses=[]),
        ):
            self.assertTrue(r["hard_no_go"])
            self.assertFalse(r["can_resume"])
            self.assertFalse(r["can_authorize_real_effect"])
            self.assertTrue(r["zero_auto_resend"])
            self.assertEqual(r["automatic_retries"], 0)
            self.assertEqual(r["p0_homologated"], 0)
            self.assertFalse(r["new_paid_services"])
            self.assertFalse(r["revocation_completeness_proven"])


if __name__ == "__main__":
    unittest.main()
