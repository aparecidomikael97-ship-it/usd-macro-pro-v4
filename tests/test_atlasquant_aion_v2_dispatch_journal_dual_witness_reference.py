"""Dispatch journal two independent *synthetic* heads, crash and fork tests."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import (
    ReferenceOneShotUnknownOutcomeJournal,
    INTENT_SCHEMA,STATE_CLAIMED,STATE_UNKNOWN,
)
from atlasquant_aion_v2_dispatch_journal_dual_witness_reference import (
    READ_SCHEMA,PURPOSE,DOMAIN,MATCH,FENCE_CANDIDATE,
    canonical_dispatch_journal_read,local_journal_intent_commitment,
    unsigned_journal_head_candidate,review_dual_witnessed_journal,
    review_one_step_claim_fence_preflight,
)


def pin(key,name):
    return {
        "key_id":"ci-"+name,
        "public_key_hex":key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex(),
    }


class JournalDualWitnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"dispatch.db"
        self.config={
            "owner_id":"owner","tenant_id":"tenant",
            "workspace_id":"workspace","period_id":"2026-10",
            "policy_generation":9,"max_period_micro_usd":300,
        }
        self.intent={
            "schema":INTENT_SCHEMA,"owner_id":"owner",
            "tenant_id":"tenant","workspace_id":"workspace",
            "conversation_id":"conversation-one","message_id":"message-one",
            "nonce_hex":"a"*64,
            "signed_v2_intent_sha256":"b"*64,
            "full_provider_request_sha256":"c"*64,
            "primary_witness_receipt_sha256":"d"*64,
            "secondary_anchor_receipt_sha256":"e"*64,
            "key_registry_roster_sha256":"f"*64,
            "policy_generation":9,"period_id":"2026-10",
            "max_cost_micro_usd":100,
        }
        self.journal=self.open_journal()
        self.keys={
            "PRIMARY_WITNESS":Ed25519PrivateKey.generate(),
            "SECONDARY_ANCHOR":Ed25519PrivateKey.generate(),
        }
        self.pins={k:pin(v,k.lower()) for k,v in self.keys.items()}
        self.challenge_counter=0
        self.assertEqual(self.journal.prepare_reference_only(
            self.intent)["state"],"PREPARED_REFERENCE_ONLY")

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def open_journal(self):
        return ReferenceOneShotUnknownOutcomeJournal(
            self.path,config=self.config,
        )

    def query(self):
        self.challenge_counter+=1
        return {
            "owner_id":"owner","tenant_id":"tenant",
            "workspace_id":"workspace","period_id":"2026-10",
            "policy_generation":9,"key_registry_roster_sha256":"f"*64,
            "nonce_hex":"a"*64,
            "challenge_nonce_hex":f"{self.challenge_counter:064x}",
            "minimum_witness_epoch":4,
        }

    def read(self,role,q,*,journal=None,epoch=4,key=None):
        head=unsigned_journal_head_candidate(
            self.journal if journal is None else journal,
            intent=self.intent,query=q,role=role,
            signer_key_id=self.pins[role]["key_id"],
            witness_epoch=epoch,
        )
        return {
            "payload":head,
            "signature_hex":(key or self.keys[role]).sign(
                canonical_dispatch_journal_read(head)
            ).hex(),
        }

    def pair(self):
        p=self.query()
        a=self.query()
        return p,self.read("PRIMARY_WITNESS",p),a,self.read("SECONDARY_ANCHOR",a)

    def verify(self,p,pr,a,ar,*,journal=None,intent=None,**changes):
        args={
            "journal":self.journal if journal is None else journal,
            "intent":self.intent if intent is None else intent,
            "primary_read":pr,"primary_pin":self.pins["PRIMARY_WITNESS"],
            "primary_query":p,
            "anchor_read":ar,"anchor_pin":self.pins["SECONDARY_ANCHOR"],
            "anchor_query":a,
        }
        args.update(changes)
        o=review_dual_witnessed_journal(**args)
        self.assertFalse(o["paid_request_authorized"])
        self.assertFalse(o["provider_response_verified"])
        self.assertFalse(o["journal_antirollback_production_verified"])
        self.assertFalse(o["two_independent_head_freshness_verified"])
        self.assertFalse(o["billing_authorized"])
        self.assertFalse(o["safe_to_resume"])
        return o

    def test_after_claim_two_heads_match_math_not_send_authority(self):
        self.journal.claim_reference_only(intent=self.intent)
        p,pr,a,ar=self.pair()
        o=self.verify(p,pr,a,ar)
        self.assertEqual(o["state"],MATCH)
        self.assertEqual(o["matching_reference_head"]["intent_state"],STATE_CLAIMED)
        self.assertTrue(o["must_not_automatically_retry"])
        self.assertTrue(DOMAIN.endswith(b"\x00"))

    def test_no_claim_prepared_is_not_dispatch_eligible(self):
        p,pr,a,ar=self.pair()
        self.assertEqual(self.verify(p,pr,a,ar)["reason"],
                         "NOT_DISPATCH_CLAIMED_OR_UNKNOWN")

    def test_one_step_claim_fence_signed_old_and_new_math_only(self):
        oldp,oldpr,olda,oldar=self.pair()
        self.journal.claim_reference_only(intent=self.intent)
        newp,newpr,newa,newar=self.pair()
        o=review_one_step_claim_fence_preflight(
            old_primary_read=oldpr,old_anchor_read=oldar,
            new_primary_read=newpr,new_anchor_read=newar,
            primary_pin=self.pins["PRIMARY_WITNESS"],
            anchor_pin=self.pins["SECONDARY_ANCHOR"],
            old_primary_query=oldp,old_anchor_query=olda,
            new_primary_query=newp,new_anchor_query=newa,
        )
        self.assertEqual(o["state"],FENCE_CANDIDATE)
        self.assertEqual(o["fence_sequence_math_only"],2)
        self.assertFalse(o["witness_cas_performed"])
        self.assertFalse(o["secondary_anchor_cas_performed"])
        self.assertFalse(o["paid_request_sent"])

    def test_fence_rejects_double_transition(self):
        oldp,oldpr,olda,oldar=self.pair()
        self.journal.claim_reference_only(intent=self.intent)
        newp,newpr,newa,newar=self.pair()
        args={
            "old_primary_read":newpr,"old_anchor_read":newar,
            "new_primary_read":newpr,"new_anchor_read":newar,
            "primary_pin":self.pins["PRIMARY_WITNESS"],
            "anchor_pin":self.pins["SECONDARY_ANCHOR"],
            "old_primary_query":newp,"old_anchor_query":newa,
            "new_primary_query":newp,"new_anchor_query":newa,
        }
        self.assertEqual(review_one_step_claim_fence_preflight(
            **args)["state"],"BLOCKED")

    def test_after_claim_crash_old_heads_block_unanchored(self):
        p,pr,a,ar=self.pair()
        self.journal.claim_reference_only(intent=self.intent)
        self.assertEqual(self.verify(p,pr,a,ar)["reason"],
                         "LOCAL_CLAIM_UNANCHORED_OR_UNKNOWN_GAP")
        self.assertFalse(self.verify(p,pr,a,ar)["paid_request_authorized"])

    def test_one_head_advanced_only_blocks_split_domain(self):
        p,oldpr,a,oldar=self.pair()
        self.journal.claim_reference_only(intent=self.intent)
        np=self.query()
        newpr=self.read("PRIMARY_WITNESS",np)
        self.assertEqual(self.verify(np,newpr,a,oldar)["reason"],
                         "PRIMARY_JOURNAL_AHEAD_OF_SECONDARY_ANCHOR")

    def test_older_local_db_restored_with_new_signed_heads_blocks(self):
        backup=Path(self.tmp.name)/"preclaim.db"
        with closing(sqlite3.connect(str(backup))) as db:
            self.journal.db.backup(db)
        self.journal.claim_reference_only(intent=self.intent)
        p,pr,a,ar=self.pair()
        self.assertEqual(self.verify(p,pr,a,ar)["state"],MATCH)
        self.journal.close()
        shutil.copyfile(backup,self.path)
        self.journal=self.open_journal()
        self.assertEqual(self.verify(p,pr,a,ar)["reason"],
                         "LOCAL_DISPATCH_JOURNAL_ROLLED_BACK")
        # The low-level #1133 claim alone is NOT safe after restoring SQLite.
        self.assertEqual(self.journal.claim_reference_only(
            intent=self.intent)["state"],
            "LOCAL_REFERENCE_CLAIM_RECORDED_UNTRUSTED")

    def test_full_restore_of_journal_and_signed_heads_negative_control(self):
        p,pr,a,ar=self.pair()
        self.journal.claim_reference_only(intent=self.intent)
        self.journal.close()
        self.path.unlink()
        self.journal=self.open_journal()
        self.journal.prepare_reference_only(self.intent)
        # Full fabricated old state with stale matching signatures cannot
        # be distinguished by the mathematical verifier.
        self.assertEqual(self.verify(p,pr,a,ar)["reason"],
                         "NOT_DISPATCH_CLAIMED_OR_UNKNOWN")
        self.assertFalse(self.verify(p,pr,a,ar)["public_keys_enrolled"])

    def test_signed_same_sequence_different_snapshot_detected(self):
        self.journal.claim_reference_only(intent=self.intent)
        p,pr,a,ar=self.pair()
        forged=deepcopy(ar)
        forged["payload"]["journal_snapshot_sha256"]="0"*64
        forged["signature_hex"]=self.keys["SECONDARY_ANCHOR"].sign(
            canonical_dispatch_journal_read(forged["payload"])
        ).hex()
        self.assertEqual(self.verify(p,pr,a,forged)["reason"],
                         "SAME_SEQUENCE_JOURNAL_HEAD_FORK")

    def test_signed_nonce_replay_challenge_and_role_swaps_rejected(self):
        self.journal.claim_reference_only(intent=self.intent)
        p,pr,a,ar=self.pair()
        q=self.query()
        self.assertEqual(self.verify(q,pr,a,ar)["reason"],
                         "PRIMARY_SIGNED_HEAD_CHALLENGE_OR_SCOPE_MISMATCH")
        self.assertEqual(self.verify(p,ar,a,pr)["state"],"BLOCKED")
        forged=deepcopy(pr)
        forged["signature_hex"]="0"*128
        self.assertEqual(self.verify(p,forged,a,ar)["reason"],
                         "PRIMARY_SIGNED_HEAD_SIGNATURE_MATH_INVALID")

    def test_provider_request_digest_binding_blocks_switch(self):
        self.journal.claim_reference_only(intent=self.intent)
        p,pr,a,ar=self.pair()
        changed=deepcopy(self.intent)
        changed["full_provider_request_sha256"]="1"*64
        self.assertEqual(self.verify(p,pr,a,ar,intent=changed)["state"],"BLOCKED")

    def test_unknown_outcome_after_lost_provider_reply_never_grants_retry(self):
        self.journal.claim_reference_only(intent=self.intent)
        self.journal.mark_unknown_reference_only(nonce_hex=self.intent["nonce_hex"])
        p,pr,a,ar=self.pair()
        self.assertEqual(self.verify(p,pr,a,ar)["state"],MATCH)
        self.assertEqual(self.verify(p,pr,a,ar)[
            "matching_reference_head"]["intent_state"],STATE_UNKNOWN)
        self.assertTrue(self.verify(p,pr,a,ar)["must_not_automatically_retry"])
        self.assertFalse(self.verify(p,pr,a,ar)["paid_request_sent"])

    def test_evidence_updates_journal_sequence_and_prevents_old_head_reuse(self):
        self.journal.claim_reference_only(intent=self.intent)
        p,pr,a,ar=self.pair()
        self.assertEqual(self.verify(p,pr,a,ar)["state"],MATCH)
        before=local_journal_intent_commitment(self.journal,intent=self.intent)
        result=self.journal.append_evidence_digest_reference_only(
            nonce_hex=self.intent["nonce_hex"],evidence_sha256="8"*64,
        )
        after=local_journal_intent_commitment(self.journal,intent=self.intent)
        self.assertEqual(result["journal_sequence"],before["journal_sequence"]+1)
        self.assertEqual(after["journal_sequence"],before["journal_sequence"]+1)
        self.assertNotEqual(before["journal_snapshot_sha256"],
                            after["journal_snapshot_sha256"])
        self.assertEqual(self.verify(p,pr,a,ar)["reason"],
                         "LOCAL_CLAIM_UNANCHORED_OR_UNKNOWN_GAP")

    def test_second_evidence_same_digest_does_not_increment_sequence(self):
        self.journal.claim_reference_only(intent=self.intent)
        result=self.journal.append_evidence_digest_reference_only(
            nonce_hex=self.intent["nonce_hex"],evidence_sha256="8"*64,
        )
        seq=result["journal_sequence"]
        same=self.journal.append_evidence_digest_reference_only(
            nonce_hex=self.intent["nonce_hex"],evidence_sha256="8"*64,
        )
        self.assertEqual(same["journal_sequence"],seq)

    def test_new_signing_pin_substitution_is_math_only_negative_control(self):
        self.journal.claim_reference_only(intent=self.intent)
        p,pr,a,ar=self.pair()
        forged_key=Ed25519PrivateKey.generate()
        fake_pin=pin(forged_key,"secondary_anchor")
        forged=deepcopy(ar)
        forged["signature_hex"]=forged_key.sign(
            canonical_dispatch_journal_read(forged["payload"])
        ).hex()
        o=self.verify(p,pr,a,forged,anchor_pin=fake_pin)
        self.assertEqual(o["state"],MATCH)
        self.assertFalse(o["public_keys_enrolled"])
        self.assertFalse(o["two_independent_head_freshness_verified"])

    def test_parallel_reference_claims_one_winner_not_paid_api(self):
        def task(_):
            j=self.open_journal()
            try:
                return j.claim_reference_only(intent=self.intent)["state"]
            finally:
                j.close()
        with ThreadPoolExecutor(max_workers=5) as pool:
            outcomes=list(pool.map(task,range(12)))
        self.assertEqual(outcomes.count(
            "LOCAL_REFERENCE_CLAIM_RECORDED_UNTRUSTED"),1)
        self.assertEqual(outcomes.count(
            "REPLAY_BLOCKED_NO_SECOND_DISPATCH"),11)
        p,pr,a,ar=self.pair()
        self.assertEqual(self.verify(p,pr,a,ar)["state"],MATCH)
        self.assertFalse(self.verify(p,pr,a,ar)["paid_request_authorized"])

    def test_corrupted_journal_fails_closed_even_signed_heads(self):
        self.journal.claim_reference_only(intent=self.intent)
        p,pr,a,ar=self.pair()
        self.journal.db.execute(
            "UPDATE aion_dispatch_intents SET intent_sha256=?",
            ("0"*64,),
        )
        self.assertEqual(self.verify(p,pr,a,ar)["reason"],
                         "JOURNAL_LOCAL_SNAPSHOT_UNAVAILABLE_OR_CORRUPT")

    def test_no_paid_request_or_network_even_mathematical_match(self):
        self.journal.claim_reference_only(intent=self.intent)
        p,pr,a,ar=self.pair()
        with patch("requests.post",side_effect=AssertionError("network")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("provider")):
            self.assertEqual(self.verify(p,pr,a,ar)["state"],MATCH)


if __name__=="__main__":
    unittest.main()
