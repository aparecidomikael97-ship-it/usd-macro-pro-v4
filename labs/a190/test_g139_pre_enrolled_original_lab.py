"""G139 independent enrollment/custody root *shape* acceptance (all synthetic).

18 tests explicitly distinguish a verified pre-existing enrollment document
from merely signing FIRST_ATTEMPT. Both issuer private keys and trust pins are
controlled by CI. Root+original replacement still passes mathematically RED.
No actual external enrollment, independent custodian, network, Worker or SEND.
"""
from copy import deepcopy
from datetime import timedelta
import base64
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from aion_chat.signed_receipt_lab import canonical_bytes
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a190.g137_native_stage_trigger_lab import (
    install_local_tripwire_lab, _record_local_permit,
)
from labs.a190.g138_signed_custody_wire_lab import (
    DOMAIN as CUSTODY_DOMAIN, SCHEMA as CUSTODY_SCHEMA,
    STATUS as CUSTODY_STATUS, root_fingerprint_lab,
)
from labs.a190.g139_pre_enrolled_original_lab import (
    G139OriginalEnrollmentBeforeCustodyLab, DOMAIN, SCHEMA,
    enrollment_root_lab,
)
from labs.a190.test_g135_signed_original_to_actual_outbox_lab import (
    NOW, ORIGINAL, EFFECT,
)

ISSUER = "synthetic-owner-enrollment-authority"
KEY_ID = "synthetic-enrollment-key-1"
ENROLLMENT_EPOCH = 4
CUSTODIAN = "synthetic-external-custodian-NOT-REAL"
CUSTODY_EPOCH = 9


class G139PreEnrolledOwnerOriginalLabTests(unittest.TestCase):
    def setUp(self):
        self.enroll_private = Ed25519PrivateKey.generate()
        self.custody_private = Ed25519PrivateKey.generate()
        self.enroll_public = self.enroll_private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw)
        self.custody_public = self.custody_private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw)
        self.root_enrollment = enrollment_root_lab(
            ISSUER, KEY_ID, ENROLLMENT_EPOCH, self.enroll_public)
        self.root_custody = root_fingerprint_lab(
            CUSTODIAN, CUSTODY_EPOCH, self.custody_public)

    @staticmethod
    def _signed(private, domain, body):
        return {
            "payload": deepcopy(body),
            "signature": base64.b64encode(
                private.sign(domain + canonical_bytes(body))
            ).decode("ascii"),
        }

    def _gate(self, *, original=None, enroll_public=None, custody_public=None,
              enroll_root=None, custody_root=None, enroll_floor=0,
              custody_floor=0, now=NOW):
        ep = self.enroll_public if enroll_public is None else enroll_public
        cp = self.custody_public if custody_public is None else custody_public
        return G139OriginalEnrollmentBeforeCustodyLab(
            original=deepcopy(ORIGINAL if original is None else original),
            enrollment_issuer=ISSUER, enrollment_key_id=KEY_ID,
            enrollment_epoch=ENROLLMENT_EPOCH,
            enrollment_public_key=ep,
            expected_enrollment_root=(
                self.root_enrollment if enroll_root is None else enroll_root),
            enrollment_floor=enroll_floor, custody_authority_id=CUSTODIAN,
            custody_epoch=CUSTODY_EPOCH,
            custody_public_key=cp,
            expected_custody_root=(
                self.root_custody if custody_root is None else custody_root),
            custody_floor=custody_floor, now=now,
        )

    def _enrollment_body(self, *, original=None, **updates):
        return {
            "schema": SCHEMA, "enrollment_id": "retained-original-record-1",
            "issuer": ISSUER, "key_id": KEY_ID,
            "enrollment_epoch": ENROLLMENT_EPOCH,
            "enrollment_sequence": 1,
            "issued_at": (NOW - timedelta(days=3)).isoformat(),
            "custodian_root_sha256": self.root_custody,
            **deepcopy(ORIGINAL if original is None else original),
            **updates,
        }

    def _enroll(self, gate, *, private=None, original=None, **updates):
        body = self._enrollment_body(original=original, **updates)
        return gate.admit_enrollment_once(
            self._signed(self.enroll_private if private is None else private,
                         DOMAIN, body)
        )

    def _custody_receipt(self, nonce, *, original=None, private=None, **updates):
        original = ORIGINAL if original is None else original
        body = {
            "schema": CUSTODY_SCHEMA, "status": CUSTODY_STATUS,
            "authority_id": CUSTODIAN, "authority_epoch": CUSTODY_EPOCH,
            "sequence": 1,
            "challenge": nonce,
            "root_sha256": self.root_custody,
            "issued_at": (NOW - timedelta(seconds=1)).isoformat(),
            "expires_at": (NOW + timedelta(seconds=20)).isoformat(),
            **deepcopy(original),
            **updates,
        }
        return self._signed(
            self.custody_private if private is None else private,
            CUSTODY_DOMAIN, body)

    def _valid_two(self, gate):
        self.assertIs(self._enroll(gate), True)
        nonce = gate.begin_custody_challenge()
        self.assertRegex(nonce, r"^[0-9a-f]{64}$")
        return gate.verify_custody_once(self._custody_receipt(nonce))

    def test_01_valid_enrollment_then_distinct_signed_custody_never_send(self):
        result = self._valid_two(self._gate())
        self.assertEqual(result["original"], ORIGINAL)
        self.assertEqual(result["custody_sequence"], 1)
        self.assertIs(result["permits_send"], False)
        self.assertIs(result["permits_retry"], False)
        self.assertIs(result["external_homologation"], False)
        print("G139_PRIOR_ENROLLMENT_AND_DISTINCT_CUSTODY_SIGNATURES=LAB_ONLY_NO_SEND")

    def test_02_missing_prior_enrollment_cannot_bootstrap_at_first_reservation(self):
        gate = self._gate()
        self.assertIsNone(gate.begin_custody_challenge())
        self.assertIsNone(gate.verify_custody_once(None))
        print("G139_MISSING_PRE_ENROLLMENT=DENY_NO_TRUST_ON_FIRST_USE")

    def test_03_missing_enrollment_ack_consumes_attempt_no_rebootstrap(self):
        gate = self._gate()
        self.assertFalse(gate.admit_enrollment_once(None))
        self.assertFalse(self._enroll(gate))
        self.assertIsNone(gate.begin_custody_challenge())

    def test_04_wrong_enrollment_signing_key_cannot_fake_original(self):
        gate = self._gate()
        attacker = Ed25519PrivateKey.generate()
        self.assertFalse(self._enroll(gate, private=attacker))

    def test_05_fake_event_id_and_economic_hash_denied(self):
        for updates in (
            {"event_id": "fake-reenrollment-B"},
            {"original_sha256": "e" * 64},
            {"owner_id": "other-owner"},
            {"tenant_id": "other-tenant"},
            {"workspace_id": "other-workspace"},
        ):
            with self.subTest(updates=updates):
                self.assertFalse(self._enroll(self._gate(), **updates))

    def test_06_enrollment_issuer_and_key_id_mismatch_denied(self):
        for updates in (
            {"issuer": "fake-enrollment-issuer"},
            {"key_id": "attacker-key"},
            {"enrollment_id": "not valid spaces"},
        ):
            with self.subTest(updates=updates):
                self.assertFalse(self._enroll(self._gate(), **updates))

    def test_07_original_enrollment_must_bind_distinct_custodian_root(self):
        gate = self._gate()
        self.assertFalse(self._enroll(
            gate, custodian_root_sha256="0" * 64))
        self.assertIsNone(gate.begin_custody_challenge())

    def test_08_epoch_sequence_rollback_and_boolean_sequence_rejected(self):
        for updates in (
            {"enrollment_epoch": ENROLLMENT_EPOCH - 1},
            {"enrollment_sequence": 0},
            {"enrollment_sequence": True},
        ):
            with self.subTest(updates=updates):
                self.assertFalse(self._enroll(self._gate(), **updates))
        self.assertFalse(self._enroll(self._gate(enroll_floor=1)))
        print("G139_STALE_PRE_ENROLLMENT_SEQUENCE=DENIED_LOCAL_FLOOR_ONLY")

    def test_09_future_stale_or_naive_enrollment_denied(self):
        for updates in (
            {"issued_at": (NOW + timedelta(days=1)).isoformat()},
            {"issued_at": (NOW - timedelta(days=366)).isoformat()},
            {"issued_at": "2026-10-20T12:00:00"},
        ):
            with self.subTest(updates=updates):
                self.assertFalse(self._enroll(self._gate(), **updates))

    def test_10_reused_enrollment_receipt_does_not_repeat_admission(self):
        gate = self._gate()
        proof = self._signed(self.enroll_private, DOMAIN,
                             self._enrollment_body())
        self.assertTrue(gate.admit_enrollment_once(proof))
        self.assertFalse(gate.admit_enrollment_once(proof))
        self.assertIsNotNone(gate.begin_custody_challenge())
        self.assertIsNone(gate.begin_custody_challenge())

    def test_11_same_enrollment_and_custody_key_refused(self):
        with self.assertRaisesRegex(ValueError, "DISTINCT"):
            self._gate(
                custody_public=self.enroll_public,
                custody_root=root_fingerprint_lab(
                    CUSTODIAN, CUSTODY_EPOCH, self.enroll_public))

    def test_12_missing_or_mismatched_trust_roots_are_not_self_repaired(self):
        with self.assertRaises(ValueError):
            self._gate(enroll_root="0" * 64)
        with self.assertRaises(ValueError):
            self._gate(custody_root="0" * 64)
        with self.assertRaises(ValueError):
            self._gate(enroll_public=b"")
        with self.assertRaises(ValueError):
            self._gate(custody_public=b"")
        with self.assertRaises(ValueError):
            self._gate(enroll_floor=-1)
        with self.assertRaises(ValueError):
            self._gate(custody_floor=-1)

    def test_13_extra_fields_and_corrupted_signature_fail_closed(self):
        gate = self._gate()
        body = self._enrollment_body()
        body["unsafe_re_enroll_if_missing"] = True
        self.assertFalse(gate.admit_enrollment_once(
            self._signed(self.enroll_private, DOMAIN, body)))
        gate2 = self._gate()
        proof = self._signed(self.enroll_private, DOMAIN,
                             self._enrollment_body())
        proof["signature"] = "not@base64"
        self.assertFalse(gate2.admit_enrollment_once(proof))

    def test_14_wrong_custody_nonce_identity_root_and_signature_denied(self):
        for tamper in (
            {"challenge": "e" * 64},
            {"event_id": "fake-second-original"},
            {"root_sha256": "0" * 64},
            {"authority_epoch": CUSTODY_EPOCH + 1},
        ):
            with self.subTest(tamper=tamper):
                gate = self._gate()
                self.assertTrue(self._enroll(gate))
                nonce = gate.begin_custody_challenge()
                self.assertIsNone(gate.verify_custody_once(
                    self._custody_receipt(nonce, **tamper)))
        gate = self._gate()
        self.assertTrue(self._enroll(gate))
        nonce = gate.begin_custody_challenge()
        self.assertIsNone(gate.verify_custody_once(
            self._custody_receipt(nonce, private=Ed25519PrivateKey.generate())))

    def test_15_custody_stale_floor_blocks_proof_even_after_good_enrollment(self):
        gate = self._gate(custody_floor=1)
        self.assertTrue(self._enroll(gate))
        nonce = gate.begin_custody_challenge()
        self.assertIsNone(gate.verify_custody_once(self._custody_receipt(nonce)))

    def test_16_unknown_custodian_ack_consumes_once_and_never_auto_resends(self):
        gate = self._gate()
        self.assertTrue(self._enroll(gate))
        nonce = gate.begin_custody_challenge()
        self.assertIsNone(gate.verify_custody_once(None))
        self.assertIsNone(gate.verify_custody_once(self._custody_receipt(nonce)))
        print("G139_CUSTODY_ACK_LOSS=UNCERTAIN_ZERO_AUTO_RESEND_LAB")

    def test_17_host_replaces_both_roots_and_original_self_enrolls_red(self):
        # Both privately generated keys and retained original are caller-owned.
        alternate_owner = {**ORIGINAL, "event_id": "attacker-new-original-B"}
        original_enrollment = self.enroll_private
        original_custody = self.custody_private
        self.enroll_private = Ed25519PrivateKey.generate()
        self.custody_private = Ed25519PrivateKey.generate()
        self.enroll_public = self.enroll_private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw)
        self.custody_public = self.custody_private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw)
        self.root_enrollment = enrollment_root_lab(
            ISSUER, KEY_ID, ENROLLMENT_EPOCH, self.enroll_public)
        self.root_custody = root_fingerprint_lab(
            CUSTODIAN, CUSTODY_EPOCH, self.custody_public)
        gate = self._gate(original=alternate_owner)
        self.assertTrue(self._enroll(gate, original=alternate_owner))
        nonce = gate.begin_custody_challenge()
        fake = gate.verify_custody_once(self._custody_receipt(
            nonce, original=alternate_owner))
        self.assertEqual(fake["original"], alternate_owner)
        print("G139_JOINT_SELF_REPIN_ENROLLMENT_AND_CUSTODY=FAKE_FIRST_ADMITTED_RED_NOT_P0")

    def test_18_same_host_can_self_mint_g137_ticket_without_any_g139(self):
        # More than two signatures needed: host owner still controls native DB.
        with tempfile.TemporaryDirectory(prefix="aion-g139-") as temp:
            dbpath = Path(temp) / "unguarded-host-authority.sqlite3"
            scope = Scope("synthetic-owner", "synthetic-tenant",
                          "synthetic-workspace")
            store = SQLiteChatStore(dbpath)
            try:
                outbox = ExecutionOutbox(store, scope)
                install_local_tripwire_lab(outbox)
                payload = {"business_event_id": "attacker-unenrolled-effect", **EFFECT}
                _record_local_permit(outbox.db, scope, "synthetic-direct",
                                     EFFECT["action"], "attacker-unenrolled-effect",
                                     payload)
                from datetime import timedelta
                item = outbox.enqueue(
                    intent_ref="synthetic-direct", action=EFFECT["action"],
                    payload=payload,
                    semantic_event_id_lab="attacker-unenrolled-effect",
                    aggregate_key="synthetic-no-real-effect",
                    policy_version="LAB", authorization_ref="FAKE-SELF-MINT",
                    created_at=NOW, valid_until=NOW+timedelta(minutes=5),
                )
                self.assertEqual(item["enqueue_state"], "ENQUEUED")
                self.assertEqual(len(outbox.list()), 1)
            finally:
                store.close()
        print("G139_DIRECT_LOCAL_G137_TICKET_WITHOUT_ENROLLMENT=STAGE_BYPASS_RED_NO_SEND")


if __name__ == "__main__":
    unittest.main()
