"""G111 RED-first: count and first-attempt record must share one SQLite view.

G107 reads a final high-water/count and THEN the individual SQLite record
through two separate callbacks. A different local reservation can be created
between those callbacks, leaving each individually correct for its point in
time while the accepted result uses an obsolete count. This is a synthetic
race, not a real provider or third-party witness.
"""
from labs.a190.test_g102_pinned_external_attestation_admission_lab import (
    G102PinnedExternalAdmission,
)
from labs.a190.g107_local_reservation_lookup import lookup_stored_reservation


class G111AtomicFinalReservationObservation(G102PinnedExternalAdmission):
    def test_11_second_reservation_between_final_reads_denies(self):
        original = self.enroll_fixture()

        def add_reservation_between_reads(effect_digest):
            previous = self.remote_reservation
            different = {
                name: previous[name] for name in (
                    "idempotency_key", "effect_digest", "decision_sha256",
                    "owner_id", "tenant_id", "workspace_id",
                )
            }
            different["idempotency_key"] = "f" * 64
            different["effect_digest"] = "e" * 64
            result = self.custody.reserve("a" * 64, different)
            assert "signature" in result
            # Lookup returns the ORIGINAL, unchanged record. G107 only
            # compared it to a previously read counter of 1, so it accepts
            # even though actual local sequence is 2 while remote is 1.
            return lookup_stored_reservation(self.custody, effect_digest)

        guard = self.make_guard(
            original, reservation_lookup=add_reservation_between_reads,
        )
        self.assertIs(
            guard(original), False,
            "G111_RED: new local write between separately read snapshot and "
            "receipt was accepted despite missing remote attestation",
        )
        self.assertEqual(self.custody.snapshot(), {"high_water": 2, "count": 2})
        self.assertEqual(self.remote_sequence, {"high_water": 1, "count": 1})
        print("G111_COUNTER_RECORD_RACE=DENIED")

    def test_12_missing_atomic_observer_fails_enrollment(self):
        original = self.enroll_fixture()
        with self.assertRaisesRegex(TypeError, "G111_ATOMIC_OBSERVER_REQUIRED"):
            self.make_guard(original, coherent_observation=False)
        self.assertEqual(self.custody.snapshot()["count"], 0)
        print("G111_MISSING_ATOMIC_READER=DENIED")

    def test_13_inconsistent_atomic_observation_denies(self):
        original = self.enroll_fixture()

        def inconsistent(_effect):
            return {"high_water": 3, "count": 3, "record": None}

        guard = self.make_guard(
            original, coherent_observation=inconsistent,
        )
        self.assertIs(guard(original), False)
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G111_ATOMIC_RECORD_MISMATCH=DENIED")

    def test_14_original_atomic_view_remains_eligible(self):
        original = self.enroll_fixture()
        guard = self.make_guard(original)
        self.assertIs(guard(original), True)
        self.assertEqual(self.custody.snapshot()["count"], 1)
        self.assertEqual(self.remote_sequence["count"], 1)
        print("G111_COHERENT_SQLITE_VIEW=PASS_SYNTHETIC_ONLY")
