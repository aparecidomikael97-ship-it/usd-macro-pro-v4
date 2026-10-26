"""G114 LAB: public-only client, signer-owned keyfile, *same-host* processes.

The synthetic signer keyfile is created by the TEST HARNESS. It is not a
KMS/HSM, not remote, and a privileged user on this runner can read/rewrite it.
CI success cannot close an externally rooted P0. NO production provider SEND.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from labs.a190.g113_subprocess_witness_client_lab import (
    SubprocessWitnessClientLab, WitnessProcessUnavailableLab,
)
from labs.a190.g114_public_key_witness_client_lab import (
    G114PublicKeyWitnessClientLab,
)
from labs.a190.g114_witness_subprocess_transport_lab import (
    G114SubprocessTransportLab,
)


class G114SeparatedSignerContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="g114-public-client-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / "witness.sqlite"
        self.key_file = self.root / "witness-lab-signing-seed.bin"
        self.synthetic_seed = b"\x56" * 32
        self.key_file.write_bytes(self.synthetic_seed)
        if os.name != "nt":
            self.key_file.chmod(0o600)
        self.pub = self._public(self.synthetic_seed)
        self.transport = G114SubprocessTransportLab(
            db_path=self.db, witness_test_key_file=self.key_file,
        )
        self.client = G114PublicKeyWitnessClientLab(
            pinned_public_key=self.pub, transport=self.transport,
        )
        self.original = {
            "event_id": sha256(b"g114-enrolled-business-event").hexdigest(),
            "original_sha256": sha256(b"g114-original-owner-decision").hexdigest(),
            "owner_id": "g114-owner", "tenant_id": "g114-tenant",
            "workspace_id": "g114-workspace",
        }
        self.intent = {
            **self.original,
            "effect_digest": sha256(b"g114-effect").hexdigest(),
            "idempotency_key": sha256(b"g114-request").hexdigest(),
        }

    @staticmethod
    def _public(seed):
        return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw,
        )

    def _enroll(self):
        self.assertEqual(
            self.client.bootstrap_synthetic_only(),
            {"status": "BOOTSTRAPPED_SYNTHETIC_ONLY"},
        )
        self.assertEqual(
            self.client.enroll_synthetic_only(**self.original), "ENROLLED",
        )

    def test_01_legacy_private_seed_exposure_is_reproduced_then_removed(self):
        # Compare actual child argv. G113 old client includes the private
        # synthetic seed in a process argument, visible to the host admin.
        legacy = SubprocessWitnessClientLab(
            db=self.root / "legacy.sqlite",
            synthetic_seed=self.synthetic_seed, pinned_public_key=self.pub,
        )
        actual_run = subprocess.run
        seen = []

        def capture(*args, **kwargs):
            seen.append(list(args[0]))
            return actual_run(*args, **kwargs)

        with mock.patch(
            "labs.a190.g113_subprocess_witness_client_lab.subprocess.run",
            side_effect=capture,
        ):
            legacy.bootstrap_synthetic_only()
        self.assertEqual(len(seen), 1)
        self.assertIn("--synthetic-seed", seen[0])
        self.assertIn(self.synthetic_seed.hex(), seen[0])

        seen.clear()
        with mock.patch(
            "labs.a190.g114_witness_subprocess_transport_lab.subprocess.run",
            side_effect=capture,
        ):
            self.client.bootstrap_synthetic_only()
        self.assertEqual(len(seen), 1)
        self.assertNotIn("--synthetic-seed", seen[0])
        self.assertNotIn(self.synthetic_seed.hex(), seen[0])
        self.assertIn("--synthetic-key-file", seen[0])
        self.assertNotIn("synthetic_seed", vars(self.client))
        self.assertNotIn("_seed", vars(self.client))
        self.assertNotIn("_witness_key_path", vars(self.client))
        print("G114_LEGACY_SECRET_ARGV=CONFIRMED_NEW_CLIENT_PUBLIC_ONLY")

    def test_02_signed_reservation_through_public_only_client(self):
        self._enroll()
        result = self.client.reserve(**self.intent)
        self.assertEqual(result["status"], "RESERVED")
        self.assertEqual((result["sequence"], result["count"]), (1, 1))
        self.assertEqual(self.client.status(self.original["event_id"])["status"], "RESERVED")
        print("G114_PUBLIC_ONLY_CLIENT=SIGNED_COMMITTED_RESERVATION")

    def test_03_lost_commit_ack_requires_status_no_second_reservation(self):
        self._enroll()
        with self.assertRaisesRegex(
            WitnessProcessUnavailableLab, "G114_ACK_UNKNOWN_NO_RESEND",
        ):
            self.client.reserve(**self.intent, lost_response=True)
        restarted_client = G114PublicKeyWitnessClientLab(
            pinned_public_key=self.pub,
            transport=G114SubprocessTransportLab(
                db_path=self.db, witness_test_key_file=self.key_file,
            ),
        )
        status = restarted_client.status(self.original["event_id"])
        self.assertEqual(status["status"], "RESERVED")
        self.assertEqual(status["high_water"], 1)
        with self.assertRaisesRegex(
            WitnessProcessUnavailableLab, "G113_DUPLICATE_OR_DENIED_NO_SEND",
        ):
            restarted_client.reserve(**self.intent)
        print("G114_LOST_ACK_AND_NEW_PUBLIC_CLIENT=SPENT_NO_RETRY")

    def test_04_changed_request_same_business_event_denied(self):
        self._enroll()
        self.client.reserve(**self.intent)
        other = {**self.intent, "idempotency_key": "f" * 64}
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client.reserve(**other)
        self.assertEqual(self.client.status(self.original["event_id"])["count"], 1)
        print("G114_NEW_TECHNICAL_ID_SAME_EVENT=NO_DUPLICATE")

    def test_05_missing_signer_file_fails_closed_without_auto_enrollment(self):
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client.status(self.original["event_id"])
        self.assertFalse(self.db.exists())
        self.key_file.unlink()
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client.bootstrap_synthetic_only()
        self.assertFalse(self.db.exists())
        print("G114_MISSING_SIGNER_FILE=NO_BOOTSTRAP_NO_SIGNATURE")

    def test_06_wrong_signer_file_with_original_pin_denied(self):
        self._enroll()
        self.key_file.write_bytes(b"\x57" * 32)
        if os.name != "nt":
            self.key_file.chmod(0o600)
        with self.assertRaisesRegex(
            WitnessProcessUnavailableLab, "G113_SIGNED_STATUS_INVALID",
        ):
            self.client.status(self.original["event_id"])
        print("G114_OTHER_SIGNER_WITH_FIXED_PUBLIC_PIN=DENIED")

    def test_07_old_nonce_replay_and_payload_mutation_denied(self):
        self._enroll()
        challenge = "1" * 64
        envelope = self.transport(
            "status", {"event_id": self.original["event_id"], "challenge": challenge},
        )
        self.assertTrue(self.client.verify_forged_or_replayed(
            envelope, challenge=challenge, event_id=self.original["event_id"],
        ))
        self.assertFalse(self.client.verify_forged_or_replayed(
            envelope, challenge="2" * 64, event_id=self.original["event_id"],
        ))
        bad = deepcopy(envelope)
        bad["payload"]["high_water"] = 999
        self.assertFalse(self.client.verify_forged_or_replayed(
            bad, challenge=challenge, event_id=self.original["event_id"],
        ))
        print("G114_STALE_OR_MUTATED_SIGNED_ENVELOPE=DENIED")

    def test_08_original_enrollment_change_denied(self):
        self._enroll()
        different = {**self.original, "original_sha256": "f" * 64}
        self.assertEqual(
            self.client.enroll_synthetic_only(**different), "ENROLLMENT_CONFLICT",
        )
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client.reserve(**{**self.intent, **different})
        self.assertEqual(self.client.status(self.original["event_id"])["high_water"], 0)
        print("G114_ORIGINAL_EVENT_REPLACEMENT=DENIED_IN_TEST_LEDGER")

    def test_09_duplicate_concurrent_subprocesses_reserve_once(self):
        self._enroll()

        def run_once(_):
            try:
                return self.client.reserve(**self.intent)["status"]
            except WitnessProcessUnavailableLab:
                return "DENIED"

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(run_once, range(4)))
        self.assertEqual(results.count("RESERVED"), 1)
        self.assertEqual(results.count("DENIED"), 3)
        self.assertEqual(self.client.status(self.original["event_id"])["count"], 1)
        print("G114_CONCURRENT_PUBLIC_ONLY_CLIENTS=ONE_TEST_COMMIT")

    def test_10_unknown_event_and_malformed_wire_not_authorized(self):
        self.client.bootstrap_synthetic_only()
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client.reserve(**self.intent)
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.transport("reserve", {**self.intent, "challenge": "bad"})
        self.assertEqual(self.client.status(self.original["event_id"])["count"], 0)
        print("G114_NOT_ENROLLED_OR_BAD_WIRE=DENIED")

    def test_11_missing_test_ledger_does_not_rebootstrap(self):
        self._enroll()
        self.client.reserve(**self.intent)
        self.db.unlink()
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.client.status(self.original["event_id"])
        self.assertFalse(self.db.exists())
        print("G114_WITNESS_LEDGER_MISSING=FAIL_CLOSED")

    def test_12_host_privileged_rollback_STILL_breaks_same_host_custody(self):
        self._enroll()
        old_bytes = self.db.read_bytes()
        self.client.reserve(**self.intent)
        self.db.write_bytes(old_bytes)
        self.assertEqual(self.client.status(self.original["event_id"])["high_water"], 0)
        self.assertEqual(self.client.reserve(**self.intent)["sequence"], 1)
        print("G114_SAME_HOST_ROLLBACK=STILL_VULNERABLE_NOT_P0")

    def test_13_invalid_external_transport_response_denied(self):
        fake = G114PublicKeyWitnessClientLab(
            pinned_public_key=self.pub,
            transport=lambda action, request, drop_response=False: {
                "payload": {"status": "RESERVED"}, "signature": "fake",
            },
        )
        with self.assertRaisesRegex(
            WitnessProcessUnavailableLab, "G113_SIGNED_STATUS_INVALID",
        ):
            fake.status(self.original["event_id"])
        self.assertEqual(vars(fake).keys(), {"_pin", "_transport"})
        print("G114_CALLER_INJECTED_FAKE_REMOTE_REPLY=DENIED")

    def test_14_two_authorized_events_may_share_same_payload(self):
        self._enroll()
        one = self.client.reserve(**self.intent)
        second_id = sha256(b"g114-distinct-event").hexdigest()
        self.assertEqual(self.client.enroll_synthetic_only(
            **{**self.original, "event_id": second_id},
        ), "ENROLLED")
        two = self.client.reserve(**{**self.intent, "event_id": second_id})
        self.assertEqual((one["sequence"], two["sequence"]), (1, 2))
        print("G114_DISTINCT_ENROLLED_BUSINESS_EVENTS=EXPLICIT_SEPARATE_RESERVES")

    def test_15_missing_pin_or_transport_fails_enrollment(self):
        with self.assertRaisesRegex(ValueError, "G114_PUBLIC_TRUST_PIN_REQUIRED"):
            G114PublicKeyWitnessClientLab(
                pinned_public_key=b"", transport=self.transport,
            )
        with self.assertRaisesRegex(TypeError, "G114_WITNESS_TRANSPORT_REQUIRED"):
            G114PublicKeyWitnessClientLab(
                pinned_public_key=self.pub, transport=None,
            )
        print("G114_MISSING_PUBLIC_PIN_OR_TRANSPORT=DENIED")


if __name__ == "__main__":
    unittest.main()
