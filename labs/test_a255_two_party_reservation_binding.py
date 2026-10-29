"""A255: signed event + signed first-attempt response (two host-pinned LAB roots)."""
import base64
from datetime import timedelta
from hashlib import sha256
import unittest
from concurrent.futures import ThreadPoolExecutor

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from labs.a254_synthetic_origin_event_identity import EFFECT_DOMAIN, canonical_bytes
from labs.a255_two_party_reservation_binding import (
    DOMAIN, SCHEMA, SyntheticTwoPartyReservationLab,
)
from labs.test_a243_signed_first_attempt import _attempt
from labs.test_a254_synthetic_origin_event_identity import (
    NOW, GOOD, ATTACKER, ISSUER, KEY_ID, _decision, _envelope, _pub,
)


WITNESS = Ed25519PrivateKey.from_private_bytes(b"\x23" * 32)
FAKE_WITNESS = Ed25519PrivateKey.from_private_bytes(b"\x24" * 32)
WITNESS_ISSUER = "synthetic-a255-independent-label-only"
WITNESS_KEY_ID = "synthetic-a255-witness-key"
CHALLENGE = "a" * 64


def _effect(origin):
    event = origin["payload"]
    return sha256(EFFECT_DOMAIN + canonical_bytes({
        "issuer": event["issuer"], "event_id": event["event_id"],
        **{key: event[key] for key in (
            "owner_id", "tenant_id", "workspace_id",
            "action", "aggregate_key", "payload_digest",
        )}
    })).hexdigest()


def _witness_receipt(
    origin, *, seq=1, signer=WITNESS, nonce=CHALLENGE, **changes
):
    payload = {
        "schema": SCHEMA, "status": "RESERVED",
        "issuer": WITNESS_ISSUER, "key_id": WITNESS_KEY_ID,
        "challenge": nonce, "event_id": origin["payload"]["event_id"],
        "origin_envelope_sha256": sha256(canonical_bytes(origin)).hexdigest(),
        "event_effect_digest": _effect(origin),
        "owner_id": origin["payload"]["owner_id"],
        "tenant_id": origin["payload"]["tenant_id"],
        "workspace_id": origin["payload"]["workspace_id"],
        "sequence": seq,
        "issued_at": (NOW - timedelta(seconds=2)).isoformat(),
        "expires_at": (NOW + timedelta(seconds=30)).isoformat(),
    }
    payload.update(changes)
    return {
        "payload": payload,
        "signature": base64.b64encode(
            signer.sign(DOMAIN + canonical_bytes(payload))
        ).decode("ascii"),
    }


def _bridge(*, origin_public=None, witness_public=None, high_water=0):
    return SyntheticTwoPartyReservationLab(
        origin_issuer=ISSUER, origin_key_id=KEY_ID,
        origin_public_key=origin_public or _pub(GOOD),
        witness_issuer=WITNESS_ISSUER, witness_key_id=WITNESS_KEY_ID,
        witness_public_key=witness_public or _pub(WITNESS),
        now=NOW, high_water=high_water,
    )


class A255TwoPartyBindingTests(unittest.TestCase):
    def test_01_two_valid_signatures_match_but_never_authorize_send(self):
        d = _decision()
        o = _envelope(d, "a255-e1")
        result = _bridge().review(d, o, _witness_receipt(o), expected_challenge=CHALLENGE)
        self.assertEqual(result["status"], "LAB_TWO_SIGNATURES_MATCHED_ONLY")
        self.assertIs(result["linked_format_valid"], True)
        self.assertIs(result["authorizes_send"], False)
        self.assertIs(result["independent_origin_proven"], False)
        self.assertIs(result["independent_witness_proven"], False)
        self.assertEqual(result["p0_homologated"], 0)

    def test_02_distinct_events_same_payload_get_distinct_reservations(self):
        d = _decision()
        bridge = _bridge()
        o1 = _envelope(d, "business-a")
        o2 = _envelope(d, "business-b")
        a = bridge.review(d, o1, _witness_receipt(o1, seq=1), expected_challenge=CHALLENGE)
        b = bridge.review(d, o2, _witness_receipt(o2, seq=2), expected_challenge=CHALLENGE)
        self.assertTrue(a["linked_format_valid"])
        self.assertTrue(b["linked_format_valid"])
        self.assertFalse(a["authorizes_send"] or b["authorizes_send"])

    def test_03_same_business_event_new_request_id_denied(self):
        bridge = _bridge()
        o = _envelope(_decision(), "same-event")
        a = bridge.review(_decision(intent_ref="one"), o, _witness_receipt(o, seq=1),
                          expected_challenge=CHALLENGE)
        b = bridge.review(_decision(intent_ref="two"), o, _witness_receipt(o, seq=2),
                          expected_challenge=CHALLENGE)
        self.assertTrue(a["linked_format_valid"])
        self.assertEqual(b["status"], "DENY_ORIGIN_EVENT_OR_REPLAY")

    def test_04_wrong_origin_signature_denied(self):
        d = _decision()
        o = _envelope(d, "wrong-origin", signer=ATTACKER)
        self.assertFalse(_bridge().review(
            d, o, _witness_receipt(o), expected_challenge=CHALLENGE
        )["linked_format_valid"])

    def test_05_wrong_witness_signature_denied(self):
        d = _decision()
        o = _envelope(d, "wrong-witness")
        self.assertFalse(_bridge().review(
            d, o, _witness_receipt(o, signer=FAKE_WITNESS),
            expected_challenge=CHALLENGE,
        )["linked_format_valid"])

    def test_06_wrong_effect_digest_even_signed_denied(self):
        d = _decision()
        o = _envelope(d, "wrong-effect")
        result = _bridge().review(d, o, _witness_receipt(
            o, event_effect_digest="b" * 64
        ), expected_challenge=CHALLENGE)
        self.assertEqual(result["status"], "DENY_EFFECT_DIGEST_MISMATCH")

    def test_07_signed_scope_or_event_mismatch_denied(self):
        d = _decision()
        o = _envelope(d, "scope-check")
        for k, v in (("owner_id", "attacker"), ("tenant_id", "attacker"),
                     ("workspace_id", "attacker"), ("event_id", "another-event")):
            with self.subTest(k=k):
                result = _bridge().review(
                    d, o, _witness_receipt(o, **{k: v}), expected_challenge=CHALLENGE,
                )
                self.assertEqual(result["status"], "DENY_EVENT_OR_SCOPE_MISMATCH")

    def test_08_challenge_mismatch_and_malformed_nonce_denied(self):
        d = _decision()
        o = _envelope(d, "nonce")
        self.assertEqual(
            _bridge().review(d, o, _witness_receipt(o, nonce="b" * 64),
                             expected_challenge=CHALLENGE)["status"],
            "DENY_WITNESS_IDENTITY_OR_CHALLENGE",
        )
        self.assertEqual(
            _bridge().review(d, o, _witness_receipt(o),
                             expected_challenge="NOT_256BIT_NONCE")["status"],
            "DENY_CHALLENGE",
        )

    def test_09_replay_of_witness_envelope_bound_to_other_origin_denied(self):
        d = _decision()
        o = _envelope(d, "origin-a")
        other = _envelope(d, "origin-b")
        self.assertEqual(_bridge().review(
            d, other, _witness_receipt(o), expected_challenge=CHALLENGE
        )["status"], "DENY_ORIGIN_ENVELOPE_MISMATCH")

    def test_10_bool_or_nonincreasing_sequence_denied(self):
        d = _decision()
        o = _envelope(d, "seq")
        self.assertEqual(_bridge().review(
            d, o, _witness_receipt(o, seq=True), expected_challenge=CHALLENGE
        )["status"], "DENY_SEQUENCE")
        self.assertEqual(_bridge(high_water=5).review(
            d, o, _witness_receipt(o, seq=5), expected_challenge=CHALLENGE
        )["status"], "DENY_STALE_WITNESS_SEQUENCE")

    def test_11_expired_and_future_witness_receipts_denied(self):
        d = _decision()
        o = _envelope(d, "time")
        for changed in (
            {"expires_at": (NOW - timedelta(seconds=1)).isoformat()},
            {"issued_at": (NOW + timedelta(seconds=1)).isoformat()},
            {"expires_at": (NOW + timedelta(days=1)).isoformat()},
        ):
            with self.subTest(change=changed):
                self.assertEqual(_bridge().review(
                    d, o, _witness_receipt(o, **changed),
                    expected_challenge=CHALLENGE,
                )["status"], "DENY_WITNESS_TIME")

    def test_12_extra_fields_malformed_signature_and_missing_reply_denied(self):
        d = _decision()
        o = _envelope(d, "malformed")
        valid = _witness_receipt(o)
        for env in (
            None, {}, {"payload": valid["payload"]},
            {"payload": {**valid["payload"], "authority_verified": True},
             "signature": valid["signature"]},
            {"payload": valid["payload"], "signature": "***"},
        ):
            with self.subTest(envelope=str(env)[:40]):
                result = _bridge().review(
                    d, o, env, expected_challenge=CHALLENGE,
                )
                self.assertFalse(result["linked_format_valid"])
                self.assertFalse(result["authorizes_send"])

    def test_13_identical_signers_or_labels_rejected_at_creation(self):
        with self.assertRaises(ValueError):
            _bridge(witness_public=_pub(GOOD))
        with self.assertRaises(ValueError):
            SyntheticTwoPartyReservationLab(
                origin_issuer=ISSUER, origin_key_id=KEY_ID,
                origin_public_key=_pub(GOOD),
                witness_issuer=ISSUER, witness_key_id="distinct-label",
                witness_public_key=_pub(WITNESS), now=NOW,
            )

    def test_14_lost_witness_ack_consumes_no_positive_authorization(self):
        d = _decision()
        o = _envelope(d, "ack-lost")
        result = _bridge().review(d, o, None, expected_challenge=CHALLENGE)
        self.assertFalse(result["linked_format_valid"])
        self.assertFalse(result["authorizes_send"])

    def test_15_outbox_never_sends_on_structurally_valid_two_party_claim(self):
        verifier = _bridge()

        def structural_guard(intent):
            decision = intent["decision"]
            o = _envelope(decision, "a255-during-dispatch")
            result = verifier.review(decision, o, _witness_receipt(o),
                                     expected_challenge=CHALLENGE)
            self.assertTrue(result["linked_format_valid"])
            return result["authorizes_send"]

        result, sends, effects = _attempt(structural_guard)
        self.assertEqual((result["state"], sends, effects), ("UNCERTAIN", 0, 0))

    def test_16_concurrent_same_event_has_at_most_one_format_match(self):
        d = _decision()
        o = _envelope(d, "parallel")
        w = _witness_receipt(o)
        verifier = _bridge()
        with ThreadPoolExecutor(max_workers=8) as pool:
            answers = list(pool.map(
                lambda _: verifier.review(d, o, w, expected_challenge=CHALLENGE),
                range(48),
            ))
        self.assertEqual(sum(v["linked_format_valid"] for v in answers), 1)
        self.assertTrue(all(v["authorizes_send"] is False for v in answers))

    @unittest.expectedFailure
    def test_17_red_two_host_controlled_keys_are_not_independent(self):
        # Both synthetic public-key pins may be swapped by one attacker.
        d = _decision()
        forged_origin = _envelope(d, "forged", signer=ATTACKER)
        forged_witness = _witness_receipt(
            forged_origin, signer=FAKE_WITNESS,
        )
        result = _bridge(origin_public=_pub(ATTACKER), witness_public=_pub(FAKE_WITNESS)).review(
            d, forged_origin, forged_witness, expected_challenge=CHALLENGE,
        )
        # Desired: refuse structurally valid but attacker-controlled pins.
        self.assertFalse(result["linked_format_valid"])

    @unittest.expectedFailure
    def test_18_red_host_rollback_of_both_ledgers_accepts_replay(self):
        d = _decision()
        o = _envelope(d, "restored-origin")
        w = _witness_receipt(o, seq=1)
        first = _bridge()
        self.assertTrue(first.review(d, o, w, expected_challenge=CHALLENGE)["linked_format_valid"])
        rolled_back = _bridge(high_water=0)  # host resets both memories
        self.assertFalse(rolled_back.review(
            d, o, w, expected_challenge=CHALLENGE,
        )["linked_format_valid"])


if __name__ == "__main__":
    unittest.main()
