"""G107 RED-first: equal SQLite counters do not prove which reservation survives.

The G106 final checkpoint compares only high_water/count. A host-controlled
SQLite custodian can be replaced with a *different* reservation at the same
ordinal after a valid synthetic out-of-band signature was issued. These tests
use real temporary SQLite but NO external provider, Worker, trusted hardware
or independent external service.
"""
from contextlib import closing
from copy import deepcopy
import sqlite3

from labs.a190.test_g102_pinned_external_attestation_admission_lab import (
    G102PinnedExternalAdmission,
)


_FIELDS = (
    "idempotency_key", "effect_digest", "decision_sha256",
    "owner_id", "tenant_id", "workspace_id",
)


class G107SameCountReservationIdentity(G102PinnedExternalAdmission):
    def _reset_with_single_reservation(self, *, different_effect=False,
                                       different_request=False):
        previous = deepcopy(self.remote_reservation)
        self.custody_db.unlink()
        self.custody = self.bootstrap()
        other = {name: previous[name] for name in _FIELDS}
        if different_effect:
            other["effect_digest"] = "e" * 64
            other["decision_sha256"] = "d" * 64
            other["idempotency_key"] = "f" * 64
        if different_request:
            other["idempotency_key"] = "f" * 64
        assert other != {name: previous[name] for name in _FIELDS}
        result = self.custody.reserve("b" * 64, other)
        assert "signature" in result
        assert self.custody.snapshot() == {"high_water": 1, "count": 1}

    def test_11_same_ordinal_rebootstrap_with_other_effect_denies(self):
        original = self.enroll_fixture()

        def replace_after_signature(challenge, request):
            signed = self.proof_after(challenge, request)
            self._reset_with_single_reservation(different_effect=True)
            return signed

        guard = self.make_guard(
            original, post_probe=replace_after_signature,
            checkpoint=lambda: self.custody.snapshot(),
        )
        self.assertIs(
            guard(original), False,
            "G107_RED: same-count SQLite rebootstrap with a different effect "
            "passed G106 final count-only check",
        )
        self.assertEqual(self.custody.snapshot(), {"high_water": 1, "count": 1})
        self.assertEqual(self.remote_sequence, {"high_water": 1, "count": 1})
        print("G107_SAME_COUNT_OTHER_EFFECT=DENIED")

    def test_12_same_effect_but_new_request_id_denies(self):
        original = self.enroll_fixture()

        def replace_id_after_signature(challenge, request):
            signed = self.proof_after(challenge, request)
            self._reset_with_single_reservation(different_request=True)
            return signed

        guard = self.make_guard(original, post_probe=replace_id_after_signature)
        self.assertIs(
            guard(original), False,
            "G107_RED: matching count and semantic effect re-enrolled with "
            "different technical reservation id passed G106",
        )
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G107_SAME_COUNT_OTHER_REQUEST=DENIED")

    def test_13_mutated_record_decision_with_identical_count_denies(self):
        original = self.enroll_fixture()

        def tamper_decision(challenge, request):
            signed = self.proof_after(challenge, request)
            with closing(sqlite3.connect(str(self.custody_db))) as db, db:
                db.execute(
                    "UPDATE first_attempts SET decision_sha256=?",
                    ("d" * 64,),
                )
            assert self.custody.snapshot() == {"high_water": 1, "count": 1}
            return signed

        guard = self.make_guard(original, post_probe=tamper_decision)
        self.assertIs(
            guard(original), False,
            "G107_RED: a different stored original decision under an unchanged "
            "high-water/count passed G106",
        )
        print("G107_SAME_COUNT_MUTATED_DECISION=DENIED")

    def test_14_intact_record_keeps_valid_synthetic_attempt(self):
        original = self.enroll_fixture()
        guard = self.make_guard(original)
        self.assertIs(guard(original), True)
        self.assertEqual(self.custody.snapshot()["count"], 1)
        self.assertEqual(self.remote_sequence["count"], 1)
        print("G107_ORIGINAL_RECORD=ONE_SYNTHETIC_RESERVATION")
