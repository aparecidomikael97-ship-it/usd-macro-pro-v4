"""AION V2 isolated persisted CAS witness proof, synthetic GitHub CI only."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import shutil
import sqlite3
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
    ReferenceV2NonceCostLedger, REFERENCE_HELD,
)
from atlasquant_aion_provider import preview_openai_request_binding
from atlasquant_aion_v2_external_witness_rollback_reference import (
    ZERO, canonical_witness_head, make_unsigned_witness_head_candidate,
    signed_receipt_sha256,
)
from atlasquant_aion_v2_authenticated_witness_read_cas_reference import (
    canonical_fresh_read,
)
from atlasquant_aion_v2_isolated_sqlite_witness_cas_reference import (
    SCHEMA, COMMITTED, REPLAY, FALSE_GATES, pin_sha256,
    ReferenceIsolatedSqliteWitnessCAS,
)


def pin(key, key_id):
    raw=key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {"key_id":key_id,"public_key_hex":raw.hex()}


def access():
    return {
        "allowed":True,"mode":"AUTHENTICATED","role":"ADMIN",
        "session":{
            "role":"ADMIN","username":"owner",
            "credential_fingerprint":"ci-only-fixture",
            "permissions":["app:read","aion:admin"],
        },
    }


class IsolatedWitnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.chat=SQLiteChatStore(root/"chat.db")
        self.scope=Scope("owner","tenant","workspace")
        self.cid=self.chat.create_conversation(self.scope,"AION").id
        self.owner=Ed25519PrivateKey.generate()
        self.collector=Ed25519PrivateKey.generate()
        self.witness=Ed25519PrivateKey.generate()
        self.owner_pin=pin(self.owner,"synthetic-owner")
        self.collector_pin=pin(self.collector,"synthetic-collector")
        self.witness_pin=pin(self.witness,"synthetic-witness")
        self.ledger=ReferenceV2NonceCostLedger(
            root/"local-holds.db",scope=self.scope,period_id="2026-10",
            policy_generation=11,owner_public_pin=self.owner_pin,
            limit_micro_usd=500,
        )
        self.env={
            "AION_MODEL_PROVIDER":"openai",
            "OPENAI_API_KEY":"unused-ci-placeholder",
            "AION_OPENAI_FAST_MODEL":"mock-fast",
            "AION_OPENAI_REASONING_MODEL":"mock-reasoning",
            "AION_OPENAI_INPUT_USD_PER_MTOK":"1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK":"2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS":"300",
            "AION_OPENAI_TIMEOUT_SECONDS":"45",
        }
        first=self.receipt(seq=1,previous=ZERO)
        self.genesis={
            "witness_epoch":6,"sequence":1,
            "receipt_sha256":signed_receipt_sha256(first),
            "snapshot_sha256":first["payload"]["ledger_snapshot_sha256"],
            "hold_count":0,"held_micro_usd":0,"limit_micro_usd":500,
        }
        self.config={
            "witness_service_id":"synthetic-service",
            "witness_key_id":self.witness_pin["key_id"],
            "witness_public_pin_sha256":pin_sha256(self.witness_pin),
            "collector_public_pin_sha256":pin_sha256(self.collector_pin),
            "owner_id":self.scope.owner_id,
            "tenant_id":self.scope.tenant_id,
            "workspace_id":self.scope.workspace_id,
            "period_id":"2026-10","policy_generation":11,
            "owner_pin_sha256":self.ledger.pin_digest,"witness_epoch":6,
        }
        self.witness_path=root/"witness-isolated.db"
        self.service=self.open_service()
        self.nonce_counter=0

    def open_service(self,**kwargs):
        opts={"config":self.config,"genesis_head":self.genesis}
        opts.update(kwargs)
        return ReferenceIsolatedSqliteWitnessCAS(self.witness_path,**opts)

    def tearDown(self):
        self.service.close()
        self.ledger.close()
        self.chat.db.close()
        self.tmp.cleanup()

    def receipt(self,*,seq,previous):
        payload=make_unsigned_witness_head_candidate(
            self.ledger,collector_key_id=self.collector_pin["key_id"],
            witness_sequence=seq,previous_receipt_sha256=previous,
        )
        return {
            "payload":payload,
            "signature_hex":self.collector.sign(
                canonical_witness_head(payload)).hex(),
        }

    def hold(self,request,message,nonce,cap=100):
        pending=stage_pending_model_user_turn(
            self.chat,self.scope,access(),conversation_id=self.cid,
            request_id=request,message=message,
        )
        prompt="AION responde em português: "+message
        pre=preview_openai_request_binding(
            prompt,lane="EXTERNAL_FAST",values=self.env,
        )
        self.assertEqual(pre["state"],"BOUND_REQUEST_PREVIEW_UNTRUSTED")
        payload={
            "schema":APPROVAL_SCHEMA,"purpose":OWNER_PURPOSE,"role":OWNER_ROLE,
            "owner_key_id":self.owner_pin["key_id"],
            "owner_id":self.scope.owner_id,"tenant_id":self.scope.tenant_id,
            "workspace_id":self.scope.workspace_id,
            "conversation_id":self.cid,"message_id":pending["message_id"],
            "request_digest":pending["request_digest"],
            "source_message_sha256":pending["message_sha256"],
            "final_prompt_sha256":sha256(prompt.encode()).hexdigest(),
            "full_provider_request_sha256":pre["request_sha256"],
            "provider_id":pre["provider"],"model_id":pre["resolved_model"],
            "lane":pre["lane"],"endpoint":pre["endpoint"],
            "max_output_tokens":pre["max_output_tokens"],
            "timeout_seconds_repr":repr(pre["timeout_seconds"]),
            "max_cost_micro_usd":cap,"policy_generation":11,
            "nonce_hex":nonce*32,
        }
        envelope={"payload":payload,"signature_hex":self.owner.sign(
            canonical_full_request_approval_v2(payload)).hex()}
        result=self.ledger.hold_reference_only(
            self.chat,access(),conversation_id=self.cid,
            message_id=pending["message_id"],final_prompt=prompt,
            envelope=envelope,host_public_pin=self.owner_pin,
            provider_values=self.env,host_quote_micro_usd=min(50,cap),
        )
        self.assertEqual(result["state"],REFERENCE_HELD,result)

    def signed_read(self):
        self.nonce_counter+=1
        query={
            "witness_service_id":self.config["witness_service_id"],
            "owner_id":self.scope.owner_id,"tenant_id":self.scope.tenant_id,
            "workspace_id":self.scope.workspace_id,
            "period_id":"2026-10","policy_generation":11,
            "owner_pin_sha256":self.ledger.pin_digest,
            "challenge_nonce_hex":f"{self.nonce_counter:064x}",
            "minimum_witness_epoch":6,
        }
        p=self.service.unsigned_read_candidate(query)
        envelope={"payload":p,"signature_hex":self.witness.sign(
            canonical_fresh_read(p)).hex()}
        return query,envelope

    def candidate(self,request="request-1",message="Explique inflação",
                  nonce="ab",cap=100):
        q,r=self.signed_read()
        current=self.service.snapshot()["current_local_witness_head"]
        self.hold(request,message,nonce,cap)
        nxt=self.receipt(
            seq=current["sequence"]+1,previous=current["receipt_sha256"],
        )
        return q,r,nxt

    def commit(self,q,r,n,*,op="op-1",service=None,pin_override=None):
        result=(service or self.service).cas_reference_only(
            operation_id=op,expected_query=q,signed_read=r,
            witness_public_pin=pin_override or self.witness_pin,
            signed_next_collector_receipt=n,
            collector_public_pin=self.collector_pin,
        )
        self.assertEqual(result["schema"],SCHEMA)
        for key,value in FALSE_GATES.items():
            self.assertIs(result[key],value,key)
        return result

    def test_local_cas_persists_full_signed_max_without_authority(self):
        q,r,n=self.candidate()
        x=self.commit(q,r,n)
        self.assertEqual(x["state"],COMMITTED)
        self.assertTrue(x["reference_cas_committed"])
        self.assertEqual(x["current_local_witness_head"]["held_micro_usd"],100)
        self.assertFalse(x["model_invocation_authorized"])

    def test_reopen_restores_state_and_idempotent_retry(self):
        q,r,n=self.candidate()
        self.commit(q,r,n)
        before=self.service.snapshot()
        self.service.close()
        self.service=self.open_service()
        self.assertEqual(self.service.snapshot(),before)
        self.assertEqual(self.commit(q,r,n)["state"],REPLAY)
        self.assertEqual(self.service.snapshot()["local_reference_appends"],1)

    def test_same_operation_with_different_input_blocks(self):
        q,r,n=self.candidate()
        self.commit(q,r,n)
        modified=deepcopy(n)
        modified["signature_hex"]="0"*128
        self.assertEqual(self.commit(q,r,modified)["state"],"BLOCKED")
        q2=deepcopy(q)
        q2["challenge_nonce_hex"]="e"*64
        self.assertEqual(self.commit(q2,r,n)["state"],"BLOCKED")

    def test_simultaneous_different_operations_only_one_commits(self):
        q,r,n=self.candidate()
        def worker(i):
            instance=self.open_service()
            try:
                return instance.cas_reference_only(
                    operation_id=f"op-{i}",expected_query=q,signed_read=r,
                    witness_public_pin=self.witness_pin,
                    signed_next_collector_receipt=n,
                    collector_public_pin=self.collector_pin,
                )["state"]
            finally:
                instance.close()
        with ThreadPoolExecutor(max_workers=5) as pool:
            out=list(pool.map(worker,range(10)))
        self.assertEqual(out.count(COMMITTED),1)
        self.assertEqual(out.count("BLOCKED"),9)

    def test_simultaneous_identical_retries_single_write(self):
        q,r,n=self.candidate()
        def worker(_):
            instance=self.open_service()
            try:
                return instance.cas_reference_only(
                    operation_id="one-id",expected_query=q,signed_read=r,
                    witness_public_pin=self.witness_pin,
                    signed_next_collector_receipt=n,
                    collector_public_pin=self.collector_pin,
                )["state"]
            finally:
                instance.close()
        with ThreadPoolExecutor(max_workers=5) as pool:
            out=list(pool.map(worker,range(8)))
        self.assertEqual(out.count(COMMITTED),1)
        self.assertEqual(out.count(REPLAY),7)

    def test_local_hold_before_witness_commit_not_safely_complete(self):
        q,r,n=self.candidate()
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"],1)
        self.assertEqual(self.service.snapshot()["local_reference_appends"],0)
        self.assertFalse(self.service.snapshot()["safe_to_resume"])
        self.assertEqual(self.commit(q,r,n)["state"],COMMITTED)

    def test_response_lost_after_cas_reopen_is_only_idempotent(self):
        q,r,n=self.candidate()
        self.commit(q,r,n)
        self.service.close()
        self.service=self.open_service()
        self.assertEqual(self.commit(q,r,n)["state"],REPLAY)
        self.assertFalse(self.service.snapshot()["provider_called"])

    def test_recover_old_witness_db_detects_rollback_only_if_anchor_is_fresh(self):
        q,r,n=self.candidate()
        self.commit(q,r,n)
        old=self.service.snapshot()["current_local_witness_head"]
        backup=Path(self.tmp.name)/"old-witness.db"
        with closing(sqlite3.connect(str(backup))) as conn:
            self.service.db.backup(conn)
        q2,r2,n2=self.candidate(
            request="request-2",message="Explique juros",nonce="cd")
        self.assertEqual(self.commit(q2,r2,n2,op="op-2")["state"],COMMITTED)
        latest=self.service.snapshot()["current_local_witness_head"]
        self.service.close()
        shutil.copyfile(backup,self.witness_path)
        self.service=self.open_service()
        self.assertEqual(self.service.snapshot()[
            "current_local_witness_head"]["sequence"],2)
        self.assertEqual(self.service.compare_supplied_external_anchor(
            latest)["reason"],"LOCALLY_RESTORED_WITNESS_BEHIND_ANCHOR")
        self.assertEqual(self.service.compare_supplied_external_anchor(
            old)["state"],"LOCAL_ANCHOR_EQUALITY_MATH_ONLY")
        self.assertFalse(self.service.snapshot()[
            "independent_protected_witness_verified"])

    def test_event_chain_corruption_blocks_reopening_and_new_cas(self):
        q,r,n=self.candidate()
        self.commit(q,r,n)
        self.service.db.execute(
            "UPDATE witness_ref_appends SET previous_receipt_sha256=?",
            ("f"*64,),
        )
        self.assertEqual(self.service.snapshot()["state"],"BLOCKED")
        self.assertEqual(self.commit(q,r,n)["state"],"BLOCKED")

    def test_inconsistent_head_detected(self):
        q,r,n=self.candidate()
        self.commit(q,r,n)
        self.service.db.execute(
            "UPDATE witness_ref_state SET current_json=?",
            ('{"sequence":123}',),
        )
        self.assertEqual(self.service.snapshot()["state"],"BLOCKED")

    def test_config_and_pins_cannot_silently_rotate(self):
        q,r,n=self.candidate()
        self.commit(q,r,n)
        cfg=deepcopy(self.config)
        cfg["policy_generation"]=12
        with self.assertRaisesRegex(ValueError,"mismatch"):
            self.open_service(config=cfg)
        altered=pin(Ed25519PrivateKey.generate(),"synthetic-witness")
        self.assertEqual(self.commit(q,r,n,pin_override=altered)[
            "reason"],"REFERENCE_KEY_PIN_CHANGED")

    def test_local_sqlite_failure_rolled_back(self):
        q,r,n=self.candidate()
        self.service.db.execute("""
            CREATE TRIGGER synthetic_failure BEFORE UPDATE ON witness_ref_state
            BEGIN SELECT RAISE(ABORT,'simulated failure'); END
        """)
        self.assertEqual(self.commit(q,r,n)["state"],"BLOCKED")
        self.assertEqual(self.service.snapshot()["local_reference_appends"],0)
        self.service.db.execute("DROP TRIGGER synthetic_failure")
        self.assertEqual(self.commit(q,r,n)["state"],COMMITTED)

    def test_stale_signed_read_cannot_append_second_hold(self):
        q,r,n=self.candidate()
        self.commit(q,r,n)
        q2,r2,n2=self.candidate(
            request="request-2",message="Explique emprego",nonce="ef")
        self.assertEqual(self.commit(q,r,n2,op="op-other")["state"],"BLOCKED")
        self.assertEqual(self.commit(q2,r2,n2,op="op-other")["state"],COMMITTED)

    def test_bad_genesis_and_unknown_old_schema_fail_closed(self):
        bad=deepcopy(self.genesis)
        bad["sequence"]=0
        with self.assertRaises(ValueError):
            ReferenceIsolatedSqliteWitnessCAS(
                Path(self.tmp.name)/"bad-genesis.db",
                config=self.config,genesis_head=bad,
            )
        old=Path(self.tmp.name)/"old.db"
        with closing(sqlite3.connect(str(old))) as conn:
            conn.execute("CREATE TABLE legacy_v1(x)")
        with self.assertRaisesRegex(ValueError,"unknown/partial"):
            ReferenceIsolatedSqliteWitnessCAS(
                old,config=self.config,genesis_head=self.genesis,
            )

    def test_signed_read_floor_and_challenge_match_request(self):
        q,r=self.signed_read()
        self.assertEqual(r["payload"]["challenge_nonce_hex"],
                         q["challenge_nonce_hex"])
        self.assertEqual(r["payload"]["minimum_witness_epoch"],6)
        bad=deepcopy(q)
        bad["minimum_witness_epoch"]=7
        with self.assertRaisesRegex(ValueError,"epoch"):
            self.service.unsigned_read_candidate(bad)

    def test_no_external_network_or_model_even_if_local_cas_commits(self):
        q,r,n=self.candidate()
        with patch("requests.post",side_effect=AssertionError("network")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("model")):
            self.assertEqual(self.commit(q,r,n)["state"],COMMITTED)
        self.assertFalse(self.service.snapshot()["network_called"])


if __name__ == "__main__":
    unittest.main()
