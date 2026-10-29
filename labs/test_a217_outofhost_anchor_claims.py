"""A217: 35 adversarial real SQLite tests for claimed, NOT real OOB roots.

All witnesses, organizations, pins and proof hashes are caller fabricated.
No external source, physical ceremony, key vault or real provider is used.
"""
from dataclasses import FrozenInstanceError
from datetime import timedelta
import json
import tempfile
import unittest

from labs import test_a202_outbox_dispatch_atomic_cas as a202
from labs import test_a216_synthetic_key_custody as a216_tests
from labs.a217_outofhost_anchor_claims import (
    ANCHOR_SCHEMA, WITNESS_SCHEMA, assess_claimed_outofhost_anchor,
)


class A217ClaimedOutsideHostReadinessTests(unittest.TestCase):
    def setUp(self):
        self.a216 = a216_tests.A216SyntheticKeyCustodyTests()
        self.a216.setUp()

    def claims(self, c):
        nonce = "2" * 64
        anchor = {
            "schema": ANCHOR_SCHEMA,
            "owner_id": c["owner_id"],
            "tenant_id": c["tenant_id"],
            "workspace_id": c["workspace_id"],
            "provider_id": c["provider_id"],
            "challenge_digest": c["challenge_digest"],
            "issuer_key_sha256": self.a216.issuer_fp,
            "acquisition_mode": "DECLARED_OFF_HOST_MANUAL",
            "ceremony_id": "manual-ceremony-001",
            "collector_id": "collector-A",
            "collector_org_id": "org-A",
            "owner_review_ref": "review-001",
            "artifact_digest": "1" * 64,
            "nonce_hex": nonce,
            "acquired_at": (a202.NOW - timedelta(seconds=30)).isoformat(),
        }
        def witness(obs, org, channel, digest, offset):
            return {
                "schema": WITNESS_SCHEMA,
                "observer_id": obs,
                "org_id": org,
                "channel_id": channel,
                "ceremony_id": anchor["ceremony_id"],
                "issuer_key_sha256": self.a216.issuer_fp,
                "challenge_digest": c["challenge_digest"],
                "nonce_hex": nonce,
                "attestation_digest": digest * 64,
                "observed_at": (a202.NOW + timedelta(seconds=offset)).isoformat(),
            }
        return (
            anchor,
            witness("witness-B", "org-B", "offline-channel-B", "3", 10),
            witness("witness-C", "org-C", "offline-channel-C", "4", 15),
        )

    def examine(self, outbox, key, c, r, cert, anchor, wa, wb, **overrides):
        args = {
            "candidate_pubkey_bytes": self.a216.a215.pubkey,
            "provisional_issuer_pubkey_bytes": self.a216.issuer_public,
            "provisional_issuer_fingerprint": self.a216.issuer_fp,
            "receipt_nonce_hex": self.a216.a215.nonce,
            "observed_at": self.a216.a215.observed,
            "last_witness_sequence": 4,
            "seen_provider_event_ids": [],
            "seen_receipt_nonces": [],
            "previous_key_epoch": 0,
            "seen_custody_serial_ids": [],
            "seen_ceremony_nonces": [],
        }
        args.update(overrides)
        return assess_claimed_outofhost_anchor(
            outbox.get(key), c, r, cert, anchor, wa, wb, **args,
        )

    def denial(self, outbox, key, c, r, cert, anchor, wa, wb, code, **overrides):
        assessment = self.examine(
            outbox, key, c, r, cert, anchor, wa, wb, **overrides,
        )
        self.assertEqual(assessment.code, code)
        self.assertFalse(assessment.claimed_separation_coherent)
        self.assertFalse(assessment.independent_origin_verified)
        self.assertFalse(assessment.may_activate)
        self.assertFalse(assessment.may_confirm)
        return assessment

    def test_01_three_distinct_fake_orgs_still_not_real_independence(self):
        with self.a216.a215.fixture() as (store, outbox, key, adapter):
            c = self.a216.a215.candidate(outbox, key)
            r, cert = self.a216.a215.receipt(c), self.a216.certificate(c)
            a, wa, wb = self.claims(c)
            before = store.db.total_changes
            result = self.examine(outbox, key, c, r, cert, a, wa, wb)
            self.assertTrue(result.custody_math_valid)
            self.assertTrue(result.claimed_separation_coherent)
            self.assertFalse(result.independent_origin_verified)
            self.assertFalse(result.may_activate)
            self.assertFalse(result.may_confirm)
            self.assertEqual(result.code, "CLAIMED_CHANNELS_COHERENT_INDEPENDENT_ACQUISITION_UNPROVEN")
            self.assertEqual(len(result.claims_digest), 64)
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(store.db.total_changes, before)
            self.assertEqual(adapter.send_calls, 1)

    def test_02_sent_does_not_transition(self):
        with self.a216.a215.fixture("pending") as (store, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            before = store.db.total_changes
            result = self.examine(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb)
            self.assertTrue(result.claimed_separation_coherent)
            self.assertFalse(result.may_confirm)
            self.assertEqual(outbox.get(key)["state"], "SENT")
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(store.db.total_changes, before)

    def test_03_repeating_host_claims_never_writes_or_resends(self):
        with self.a216.a215.fixture() as (store, outbox, key, adapter):
            c = self.a216.a215.candidate(outbox, key)
            r, cert = self.a216.a215.receipt(c), self.a216.certificate(c)
            a, wa, wb = self.claims(c)
            before = store.db.total_changes
            for _ in range(6):
                result = self.examine(outbox, key, c, r, cert, a, wa, wb)
                self.assertTrue(result.claimed_separation_coherent)
                self.assertFalse(result.may_activate)
            self.assertEqual(store.db.total_changes, before)
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(outbox.effect_count(), 0)

    def test_04_wrong_claimed_root_fingerprint(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            a["issuer_key_sha256"] = "f" * 64
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "ANCHOR_SCOPE_OR_KEY_MISMATCH")

    def test_05_every_scope_and_binding_field_is_checked(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            for field in ("owner_id", "tenant_id", "workspace_id", "provider_id", "challenge_digest"):
                with self.subTest(field=field):
                    a, wa, wb = self.claims(c)
                    a[field] = "intruder"
                    self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "ANCHOR_SCOPE_OR_KEY_MISMATCH")

    def test_06_wrong_witness_key(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wb["issuer_key_sha256"] = "f" * 64
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "WITNESS_ROOT_OR_INTENT_MISMATCH")

    def test_07_wrong_witness_challenge(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wa["challenge_digest"] = "f" * 64
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "WITNESS_ROOT_OR_INTENT_MISMATCH")

    def test_08_fake_verified_flag_rejected_in_anchor(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            a["independently_verified"] = True
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "ANCHOR_CLAIM_ENVELOPE_NOT_EXACT")

    def test_09_fake_verified_flag_rejected_in_witness(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wa["external_verified"] = True
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "WITNESS_CLAIM_ENVELOPE_NOT_EXACT")

    def test_10_same_claimed_witness_observer_rejected(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wb["observer_id"] = wa["observer_id"]
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "DUPLICATED_CLAIMED_INDEPENDENCE")

    def test_11_same_claimed_witness_org_rejected(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wb["org_id"] = wa["org_id"]
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "DUPLICATED_CLAIMED_INDEPENDENCE")

    def test_12_same_claimed_witness_channel_rejected(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wb["channel_id"] = wa["channel_id"]
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "DUPLICATED_CLAIMED_INDEPENDENCE")

    def test_13_collector_org_cannot_equal_witness_org(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            a["collector_org_id"] = wa["org_id"]
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "CLAIMED_COLLECTOR_WITNESS_COLLISION")

    def test_14_collector_cannot_equal_witness_identity(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            a["collector_id"] = wb["observer_id"]
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "CLAIMED_COLLECTOR_WITNESS_COLLISION")

    def test_15_witness_ceremony_mismatch(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wa["ceremony_id"] = "other-ceremony"
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "WITNESS_CEREMONY_OR_NONCE_MISMATCH")

    def test_16_witness_nonce_mismatch(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wa["nonce_hex"] = "f" * 64
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "WITNESS_CEREMONY_OR_NONCE_MISMATCH")

    def test_17_invalid_anchor_artifact_digest(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            a["artifact_digest"] = "not-real-hash"
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "INVALID_CLAIMED_ANCHOR_DIGEST")

    def test_18_non_outofhost_acquisition_mode_rejected(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            a["acquisition_mode"] = "HOST_ASSERTED_API"
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "UNACCEPTABLE_CLAIMED_ACQUISITION_MODE")

    def test_19_invalid_collector_identifier(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            a["collector_id"] = "bad identifier /"
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "INVALID_CLAIMED_COLLECTOR_IDENTITY")

    def test_20_invalid_witness_identifier(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wa["observer_id"] = ""
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "INVALID_CLAIMED_WITNESS_IDENTITY")

    def test_21_invalid_witness_attestation_digest(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wa["attestation_digest"] = "fake"
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "INVALID_CLAIMED_WITNESS_DIGEST")

    def test_22_seen_nonce_blocks_claim_replay(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "CEREMONY_NONCE_CLAIM_REPLAY", seen_ceremony_nonces=["2" * 64])

    def test_23_invalid_host_supplied_nonce_history(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "UNTRUSTED_CEREMONY_NONCE_HISTORY", seen_ceremony_nonces=["not-hash"])

    def test_24_acquisition_after_observation_denied(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            a["acquired_at"] = (a202.NOW + timedelta(minutes=2)).isoformat()
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "DECLARED_OBSERVATION_TIME_CONFLICT")

    def test_25_witness_before_acquisition_denied(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wa["observed_at"] = (a202.NOW - timedelta(minutes=1)).isoformat()
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "DECLARED_OBSERVATION_TIME_CONFLICT")

    def test_26_naive_witness_clock_denied(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            wb["observed_at"] = "2026-10-27T22:00:15"
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "INVALID_DECLARED_OBSERVATION_TIME")

    def test_27_far_stale_acquisition_denied(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            a["acquired_at"] = (a202.NOW - timedelta(days=2)).isoformat()
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb, "DECLARED_OBSERVATION_TIME_CONFLICT")

    def test_28_duplicate_json_anchor_denied(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            raw = json.dumps(a)
            dup = raw.replace('"collector_id": "collector-A"', '"collector_id": "collector-A", "collector_id": "intruder"', 1)
            self.assertNotEqual(raw, dup)
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), dup, wa, wb, "ANCHOR_CLAIM_ENVELOPE_NOT_EXACT")

    def test_29_duplicate_json_witness_denied(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            raw = json.dumps(wa)
            dup = raw.replace('"org_id": "org-B"', '"org_id": "org-B", "org_id": "intruder"', 1)
            self.assertNotEqual(raw, dup)
            self.denial(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, dup, wb, "WITNESS_CLAIM_MISSING_OR_AMBIGUOUS")

    def test_30_wrong_custody_signature_blocks_oob_diagnostic(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            cert = self.a216.certificate(c)
            cert["issuer_signature_b64"] = "bad"
            self.denial(outbox, key, c, self.a216.a215.receipt(c), cert, a, wa, wb, "A216_INVALID_ISSUER_SIGNATURE_ENCODING")

    def test_31_wrong_effect_signature_blocks_oob_diagnostic(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            receipt = self.a216.a215.receipt(c)
            receipt["signature_b64"] = "bad"
            self.denial(outbox, key, c, receipt, self.a216.certificate(c), a, wa, wb, "A216_A215_SYNTHETIC_SIGNATURE_INVALID_SIGNATURE_ENCODING")

    def test_32_immutable_result_cannot_grant_trust(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            result = self.examine(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb)
            with self.assertRaises(FrozenInstanceError):
                result.may_activate = True
            with self.assertRaises(FrozenInstanceError):
                result.independent_origin_verified = True

    def test_33_json_all_three_claims_still_no_authority(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            result = self.examine(
                outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c),
                json.dumps(a), json.dumps(wa), json.dumps(wb),
            )
            self.assertTrue(result.claimed_separation_coherent)
            self.assertFalse(result.independent_origin_verified)

    def test_34_false_organization_independence_never_claimed_as_authority(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            c = self.a216.a215.candidate(outbox, key)
            a, wa, wb = self.claims(c)
            result = self.examine(outbox, key, c, self.a216.a215.receipt(c), self.a216.certificate(c), a, wa, wb)
            self.assertTrue(result.claimed_separation_coherent)
            self.assertFalse(result.independent_origin_verified)
            self.assertFalse(result.may_activate)
            self.assertFalse(result.may_confirm)

    def test_35_outbox_confirmation_remains_forbidden(self):
        with self.a216.a215.fixture() as (_, outbox, key, _):
            with self.assertRaisesRegex(PermissionError, "INDEPENDENT_EFFECT_RECEIPT_REQUIRED"):
                outbox._confirm(
                    key, effect_ref="fake-oob-claim",
                    confirmed_at=a202.NOW, result={"external_verified": True},
                )
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
            self.assertEqual(outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
