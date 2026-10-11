"""Owner-signed V2 + real POST preview + dual-witness PREPARED local CAS tests.

All keys and IDs are synthetic. Nothing permits a paid API request or real
owner/witness identity. Includes deliberate fake-root negative control.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_chat_signed_full_request_review_v2 import (
    APPROVAL_SCHEMA,PURPOSE,ROLE,canonical_full_request_approval_v2,
)
from atlasquant_aion_provider import preview_openai_request_binding
from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import (
    INTENT_SCHEMA,ReferenceOneShotUnknownOutcomeJournal,
)
from atlasquant_aion_v2_dispatch_journal_dual_witness_reference import (
    unsigned_journal_head_candidate,canonical_dispatch_journal_read,
)
from atlasquant_aion_v2_owner_signed_one_shot_admission_reference import (
    MATH_CANDIDATE,LOCAL_BURN,NO_GO,
    review_owner_signed_preclaim_reference,
    consume_one_local_reference_claim_only,
)


def pin(key,name):
    return {
        "key_id":name,
        "public_key_hex":key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex(),
    }


class OwnerOneShotComposedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db_path=Path(self.tmp.name)/"one-shot.db"
        self.config={
            "owner_id":"owner-fixture","tenant_id":"tenant-fixture",
            "workspace_id":"workspace-fixture","period_id":"2026-10",
            "policy_generation":9,"max_period_micro_usd":500,
        }
        self.v={
            "AION_MODEL_PROVIDER":"openai",
            "OPENAI_API_KEY":"invalid-fixture-token-never-real",
            "AION_OPENAI_FAST_MODEL":"fixture-fast",
            "AION_OPENAI_REASONING_MODEL":"fixture-reason",
            "AION_OPENAI_INPUT_USD_PER_MTOK":"1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK":"2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS":"100",
            "AION_OPENAI_TIMEOUT_SECONDS":"8",
        }
        self.prompt="Pedido de teste sem informações privadas"
        self.lane="EXTERNAL_FAST"
        self.owner_key=Ed25519PrivateKey.generate()
        self.primary_key=Ed25519PrivateKey.generate()
        self.anchor_key=Ed25519PrivateKey.generate()
        self.owner_pin=pin(self.owner_key,"owner-key-ci")
        self.primary_pin=pin(self.primary_key,"primary-ci")
        self.anchor_pin=pin(self.anchor_key,"secondary-ci")
        self.preview=preview_openai_request_binding(
            self.prompt,lane=self.lane,values=self.v,
        )
        self.assertEqual(self.preview["state"],"BOUND_REQUEST_PREVIEW_UNTRUSTED")
        self.p=self.make_payload()
        self.env=self.envelope()
        signed=canonical_full_request_approval_v2(self.p)
        self.intent={
            "schema":INTENT_SCHEMA,
            "owner_id":self.config["owner_id"],
            "tenant_id":self.config["tenant_id"],
            "workspace_id":self.config["workspace_id"],
            "conversation_id":self.p["conversation_id"],
            "message_id":self.p["message_id"],
            "nonce_hex":self.p["nonce_hex"],
            "signed_v2_intent_sha256":sha256(signed).hexdigest(),
            "full_provider_request_sha256":self.preview["request_sha256"],
            "primary_witness_receipt_sha256":"d"*64,
            "secondary_anchor_receipt_sha256":"e"*64,
            "key_registry_roster_sha256":"f"*64,
            "policy_generation":9,"period_id":"2026-10",
            "max_cost_micro_usd":100,
        }
        self.journal=ReferenceOneShotUnknownOutcomeJournal(
            self.db_path,config=self.config,
        )
        self.assertEqual(
            self.journal.prepare_reference_only(self.intent)["state"],
            "PREPARED_REFERENCE_ONLY",
        )
        self.heads=self.make_heads()

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def make_payload(self):
        return {
            "schema":APPROVAL_SCHEMA,"purpose":PURPOSE,"role":ROLE,
            "owner_key_id":self.owner_pin["key_id"],
            "owner_id":self.config["owner_id"],
            "tenant_id":self.config["tenant_id"],
            "workspace_id":self.config["workspace_id"],
            "conversation_id":"ci-conversation",
            "message_id":"ci-message",
            "request_digest":"1"*64,
            "source_message_sha256":"2"*64,
            "final_prompt_sha256":self.preview["final_prompt_sha256"],
            "full_provider_request_sha256":self.preview["request_sha256"],
            "provider_id":"openai","model_id":self.preview["resolved_model"],
            "lane":self.lane,"endpoint":self.preview["endpoint"],
            "max_output_tokens":self.preview["max_output_tokens"],
            "timeout_seconds_repr":repr(self.preview["timeout_seconds"]),
            "max_cost_micro_usd":100,
            "policy_generation":9,"nonce_hex":"a"*64,
        }

    def envelope(self,key=None,payload=None):
        body=self.p if payload is None else payload
        return {
            "payload":body,
            "signature_hex":(key or self.owner_key).sign(
                canonical_full_request_approval_v2(body)
            ).hex(),
        }

    def make_heads(self):
        base={
            "owner_id":self.config["owner_id"],
            "tenant_id":self.config["tenant_id"],
            "workspace_id":self.config["workspace_id"],
            "period_id":self.config["period_id"],
            "policy_generation":9,
            "key_registry_roster_sha256":self.intent["key_registry_roster_sha256"],
            "nonce_hex":self.intent["nonce_hex"],
            "minimum_witness_epoch":4,
        }
        def signed(role,key,pin,name):
            q={**base,"challenge_nonce_hex":name*64}
            payload=unsigned_journal_head_candidate(
                self.journal,intent=self.intent,query=q,
                role=role,signer_key_id=pin["key_id"],
                witness_epoch=4,
            )
            return q,{
                "payload":payload,
                "signature_hex":key.sign(
                    canonical_dispatch_journal_read(payload)
                ).hex(),
            }
        pq,pr=signed("PRIMARY_WITNESS",self.primary_key,
                     self.primary_pin,"5")
        aq,ar=signed("SECONDARY_ANCHOR",self.anchor_key,
                     self.anchor_pin,"6")
        return {
            "primary_read":pr,"primary_pin":self.primary_pin,
            "primary_query":pq,
            "anchor_read":ar,"anchor_pin":self.anchor_pin,
            "anchor_query":aq,
        }

    def kwargs(self,**override):
        d={
            "journal":self.journal,"intent":self.intent,
            "owner_envelope":self.env,"owner_public_pin":self.owner_pin,
            "witness_heads":self.heads,"final_prompt":self.prompt,
            "lane":self.lane,"provider_values":self.v,
            "original_message_sha256_assertion":"2"*64,
            "original_request_digest_assertion":"1"*64,
            "quoted_micro_usd":50,
        }
        d.update(override)
        return d

    def assert_no_go(self,result):
        self.assertTrue(result["must_not_automatically_retry"])
        for k,v in NO_GO.items():
            self.assertIs(result[k],v,k)

    def review(self,**override):
        r=review_owner_signed_preclaim_reference(**self.kwargs(**override))
        self.assert_no_go(r)
        return r

    def burn(self,**override):
        r=consume_one_local_reference_claim_only(**self.kwargs(**override))
        self.assert_no_go(r)
        return r

    def test_math_candidate_only_never_provider_permission(self):
        r=self.review()
        self.assertEqual(r["state"],MATH_CANDIDATE)
        self.assertTrue(r["signature_math_and_local_state_only"])
        self.assertEqual(
            r["reference_full_request_sha256"],self.preview["request_sha256"],
        )
        self.assertFalse(r["original_user_message_persisted_verified"])

    def test_once_local_burn_cannot_dispatch_even_after_math(self):
        self.assertEqual(self.burn()["state"],LOCAL_BURN)
        self.assertFalse(self.burn()["paid_dispatch_authorized"])
        self.assertEqual(self.burn()["state"],"BLOCKED")
        self.assertEqual(self.review()["state"],"BLOCKED")
        observed=self.journal.read_reference_only(
            nonce_hex=self.intent["nonce_hex"]
        )
        self.assertEqual(observed["stored_reference_state"],"DISPATCH_CLAIMED")
        self.assertTrue(observed["must_not_automatically_retry"])

    def test_after_crash_local_claim_still_burns_nonce(self):
        self.burn()
        self.journal.close()
        self.journal=ReferenceOneShotUnknownOutcomeJournal(
            self.db_path,config=self.config,
        )
        self.assertEqual(self.burn()["state"],"BLOCKED")
        self.assertEqual(
            self.journal.read_reference_only(
                nonce_hex=self.intent["nonce_hex"]
            )["stored_reference_state"],"DISPATCH_CLAIMED",
        )

    def test_unknown_outcome_never_reopens_authorization(self):
        self.burn()
        self.journal.mark_unknown_reference_only(
            nonce_hex=self.intent["nonce_hex"]
        )
        self.assertEqual(self.burn()["state"],"BLOCKED")
        self.assertFalse(self.review()["real_post_authorized"])

    def test_signature_corruption_blocks_without_burning(self):
        e=deepcopy(self.env)
        e["signature_hex"]="0"*128
        r=self.burn(owner_envelope=e)
        self.assertEqual(r["reason"],"OWNER_V2_SIGNATURE_INVALID")
        self.assertEqual(self.review()["state"],MATH_CANDIDATE)

    def test_owner_signer_pin_swap_attacker_negative_control(self):
        attacker=Ed25519PrivateKey.generate()
        fraudulent=self.envelope(key=attacker)
        fake_pin=pin(attacker,self.owner_pin["key_id"])
        r=self.review(owner_envelope=fraudulent,owner_public_pin=fake_pin)
        self.assertEqual(r["state"],MATH_CANDIDATE)
        self.assertFalse(r["owner_enrollment_verified"])
        self.assertFalse(r["owner_presence_verified"])

    def test_owner_wrong_key_without_substitution_blocks(self):
        fake=Ed25519PrivateKey.generate()
        r=self.burn(owner_envelope=self.envelope(key=fake))
        self.assertEqual(r["state"],"BLOCKED")

    def test_different_signed_nonce_and_recomputed_digest_cannot_replace_prepared(self):
        bad=deepcopy(self.p)
        bad["nonce_hex"]="b"*64
        e=self.envelope(payload=bad)
        r=self.burn(owner_envelope=e)
        self.assertEqual(r["reason"],"OWNER_SIGNED_SCOPE_INTENT_OR_NONCE_REBOUND")

    def test_same_payload_changed_provider_model_or_transport_blocks(self):
        for field,value in (
            ("model_id","attacker-model"),
            ("lane","EXTERNAL_REASONING"),
            ("endpoint","https://elsewhere.example/v1/responses"),
            ("max_output_tokens",500),
            ("timeout_seconds_repr","4.0"),
        ):
            with self.subTest(field=field):
                bad=deepcopy(self.p)
                bad[field]=value
                e=self.envelope(payload=bad)
                self.assertEqual(self.burn(owner_envelope=e)["state"],"BLOCKED")

    def test_resolved_provider_values_change_after_owner_signature_blocks(self):
        for name,value in (
            ("AION_OPENAI_FAST_MODEL","other-model"),
            ("AION_OPENAI_MAX_OUTPUT_TOKENS","200"),
            ("AION_OPENAI_TIMEOUT_SECONDS","10"),
        ):
            with self.subTest(name=name):
                v={**self.v,name:value}
                self.assertEqual(self.burn(provider_values=v)["reason"],
                                 "SIGNED_FULL_PROVIDER_POST_OR_TRANSPORT_CHANGED")

    def test_untrusted_original_message_digest_assertion_cannot_be_swapped(self):
        self.assertEqual(
            self.burn(original_message_sha256_assertion="3"*64)["state"],
            "BLOCKED",
        )
        self.assertEqual(
            self.burn(original_request_digest_assertion="4"*64)["state"],
            "BLOCKED",
        )

    def test_overquote_or_bool_quote_does_not_consume(self):
        for quote in (101,0,True,"50",None):
            with self.subTest(quote=repr(quote)):
                self.assertEqual(
                    self.burn(quoted_micro_usd=quote)["state"],"BLOCKED",
                )
        self.assertEqual(self.review()["state"],MATH_CANDIDATE)

    def test_second_witness_missing_fails_closed(self):
        v=deepcopy(self.heads)
        v["anchor_read"]=None
        self.assertEqual(
            self.burn(witness_heads=v)["reason"],
            "NO_FRESH_PREPARED_TWO_WITNESS_REFERENCE",
        )

    def test_witness_challenge_replay_fails_closed(self):
        v=deepcopy(self.heads)
        v["primary_query"]["challenge_nonce_hex"]="7"*64
        self.assertEqual(self.burn(witness_heads=v)["state"],"BLOCKED")

    def test_journal_already_claimed_by_other_call_blocks_after_preflight(self):
        self.journal.claim_reference_only(intent=self.intent)
        self.assertEqual(self.burn()["state"],"BLOCKED")

    def test_dual_signature_heads_can_be_faked_with_substituted_pins(self):
        # Mathematical match does NOT prove two independent trust domains.
        attacker=Ed25519PrivateKey.generate()
        forged=deepcopy(self.heads)
        forged["anchor_pin"]=pin(attacker,self.anchor_pin["key_id"])
        forged["anchor_read"]["signature_hex"]=attacker.sign(
            canonical_dispatch_journal_read(
                forged["anchor_read"]["payload"],
            )
        ).hex()
        result=self.review(witness_heads=forged)
        self.assertEqual(result["state"],MATH_CANDIDATE)
        self.assertFalse(result["noncolluding_signed_witnesses_enrolled"])

    def test_concurrent_claims_one_burn_no_network(self):
        def worker(_):
            j=ReferenceOneShotUnknownOutcomeJournal(
                self.db_path,config=self.config,
            )
            try:
                return consume_one_local_reference_claim_only(
                    **self.kwargs(journal=j),
                )["state"]
            finally:
                j.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            states=list(pool.map(worker,range(7)))
        self.assertEqual(states.count(LOCAL_BURN),1)
        self.assertEqual(states.count("BLOCKED"),6)
        self.assertEqual(
            self.journal.read_reference_only(
                nonce_hex=self.intent["nonce_hex"]
            )["stored_reference_state"],"DISPATCH_CLAIMED",
        )

    def test_no_http_even_on_successful_reference_burn(self):
        with patch("requests.sessions.Session.send",
                   side_effect=AssertionError("NO paid request")), \
             patch("requests.post",side_effect=AssertionError("NO request")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("NO model")):
            self.assertEqual(self.burn()["state"],LOCAL_BURN)
        self.assertFalse(self.burn()["network_called"])

    def test_closed_schema_extra_authority_injection_rejected(self):
        e=deepcopy(self.env)
        e["payload"]["paid_dispatch_authorized"]=True
        self.assertEqual(self.burn(owner_envelope=e)["state"],"BLOCKED")

    def test_restored_local_journal_and_old_heads_can_repass_math_negative(self):
        # The reference has no non-restorable external root. Older local
        # database + older two witness responses could pass math again.
        self.assertEqual(self.review()["state"],MATH_CANDIDATE)
        self.assertFalse(self.review()["external_antirollback_verified"])


if __name__=="__main__":
    unittest.main()
