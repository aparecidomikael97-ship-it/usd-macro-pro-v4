"""A308 signed evidence binding negative tests, synthetic witnesses only."""
import copy
import hashlib
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from labs.test_a304_custodian_status_lab import fixture as a304_fixture
from labs.test_a305_restart_revocation_no_resend_lab import later_status
from labs.test_a306_manual_intent_reconciliation_lab import case_fixture, claim
from labs.a305_restart_revocation_no_resend_lab import probe_sqlite_restart_ack_loss
from labs.a306_manual_intent_reconciliation_lab import assess_manual_reconciliation
from labs.a302_witness_receipt_contract_lab import _encoded
from labs.a308_evidence_provenance_contract_lab import (
    SCHEMA, MAX_EVIDENCE_BYTES, MAX_CLAIMS,
    receipt_signing_bytes, assess_evidence_provenance,
)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def public_key(private):
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def fixture(observation):
    before, status_key, _ = a304_fixture()
    after = later_status(before, status_key, "REVOKED")
    payloads = [
        b"A308 synthetic provider receipt: observed local effect",
        b"A308 synthetic custodian statement: records the claim",
    ]
    review = case_fixture()
    review["claimed_evidence"] = [
        dict(claim("PRESENT", "synthetic-provider-a", "event-a"),
             evidence_sha256=sha(payloads[0])),
        dict(claim("PRESENT", "synthetic-custodian-b", "event-b"),
             evidence_sha256=sha(payloads[1])),
    ]
    manual = assess_manual_reconciliation(
        observation=observation,
        before_status_inputs=before,
        after_status_inputs=after,
        previous_incident_epoch=4,
        recovery_incident_epoch=5,
        review_case=review,
        last_closed_case_generation=6,
    )
    assert manual["case_file_locally_valid"]
    assert manual["claimed_evidence_consistent_locally"]
    keys = {
        source: Ed25519PrivateKey.generate()
        for source in ("synthetic-provider-a", "synthetic-custodian-b")
    }
    pins = {source: public_key(key) for source, key in keys.items()}
    heads = {
        source: {"sequence": 4, "receipt_sha256": "c" * 64}
        for source in keys
    }
    nonce = "d" * 64
    receipts = []
    for record in review["claimed_evidence"]:
        source = record["source_id"]
        item = {
            "schema": SCHEMA,
            "source_id": source,
            "reference_id": record["reference_id"],
            "intent_id": record["intent_id"],
            "message_id": record["message_id"],
            "observed_outcome": record["observed_outcome"],
            "evidence_sha256": record["evidence_sha256"],
            "case_sha256": manual["case_digest_sha256"],
            "challenge_nonce": nonce,
            "incident_epoch": review["incident_epoch"],
            "sequence": 5,
            "previous_receipt_sha256": "c" * 64,
            "issued_at": 9900,
            "expires_at": 10100,
        }
        item["signature_hex"] = keys[source].sign(
            receipt_signing_bytes(item)).hex()
        receipts.append(item)
    return {
        "review_case": review, "manual_assessment": manual,
        "raw_evidence": payloads, "signed_receipts": receipts,
        "pinned_source_keys": pins, "last_seen_heads": heads,
        "challenge_nonce": nonce, "now_epoch": 10000,
    }, keys


def evaluate(args, **kwargs):
    return assess_evidence_provenance(**dict(args, **kwargs))


class A308EvidenceProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = probe_sqlite_restart_ack_loss()

    def setUp(self):
        self.f, self.keys = fixture(self.observation)

    def assert_no_go(self, out):
        self.assertFalse(out["evidence_provenance_independent"])
        self.assertFalse(out["actual_provider_outcome_verified"])
        self.assertFalse(out["last_seen_heads_off_host_verified"])
        self.assertFalse(out["trusted_clock_verified"])
        self.assertFalse(out["can_resume"])
        self.assertFalse(out["can_resend"])
        self.assertFalse(out["can_auto_retry"])
        self.assertFalse(out["can_authorize_real_effect"])
        self.assertEqual(out["automatic_retries"], 0)
        self.assertTrue(out["zero_auto_resend"])
        self.assertTrue(out["hard_no_go"])
        self.assertEqual(out["p0_homologated"], 0)
        self.assertFalse(out["new_paid_services"])
        self.assertTrue(out["no_provider_worker_deploy_orders"])

    def test_two_signed_payloads_are_only_locally_coherent(self):
        r = evaluate(self.f)
        self.assertTrue(r["case_structure_locally_consistent"])
        self.assertTrue(r["payload_digests_match_locally"])
        self.assertEqual(r["cryptographically_verified_receipts"], 2)
        self.assertTrue(r["receipt_chain_locally_consistent"])
        self.assertEqual(r["issues"], [
            "ACK_UNKNOWN_NEVER_AUTO_RESEND",
            "INDEPENDENT_EVIDENCE_ORIGIN_NOT_AUTHENTICATED",
        ])
        self.assert_no_go(r)

    def test_two_distinct_local_keys_are_not_real_independence(self):
        r = evaluate(self.f)
        self.assertTrue(r["receipt_chain_locally_consistent"])
        self.assertFalse(r["evidence_provenance_independent"])
        self.assertFalse(r["actual_provider_outcome_verified"])
        self.assert_no_go(r)

    def test_single_hex_digest_without_content_not_accepted(self):
        edited = list(self.f["raw_evidence"])
        edited[0] = b"unrelated fake evidence"
        r = evaluate(self.f, raw_evidence=edited)
        self.assertIn("CLAIM_DIGEST_NOT_BOUND_TO_BYTES", r["issues"])
        self.assertFalse(r["payload_digests_match_locally"])
        self.assert_no_go(r)

    def test_swapped_payloads_not_accepted(self):
        r = evaluate(self.f, raw_evidence=list(reversed(self.f["raw_evidence"])))
        self.assertIn("CLAIM_DIGEST_NOT_BOUND_TO_BYTES", r["issues"])

    def test_missing_payloads_denied(self):
        r = evaluate(self.f, raw_evidence=[])
        self.assertIn("EVIDENCE_PAYLOAD_COUNT_INVALID", r["issues"])
        self.assert_no_go(r)

    def test_nonbytes_payload_denied(self):
        r = evaluate(self.f, raw_evidence=["text", self.f["raw_evidence"][1]])
        self.assertIn("EVIDENCE_BYTES_MISSING_OR_OVERSIZED", r["issues"])

    def test_oversized_evidence_denied(self):
        r = evaluate(self.f, raw_evidence=[
            b"x" * (MAX_EVIDENCE_BYTES + 1), self.f["raw_evidence"][1]
        ])
        self.assertIn("EVIDENCE_BYTES_MISSING_OR_OVERSIZED", r["issues"])

    def test_missing_receipt_denied(self):
        r = evaluate(self.f, signed_receipts=self.f["signed_receipts"][:1])
        self.assertIn("SIGNED_RECEIPT_COUNT_INVALID", r["issues"])

    def test_corrupted_signature_denied(self):
        receipts = copy.deepcopy(self.f["signed_receipts"])
        receipts[0]["signature_hex"] = "0" * 128
        r = evaluate(self.f, signed_receipts=receipts)
        self.assertIn("SIGNATURE_NOT_VERIFIED", r["issues"])

    def test_wrong_key_denied(self):
        pins = dict(self.f["pinned_source_keys"])
        pins["synthetic-provider-a"] = public_key(Ed25519PrivateKey.generate())
        r = evaluate(self.f, pinned_source_keys=pins)
        self.assertIn("SIGNATURE_NOT_VERIFIED", r["issues"])

    def test_same_key_for_two_fake_sources_detected(self):
        pins = dict(self.f["pinned_source_keys"])
        pins["synthetic-custodian-b"] = pins["synthetic-provider-a"]
        r = evaluate(self.f, pinned_source_keys=pins)
        self.assertIn("SOURCE_PINS_NOT_DISTINCT_OR_INVALID", r["issues"])

    def test_unpinned_source_denied(self):
        pins = dict(self.f["pinned_source_keys"])
        del pins["synthetic-provider-a"]
        r = evaluate(self.f, pinned_source_keys=pins)
        self.assertIn("SOURCE_NOT_IN_PINSET", r["issues"])

    def test_renamed_source_claim_cannot_reuse_old_signature(self):
        review = copy.deepcopy(self.f["review_case"])
        review["claimed_evidence"][0]["source_id"] = "synthetic-custodian-b"
        r = evaluate(self.f, review_case=review)
        self.assertIn("SIGNED_CLAIM_BINDING_MISMATCH", r["issues"])
        self.assertIn("REVIEW_CASE_HASH_MISMATCH", r["issues"])

    def test_cross_case_receipt_is_rejected(self):
        review = dict(self.f["review_case"], case_id="different-case")
        r = evaluate(self.f, review_case=review)
        self.assertIn("REVIEW_CASE_HASH_MISMATCH", r["issues"])
        self.assertIn("SIGNED_CASE_BINDING_MISMATCH", r["issues"])

    def test_nonce_replay_denied(self):
        r = evaluate(self.f, challenge_nonce="f" * 64)
        self.assertIn("RECEIPT_NONCE_REPLAY", r["issues"])

    def test_expired_receipt_denied(self):
        r = evaluate(self.f, now_epoch=10100)
        self.assertIn("RECEIPT_STALE_OR_FUTURE", r["issues"])

    def test_future_receipt_denied(self):
        r = evaluate(self.f, now_epoch=9899)
        self.assertIn("RECEIPT_STALE_OR_FUTURE", r["issues"])

    def test_old_seen_sequence_detects_replay(self):
        heads = copy.deepcopy(self.f["last_seen_heads"])
        heads["synthetic-provider-a"]["sequence"] = 5
        r = evaluate(self.f, last_seen_heads=heads)
        self.assertIn("RECEIPT_REPLAY_OR_CHAIN_GAP", r["issues"])

    def test_changed_previous_receipt_hash_detected(self):
        heads = copy.deepcopy(self.f["last_seen_heads"])
        heads["synthetic-custodian-b"]["receipt_sha256"] = "0" * 64
        r = evaluate(self.f, last_seen_heads=heads)
        self.assertIn("RECEIPT_REPLAY_OR_CHAIN_GAP", r["issues"])

    def test_missing_offhost_head_denied(self):
        heads = copy.deepcopy(self.f["last_seen_heads"])
        del heads["synthetic-provider-a"]
        r = evaluate(self.f, last_seen_heads=heads)
        self.assertIn("LAST_SEEN_HEADS_INVALID", r["issues"])
        self.assertIn("OFF_HOST_HEAD_NOT_PROVIDED", r["issues"])

    def test_signed_incident_epoch_mismatch_denied(self):
        receipts = copy.deepcopy(self.f["signed_receipts"])
        receipts[0]["incident_epoch"] = 4
        r = evaluate(self.f, signed_receipts=receipts)
        self.assertIn("SIGNED_INCIDENT_EPOCH_MISMATCH", r["issues"])

    def test_extra_receipt_field_denied(self):
        receipts = copy.deepcopy(self.f["signed_receipts"])
        receipts[0]["operator_approved"] = True
        r = evaluate(self.f, signed_receipts=receipts)
        self.assertIn("RECEIPT_FIELDS_INVALID", r["issues"])

    def test_empty_claims_cannot_promote_local_case(self):
        review = case_fixture()
        r = evaluate(self.f, review_case=review)
        self.assertIn("CLAIM_COUNT_INVALID", r["issues"])
        self.assert_no_go(r)

    def test_forged_manual_assessment_not_accepted(self):
        manual = dict(self.f["manual_assessment"], can_resume=True)
        r = evaluate(self.f, manual_assessment=manual)
        self.assertIn("A306_A307_NEGATIVE_ASSESSMENT_MISSING", r["issues"])
        self.assert_no_go(r)

    def test_receipts_can_be_cryptographically_valid_with_old_local_heads(self):
        forged, _ = fixture(self.observation)
        r = evaluate(forged)
        self.assertTrue(r["receipt_chain_locally_consistent"])
        self.assertFalse(r["last_seen_heads_off_host_verified"])
        self.assertFalse(r["evidence_provenance_independent"])
        self.assert_no_go(r)

    def test_malformed_boolean_timestamp_fails_closed(self):
        r = evaluate(self.f, now_epoch=True)
        self.assertIn("UNTRUSTED_NOW_FORMAT", r["issues"])
        self.assert_no_go(r)

    def test_overlimit_claims_fail_closed(self):
        review = copy.deepcopy(self.f["review_case"])
        review["claimed_evidence"] = (
            review["claimed_evidence"] * (MAX_CLAIMS + 1)
        )
        r = evaluate(self.f, review_case=review)
        self.assertIn("CLAIM_COUNT_INVALID", r["issues"])
        self.assert_no_go(r)

    def test_all_attempts_remain_zero_auto_resend(self):
        for r in (
            evaluate(self.f),
            evaluate(self.f, raw_evidence=[]),
            evaluate(self.f, signed_receipts=[]),
            evaluate(self.f, pinned_source_keys={}),
        ):
            self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
