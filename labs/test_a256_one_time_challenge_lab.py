"""A256 LAB: event-bound one-use nonce and honest host rollback limitations."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest import mock
import unittest

from labs.a256_one_time_challenge_lab import SyntheticOneTimeChallengeLab
from labs.test_a243_signed_first_attempt import _attempt
from labs.test_a254_synthetic_origin_event_identity import (
    NOW, GOOD, ATTACKER, ISSUER, KEY_ID, _decision, _envelope, _pub,
)
from labs.test_a255_two_party_reservation_binding import (
    WITNESS, FAKE_WITNESS, WITNESS_ISSUER, WITNESS_KEY_ID,
    _witness_receipt,
)


def _lab(*, origin_public=None, witness_public=None, ttl_seconds=60):
    return SyntheticOneTimeChallengeLab(
        origin_issuer=ISSUER, origin_key_id=KEY_ID,
        origin_public_key=origin_public or _pub(GOOD),
        witness_issuer=WITNESS_ISSUER, witness_key_id=WITNESS_KEY_ID,
        witness_public_key=witness_public or _pub(WITNESS),
        now=NOW, ttl_seconds=ttl_seconds,
    )


def _begin(lab, d, origin):
    record = lab.begin(d, origin)
    assert record["challenge"] is not None, record
    return record["challenge"]


def _finish(lab, d, origin, challenge, **kwargs):
    return lab.review(
        d, origin, _witness_receipt(origin, nonce=challenge),
        challenge=challenge, **kwargs,
    )


class A256OneTimeChallengeTests(unittest.TestCase):
    def test_01_fresh_nonce_two_signatures_are_still_not_authority(self):
        d = _decision()
        o = _envelope(d, "a256-normal")
        lab = _lab()
        challenge = _begin(lab, d, o)
        self.assertEqual(len(challenge), 64)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in challenge))
        result = _finish(lab, d, o, challenge)
        self.assertEqual(result["status"], "LAB_TWO_SIGNATURES_MATCHED_ONLY")
        self.assertTrue(result["linked_format_valid"])
        self.assertIs(result["authorizes_send"], False)
        self.assertIs(result["independent_challenge_proven"], False)
        self.assertEqual(result["p0_homologated"], 0)

    def test_02_two_distinct_events_same_payload_get_distinct_challenges(self):
        d = _decision()
        lab = _lab()
        a, b = _envelope(d, "event-A"), _envelope(d, "event-B")
        ca, cb = _begin(lab, d, a), _begin(lab, d, b)
        self.assertNotEqual(ca, cb)
        self.assertTrue(_finish(lab, d, a, ca)["linked_format_valid"])
        receipt_b = _witness_receipt(b, seq=2, nonce=cb)
        self.assertTrue(lab.review(d, b, receipt_b, challenge=cb)["linked_format_valid"])

    def test_03_same_event_with_new_request_id_cannot_get_new_challenge(self):
        d = _decision(intent_ref="request-one")
        o = _envelope(d, "event-repeat")
        lab = _lab()
        c = _begin(lab, d, o)
        another = lab.begin(_decision(intent_ref="request-two"), o)
        self.assertEqual(another["status"], "DENY_EVENT_ALREADY_SEEN_OR_PENDING")
        self.assertIsNone(another["challenge"])
        self.assertTrue(_finish(lab, d, o, c)["linked_format_valid"])

    def test_04_bad_witness_signature_consumes_nonce_even_if_later_valid(self):
        d = _decision()
        o = _envelope(d, "bad-signature")
        lab = _lab()
        c = _begin(lab, d, o)
        bad = lab.review(
            d, o, _witness_receipt(o, nonce=c, signer=FAKE_WITNESS),
            challenge=c,
        )
        self.assertFalse(bad["linked_format_valid"])
        self.assertEqual(_finish(lab, d, o, c)["status"], "DENY_CHALLENGE_ALREADY_CONSUMED")
        self.assertEqual(lab.begin(d, o)["status"], "DENY_EVENT_ALREADY_SEEN_OR_PENDING")

    def test_05_wrong_event_cannot_borrow_challenge_and_burns_it(self):
        d = _decision()
        a, b = _envelope(d, "bound-A"), _envelope(d, "bound-B")
        lab = _lab()
        c = _begin(lab, d, a)
        result = lab.review(d, b, _witness_receipt(a, nonce=c), challenge=c)
        self.assertEqual(result["status"], "DENY_CHALLENGE_EVENT_MISMATCH")
        self.assertEqual(_finish(lab, d, a, c)["status"], "DENY_CHALLENGE_ALREADY_CONSUMED")

    def test_06_lost_ack_consumes_challenge_without_reissue(self):
        d, lab = _decision(), _lab()
        o = _envelope(d, "lost-ack")
        c = _begin(lab, d, o)
        result = lab.review(d, o, None, challenge=c)
        self.assertFalse(result["authorizes_send"])
        self.assertFalse(result["linked_format_valid"])
        self.assertEqual(_finish(lab, d, o, c)["status"], "DENY_CHALLENGE_ALREADY_CONSUMED")
        self.assertIsNone(lab.begin(d, o)["challenge"])

    def test_07_late_witness_response_is_denied_and_consumed(self):
        d = _decision()
        o = _envelope(d, "expired")
        lab = _lab(ttl_seconds=20)
        c = _begin(lab, d, o)
        late = _finish(lab, d, o, c, observed_at=NOW + timedelta(seconds=21))
        self.assertEqual(late["status"], "DENY_EXPIRED_CHALLENGE")
        self.assertFalse(late["authorizes_send"])
        self.assertEqual(_finish(lab, d, o, c)["status"], "DENY_CHALLENGE_ALREADY_CONSUMED")

    def test_08_clock_moved_backwards_is_denied(self):
        d = _decision()
        o = _envelope(d, "clock-back")
        lab = _lab()
        c = _begin(lab, d, o)
        result = _finish(lab, d, o, c, observed_at=NOW - timedelta(seconds=2))
        self.assertEqual(result["status"], "DENY_EXPIRED_CHALLENGE")

    def test_09_rng_nonce_collision_does_not_overwrite_first_record(self):
        d = _decision()
        a, b = _envelope(d, "collision-a"), _envelope(d, "collision-b")
        lab = _lab()
        with mock.patch(
            "labs.a256_one_time_challenge_lab.secrets.token_hex",
            return_value="f" * 64,
        ):
            ca = _begin(lab, d, a)
            denied = lab.begin(d, b)
        self.assertEqual(denied["status"], "DENY_CHALLENGE_COLLISION")
        self.assertIsNone(denied["challenge"])
        self.assertTrue(_finish(lab, d, a, ca)["linked_format_valid"])

    def test_10_malformed_origin_or_decision_never_issues_challenge(self):
        d = _decision()
        o = _envelope(d, "valid-structure")
        for dec, env in (
            (None, o),
            ({**d, "tenant_id": "foreign"}, o),
            (d, {}),
            (d, {**o, "trusted": True}),
            (d, {"payload": {**o["payload"], "event_id": "../evil"},
                 "signature": o["signature"]}),
            (d, {"payload": {**o["payload"], "trusted": True},
                 "signature": o["signature"]}),
        ):
            with self.subTest(variant=str(dec)[:10]):
                result = _lab().begin(dec, env)
                self.assertFalse(result["authorizes_send"])
                self.assertIsNone(result["challenge"])

    def test_11_unknown_nonce_is_not_treated_as_issued(self):
        d, lab = _decision(), _lab()
        o = _envelope(d, "unknown")
        result = lab.review(
            d, o, _witness_receipt(o, nonce="b" * 64),
            challenge="b" * 64,
        )
        self.assertEqual(result["status"], "DENY_UNKNOWN_CHALLENGE")
        self.assertIs(result["authorizes_send"], False)

    def test_12_wrong_nonce_in_witness_envelope_burns_local_challenge(self):
        d, lab = _decision(), _lab()
        o = _envelope(d, "wrong-nonce")
        c = _begin(lab, d, o)
        result = lab.review(
            d, o, _witness_receipt(o, nonce="d" * 64), challenge=c,
        )
        self.assertEqual(result["status"], "DENY_WITNESS_IDENTITY_OR_CHALLENGE")
        self.assertEqual(_finish(lab, d, o, c)["status"], "DENY_CHALLENGE_ALREADY_CONSUMED")

    def test_13_decision_request_ref_may_change_but_semantics_cannot(self):
        d = _decision(intent_ref="request-1")
        o = _envelope(d, "same-event")
        lab = _lab()
        c = _begin(lab, d, o)
        d2 = _decision(intent_ref="request-2")
        self.assertTrue(_finish(lab, d2, o, c)["linked_format_valid"])
        altered = _decision(payload="different")
        o2 = _envelope(altered, "new-event")
        c2 = _begin(lab, altered, o2)
        mismatch = _finish(lab, d, o2, c2)
        self.assertEqual(mismatch["status"], "DENY_CHALLENGE_EVENT_MISMATCH")

    def test_14_concurrent_delivery_accepts_at_most_one_reply(self):
        d = _decision()
        o = _envelope(d, "parallel-delivery")
        lab = _lab()
        c = _begin(lab, d, o)
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(lambda _: _finish(lab, d, o, c), range(64)))
        self.assertEqual(sum(x["linked_format_valid"] is True for x in results), 1)
        self.assertEqual(sum(x["status"] == "DENY_CHALLENGE_ALREADY_CONSUMED" for x in results), 63)
        self.assertTrue(all(x["authorizes_send"] is False for x in results))

    def test_15_outbox_never_sends_after_valid_nonce_and_two_signatures(self):
        lab = _lab()
        def guarded(intent):
            decision = intent["decision"]
            o = _envelope(decision, "outbox-unsigned-authority")
            c = _begin(lab, decision, o)
            result = _finish(lab, decision, o, c)
            self.assertTrue(result["linked_format_valid"])
            return result["authorizes_send"]
        status, send_calls, effects = _attempt(guarded)
        self.assertEqual((status["state"], send_calls, effects), ("UNCERTAIN", 0, 0))

    def test_16_reusing_consumed_nonce_after_success_is_denied(self):
        d, lab = _decision(), _lab()
        o = _envelope(d, "replay")
        c = _begin(lab, d, o)
        self.assertTrue(_finish(lab, d, o, c)["linked_format_valid"])
        self.assertEqual(_finish(lab, d, o, c)["status"], "DENY_CHALLENGE_ALREADY_CONSUMED")
        self.assertFalse(_finish(lab, d, o, c)["authorizes_send"])

    @unittest.expectedFailure
    def test_17_red_host_restart_forgets_spent_event_and_nonce_history(self):
        d = _decision()
        o = _envelope(d, "restored")
        first = _lab()
        c = _begin(first, d, o)
        self.assertTrue(_finish(first, d, o, c)["linked_format_valid"])
        second = _lab()  # intentionally loses host-only state
        # Desired: independently monotonic history denies reissuance.
        self.assertIsNone(second.begin(d, o)["challenge"])

    @unittest.expectedFailure
    def test_18_red_host_repins_both_attacker_keys_as_valid_signers(self):
        d = _decision()
        o = _envelope(d, "host-forgery", signer=ATTACKER)
        lab = _lab(origin_public=_pub(ATTACKER), witness_public=_pub(FAKE_WITNESS))
        c = _begin(lab, d, o)
        forged_receipt = _witness_receipt(o, nonce=c, signer=FAKE_WITNESS)
        result = lab.review(d, o, forged_receipt, challenge=c)
        # Desired: prove signer independence outside host; not available.
        self.assertFalse(result["linked_format_valid"])


if __name__ == "__main__":
    unittest.main()
