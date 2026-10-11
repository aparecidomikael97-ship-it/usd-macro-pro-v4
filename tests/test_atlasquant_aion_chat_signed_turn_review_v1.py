"""Adversarial cryptographic-only owner turn consent review in disposable CI.

Keys generated only inside the test process; no real HUMAN_OWNER enrollment.
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
from atlasquant_aion_chat_signed_turn_review_v1 import (
    APPROVAL_SCHEMA, CANDIDATE, DOMAIN, FALSE_GATES, PURPOSE, ROLE, SCHEMA,
    canonical_approval_message, review_signed_pending_model_turn,
)

_UNSET_ENVELOPE = object()


def access(username="owner", *, allowed=True, role="ADMIN"):
    return {
        "allowed": allowed, "mode": "AUTHENTICATED", "role": role,
        "session": {"role": role, "username": username,
                    "credential_fingerprint": "synthetic-fingerprint",
                    "permissions": ["app:read", "aion:admin"]},
    }


class SignedReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SQLiteChatStore(Path(self.temp.name) / "chat.db")
        self.scope = Scope("owner","tenant","workspace")
        self.cid = self.store.create_conversation(self.scope,"AION").id
        self.source = "Explique inflação e seus efeitos"
        self.pending = stage_pending_model_user_turn(
            self.store,self.scope,access(),
            conversation_id=self.cid,request_id="request-123456",
            message=self.source,
        )
        self.prompt = "Responda em português claro: "+self.source
        self.key = Ed25519PrivateKey.generate()
        self.public = self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
        self.pin = {"key_id":"synthetic-owner-key-v1",
                    "public_key_hex":self.public}
        self.payload = {
            "schema":APPROVAL_SCHEMA,
            "purpose":PURPOSE,
            "role":ROLE,
            "owner_key_id":self.pin["key_id"],
            "owner_id":self.scope.owner_id,
            "tenant_id":self.scope.tenant_id,
            "workspace_id":self.scope.workspace_id,
            "conversation_id":self.cid,
            "message_id":self.pending["message_id"],
            "request_digest":self.pending["request_digest"],
            "source_message_sha256":sha256(self.source.encode()).hexdigest(),
            "final_prompt_sha256":sha256(self.prompt.encode()).hexdigest(),
            "provider_id":"openai",
            "model_id":"gpt-test-mock",
            "lane":"EXTERNAL_FAST",
            "max_cost_micro_usd":100,
            "policy_generation":7,
            "nonce_hex":"ab"*32,
        }

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def signed(self,payload=None,key=None):
        payload=deepcopy(self.payload if payload is None else payload)
        sign_key=key or self.key
        return {"payload":payload,
                "signature_hex":sign_key.sign(
                    canonical_approval_message(payload)
                ).hex()}

    def review(self,envelope=_UNSET_ENVELOPE,**overrides):
        x={"store":self.store,"scope":self.scope,"access":access(),
           "conversation_id":self.cid,"message_id":self.pending["message_id"],
           "final_prompt":self.prompt,
           "envelope":self.signed() if envelope is _UNSET_ENVELOPE else envelope,
           "host_public_pin":self.pin,"expected_policy_generation":7}
        x.update(overrides)
        r=review_signed_pending_model_turn(
            x["store"],x["scope"],x["access"],
            conversation_id=x["conversation_id"],message_id=x["message_id"],
            final_prompt=x["final_prompt"],envelope=x["envelope"],
            host_public_pin=x["host_public_pin"],
            expected_policy_generation=x["expected_policy_generation"],
        )
        self.assertEqual(r["schema"],SCHEMA)
        self.assertTrue(r["reference_only"])
        for flag,val in FALSE_GATES.items():
            self.assertIs(r[flag],val,flag)
        return r

    def test_complete_signature_still_not_authorization(self):
        r=self.review()
        self.assertEqual(r["state"],CANDIDATE)
        self.assertTrue(r["public_signature_math_valid"])
        self.assertTrue(r["scope_and_stored_message_matched"])
        self.assertFalse(r["external_model_request_approved"])
        self.assertFalse(r["nonce_reserved_or_consumed"])
        self.assertFalse(r["provider_called"])
        self.assertEqual(len(r["signed_payload_sha256"]),64)

    def test_identical_signed_turn_replay_remains_only_untrusted_math(self):
        e=self.signed()
        a=self.review(e)
        b=self.review(e)
        self.assertEqual(a,b)
        self.assertFalse(b["anti_replay_verified"])
        self.assertEqual(self.store.get_conversation(self.scope,self.cid).message_count,1)

    def test_signature_domain_separation(self):
        self.assertTrue(DOMAIN.endswith(b"\x00"))
        self.assertIn(b"OWNER_MODEL_APPROVAL",DOMAIN)
        self.assertEqual(self.review()["state"],CANDIDATE)

    def test_corrupted_signature_is_blocked(self):
        e=self.signed()
        sig=e["signature_hex"]
        e["signature_hex"]=("a" if sig[0]!="a" else "b")+sig[1:]
        self.assertEqual(self.review(e)["reason"],"OWNER_SIGNATURE_MATH_INVALID")

    def test_signature_by_wrong_key_is_blocked(self):
        attacker=Ed25519PrivateKey.generate()
        self.assertEqual(self.review(self.signed(key=attacker))["state"],"BLOCKED")

    def test_user_supplied_pin_replacement_is_not_accepted_against_host_pin(self):
        attacker=Ed25519PrivateKey.generate()
        attacker_pin={"key_id":self.pin["key_id"],
                      "public_key_hex":attacker.public_key().public_bytes(
                          encoding=serialization.Encoding.Raw,
                          format=serialization.PublicFormat.Raw).hex()}
        self.assertEqual(self.review(self.signed(key=attacker))["state"],"BLOCKED")
        # If a compromised host installs the attacker's public key, mathematics
        # passes, but owner identity and trusted enrollment STILL remain false.
        candidate=self.review(self.signed(key=attacker),host_public_pin=attacker_pin)
        self.assertEqual(candidate["state"],CANDIDATE)
        self.assertFalse(candidate["enrolled_owner_key_verified"])

    def test_envelope_unknown_fields_rejected(self):
        e=self.signed();e["owner_authenticated"]=True
        self.assertEqual(self.review(e)["state"],"BLOCKED")

    def test_envelope_missing_fields_rejected(self):
        for field in ("payload","signature_hex"):
            e=self.signed();e.pop(field)
            with self.subTest(field=field):
                self.assertEqual(self.review(e)["state"],"BLOCKED")

    def test_payload_unknown_authority_flag_rejected(self):
        e=self.signed();e["payload"]["owner_approved"]=True
        self.assertEqual(self.review(e)["reason"],"SIGNED_PAYLOAD_SCHEMA_INVALID")

    def test_payload_missing_any_field_rejected(self):
        for field in self.payload:
            e=self.signed();e["payload"].pop(field)
            with self.subTest(field=field):
                self.assertEqual(self.review(e)["state"],"BLOCKED")

    def test_signed_user_text_changed_in_db_after_signature_rejected(self):
        e=self.signed()
        self.store.db.execute(
            "UPDATE messages SET data=replace(data, ?, ?) WHERE id=?",
            ("Explique inflação","Explique recessão",self.pending["message_id"])
        )
        self.store.db.commit()
        self.assertEqual(self.review(e)["state"],"BLOCKED")

    def test_signed_prompt_mutation_rejected_without_network(self):
        e=self.signed()
        r=self.review(e,final_prompt=self.prompt+" Segredo: abc")
        self.assertEqual(r["state"],"BLOCKED")

    def test_cross_tenant_scope_denied(self):
        r=self.review(scope=Scope("owner","other","workspace"))
        self.assertEqual(r["state"],"BLOCKED")

    def test_cross_workspace_scope_denied(self):
        self.assertEqual(self.review(scope=Scope("owner","tenant","other"))["state"],"BLOCKED")

    def test_wrong_actor_session_denied(self):
        self.assertEqual(self.review(access=access("delegado"))["state"],"BLOCKED")

    def test_non_admin_session_denied(self):
        self.assertEqual(self.review(access=access(role="USER"))["state"],"BLOCKED")

    def test_blocked_login_denied(self):
        self.assertEqual(self.review(access=access(allowed=False))["state"],"BLOCKED")

    def test_conversation_swapping_denied(self):
        other=self.store.create_conversation(self.scope,"outra").id
        self.assertEqual(self.review(conversation_id=other)["state"],"BLOCKED")

    def test_message_swapping_denied(self):
        self.assertEqual(self.review(message_id="aion-pending-model-"+"1"*64)["state"],"BLOCKED")

    def test_model_swapping_with_old_signature_denied(self):
        e=self.signed();e["payload"]["model_id"]="gpt-other"
        self.assertEqual(self.review(e)["reason"],"OWNER_SIGNATURE_MATH_INVALID")

    def test_price_cap_swapping_with_old_signature_denied(self):
        e=self.signed();e["payload"]["max_cost_micro_usd"]=200
        self.assertEqual(self.review(e)["reason"],"OWNER_SIGNATURE_MATH_INVALID")

    def test_nonce_swapping_with_old_signature_denied(self):
        e=self.signed();e["payload"]["nonce_hex"]="cd"*32
        self.assertEqual(self.review(e)["reason"],"OWNER_SIGNATURE_MATH_INVALID")

    def test_policy_generation_swapping_with_old_signature_denied(self):
        e=self.signed();e["payload"]["policy_generation"]=8
        self.assertEqual(self.review(e)["reason"],"COST_CAP_OR_POLICY_INVALID")

    def test_signed_policy_generation_must_match_host(self):
        e=self.signed()
        self.assertEqual(self.review(e,expected_policy_generation=8)["state"],"BLOCKED")

    def test_signed_provider_and_lane_swap_with_old_signature_denied(self):
        for field,value in (("provider_id","another"),("lane","EXTERNAL_REASONING")):
            e=self.signed();e["payload"][field]=value
            with self.subTest(field=field):
                self.assertEqual(self.review(e)["state"],"BLOCKED")

    def test_signed_scope_mutations_fail_closed(self):
        for field,value in (("owner_id","other"),("tenant_id","other"),
                            ("workspace_id","other"),("conversation_id","different"),
                            ("message_id","different"),("request_digest","c"*64),
                            ("source_message_sha256","d"*64)):
            e=self.signed();e["payload"][field]=value
            with self.subTest(field=field):
                self.assertEqual(self.review(e)["state"],"BLOCKED")

    def test_resigned_changed_model_is_new_math_but_not_authority(self):
        p=dict(self.payload);p["model_id"]="gpt-other"
        e=self.signed(p)
        r=self.review(e)
        self.assertEqual(r["state"],CANDIDATE)
        self.assertFalse(r["model_invocation_authorized"])

    def test_resigned_new_nonce_does_not_establish_freshness(self):
        p=dict(self.payload);p["nonce_hex"]="cc"*32
        r=self.review(self.signed(p))
        self.assertEqual(r["state"],CANDIDATE)
        self.assertFalse(r["nonce_freshness_durably_verified"])

    def test_invalid_role_and_purpose_are_rejected(self):
        for field,value in (("role","COLLECTOR_ED25519"),
                            ("purpose","APPROVE_INSTALL"),
                            ("schema","AION_V1")):
            p=dict(self.payload);p[field]=value
            with self.subTest(field=field):
                self.assertEqual(self.review(self.signed(p))["state"],"BLOCKED")

    def test_zero_negative_noninteger_and_bool_cost_denied(self):
        for value in (0,-1,True,False,1.0,"100",20_000_001,None):
            p=dict(self.payload);p["max_cost_micro_usd"]=value
            with self.subTest(cost=value):
                self.assertEqual(self.review(self.signed(p))["state"],"BLOCKED")

    def test_policy_bool_float_invalid(self):
        for value in (0,True,False,1.5,"7",-1,None):
            p=dict(self.payload);p["policy_generation"]=value
            with self.subTest(gen=value):
                self.assertEqual(self.review(self.signed(p))["state"],"BLOCKED")

    def test_wrong_nonce_or_hash_encoding_denied(self):
        for field in ("nonce_hex","request_digest","source_message_sha256",
                      "final_prompt_sha256"):
            for bad in ("Z"*64,"A"*64,"f"*63,True,None):
                p=dict(self.payload);p[field]=bad
                with self.subTest(field=field,bad=bad):
                    self.assertEqual(self.review(self.signed(p))["state"],"BLOCKED")

    def test_wrong_lane_provider_and_model_denied(self):
        for field,value in (("lane","LOCAL_DETERMINISTIC"),("lane","external_fast"),
                            ("provider_id","OpenAI"),("provider_id",""),
                            ("model_id","foo\nbar")):
            p=dict(self.payload);p[field]=value
            with self.subTest(field=field):
                self.assertEqual(self.review(self.signed(p))["state"],"BLOCKED")

    def test_host_pin_invalid_or_authority_flag_denied(self):
        for pin in ({},None,False,
                    {"key_id":self.pin["key_id"],"public_key_hex":self.public,
                     "enrolled_owner":True},
                    {"key_id":"", "public_key_hex":self.public},
                    {"key_id":self.pin["key_id"],"public_key_hex":"0"*63}):
            with self.subTest(pin=str(pin)[:20]):
                self.assertEqual(self.review(host_public_pin=pin)["state"],"BLOCKED")

    def test_key_id_mismatch_denied(self):
        p=dict(self.payload);p["owner_key_id"]="other"
        self.assertEqual(self.review(self.signed(p))["state"],"BLOCKED")

    def test_signature_type_encoding_denied(self):
        for val in (None,"Z"*128,"a"*127,True):
            e=self.signed();e["signature_hex"]=val
            with self.subTest(val=val):
                self.assertEqual(self.review(e)["state"],"BLOCKED")

    def test_final_prompt_invalid_or_too_long_denied(self):
        for value in (None,False,""," ","x"*40001,"minha senha é 123"):
            with self.subTest(value=str(value)[:12]):
                self.assertEqual(self.review(final_prompt=value)["state"],"BLOCKED")

    def test_staged_message_must_remain_pending(self):
        self.store.db.execute(
            "UPDATE messages SET data=replace(data, ?, ?) WHERE id=?",
            ('"PENDING"','"APPROVED"',self.pending["message_id"])
        )
        self.store.db.commit()
        self.assertEqual(self.review()["state"],"BLOCKED")

    def test_signed_review_does_not_mutate_or_create_assistant_response(self):
        before=self.store.get_conversation(self.scope,self.cid).message_count
        self.assertEqual(self.review()["state"],CANDIDATE)
        self.assertEqual(self.store.get_conversation(self.scope,self.cid).message_count,before)
        self.assertEqual([x.role for x in self.store.list_messages(self.scope,self.cid).items],["user"])

    def test_no_network_provider_transport_called(self):
        import requests
        with patch.object(requests.sessions.Session,"request",
                          side_effect=AssertionError("NETWORK FORBIDDEN")):
            self.assertEqual(self.review()["state"],CANDIDATE)
        self.assertFalse(self.review()["provider_called"])

    def test_no_keys_secrets_or_prompt_exposed_in_receipt(self):
        r=self.review()
        self.assertNotIn(self.prompt,str(r))
        self.assertNotIn(self.source,str(r))
        self.assertNotIn(self.public,str(r))
        self.assertNotIn("signature_hex",r)

    def test_server_side_untrusted_role_forgery_denied(self):
        e=self.signed()
        e["payload"]["role"]="HUMAN_OWNER_ED25519"
        self.assertEqual(self.review(e)["state"],CANDIDATE)
        self.assertFalse(self.review(e)["human_owner_identity_verified"])

    def test_canonical_json_is_repeatable_and_sensitive_to_each_field(self):
        x=canonical_approval_message(dict(self.payload))
        self.assertEqual(x,canonical_approval_message(dict(reversed(list(self.payload.items())))))
        y=dict(self.payload);y["max_cost_micro_usd"]+=1
        self.assertNotEqual(x,canonical_approval_message(y))
        self.assertTrue(x.startswith(DOMAIN))

    def test_malformed_envelope_and_access_rejected(self):
        for env in (None,[],True,"BAD",{}):
            with self.subTest(env=env):
                self.assertEqual(self.review(envelope=env)["state"],"BLOCKED")
        self.assertEqual(self.review(access=None)["state"],"BLOCKED")


if __name__ == "__main__":
    unittest.main()
