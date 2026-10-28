"""A214: untrusted effect candidate intake is READ-ONLY, with HARD NO-GO.

Real SQLite Outbox and synthetic adapter. No external provider, key, receipt,
replay store, browser, network or actual external effect is involved.
A local binding match MUST NEVER imply confirmation or safe resend.
"""
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from datetime import timedelta
import copy
import json
import tempfile
import unittest

from atlasquant_aion_external_evidence_intake import (
    CANDIDATE_SCHEMA, CHALLENGE_SCHEMA, decode_candidate_json,
    make_local_evidence_challenge, preflight_untrusted_effect_candidate,
)
from labs import test_a202_outbox_dispatch_atomic_cas as a202
from labs.test_a213_outbox_untrusted_positive_hard_nogo import UntrustedPositive


class A214ReadOnlyEvidenceIntakeTests(unittest.TestCase):
    def setUp(self):
        self.helper = a202.A202SameLeaseOwnerDispatchRaceTests()
        self.observed = a202.NOW + timedelta(minutes=1)

    @contextmanager
    def fixture(self, send_mode="positive"):
        with tempfile.TemporaryDirectory() as root:
            _, store, outbox, key = self.helper.seed_claim(root)
            adapter = UntrustedPositive(send_mode)
            try:
                dispatched = outbox.dispatch_claimed(
                    key, worker_id=a202.WORKER,
                    authorize=self.helper.authorize, adapter=adapter, now=a202.NOW,
                )
                self.assertIn(dispatched["state"], {"SENT", "UNCERTAIN"})
                self.assertEqual(outbox.effect_count(), 0)
                yield store, outbox, key, adapter
            finally:
                store.close()

    def candidate(self, outbox, key):
        challenge = outbox.evidence_challenge(key)
        body = json.loads(challenge.challenge_json)
        self.assertEqual(body.pop("schema"), CHALLENGE_SCHEMA)
        return {
            "schema": CANDIDATE_SCHEMA,
            **body,
            "challenge_digest": challenge.challenge_digest,
            "provider_id": "synthetic-provider",
            "provider_event_id": "synthetic-event-1",
            "effect_ref": "synthetic-effect-1",
            "effect_state": "EFFECT_CONFIRMED",
            "provider_receipt_digest": "f" * 64,
            "witness_root_fingerprint": "a" * 64,
            "witness_checkpoint_hash": "b" * 64,
            "witness_sequence": 1,
            "occurred_at": a202.NOW.isoformat(),
        }

    def inspect(self, outbox, key, candidate, *, observed=None):
        return outbox.inspect_untrusted_effect_candidate(
            key, candidate,
            observed_at=observed if observed is not None else self.observed,
        )

    def assert_denied(self, outbox, key, candidate, code, *, observed=None):
        result = self.inspect(outbox, key, candidate, observed=observed)
        self.assertEqual(result.code, code)
        self.assertFalse(result.matches_local_binding)
        self.assertFalse(result.may_confirm)
        self.assertEqual(result.challenge_digest, "")

    def test_01_positive_send_is_uncertain_and_candidate_does_not_confirm(self):
        with self.fixture() as (store, outbox, key, adapter):
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
            prior_changes = store.db.total_changes
            c = self.candidate(outbox, key)
            result = self.inspect(outbox, key, c)
            self.assertTrue(result.matches_local_binding)
            self.assertFalse(result.may_confirm)
            self.assertEqual(
                result.code, "LOCAL_BINDING_OK_EXTERNAL_AUTHORITY_AND_EFFECT_UNPROVEN",
            )
            self.assertEqual(result.challenge_digest, c["challenge_digest"])
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(store.db.total_changes, prior_changes)
            self.assertEqual(adapter.send_calls, 1)

    def test_02_sent_is_still_not_confirmed_by_perfect_claim(self):
        with self.fixture("pending") as (store, outbox, key, adapter):
            self.assertEqual(outbox.get(key)["state"], "SENT")
            changes = store.db.total_changes
            result = self.inspect(outbox, key, self.candidate(outbox, key))
            self.assertTrue(result.matches_local_binding)
            self.assertFalse(result.may_confirm)
            self.assertEqual(store.db.total_changes, changes)
            self.assertEqual(outbox.get(key)["state"], "SENT")
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(adapter.send_calls, 1)

    def test_03_challenge_is_local_deterministic_and_never_authoritative(self):
        with self.fixture() as (_, outbox, key, _adapter):
            a = outbox.evidence_challenge(key)
            b = outbox.evidence_challenge(key)
            self.assertEqual(a, b)
            self.assertFalse(a.may_confirm)
            self.assertEqual(len(a.challenge_digest), 64)
            self.assertEqual(a.state, "UNCERTAIN")
            self.assertEqual(json.loads(a.challenge_json)["schema"], CHALLENGE_SCHEMA)

    def test_04_frozen_results_cannot_toggle_confirmation(self):
        with self.fixture() as (_, outbox, key, _adapter):
            challenge = outbox.evidence_challenge(key)
            result = self.inspect(outbox, key, self.candidate(outbox, key))
            with self.assertRaises(FrozenInstanceError):
                challenge.may_confirm = True
            with self.assertRaises(FrozenInstanceError):
                result.may_confirm = True

    def test_05_identical_replays_never_produce_effect_or_resend(self):
        with self.fixture() as (store, outbox, key, adapter):
            c = self.candidate(outbox, key)
            before = store.db.total_changes
            for _ in range(7):
                self.assertFalse(self.inspect(outbox, key, c).may_confirm)
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(store.db.total_changes, before)

    def test_06_fabricated_verified_claim_is_rejected_as_extra_field(self):
        with self.fixture() as (_, outbox, key, _adapter):
            for forged in ("independently_verified", "trusted", "signature_valid", "may_confirm"):
                with self.subTest(forged=forged):
                    c = self.candidate(outbox, key)
                    c[forged] = True
                    self.assert_denied(outbox, key, c, "CANDIDATE_ENVELOPE_NOT_EXACT")

    def test_07_missing_required_fields_are_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            for field in ("owner_id", "witness_sequence", "decision_id", "effect_ref", "challenge_digest"):
                with self.subTest(field=field):
                    c = self.candidate(outbox, key)
                    c.pop(field)
                    self.assert_denied(outbox, key, c, "CANDIDATE_ENVELOPE_NOT_EXACT")

    def test_08_wrong_or_invalid_challenge_digest_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            c = self.candidate(outbox, key)
            c["challenge_digest"] = "0" * 64
            self.assert_denied(outbox, key, c, "LOCAL_CHALLENGE_MISMATCH")
            c["challenge_digest"] = "G" * 64
            self.assert_denied(outbox, key, c, "INVALID_CHALLENGE_DIGEST")

    def test_09_every_original_intent_field_is_bound(self):
        with self.fixture() as (_, outbox, key, _adapter):
            base = self.candidate(outbox, key)
            bound = (
                "owner_id", "tenant_id", "workspace_id", "idempotency_key",
                "decision_id", "intent_ref", "action", "payload_digest",
                "policy_version", "authorization_ref", "aggregate_seq",
                "attempts", "state", "dispatch_started_at", "sent_at",
                "created_at", "valid_until",
            )
            for field in bound:
                with self.subTest(field=field):
                    c = dict(base)
                    c[field] = ("forged-value" if isinstance(c[field], str) else 999)
                    self.assert_denied(
                        outbox, key, c, "ORIGINAL_INTENT_OR_ATTEMPT_MISMATCH",
                    )

    def test_10_bool_not_accepted_as_integer_attempt(self):
        with self.fixture() as (_, outbox, key, _adapter):
            c = self.candidate(outbox, key)
            c["attempts"] = True
            self.assert_denied(outbox, key, c, "ORIGINAL_INTENT_OR_ATTEMPT_MISMATCH")

    def test_11_wrong_schema_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            c = self.candidate(outbox, key)
            c["schema"] = CHALLENGE_SCHEMA
            self.assert_denied(outbox, key, c, "UNSUPPORTED_CANDIDATE_SCHEMA")

    def test_12_invalid_provider_identifiers_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            for field in ("provider_id", "provider_event_id", "effect_ref"):
                with self.subTest(field=field):
                    c = self.candidate(outbox, key)
                    c[field] = " contains spaces / bad "
                    self.assert_denied(outbox, key, c, "INVALID_PROVIDER_IDENTIFIERS")

    def test_13_fingerprint_spoofing_with_invalid_hex_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            for field in ("provider_receipt_digest", "witness_root_fingerprint", "witness_checkpoint_hash"):
                with self.subTest(field=field):
                    c = self.candidate(outbox, key)
                    c[field] = "not-an-authentic-receipt"
                    self.assert_denied(
                        outbox, key, c, "INVALID_UNATTESTED_EVIDENCE_FINGERPRINT",
                    )

    def test_14_arbitrary_well_formed_witness_hashes_still_do_not_confirm(self):
        with self.fixture() as (_, outbox, key, _adapter):
            for fake in ("0", "1", "c"):
                c = self.candidate(outbox, key)
                c["witness_root_fingerprint"] = fake * 64
                c["witness_checkpoint_hash"] = fake * 64
                result = self.inspect(outbox, key, c)
                self.assertTrue(result.matches_local_binding)
                self.assertFalse(result.may_confirm)

    def test_15_invalid_witness_sequence_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            for val in (0, -1, True, 1.0, "1", None):
                with self.subTest(val=val):
                    c = self.candidate(outbox, key)
                    c["witness_sequence"] = val
                    self.assert_denied(outbox, key, c, "INVALID_WITNESS_SEQUENCE")

    def test_16_nonfinal_claimed_effect_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            for val in ("PENDING", "ABSENT", "UNKNOWN", "", True):
                with self.subTest(val=val):
                    c = self.candidate(outbox, key)
                    c["effect_state"] = val
                    self.assert_denied(outbox, key, c, "CLAIMED_EFFECT_NOT_FINAL")

    def test_17_claimed_effect_before_dispatch_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            c = self.candidate(outbox, key)
            c["occurred_at"] = (a202.NOW - timedelta(seconds=1)).isoformat()
            self.assert_denied(
                outbox, key, c, "CLAIMED_EFFECT_OUTSIDE_OBSERVED_WINDOW",
            )

    def test_18_claimed_effect_after_observation_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            c = self.candidate(outbox, key)
            c["occurred_at"] = (self.observed + timedelta(seconds=1)).isoformat()
            self.assert_denied(
                outbox, key, c, "CLAIMED_EFFECT_OUTSIDE_OBSERVED_WINDOW",
            )

    def test_19_naive_or_invalid_event_time_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            for value in ("2026-10-27T22:00:00", "yesterday", None, 5):
                with self.subTest(value=value):
                    c = self.candidate(outbox, key)
                    c["occurred_at"] = value
                    self.assert_denied(outbox, key, c, "INVALID_CLAIMED_EVENT_TIME")

    def test_20_invalid_observed_at_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            c = self.candidate(outbox, key)
            self.assert_denied(
                outbox, key, c, "INVALID_CLAIMED_EVENT_TIME",
                observed="2026-10-27T22:01:00",
            )

    def test_21_proper_json_candidate_is_accepted_only_as_untrusted_match(self):
        with self.fixture() as (_, outbox, key, _adapter):
            raw = json.dumps(self.candidate(outbox, key), sort_keys=True)
            result = self.inspect(outbox, key, raw)
            self.assertTrue(result.matches_local_binding)
            self.assertFalse(result.may_confirm)

    def test_22_duplicate_json_keys_rejected_even_when_values_identical(self):
        with self.fixture() as (_, outbox, key, _adapter):
            raw = json.dumps(self.candidate(outbox, key))
            duplicate = raw.replace(
                '"provider_id": "synthetic-provider"',
                '"provider_id": "synthetic-provider", "provider_id": "synthetic-provider"',
                1,
            )
            self.assertNotEqual(raw, duplicate)
            with self.assertRaises(ValueError):
                decode_candidate_json(duplicate)
            self.assert_denied(
                outbox, key, duplicate, "MALFORMED_OR_AMBIGUOUS_CANDIDATE",
            )

    def test_23_json_payload_over_8192_bytes_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            raw = json.dumps(self.candidate(outbox, key))
            oversized = raw + " " * 8192
            self.assert_denied(
                outbox, key, oversized, "MALFORMED_OR_AMBIGUOUS_CANDIDATE",
            )

    def test_24_json_nonfinite_and_truncated_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            for raw in ('{"bad":NaN}', '{"bad":Infinity}', '{"broken":'):
                with self.subTest(raw=raw):
                    self.assert_denied(
                        outbox, key, raw, "MALFORMED_OR_AMBIGUOUS_CANDIDATE",
                    )

    def test_25_candidate_list_or_null_rejected(self):
        with self.fixture() as (_, outbox, key, _adapter):
            for value in ([], None, 3, "[]", "null"):
                with self.subTest(value=value):
                    result = self.inspect(outbox, key, value)
                    self.assertFalse(result.may_confirm)
                    self.assertFalse(result.matches_local_binding)

    def test_26_pending_and_claimed_may_not_issue_challenge(self):
        with tempfile.TemporaryDirectory() as root:
            _, store, outbox, key = self.helper.seed_claim(root)
            try:
                with self.assertRaisesRegex(ValueError, "only ambiguous"):
                    outbox.evidence_challenge(key)
                result = self.inspect(outbox, key, {})
                self.assertEqual(result.code, "LOCAL_INTENT_UNAVAILABLE")
                self.assertFalse(result.may_confirm)
                self.assertEqual(outbox.get(key)["state"], "CLAIMED")
            finally:
                store.close()

    def test_27_corrupt_local_decision_or_aggregate_fails_closed(self):
        with self.fixture() as (_, outbox, key, _adapter):
            record = outbox.get(key)
            mutations = [
                ("decision", None),
                ("schema", "wrong-schema"),
                ("aggregate_seq", 900),
                ("idempotency_key", "0" * 64),
                ("state", "CONFIRMED"),
            ]
            for field, value in mutations:
                with self.subTest(field=field):
                    fake = copy.deepcopy(record)
                    fake[field] = value
                    with self.assertRaises(ValueError):
                        make_local_evidence_challenge(fake)
                    result = preflight_untrusted_effect_candidate(
                        fake, {}, observed_at=self.observed,
                    )
                    self.assertEqual(result.code, "LOCAL_INTENT_UNAVAILABLE")
                    self.assertFalse(result.may_confirm)

    def test_28_direct_internal_confirmation_remains_forbidden(self):
        with self.fixture() as (_, outbox, key, _adapter):
            with self.assertRaisesRegex(
                PermissionError, "INDEPENDENT_EFFECT_RECEIPT_REQUIRED",
            ):
                outbox._confirm(
                    key, effect_ref="fabricated-external-proof",
                    confirmed_at=a202.NOW, result={"verified": True},
                )
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
            self.assertEqual(outbox.effect_count(), 0)

    def test_29_challenge_read_and_candidate_read_do_not_write_sqlite(self):
        with self.fixture() as (store, outbox, key, _adapter):
            initial = store.db.total_changes
            for _ in range(5):
                self.inspect(outbox, key, self.candidate(outbox, key))
            self.assertEqual(store.db.total_changes, initial)
            self.assertEqual(outbox.effect_count(), 0)

    def test_30_old_scope_and_attempt_claims_stale_after_new_snapshot(self):
        with self.fixture() as (_, outbox, key, _adapter):
            c = self.candidate(outbox, key)
            c["tenant_id"] = "another-tenant"
            c["attempts"] = 0
            self.assert_denied(outbox, key, c, "ORIGINAL_INTENT_OR_ATTEMPT_MISMATCH")


if __name__ == "__main__":
    unittest.main()
