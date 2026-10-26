"""G120 RED-first: self-service event ID enrollment bypasses original authority.

The G115 test witness freely enrolls any new business event ID supplied by
the same host, without owner attestation. Re-enrolling an identical decision
as a NEW event can authorize a second in-memory adapter dispatch. Nothing
here is a real provider call or independent identity proof.
"""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from test_atlasquant_aion_execution_outbox import NOW
from labs.a190.test_g115_cross_process_outbox_guard_lab import (
    G115CrossProcessOutboxLab,
)


class G120UnattestedBusinessIdentityRed(G115CrossProcessOutboxLab):
    def test_12_caller_reenrolls_same_business_effect_as_new_event_denied(self):
        new_event = sha256(b"g120-caller-invented-identity-for-same-effect").hexdigest()
        self.assertNotEqual(new_event, self.business_event_id)
        # The synthetic issuer has no separate owner enrollment authority:
        # the same caller can enroll another technical business event.
        self.assertEqual(
            self.client.enroll_synthetic_only(
                **{**self.enrollment, "event_id": new_event},
            ), "ENROLLED",
        )
        try:
            guard = self.guard_for(event=new_event)
        except ValueError as exc:
            self.assertIn("G120_OWNER_ENROLLMENT", str(exc))
        else:
            store, outbox, row = self.host(guard=guard)
            try:
                result, adapter = self.claim_and_send(outbox, row)
                self.assertEqual(
                    result["state"], "UNCERTAIN",
                    "G120_RED: caller-invented event identity authorized "
                    "another simulated first-attempt dispatch",
                )
                self.assertEqual(adapter.send_calls, 0)
            finally:
                store.close()
        print("G120_UNAPPROVED_SECOND_EVENT=NO_FAKE_SEND")

    def test_13_corrupted_owner_signature_denied_before_adapter(self):
        forged = deepcopy(self.owner_proof)
        forged["signature"] = "ZmFrZQ=="
        with self.assertRaisesRegex(ValueError, "G120_OWNER_ENROLLMENT_SIGNATURE_INVALID"):
            self.guard_for(owner_receipt=forged)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G120_CORRUPT_SYNTHETIC_OWNER_SIGNATURE=DENIED")

    def test_14_other_signer_under_pinned_owner_root_denied(self):
        stranger = Ed25519PrivateKey.from_private_bytes(b"\x74" * 32)
        signed_by_stranger = self.issue_test_owner_enrollment(
            event_id=self.business_event_id,
            decision=self.original_row["decision"],
            signer=stranger,
        )
        with self.assertRaisesRegex(ValueError, "G120_OWNER_ENROLLMENT_SIGNATURE_INVALID"):
            self.guard_for(owner_receipt=signed_by_stranger)
        print("G120_WRONG_OWNER_SIGNING_KEY=DENIED")

    def test_15_tampered_owner_scope_policy_and_nonce_denied(self):
        for field, wrong in (
            ("owner_id", "other-owner"), ("tenant_id", "other-tenant"),
            ("workspace_id", "other-workspace"),
            ("policy_version", "other-policy"),
            ("authorization_ref", "other-approval"),
            ("action", "delete-account"),
            ("nonce", "f" * 64),
            ("audience", "some-other-audience"),
        ):
            with self.subTest(field=field):
                modified = deepcopy(self.owner_proof)
                modified["payload"][field] = wrong
                with self.assertRaisesRegex(ValueError, "G120_OWNER_ENROLLMENT_"):
                    self.guard_for(owner_receipt=modified)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G120_OWNER_SCOPE_POLICY_ACTION_NONCE=DENIED")

    def test_16_approval_expired_at_dispatch_blocks_fake_send(self):
        current = [NOW + timedelta(seconds=2)]
        guard = self.guard_for(approval_clock=lambda: current[0])
        current[0] = NOW + timedelta(minutes=6)
        store, outbox, row = self.host(guard=guard)
        try:
            result, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
        finally:
            store.close()
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G120_EXPIRED_OWNER_APPROVAL_AT_USE=ZERO_FAKE_SEND")

    def test_17_long_lived_approval_window_even_if_signed_denied(self):
        overlong = self.issue_test_owner_enrollment(
            event_id=self.business_event_id,
            decision=self.original_row["decision"],
        )
        overlong["payload"]["expires_at"] = (
            NOW + timedelta(days=30)
        ).isoformat()
        from aion_chat.signed_receipt_lab import canonical_bytes
        from labs.a190.g120_synthetic_owner_enrollment_lab import DOMAIN
        import base64
        overlong["signature"] = base64.b64encode(
            self.owner_private.sign(
                DOMAIN + canonical_bytes(overlong["payload"])
            )
        ).decode("ascii")
        with self.assertRaisesRegex(
            ValueError, "G120_OWNER_ENROLLMENT_EXPIRED_OR_NOT_YET_VALID",
        ):
            self.guard_for(owner_receipt=overlong)
        print("G120_EXCESSIVELY_LONG_APPROVAL=DENIED")

    def test_18_missing_approval_missing_pin_or_untrusted_clock_denied(self):
        with self.assertRaisesRegex(ValueError, "G120_OWNER_ENROLLMENT_"):
            self.guard_for(owner_receipt={})
        with self.assertRaisesRegex(ValueError, "G120_OWNER_ENROLLMENT_"):
            self.guard_for(owner_public_pin=b"")
        with self.assertRaisesRegex(
            ValueError, "G120_OWNER_ENROLLMENT_TRUSTED_AWARE_CLOCK_REQUIRED",
        ):
            self.guard_for(approval_clock=lambda: None)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G120_MISSING_APPROVAL_PIN_OR_CLOCK=DENIED")

    def test_19_same_host_repins_both_owner_key_and_proof_STILL_unsafe(self):
        # Deliberate negative control. A host admin who can replace BOTH
        # public key pin and enrollment may still impersonate the simulated
        # 'owner'; the external P0 requirement remains unmet.
        other_key = Ed25519PrivateKey.from_private_bytes(b"\x75" * 32)
        other_pub = other_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw,
        )
        new_event = sha256(b"g120-host-forged-owner-and-new-event").hexdigest()
        self.assertEqual(
            self.client.enroll_synthetic_only(
                **{**self.enrollment, "event_id": new_event},
            ), "ENROLLED",
        )
        fake_owner_enrollment = self.issue_test_owner_enrollment(
            event_id=new_event,
            decision=self.original_row["decision"],
            signer=other_key,
        )
        new_guard = self.guard_for(
            event=new_event, owner_receipt=fake_owner_enrollment,
            owner_public_pin=other_pub,
        )
        store, outbox, row = self.host(guard=new_guard)
        try:
            result, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(result["state"], "CONFIRMED")
            self.assertEqual(adapter.send_calls, 1)
        finally:
            store.close()
        print("G120_HOST_CONTROLLED_OWNER_REPIN=STILL_VULNERABLE_NOT_P0")
