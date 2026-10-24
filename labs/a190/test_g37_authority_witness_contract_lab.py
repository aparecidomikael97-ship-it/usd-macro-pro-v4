"""A190 G37 signed semantic reservation contract checks, LAB only."""
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import sqlite3

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g20_independent_witness_recovery_contract_lab import Admission, RecoveryDenied
from g37_signed_semantic_witness_lab import (
    event_key, issue_for_lab, subprocess_witness,
)
from g37_test_fixtures_lab import EVENT, G37Fixture


class G37AuthorityWitnessTests(G37Fixture):
    def test_01_unsigned_digest_cannot_be_observed(self):
        with self.assertRaisesRegex(RecoveryDenied, "G37_CERTIFIED_PERMIT_REQUIRED_NO_RAW_DIGEST"):
            subprocess_witness(self.witness_dir, "reserve", {
                "snapshot_digest": "a"*64})
        print("G37_RAW_DIGEST_DENIED_GREEN=NO_HOST_SUPPLIED_SNAPSHOT_RESERVATION")

    def test_02_valid_issuer_permit_gets_one_reservation(self):
        c = self.certificate()
        result = self.reserve(c)
        self.assertEqual(result["event_sequence"],1)
        self.assertFalse(result["idempotent"])
        self.assertEqual(result["event_key"],event_key(c["permit"]))
        print("G37_ISSUER_GATE_GREEN=AUTHORITY_SIGNATURE_REQUIRED")

    def test_03_same_signed_semantic_permit_is_idempotent(self):
        cert = self.certificate()
        a = self.reserve(cert)
        b = self.reserve(cert)
        self.assertTrue(b["idempotent"])
        self.assertEqual(a["event_sequence"], b["event_sequence"])
        self.assertEqual(a["permit_digest"], b["permit_digest"])

    def test_04_alias_request_ids_do_not_multiply_reservation(self):
        c = self.certificate()
        first = self.stage(request_ref="request-A")
        other = self.stage(request_ref="request-B")
        self.assertNotEqual(first["idempotency_key"],other["idempotency_key"])
        a,b=self.reserve(c),self.reserve(c)
        self.assertEqual(a["event_sequence"],b["event_sequence"])
        self.assertTrue(b["idempotent"])
        self.assertEqual(self.admit(first,c),Admission.UNCERTAIN)
        self.assertEqual(self.admit(other,c),Admission.UNCERTAIN)
        print("G37_SEMANTIC_DEDUP_GREEN=TWO_REQUEST_ALIASES_ONE_WITNESS_RESERVATION")
        print("G37_LOCAL_ALIAS_RED=TWO_OUTBOX_ROWS_STILL_EXIST")

    def test_05_conflicting_authority_signed_semantic_amount_denied(self):
        self.reserve(self.certificate())
        distinct = self.certificate(amount_minor=2000)
        with self.assertRaisesRegex(RecoveryDenied, "G37_SEMANTIC_EVENT_CONFLICT"):
            self.reserve(distinct)
        print("G37_CONFLICT_GREEN=SAME_BUSINESS_EVENT_DIFFERENT_AMOUNT_DENIED")

    def test_06_changed_permit_without_new_signature_rejected(self):
        cert = self.certificate()
        cert["permit"] = dict(cert["permit"], amount_minor=2000)
        with self.assertRaisesRegex(RecoveryDenied, "G37_ISSUER_SIGNATURE_INVALID"):
            self.reserve(cert)

    def test_07_forged_issuer_signature_rejected(self):
        cert = self.certificate()
        other = Ed25519PrivateKey.generate()
        cert["issuer_signature"] = other.sign(
            __import__("g37_signed_semantic_witness_lab").signing_bytes(cert["permit"])).hex()
        with self.assertRaisesRegex(RecoveryDenied, "G37_ISSUER_SIGNATURE_INVALID"):
            self.reserve(cert)

    def test_08_expired_permit_rejected(self):
        now=int(datetime.now(timezone.utc).timestamp())
        with self.assertRaisesRegex(RecoveryDenied, "G37_PERMIT_INVALID_OR_EXPIRED"):
            self.reserve(self.certificate(expiry=now-1))

    def test_09_bad_amount_and_missing_fields_rejected(self):
        c=self.certificate(amount_minor=0)
        with self.assertRaisesRegex(RecoveryDenied, "G37_PERMIT_INVALID_OR_EXPIRED"):
            self.reserve(c)
        bad=self.certificate()
        bad["permit"].pop("currency")
        with self.assertRaisesRegex(RecoveryDenied, "G37_PERMIT_INVALID_OR_EXPIRED"):
            self.reserve(bad)

    def test_10_bad_authority_pin_reprovision_denied(self):
        bad=(b"\x08"*32).hex()
        with self.assertRaisesRegex(RecoveryDenied, "G37_AUTHORITY_PIN_ROTATION_DENIED"):
            subprocess_witness(self.witness_dir, "init",{"authority_pin":bad})

    def test_11_missing_certificate_cannot_reserve(self):
        with self.assertRaisesRegex(RecoveryDenied,"G37_CERTIFIED_PERMIT_REQUIRED_NO_RAW_DIGEST"):
            subprocess_witness(self.witness_dir,"reserve",{"certified":None})

    def test_12_invalid_challenge_denied(self):
        cert=self.certificate()
        self.reserve(cert)
        with self.assertRaisesRegex(RecoveryDenied,"G37_CHALLENGE_OR_EVENT_INVALID"):
            subprocess_witness(self.witness_dir,"attest",{
                "event_key":event_key(cert["permit"]),"nonce":"bad"})

    def test_13_missing_event_reservation_cannot_attest(self):
        cert=self.certificate()
        with self.assertRaisesRegex(RecoveryDenied,"G37_RESERVATION_ABSENT"):
            self.attest(cert,os.urandom(32))

    def test_14_second_separately_authorized_event_advances_global_counter(self):
        a,b=self.reserve(self.certificate()),self.reserve(self.certificate(event_id=EVENT+"-2"))
        self.assertEqual((a["event_sequence"],b["event_sequence"]),(1,2))
        c=self.certificate()
        proof=self.attest(c,os.urandom(32))
        self.assertEqual(proof["global_sequence"],2)

    def test_15_witness_process_restart_preserves_signer_and_sequence(self):
        cert=self.certificate()
        self.reserve(cert)
        again=subprocess_witness(self.witness_dir,"init",{
            "authority_pin":self.issuer_public.hex()})
        self.assertEqual(again["custody_public_key"],self.custody_public.hex())
        self.assertEqual(self.reserve(cert)["event_sequence"],1)
        print("G37_WITNESS_RESTART_GREEN=ISSUER_PIN_AND_SEMANTIC_RESERVE_PERSIST")

    def test_16_direct_latest_row_tamper_detected(self):
        c=self.certificate()
        self.reserve(c)
        db=sqlite3.connect(self.witness_dir/"witness.sqlite3")
        try:
            db.execute("UPDATE reservations SET permit_digest=?",("f"*64,))
            db.commit()
        finally:
            db.close()
        with self.assertRaisesRegex(RecoveryDenied,"G37_CURRENT_HEAD_TAMPER"):
            self.attest(c,os.urandom(32))

    def test_17_host_can_restore_witness_database_counter_red(self):
        cert1=self.certificate()
        self.reserve(cert1)
        backup=self.witness_dir/"old.sqlite3"
        shutil.copyfile(self.witness_dir/"witness.sqlite3",backup)
        self.reserve(self.certificate(event_id=EVENT+"-2"))
        shutil.copyfile(backup,self.witness_dir/"witness.sqlite3")
        self.assertEqual(self.reserve(cert1)["event_sequence"],1)
        newer=self.reserve(self.certificate(event_id=EVENT+"-3"))
        self.assertEqual(newer["event_sequence"],2)
        print("G37_HOST_WITNESS_ROLLBACK_RED=COUNTER_REUSED_AFTER_DB_RESTORE")

    def test_18_compromised_issuer_can_authorize_dishonest_business_event_red(self):
        compromised_cert=self.certificate(event_id="fabricated-business-event")
        result=self.reserve(compromised_cert)
        self.assertEqual(result["event_sequence"],1)
        print("G37_ISSUER_CAPTURE_RED=LOCAL_KEY_CAN_SIGN_FABRICATED_EVENT")


if __name__=="__main__":
    import unittest
    unittest.main()
