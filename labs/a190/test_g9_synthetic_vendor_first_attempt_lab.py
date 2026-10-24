"""A190 G9 end-to-end synthetic custodian/vendor first-attempt adversarial suite."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g8_independent_authority_protocol_lab import (
    Client, RECEIPT_DOMAIN, launch, pub_bytes, rpc, seal, synthetic_event,
)
from g9_synthetic_vendor_first_attempt_lab import (
    FirstAttemptJournal, SYNTHETIC_STATUS, VENDOR_DOMAIN, launch_vendor,
    verify_vendor_receipt,
)

SEMANTIC = sha256(b"ONE-SYNTHETIC-NONFINANCIAL-EFFECT").hexdigest()


class G9VendorFirstAttemptLab(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="a190_g9_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.signer = Ed25519PrivateKey.generate()
        self.authority_state = self.root / "synthetic_custodian"
        self.authority_proc, self.authority_addr, self.authority_pin = launch(
            self.authority_state, pub_bytes(self.signer).hex()
        )
        self.addCleanup(self.stop_authority)
        self.vendor_state = self.root / "synthetic_provider"
        self.vendor_proc = None
        self.start_vendor()
        self.addCleanup(self.stop_vendor)
        self.event = synthetic_event(self.signer)
        self.reservation = self.reserve("req-authority-1")

    def stop_authority(self):
        if self.authority_proc.is_alive():
            self.authority_proc.terminate()
            self.authority_proc.join(timeout=5)
            self.assertFalse(self.authority_proc.is_alive())

    def start_vendor(self):
        self.vendor_proc, self.vendor_addr, self.vendor_pin = launch_vendor(
            self.vendor_state, self.authority_pin
        )
        self.assertTrue(self.vendor_proc.is_alive())

    def stop_vendor(self):
        if self.vendor_proc is not None and self.vendor_proc.is_alive():
            self.vendor_proc.terminate()
            self.vendor_proc.join(timeout=5)
            self.assertFalse(self.vendor_proc.is_alive())
        self.vendor_proc = None

    def reserve(self, request_id):
        client = Client(self.authority_addr, self.authority_pin)
        response = client.reserve_once(
            self.event if hasattr(self, "event") else synthetic_event(self.signer),
            "untrusted-claimed-id", request_id,
        )
        self.assertEqual("RESERVED_ONLY_VERIFIED_NO_EFFECT", response["status"])
        return response["receipt"]

    def journal(self, filename="first_attempt_journal.sqlite"):
        return FirstAttemptJournal(
            self.root / filename, self.authority_pin, self.vendor_pin,
            self.vendor_addr,
        )

    def raw_vendor(self, reservation=None, request_id="fake-provider-request-1",
                   drop_ack=False):
        return rpc(self.vendor_addr, {
            "op": "submit",
            "reservation": reservation or self.reservation,
            "request_id": request_id,
            "lab_drop_response": drop_ack,
        })

    def test_01_two_distinct_signed_receipts_but_no_real_effect(self):
        coordinator = self.journal()
        first = coordinator.attempt_once(
            self.reservation, "vendor-request-one"
        )
        self.assertEqual(
            "SIMULATED_PROVIDER_ACK_VERIFIED_NO_REAL_EFFECT", first["status"]
        )
        proof = first["receipt"]
        self.assertEqual(SYNTHETIC_STATUS, proof["payload"]["status"])
        self.assertTrue(verify_vendor_receipt(
            proof, self.vendor_pin, self.reservation
        ))
        self.assertEqual(
            "SIMULATED_VENDOR_RECORD_RECONCILED_READ_ONLY",
            coordinator.reconcile_read_only(SEMANTIC),
        )
        print("A190_G9_TWO_PINNED_SIGNATURES_VALID=SIMULATION_ONLY")
        print("A190_G9_REAL_PROVIDER_EFFECT_COUNT=ZERO")

    def test_02_vendor_tcp_ack_lost_after_commit_then_no_resend(self):
        coordinator = self.journal()
        response = coordinator.attempt_once(
            self.reservation, "vendor-lost-ack", drop_ack=True
        )
        self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND", response["status"])
        self.assertEqual(1, coordinator.submit_count)
        again = coordinator.attempt_once(
            self.reservation, "vendor-would-resend"
        )
        self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND", again["status"])
        self.assertEqual(1, coordinator.submit_count)
        self.assertEqual(
            "SIMULATED_VENDOR_RECORD_RECONCILED_READ_ONLY",
            coordinator.reconcile_read_only(SEMANTIC),
        )
        print("A190_G9_VENDOR_ACK_LOSS_AFTER_COMMIT=UNCERTAIN_NO_AUTO_RESEND")
        print("A190_G9_SIGNED_VENDOR_READ_ONLY_RECONCILIATION=SIMULATED_ONLY")

    def test_03_h0_crash_after_attempt_journal_before_vendor_send(self):
        before = self.journal()
        self.assertEqual(
            "STAGED_FIRST_ATTEMPT",
            before.stage_first_attempt(self.reservation, "staged-request")
        )
        # Simulated process restart: separate object reopens persisted journal.
        after = self.journal()
        response = after.attempt_once(
            self.reservation, "new-request-after-H0"
        )
        self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND", response["status"])
        self.assertEqual(0, after.submit_count)
        self.assertEqual(
            "UNCERTAIN_NOT_FOUND_STILL_NO_AUTO_RESEND",
            after.reconcile_read_only(SEMANTIC),
        )
        print("A190_G9_H0_AFTER_JOURNAL_BEFORE_SEND=UNCERTAIN_NO_AUTO_RESEND")

    def test_04_vendor_unavailable_no_send_then_no_retry_after_return(self):
        self.stop_vendor()
        coordinator = self.journal()
        result = coordinator.attempt_once(
            self.reservation, "vendor-is-offline"
        )
        self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND", result["status"])
        self.assertEqual(
            "UNCERTAIN_PROVIDER_UNAVAILABLE_ZERO_AUTO_RESEND",
            coordinator.reconcile_read_only(SEMANTIC),
        )
        self.start_vendor()
        restarted = self.journal()
        again = restarted.attempt_once(
            self.reservation, "vendor-back-online"
        )
        self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND", again["status"])
        self.assertEqual(0, restarted.submit_count)
        self.assertEqual(
            "UNCERTAIN_NOT_FOUND_STILL_NO_AUTO_RESEND",
            restarted.reconcile_read_only(SEMANTIC),
        )
        print("A190_G9_VENDOR_DOWN_AND_RECOVERY=FAIL_CLOSED_NO_AUTO_RESEND")

    def test_05_fake_authority_receipt_denied_before_vendor(self):
        attacker = Ed25519PrivateKey.generate()
        fake = seal(attacker, RECEIPT_DOMAIN, self.reservation["payload"])
        coordinator = self.journal()
        result = coordinator.attempt_once(fake, "attacker-local")
        self.assertEqual("DENY_INVALID_AUTHORITY_RESERVATION", result["status"])
        rejected = self.raw_vendor(fake, "attacker-direct")
        self.assertEqual("DENY_UNVERIFIED_RESERVATION", rejected["status"])
        print("A190_G9_VENDOR_DENIES_CALLER_SIGNED_AUTHORITY_RECEIPT")

    def test_06_provider_receipt_forged_wrong_pin_and_self_pin_red(self):
        result = self.raw_vendor(request_id="real-vendor-receipt")
        self.assertEqual("SYNTHETIC_RECORDED", result["status"])
        attacker = Ed25519PrivateKey.generate()
        fake = seal(attacker, VENDOR_DOMAIN, result["receipt"]["payload"])
        self.assertFalse(verify_vendor_receipt(
            fake, self.vendor_pin, self.reservation
        ))
        self.assertTrue(verify_vendor_receipt(
            fake, pub_bytes(attacker), self.reservation
        ))
        print("A190_G9_VENDOR_FORGERY_WITH_RETAINED_PIN=DENIED")
        print("A190_G9_SELF_PINNED_FAKE_VENDOR_RECEIPT=RED")

    def test_07_provider_status_or_binding_tampering_denied(self):
        result = self.raw_vendor(request_id="binding-source")
        receipt = result["receipt"]
        changed = json.loads(json.dumps(receipt))
        changed["payload"]["status"] = "REAL_PROVIDER_PAID"
        self.assertFalse(verify_vendor_receipt(
            changed, self.vendor_pin, self.reservation
        ))
        another = json.loads(json.dumps(receipt))
        another["payload"]["reservation_sha256"] = "0" * 64
        self.assertFalse(verify_vendor_receipt(
            another, self.vendor_pin, self.reservation
        ))
        self.assertFalse(verify_vendor_receipt(
            receipt, self.vendor_pin, self.reservation, epoch=2
        ))
        self.assertFalse(verify_vendor_receipt(
            receipt, self.vendor_pin, self.reservation,
            now=receipt["payload"]["expires"] + 1,
        ))
        print("A190_G9_PROVIDER_EFFECT_BINDING_EPOCH_EXPIRY_TAMPER=DENIED")

    def test_08_provider_receipt_for_second_intent_cannot_attest_first(self):
        digest2 = sha256(b"OTHER-SYNTHETIC-NONFINANCIAL-EFFECT").hexdigest()
        event2 = synthetic_event(
            self.signer, ref="issuer-event-02", digest=digest2
        )
        client = Client(self.authority_addr, self.authority_pin)
        outcome = client.reserve_once(event2, "claim-second", "auth-other-req")
        self.assertEqual("RESERVED_ONLY_VERIFIED_NO_EFFECT", outcome["status"])
        result = self.raw_vendor(
            reservation=outcome["receipt"], request_id="vendor-other"
        )
        self.assertEqual("SYNTHETIC_RECORDED", result["status"])
        self.assertTrue(verify_vendor_receipt(
            result["receipt"], self.vendor_pin, outcome["receipt"]
        ))
        self.assertFalse(verify_vendor_receipt(
            result["receipt"], self.vendor_pin, self.reservation
        ))
        print("A190_G9_CROSS_INTENT_VENDOR_RECEIPT_REUSE=DENIED")

    def test_09_vendor_direct_replay_distinct_ids_blocked_by_semantic(self):
        first = self.raw_vendor(request_id="vendor-original-request")
        self.assertEqual("SYNTHETIC_RECORDED", first["status"])
        again = self.raw_vendor(request_id="vendor-different-request")
        self.assertEqual(
            "DENY_VENDOR_DUPLICATE_SEMANTIC", again["status"]
        )
        print("A190_G9_SYNTHETIC_VENDOR_REPLAY_NEW_REQUEST=DENIED")

    def test_10_concurrent_vendor_submission_only_one_record(self):
        requests = ["concurrent-vendor-" + str(i) for i in range(6)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(
                lambda rid: self.raw_vendor(request_id=rid), requests
            ))
        statuses = [r["status"] for r in results]
        self.assertEqual(1, statuses.count("SYNTHETIC_RECORDED"))
        self.assertEqual(5, statuses.count("DENY_VENDOR_DUPLICATE_SEMANTIC"))
        print("A190_G9_SYNTHETIC_VENDOR_CONCURRENT_SUBMISSIONS=ONE_ONLY")

    def test_11_client_local_journal_deleted_vendor_still_dedups(self):
        journal = self.journal()
        first = journal.attempt_once(self.reservation, "vendor-first")
        self.assertEqual(
            "SIMULATED_PROVIDER_ACK_VERIFIED_NO_REAL_EFFECT", first["status"]
        )
        # A compromised client loses/changes its local first-attempt journal.
        new_journal = self.journal("untrusted-replaced-journal.sqlite")
        outcome = new_journal.attempt_once(
            self.reservation, "vendor-second"
        )
        self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND", outcome["status"])
        self.assertEqual(
            "SIMULATED_VENDOR_RECORD_RECONCILED_READ_ONLY",
            new_journal.reconcile_read_only(SEMANTIC),
        )
        print("A190_G9_CLIENT_JOURNAL_RESET_VENDOR_STILL_DEDUPS=PASS_LAB")

    def test_12_same_host_admin_restores_vendor_sqlite_duplication_red(self):
        db = self.vendor_state / "fake-vendor-ledger.sqlite"
        snapshot = self.root / "old-vendor-state.sqlite"
        shutil.copy2(db, snapshot)
        first = self.raw_vendor(request_id="vendor-before-restore")
        self.assertEqual("SYNTHETIC_RECORDED", first["status"])
        self.stop_vendor()
        shutil.copy2(snapshot, db)
        original_pin = self.vendor_pin
        self.start_vendor()
        self.assertEqual(original_pin, self.vendor_pin)
        second = self.raw_vendor(request_id="vendor-after-restore")
        self.assertEqual("SYNTHETIC_RECORDED", second["status"])
        self.assertTrue(verify_vendor_receipt(
            second["receipt"], self.vendor_pin, self.reservation
        ))
        print("A190_G9_HOST_ADMIN_VENDOR_LEDGER_RESTORE=SECOND_SIGNED_SIMULATED_RECORD_RED")
        print("A190_G9_TRUE_EXTERNAL_PROVIDER_IDEMPOTENCY_PROVEN=False")


if __name__ == "__main__":
    unittest.main(verbosity=2)
