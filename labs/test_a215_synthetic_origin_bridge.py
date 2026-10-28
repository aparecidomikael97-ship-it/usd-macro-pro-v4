"""A215 real SQLite Outbox + synthetic-only Ed25519 origin-bridge tests.

No provider, no independent key custody, no operator root, no real effects.
The synthetic signer is generated only within ephemeral test memory.
"""
import base64
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from datetime import timedelta
import json
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_external_evidence_intake import CANDIDATE_SCHEMA
from labs import test_a202_outbox_dispatch_atomic_cas as a202
from labs.a212_synthetic_signed_effect_preflight import SCHEMA, signing_message
from labs.a215_synthetic_origin_bridge import inspect_synthetic_origin_bridge
from labs.test_a213_outbox_untrusted_positive_hard_nogo import UntrustedPositive


class A215SyntheticOriginBridgeTests(unittest.TestCase):
    def setUp(self):
        self.helper = a202.A202SameLeaseOwnerDispatchRaceTests()
        self.signer = Ed25519PrivateKey.generate()
        self.pubkey = self.signer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.now = a202.NOW
        self.observed = self.now + timedelta(minutes=1)
        self.nonce = "d" * 64

    @contextmanager
    def fixture(self, send_mode="positive"):
        with tempfile.TemporaryDirectory() as root:
            _, store, outbox, key = self.helper.seed_claim(root)
            adapter = UntrustedPositive(send_mode)
            try:
                result = outbox.dispatch_claimed(
                    key, worker_id=a202.WORKER,
                    authorize=self.helper.authorize, adapter=adapter,
                    now=self.now,
                )
                self.assertIn(result["state"], {"UNCERTAIN", "SENT"})
                self.assertEqual(outbox.effect_count(), 0)
                yield store, outbox, key, adapter
            finally:
                store.close()

    def candidate(self, outbox, key):
        challenge = outbox.evidence_challenge(key)
        body = json.loads(challenge.challenge_json)
        body.pop("schema")
        return {
            "schema": CANDIDATE_SCHEMA,
            **body,
            "challenge_digest": challenge.challenge_digest,
            "provider_id": "synthetic-provider",
            "provider_event_id": "synthetic-event",
            "effect_ref": "synthetic-effect",
            "effect_state": "EFFECT_CONFIRMED",
            "provider_receipt_digest": "f" * 64,
            "witness_root_fingerprint": "a" * 64,
            "witness_checkpoint_hash": "b" * 64,
            "witness_sequence": 5,
            "occurred_at": self.now.isoformat(),
        }

    def sign(self, statement):
        signature = self.signer.sign(signing_message(statement))
        return {**statement, "signature_b64": base64.b64encode(signature).decode("ascii")}

    def receipt(self, candidate):
        statement = {
            "schema": SCHEMA,
            "owner_id": candidate["owner_id"],
            "tenant_id": candidate["tenant_id"],
            "workspace_id": candidate["workspace_id"],
            "operation_kind": candidate["action"].upper(),
            "intent_digest": candidate["challenge_digest"],
            "idempotency_key": candidate["idempotency_key"],
            "provider_id": candidate["provider_id"],
            "witness_root_id": candidate["witness_root_fingerprint"],
            "witness_checkpoint_hash": candidate["witness_checkpoint_hash"],
            "receipt_nonce_hex": self.nonce,
            "subject_digest": candidate["provider_receipt_digest"],
            "provider_event_id": candidate["provider_event_id"],
            "effect_ref": candidate["effect_ref"],
            "effect_state": candidate["effect_state"],
            "occurred_at": candidate["occurred_at"],
            "witness_sequence": candidate["witness_sequence"],
        }
        return self.sign(statement)

    def inspect(self, outbox, key, candidate, receipt, **overrides):
        params = dict(
            candidate_pubkey_bytes=self.pubkey,
            receipt_nonce_hex=self.nonce,
            observed_at=self.observed,
            last_witness_sequence=4,
            seen_provider_event_ids=[],
            seen_receipt_nonces=[],
        )
        params.update(overrides)
        return inspect_synthetic_origin_bridge(
            outbox.get(key), candidate, receipt, **params,
        )

    def assert_denied(self, outbox, key, candidate, receipt, code, **overrides):
        result = self.inspect(outbox, key, candidate, receipt, **overrides)
        self.assertEqual(result.code, code)
        self.assertFalse(result.may_confirm)
        self.assertFalse(result.independent_origin_verified)
        self.assertFalse(result.signature_math_valid)
        return result

    def test_01_all_crypto_math_and_local_binding_match_without_authority(self):
        with self.fixture() as (store, outbox, key, adapter):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            before = store.db.total_changes
            result = self.inspect(outbox, key, c, r)
            self.assertTrue(result.local_binding_ok)
            self.assertTrue(result.signature_math_valid)
            self.assertFalse(result.independent_origin_verified)
            self.assertFalse(result.may_confirm)
            self.assertEqual(
                result.code,
                "LOCAL_AND_SIGNATURE_MATH_MATCH_BUT_ORIGIN_AND_EFFECT_UNPROVEN",
            )
            self.assertEqual(result.challenge_digest, c["challenge_digest"])
            self.assertEqual(len(result.signed_statement_digest), 64)
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(store.db.total_changes, before)
            self.assertEqual(adapter.send_calls, 1)

    def test_02_sent_state_still_stays_sent_without_confirmation(self):
        with self.fixture("pending") as (store, outbox, key, adapter):
            self.assertEqual(outbox.get(key)["state"], "SENT")
            c = self.candidate(outbox, key)
            before = store.db.total_changes
            result = self.inspect(outbox, key, c, self.receipt(c))
            self.assertTrue(result.signature_math_valid)
            self.assertFalse(result.may_confirm)
            self.assertEqual(store.db.total_changes, before)
            self.assertEqual(outbox.get(key)["state"], "SENT")
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(adapter.send_calls, 1)

    def test_03_host_generated_key_still_no_independent_provenance(self):
        with self.fixture() as (_, outbox, key, _):
            candidate = self.candidate(outbox, key)
            receipt = self.receipt(candidate)
            result = self.inspect(outbox, key, candidate, receipt)
            self.assertTrue(result.signature_math_valid)
            self.assertFalse(result.independent_origin_verified)

    def test_04_wrong_signature_bytes_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            r["signature_b64"] = base64.b64encode(b"\x00" * 64).decode()
            self.assert_denied(
                outbox, key, c, r, "SYNTHETIC_SIGNATURE_SIGNATURE_MATH_NOT_VALID",
            )

    def test_05_wrong_valid_length_public_key_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            other = Ed25519PrivateKey.generate().public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            self.assert_denied(
                outbox, key, c, self.receipt(c),
                "SYNTHETIC_SIGNATURE_SIGNATURE_MATH_NOT_VALID",
                candidate_pubkey_bytes=other,
            )

    def test_06_forged_provider_event_conflict(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            r["provider_event_id"] = "synthetic-other-event"
            self.assert_denied(
                outbox, key, c, r, "SYNTHETIC_RECEIPT_CANDIDATE_CONFLICT",
            )

    def test_07_forged_effect_ref_conflict(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            r["effect_ref"] = "another-effect"
            self.assert_denied(
                outbox, key, c, r, "SYNTHETIC_RECEIPT_CANDIDATE_CONFLICT",
            )

    def test_08_nonconfirmed_receipt_conflict(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            r["effect_state"] = "PENDING"
            self.assert_denied(
                outbox, key, c, r, "SYNTHETIC_RECEIPT_CANDIDATE_CONFLICT",
            )

    def test_09_forged_witness_root_conflict(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            r["witness_root_id"] = "c" * 64
            self.assert_denied(
                outbox, key, c, r, "SYNTHETIC_ROOT_CLAIM_CONFLICT",
            )

    def test_10_forged_checkpoint_conflict(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            r["witness_checkpoint_hash"] = "c" * 64
            self.assert_denied(
                outbox, key, c, r, "SYNTHETIC_RECEIPT_CANDIDATE_CONFLICT",
            )

    def test_11_forged_witness_sequence_conflict(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            r["witness_sequence"] += 1
            self.assert_denied(
                outbox, key, c, r, "SYNTHETIC_RECEIPT_CANDIDATE_CONFLICT",
            )

    def test_12_forged_occurred_time_conflict(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            r["occurred_at"] = (self.now + timedelta(seconds=3)).isoformat()
            self.assert_denied(
                outbox, key, c, r, "SYNTHETIC_RECEIPT_CANDIDATE_CONFLICT",
            )

    def test_13_wrong_owner_in_local_claim_denied_before_crypto(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            c["owner_id"] = "intruder-owner"
            self.assert_denied(
                outbox, key, c, r,
                "LOCAL_BINDING_ORIGINAL_INTENT_OR_ATTEMPT_MISMATCH",
            )

    def test_14_wrong_local_challenge_digest_denied_before_crypto(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            c["challenge_digest"] = "0" * 64
            self.assert_denied(
                outbox, key, c, r, "LOCAL_BINDING_LOCAL_CHALLENGE_MISMATCH",
            )

    def test_15_self_asserted_external_verification_in_candidate_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            c["independently_verified"] = True
            self.assert_denied(
                outbox, key, c, r,
                "LOCAL_BINDING_CANDIDATE_ENVELOPE_NOT_EXACT",
            )

    def test_16_signed_receipt_extra_authority_field_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            r["independently_verified"] = True
            self.assert_denied(
                outbox, key, c, r,
                "SYNTHETIC_SIGNATURE_RECEIPT_ENVELOPE_NOT_EXACT",
            )

    def test_17_seen_provider_event_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            self.assert_denied(
                outbox, key, c, self.receipt(c),
                "SYNTHETIC_SIGNATURE_PROVIDER_EVENT_REPLAY",
                seen_provider_event_ids=["synthetic-event"],
            )

    def test_18_seen_receipt_nonce_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            self.assert_denied(
                outbox, key, c, self.receipt(c),
                "SYNTHETIC_SIGNATURE_RECEIPT_NONCE_REPLAY",
                seen_receipt_nonces=[self.nonce],
            )

    def test_19_witness_height_rollback_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            self.assert_denied(
                outbox, key, c, self.receipt(c),
                "SYNTHETIC_SIGNATURE_STALE_WITNESS_SEQUENCE",
                last_witness_sequence=5,
            )

    def test_20_boolean_witness_history_floor_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            self.assert_denied(
                outbox, key, c, self.receipt(c),
                "SYNTHETIC_SIGNATURE_INVALID_SEQUENCE_FLOOR",
                last_witness_sequence=True,
            )

    def test_21_user_supplied_histories_do_not_become_durable_authority(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            outcome = self.inspect(
                outbox, key, c, self.receipt(c),
                seen_provider_event_ids=(),
                seen_receipt_nonces=frozenset(),
            )
            self.assertTrue(outcome.signature_math_valid)
            self.assertFalse(outcome.independent_origin_verified)
            self.assertFalse(outcome.may_confirm)

    def test_22_naive_observation_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            self.assert_denied(
                outbox, key, c, self.receipt(c),
                "LOCAL_BINDING_INVALID_CLAIMED_EVENT_TIME",
                observed_at="2026-10-27T22:01:00",
            )

    def test_23_effect_predates_dispatch_denied_before_signature(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            c["occurred_at"] = (self.now - timedelta(seconds=1)).isoformat()
            self.assert_denied(
                outbox, key, c, r,
                "LOCAL_BINDING_CLAIMED_EFFECT_OUTSIDE_OBSERVED_WINDOW",
            )

    def test_24_duplicate_json_candidate_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            text = json.dumps(c)
            duplicate = text.replace(
                '"provider_id": "synthetic-provider"',
                '"provider_id": "synthetic-provider", "provider_id": "intruder"',
                1,
            )
            self.assertNotEqual(text, duplicate)
            self.assert_denied(
                outbox, key, duplicate, r,
                "LOCAL_BINDING_MALFORMED_OR_AMBIGUOUS_CANDIDATE",
            )

    def test_25_duplicate_signed_receipt_json_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = json.dumps(self.receipt(c))
            duplicate = r.replace(
                '"provider_id": "synthetic-provider"',
                '"provider_id": "synthetic-provider", "provider_id": "intruder"',
                1,
            )
            self.assertNotEqual(r, duplicate)
            self.assert_denied(
                outbox, key, c, duplicate,
                "MALFORMED_OR_AMBIGUOUS_SIGNED_RECEIPT",
            )

    def test_26_invalid_receipt_type_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            self.assert_denied(
                outbox, key, c, 42, "SIGNED_RECEIPT_NOT_MAPPING",
            )

    def test_27_invalid_public_key_bytes_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            self.assert_denied(
                outbox, key, c, self.receipt(c),
                "SYNTHETIC_SIGNATURE_INVALID_UNATTESTED_PUBLIC_KEY",
                candidate_pubkey_bytes=b"short",
            )

    def test_28_wrong_nonce_binding_even_with_math_valid_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            self.assert_denied(
                outbox, key, c, self.receipt(c),
                "SYNTHETIC_SIGNATURE_SIGNED_CAUSAL_BINDING_MISMATCH",
                receipt_nonce_hex="e" * 64,
            )

    def test_29_resigned_subject_mismatch_denied(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            body = {k: v for k, v in r.items() if k != "signature_b64"}
            body["subject_digest"] = "e" * 64
            self.assert_denied(
                outbox, key, c, self.sign(body),
                "SYNTHETIC_SIGNATURE_SIGNED_CAUSAL_BINDING_MISMATCH",
            )

    def test_30_claimed_not_dispatched_cannot_use_origin_bridge(self):
        with tempfile.TemporaryDirectory() as root:
            _, store, outbox, key = self.helper.seed_claim(root)
            try:
                result = inspect_synthetic_origin_bridge(
                    outbox.get(key), {}, {},
                    candidate_pubkey_bytes=self.pubkey,
                    receipt_nonce_hex=self.nonce,
                    observed_at=self.observed,
                    last_witness_sequence=4,
                    seen_provider_event_ids=[],
                    seen_receipt_nonces=[],
                )
                self.assertEqual(
                    result.code, "LOCAL_BINDING_LOCAL_INTENT_UNAVAILABLE",
                )
                self.assertFalse(result.may_confirm)
                self.assertEqual(outbox.get(key)["state"], "CLAIMED")
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_31_replay_same_signed_claim_never_writes_or_resends(self):
        with self.fixture() as (store, outbox, key, adapter):
            c = self.candidate(outbox, key)
            r = self.receipt(c)
            before = store.db.total_changes
            for _ in range(10):
                result = self.inspect(outbox, key, c, r)
                self.assertTrue(result.signature_math_valid)
                self.assertFalse(result.may_confirm)
            self.assertEqual(store.db.total_changes, before)
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(adapter.send_calls, 1)

    def test_32_immutable_result_cannot_be_promoted(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            result = self.inspect(outbox, key, c, self.receipt(c))
            with self.assertRaises(FrozenInstanceError):
                result.may_confirm = True
            with self.assertRaises(FrozenInstanceError):
                result.independent_origin_verified = True

    def test_33_strict_json_signed_receipt_and_candidate_still_no_authority(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            result = self.inspect(
                outbox, key, json.dumps(c), json.dumps(self.receipt(c)),
            )
            self.assertTrue(result.signature_math_valid)
            self.assertFalse(result.independent_origin_verified)

    def test_34_aware_string_observation_supported(self):
        with self.fixture() as (_, outbox, key, _):
            c = self.candidate(outbox, key)
            result = self.inspect(
                outbox, key, c, self.receipt(c),
                observed_at=self.observed.isoformat(),
            )
            self.assertTrue(result.signature_math_valid)
            self.assertFalse(result.may_confirm)

    def test_35_direct_confirm_still_blocked_by_outbox(self):
        with self.fixture() as (_, outbox, key, _):
            with self.assertRaisesRegex(PermissionError, "INDEPENDENT_EFFECT_RECEIPT_REQUIRED"):
                outbox._confirm(
                    key, effect_ref="host-signed-fake",
                    confirmed_at=self.now, result={"verified": True},
                )
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
            self.assertEqual(outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
