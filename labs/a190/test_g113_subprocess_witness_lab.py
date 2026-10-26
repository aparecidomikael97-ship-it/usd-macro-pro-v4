"""G113 same-host separate-PROCESS witness: acceptance and genuine limits.

Every test uses an actual independent Python subprocess invocation and a
separate synthetic SQLite ledger file on the SAME GitHub runner machine.
This is not external authority, trusted key provisioning or native VFS proof.
No network, real SEND, provider, Worker or money is involved.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from labs.a190.g113_subprocess_witness_client_lab import (
    SubprocessWitnessClientLab, WitnessProcessUnavailableLab,
)


class G113SubprocessWitnessContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="g113-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "witness-ledger.sqlite"
        self.seed = b"\x51" * 32
        self.public_key = Ed25519PrivateKey.from_private_bytes(
            self.seed,
        ).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.client = SubprocessWitnessClientLab(
            db=self.db, synthetic_seed=self.seed,
            pinned_public_key=self.public_key,
        )
        self.identity = {
            "event_id": sha256(b"g113:event:unique-business-1").hexdigest(),
            "original_sha256": sha256(b"g113:human-origin:decision-1").hexdigest(),
            "owner_id": "owner-test", "tenant_id": "tenant-test",
            "workspace_id": "workspace-test",
        }
        self.reservation = {
            **self.identity,
            "effect_digest": sha256(b"g113:effect").hexdigest(),
            "idempotency_key": sha256(b"g113:request-1").hexdigest(),
        }

    def _ready(self):
        self.assertEqual(
            self.client.bootstrap_synthetic_only()["status"],
            "BOOTSTRAPPED_SYNTHETIC_ONLY",
        )
        self.assertEqual(
            self.client.enroll_synthetic_only(**self.identity),
            "ENROLLED",
        )

    def test_01_signed_first_reservation_survives_process_restart(self):
        self._ready()
        receipt = self.client.reserve(**self.reservation)
        self.assertEqual(receipt["status"], "RESERVED")
        self.assertEqual(receipt["sequence"], 1)
        self.assertEqual(receipt["count"], 1)
        recovered = SubprocessWitnessClientLab(
            db=self.db, synthetic_seed=self.seed,
            pinned_public_key=self.public_key,
        ).status(self.identity["event_id"])
        self.assertEqual(recovered["status"], "RESERVED")
        self.assertEqual(recovered["idempotency_key"], self.reservation["idempotency_key"])
        self.assertEqual(recovered["sequence"], 1)
        print("G113_DIFFERENT_PROCESSES=SIGNED_RESERVATION_PERSISTS")

    def test_02_reenrollment_and_changed_request_cannot_duplicate(self):
        self._ready()
        self.assertEqual(self.client.reserve(**self.reservation)["sequence"], 1)
        self.assertEqual(
            self.client.enroll_synthetic_only(**self.identity), "ALREADY_ENROLLED"
        )
        another_id = {
            **self.reservation,
            "idempotency_key": sha256(b"g113:request-2").hexdigest(),
        }
        with self.assertRaisesRegex(
            WitnessProcessUnavailableLab, "G113_DUPLICATE_OR_DENIED_NO_SEND"
        ):
            self.client.reserve(**another_id)
        self.assertEqual(self.client.status(self.identity["event_id"])["high_water"], 1)
        print("G113_CHANGED_REQUEST_SAME_BUSINESS_EVENT=DENIED")

    def test_03_lost_ack_after_commit_is_uncertain_not_retryable(self):
        self._ready()
        with self.assertRaisesRegex(
            WitnessProcessUnavailableLab, "G113_LOST_RESPONSE_AFTER_COMMIT"
        ):
            self.client.reserve(**self.reservation, lost_response=True)
        # Simulate app restart; a different subprocess still sees the commit.
        restarted = SubprocessWitnessClientLab(
            db=self.db, synthetic_seed=self.seed,
            pinned_public_key=self.public_key,
        )
        self.assertEqual(restarted.status(self.identity["event_id"])["status"], "RESERVED")
        with self.assertRaises(WitnessProcessUnavailableLab):
            restarted.reserve(**self.reservation)
        self.assertEqual(restarted.status(self.identity["event_id"])["high_water"], 1)
        print("G113_COMMIT_ACK_LOST=UNCERTAIN_NO_SECOND_RESERVATION")

    def test_04_host_outbox_file_loss_does_not_delete_emulated_witness(self):
        self._ready()
        self.client.reserve(**self.reservation)
        local_host_file = Path(self.temp.name) / "aion-local-cache.sqlite"
        local_host_file.write_bytes(b"synthetic local host state")
        local_host_file.unlink()
        self.assertFalse(local_host_file.exists())
        self.assertEqual(
            self.client.status(self.identity["event_id"])["status"], "RESERVED"
        )
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client.reserve(**self.reservation)
        print("G113_LOCAL_HOST_FILE_LOSS=WITNESS_LEDGER_STILL_SPENT")

    def test_05_unenrolled_event_denied_without_auto_creation(self):
        self.client.bootstrap_synthetic_only()
        status = self.client.status(self.identity["event_id"])
        self.assertEqual(status["status"], "NOT_FOUND")
        with self.assertRaisesRegex(
            WitnessProcessUnavailableLab, "G113_DUPLICATE_OR_DENIED_NO_SEND"
        ):
            self.client.reserve(**self.reservation)
        self.assertEqual(self.client.status(self.identity["event_id"])["high_water"], 0)
        print("G113_UNKNOWN_ORIGINAL_BUSINESS_EVENT=DENIED")

    def test_06_original_enrollment_cannot_be_overwritten_by_request(self):
        self._ready()
        changed = {
            **self.identity,
            "original_sha256": sha256(b"forged-original-identity").hexdigest(),
        }
        self.assertEqual(
            self.client.enroll_synthetic_only(**changed), "ENROLLMENT_CONFLICT"
        )
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client.reserve(**{**self.reservation, **changed})
        self.assertEqual(self.client.status(self.identity["event_id"])["status"], "ENROLLED")
        print("G113_ORIGINAL_ENROLLMENT_SWAP=DENIED")

    def test_07_wrong_signer_with_old_pin_does_not_authorize(self):
        self._ready()
        untrusted = SubprocessWitnessClientLab(
            db=self.db, synthetic_seed=b"\x52" * 32,
            pinned_public_key=self.public_key,
        )
        with self.assertRaisesRegex(
            WitnessProcessUnavailableLab, "G113_SIGNED_STATUS_INVALID"
        ):
            untrusted.status(self.identity["event_id"])
        self.assertEqual(self.client.status(self.identity["event_id"])["status"], "ENROLLED")
        print("G113_WRONG_REMOTE_SIGNING_KEY=DENIED_BY_FIXED_PIN")

    def test_08_replayed_challenge_and_tampered_signed_payload_denied(self):
        self._ready()
        event_id = self.identity["event_id"]
        old = "1" * 64
        reply = self.client._invoke("status", {"event_id": event_id, "challenge": old})
        self.assertTrue(self.client.verify_forged_or_replayed(
            reply, challenge=old, event_id=event_id,
        ))
        self.assertFalse(self.client.verify_forged_or_replayed(
            reply, challenge="2" * 64, event_id=event_id,
        ))
        tampered = deepcopy(reply)
        tampered["payload"]["high_water"] = 7
        self.assertFalse(self.client.verify_forged_or_replayed(
            tampered, challenge=old, event_id=event_id,
        ))
        print("G113_REPLAYED_OR_TAMPERED_SIGNATURE=DENIED")

    def test_09_missing_emulated_witness_does_not_bootstrap(self):
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client.status(self.identity["event_id"])
        self.assertFalse(self.db.exists())
        self._ready()
        self.db.unlink()
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client.status(self.identity["event_id"])
        self.assertFalse(self.db.exists())
        print("G113_LOST_EMULATOR_FILE=FAIL_CLOSED_NO_BOOTSTRAP")

    def test_10_distinct_business_events_can_have_identical_effect_digest(self):
        self._ready()
        first = self.client.reserve(**self.reservation)
        second_id = sha256(b"g113:event:unique-business-2").hexdigest()
        second_event = {**self.identity, "event_id": second_id}
        self.assertEqual(self.client.enroll_synthetic_only(**second_event), "ENROLLED")
        second = self.client.reserve(**{**self.reservation, "event_id": second_id})
        self.assertEqual([first["sequence"], second["sequence"]], [1, 2])
        print("G113_DISTINCT_ENROLLED_EVENTS_SAME_PAYLOAD=TWO_EXPLICIT_EFFECTS")

    def test_11_duplicated_concurrent_requests_produce_one_reservation(self):
        self._ready()

        def reserve_once(_):
            try:
                return self.client.reserve(**self.reservation)["status"]
            except WitnessProcessUnavailableLab:
                return "DENIED"

        with ThreadPoolExecutor(max_workers=4) as pool:
            answers = list(pool.map(reserve_once, range(4)))
        self.assertEqual(answers.count("RESERVED"), 1)
        self.assertEqual(answers.count("DENIED"), 3)
        self.assertEqual(self.client.status(self.identity["event_id"])["high_water"], 1)
        print("G113_FOUR_PARALLEL_PROCESSES=ONE_SYNTHETIC_COMMIT")

    def test_12_privileged_same_host_rollback_STILL_bypasses_monotonicity(self):
        self._ready()
        # This is an intentionally documented REMAINING VULNERABILITY:
        # same-host root can restore both synthetic ledger data and signing
        # seed. None of these signatures is external P0-grade evidence.
        saved_enrollment_only = self.db.read_bytes()
        self.assertEqual(self.client.reserve(**self.reservation)["sequence"], 1)
        self.db.write_bytes(saved_enrollment_only)
        self.assertEqual(self.client.status(self.identity["event_id"])["high_water"], 0)
        self.assertEqual(self.client.reserve(**self.reservation)["sequence"], 1)
        print("G113_SAME_HOST_WITNESS_ROLLBACK=STILL_VULNERABLE_NOT_P0")

    def test_13_wrong_or_missing_event_request_rejected(self):
        self._ready()
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client._invoke("reserve", {
                **self.reservation, "challenge": "bad-challenge"
            })
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client._invoke("reserve", {
                **self.reservation, "challenge": "1" * 64,
                "attacker_controlled_root": "fake",
            })
        self.assertEqual(self.client.status(self.identity["event_id"])["high_water"], 0)
        print("G113_INVALID_WIRE_PROTOCOL=DENIED")


if __name__ == "__main__":
    unittest.main()
