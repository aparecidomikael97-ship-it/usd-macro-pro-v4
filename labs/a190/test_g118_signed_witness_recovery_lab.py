"""G118 lab recovery after an ACK loss: signed witness != provider effect.

The 12 new contracts are appended to the 11 G115 inherited contracts.
Every signer and test ledger is same-host synthetic; provider never contacted.
GREEN here is NOT a first-SEND, immutable-source or external P0 certification.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import os
import sqlite3

from aion_chat.first_attempt_witness_lab import _effect_digest
from labs.a190.g113_subprocess_witness_client_lab import WitnessProcessUnavailableLab
from labs.a190.g114_public_key_witness_client_lab import G114PublicKeyWitnessClientLab
from labs.a190.g118_signed_witness_recovery_lab import G118SignedWitnessRecoveryLab
from labs.a190.test_g115_cross_process_outbox_guard_lab import G115CrossProcessOutboxLab


class G118WitnessRecoveryTests(G115CrossProcessOutboxLab):
    def observer(self, *, client=None, event_id=None, floor=0):
        return G118SignedWitnessRecoveryLab(
            witness_client=self.client if client is None else client,
            event_id=self.business_event_id if event_id is None else event_id,
            original_decision=self.original_row["decision"],
            original_sha256=self.original_digest,
            retained_high_water=floor,
        )

    def reserve_once(self, *, lost_response=False):
        return self.client.reserve(
            event_id=self.business_event_id,
            original_sha256=self.original_digest,
            effect_digest=_effect_digest(self.original_row["decision"]),
            idempotency_key=self.original_row["idempotency_key"],
            owner_id=self.scope.owner_id, tenant_id=self.scope.tenant_id,
            workspace_id=self.scope.workspace_id,
            lost_response=lost_response,
        )

    def assert_no_send_claims(self, result):
        self.assertFalse(result.allow_send)
        self.assertFalse(result.allow_retry)
        self.assertFalse(result.may_mark_provider_confirmed)
        self.assertEqual(result.provider_outcome, "UNKNOWN")

    def test_12_unreserved_signed_status_is_not_permission_to_retry(self):
        result = self.observer().inspect()
        self.assertEqual(result.disposition, "UNSPENT_NOT_PROVEN_NO_SEND")
        self.assertTrue(result.signed_witness_observed)
        self.assert_no_send_claims(result)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G118_SIGNED_ENROLLED=NOT_PROOF_OF_SAFE_RETRY")

    def test_13_committed_witness_reservation_not_provider_confirmation(self):
        self.assertEqual(self.reserve_once()["sequence"], 1)
        result = self.observer(floor=1).inspect()
        self.assertEqual(result.disposition, "RESERVATION_PRESENT_PROVIDER_UNKNOWN")
        self.assertEqual(result.observed_sequence, 1)
        self.assertTrue(result.signed_witness_observed)
        self.assert_no_send_claims(result)
        print("G118_SIGNED_RESERVED=PROVIDER_UNKNOWN_NOT_CONFIRMED")

    def test_14_lost_commit_ack_with_process_restart_stays_uncertain(self):
        with self.assertRaisesRegex(
            WitnessProcessUnavailableLab, "G114_ACK_UNKNOWN_NO_RESEND"
        ):
            self.reserve_once(lost_response=True)
        restarted = G114PublicKeyWitnessClientLab(
            pinned_public_key=self.pinned_public_key,
            transport=self.client._transport,
        )
        decision = self.observer(client=restarted, floor=1).inspect()
        self.assertEqual(decision.disposition, "RESERVATION_PRESENT_PROVIDER_UNKNOWN")
        self.assert_no_send_claims(decision)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 1)
        print("G118_LOST_ACK_RESTART=SIGNED_SPENT_PROVIDER_UNKNOWN")

    def test_15_outbox_uncertain_stays_uncertain_despite_signed_reservation(self):
        def drop_after_commit(action, request, *, drop_response=False):
            return self.client._transport(
                action, request,
                drop_response=drop_response or action == "reserve",
            )
        guard = self.guard_for(
            client=self.signed_client_with_transport(drop_after_commit)
        )
        store, outbox, row = self.host(guard=guard)
        try:
            initial, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(initial["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
            recovered = self.observer(floor=1).inspect()
            self.assertEqual(
                recovered.disposition, "RESERVATION_PRESENT_PROVIDER_UNKNOWN"
            )
            self.assert_no_send_claims(recovered)
            self.assertEqual(outbox.get(row["idempotency_key"])["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
        finally:
            store.close()
        print("G118_RECOVERY_READ_DOES_NOT_PROMOTE_OUTBOX_CONFIRMED")

    def test_16_unknown_event_signed_not_found_never_proves_absence(self):
        missing = sha256(b"g118-event-never-enrolled").hexdigest()
        result = self.observer(event_id=missing).inspect()
        self.assertEqual(result.disposition, "ABSENCE_UNPROVEN_NO_SEND")
        self.assertTrue(result.signed_witness_observed)
        self.assert_no_send_claims(result)
        print("G118_SIGNED_NOT_FOUND=NOT_AUTHORITATIVE_PROVIDER_ABSENCE")

    def test_17_missing_or_wrong_signer_reports_unavailable_and_no_send(self):
        self.seed_file.unlink()
        no_key = self.observer().inspect()
        self.assertEqual(no_key.disposition, "WITNESS_UNAVAILABLE_HOLD_NO_SEND")
        self.assert_no_send_claims(no_key)
        self.seed_file.write_bytes(b"\x62" * 32)
        if os.name != "nt":
            self.seed_file.chmod(0o600)
        wrong_key = self.observer().inspect()
        self.assertEqual(wrong_key.disposition, "WITNESS_UNAVAILABLE_HOLD_NO_SEND")
        self.assert_no_send_claims(wrong_key)
        print("G118_MISSING_OR_INVALID_SIGNER=NO_SEND")

    def test_18_signed_other_request_id_is_identity_conflict(self):
        self.reserve_once()
        with sqlite3.connect(str(self.witness_db)) as conn:
            conn.execute(
                "UPDATE event_enrollments SET idempotency_key=? WHERE event_id=?",
                ("f" * 64, self.business_event_id),
            )
        outcome = self.observer(floor=1).inspect()
        self.assertEqual(
            outcome.disposition, "RESERVATION_IDENTITY_CONFLICT_NO_SEND"
        )
        self.assert_no_send_claims(outcome)
        print("G118_SIGNED_OTHER_TECHNICAL_ID=IDENTITY_CONFLICT")

    def test_19_signed_other_original_is_identity_conflict(self):
        with sqlite3.connect(str(self.witness_db)) as conn:
            conn.execute(
                "UPDATE event_enrollments SET original_sha256=? WHERE event_id=?",
                ("f" * 64, self.business_event_id),
            )
        outcome = self.observer().inspect()
        self.assertEqual(
            outcome.disposition, "ORIGINAL_IDENTITY_CONFLICT_NO_SEND"
        )
        self.assert_no_send_claims(outcome)
        print("G118_HOST_TAMPERED_ORIGINAL=SIGNED_BUT_DENIED")

    def test_20_retained_floor_detects_same_host_ledger_rollback(self):
        previously = self.witness_db.read_bytes()
        self.reserve_once()
        self.witness_db.write_bytes(previously)
        outcome = self.observer(floor=1).inspect()
        self.assertEqual(outcome.disposition, "ROLLBACK_SUSPECTED_NO_SEND")
        self.assert_no_send_claims(outcome)
        # Host also controls this local floor: resetting it back to 0 is a
        # KNOWN unclosed attack. Not a real monotonic external checkpoint.
        unsafe_floor = self.observer(floor=0).inspect()
        self.assertEqual(unsafe_floor.disposition, "UNSPENT_NOT_PROVEN_NO_SEND")
        self.assert_no_send_claims(unsafe_floor)
        print("G118_RESET_LOCAL_FLOOR=STILL_NOT_EXTERNAL_ANTIROLLBACK")

    def test_21_subsequent_different_event_does_not_erase_first_reservation(self):
        self.reserve_once()
        new_event = sha256(b"g118-unrelated-real-business-event").hexdigest()
        self.assertEqual(
            self.client.enroll_synthetic_only(
                **{**self.enrollment, "event_id": new_event}
            ), "ENROLLED",
        )
        self.client.reserve(
            event_id=new_event, original_sha256=self.original_digest,
            effect_digest=_effect_digest(self.original_row["decision"]),
            idempotency_key=sha256(b"g118-other-idempotency").hexdigest(),
            owner_id=self.scope.owner_id, tenant_id=self.scope.tenant_id,
            workspace_id=self.scope.workspace_id,
        )
        outcome = self.observer(floor=1).inspect()
        self.assertEqual(outcome.disposition, "RESERVATION_PRESENT_PROVIDER_UNKNOWN")
        self.assertEqual(outcome.observed_sequence, 1)
        self.assert_no_send_claims(outcome)
        self.assertEqual(self.client.status(self.business_event_id)["high_water"], 2)
        print("G118_LATER_EVENT_ADVANCED_HIGHWATER=FIRST_EVENT_STILL_SPENT")

    def test_22_unsigned_transport_lookalike_refused(self):
        class BareStatus:
            def status(self, _event):
                return {"status": "RESERVED", "sequence": 1}
        with self.assertRaisesRegex(
            TypeError, "G118_SIGNED_PUBLIC_CLIENT_REQUIRED"
        ):
            self.observer(client=BareStatus())
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G118_UNSIGNED_DUCK_CLIENT=DENIED")

    def test_23_recovery_result_immutable_never_approves_send(self):
        result = self.observer().inspect()
        with self.assertRaises(FrozenInstanceError):
            result.allow_send = True
        self.assertFalse(hasattr(self.observer(), "reserve"))
        self.assertFalse(hasattr(self.observer(), "send"))
        self.assertFalse(hasattr(self.observer(), "confirm_provider"))
        self.assert_no_send_claims(result)
        print("G118_RECOVERY_RESULT=IMMUTABLE_NO_SEND_NO_CONFIRM")
