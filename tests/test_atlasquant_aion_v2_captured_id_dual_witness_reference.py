"""Synthetic signed capture highwater: rollback, fork, fake roots and GET only."""
from __future__ import annotations

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
    ReferenceOneShotUnknownOutcomeJournal, INTENT_SCHEMA,
)
from atlasquant_aion_v2_readonly_recovery_id_capture_reference import (
    ReferenceDurableRecoveryIdCapture, CAPTURE_SCHEMA,
)
from atlasquant_aion_v2_dispatch_journal_dual_witness_reference import (
    unsigned_journal_head_candidate,canonical_dispatch_journal_read,
)
from atlasquant_aion_v2_captured_id_dual_witness_reference import (
    SCHEMA,READ_SCHEMA,PURPOSE,DOMAIN,ZERO,MATCH,FENCE,
    STATE_CAPTURED,STATE_ABSENT,
    canonical_capture_witness_read,unsigned_capture_witness_candidate,
    local_capture_commitment,review_double_witnessed_capture_for_offline_get,
    review_one_step_capture_anchor_preflight,
)


def pin(key,role):
    return {
        "key_id":"fixture-"+role.lower(),
        "public_key_hex":key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex(),
    }


class SignedCaptureReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.cp=self.root/"captures.db"
        self.jp=self.root/"journal.db"
        self.config={
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "period_id":"2026-10","policy_generation":9,
            "max_period_micro_usd":500,
        }
        self.intent={
            "schema":INTENT_SCHEMA,
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "conversation_id":"conversation","message_id":"message-one",
            "nonce_hex":"a"*64,"signed_v2_intent_sha256":"b"*64,
            "full_provider_request_sha256":"c"*64,
            "primary_witness_receipt_sha256":"d"*64,
            "secondary_anchor_receipt_sha256":"e"*64,
            "key_registry_roster_sha256":"f"*64,
            "policy_generation":9,"period_id":"2026-10",
            "max_cost_micro_usd":100,
        }
        self.journal=ReferenceOneShotUnknownOutcomeJournal(self.jp,config=self.config)
        self.capture=ReferenceDurableRecoveryIdCapture(self.cp,journal=self.journal)
        self.assertEqual(self.journal.prepare_reference_only(self.intent)[
            "state"],"PREPARED_REFERENCE_ONLY")
        self.assertEqual(self.journal.claim_reference_only(intent=self.intent)[
            "state"],"LOCAL_REFERENCE_CLAIM_RECORDED_UNTRUSTED")
        self.keys={
            "PRIMARY_WITNESS":Ed25519PrivateKey.generate(),
            "SECONDARY_ANCHOR":Ed25519PrivateKey.generate(),
        }
        self.pins={k:pin(v,k) for k,v in self.keys.items()}
        self.ct=0
        self.capture_data={
            "schema":CAPTURE_SCHEMA,
            "source_kind":"CI_SYNTHETIC_PROVIDER_ID_ALREADY_RECEIVED",
            "provider":"openai","mode":"OPENAI_RESPONSES_BACKGROUND",
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "nonce_hex":"a"*64,"signed_v2_intent_sha256":"b"*64,
            "full_provider_request_sha256":"c"*64,
            "key_registry_roster_sha256":"f"*64,"claim_sequence":2,
            "documented_retention_opt_in":False,
            "locator":{
                "response_id":"resp_known_fixture",
                "batch_id":"","batch_custom_id":"","diagnostic_request_id":"",
            },
        }
        self.journal_args=self.make_journal_heads()

    def tearDown(self):
        self.capture.close()
        self.journal.close()
        self.temp.cleanup()

    def query(self):
        self.ct+=1
        return {
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "period_id":"2026-10","policy_generation":9,
            "key_registry_roster_sha256":"f"*64,"nonce_hex":"a"*64,
            "challenge_nonce_hex":f"{self.ct:064x}",
            "minimum_witness_epoch":4,
        }

    def signed_journal(self,role,q):
        payload=unsigned_journal_head_candidate(
            self.journal,intent=self.intent,query=q,role=role,
            signer_key_id=self.pins[role]["key_id"],witness_epoch=4,
        )
        return {
            "payload":payload,
            "signature_hex":self.keys[role].sign(
                canonical_dispatch_journal_read(payload)).hex(),
        }

    def make_journal_heads(self):
        p=self.query()
        a=self.query()
        return {
            "primary_read":self.signed_journal("PRIMARY_WITNESS",p),
            "primary_pin":self.pins["PRIMARY_WITNESS"],"primary_query":p,
            "anchor_read":self.signed_journal("SECONDARY_ANCHOR",a),
            "anchor_pin":self.pins["SECONDARY_ANCHOR"],"anchor_query":a,
        }

    def head(self,role,query,*,key=None,override=None):
        payload=unsigned_capture_witness_candidate(
            self.capture,journal=self.journal,intent=self.intent,
            query=query,role=role,
            signer_key_id=self.pins[role]["key_id"],witness_epoch=4,
        )
        if override:
            payload.update(override)
        return {
            "payload":payload,
            "signature_hex":(key or self.keys[role]).sign(
                canonical_capture_witness_read(payload)).hex(),
        }

    def pair(self):
        p=self.query()
        a=self.query()
        return p,self.head("PRIMARY_WITNESS",p),a,self.head("SECONDARY_ANCHOR",a)

    def args(self,p,pr,a,ar,**overrides):
        d={
            "capture_db":self.capture,"journal":self.journal,
            "intent":self.intent,"journal_head_args":self.journal_args,
            "primary_query":p,"primary_read":pr,
            "primary_pin":self.pins["PRIMARY_WITNESS"],
            "anchor_query":a,"anchor_read":ar,
            "anchor_pin":self.pins["SECONDARY_ANCHOR"],
        }
        d.update(overrides)
        return d

    def review(self,p,pr,a,ar,**kw):
        x=review_double_witnessed_capture_for_offline_get(
            **self.args(p,pr,a,ar,**kw)
        )
        self.assertEqual(x["schema"],SCHEMA)
        self.assertTrue(x["must_not_automatically_retry"])
        for field in (
            "owner_presence_verified","provider_id_provenance_verified",
            "capture_antirollback_production_verified",
            "independent_fresh_read_verified","real_get_authorized",
            "real_get_performed","paid_post_authorized",
            "paid_post_performed","network_called",
            "billing_settlement_verified","safe_to_resume",
        ):
            self.assertIs(x[field],False,field)
        return x

    def capture_once(self):
        self.assertEqual(self.capture.capture_reference_only(
            journal=self.journal,intent=self.intent,
            observed_capture=self.capture_data,
        )["state"],"LOCAL_PROVIDER_IDENTIFIER_CAPTURE_MATH_ONLY_UNTRUSTED")

    def test_initial_absent_heads_do_not_generate_get_plan(self):
        p,pr,a,ar=self.pair()
        self.assertEqual(self.review(p,pr,a,ar)["reason"],
                         "KNOWN_RESPONSE_ID_NOT_CAPTURED")

    def test_captured_id_two_signed_heads_only_math_get_route(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        v=self.review(p,pr,a,ar)
        self.assertEqual(v["state"],MATCH)
        self.assertEqual(v["offline_relative_get_paths"],[
            {"method":"GET","relative_path":"/v1/responses/resp_known_fixture"}
        ])
        self.assertEqual(v["matching_untrusted_head"]["capture_sequence"],1)
        self.assertTrue(DOMAIN.endswith(b"\x00"))

    def test_one_step_old_absent_to_new_captured_fence_math_only(self):
        op,opr,oa,oar=self.pair()
        self.capture_once()
        np,npr,na,nar=self.pair()
        x=review_one_step_capture_anchor_preflight(
            old_primary_query=op,old_primary_read=opr,
            old_anchor_query=oa,old_anchor_read=oar,
            new_primary_query=np,new_primary_read=npr,
            new_anchor_query=na,new_anchor_read=nar,
            primary_pin=self.pins["PRIMARY_WITNESS"],
            anchor_pin=self.pins["SECONDARY_ANCHOR"],
        )
        self.assertEqual(x["state"],FENCE)
        self.assertFalse(x["capture_external_cas_performed"])
        self.assertFalse(x["secondary_external_cas_performed"])

    def test_later_nonce_capture_monotonic_fence_N_to_N_plus_one_math(self):
        # Synthetic role signatures can represent a later global capture
        # sequence where this nonce had no capture yet, but other IDs did.
        oldp,oldpr,olda,oldar=self.pair()
        self.capture_once()
        newp,newpr,newa,newar=self.pair()
        for role,payload,prior,new_hash in (
            ("PRIMARY_WITNESS",oldpr,5,"1"*64),
            ("SECONDARY_ANCHOR",oldar,5,"1"*64),
            ("PRIMARY_WITNESS",newpr,6,"2"*64),
            ("SECONDARY_ANCHOR",newar,6,"2"*64),
        ):
            payload["payload"]["capture_sequence"]=prior
            payload["payload"]["capture_snapshot_sha256"]=new_hash
            payload["signature_hex"]=self.keys[role].sign(
                canonical_capture_witness_read(payload["payload"])).hex()
        args=dict(
            old_primary_query=oldp,old_primary_read=oldpr,
            old_anchor_query=olda,old_anchor_read=oldar,
            new_primary_query=newp,new_primary_read=newpr,
            new_anchor_query=newa,new_anchor_read=newar,
            primary_pin=self.pins["PRIMARY_WITNESS"],
            anchor_pin=self.pins["SECONDARY_ANCHOR"],
        )
        self.assertEqual(review_one_step_capture_anchor_preflight(
            **args)["state"],FENCE)
        # A missing global event sequence must never be treated as a CAS.
        newpr["payload"]["capture_sequence"]=7
        newar["payload"]["capture_sequence"]=7
        for role,payload in (("PRIMARY_WITNESS",newpr),
                             ("SECONDARY_ANCHOR",newar)):
            payload["signature_hex"]=self.keys[role].sign(
                canonical_capture_witness_read(payload["payload"])).hex()
        self.assertEqual(review_one_step_capture_anchor_preflight(
            **args)["state"],"BLOCKED")

    def test_same_capture_as_old_and_new_cannot_fence_again(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        x=review_one_step_capture_anchor_preflight(
            old_primary_query=p,old_primary_read=pr,
            old_anchor_query=a,old_anchor_read=ar,
            new_primary_query=p,new_primary_read=pr,
            new_anchor_query=a,new_anchor_read=ar,
            primary_pin=self.pins["PRIMARY_WITNESS"],
            anchor_pin=self.pins["SECONDARY_ANCHOR"],
        )
        self.assertEqual(x["state"],"BLOCKED")

    def test_db_restore_older_than_new_witness_heads_blocks(self):
        older=self.root/"old-capture.db"
        with closing(sqlite3.connect(str(older))) as dst:
            self.capture.db.backup(dst)
        self.capture_once()
        p,pr,a,ar=self.pair()
        self.assertEqual(self.review(p,pr,a,ar)["state"],MATCH)
        self.capture.close()
        shutil.copyfile(older,self.cp)
        self.capture=ReferenceDurableRecoveryIdCapture(self.cp,journal=self.journal)
        self.assertEqual(self.review(p,pr,a,ar)["reason"],
                         "LOCAL_CAPTURE_RESTORED_BEHIND_WITNESSES")

    def test_capture_ahead_of_signed_absent_heads_blocks(self):
        p,pr,a,ar=self.pair()
        self.capture_once()
        self.assertEqual(self.review(p,pr,a,ar)["reason"],
                         "UNANCHORED_LOCAL_CAPTURE_ADVANCE")

    def test_primary_head_ahead_secondary_after_capture_blocks(self):
        p,pr,a,ar=self.pair()
        self.capture_once()
        np=self.query()
        new_pr=self.head("PRIMARY_WITNESS",np)
        self.assertEqual(self.review(np,new_pr,a,ar)["reason"],
                         "PRIMARY_CAPTURE_AHEAD_OF_SECOND_ANCHOR")

    def test_primary_old_secondary_new_after_capture_blocks(self):
        p,pr,a,ar=self.pair()
        self.capture_once()
        na=self.query()
        new_ar=self.head("SECONDARY_ANCHOR",na)
        self.assertEqual(self.review(p,pr,na,new_ar)["reason"],
                         "PRIMARY_CAPTURE_ROLLBACK_BEHIND_ANCHOR")

    def test_same_sequence_distinct_event_digest_signed_fork_blocks(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        conflicting=deepcopy(ar)
        conflicting["payload"]["capture_event_sha256"]="7"*64
        conflicting["signature_hex"]=self.keys["SECONDARY_ANCHOR"].sign(
            canonical_capture_witness_read(conflicting["payload"])
        ).hex()
        self.assertEqual(self.review(p,pr,a,conflicting)["reason"],
                         "SAME_SEQUENCE_CAPTURE_FORK")

    def test_both_capture_heads_match_but_journal_changed_blocks(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        self.journal.mark_unknown_reference_only(nonce_hex=self.intent["nonce_hex"])
        self.assertEqual(self.review(p,pr,a,ar)["reason"],
                         "DISPATCH_JOURNAL_NOT_DUAL_WITNESSED")

    def test_capture_head_claim_digest_tamper_signed_but_wrong_local(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        bad=deepcopy(pr)
        bad["payload"]["full_provider_request_sha256"]="8"*64
        bad["signature_hex"]=self.keys["PRIMARY_WITNESS"].sign(
            canonical_capture_witness_read(bad["payload"])
        ).hex()
        self.assertEqual(self.review(p,bad,a,ar)["state"],"BLOCKED")

    def test_stale_challenge_replay_blocks(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        newp=self.query()
        self.assertEqual(self.review(newp,pr,a,ar)["reason"],
                         "PRIMARY_READ_SIGNED_NONCE_SCOPE_OR_EPOCH_FLOOR_MISMATCH")

    def test_epoch_floor_downgrade_or_changed_scope_blocks(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        for field,value in (("minimum_witness_epoch",3),
                            ("tenant_id","other"),
                            ("key_registry_roster_sha256","0"*64)):
            with self.subTest(field=field):
                q=deepcopy(a)
                q[field]=value
                self.assertEqual(self.review(p,pr,q,ar)["state"],"BLOCKED")

    def test_swapped_roles_or_bad_signature_blocks(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        self.assertEqual(self.review(p,ar,a,pr)["state"],"BLOCKED")
        bad=deepcopy(ar)
        bad["signature_hex"]="0"*128
        self.assertEqual(self.review(p,pr,a,bad)["reason"],
                         "SECONDARY_SIGNATURE_MATH_INVALID")

    def test_pin_substitution_still_passes_math_negative_control(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        attacker=Ed25519PrivateKey.generate()
        fakepin=pin(attacker,"SECONDARY_ANCHOR")
        fake=deepcopy(ar)
        fake["signature_hex"]=attacker.sign(
            canonical_capture_witness_read(fake["payload"])
        ).hex()
        out=self.review(p,pr,a,fake,anchor_pin=fakepin)
        self.assertEqual(out["state"],MATCH)
        self.assertFalse(out["second_anchor_live_enrolled"])
        self.assertFalse(out["real_get_authorized"])

    def test_missing_remote_witness_must_block_even_valid_local_capture(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        self.assertEqual(self.review(p,pr,a,None)["state"],"BLOCKED")
        self.assertEqual(self.review(p,pr,a,ar,journal_head_args={})["state"],
                         "BLOCKED")

    def test_malformed_signed_payload_and_authority_injection_block(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        for key in list(ar["payload"]):
            with self.subTest(field=key):
                bad=deepcopy(ar)
                bad["payload"].pop(key)
                self.assertEqual(self.review(p,pr,a,bad)["state"],"BLOCKED")
        bad=deepcopy(pr)
        bad["payload"]["post_authorized"]=True
        self.assertEqual(self.review(p,bad,a,ar)["state"],"BLOCKED")

    def test_local_capture_corruption_blocks_even_unchanged_signed_heads(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        self.capture.db.execute(
            "UPDATE aion_recovery_ids_ref SET capture_sha256=?",
            ("0"*64,),
        )
        self.assertEqual(self.review(p,pr,a,ar)["reason"],
                         "CAPTURE_LOCAL_REFERENCE_UNAVAILABLE_OR_CORRUPT")

    def test_fake_signatures_and_restored_synchronous_history_remain_untrusted(self):
        # An adversary with all prior pins/heads and previous local files
        # can present a math-valid historical capture after later activity.
        self.capture_once()
        p,pr,a,ar=self.pair()
        self.assertEqual(self.review(p,pr,a,ar)["state"],MATCH)
        self.assertFalse(self.review(p,pr,a,ar)[
            "capture_antirollback_production_verified"])
        self.assertFalse(self.review(p,pr,a,ar)["real_get_performed"])

    def test_no_live_get_post_or_provider_generation_even_in_math_match(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        with patch("requests.get",side_effect=AssertionError("GET")), \
             patch("requests.post",side_effect=AssertionError("POST")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("MODEL")):
            o=self.review(p,pr,a,ar)
            self.assertEqual(o["state"],MATCH)
        self.assertFalse(o["network_called"])

    def test_unchanged_journal_but_unenrolled_witness_signers_never_become_authority(self):
        self.capture_once()
        p,pr,a,ar=self.pair()
        o=self.review(p,pr,a,ar)
        self.assertTrue(o["mathematical_candidate_only"])
        self.assertFalse(o["real_get_authorized"])
        self.assertFalse(o["paid_post_authorized"])
        self.assertFalse(o["provider_exactly_once_verified"])


if __name__=="__main__":
    unittest.main()
