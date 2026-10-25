"""A190 G37 read-only real Outbox binding; witness never unlocks provider SEND."""
from datetime import datetime, timezone
import os
import shutil

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g20_independent_witness_recovery_contract_lab import Admission, RecoveryDenied
from g37_test_fixtures_lab import EVENT,G37Fixture
from g37_signed_semantic_witness_lab import issue_for_lab, subprocess_witness


class G37RealOutboxReadOnlyRecovery(G37Fixture):
    def test_01_pinned_issuer_and_custodian_matched_only_uncertain(self):
        row=self.stage()
        cert=self.certificate()
        self.reserve(cert)
        self.assertEqual(self.admit(row,cert),Admission.UNCERTAIN)
        self.assertEqual(self.adapter.reads,0)
        self.assertEqual(self.outbox.effect_count(),0)
        print("G37_DOUBLE_PIN_RECOVERY_GREEN=MATCH_ONLY_UNCERTAIN_ZERO_SEND")

    def test_02_uncertain_reopened_outbox_still_no_resend(self):
        row=self.stage()
        cert=self.certificate()
        self.reserve(cert)
        self.make_uncertain(row)
        self.reopen()
        self.assertEqual(self.outbox.get(row["idempotency_key"])["state"],"UNCERTAIN")
        self.assertEqual(self.admit(row,cert),Admission.UNCERTAIN)
        self.assertIsNone(self.outbox.claim_next(
            "g37-worker",now=__import__("g37_test_fixtures_lab").NOW))
        self.assertEqual(self.adapter.reads,0)
        print("G37_REOPEN_GREEN=SIGNED_RESERVATION_STILL_ZERO_AUTO_RESEND")

    def test_03_missing_witness_proof_denied(self):
        row=self.stage()
        cert=self.certificate()
        with self.assertRaisesRegex(RecoveryDenied,"G37_CUSTODY_PROOF_MISSING"):
            self.admit(row,cert,proof={})

    def test_04_no_authority_certificate_denied(self):
        row=self.stage()
        with self.assertRaisesRegex(RecoveryDenied,"G37_AUTHORITY_CERTIFICATE_MISSING"):
            self.admit(row,{},proof={})

    def test_05_local_amount_mismatch_denied(self):
        row=self.stage(amount_minor=2000)
        cert=self.certificate(amount_minor=1000)
        self.reserve(cert)
        with self.assertRaisesRegex(RecoveryDenied,"G37_REAL_OUTBOX_SEMANTIC_BINDING_MISMATCH"):
            self.admit(row,cert)

    def test_06_local_business_id_mismatch_denied(self):
        row=self.stage(event_id=EVENT+"-alias")
        cert=self.certificate()
        self.reserve(cert)
        with self.assertRaisesRegex(RecoveryDenied,"G37_REAL_OUTBOX_SEMANTIC_BINDING_MISMATCH"):
            self.admit(row,cert)

    def test_07_local_scope_mismatch_denied(self):
        row=self.stage()
        cert=self.certificate(scope=["other-owner","g37-tenant","g37-workspace"])
        self.reserve(cert)
        with self.assertRaisesRegex(RecoveryDenied,"G37_REAL_OUTBOX_SEMANTIC_BINDING_MISMATCH"):
            self.admit(row,cert)

    def test_08_explicit_foreign_issuer_pin_denied(self):
        row=self.stage()
        cert=self.certificate()
        self.reserve(cert)
        other=Ed25519PrivateKey.generate()
        from cryptography.hazmat.primitives import serialization
        pin=other.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        with self.assertRaisesRegex(RecoveryDenied,"G37_ISSUER_SIGNATURE_INVALID"):
            self.admit(row,cert,issuer_key=pin)

    def test_09_explicit_foreign_custody_pin_denied(self):
        row=self.stage()
        cert=self.certificate()
        self.reserve(cert)
        with self.assertRaisesRegex(RecoveryDenied,"G37_CUSTODY_SIGNATURE_INVALID"):
            self.admit(row,cert,custody_key=b"\x03"*32)

    def test_10_stale_nonce_replay_denied(self):
        row=self.stage()
        cert=self.certificate()
        self.reserve(cert)
        old=os.urandom(32)
        proof=self.attest(cert,old)
        with self.assertRaisesRegex(RecoveryDenied,"G37_CUSTODY_CHALLENGE_MISMATCH"):
            self.admit(row,cert,nonce=os.urandom(32),proof=proof)

    def test_11_tampered_custody_signature_denied(self):
        row=self.stage()
        cert=self.certificate()
        self.reserve(cert)
        ch=os.urandom(32)
        proof=self.attest(cert,ch)
        proof["custody_signature"]="00"*64
        with self.assertRaisesRegex(RecoveryDenied,"G37_CUSTODY_SIGNATURE_INVALID"):
            self.admit(row,cert,nonce=ch,proof=proof)

    def test_12_signed_cert_does_not_prove_local_global_freshness_red(self):
        row=self.stage()
        cert=self.certificate()
        self.reserve(cert)
        old=self.store_path.parent/"old.sqlite3"
        self.store.close()
        shutil.copyfile(self.store_path,old)
        self.reopen()
        self.make_uncertain(row)
        self.store.close()
        shutil.copyfile(old,self.store_path)
        self.reopen()
        self.assertEqual(self.outbox.get(row["idempotency_key"])["state"],"PENDING")
        self.assertEqual(self.admit(row,cert),Admission.UNCERTAIN)
        print("G37_OUTBOX_ROLLBACK_RED=CERTIFICATE_ALONE_DOES_NOT_PIN_LATEST_STATE")

    def test_13_combined_host_and_custody_rollback_old_valid_proof_red(self):
        first=self.stage()
        cert=self.certificate()
        self.reserve(cert)
        old_db=self.store_path.parent/"host-old.sqlite3"
        old_witness=self.witness_dir/"witness-old.sqlite3"
        self.store.close()
        shutil.copyfile(self.store_path,old_db)
        shutil.copyfile(self.witness_dir/"witness.sqlite3",old_witness)
        self.reopen()
        self.stage(request_ref="second",event_id=EVENT+"-2")
        self.reserve(self.certificate(event_id=EVENT+"-2"))
        self.store.close()
        shutil.copyfile(old_db,self.store_path)
        shutil.copyfile(old_witness,self.witness_dir/"witness.sqlite3")
        self.reopen()
        self.assertEqual(self.admit(first,cert),Admission.UNCERTAIN)
        print("G37_COROLLBACK_RED=SIGNATURES_VALID_AFTER_SAME_HOST_RESTORE")

    def test_14_caller_can_fake_signed_new_event_if_issuer_stolen_red(self):
        forged=self.certificate(event_id="fictitious-event")
        self.reserve(forged)
        row=self.stage(event_id="fictitious-event")
        self.assertEqual(self.admit(row,forged),Admission.UNCERTAIN)
        print("G37_FABRICATED_AUTHORITY_RED=SIGNED_FAKE_MATCHES_LOCAL_OUTBOX")

    def test_15_declared_same_event_cannot_stage_second_request_alias_g57(self):
        cert=self.certificate()
        self.reserve(cert)
        a=self.stage(request_ref="different-req-A")
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(request_ref="different-req-B")
        self.assertEqual(self.admit(a,cert),Admission.UNCERTAIN)
        self.assertEqual(len(self.outbox.list()),1)
        self.assertEqual(self.adapter.reads,0)
        print("G57_G37_REQUEST_ALIAS_GREEN=ONE_LOCAL_RESERVATION")

    def test_16_unavailable_witness_denies_no_send(self):
        row=self.stage()
        cert=self.certificate()
        self.reserve(cert)
        shutil.rmtree(self.witness_dir)
        with self.assertRaisesRegex(RecoveryDenied,"G37_CUSTODY_DENIED"):
            self.admit(row,cert)
        self.assertEqual(self.adapter.reads,0)


if __name__=="__main__":
    import unittest
    unittest.main()
