"""A254 synthetic signed event-ID P0-3 contract and honest red limits."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from labs.a254_synthetic_origin_event_identity import (
    DOMAIN, SCHEMA, SyntheticOriginEventRegistryLab, canonical_bytes,
)
from labs.test_a243_signed_first_attempt import _attempt


NOW = datetime(2026, 10, 29, 13, 0, tzinfo=timezone.utc)
ISSUER, KEY_ID = "a254-lab-origin", "a254-lab-key"
GOOD = Ed25519PrivateKey.from_private_bytes(b"\x21" * 32)
ATTACKER = Ed25519PrivateKey.from_private_bytes(b"\x22" * 32)


def _pub(private):
    return private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _decision(*, payload="identical", intent_ref="technical-request-1"):
    return {
        "owner_id": "owner-a254", "tenant_id": "tenant-a254",
        "workspace_id": "workspace-a254", "action": "test-effect",
        "aggregate_key": "aggregate-a", "payload_digest":
            sha256(payload.encode("utf-8")).hexdigest(),
        "intent_ref": intent_ref,
    }


def _envelope(decision, event_id, *, signer=GOOD, **tamper):
    event = {
        "schema": SCHEMA, "issuer": ISSUER, "key_id": KEY_ID,
        "event_id": event_id,
        "issued_at": (NOW - timedelta(seconds=10)).isoformat(),
        "expires_at": (NOW + timedelta(seconds=40)).isoformat(),
        **{name: decision[name] for name in (
            "owner_id", "tenant_id", "workspace_id", "action",
            "aggregate_key", "payload_digest",
        )},
    }
    event.update(tamper)
    sig = base64.b64encode(signer.sign(DOMAIN + canonical_bytes(event))).decode()
    return {"payload": event, "signature": sig}


def _registry(*, public=None):
    return SyntheticOriginEventRegistryLab(
        issuer=ISSUER, key_id=KEY_ID, public_key=public or _pub(GOOD),
        now=NOW,
    )


class A254SignedEventIdentityContractTests(unittest.TestCase):
    def test_01_valid_synthetic_origin_event_is_not_send_authority(self):
        d = _decision()
        result = _registry().review(d, _envelope(d, "business-event-1"))
        self.assertEqual(result["status"], "LAB_SIGNED_DISTINCT_EVENT")
        self.assertTrue(result["format_valid"])
        self.assertTrue(result["new_event"])
        self.assertEqual(len(result["event_effect_digest"]), 64)
        self.assertIs(result["authorizes_send"], False)
        self.assertIs(result["independent_origin_proven"], False)

    def test_02_distinct_signed_events_with_identical_payload_are_distinct(self):
        d = _decision()
        registry = _registry()
        a = registry.review(d, _envelope(d, "distinct-A"))
        b = registry.review(d, _envelope(d, "distinct-B"))
        self.assertTrue(a["new_event"])
        self.assertTrue(b["new_event"])
        self.assertNotEqual(a["event_effect_digest"], b["event_effect_digest"])
        self.assertFalse(a["authorizes_send"] or b["authorizes_send"])

    def test_03_same_signed_event_replayed_with_new_request_id_is_denied(self):
        registry = _registry()
        d = _decision(intent_ref="request-one")
        d2 = _decision(intent_ref="request-two")
        env = _envelope(d, "same-event")
        a = registry.review(d, env)
        b = registry.review(d2, env)
        self.assertTrue(a["new_event"])
        self.assertEqual(b["status"], "DENY_REPEATED_EVENT")
        self.assertIs(b["authorizes_send"], False)

    def test_04_same_event_id_altered_payload_denied_as_conflict(self):
        registry = _registry()
        a = _decision(payload="before")
        b = _decision(payload="after")
        self.assertTrue(registry.review(a, _envelope(a, "same-id"))["new_event"])
        rejected = registry.review(b, _envelope(b, "same-id"))
        self.assertEqual(rejected["status"], "DENY_EVENT_ID_PAYLOAD_CONFLICT")

    def test_05_wrong_signer_does_not_pass_fixed_lab_pin(self):
        d = _decision()
        result = _registry().review(d, _envelope(d, "A", signer=ATTACKER))
        self.assertFalse(result["format_valid"])
        self.assertIs(result["authorizes_send"], False)

    def test_06_wrong_tenant_action_or_digest_denied(self):
        d = _decision()
        for field, altered in (
            ("owner_id", "other-owner"), ("tenant_id", "other-tenant"),
            ("workspace_id", "other-workspace"), ("action", "other-action"),
            ("aggregate_key", "other-aggregate"),
            ("payload_digest", "f" * 64),
        ):
            with self.subTest(field=field):
                self.assertEqual(
                    _registry().review(
                        d, _envelope(d, "business-1", **{field: altered})
                    )["status"], "DENY_SCOPE_ACTION_OR_PAYLOAD_MISMATCH",
                )

    def test_07_invalid_origin_pins_and_signature_denied(self):
        d = _decision()
        for changed in (
            {"issuer": "different-issuer"},
            {"key_id": "different-key"},
            {"schema": "unknown-version"},
        ):
            with self.subTest(changed=changed):
                self.assertEqual(
                    _registry().review(d, _envelope(d, "id-1", **changed))["status"],
                    "DENY_ORIGIN_PIN",
                )
        envelope = _envelope(d, "id-1")
        envelope["signature"] = "****"
        self.assertFalse(_registry().review(d, envelope)["format_valid"])

    def test_08_bad_event_id_and_expired_oversized_ttl_denied(self):
        d = _decision()
        for invalid_id in ("", "../path", "with spaces", "a" * 129):
            with self.subTest(event=invalid_id):
                self.assertEqual(
                    _registry().review(d, _envelope(d, invalid_id))["status"],
                    "DENY_EVENT_ID",
                )
        self.assertEqual(
            _registry().review(
                d, _envelope(d, "expired", expires_at=(NOW - timedelta(seconds=1)).isoformat())
            )["status"], "DENY_EVENT_TIME",
        )
        self.assertEqual(
            _registry().review(
                d, _envelope(d, "long", expires_at=(NOW + timedelta(days=3)).isoformat())
            )["status"], "DENY_EVENT_TIME",
        )

    def test_09_strict_shape_and_malformed_inputs_never_authorize(self):
        d = _decision()
        cases = [
            None, {}, {"payload": {}, "signature": ""},
            {"payload": _envelope(d, "x")["payload"]},
            {"payload": [], "signature": b"abc"},
            {"payload": {**_envelope(d, "x")["payload"], "verified": True},
             "signature": _envelope(d, "x")["signature"]},
        ]
        for env in cases:
            with self.subTest(case=str(env)[:30]):
                result = _registry().review(d, env)
                self.assertFalse(result["authorizes_send"])
                self.assertFalse(result["independent_origin_proven"])

    def test_10_concurrent_same_event_is_locally_admitted_once(self):
        d = _decision()
        envelope = _envelope(d, "same-from-threads")
        registry = _registry()
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(
                lambda _: registry.review(d, envelope), range(60)
            ))
        self.assertEqual(sum(r["new_event"] is True for r in results), 1)
        self.assertEqual(
            sum(r["status"] == "DENY_REPEATED_EVENT" for r in results), 59
        )

    def test_11_integration_with_outbox_only_denies_real_send(self):
        # The synthetic format verifier is NOT a first-attempt authorization.
        # Even if a host manufactures a valid signature, it never grants SEND.
        registry = _registry()
        def no_send_guard(intent):
            d = intent["decision"]
            result = registry.review(d, _envelope(d, "event-during-dispatch"))
            return result["authorizes_send"]

        result, sends, effects = _attempt(no_send_guard)
        self.assertEqual((result["state"], sends, effects), ("UNCERTAIN", 0, 0))

    @unittest.expectedFailure
    def test_12_host_repinning_attacker_root_is_not_independent_provenance(self):
        d = _decision()
        env = _envelope(d, "attacker-event", signer=ATTACKER)
        # Desired: a host-controlled pin must not authenticate attacker origin.
        # Current synthetic verifier accepts the host-provided key as a format pin.
        self.assertFalse(_registry(public=_pub(ATTACKER)).review(d, env)["format_valid"])

    @unittest.expectedFailure
    def test_13_host_rollback_of_registry_is_not_independent_replay_proof(self):
        d = _decision()
        env = _envelope(d, "reused-event")
        first = _registry()
        self.assertTrue(first.review(d, env)["new_event"])
        # Restoring the host (or creating a new process) loses this in-memory
        # seen-set. A genuine independent monotonic origin is not present.
        restarted = _registry()
        self.assertFalse(restarted.review(d, env)["new_event"])


if __name__ == "__main__":
    unittest.main()
