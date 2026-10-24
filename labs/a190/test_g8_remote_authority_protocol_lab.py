"""A190 G8 cross-platform adversarial contract tests; synthetic loopback only."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g8_independent_authority_protocol_lab import (
    Client, EVENT_DOMAIN, Custodian, check_seal, launch, pub_bytes, rpc,
    seal, synthetic_event, verify_receipt,
)

SEMANTIC = sha256(b"ONE-SYNTHETIC-NONFINANCIAL-EFFECT").hexdigest()


class G8RemoteProtocolLab(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="a190_g8_")
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "remote_process_state"
        self.source_signer = Ed25519PrivateKey.generate()
        self.proc = None
        self.launch()
        self.addCleanup(self.stop)
        self.client = Client(self.address, self.public_pin)
        self.event = synthetic_event(self.source_signer)

    def launch(self):
        self.proc, self.address, self.public_pin = launch(
            self.state, pub_bytes(self.source_signer).hex()
        )
        self.assertTrue(self.proc.is_alive())

    def stop(self):
        if self.proc is not None and self.proc.is_alive():
            self.proc.terminate()
            self.proc.join(timeout=5)
            self.assertFalse(self.proc.is_alive())
        self.proc = None

    def test_01_real_process_signed_reserve_and_replay_denied(self):
        response = self.client.reserve_once(self.event, "client-alias-A", "request-one")
        self.assertEqual("RESERVED_ONLY_VERIFIED_NO_EFFECT", response["status"])
        self.assertTrue(verify_receipt(response["receipt"], self.public_pin))
        self.assertEqual("RESERVED_ONLY_NO_EFFECT",
                         response["receipt"]["payload"]["status"])
        second = self.client.reserve_once(self.event, "client-alias-B", "request-two")
        self.assertEqual("DENY_DUPLICATE_SEMANTIC_OR_REQUEST", second["status"])
        print("A190_G8_REAL_INTERPROCESS_ED25519_RESERVE=PASS_LAB")
        print("A190_G8_SAME_SEMANTIC_DIFFERENT_REQUEST_AND_CLAIMED_ID=DENIED")

    def test_02_same_semantic_two_signed_event_refs_denied(self):
        first = self.client.reserve_once(self.event, "owner-self-1", "req-01")
        self.assertEqual("RESERVED_ONLY_VERIFIED_NO_EFFECT", first["status"])
        second_event = synthetic_event(
            self.source_signer, ref="different-issuer-event-same-economics"
        )
        other_client = Client(self.address, self.public_pin)
        second = other_client.reserve_once(second_event, "owner-self-2", "req-02")
        self.assertEqual("DENY_DUPLICATE_SEMANTIC_OR_REQUEST", second["status"])
        print("A190_G8_SIGNED_ALTERNATE_ORIGINAL_SAME_SEMANTIC=DENIED_LAB")

    def test_03_forged_original_issuer_and_mutation_denied(self):
        attacker = Ed25519PrivateKey.generate()
        forged = synthetic_event(attacker, ref="attacker-self-certification")
        out = self.client.reserve_once(forged, "self-alias", "request-forged")
        self.assertEqual("DENY_UNAUTHENTICATED_EVENT", out["status"])
        tampered = json.loads(json.dumps(self.event))
        tampered["payload"]["event_ref"] = "altered-after-signing"
        out2 = self.client.reserve_once(tampered, "self-alias", "request-altered")
        self.assertEqual("DENY_UNAUTHENTICATED_EVENT", out2["status"])
        print("A190_G8_UNTRUSTED_EVENT_SOURCE_PIN_AND_POST_SIGN_MUTATION=DENIED")

    def test_04_actual_tcp_ack_lost_after_durable_commit_zero_resend(self):
        first = self.client.reserve_once(
            self.event, "claim1", "reqlost1", drop_ack=True
        )
        self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND", first["status"])
        self.assertEqual(1, self.client.send_count)
        retried = self.client.reserve_once(self.event, "claim1", "reqlost2")
        self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND", retried["status"])
        self.assertEqual(1, self.client.send_count)
        reconciled = self.client.reconcile_read_only(
            "synthetic_tenant", SEMANTIC
        )
        self.assertEqual("READ_ONLY_RESERVATION_NOT_EFFECT_CONFIRMED",
                         reconciled["status"])
        print("A190_G8_TCP_REPLY_DROPPED_AFTER_COMMIT=UNCERTAIN_ZERO_AUTO_RESEND")
        print("A190_G8_READ_ONLY_RECONCILIATION=RESERVED_NOT_EFFECT_CONFIRMED")

    def test_05_client_local_state_rollback_cannot_reopen_server(self):
        first = self.client.reserve_once(self.event, "claim1", "req-a")
        self.assertEqual("RESERVED_ONLY_VERIFIED_NO_EFFECT", first["status"])
        # The compromised client loses its entire in-memory history.
        fresh = Client(self.address, self.public_pin)
        second = fresh.reserve_once(self.event, "claim2", "req-b")
        self.assertEqual("DENY_DUPLICATE_SEMANTIC_OR_REQUEST", second["status"])
        print("A190_G8_CLIENT_ONLY_ROLLBACK_SERVER_RETAINED=DENY_DUPLICATE")

    def test_06_unavailable_authority_denies_and_will_not_auto_retry(self):
        self.stop()
        first = self.client.reserve_once(self.event, "claim", "req-offline")
        self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND", first["status"])
        self.assertEqual(1, self.client.send_count)
        again = self.client.reserve_once(self.event, "claim", "req-online")
        self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND", again["status"])
        self.assertEqual(1, self.client.send_count)
        read = self.client.reconcile_read_only("synthetic_tenant", SEMANTIC)
        self.assertEqual("UNCERTAIN_AUTHORITY_UNAVAILABLE", read["status"])
        print("A190_G8_H0_AUTHORITY_UNAVAILABLE=NO_NEW_EFFECT_NO_AUTO_RESEND")

    def test_07_same_host_admin_remote_database_restore_is_red(self):
        original_db = self.state / "custodian.sqlite"
        backup = Path(self.temp.name) / "old_snapshot.sqlite"
        shutil.copy2(original_db, backup)
        first = self.client.reserve_once(self.event, "claim", "req-real-1")
        self.assertEqual("RESERVED_ONLY_VERIFIED_NO_EFFECT", first["status"])
        self.stop()
        # Same-host administrator can edit/restore "server-owned" SQLite.
        shutil.copy2(backup, original_db)
        old_pub = self.public_pin
        self.launch()
        self.assertEqual(old_pub, self.public_pin)
        fresh = Client(self.address, self.public_pin)
        second = fresh.reserve_once(self.event, "claim", "req-real-2")
        self.assertEqual("RESERVED_ONLY_VERIFIED_NO_EFFECT", second["status"])
        self.assertTrue(verify_receipt(second["receipt"], self.public_pin))
        print("A190_G8_SAME_HOST_ADMIN_REMOTE_STATE_RESTORE=UNSAFE_RESIGN_RED")
        print("A190_G8_REAL_INDEPENDENT_HOST_PROVEN=False")

    def test_08_receipt_wrong_pin_expiry_epoch_and_fake_effect_denied(self):
        response = self.client.reserve_once(self.event, "claim", "req-pin")
        self.assertEqual("RESERVED_ONLY_VERIFIED_NO_EFFECT", response["status"])
        receipt = response["receipt"]
        attacker = Ed25519PrivateKey.generate()
        self.assertFalse(verify_receipt(receipt, pub_bytes(attacker)))
        self.assertFalse(verify_receipt(
            receipt, self.public_pin, now=receipt["payload"]["expires"] + 1
        ))
        self.assertFalse(verify_receipt(receipt, self.public_pin, epoch=2))
        forged = json.loads(json.dumps(receipt))
        forged["payload"]["status"] = "EFFECT_CONFIRMED"
        self.assertFalse(verify_receipt(forged, self.public_pin))
        self.assertTrue(verify_receipt(
            seal(attacker, b"A190:G8:SYNTHETIC_CUSTODIAN\0",
                 receipt["payload"]),
            pub_bytes(attacker),
        ))
        print("A190_G8_PIN_EPOCH_EXPIRY_EFFECT_FORGERY=DENIED_WITH_RETAINED_PIN")
        print("A190_G8_SELF_PIN_FORGERY_REMAINS_POSSIBLE=RED")

    def test_09_concurrent_same_semantic_only_one_server_reservation(self):
        reqs = [{
            "op": "reserve",
            "event": self.event,
            "claimed_id": "self-claimed-" + str(n),
            "request_id": "race-" + str(n),
        } for n in range(6)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda data: rpc(self.address, data), reqs))
        values = [result["status"] for result in results]
        self.assertEqual(1, values.count("RESERVED_ONLY"))
        self.assertEqual(5, values.count("DENY_DUPLICATE_SEMANTIC_OR_REQUEST"))
        print("A190_G8_REAL_TCP_SQLITE_CONCURRENT_SAME_SEMANTIC=ONE_ONLY")

    def test_10_read_only_lookup_never_means_provider_effect(self):
        before = self.client.reconcile_read_only("synthetic_tenant", SEMANTIC)
        self.assertEqual("UNCERTAIN_NO_ATTESTED_RESERVATION", before["status"])
        first = self.client.reserve_once(self.event, "claim", "req-readonly")
        self.assertEqual("RESERVED_ONLY_VERIFIED_NO_EFFECT", first["status"])
        after = self.client.reconcile_read_only("synthetic_tenant", SEMANTIC)
        self.assertEqual("READ_ONLY_RESERVATION_NOT_EFFECT_CONFIRMED",
                         after["status"])
        print("A190_G8_NO_PROVIDER_RECEIPT_NO_EFFECT_CONFIRMED=ENFORCED_LAB")


if __name__ == "__main__":
    unittest.main(verbosity=2)
