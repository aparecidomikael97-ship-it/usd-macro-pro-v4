"""Two-service signed high-watermark CI, ephemeral synthetic keys only.

Separate independent state in RAM fixtures; no cloud/production authority.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
from threading import Lock
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_v2_authenticated_witness_read_cas_reference import (
    READ_SCHEMA, READ_PURPOSE, READ_ROLE, canonical_fresh_read,
)
from atlasquant_aion_v2_secondary_anchor_reference import (
    SCHEMA, ANCHOR_READ_SCHEMA, ANCHOR_READ_PURPOSE, ANCHOR_ROLE,
    ANCHOR_DOMAIN, HEAD_MATCH, ADVANCE_CANDIDATE,
    canonical_anchor_read, review_two_signed_domains,
    review_secondary_anchor_advance_preconditions,
)


def pin(key, key_id):
    return {"key_id":key_id,"public_key_hex":
            key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ).hex()}


class TwoDomainAnchorReferenceTests(unittest.TestCase):
    def setUp(self):
        self.primary_key=Ed25519PrivateKey.generate()
        self.anchor_key=Ed25519PrivateKey.generate()
        self.primary_pin=pin(self.primary_key,"synthetic-primary-witness")
        self.anchor_pin=pin(self.anchor_key,"synthetic-second-domain")
        self.primary={
            "witness_epoch":7,"sequence":1,
            "receipt_sha256":"a"*64,"snapshot_sha256":"b"*64,
            "hold_count":0,"held_micro_usd":0,"limit_micro_usd":500,
        }
        self.anchor=deepcopy(self.primary)
        self.anchor_lock=Lock()
        self.counter=0
        self.owner_pin_sha256="c"*64
        self.witness_pin_sha256=sha256(json.dumps(
            self.primary_pin,sort_keys=True,ensure_ascii=False,
            separators=(",",":"),
        ).encode("utf-8")).hexdigest()

    def query(self,kind):
        self.counter+=1
        q={
            "witness_service_id":"fixture-witness",
            "owner_id":"owner","tenant_id":"tenant",
            "workspace_id":"workspace","period_id":"2026-10",
            "policy_generation":7,
            "owner_pin_sha256":self.owner_pin_sha256,
            "challenge_nonce_hex":f"{self.counter:064x}",
        }
        if kind=="primary":
            q["minimum_witness_epoch"]=7
        else:
            q.update({
                "anchor_service_id":"fixture-secondary-independent",
                "witness_pin_sha256":self.witness_pin_sha256,
                "minimum_anchor_epoch":7,
            })
        return q

    def read(self,kind,q,*,head=None,key=None):
        head=deepcopy(head or (self.primary if kind=="primary" else self.anchor))
        if kind=="primary":
            payload={
                "schema":READ_SCHEMA,"purpose":READ_PURPOSE,
                "role":READ_ROLE,
                "witness_key_id":self.primary_pin["key_id"],
                "witness_service_id":q["witness_service_id"],
                "owner_id":q["owner_id"],"tenant_id":q["tenant_id"],
                "workspace_id":q["workspace_id"],"period_id":q["period_id"],
                "policy_generation":q["policy_generation"],
                "owner_pin_sha256":q["owner_pin_sha256"],
                "challenge_nonce_hex":q["challenge_nonce_hex"],
                "minimum_witness_epoch":q["minimum_witness_epoch"],
                "witness_epoch":head["witness_epoch"],
                "head_sequence":head["sequence"],
                "head_receipt_sha256":head["receipt_sha256"],
                "head_snapshot_sha256":head["snapshot_sha256"],
                "head_hold_count":head["hold_count"],
                "head_held_micro_usd":head["held_micro_usd"],
                "head_limit_micro_usd":head["limit_micro_usd"],
            }
            signed=(key or self.primary_key).sign(
                canonical_fresh_read(payload)).hex()
        else:
            payload={
                "schema":ANCHOR_READ_SCHEMA,"purpose":ANCHOR_READ_PURPOSE,
                "role":ANCHOR_ROLE,
                "anchor_key_id":self.anchor_pin["key_id"],
                "anchor_service_id":q["anchor_service_id"],
                "witness_service_id":q["witness_service_id"],
                "owner_id":q["owner_id"],"tenant_id":q["tenant_id"],
                "workspace_id":q["workspace_id"],"period_id":q["period_id"],
                "policy_generation":q["policy_generation"],
                "owner_pin_sha256":q["owner_pin_sha256"],
                "witness_pin_sha256":q["witness_pin_sha256"],
                "challenge_nonce_hex":q["challenge_nonce_hex"],
                "minimum_anchor_epoch":q["minimum_anchor_epoch"],
                "anchor_epoch":head["witness_epoch"],
                "head_sequence":head["sequence"],
                "head_receipt_sha256":head["receipt_sha256"],
                "head_snapshot_sha256":head["snapshot_sha256"],
                "head_hold_count":head["hold_count"],
                "head_held_micro_usd":head["held_micro_usd"],
                "head_limit_micro_usd":head["limit_micro_usd"],
            }
            signed=(key or self.anchor_key).sign(
                canonical_anchor_read(payload)).hex()
        return {"payload":payload,"signature_hex":signed}

    def pair(self):
        p=self.query("primary")
        a=self.query("anchor")
        return p,self.read("primary",p),a,self.read("anchor",a)

    def compare(self,p,pr,a,ar,**kwargs):
        args={
            "primary_signed_read":pr,"primary_public_pin":self.primary_pin,
            "primary_query":p,"anchor_signed_read":ar,
            "anchor_public_pin":self.anchor_pin,"anchor_query":a,
        }
        args.update(kwargs)
        result=review_two_signed_domains(**args)
        self.assertEqual(result["schema"],SCHEMA)
        self.assertTrue(result["reference_only"])
        for f in (
            "actual_two_trust_domains_verified","anchor_public_key_enrolled",
            "anchor_high_watermark_durable","owner_consent_verified",
            "model_invocation_authorized","paid_provider_called",
            "network_called","safe_to_resume",
        ):
            self.assertIs(result[f],False,f)
        return result

    def proposal(self,old_anchor_query,old_anchor_read,
                 primary_query,primary_read,**kwargs):
        args={
            "old_anchor_signed_read":old_anchor_read,
            "old_anchor_public_pin":self.anchor_pin,
            "old_anchor_query":old_anchor_query,
            "primary_signed_read":primary_read,
            "primary_public_pin":self.primary_pin,
            "primary_query":primary_query,
            "current_anchor_head_for_fixture":self.anchor,
        }
        args.update(kwargs)
        out=review_secondary_anchor_advance_preconditions(**args)
        self.assertIs(out["anchor_cas_committed"],False)
        self.assertIs(out["cross_domain_atomicity_verified"],False)
        return out

    def primary_step(self):
        cur=deepcopy(self.primary)
        cur["sequence"]+=1
        cur["hold_count"]+=1
        cur["held_micro_usd"]+=100
        cur["receipt_sha256"]=format(cur["sequence"],"064x")
        cur["snapshot_sha256"]=format(cur["sequence"]+100,"064x")
        self.primary=cur

    def test_mathematically_equal_signed_heads_not_real_independence(self):
        p,pr,a,ar=self.pair()
        o=self.compare(p,pr,a,ar)
        self.assertEqual(o["state"],HEAD_MATCH)
        self.assertTrue(o["mathematics_match"])
        self.assertFalse(o["freshness_independently_verified"])
        self.assertTrue(ANCHOR_DOMAIN.endswith(b"\x00"))

    def test_primary_old_restore_against_newer_anchor_blocks(self):
        self.primary_step()
        self.anchor=deepcopy(self.primary)
        self.primary={
            "witness_epoch":7,"sequence":1,
            "receipt_sha256":"a"*64,"snapshot_sha256":"b"*64,
            "hold_count":0,"held_micro_usd":0,"limit_micro_usd":500,
        }
        p,pr,a,ar=self.pair()
        self.assertEqual(self.compare(p,pr,a,ar)["reason"],
                         "PRIMARY_ROLLBACK_BEHIND_SECOND_ANCHOR")

    def test_anchor_behind_current_primary_blocks_spend_until_reconcile(self):
        self.primary_step()
        p,pr,a,ar=self.pair()
        self.assertEqual(self.compare(p,pr,a,ar)["reason"],
                         "PRIMARY_AHEAD_OF_ANCHOR_RECONCILIATION_REQUIRED")
        self.assertFalse(self.compare(p,pr,a,ar)["paid_provider_called"])

    def test_same_sequence_different_receipt_fork_blocks(self):
        self.primary["receipt_sha256"]="d"*64
        p,pr,a,ar=self.pair()
        self.assertEqual(self.compare(p,pr,a,ar)["reason"],
                         "SAME_SEQUENCE_WITNESS_FORK_OR_MUTATION")

    def test_separate_signed_anchor_challenge_replay_is_blocked(self):
        p,pr,a,ar=self.pair()
        second=self.query("anchor")
        self.assertEqual(self.compare(p,pr,second,ar)["reason"],
                         "ANCHOR_SIGNED_SCOPE_OR_CHALLENGE_MISMATCH")
        self.assertEqual(self.compare(p,pr,a,ar)["state"],HEAD_MATCH)

    def test_anchor_signature_and_wrong_pin_rejected(self):
        p,pr,a,ar=self.pair()
        forged=deepcopy(ar)
        forged["signature_hex"]="0"*128
        self.assertEqual(self.compare(p,pr,a,forged)["reason"],
                         "ANCHOR_SIGNATURE_MATH_INVALID")
        attacker=Ed25519PrivateKey.generate()
        fake=pin(attacker,self.anchor_pin["key_id"])
        self.assertEqual(self.compare(p,pr,a,ar,
                         anchor_public_pin=fake)["state"],"BLOCKED")

    def test_independent_anchor_pin_forged_with_host_pin_swap_can_pass_math(self):
        p,pr,a,ar=self.pair()
        attacker=Ed25519PrivateKey.generate()
        fake_pin=pin(attacker,self.anchor_pin["key_id"])
        forged=self.read("anchor",a,key=attacker)
        o=self.compare(p,pr,a,forged,anchor_public_pin=fake_pin)
        self.assertEqual(o["state"],HEAD_MATCH)
        self.assertFalse(o["anchor_public_key_enrolled"])
        self.assertFalse(o["actual_two_trust_domains_verified"])

    def test_cross_scope_owner_period_and_witness_pin_change_block(self):
        p,pr,a,ar=self.pair()
        for k,v in (
            ("owner_id","different"),("tenant_id","other"),
            ("period_id","2026-11"),("witness_service_id","different"),
            ("witness_pin_sha256","d"*64),
        ):
            with self.subTest(field=k):
                bad=deepcopy(a)
                bad[k]=v
                self.assertEqual(self.compare(p,pr,bad,ar)["state"],"BLOCKED")

    def test_signed_independent_anchor_floor_tamper_blocks(self):
        p,pr,a,ar=self.pair()
        q=deepcopy(a)
        q["minimum_anchor_epoch"]=1
        self.assertEqual(self.compare(p,pr,q,ar)["reason"],
                         "ANCHOR_SIGNED_SCOPE_OR_CHALLENGE_MISMATCH")

    def test_two_domains_both_fully_restored_old_can_pass_math_negative_control(self):
        old=deepcopy(self.primary)
        self.primary_step()
        self.anchor=deepcopy(self.primary)
        self.primary=deepcopy(old)
        self.anchor=deepcopy(old)
        p,pr,a,ar=self.pair()
        self.assertEqual(self.compare(p,pr,a,ar)["state"],HEAD_MATCH)
        self.assertFalse(self.compare(p,pr,a,ar)[
            "rollback_protection_production_verified"])

    def test_anchor_preflight_one_step_no_append_performed(self):
        aq=self.query("anchor")
        old_anchor_read=self.read("anchor",aq)
        self.primary_step()
        pq=self.query("primary")
        new_primary_read=self.read("primary",pq)
        o=self.proposal(aq,old_anchor_read,pq,new_primary_read)
        self.assertEqual(o["state"],ADVANCE_CANDIDATE)
        self.assertEqual(o["proposed_anchor_head"]["sequence"],2)
        self.assertEqual(self.anchor["sequence"],1)

    def test_reference_concurrent_anchor_compare_and_swap_one_winner(self):
        aq=self.query("anchor")
        ar=self.read("anchor",aq)
        self.primary_step()
        pq=self.query("primary")
        pr=self.read("primary",pq)
        def worker(_):
            with self.anchor_lock:
                o=self.proposal(aq,ar,pq,pr)
                if o["state"]==ADVANCE_CANDIDATE:
                    self.anchor=deepcopy(o["proposed_anchor_head"])
                return o["state"]
        with ThreadPoolExecutor(max_workers=5) as pool:
            states=list(pool.map(worker,range(10)))
        self.assertEqual(states.count(ADVANCE_CANDIDATE),1)
        self.assertEqual(states.count("BLOCKED"),9)
        self.assertEqual(self.anchor["sequence"],2)

    def test_invalid_nonmonotonic_double_increment_and_same_digest(self):
        aq=self.query("anchor")
        ar=self.read("anchor",aq)
        self.primary_step()
        pq=self.query("primary")
        for field,bad in (
            ("sequence",3),("hold_count",2),("held_micro_usd",0),
            ("limit_micro_usd",999),
            ("snapshot_sha256",self.anchor["snapshot_sha256"]),
            ("witness_epoch",8),
        ):
            with self.subTest(field=field):
                head=deepcopy(self.primary)
                head[field]=bad
                pr=self.read("primary",pq,head=head)
                self.assertEqual(self.proposal(aq,ar,pq,pr)["state"],"BLOCKED")

    def test_lost_anchor_response_requires_fresh_double_read_no_paid_retry(self):
        aq=self.query("anchor")
        ar=self.read("anchor",aq)
        self.primary_step()
        pq=self.query("primary")
        pr=self.read("primary",pq)
        o=self.proposal(aq,ar,pq,pr)
        self.assertEqual(o["state"],ADVANCE_CANDIDATE)
        self.anchor=deepcopy(o["proposed_anchor_head"])
        self.assertEqual(self.proposal(aq,ar,pq,pr)["state"],"BLOCKED")
        p2,r2,a2,r3=self.pair()
        self.assertEqual(self.compare(p2,r2,a2,r3)["state"],HEAD_MATCH)
        self.assertFalse(self.compare(p2,r2,a2,r3)[
            "model_invocation_authorized"])

    def test_missing_anchor_or_unavailable_primary_blocks_without_network(self):
        p,pr,a,ar=self.pair()
        self.assertEqual(self.compare(p,pr,a,None)["state"],"BLOCKED")
        self.assertEqual(self.compare(p,None,a,ar)["state"],"BLOCKED")
        with patch("requests.post",side_effect=AssertionError("network")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("model")):
            self.assertEqual(self.compare(p,pr,a,ar)["state"],HEAD_MATCH)

    def test_authority_flag_injection_and_malformed_fields_fail_closed(self):
        p,pr,a,ar=self.pair()
        bad=deepcopy(ar)
        bad["payload"]["provider_approved"]=True
        self.assertEqual(self.compare(p,pr,a,bad)["state"],"BLOCKED")
        for field in ar["payload"]:
            with self.subTest(field=field):
                bad=deepcopy(ar)
                bad["payload"].pop(field)
                self.assertEqual(self.compare(p,pr,a,bad)["state"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
