"""G120 RED-first: self-service event ID enrollment bypasses original authority.

The G115 test witness freely enrolls any new business event ID supplied by
the same host, without owner attestation. Re-enrolling an identical decision
as a NEW event can authorize a second in-memory adapter dispatch. Nothing
here is a real provider call or independent identity proof.
"""
from hashlib import sha256

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
