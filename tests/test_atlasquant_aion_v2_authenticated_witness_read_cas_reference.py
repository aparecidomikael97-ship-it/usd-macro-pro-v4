"""Synthetic external witness service proving READ challenge + CAS math only.

All owner/collector/witness private keys are ephemeral CI fixtures. The mock
service is a Python in-memory lock, not independent durable protection.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from threading import Lock
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_pending_model_turn_v1 import stage_pending_model_user_turn
from atlasquant_aion_chat_signed_full_request_review_v2 import (
    APPROVAL_SCHEMA, PURPOSE as OWNER_PURPOSE, ROLE as OWNER_ROLE,
    canonical_full_request_approval_v2,
)
from atlasquant_aion_chat_reference_v2_nonce_cost_hold import (
    REFERENCE_HELD, ReferenceV2NonceCostLedger,
)
from atlasquant_aion_provider import preview_openai_request_binding
from atlasquant_aion_v2_external_witness_rollback_reference import (
    ZERO, canonical_witness_head, signed_receipt_sha256,
    make_unsigned_witness_head_candidate,
    review_witnessed_v2_reference_state,
)
from atlasquant_aion_v2_authenticated_witness_read_cas_reference import (
    READ_SCHEMA, READ_ROLE, READ_PURPOSE, READ_DOMAIN,
    READ_CANDIDATE, CAS_CANDIDATE, canonical_fresh_read,
    review_signed_fresh_witness_read, review_reference_witness_cas_preconditions,
)


def pin(key, key_id):
    return {"key_id": key_id, "public_key_hex":
            key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ).hex()}


def access():
    return {
        "allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
        "session": {
            "role": "ADMIN", "username": "owner",
            "credential_fingerprint": "fixture-fingerprint",
            "permissions": ["app:read", "aion:admin"],
        },
    }


class MockExternalWitness:
    """One in-RAM CAS head, separate from restorable fake ledger, NO real trust."""
    def __init__(self, key, pin_data, initial_head):
        self.key = key
        self.pin = pin_data
        self.head = deepcopy(initial_head)
        self.lock = Lock()

    def read(self, query):
        with self.lock:
            head = deepcopy(self.head)
        payload = {
            "schema": READ_SCHEMA,
            "purpose": READ_PURPOSE,
            "role": READ_ROLE,
            "witness_key_id": self.pin["key_id"],
            "witness_service_id": query["witness_service_id"],
            "owner_id": query["owner_id"],
            "tenant_id": query["tenant_id"],
            "workspace_id": query["workspace_id"],
            "period_id": query["period_id"],
            "policy_generation": query["policy_generation"],
            "owner_pin_sha256": query["owner_pin_sha256"],
            "challenge_nonce_hex": query["challenge_nonce_hex"],
            "minimum_witness_epoch": query["minimum_witness_epoch"],
            "witness_epoch": head["witness_epoch"],
            "head_sequence": head["sequence"],
            "head_receipt_sha256": head["receipt_sha256"],
            "head_snapshot_sha256": head["snapshot_sha256"],
            "head_hold_count": head["hold_count"],
            "head_held_micro_usd": head["held_micro_usd"],
            "head_limit_micro_usd": head["limit_micro_usd"],
        }
        return {
            "payload": payload,
            "signature_hex": self.key.sign(canonical_fresh_read(payload)).hex(),
        }

    def attempt(self, read_response, query, next_receipt, collector_pin):
        with self.lock:
            outcome = review_reference_witness_cas_preconditions(
                read_response=read_response,
                trusted_witness_pin=self.pin, expected_query=query,
                current_service_head=self.head,
                signed_next_collector_receipt=next_receipt,
                collector_public_pin=collector_pin,
            )
            # THIS IS A TEST-ONLY MUTATION. The source verifier NEVER does it.
            if outcome["state"] == CAS_CANDIDATE:
                self.head = deepcopy(outcome["proposed_head"])
            return outcome


class AuthenticatedWitnessReadCasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.chat = SQLiteChatStore(base / "chat.db")
        self.scope = Scope("owner", "tenant", "workspace")
        self.cid = self.chat.create_conversation(self.scope, "AION").id
        self.owner = Ed25519PrivateKey.generate()
        self.collector = Ed25519PrivateKey.generate()
        self.witness = Ed25519PrivateKey.generate()
        self.owner_pin = pin(self.owner, "owner-fixture")
        self.collector_pin = pin(self.collector, "collector-fixture")
        self.witness_pin = pin(self.witness, "witness-fixture")
        self.env = {
            "AION_MODEL_PROVIDER": "openai",
            "OPENAI_API_KEY": "fixture-not-a-real-credential",
            "AION_OPENAI_FAST_MODEL": "synthetic-model",
            "AION_OPENAI_REASONING_MODEL": "synthetic-reason",
            "AION_OPENAI_INPUT_USD_PER_MTOK": "1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK": "2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS": "300",
            "AION_OPENAI_TIMEOUT_SECONDS": "45",
        }
        self.ledger = ReferenceV2NonceCostLedger(
            base / "holds.db", scope=self.scope,
            period_id="2026-10", policy_generation=7,
            owner_public_pin=self.owner_pin, limit_micro_usd=500,
        )
        self.first_receipt = self.collector_receipt(
            seq=1, previous=ZERO,
        )
        d = self.first_receipt["payload"]
        self.initial_head = {
            "witness_epoch": 3, "sequence": 1,
            "receipt_sha256": signed_receipt_sha256(self.first_receipt),
            "snapshot_sha256": d["ledger_snapshot_sha256"],
            "hold_count": 0, "held_micro_usd": 0,
            "limit_micro_usd": 500,
        }
        self.service = MockExternalWitness(
            self.witness, self.witness_pin, self.initial_head,
        )
        self.nonce_id = 0

    def tearDown(self):
        self.ledger.close()
        self.chat.db.close()
        self.temp.cleanup()

    def query(self, *, nonce=None, floor=3):
        self.nonce_id += 1
        return {
            "witness_service_id": "test-independent-service",
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "period_id": "2026-10",
            "policy_generation": 7,
            "owner_pin_sha256": self.ledger.pin_digest,
            "challenge_nonce_hex": nonce or f"{self.nonce_id:064x}",
            "minimum_witness_epoch": floor,
        }

    def collector_receipt(self, *, seq, previous, key=None):
        payload = make_unsigned_witness_head_candidate(
            self.ledger, collector_key_id=self.collector_pin["key_id"],
            witness_sequence=seq, previous_receipt_sha256=previous,
        )
        return {
            "payload": payload,
            "signature_hex": (key or self.collector).sign(
                canonical_witness_head(payload)
            ).hex(),
        }

    def hold(self, *, request="request-0001", source="Explique inflação",
             nonce="aa", cap=100):
        pending = stage_pending_model_user_turn(
            self.chat, self.scope, access(), conversation_id=self.cid,
            request_id=request, message=source,
        )
        prompt = "AION responde em português: " + source
        preview = preview_openai_request_binding(
            prompt, lane="EXTERNAL_FAST", values=self.env,
        )
        self.assertEqual(preview["state"], "BOUND_REQUEST_PREVIEW_UNTRUSTED")
        payload = {
            "schema": APPROVAL_SCHEMA,
            "purpose": OWNER_PURPOSE, "role": OWNER_ROLE,
            "owner_key_id": self.owner_pin["key_id"],
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "conversation_id": self.cid,
            "message_id": pending["message_id"],
            "request_digest": pending["request_digest"],
            "source_message_sha256": pending["message_sha256"],
            "final_prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
            "full_provider_request_sha256": preview["request_sha256"],
            "provider_id": preview["provider"],
            "model_id": preview["resolved_model"],
            "lane": preview["lane"],
            "endpoint": preview["endpoint"],
            "max_output_tokens": preview["max_output_tokens"],
            "timeout_seconds_repr": repr(preview["timeout_seconds"]),
            "max_cost_micro_usd": cap,
            "policy_generation": 7,
            "nonce_hex": nonce*32,
        }
        envelope = {
            "payload": payload,
            "signature_hex": self.owner.sign(
                canonical_full_request_approval_v2(payload)
            ).hex(),
        }
        result = self.ledger.hold_reference_only(
            self.chat, access(), conversation_id=self.cid,
            message_id=pending["message_id"], final_prompt=prompt,
            envelope=envelope, host_public_pin=self.owner_pin,
            provider_values=self.env, host_quote_micro_usd=min(cap, 50),
        )
        self.assertEqual(result["state"], REFERENCE_HELD)
        self.assertFalse(result["model_invocation_authorized"])

    def prepare(self):
        q = self.query()
        read = self.service.read(q)
        self.assertEqual(self.read(read, q)["state"], READ_CANDIDATE)
        self.hold()
        next_receipt = self.collector_receipt(
            seq=2, previous=self.initial_head["receipt_sha256"],
        )
        return q, read, next_receipt

    def read(self, response, query, **overrides):
        args = {
            "response": response,
            "trusted_witness_pin": self.witness_pin,
            "expected_query": query,
        }
        args.update(overrides)
        result = review_signed_fresh_witness_read(**args)
        self.assertIs(result["provider_request_approved"], False)
        self.assertIs(result["witness_freshness_independently_verified"], False)
        self.assertIs(result["safe_to_resume"], False)
        return result

    def check_cas(self, q, read, next_receipt, **overrides):
        args = {
            "read_response": read, "trusted_witness_pin": self.witness_pin,
            "expected_query": q, "current_service_head": self.service.head,
            "signed_next_collector_receipt": next_receipt,
            "collector_public_pin": self.collector_pin,
        }
        args.update(overrides)
        result = review_reference_witness_cas_preconditions(**args)
        self.assertFalse(result["atomic_compare_and_swap_performed"])
        self.assertFalse(result["paid_dispatch_performed"])
        self.assertFalse(result["witness_append_durable"])
        self.assertFalse(result["owner_identity_verified"])
        return result

    def test_fresh_signed_read_with_challenge_only_math(self):
        q = self.query()
        read = self.service.read(q)
        state = self.read(read, q)
        self.assertEqual(state["state"], READ_CANDIDATE)
        self.assertEqual(state["read_head"], self.initial_head)
        self.assertTrue(READ_DOMAIN.endswith(b"\x00"))
        self.assertFalse(state["witness_public_key_enrolled"])

    def test_replay_signed_old_response_against_new_challenge_blocked(self):
        q1 = self.query()
        response = self.service.read(q1)
        q2 = self.query()
        self.assertEqual(self.read(response,q2)["reason"],
                         "READ_CHALLENGE_OR_SCOPE_MISMATCH")
        self.assertEqual(self.read(response,q1)["state"], READ_CANDIDATE)
        self.assertFalse(self.read(response,q1)[
            "witness_freshness_independently_verified"])

    def test_valid_reference_cas_pure_then_synthetic_service_advances(self):
        q,read,next_receipt = self.prepare()
        pure = self.check_cas(q,read,next_receipt)
        self.assertEqual(pure["state"], CAS_CANDIDATE)
        self.assertEqual(self.service.head, self.initial_head)
        outcome = self.service.attempt(read,q,next_receipt,self.collector_pin)
        self.assertEqual(outcome["state"], CAS_CANDIDATE)
        self.assertEqual(self.service.head["sequence"], 2)
        self.assertEqual(self.service.head["held_micro_usd"], 100)
        self.assertEqual(self.service.head["hold_count"], 1)
        self.assertFalse(outcome["witness_append_durable"])
        self.assertEqual(self.check_cas(q,read,next_receipt)["reason"],
                         "SERVICE_HEAD_CHANGED_OR_STALE_READ")

    def test_parallel_competing_compare_swap_one_reference_winner(self):
        q,read,next_receipt = self.prepare()
        def attempt(_):
            return self.service.attempt(read,q,next_receipt,self.collector_pin)["state"]
        with ThreadPoolExecutor(max_workers=6) as pool:
            states=list(pool.map(attempt,range(12)))
        self.assertEqual(states.count(CAS_CANDIDATE),1)
        self.assertEqual(states.count("BLOCKED"),11)
        self.assertEqual(self.service.head["sequence"],2)

    def test_old_read_then_new_service_head_rejected(self):
        q,read,next_receipt = self.prepare()
        self.service.attempt(read,q,next_receipt,self.collector_pin)
        self.assertEqual(self.check_cas(q,read,next_receipt)["reason"],
                         "SERVICE_HEAD_CHANGED_OR_STALE_READ")

    def test_local_hold_then_crash_before_external_cas_is_not_safe(self):
        q,read,next_receipt=self.prepare()
        # Simulate power loss immediately after SQLite hold, before CAS.
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"], 1)
        self.assertEqual(self.service.head["sequence"], 1)
        self.assertEqual(review_witnessed_v2_reference_state(
            self.ledger, envelope=self.first_receipt,
            collector_public_pin=self.collector_pin,
            independent_expected_head={
                "sequence": 1,
                "receipt_sha256": self.initial_head["receipt_sha256"],
            },
        )["reason"], "LOCAL_SQLITE_SNAPSHOT_NOT_AT_EXTERNAL_HEAD")
        self.assertFalse(self.check_cas(q,read,next_receipt)[
            "atomic_compare_and_swap_performed"])

    def test_response_lost_after_synthetic_cas_no_automatic_replay_or_payment(self):
        q,read,next_receipt=self.prepare()
        self.assertEqual(self.service.attempt(read,q,next_receipt,self.collector_pin)[
            "state"], CAS_CANDIDATE)
        # Drop the response. A fresh READ sees seq 2 but CANNOT infer any
        # paid HTTP outcome or turn the old signature into execution.
        q2=self.query()
        response2=self.service.read(q2)
        self.assertEqual(self.read(response2,q2)["read_head"]["sequence"],2)
        self.assertEqual(self.check_cas(q,read,next_receipt)["state"], "BLOCKED")
        self.assertFalse(self.read(response2,q2)["paid_dispatch_performed"])

    def test_corrupted_signature_and_wrong_pin_block(self):
        q,read,next_receipt=self.prepare()
        fake=deepcopy(read)
        fake["signature_hex"]="0"*128
        self.assertEqual(self.read(fake,q)["reason"],
                         "WITNESS_READ_SIGNATURE_INVALID")
        attacker=Ed25519PrivateKey.generate()
        forged_pin=pin(attacker,"witness-fixture")
        self.assertEqual(self.read(read,q,trusted_witness_pin=forged_pin)[
            "state"],"BLOCKED")
        tampered=deepcopy(next_receipt)
        tampered["signature_hex"]="0"*128
        self.assertEqual(self.check_cas(q,read,tampered)["reason"],
                         "COLLECTOR_RECEIPT_SIGNATURE_MATH_INVALID")

    def test_attacker_host_can_swap_both_trust_pin_and_signed_head_math_only(self):
        q=self.query()
        attacker=Ed25519PrivateKey.generate()
        fake_pin=pin(attacker,"witness-fixture")
        forged=deepcopy(self.service.read(q))
        forged["signature_hex"]=attacker.sign(
            canonical_fresh_read(forged["payload"])
        ).hex()
        result=self.read(forged,q,trusted_witness_pin=fake_pin)
        self.assertEqual(result["state"],READ_CANDIDATE)
        self.assertFalse(result["witness_service_authenticated"])
        self.assertFalse(result["witness_public_key_enrolled"])

    def test_untrusted_epoch_lower_than_host_floor_refused(self):
        q=self.query(floor=4)
        signed=self.service.read(q)
        self.assertEqual(self.read(signed,q)["reason"],
                         "READ_EPOCH_OR_HEAD_INVALID")
        self.assertEqual(self.read(signed,{**q,"minimum_witness_epoch":3})[
            "reason"], "READ_CHALLENGE_OR_SCOPE_MISMATCH")

    def test_new_head_wrong_count_cap_delta_or_previous_digest_rejected(self):
        q,read,next_receipt=self.prepare()
        variants=[
            ("witness_sequence",3),
            ("previous_receipt_sha256","f"*64),
            ("ledger_hold_count",2),
            ("ledger_held_micro_usd",0),
            ("ledger_limit_micro_usd",999),
            ("ledger_snapshot_sha256",self.initial_head["snapshot_sha256"]),
            ("period_id","2026-11"),
            ("policy_generation",8),
            ("owner_id","attacker"),
        ]
        for name,v in variants:
            with self.subTest(field=name):
                changed=deepcopy(next_receipt)
                changed["payload"][name]=v
                changed["signature_hex"]=self.collector.sign(
                    canonical_witness_head(changed["payload"])
                ).hex()
                self.assertEqual(self.check_cas(q,read,changed)["state"],"BLOCKED")

    def test_wrong_service_head_same_epoch_fork_and_stale_block(self):
        q,read,next_receipt=self.prepare()
        for key,changed in (
            ("sequence",7),
            ("receipt_sha256","f"*64),
            ("snapshot_sha256","f"*64),
            ("held_micro_usd",1),
        ):
            with self.subTest(field=key):
                forged=deepcopy(self.initial_head)
                forged[key]=changed
                self.assertEqual(self.check_cas(
                    q,read,next_receipt,current_service_head=forged
                )["reason"], "SERVICE_HEAD_CHANGED_OR_STALE_READ")

    def test_unknown_and_missing_fields_fail_closed(self):
        q=self.query()
        signed=self.service.read(q)
        for f in list(signed["payload"]):
            with self.subTest(field=f):
                bad=deepcopy(signed)
                bad["payload"].pop(f)
                self.assertEqual(self.read(bad,q)["state"],"BLOCKED")
        tampered=deepcopy(signed)
        tampered["payload"]["safe_to_resume"]=True
        self.assertEqual(self.read(tampered,q)["state"],"BLOCKED")
        qbad=deepcopy(q)
        qbad["provider_request_approved"]=True
        self.assertEqual(self.read(signed,qbad)["state"],"BLOCKED")

    def test_invalid_challenge_and_public_pin_block(self):
        q=self.query()
        signed=self.service.read(q)
        for nonce in (ZERO,"q"*64,True,0,"1"):
            with self.subTest(nonce=repr(nonce)):
                bad=deepcopy(q)
                bad["challenge_nonce_hex"]=nonce
                self.assertEqual(self.read(signed,bad)["state"],"BLOCKED")
        for bad in (None,{},{"key_id":"x"},True):
            self.assertEqual(self.read(signed,q,trusted_witness_pin=bad)[
                "state"],"BLOCKED")

    def test_zero_network_even_for_successful_signed_read_cas_math(self):
        q,read,next_receipt=self.prepare()
        with patch("requests.post",side_effect=AssertionError("network")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("model")):
            self.assertEqual(self.read(read,q)["state"],READ_CANDIDATE)
            self.assertEqual(self.check_cas(q,read,next_receipt)[
                "state"],CAS_CANDIDATE)
        self.assertFalse(self.read(read,q)["network_called"])


if __name__=="__main__":
    unittest.main()
