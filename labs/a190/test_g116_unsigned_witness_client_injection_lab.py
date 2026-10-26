"""G116 RED-first: G115 accepts fake unsigned client results as admission.

A caller-provided object with status/reserve functions can forge an ENROLLED,
RESERVED, RESERVED sequence of bare dictionaries without any Ed25519 signing.
G115 presently verifies the *shape* of those results but not that they came
from the G114 public-key-pinned verification boundary.

The real result of any test 'send' is an in-memory fake adapter ONLY.
"""
from aion_chat.first_attempt_witness_lab import _effect_digest

from labs.a190.test_g115_cross_process_outbox_guard_lab import (
    G115CrossProcessOutboxLab,
)


class UnsignedForgedWitness:
    """No signer key, no cryptographic signature, no disk reservation."""

    def __init__(self, enrollment, original_decision, request_id):
        self.enrollment = enrollment
        self.effect = _effect_digest(original_decision)
        self.request_id = request_id
        self.status_calls = 0
        self.reserve_calls = 0

    def _status(self, kind, ordinal):
        return dict(
            self.enrollment,
            status=kind,
            high_water=ordinal, count=ordinal, sequence=ordinal,
            effect_digest=self.effect if ordinal else "",
            idempotency_key=self.request_id if ordinal else "",
        )

    def status(self, _event_id):
        self.status_calls += 1
        return self._status(
            "ENROLLED" if self.status_calls == 1 else "RESERVED",
            0 if self.status_calls == 1 else 1,
        )

    def reserve(self, **_request):
        self.reserve_calls += 1
        return self._status("RESERVED", 1)


class G116UnsignedWitnessInjectionTests(G115CrossProcessOutboxLab):
    """Existing G115 contract reruns, plus two new adversarial cases."""

    def _unsigned(self):
        return UnsignedForgedWitness(
            self.enrollment, self.original_row["decision"],
            self.original_row["idempotency_key"],
        )

    def test_12_unsigned_duck_type_must_be_refused_at_enrollment(self):
        fake = self._unsigned()
        with self.assertRaisesRegex(
            TypeError, "G116_AUTHENTICATED_CLIENT_REQUIRED",
        ):
            self.guard_for(client=fake)
        self.assertEqual(fake.reserve_calls, 0)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G116_UNSIGNED_CLIENT_CONSTRUCTOR=DENIED")

    def test_13_unsigned_dictionary_sequence_cannot_release_outbox(self):
        fake = self._unsigned()
        # A correct guard should refuse fake transport BEFORE it can reach
        # the in-memory adapter. If a previous guard accepts this client,
        # actually exercise the Outbox fake-dispatch path and FAIL red.
        try:
            guard = self.guard_for(client=fake)
        except TypeError as exc:
            self.assertIn("G116_AUTHENTICATED_CLIENT_REQUIRED", str(exc))
        else:
            store, outbox, row = self.host(guard=guard)
            try:
                result, adapter = self.claim_and_send(outbox, row)
                self.assertEqual(
                    result["state"], "UNCERTAIN",
                    "G116_RED: unsigned dictionaries authorized fake SEND",
                )
                self.assertEqual(adapter.send_calls, 0)
            finally:
                store.close()
        self.assertEqual(fake.reserve_calls, 0)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G116_UNSIGNED_BARE_RESPONSES=NO_ADAPTER_SEND")
