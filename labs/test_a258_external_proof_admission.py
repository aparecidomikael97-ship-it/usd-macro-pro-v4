"""A258 lab audit: signed artifacts and CI claims are NOT independent proof."""
from dataclasses import FrozenInstanceError
from concurrent.futures import ThreadPoolExecutor
import unittest

from labs.a258_external_proof_admission import (
    GAPS, SCHEMA, assess_offline_claims,
)
from labs.test_a243_signed_first_attempt import _attempt
from labs.test_a254_synthetic_origin_event_identity import (
    NOW, _decision, _envelope,
)
from labs.test_a255_two_party_reservation_binding import (
    CHALLENGE, _bridge, _witness_receipt,
)
from labs.test_a257_monotonic_origin_gate import (
    FakeMonotonicClock, _issue, _lab, _review,
)


class A258OfflineProofAdmissionTests(unittest.TestCase):
    def _assert_no_go(self, value):
        result = assess_offline_claims(value)
        self.assertEqual(result.schema, SCHEMA)
        self.assertEqual(result.status, "HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING")
        self.assertEqual(result.p0_homologated, 0)
        self.assertEqual(result.p0_required, 6)
        self.assertEqual(result.missing_p0, tuple(p for p, _ in GAPS))
        self.assertFalse(result.independent_authority_proven)
        self.assertFalse(result.authorizes_send)
        self.assertFalse(result.permits_worker)
        self.assertFalse(result.permits_deploy)
        self.assertFalse(result.permits_merge)
        return result

    def test_01_no_claims_denies_all_six_p0(self):
        outcome = self._assert_no_go(None)
        self.assertEqual(outcome.evidence_classification, "NO_EXTERNAL_EVIDENCE_SUBMITTED")

    def test_02_fake_verified_trusted_and_green_flags_are_not_authority(self):
        for claim in (
            {"trusted": True, "verified": True, "ready": True},
            {"p0_complete": 6, "ci_passed": True, "go": True},
            {"external_verified": True, "root_independent": True},
            {"authorizes_send": True, "human_owner": True},
            {"status": "RESERVED", "signed": True, "attested": True},
        ):
            with self.subTest(claim=claim):
                self._assert_no_go(claim)

    def test_03_signed_origin_event_does_not_prove_external_issuer(self):
        d = _decision()
        envelope = _envelope(d, "a258-lab-origin")
        self._assert_no_go(envelope)

    def test_04_two_valid_signatures_do_not_prove_separate_key_custody(self):
        d = _decision()
        origin = _envelope(d, "a258-lab-two-signatures")
        result = _bridge().review(
            d, origin, _witness_receipt(origin), expected_challenge=CHALLENGE,
        )
        self.assertTrue(result["linked_format_valid"])
        self.assertFalse(result["authorizes_send"])
        self._assert_no_go(result)

    def test_05_valid_one_time_nonce_is_not_external_attestation(self):
        d, lab = _decision(), _lab(FakeMonotonicClock())
        origin = _envelope(d, "a258-lab-nonce")
        nonce = _issue(lab, d, origin)
        result = _review(lab, d, origin, nonce)
        self.assertTrue(result["linked_format_valid"])
        self.assertFalse(result["independent_challenge_proven"])
        self._assert_no_go(result)

    def test_06_six_p0_ids_are_distinct_and_stable(self):
        self.assertEqual(tuple(x[0] for x in GAPS), tuple(
            f"P0-{n}" for n in range(1, 7)
        ))
        self.assertEqual(len({x[1] for x in GAPS}), 6)
        self.assertTrue(all(x[1] for x in GAPS))

    def test_07_malformed_objects_cannot_create_a_positive_result(self):
        class Hostile:
            def __bool__(self):
                raise RuntimeError("host controlled truthiness")
            def __getattribute__(self, field):
                if field not in {"__class__"}:
                    raise RuntimeError("host controlled property")
                return super().__getattribute__(field)

        for sample in (object(), Hostile(), [], (), "GO", b"GO", 1, float("nan")):
            with self.subTest(sample=type(sample).__name__):
                self._assert_no_go(sample)

    def test_08_immutable_assessment_prevents_accidental_status_flip(self):
        result = self._assert_no_go({"ready": True})
        with self.assertRaises(FrozenInstanceError):
            result.authorizes_send = True
        with self.assertRaises(FrozenInstanceError):
            result.p0_homologated = 6

    def test_09_serialized_assessment_contains_no_positive_send_field(self):
        snapshot = self._assert_no_go({"receipt": "fake"}).as_dict()
        self.assertEqual(snapshot["p0_homologated"], 0)
        self.assertFalse(snapshot["authorizes_send"])
        self.assertFalse(snapshot["permits_deploy"])
        self.assertEqual(len(snapshot["missing_p0"]), 6)

    def test_10_concurrent_claims_cannot_flip_offline_status(self):
        with ThreadPoolExecutor(max_workers=12) as pool:
            values = list(pool.map(
                lambda i: assess_offline_claims({
                    "verified": i % 2 == 0, "p0_complete": 6,
                    "authorizes_send": True,
                }), range(90),
            ))
        self.assertEqual(len(values), 90)
        self.assertTrue(all(v.authorizes_send is False for v in values))
        self.assertTrue(all(v.p0_homologated == 0 for v in values))

    def test_11_outbox_default_guard_denies_without_witness(self):
        result, sends, effects = _attempt(None)
        self.assertEqual((result["state"], sends, effects), ("UNCERTAIN", 0, 0))

    def test_12_offline_assessment_callback_denies_real_dispatch(self):
        result, sends, effects = _attempt(
            lambda intent: assess_offline_claims(intent).authorizes_send
        )
        self.assertEqual((result["state"], sends, effects), ("UNCERTAIN", 0, 0))

    def test_13_production_outbox_rejects_caller_true_callback(self):
        """A259 migrates unsafe callback to explicit labs-only test fixture."""
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from aion_chat.models import Scope
        from aion_chat.store import SQLiteChatStore
        from atlasquant_aion_execution_outbox import ExecutionOutbox
        with TemporaryDirectory(prefix="a259-prod-reject-") as tmp:
            store = SQLiteChatStore(Path(tmp) / "outbox.db")
            try:
                with self.assertRaises(TypeError):
                    ExecutionOutbox(
                        store, Scope("owner-a258", "tenant-a258", "workspace-a258"),
                        first_attempt_guard=lambda intent: True,
                    )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
