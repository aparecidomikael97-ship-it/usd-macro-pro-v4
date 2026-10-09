"""Synthetic provider receipts + owner manual review after UNKNOWN_OUTCOME.

Every key in CI is disposable. No actual provider signs these fixtures.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import (
    INTENT_SCHEMA, ReferenceOneShotUnknownOutcomeJournal,
)
from atlasquant_aion_v2_dispatch_journal_dual_witness_reference import (
    canonical_dispatch_journal_read, unsigned_journal_head_candidate,
    local_journal_intent_commitment,
)
from atlasquant_aion_v2_unknown_outcome_reconciliation_reference import (
    PROVIDER_SCHEMA, REVIEW_SCHEMA, PROVIDER_PURPOSE, REVIEW_PURPOSE,
    PROVIDER_ROLE, REVIEW_ROLE,
    PROVIDER_CANDIDATE, REVIEW_CANDIDATE, ZERO,
    STATUS_PROCESSED, STATUS_NOT_FOUND, STATUS_UNCERTAIN,
    DECISION_KEEP_UNKNOWN, DECISION_ACK_PROCESSED,
    DECISION_ACK_NOT_FOUND,
    canonical_provider_observation, provider_observation_sha256,
    canonical_owner_review,
    review_provider_outcome_observation, review_manual_reconciliation_candidate,
)


def pin(k,name):
    return {
        "key_id":name,
        "public_key_hex":k.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex(),
    }


class UnknownOutcomeReconciliationReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.config={
            "owner_id":"owner","tenant_id":"tenant",
            "workspace_id":"workspace","period_id":"2026-10",
            "policy_generation":9,"max_period_micro_usd":500,
        }
        self.intent={
            "schema":INTENT_SCHEMA,"owner_id":"owner",
            "tenant_id":"tenant","workspace_id":"workspace",
            "conversation_id":"synthetic-conversation",
            "message_id":"synthetic-message",
            "nonce_hex":"a"*64,"signed_v2_intent_sha256":"b"*64,
            "full_provider_request_sha256":"c"*64,
            "primary_witness_receipt_sha256":"d"*64,
            "secondary_anchor_receipt_sha256":"e"*64,
            "key_registry_roster_sha256":"f"*64,
            "policy_generation":9,"period_id":"2026-10",
            "max_cost_micro_usd":100,
        }
        self.journal=ReferenceOneShotUnknownOutcomeJournal(
            Path(self.temp.name)/"journal.db",config=self.config,
        )
        self.primary=Ed25519PrivateKey.generate()
        self.anchor=Ed25519PrivateKey.generate()
        self.provider=Ed25519PrivateKey.generate()
        self.owner=Ed25519PrivateKey.generate()
        self.primary_pin=pin(self.primary,"primary-fixture")
        self.anchor_pin=pin(self.anchor,"anchor-fixture")
        self.provider_pin=pin(self.provider,"provider-fixture")
        self.owner_pin=pin(self.owner,"owner-fixture")
        self.n=0
        self.assertEqual(self.journal.prepare_reference_only(
            self.intent)["state"],"PREPARED_REFERENCE_ONLY")
        self.assertEqual(self.journal.claim_reference_only(
            intent=self.intent)["state"],
            "LOCAL_REFERENCE_CLAIM_RECORDED_UNTRUSTED")
        self.journal.mark_unknown_reference_only(nonce_hex=self.intent["nonce_hex"])
        self.head_args=self.make_heads()

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def q(self):
        self.n+=1
        return {
            "owner_id":"owner","tenant_id":"tenant",
            "workspace_id":"workspace","period_id":"2026-10",
            "policy_generation":9,
            "key_registry_roster_sha256":"f"*64,
            "nonce_hex":"a"*64,
            "challenge_nonce_hex":f"{self.n:064x}",
            "minimum_witness_epoch":4,
        }

    def head(self,q,role,key,p):
        payload=unsigned_journal_head_candidate(
            self.journal,intent=self.intent,query=q,role=role,
            signer_key_id=p["key_id"],witness_epoch=4,
        )
        return {
            "payload":payload,
            "signature_hex":key.sign(canonical_dispatch_journal_read(payload)).hex(),
        }

    def make_heads(self):
        q1=self.q()
        q2=self.q()
        return {
            "primary_read":self.head(q1,"PRIMARY_WITNESS",self.primary,self.primary_pin),
            "primary_pin":self.primary_pin,"primary_query":q1,
            "anchor_read":self.head(q2,"SECONDARY_ANCHOR",self.anchor,self.anchor_pin),
            "anchor_pin":self.anchor_pin,"anchor_query":q2,
        }

    def observation(self,status=STATUS_PROCESSED,*,response=None,cost=None):
        h=local_journal_intent_commitment(
            self.journal,intent=self.intent,
        )
        payload={
            "schema":PROVIDER_SCHEMA,"purpose":PROVIDER_PURPOSE,
            "role":PROVIDER_ROLE,"provider_key_id":self.provider_pin["key_id"],
            "provider_id":"synthetic-provider","provider_request_id":"synthetic-001",
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "period_id":"2026-10","policy_generation":9,
            "nonce_hex":self.intent["nonce_hex"],
            "signed_v2_intent_sha256":self.intent["signed_v2_intent_sha256"],
            "full_provider_request_sha256":self.intent["full_provider_request_sha256"],
            "key_registry_roster_sha256":self.intent["key_registry_roster_sha256"],
            "journal_snapshot_sha256":h["journal_snapshot_sha256"],
            "journal_sequence":h["journal_sequence"],
            "claim_sequence":h["claim_sequence"],
            "observation_status":status,
            "response_sha256":("1"*64 if status==STATUS_PROCESSED else ZERO)
                              if response is None else response,
            "reported_micro_usd":(50 if status==STATUS_PROCESSED else 0)
                                if cost is None else cost,
        }
        return {
            "payload":payload,
            "signature_hex":self.provider.sign(
                canonical_provider_observation(payload)
            ).hex(),
        }

    def review_envelope(self,obs,decision=DECISION_KEEP_UNKNOWN,*,challenge="4"*64):
        h=local_journal_intent_commitment(self.journal,intent=self.intent)
        payload={
            "schema":REVIEW_SCHEMA,"purpose":REVIEW_PURPOSE,
            "role":REVIEW_ROLE,"owner_review_key_id":self.owner_pin["key_id"],
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "period_id":"2026-10","policy_generation":9,
            "nonce_hex":self.intent["nonce_hex"],
            "signed_v2_intent_sha256":self.intent["signed_v2_intent_sha256"],
            "full_provider_request_sha256":self.intent["full_provider_request_sha256"],
            "journal_snapshot_sha256":h["journal_snapshot_sha256"],
            "journal_sequence":h["journal_sequence"],
            "claim_sequence":h["claim_sequence"],
            "provider_observation_sha256":provider_observation_sha256(obs),
            "decision_code":decision,"challenge_nonce_hex":challenge,
        }
        return {
            "payload":payload,"signature_hex":self.owner.sign(
                canonical_owner_review(payload)
            ).hex(),
        }

    def provider_check(self,obs=None,**kw):
        x=review_provider_outcome_observation(
            journal=self.journal,intent=self.intent,head_args=self.head_args,
            provider_envelope=self.observation() if obs is None else obs,
            provider_public_pin=kw.get("provider_public_pin",self.provider_pin),
        )
        self.no_authority(x)
        return x

    def owner_check(self,obs,review,*,challenge="4"*64,**kw):
        x=review_manual_reconciliation_candidate(
            journal=self.journal,intent=self.intent,head_args=self.head_args,
            provider_envelope=obs,
            provider_public_pin=kw.get("provider_public_pin",self.provider_pin),
            owner_review_envelope=review,
            owner_review_public_pin=kw.get("owner_review_public_pin",self.owner_pin),
            expected_new_challenge_nonce_hex=challenge,
        )
        self.no_authority(x)
        return x

    def no_authority(self,x):
        self.assertTrue(x["needs_human_reconciliation"])
        self.assertTrue(x["must_not_automatically_retry"])
        self.assertFalse(x["paid_dispatch_authorized"])
        self.assertFalse(x["automatic_retry_permitted"])
        self.assertFalse(x["same_nonce_reusable"])
        self.assertFalse(x["billing_settlement_verified"])
        self.assertFalse(x["provider_public_key_enrolled"])
        self.assertFalse(x["real_owner_identity_verified"])
        self.assertFalse(x["paid_provider_called"])
        self.assertFalse(x["network_called"])
        self.assertFalse(x["safe_to_resume"])

    def test_provider_processed_math_only_not_billing(self):
        o=self.provider_check()
        self.assertEqual(o["state"],PROVIDER_CANDIDATE)
        self.assertEqual(len(o["observation_sha256_math_only"]),64)
        self.assertFalse(o["real_charge_verified"])

    def test_owner_can_acknowledge_synthetic_processed_without_new_call(self):
        obs=self.observation()
        review=self.review_envelope(obs,DECISION_ACK_PROCESSED)
        o=self.owner_check(obs,review)
        self.assertEqual(o["state"],REVIEW_CANDIDATE)
        self.assertEqual(o["review_decision_math_only"],DECISION_ACK_PROCESSED)
        self.assertFalse(o["real_refund_authorized"])

    def test_not_found_is_not_proof_provider_never_processed(self):
        obs=self.observation(STATUS_NOT_FOUND)
        self.assertEqual(self.provider_check(obs)["state"],PROVIDER_CANDIDATE)
        o=self.owner_check(obs,self.review_envelope(obs,DECISION_ACK_NOT_FOUND))
        self.assertEqual(o["state"],REVIEW_CANDIDATE)
        self.assertTrue(o["reconciliation_not_actual_settlement"])
        self.assertFalse(o["actual_provider_idempotency_verified"])

    def test_uncertain_keeps_unknown_and_requires_reconciliation(self):
        obs=self.observation(STATUS_UNCERTAIN)
        o=self.owner_check(obs,self.review_envelope(obs,DECISION_KEEP_UNKNOWN))
        self.assertEqual(o["state"],REVIEW_CANDIDATE)
        self.assertFalse(o["provider_public_key_enrolled"])

    def test_never_acknowledge_processed_when_not_found(self):
        obs=self.observation(STATUS_NOT_FOUND)
        o=self.owner_check(obs,self.review_envelope(obs,DECISION_ACK_PROCESSED))
        self.assertEqual(o["reason"],"OWNER_DECISION_CONTRADICTS_OBSERVATION")

    def test_never_acknowledge_not_found_when_processed(self):
        obs=self.observation()
        o=self.owner_check(obs,self.review_envelope(obs,DECISION_ACK_NOT_FOUND))
        self.assertEqual(o["state"],"BLOCKED")

    def test_corrupt_provider_signature_fails_closed(self):
        obs=self.observation()
        obs["signature_hex"]="0"*128
        self.assertEqual(self.provider_check(obs)["reason"],
                         "PROVIDER_FIXTURE_SIGNATURE_INVALID")

    def test_replay_response_with_swapped_request_digest_fails(self):
        obs=self.observation()
        obs["payload"]["full_provider_request_sha256"]="0"*64
        obs["signature_hex"]=self.provider.sign(
            canonical_provider_observation(obs["payload"])
        ).hex()
        self.assertEqual(self.provider_check(obs)["reason"],
                         "PROVIDER_SIGNED_REQUEST_SCOPE_MISMATCH")

    def test_owner_signature_cannot_be_replaced_by_provider_signature(self):
        obs=self.observation()
        review=self.review_envelope(obs)
        review["signature_hex"]=obs["signature_hex"]
        self.assertEqual(self.owner_check(obs,review)["reason"],
                         "OWNER_REVIEW_SIGNATURE_INVALID")

    def test_owner_review_challenge_replay_blocks_new_expected_nonce(self):
        obs=self.observation()
        review=self.review_envelope(obs)
        self.assertEqual(self.owner_check(obs,review,challenge="5"*64)[
            "reason"],"OWNER_ROLE_PURPOSE_OR_NEW_CHALLENGE_MISMATCH")

    def test_previous_owner_review_rebound_to_different_evidence_blocks(self):
        obs=self.observation()
        review=self.review_envelope(obs)
        other=self.observation(STATUS_NOT_FOUND)
        self.assertEqual(self.owner_check(other,review)["reason"],
                         "OWNER_REVIEW_HEAD_OR_OBSERVATION_REBOUND")

    def test_provider_cannot_claim_processed_without_response_digest(self):
        obs=self.observation(response=ZERO)
        obs["signature_hex"]=self.provider.sign(
            canonical_provider_observation(obs["payload"])
        ).hex()
        self.assertEqual(self.provider_check(obs)["reason"],
                         "PROCESSED_OBSERVATION_MUST_BIND_RESPONSE_HASH")

    def test_not_found_cannot_assert_charge_or_response(self):
        obs=self.observation(STATUS_NOT_FOUND,cost=40)
        obs["signature_hex"]=self.provider.sign(
            canonical_provider_observation(obs["payload"])
        ).hex()
        self.assertEqual(self.provider_check(obs)["reason"],
                         "UNCONFIRMED_OBSERVATION_CANNOT_ASSERT_CHARGE_OR_RESPONSE")

    def test_modified_journal_without_new_dual_heads_fails(self):
        obs=self.observation()
        self.assertEqual(self.provider_check(obs)["state"],PROVIDER_CANDIDATE)
        self.journal.append_evidence_digest_reference_only(
            nonce_hex=self.intent["nonce_hex"],evidence_sha256="8"*64,
        )
        self.assertEqual(self.provider_check(obs)["reason"],
                         "DISPATCH_JOURNAL_NOT_DOUBLE_SIGNED_MATH_MATCHED")

    def test_malicious_fake_provider_root_still_passes_math_negative_control(self):
        fake=Ed25519PrivateKey.generate()
        substituted=pin(fake,"provider-fixture")
        obs=self.observation()
        obs["signature_hex"]=fake.sign(canonical_provider_observation(
            obs["payload"])).hex()
        result=self.provider_check(obs,provider_public_pin=substituted)
        self.assertEqual(result["state"],PROVIDER_CANDIDATE)
        self.assertFalse(result["true_provider_provenance_verified"])

    def test_fake_owner_root_math_valid_but_not_real_owner_presence(self):
        fake=Ed25519PrivateKey.generate()
        substitute=pin(fake,"owner-fixture")
        obs=self.observation()
        review=self.review_envelope(obs)
        review["signature_hex"]=fake.sign(canonical_owner_review(
            review["payload"])).hex()
        result=self.owner_check(
            obs,review,owner_review_public_pin=substitute,
        )
        self.assertEqual(result["state"],REVIEW_CANDIDATE)
        self.assertFalse(result["real_owner_identity_verified"])

    def test_two_conflicting_signed_fixture_observations_both_pass_math(self):
        confirmed=self.observation()
        absent=self.observation(STATUS_NOT_FOUND)
        self.assertEqual(self.provider_check(confirmed)["state"],PROVIDER_CANDIDATE)
        self.assertEqual(self.provider_check(absent)["state"],PROVIDER_CANDIDATE)
        # Both signatures passing mathematics is precisely why a real
        # authoritative provider transcript and replay registry are required.
        self.assertFalse(self.provider_check(absent)[
            "true_provider_provenance_verified"])

    def test_unauthenticated_or_wrong_schema_fields_block(self):
        obs=self.observation()
        for key in list(obs["payload"]):
            with self.subTest(key=key):
                bad=deepcopy(obs)
                bad["payload"].pop(key)
                self.assertEqual(self.provider_check(bad)["state"],"BLOCKED")
        review=self.review_envelope(obs)
        for key in list(review["payload"]):
            with self.subTest(review_field=key):
                bad=deepcopy(review)
                bad["payload"].pop(key)
                self.assertEqual(self.owner_check(obs,bad)["state"],"BLOCKED")

    def test_nonce_scope_and_claim_sequence_tampering_detected(self):
        for k,v in (
            ("nonce_hex","1"*64),("tenant_id","other"),
            ("claim_sequence",99),("journal_snapshot_sha256","0"*64),
        ):
            with self.subTest(field=k):
                obs=self.observation()
                obs["payload"][k]=v
                obs["signature_hex"]=self.provider.sign(
                    canonical_provider_observation(obs["payload"])
                ).hex()
                self.assertEqual(self.provider_check(obs)["state"],"BLOCKED")

    def test_same_review_challenge_can_replay_if_caller_reuses_it(self):
        obs=self.observation()
        review=self.review_envelope(obs)
        self.assertEqual(self.owner_check(obs,review)["state"],REVIEW_CANDIDATE)
        self.assertEqual(self.owner_check(obs,review)["state"],REVIEW_CANDIDATE)
        self.assertFalse(self.owner_check(obs,review)[
            "witness_heads_independently_fresh"])

    def test_no_http_no_provider_even_for_valid_math(self):
        obs=self.observation()
        review=self.review_envelope(obs)
        with patch("requests.post",side_effect=AssertionError("network")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("model")):
            self.assertEqual(self.provider_check(obs)["state"],PROVIDER_CANDIDATE)
            self.assertEqual(self.owner_check(obs,review)["state"],REVIEW_CANDIDATE)


if __name__=="__main__":
    unittest.main()
