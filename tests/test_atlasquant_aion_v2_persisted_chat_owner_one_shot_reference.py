"""Real scoped SQLite pending USER message + V2 owner signature + one local claim.

All identity authority inputs remain test fixtures. Zero network and no
global exactly-once or permission for a paid request.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_pending_model_turn_v1 import stage_pending_model_user_turn
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
from atlasquant_aion_v2_persisted_chat_owner_one_shot_reference import (
    MATCH,BURN,NO_AUTH,
    review_persisted_owner_preclaim_reference,
    consume_persisted_owner_local_reference_only,
)


def pin(key,identifier):
    return {
        "key_id":identifier,
        "public_key_hex":key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex(),
    }


def access(username="owner",role="ADMIN",allowed=True,mode="AUTHENTICATED"):
    return {
        "allowed":allowed,"mode":mode,"role":role,
        "session":{
            "role":role,"username":username,
            "credential_fingerprint":"ci-fingerprint-placeholder",
            "permissions":["app:read","aion:admin"],
        },
    }


class PersistedSignedOneShotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.scope=Scope("owner","tenant","workspace")
        self.store=SQLiteChatStore(Path(self.tmp.name)/"chat.db")
        self.cid=self.store.create_conversation(self.scope,"AION").id
        self.source="Explique inflação e seus efeitos"
        self.pending=stage_pending_model_user_turn(
            self.store,self.scope,access(),
            conversation_id=self.cid,request_id="signed-session-20261009",
            message=self.source,
        )
        self.mid=self.pending["message_id"]
        self.prompt="Responda em português sobre macroeconomia: "+self.source
        self.values={
            "AION_MODEL_PROVIDER":"openai",
            "OPENAI_API_KEY":"test-only-NEVER-valid",
            "AION_OPENAI_FAST_MODEL":"mock-fast-model",
            "AION_OPENAI_REASONING_MODEL":"mock-reasoning-model",
            "AION_OPENAI_INPUT_USD_PER_MTOK":"1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK":"2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS":"400",
            "AION_OPENAI_TIMEOUT_SECONDS":"45",
        }
        self.preview=preview_openai_request_binding(
            self.prompt,lane="EXTERNAL_FAST",values=self.values,
        )
        self.owner=Ed25519PrivateKey.generate()
        self.primary=Ed25519PrivateKey.generate()
        self.secondary=Ed25519PrivateKey.generate()
        self.pin_owner=pin(self.owner,"owner-fixture-key")
        self.pin_primary=pin(self.primary,"primary-fixture-key")
        self.pin_secondary=pin(self.secondary,"secondary-fixture-key")
        self.payload={
            "schema":APPROVAL_SCHEMA,"purpose":PURPOSE,"role":ROLE,
            "owner_key_id":self.pin_owner["key_id"],
            "owner_id":self.scope.owner_id,
            "tenant_id":self.scope.tenant_id,
            "workspace_id":self.scope.workspace_id,
            "conversation_id":self.cid,
            "message_id":self.mid,
            "request_digest":self.pending["request_digest"],
            "source_message_sha256":sha256(self.source.encode()).hexdigest(),
            "final_prompt_sha256":self.preview["final_prompt_sha256"],
            "full_provider_request_sha256":self.preview["request_sha256"],
            "provider_id":"openai",
            "model_id":self.preview["resolved_model"],
            "lane":"EXTERNAL_FAST",
            "endpoint":self.preview["endpoint"],
            "max_output_tokens":self.preview["max_output_tokens"],
            "timeout_seconds_repr":repr(self.preview["timeout_seconds"]),
            "max_cost_micro_usd":2000,"policy_generation":7,
            "nonce_hex":"ac"*32,
        }
        self.env=self.envelope()
        self.config={
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "period_id":"2026-10","policy_generation":7,
            "max_period_micro_usd":10000,
        }
        self.intent={
            "schema":INTENT_SCHEMA,
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "conversation_id":self.cid,"message_id":self.mid,
            "nonce_hex":self.payload["nonce_hex"],
            "signed_v2_intent_sha256":sha256(
                canonical_full_request_approval_v2(self.payload)
            ).hexdigest(),
            "full_provider_request_sha256":self.preview["request_sha256"],
            "primary_witness_receipt_sha256":"d"*64,
            "secondary_anchor_receipt_sha256":"e"*64,
            "key_registry_roster_sha256":"f"*64,
            "policy_generation":7,"period_id":"2026-10",
            "max_cost_micro_usd":2000,
        }
        self.journal=ReferenceOneShotUnknownOutcomeJournal(
            Path(self.tmp.name)/"journal.db",config=self.config,
        )
        self.assertEqual(self.journal.prepare_reference_only(
            self.intent)["state"],"PREPARED_REFERENCE_ONLY")
        self.heads=self.make_heads()

    def tearDown(self):
        self.journal.close()
        self.store.db.close()
        self.tmp.cleanup()

    def envelope(self,body=None,key=None):
        payload=deepcopy(body if body is not None else self.payload)
        return {
            "payload":payload,
            "signature_hex":(key or self.owner).sign(
                canonical_full_request_approval_v2(payload)
            ).hex(),
        }

    def make_heads(self):
        shared={
            "owner_id":"owner","tenant_id":"tenant",
            "workspace_id":"workspace","period_id":"2026-10",
            "policy_generation":7,
            "key_registry_roster_sha256":"f"*64,
            "nonce_hex":self.payload["nonce_hex"],
            "minimum_witness_epoch":4,
        }
        def signed(role,key,keypin,char):
            query={**shared,"challenge_nonce_hex":char*64}
            payload=unsigned_journal_head_candidate(
                self.journal,intent=self.intent,query=query,
                role=role,signer_key_id=keypin["key_id"],
                witness_epoch=4,
            )
            return query,{
                "payload":payload,"signature_hex":key.sign(
                    canonical_dispatch_journal_read(payload)
                ).hex(),
            }
        pq,pr=signed("PRIMARY_WITNESS",self.primary,self.pin_primary,"5")
        aq,ar=signed("SECONDARY_ANCHOR",self.secondary,self.pin_secondary,"6")
        return {
            "primary_read":pr,"primary_pin":self.pin_primary,
            "primary_query":pq,"anchor_read":ar,
            "anchor_pin":self.pin_secondary,"anchor_query":aq,
        }

    def args(self,**overrides):
        d={
            "store":self.store,"scope":self.scope,"access":access(),
            "journal":self.journal,"intent":self.intent,
            "conversation_id":self.cid,"message_id":self.mid,
            "final_prompt":self.prompt,"owner_envelope":self.env,
            "owner_public_pin":self.pin_owner,"witness_heads":self.heads,
            "lane":"EXTERNAL_FAST","provider_values":self.values,
            "expected_policy_generation":7,"host_quote_micro_usd":1000,
        }
        d.update(overrides)
        return d

    def review(self,**kwargs):
        result=review_persisted_owner_preclaim_reference(
            **self.args(**kwargs)
        )
        self.no_authority(result)
        return result

    def burn(self,**kwargs):
        result=consume_persisted_owner_local_reference_only(
            **self.args(**kwargs)
        )
        self.no_authority(result)
        return result

    def no_authority(self,result):
        self.assertTrue(result["must_not_automatically_retry"])
        for key,val in NO_AUTH.items():
            self.assertIs(result[key],val,key)

    def test_stored_pending_session_signature_witness_match_math_only(self):
        self.assertEqual(self.review()["state"],MATCH)
        self.assertFalse(self.review()["host_access_is_independently_authenticated"])

    def test_stored_pending_before_one_local_burn_and_no_paid_permission(self):
        self.assertEqual(self.burn()["state"],BURN)
        self.assertEqual(self.burn()["state"],"BLOCKED")
        self.assertFalse(self.review()["paid_dispatch_authorized"])
        self.assertEqual(self.journal.read_reference_only(
            nonce_hex=self.intent["nonce_hex"]
        )["stored_reference_state"],"DISPATCH_CLAIMED")

    def test_fake_owner_public_pin_and_forged_signed_turn_math_only(self):
        attacker=Ed25519PrivateKey.generate()
        fraudulent=self.envelope(key=attacker)
        result=self.review(
            owner_envelope=fraudulent,
            owner_public_pin=pin(attacker,self.pin_owner["key_id"]),
        )
        self.assertEqual(result["state"],MATCH)
        self.assertFalse(result["owner_enrollment_verified"])
        self.assertFalse(result["host_access_is_independently_authenticated"])

    def test_session_user_role_and_mode_mismatch_block(self):
        for cred in (
            access(username="someone-else"),
            access(role="VIEWER"),
            access(allowed=False),
            access(mode="ANONYMOUS"),
            {"allowed":True},
        ):
            with self.subTest(cred=repr(cred)[:70]):
                self.assertEqual(self.burn(access=cred)["state"],"BLOCKED")
        self.assertEqual(self.review()["state"],MATCH)

    def test_scoped_owner_tenant_workspace_swap_blocks(self):
        for scope in (
            Scope("intruder","tenant","workspace"),
            Scope("owner","other-tenant","workspace"),
            Scope("owner","tenant","other-workspace"),
        ):
            with self.subTest(scope=scope):
                self.assertEqual(self.burn(scope=scope)["state"],"BLOCKED")

    def test_different_conversation_message_or_intent_scope_blocks(self):
        for change in (
            {"conversation_id":"other-conversation"},
            {"message_id":"other-message"},
            {"expected_policy_generation":8},
            {"host_quote_micro_usd":3000},
        ):
            with self.subTest(change=change):
                self.assertEqual(self.burn(**change)["state"],"BLOCKED")

    def test_stored_pending_user_content_tamper_blocks(self):
        self.store.db.execute(
            "UPDATE messages SET data=replace(data, ?, ?) WHERE id=?",
            (self.source,"conteúdo alterado",self.mid),
        )
        self.assertEqual(self.burn()["state"],"BLOCKED")
        self.assertEqual(self.journal.read_reference_only(
            nonce_hex=self.intent["nonce_hex"]
        )["stored_reference_state"],"PREPARED")

    def test_pending_metadata_elevation_blocks(self):
        self.store.db.execute(
            "UPDATE messages SET data=replace(data, ?, ?) WHERE id=?",
            ('"approval_state": "PENDING"',
             '"approval_state": "APPROVED"',self.mid),
        )
        self.assertEqual(self.burn()["state"],"BLOCKED")

    def test_signed_prompt_or_host_provider_settings_changed_blocks(self):
        self.assertEqual(self.burn(final_prompt=self.prompt+" mudado")[
            "state"],"BLOCKED")
        changed={**self.values,"AION_OPENAI_FAST_MODEL":"different-model"}
        self.assertEqual(self.burn(provider_values=changed)["state"],"BLOCKED")
        self.assertEqual(self.review()["state"],MATCH)

    def test_tampered_signature_or_nonce_blocks_without_consuming(self):
        changed=deepcopy(self.env)
        changed["signature_hex"]="0"*128
        self.assertEqual(self.burn(owner_envelope=changed)["state"],"BLOCKED")
        changed=deepcopy(self.payload)
        changed["nonce_hex"]="bb"*32
        self.assertEqual(self.burn(owner_envelope=self.envelope(changed))[
            "state"],"BLOCKED")
        self.assertEqual(self.review()["state"],MATCH)

    def test_missing_secondary_witness_blocks(self):
        altered=deepcopy(self.heads)
        altered["anchor_read"]=None
        self.assertEqual(self.burn(witness_heads=altered)["state"],"BLOCKED")

    def test_lost_access_revocation_before_claim_blocks(self):
        self.assertEqual(self.review()["state"],MATCH)
        self.assertEqual(self.burn(access=access(allowed=False))[
            "state"],"BLOCKED")

    def test_test_fake_authenticated_access_is_not_real_identity(self):
        self.assertEqual(self.review()["state"],MATCH)
        self.assertFalse(self.review()[
            "session_freshness_and_revocation_verified"
        ])

    def test_no_network_when_reference_consumes_local_nonce(self):
        with patch("requests.sessions.Session.send",
                   side_effect=AssertionError("no network")), \
             patch("requests.post",side_effect=AssertionError("no API")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("no model")):
            self.assertEqual(self.burn()["state"],BURN)
        self.assertFalse(self.burn()["network_called"])

    def test_reviewing_again_after_claim_rejects_old_signed_prepared_heads(self):
        self.burn()
        self.assertEqual(self.review()["state"],"BLOCKED")

    def test_message_changes_between_initial_and_second_read_block(self):
        import atlasquant_aion_v2_persisted_chat_owner_one_shot_reference as composed
        original=composed._verify_all
        count=[0]
        def mutate_after_first(**kwargs):
            result=original(**kwargs)
            count[0]+=1
            if count[0]==1:
                self.store.db.execute(
                    "UPDATE messages SET data=replace(data, ?, ?) WHERE id=?",
                    (self.source,"conteúdo concorrente adulterado",self.mid),
                )
            return result
        with patch.object(composed,"_verify_all",side_effect=mutate_after_first):
            result=self.burn()
        self.assertEqual(result["state"],"BLOCKED")
        self.assertEqual(self.journal.read_reference_only(
            nonce_hex=self.intent["nonce_hex"]
        )["stored_reference_state"],"PREPARED")

    def test_cloned_sqlite_and_old_signature_math_not_external_rollback_proof(self):
        self.assertEqual(self.review()["state"],MATCH)
        self.assertFalse(self.review()["chat_store_is_remote_antirollback_protected"])
        self.assertFalse(self.review()["external_antirollback_verified"])


if __name__=="__main__":
    unittest.main()
