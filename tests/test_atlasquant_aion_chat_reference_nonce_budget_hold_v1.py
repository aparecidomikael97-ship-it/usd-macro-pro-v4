"""Disposable-reference SQLite hold tests; no host, provider, billing or real key."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_pending_model_turn_v1 import stage_pending_model_user_turn
from atlasquant_aion_chat_signed_turn_review_v1 import (
    APPROVAL_SCHEMA, ROLE, PURPOSE, canonical_approval_message,
)
from atlasquant_aion_chat_reference_nonce_budget_hold_v1 import (
    SCHEMA,REFERENCE_HELD,REFERENCE_REPLAY,ReferenceNonceBudgetLedger,
)


def access():
    return {"allowed":True,"mode":"AUTHENTICATED","role":"ADMIN",
            "session":{"role":"ADMIN","username":"owner",
                       "credential_fingerprint":"only-fixture-credential",
                       "permissions":["app:read","aion:admin"]}}


class HoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.chat_path=Path(self.tmp.name)/"chat.db"
        self.ref_path=Path(self.tmp.name)/"holds.db"
        self.scope=Scope("owner","tenant","workspace")
        self.chat=SQLiteChatStore(self.chat_path)
        self.cid=self.chat.create_conversation(self.scope,"chat").id
        self.key=Ed25519PrivateKey.generate()
        pub=self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
        self.pin={"key_id":"fixture-owner-pin","public_key_hex":pub}
        self.ledger=ReferenceNonceBudgetLedger(
            self.ref_path,scope=self.scope,period_id="2026-10",
            policy_generation=5,owner_public_pin=self.pin,
            limit_micro_usd=300,
        )
        self.message="Explique inflação no Brasil de forma objetiva"
        self.final_prompt="AION responde apenas texto: "+self.message
        self.pending=self._stage("request-0001",self.message)
        self.payload=self._payload(self.pending,nonce="ab"*32)

    def tearDown(self):
        self.chat.db.close()
        self.ledger.close()
        self.tmp.cleanup()

    def _stage(self,request_id,text):
        return stage_pending_model_user_turn(
            self.chat,self.scope,access(),conversation_id=self.cid,
            request_id=request_id,message=text,
        )

    def _payload(self,pending,nonce,cap=100,prompt=None):
        prompt=self.final_prompt if prompt is None else prompt
        return {
            "schema":APPROVAL_SCHEMA,"purpose":PURPOSE,"role":ROLE,
            "owner_key_id":self.pin["key_id"],
            "owner_id":self.scope.owner_id,"tenant_id":self.scope.tenant_id,
            "workspace_id":self.scope.workspace_id,
            "conversation_id":self.cid,"message_id":pending["message_id"],
            "request_digest":pending["request_digest"],
            "source_message_sha256":pending["message_sha256"],
            "final_prompt_sha256":sha256(prompt.encode()).hexdigest(),
            "provider_id":"openai","model_id":"test-mock",
            "lane":"EXTERNAL_FAST","max_cost_micro_usd":cap,
            "policy_generation":5,"nonce_hex":nonce,
        }

    def _envelope(self,payload=None,key=None):
        p=deepcopy(self.payload if payload is None else payload)
        k=self.key if key is None else key
        return {"payload":p,"signature_hex":k.sign(canonical_approval_message(p)).hex()}

    def _reserve(self,payload=None,*,ledger=None,chat=None,pin=None,quote=70,
                 prompt=None,actor_access=None,key=None):
        p=self.payload if payload is None else payload
        return (ledger or self.ledger).hold_reference_only(
            chat or self.chat, access() if actor_access is None else actor_access,
            conversation_id=self.cid,message_id=p["message_id"],
            final_prompt=self.final_prompt if prompt is None else prompt,
            envelope=self._envelope(p,key=key),
            host_public_pin=self.pin if pin is None else pin,
            host_quote_micro_usd=quote,
        )

    def assert_no_authority(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertTrue(r["reference_store_only"])
        for x in ("model_invocation_authorized","provider_called",
                  "real_budget_reserved","real_billing_authorized",
                  "trusted_human_owner_consent","independent_witness_protected",
                  "hardware_antirollback_verified","safe_to_resume",
                  "installer_authorized"):
            self.assertIs(r[x],False,x)

    def test_single_hold_is_recorded_and_no_payment_or_provider(self):
        r=self._reserve()
        self.assertEqual(r["state"],REFERENCE_HELD)
        self.assertEqual(r["reference_hold_micro_usd"],100)
        self.assertEqual(r["reference_total_held_micro_usd"],100)
        self.assert_no_authority(r)
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"],1)
        self.assertEqual(self.chat.get_conversation(self.scope,self.cid).message_count,1)

    def test_same_nonce_same_request_is_idempotent(self):
        a=self._reserve()
        b=self._reserve()
        self.assertEqual(a["nonce_hex"],b["nonce_hex"])
        self.assertEqual(b["state"],REFERENCE_REPLAY)
        self.assertEqual(self.ledger.reference_snapshot()["held_micro_usd"],100)
        self.assert_no_authority(b)

    def test_nonce_reused_with_new_signed_intent_is_blocked(self):
        self._reserve()
        p=deepcopy(self.payload);p["max_cost_micro_usd"]=200
        r=self._reserve(p)
        self.assertEqual(r["reason"],"NONCE_ALREADY_BOUND_DIFFERENTLY")
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"],1)

    def test_same_message_with_new_nonce_cannot_double_hold(self):
        self._reserve()
        p=deepcopy(self.payload);p["nonce_hex"]="cd"*32
        r=self._reserve(p)
        self.assertEqual(r["reason"],"MESSAGE_ALREADY_HAS_REFERENCE_HOLD")
        self.assertEqual(self.ledger.reference_snapshot()["held_micro_usd"],100)

    def test_second_message_separate_nonce_can_reserve(self):
        self._reserve()
        next_pending=self._stage("request-0002","Explique produtividade")
        p=self._payload(next_pending,"cd"*32)
        self.assertEqual(self._reserve(p)["state"],REFERENCE_HELD)
        self.assertEqual(self.ledger.reference_snapshot()["held_micro_usd"],200)

    def test_total_limit_enforced_using_signed_maximum_not_quote(self):
        self._reserve()
        p2=self._payload(self._stage("request-0002","Sobre PIB"),"cd"*32,cap=200)
        self.assertEqual(self._reserve(p2,quote=1)["state"],REFERENCE_HELD)
        p3=self._payload(self._stage("request-0003","Sobre CPI"),"ef"*32,cap=1)
        r=self._reserve(p3,quote=1)
        self.assertEqual(r["reason"],"REFERENCE_BUDGET_EXCEEDED")
        self.assertEqual(self.ledger.reference_snapshot()["held_micro_usd"],300)

    def test_quote_exceeding_signed_maximum_blocked(self):
        self.assertEqual(self._reserve(quote=101)["reason"],"HOST_QUOTE_EXCEEDS_SIGNED_CAP")
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"],0)

    def test_zero_negative_bool_or_floating_quote_is_blocked(self):
        for value in (None,False,True,0,-1,1.0,"1",2_000_000_001):
            with self.subTest(quote=value):
                self.assertEqual(self._reserve(quote=value)["state"],"BLOCKED")
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"],0)

    def test_modified_signature_after_signing_is_rejected(self):
        e=self._envelope()
        e["signature_hex"]="0"*128
        r=self.ledger.hold_reference_only(
            self.chat,access(),conversation_id=self.cid,
            message_id=self.pending["message_id"],final_prompt=self.final_prompt,
            envelope=e,host_public_pin=self.pin,host_quote_micro_usd=70,
        )
        self.assertEqual(r["state"],"BLOCKED")
        self.assert_no_authority(r)

    def test_wrong_private_key_not_accepted(self):
        r=self._reserve(key=Ed25519PrivateKey.generate())
        self.assertEqual(r["state"],"BLOCKED")

    def test_wrong_host_pin_not_accepted(self):
        k=Ed25519PrivateKey.generate()
        pin={"key_id":self.pin["key_id"],"public_key_hex":
             k.public_key().public_bytes(
                 encoding=serialization.Encoding.Raw,
                 format=serialization.PublicFormat.Raw).hex()}
        self.assertEqual(self._reserve(pin=pin)["state"],"BLOCKED")

    def test_forged_trusted_host_pin_matching_attacker_key_fails_opening_existing_ledger(self):
        attacker=Ed25519PrivateKey.generate()
        newpin={"key_id":self.pin["key_id"],
                "public_key_hex":attacker.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                ).hex()}
        with self.assertRaisesRegex(ValueError,"config/pin mismatch"):
            ReferenceNonceBudgetLedger(
                self.ref_path,scope=self.scope,period_id="2026-10",
                policy_generation=5,owner_public_pin=newpin,
                limit_micro_usd=300,
            )
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"],0)

    def test_wrong_scope_and_admin_denied(self):
        bad=access();bad["session"]["username"]="delegado"
        self.assertEqual(self._reserve(actor_access=bad)["state"],"BLOCKED")
        other=access();other["mode"]="PREVIEW"
        self.assertEqual(self._reserve(actor_access=other)["state"],"BLOCKED")
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"],0)

    def test_wrong_prompt_denied(self):
        self.assertEqual(self._reserve(prompt="texto completamente diferente")["state"],"BLOCKED")

    def test_wrong_signed_model_can_be_reviewed_as_new_math_but_still_no_authority(self):
        p=deepcopy(self.payload);p["model_id"]="another-test-model"
        r=self._reserve(p)
        self.assertEqual(r["state"],REFERENCE_HELD)
        self.assert_no_authority(r)

    def test_reference_hold_does_not_authorize_paid_api(self):
        self.assertEqual(self._reserve()["state"],REFERENCE_HELD)
        self.assertFalse(self.ledger.reference_snapshot()["real_billing_authorized"])
        self.assertFalse(self.ledger.reference_snapshot()["model_invocation_authorized"])

    def test_source_chat_store_is_not_modified_by_hold(self):
        before=self.chat.get_conversation(self.scope,self.cid).message_count
        self._reserve()
        self.assertEqual(self.chat.get_conversation(self.scope,self.cid).message_count,before)

    def test_reopen_preserves_total_and_nonce_without_reset(self):
        self._reserve()
        self.ledger.close()
        self.ledger=ReferenceNonceBudgetLedger(
            self.ref_path,scope=self.scope,period_id="2026-10",
            policy_generation=5,owner_public_pin=self.pin,limit_micro_usd=300,
        )
        self.assertEqual(self._reserve()["state"],REFERENCE_REPLAY)
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"],1)

    def test_wrong_budget_limit_on_reopen_does_not_reset(self):
        self._reserve()
        with self.assertRaisesRegex(ValueError,"config/pin mismatch"):
            ReferenceNonceBudgetLedger(
                self.ref_path,scope=self.scope,period_id="2026-10",
                policy_generation=5,owner_public_pin=self.pin,limit_micro_usd=999,
            )
        self.assertEqual(self.ledger.reference_snapshot()["held_micro_usd"],100)

    def test_wrong_month_on_reopen_does_not_rollover(self):
        self._reserve()
        with self.assertRaisesRegex(ValueError,"config/pin mismatch"):
            ReferenceNonceBudgetLedger(
                self.ref_path,scope=self.scope,period_id="2026-11",
                policy_generation=5,owner_public_pin=self.pin,limit_micro_usd=300,
            )
        self.assertEqual(self.ledger.reference_snapshot()["held_micro_usd"],100)

    def test_lowered_policy_on_reopen_rejected(self):
        self._reserve()
        with self.assertRaisesRegex(ValueError,"config/pin mismatch"):
            ReferenceNonceBudgetLedger(
                self.ref_path,scope=self.scope,period_id="2026-10",
                policy_generation=4,owner_public_pin=self.pin,limit_micro_usd=300,
            )

    def test_changed_scoped_owner_reopen_rejected(self):
        with self.assertRaisesRegex(ValueError,"config/pin mismatch"):
            ReferenceNonceBudgetLedger(
                self.ref_path,scope=Scope("someone","tenant","workspace"),
                period_id="2026-10",policy_generation=5,
                owner_public_pin=self.pin,limit_micro_usd=300,
            )

    def test_corrupt_totals_block_further_reference_holds(self):
        self._reserve()
        self.ledger.db.execute(
            "UPDATE reference_config SET held_total_micro_usd=0 WHERE singleton=1"
        )
        self.assertEqual(self._reserve()["state"],"BLOCKED")
        self.assertEqual(self.ledger.reference_snapshot()["state"],"BLOCKED")

    def test_atomic_rollback_after_insert_error(self):
        self.ledger.db.execute("""
            CREATE TRIGGER abort_holds BEFORE UPDATE ON reference_config
            BEGIN SELECT RAISE(ABORT,'fixture I/O error'); END;
        """)
        self.assertEqual(self._reserve()["state"],"BLOCKED")
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"],0)
        self.ledger.db.execute("DROP TRIGGER abort_holds")

    def test_same_nonce_after_failed_transaction_can_retry_once(self):
        self.ledger.db.execute("""
            CREATE TRIGGER fail_first BEFORE UPDATE ON reference_config
            BEGIN SELECT RAISE(ABORT,'fixture failure'); END;
        """)
        self.assertEqual(self._reserve()["state"],"BLOCKED")
        self.ledger.db.execute("DROP TRIGGER fail_first")
        self.assertEqual(self._reserve()["state"],REFERENCE_HELD)

    def test_invalid_initial_reference_limit_rejected(self):
        for cost in (0,-1,True,False,1.1,"300",2_000_000_001):
            with self.subTest(cost=cost):
                with self.assertRaises(ValueError):
                    ReferenceNonceBudgetLedger(
                        Path(self.tmp.name)/"other.db",scope=self.scope,
                        period_id="2026-10",policy_generation=5,
                        owner_public_pin=self.pin,limit_micro_usd=cost,
                    )

    def test_invalid_initial_policy_and_period_rejected(self):
        for month,gen in (("2026-13",5),("2026-00",5),
                          ("2026-10",True),("2026-10",0),
                          ("2026-10",-1),("2026-10",2.1)):
            with self.subTest(month=month,gen=gen):
                with self.assertRaises(ValueError):
                    ReferenceNonceBudgetLedger(
                        Path(self.tmp.name)/"other.db",scope=self.scope,
                        period_id=month,policy_generation=gen,
                        owner_public_pin=self.pin,limit_micro_usd=300,
                    )

    def test_no_provider_network_calls_or_subprocess(self):
        import requests,subprocess,socket
        with patch.object(requests.sessions.Session,"request",side_effect=AssertionError),
             patch.object(subprocess,"Popen",side_effect=AssertionError),
             patch.object(socket,"socket",side_effect=AssertionError):
            self.assertEqual(self._reserve()["state"],REFERENCE_HELD)
        self.assert_no_authority(self.ledger.reference_snapshot())

    def test_atomic_competing_signed_holds_under_one_budget(self):
        p2=self._payload(self._stage("request-0002","Analise indicadores"),"cd"*32,cap=200)
        self.ledger.close()
        # Each concurrent caller holds distinct connections, as in processes.
        def contender(p):
            chat=SQLiteChatStore(self.chat_path)
            ledger=ReferenceNonceBudgetLedger(
                self.ref_path,scope=self.scope,period_id="2026-10",
                policy_generation=5,owner_public_pin=self.pin,limit_micro_usd=300,
            )
            try:
                return self._reserve(p,chat=chat,ledger=ledger,quote=1)
            finally:
                ledger.close()
                chat.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(contender,[self.payload,p2]))
        self.ledger=ReferenceNonceBudgetLedger(
            self.ref_path,scope=self.scope,period_id="2026-10",
            policy_generation=5,owner_public_pin=self.pin,limit_micro_usd=300,
        )
        self.assertEqual([r["state"] for r in results].count(REFERENCE_HELD),2)
        self.assertEqual(self.ledger.reference_snapshot()["held_micro_usd"],300)

    def test_atomic_competing_holds_exceeding_budget_only_one_wins(self):
        p2=self._payload(self._stage("request-0002","Analise indicadores"),"cd"*32,cap=200)
        p1=deepcopy(self.payload);p1["max_cost_micro_usd"]=200
        self.ledger.close()
        def contender(p):
            chat=SQLiteChatStore(self.chat_path)
            ledger=ReferenceNonceBudgetLedger(
                self.ref_path,scope=self.scope,period_id="2026-10",
                policy_generation=5,owner_public_pin=self.pin,limit_micro_usd=300,
            )
            try:
                return self._reserve(p,chat=chat,ledger=ledger,quote=1)
            finally:
                ledger.close()
                chat.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(contender,[p1,p2]))
        self.ledger=ReferenceNonceBudgetLedger(
            self.ref_path,scope=self.scope,period_id="2026-10",
            policy_generation=5,owner_public_pin=self.pin,limit_micro_usd=300,
        )
        self.assertEqual([r["state"] for r in results].count(REFERENCE_HELD),1)
        self.assertEqual([r["reason"] for r in results].count("REFERENCE_BUDGET_EXCEEDED"),1)
        self.assertEqual(self.ledger.reference_snapshot()["held_micro_usd"],200)

    def test_two_concurrent_same_nonce_never_double_hold(self):
        self.ledger.close()
        def worker(_):
            chat=SQLiteChatStore(self.chat_path)
            ledger=ReferenceNonceBudgetLedger(
                self.ref_path,scope=self.scope,period_id="2026-10",
                policy_generation=5,owner_public_pin=self.pin,limit_micro_usd=300,
            )
            try:
                return self._reserve(chat=chat,ledger=ledger)
            finally:
                ledger.close();chat.db.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(worker,range(4)))
        self.ledger=ReferenceNonceBudgetLedger(
            self.ref_path,scope=self.scope,period_id="2026-10",
            policy_generation=5,owner_public_pin=self.pin,limit_micro_usd=300,
        )
        self.assertEqual([r["state"] for r in results].count(REFERENCE_HELD),1)
        self.assertEqual([r["state"] for r in results].count(REFERENCE_REPLAY),3)
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"],1)

    def test_corrupted_existing_nonce_cannot_be_accepted_as_same_hold(self):
        self._reserve()
        self.ledger.db.execute(
            "UPDATE reference_holds SET signed_intent_sha256=? WHERE nonce_hex=?",
            ("f"*64,"ab"*32)
        )
        self.assertEqual(self._reserve()["state"],"BLOCKED")

    def test_reference_only_budget_month_cannot_claim_brl_limit(self):
        self.assertEqual(self._reserve()["state"],REFERENCE_HELD)
        r=self.ledger.reference_snapshot()
        self.assertFalse(r["real_usd_brl_fx_verified"])
        self.assertFalse(r["monthly_budget_production_enforced"])

    def test_wrong_policy_generation_signed_payload_denied(self):
        p=deepcopy(self.payload);p["policy_generation"]=6
        self.assertEqual(self._reserve(p)["state"],"BLOCKED")

    def test_budget_holds_cannot_be_refunded_by_user(self):
        self._reserve()
        self.assertFalse(hasattr(self.ledger,"refund"))
        self.assertFalse(hasattr(self.ledger,"release_hold"))
        self.assertFalse(hasattr(self.ledger,"execute_provider"))


if __name__=="__main__":
    unittest.main()
