"""A257 LAB — actual elapsed nonce TTL and pre-issue origin signature gate.

A deterministic injected clock is still under HOST control. No external time,
origin custody, antirollback, Worker, credential or real provider action.
"""
from datetime import timedelta
import math
import unittest

from labs.a256_one_time_challenge_lab import SyntheticOneTimeChallengeLab
from labs.test_a243_signed_first_attempt import _attempt
from labs.test_a254_synthetic_origin_event_identity import (
    NOW, GOOD, ATTACKER, ISSUER, KEY_ID, _decision, _envelope, _pub,
)
from labs.test_a255_two_party_reservation_binding import (
    WITNESS, WITNESS_ISSUER, WITNESS_KEY_ID, _witness_receipt,
)


class FakeMonotonicClock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value


def _lab(tick, *, ttl_seconds=60):
    return SyntheticOneTimeChallengeLab(
        origin_issuer=ISSUER, origin_key_id=KEY_ID,
        origin_public_key=_pub(GOOD),
        witness_issuer=WITNESS_ISSUER, witness_key_id=WITNESS_KEY_ID,
        witness_public_key=_pub(WITNESS), now=NOW,
        ttl_seconds=ttl_seconds, monotonic_clock=tick,
    )


def _issue(lab, d, origin):
    result = lab.begin(d, origin)
    assert result["challenge"], result
    return result["challenge"]


def _review(lab, d, origin, challenge, **options):
    return lab.review(
        d, origin, _witness_receipt(origin, nonce=challenge),
        challenge=challenge, **options,
    )


class A257MonotonicChallengeTests(unittest.TestCase):
    def test_01_challenge_expires_without_caller_observed_at(self):
        tick, d = FakeMonotonicClock(), _decision()
        event = _envelope(d, "a257-elapsed-ttl")
        lab = _lab(tick)
        challenge = _issue(lab, d, event)
        tick.value += 61
        result = _review(lab, d, event, challenge)
        self.assertEqual(result["status"], "DENY_EXPIRED_CHALLENGE")
        self.assertFalse(result["authorizes_send"])
        self.assertEqual(_review(lab, d, event, challenge)["status"],
                         "DENY_CHALLENGE_ALREADY_CONSUMED")

    def test_02_monotonic_window_accepts_formatted_signatures_never_sends(self):
        tick, d = FakeMonotonicClock(), _decision()
        origin = _envelope(d, "a257-in-time")
        lab = _lab(tick)
        c = _issue(lab, d, origin)
        tick.value += 12
        result = _review(lab, d, origin, c)
        self.assertTrue(result["linked_format_valid"])
        self.assertFalse(result["authorizes_send"])
        self.assertFalse(result["independent_challenge_proven"])

    def test_03_witness_expiration_observed_even_when_nonce_ttl_not_elapsed(self):
        tick, d = FakeMonotonicClock(), _decision()
        origin = _envelope(d, "a257-witness-expiry")
        lab = _lab(tick)
        c = _issue(lab, d, origin)
        tick.value += 35  # signed witness expires at NOW + 30 sec
        result = _review(lab, d, origin, c)
        self.assertEqual(result["status"], "DENY_WITNESS_TIME_ELAPSED")
        self.assertFalse(result["authorizes_send"])

    def test_04_forged_reported_clock_cannot_bypass_monotonic_timeout(self):
        tick, d = FakeMonotonicClock(), _decision()
        origin = _envelope(d, "a257-wall-override")
        lab = _lab(tick, ttl_seconds=20)
        c = _issue(lab, d, origin)
        tick.value += 21
        result = _review(lab, d, origin, c, observed_at=NOW)
        self.assertEqual(result["status"], "DENY_EXPIRED_CHALLENGE")

    def test_05_wrong_origin_signature_cannot_burn_event_or_get_nonce(self):
        tick, d = FakeMonotonicClock(), _decision()
        lab = _lab(tick)
        forged = _envelope(d, "a257-forged", signer=ATTACKER)
        refused = lab.begin(d, forged)
        self.assertEqual(refused["status"], "DENY_UNVERIFIED_OR_EXPIRED_ORIGIN")
        self.assertIsNone(refused["challenge"])
        # A later correctly signed origin for SAME event ID remains eligible:
        authentic = _envelope(d, "a257-forged")
        self.assertIsNotNone(lab.begin(d, authentic)["challenge"])

    def test_06_host_pinned_origin_issuer_and_key_id_must_match(self):
        d = _decision()
        for field, value in (("issuer", "foreign"), ("key_id", "not-the-pin")):
            with self.subTest(field=field):
                tick = FakeMonotonicClock()
                origin = _envelope(d, "a257-pin", **{field: value})
                result = _lab(tick).begin(d, origin)
                self.assertEqual(result["status"], "DENY_UNVERIFIED_OR_EXPIRED_ORIGIN")
                self.assertIsNone(result["challenge"])

    def test_07_expired_or_future_origin_never_gets_challenge(self):
        d = _decision()
        for time_fields in (
            {"expires_at": (NOW - timedelta(seconds=1)).isoformat()},
            {"issued_at": (NOW + timedelta(seconds=1)).isoformat()},
            {"expires_at": (NOW + timedelta(days=1)).isoformat()},
        ):
            with self.subTest(fields=time_fields):
                event = _envelope(d, "a257-expired", **time_fields)
                result = _lab(FakeMonotonicClock()).begin(d, event)
                self.assertEqual(result["status"], "DENY_UNVERIFIED_OR_EXPIRED_ORIGIN")

    def test_08_monotonic_clock_rollback_consumes_nonce_and_poison_future(self):
        tick, d = FakeMonotonicClock(2000), _decision()
        event = _envelope(d, "a257-clock-rollback")
        lab = _lab(tick)
        c = _issue(lab, d, event)
        tick.value = 1990
        first = _review(lab, d, event, c)
        self.assertEqual(first["status"], "DENY_LOCAL_CLOCK_UNSAFE")
        self.assertEqual(_review(lab, d, event, c)["status"],
                         "DENY_CHALLENGE_ALREADY_CONSUMED")
        tick.value = 2200
        later = lab.begin(d, _envelope(d, "a257-clock-rollback-other"))
        self.assertEqual(later["status"], "DENY_LOCAL_CLOCK_UNSAFE")
        self.assertFalse(later["authorizes_send"])

    def test_09_nonfinite_clock_denied_not_accepted_as_unbounded_time(self):
        for bad in (float("nan"), float("inf"), -1.0, True, "1000"):
            with self.subTest(value=str(bad)):
                d = _decision()
                tick = FakeMonotonicClock(bad)
                event = _envelope(d, "a257-invalid-clock")
                lab = _lab(tick)
                self.assertEqual(lab.begin(d, event)["status"], "DENY_LOCAL_CLOCK_UNSAFE")

    def test_10_nonfinite_clock_during_review_burns_nonce(self):
        tick, d = FakeMonotonicClock(), _decision()
        o = _envelope(d, "a257-invalid-review")
        lab = _lab(tick)
        c = _issue(lab, d, o)
        tick.value = math.nan
        self.assertEqual(_review(lab, d, o, c)["status"], "DENY_LOCAL_CLOCK_UNSAFE")
        tick.value = 2000
        self.assertEqual(_review(lab, d, o, c)["status"],
                         "DENY_CHALLENGE_ALREADY_CONSUMED")

    def test_11_origin_expires_before_second_issue_on_advancing_host_time(self):
        tick, d = FakeMonotonicClock(), _decision()
        lab = _lab(tick)
        first = _envelope(d, "a257-first")
        self.assertIsNotNone(lab.begin(d, first)["challenge"])
        tick.value += 45  # origin signed until NOW + 40 seconds
        second = _envelope(d, "a257-second")
        result = lab.begin(d, second)
        self.assertEqual(result["status"], "DENY_UNVERIFIED_OR_EXPIRED_ORIGIN")

    def test_12_reported_timestamp_moving_backward_adds_denial(self):
        tick, d = FakeMonotonicClock(), _decision()
        origin = _envelope(d, "a257-observed-backward")
        lab = _lab(tick)
        c = _issue(lab, d, origin)
        tick.value += 1
        self.assertEqual(_review(
            lab, d, origin, c, observed_at=NOW - timedelta(seconds=1)
        )["status"], "DENY_EXPIRED_CHALLENGE")

    def test_13_new_challenge_may_be_issued_to_distinct_signed_event(self):
        tick, d = FakeMonotonicClock(), _decision()
        lab = _lab(tick)
        first, second = _envelope(d, "a257-one"), _envelope(d, "a257-two")
        c1 = _issue(lab, d, first)
        self.assertTrue(_review(lab, d, first, c1)["linked_format_valid"])
        tick.value += 1
        c2 = _issue(lab, d, second)
        self.assertNotEqual(c1, c2)
        self.assertFalse(_review(lab, d, second, c2)["authorizes_send"])

    def test_14_outbox_never_sends_even_with_in_window_challenge(self):
        tick = FakeMonotonicClock()
        lab = _lab(tick)
        def denied(intent):
            d = intent["decision"]
            o = _envelope(d, "a257-outbox-format-only")
            c = _issue(lab, d, o)
            return _review(lab, d, o, c)["authorizes_send"]
        status, sends, effects = _attempt(denied)
        self.assertEqual((status["state"], sends, effects), ("UNCERTAIN", 0, 0))

    @unittest.expectedFailure
    def test_15_red_host_clock_freeze_can_fake_elapsed_time(self):
        d, tick = _decision(), FakeMonotonicClock()
        lab = _lab(tick, ttl_seconds=1)
        o = _envelope(d, "a257-host-freeze")
        c = _issue(lab, d, o)
        # A hostile host can return a frozen monotonic tick forever; there
        # is no independently attested time source. Desired is denial.
        self.assertFalse(_review(lab, d, o, c)["linked_format_valid"])


if __name__ == "__main__":
    unittest.main()
