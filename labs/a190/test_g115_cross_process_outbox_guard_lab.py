"""G115 synthetic in-memory Outbox wired to G114 cross-process signed witness.

This is NOT the production Worker. The adapter, enrollment, Ed25519 signer
and witness SQLite database are test-only/same-host. A successful simulated
adapter call proves callback ordering, NOT a real provider SEND or P0 GO.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from aion_chat.intent_binding_a182_lab import semantic_bytes
from labs.a190.g113_subprocess_witness_client_lab import WitnessProcessUnavailableLab
from labs.a190.g114_witness_subprocess_transport_lab import G114SubprocessTransportLab
from labs.a190.g114_public_key_witness_client_lab import G114PublicKeyWitnessClientLab
from labs.a190.g115_public_witness_outbox_guard_lab import PublicOnlyWitnessOutboxGuardLab
from test_atlasquant_aion_intent_binding_a182_lab import A182Fixture
from test_atlasquant_aion_execution_outbox import NOW


class G115CrossProcessOutboxLab(A182Fixture):
    def setUp(self):
        super().setUp()
        root = Path(self.tmp.name)
        self.witness_db = root / "g115-witness.sqlite"
        self.seed_file = root / "g115-witness-signer.bin"
        self.seed = b"\x61" * 32
        self.seed_file.write_bytes(self.seed)
        if os.name != "nt":
            self.seed_file.chmod(0o600)
        public = Ed25519PrivateKey.from_private_bytes(
            self.seed
        ).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.pinned_public_key = public
        self.client = G114PublicKeyWitnessClientLab(
            pinned_public_key=public,
            transport=G114SubprocessTransportLab(
                db_path=self.witness_db,
                witness_test_key_file=self.seed_file,
            ),
        )
        self.original_row = self.original()
        self.business_event_id = sha256(
            b"g115-synthetic-pre-enrolled-original-business-event"
        ).hexdigest()
        self.original_digest = sha256(
            semantic_bytes(self.original_row["decision"])
        ).hexdigest()
        self.enrollment = dict(
            event_id=self.business_event_id,
            original_sha256=self.original_digest,
            owner_id=self.scope.owner_id,
            tenant_id=self.scope.tenant_id,
            workspace_id=self.scope.workspace_id,
        )
        self.client.bootstrap_synthetic_only()
        self.assertEqual(
            self.client.enroll_synthetic_only(**self.enrollment), "ENROLLED"
        )

    def signed_client_with_transport(self, transport):
        # Fault-inject the untrusted TRANSPORT, but retain the real G114
        # signature verifier. Never replace the signed client with arbitrary
        # duck-typed status()/reserve() dictionaries.
        return G114PublicKeyWitnessClientLab(
            pinned_public_key=self.pinned_public_key,
            transport=transport,
        )

    def guard_for(self, *, client=None, event=None, original=None, pin=None):
        return PublicOnlyWitnessOutboxGuardLab(
            witness_client=self.client if client is None else client,
            enrolled_event_id=self.business_event_id if event is None else event,
            enrolled_original_sha256=(
                self.original_digest if pin is None else pin
            ),
            original_decision=(
                self.original_row["decision"] if original is None else original
            ),
        )

    def test_01_one_first_attempt_reaches_synthetic_adapter(self):
        store, outbox, row = self.host(guard=self.guard_for())
        try:
            result, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(result["state"], "CONFIRMED")
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(
                self.client.status(self.business_event_id)["sequence"], 1
            )
        finally:
            store.close()
        print("G115_VALID_SIGNED_CROSS_PROCESS_RESERVATION=ONE_FAKE_SEND")

    def test_02_unknown_original_enrollment_is_uncertain_no_send(self):
        unknown_id = sha256(b"g115-other-event-not-enrolled").hexdigest()
        store, outbox, row = self.host(guard=self.guard_for(event=unknown_id))
        try:
            result, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
            self.assertEqual(
                self.client.status(self.business_event_id)["high_water"], 0
            )
        finally:
            store.close()
        print("G115_UNENROLLED_EVENT=OUTBOX_UNCERTAIN_ZERO_SEND")

    def test_03_lost_commit_ack_is_uncertain_and_witness_spent(self):
        def lose_ack_transport(action, request, *, drop_response=False):
            return self.client._transport(
                action, request,
                drop_response=drop_response or action == "reserve",
            )

        guard = self.guard_for(
            client=self.signed_client_with_transport(lose_ack_transport),
        )
        store, outbox, row = self.host(guard=guard)
        try:
            result, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
            self.assertIsNone(outbox.claim_next("retry", now=NOW + timedelta(seconds=4)))
            record = self.client.status(self.business_event_id)
            self.assertEqual(record["status"], "RESERVED")
            self.assertEqual(record["sequence"], 1)
        finally:
            store.close()
        print("G115_LOST_REMOTE_ACK=NO_PROVIDER_SEND_SPENT")

    def test_04_altered_semantic_decision_denied_before_reservation(self):
        guard = self.guard_for()
        changed = deepcopy(self.original_row)
        changed["decision"]["aggregate_key"] = "rebound-other-account"
        self.assertFalse(guard(changed))
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G115_ALTERED_ORIGINAL=DENIED_BEFORE_REMOTE_COMMIT")

    def test_05_new_technical_request_after_host_reset_denied(self):
        store, outbox, row = self.host(guard=self.guard_for())
        try:
            first, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(first["state"], "CONFIRMED")
            self.assertEqual(adapter.send_calls, 1)
        finally:
            store.close()
        self.host_db.unlink()
        store2, out2, changed_id = self.host(
            ref="new-technical-id", guard=self.guard_for(),
        )
        try:
            outcome, adapter2 = self.claim_and_send(out2, changed_id)
            self.assertEqual(outcome["state"], "UNCERTAIN")
            self.assertEqual(adapter2.send_calls, 0)
            self.assertEqual(self.client.status(self.business_event_id)["count"], 1)
        finally:
            store2.close()
        print("G115_HOST_RESET_NEW_REQUEST_ID=REMOTE_EVENT_STILL_SPENT")

    def test_06_wrong_signer_denied_before_reservation(self):
        self.seed_file.write_bytes(b"\x62" * 32)
        if os.name != "nt":
            self.seed_file.chmod(0o600)
        store, outbox, row = self.host(guard=self.guard_for())
        try:
            result, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
        finally:
            store.close()
        # Reuse the ORIGINAL synthetic test key only to inspect the ledger.
        self.seed_file.write_bytes(self.seed)
        if os.name != "nt":
            self.seed_file.chmod(0o600)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G115_WRONG_SIGNER=OUTBOX_ZERO_SEND")

    def test_07_post_commit_key_swap_denies_even_with_valid_first_receipt(self):
        def swap_key_after_commit(action, request, *, drop_response=False):
            signed = self.client._transport(
                action, request, drop_response=drop_response,
            )
            if action == "reserve":
                self.seed_file.write_bytes(b"\x62" * 32)
                if os.name != "nt":
                    self.seed_file.chmod(0o600)
            return signed

        guard = self.guard_for(
            client=self.signed_client_with_transport(swap_key_after_commit),
        )
        store, outbox, row = self.host(guard=guard)
        try:
            result, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
        finally:
            store.close()
        self.seed_file.write_bytes(self.seed)
        if os.name != "nt":
            self.seed_file.chmod(0o600)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 1)
        print("G115_POST_COMMIT_SIGNATURE_FAIL=SPENT_NO_SEND")

    def test_08_remote_transport_unavailable_denies_cleanly(self):
        def no_transport(_action, _request, *, drop_response=False):
            raise WitnessProcessUnavailableLab("g115 unavailable")

        guard = self.guard_for(
            client=self.signed_client_with_transport(no_transport),
        )
        store, outbox, row = self.host(guard=guard)
        try:
            result, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
        finally:
            store.close()
        self.assertEqual(self.client.status(self.business_event_id)["high_water"], 0)
        print("G115_REMOTE_UNAVAILABLE=ZERO_SEND")

    def test_09_four_concurrent_guards_only_one_synthetic_admission(self):
        guard = self.guard_for()
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(
                lambda _i: guard(deepcopy(self.original_row)), range(4),
            ))
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual(outcomes.count(False), 3)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 1)
        print("G115_FOUR_CONCURRENT_FIRST_ATTEMPTS=ONE_LAB_ADMISSION")

    def test_10_changed_enrollment_pin_constructor_denied(self):
        with self.assertRaisesRegex(ValueError, "G115_ORIGINAL_DECISION_PIN_REQUIRED"):
            self.guard_for(pin="f" * 64)
        mutated = deepcopy(self.original_row["decision"])
        mutated["aggregate_key"] = "not-original"
        with self.assertRaisesRegex(ValueError, "G115_ORIGINAL_DECISION_PIN_REQUIRED"):
            self.guard_for(original=mutated)
        self.assertEqual(self.client.status(self.business_event_id)["high_water"], 0)
        print("G115_MISMATCHED_ORIGINAL_PIN=NO_ENROLLMENT")

    def test_11_host_admin_witness_rollback_still_reopens_event(self):
        old_ledger = self.witness_db.read_bytes()
        first = self.guard_for()
        self.assertTrue(first(deepcopy(self.original_row)))
        self.witness_db.write_bytes(old_ledger)
        # Explicit negative demonstration: process separation is not external
        # root, host admin can restore database and respend the original event.
        self.assertTrue(self.guard_for()(deepcopy(self.original_row)))
        print("G115_HOST_CONTROLLED_WITNESS_ROLLBACK=STILL_VULNERABLE_NOT_P0")


if __name__ == "__main__":
    import unittest
    unittest.main()
