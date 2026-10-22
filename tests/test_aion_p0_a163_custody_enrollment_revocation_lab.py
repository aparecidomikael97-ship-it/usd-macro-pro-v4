"""A163: ephemeral 5-role Ed25519 custody ceremony, key rotation, revocation.

Each test uses disposable keys and local SQLite. Caller-supplied issuer
and anchor simulate trust; these tests NEVER establish independent real
administrators, monotonic storage, owner FIDO2 or provider effect.
"""
import base64
from contextlib import closing
from dataclasses import replace
import os
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_p0_a145_authenticated_checkpoint_lab import SignedCheckpoint,checkpoint_payload
from aion_p0_a145_checkpoint_verifier_lab import Checkpoint,canonical_history_digest
from aion_p0_a147_sqlite_crash_journal_lab import SyntheticCrashJournalLAB
from aion_p0_a150_pinned_policy_lease_lab import LeasedPinnedWitnessLAB
from aion_p0_a161_dual_custodian_floor_lab import (
    FloorClaim,SignedFloor,AUDIENCE,canonical_claim_bytes,
)
from aion_p0_a163_custody_enrollment_revocation_lab import (
    CustodyRejected,PolicyEvent,SignedPolicyEvent,PolicyAnchor,
    CustodyReview,VerifiedPolicyLAB,SCHEMA,
    POLICY_DOMAIN,POP_DOMAIN,RETIRE_DOMAIN,canonical_policy_bytes,
    policy_event_digest,validate_policy_chain,assess_enrollment_and_recovery,
)


def pub(private):
    return private.public_key().public_bytes(
        serialization.Encoding.Raw,serialization.PublicFormat.Raw)


def priv(private):
    return private.private_bytes(
        serialization.Encoding.Raw,serialization.PrivateFormat.Raw,
        serialization.NoEncryption())


def signature(private,message):
    return base64.b64encode(private.sign(message)).decode("ascii")


class A163CustodyEnrollmentRotationRevocationLAB(unittest.TestCase):
    def setUp(self):
        p=patch.dict(os.environ,{
            "AION_LAB_MODE":"1",
            "AION_WORKER_ENABLED":"0",
            "AION_EXTERNAL_EXECUTION_ENABLED":"0",
        })
        p.start()
        self.addCleanup(p.stop)
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root=Path(folder.name)
        (root/"journal").mkdir()
        (root/"witness").mkdir()
        self.now=1_800_000_000_000_000_000
        self.issuer=Ed25519PrivateKey.generate()
        self.d1=Ed25519PrivateKey.generate()
        self.d2=Ed25519PrivateKey.generate()
        self.publisher=Ed25519PrivateKey.generate()
        self.witness_key=Ed25519PrivateKey.generate()
        self.cp_signer=Ed25519PrivateKey.generate()
        self.ledger="ledger-A"
        self.journal=SyntheticCrashJournalLAB.bootstrap_synthetic_lab(
            lab_dir=root/"journal",ledger_id=self.ledger,
        )
        self.witness=LeasedPinnedWitnessLAB.bootstrap_synthetic(
            witness_dir=root/"witness",ledger_id=self.ledger,
            publisher_key_id="publisher-1",
            publisher_public_key=pub(self.publisher),
            witness_private_key=priv(self.witness_key),
            clock_ns=lambda:self.now,
        )
        self.epoch=self.witness.policy.epoch
        self.nonce="b"*32
        self.records=[]
        self.old_d1=None
        self.old_d2=None
        self.add_event("ENROLL",d1=self.d1,d2=self.d2)

    def make_record(self,action,d1,d2,*,issuer=None,old_d1=None,old_d2=None,
                    generation=None,previous_digest=None,issued_ns=None,nonce=None,
                    ledger=None,epoch=None):
        n=len(self.records)+1 if generation is None else generation
        digest=("0"*64 if n==1 else policy_event_digest(self.records[-1]))
        ev=PolicyEvent(
            ledger_id=self.ledger if ledger is None else ledger,
            epoch=self.epoch if epoch is None else epoch,
            generation=n,action=action,
            previous_digest=digest if previous_digest is None else previous_digest,
            d1_public_hex=pub(d1).hex() if d1 is not None else "",
            d2_public_hex=pub(d2).hex() if d2 is not None else "",
            request_nonce=secrets.token_hex(16) if nonce is None else nonce,
            issued_ns=self.now+n*1_000_000_000 if issued_ns is None else issued_ns,
        )
        payload=canonical_policy_bytes(ev)
        return SignedPolicyEvent(
            event=ev,
            issuer_signature_b64=signature(self.issuer if issuer is None else issuer,payload),
            d1_pop_b64=signature(d1,POP_DOMAIN+payload) if d1 is not None else "",
            d2_pop_b64=signature(d2,POP_DOMAIN+payload) if d2 is not None else "",
            old_d1_retire_b64=(signature(old_d1,RETIRE_DOMAIN+payload)
                               if old_d1 is not None else ""),
            old_d2_retire_b64=(signature(old_d2,RETIRE_DOMAIN+payload)
                               if old_d2 is not None else ""),
        )

    def add_event(self,action,*,d1=None,d2=None,issuer=None,
                  old_d1=None,old_d2=None):
        record=self.make_record(action,d1,d2,issuer=issuer,
                                old_d1=old_d1,old_d2=old_d2)
        self.records.append(record)
        if d1 is not None:
            self.d1=d1
        if d2 is not None:
            self.d2=d2
        return record

    def rotate(self,d1=None,d2=None,**kwargs):
        prior_d1,prior_d2=self.d1,self.d2
        new1=Ed25519PrivateKey.generate() if d1 is None else d1
        new2=Ed25519PrivateKey.generate() if d2 is None else d2
        self.add_event("ROTATE",d1=new1,d2=new2,
                       old_d1=prior_d1,old_d2=prior_d2,**kwargs)
        return prior_d1,prior_d2

    def revoke(self):
        return self.add_event("REVOKE_ALL")

    def anchor(self):
        last=self.records[-1]
        return PolicyAnchor(self.ledger,self.epoch,len(self.records),
                            policy_event_digest(last))

    def checkpoint(self):
        events=self.journal.read_events()
        item=Checkpoint(self.ledger,len(events),canonical_history_digest(events))
        return SignedCheckpoint(
            item,"checkpoint",signature(self.cp_signer,checkpoint_payload(item)),
        )

    def floors(self,d1=None,d2=None,claim=None):
        meta=self.witness.read_head()
        item=(claim if claim is not None else FloorClaim(
            ledger_id=self.ledger,epoch=self.epoch,
            sequence=meta["sequence"],history_digest=meta["digest"],
            request_nonce=self.nonce,audience=AUDIENCE,
            observed_ns=self.now-1_000_000_000,
            valid_until_ns=self.now+4_000_000_000,
        ))
        key1=self.d1 if d1 is None else d1
        key2=self.d2 if d2 is None else d2
        return (
            SignedFloor(item,"d1",signature(key1,canonical_claim_bytes(item))),
            SignedFloor(item,"d2",signature(key2,canonical_claim_bytes(item))),
        )

    def verify(self,*,records=None,issuer_key=None,anchor=None,ledger=None,epoch=None):
        return validate_policy_chain(
            signed_events=self.records if records is None else records,
            trusted_issuer_public_key=(pub(self.issuer) if issuer_key is None else issuer_key),
            required_anchor=self.anchor() if anchor is None else anchor,
            ledger_id=self.ledger if ledger is None else ledger,
            epoch=self.epoch if epoch is None else epoch,
        )

    def decision(self,*,records=None,issuer_key=None,anchor=None,
                 d1=None,d2=None,ledger=None,epoch=None,nonce=None,now=None,
                 cp_pins=None,journal=None,witness=None):
        one,two=self.floors()
        return assess_enrollment_and_recovery(
            signed_events=self.records if records is None else records,
            trusted_issuer_public_key=(pub(self.issuer) if issuer_key is None else issuer_key),
            required_anchor=self.anchor() if anchor is None else anchor,
            ledger_id=self.ledger if ledger is None else ledger,
            epoch=self.epoch if epoch is None else epoch,
            journal=self.journal if journal is None else journal,
            local_witness=self.witness if witness is None else witness,
            checkpoint=self.checkpoint(),
            checkpoint_pins=({"checkpoint":pub(self.cp_signer)}
                             if cp_pins is None else cp_pins),
            floor_d1=one if d1 is None else d1,
            floor_d2=two if d2 is None else d2,
            request_nonce=self.nonce if nonce is None else nonce,
            now_ns=self.now if now is None else now,
        )

    def invariant(self,result):
        self.assertIs(type(result),CustodyReview)
        self.assertEqual(result.schema,SCHEMA)
        self.assertIn(result.verdict,("LAB_HARD_BLOCKED","LAB_QUARANTINE_MANUAL_REVIEW"))
        for name in (
            "actual_independent_issuer_custody_verified",
            "actual_independent_d1_d2_administrators_verified",
            "out_of_band_irreversible_anchor_verified",
            "owner_consent_verified",
            "provider_effect_or_no_effect_verified",
            "live_enrollment_performed",
            "checkpoint_restore_allowed",
            "worker_allowed","external_execution_allowed",
            "automatic_retry_allowed","automatic_resend_allowed",
        ):
            self.assertIs(getattr(result,name),False,name)
        self.assertEqual(result.homologated_p0_count,0)

    def denied(self,contains=None,**kwargs):
        result=self.decision(**kwargs)
        self.invariant(result)
        self.assertEqual(result.verdict,"LAB_HARD_BLOCKED",result)
        if contains:
            self.assertIn(contains,result.reason)
        return result

    def quarantine(self,**kwargs):
        result=self.decision(**kwargs)
        self.invariant(result)
        self.assertEqual(result.verdict,"LAB_QUARANTINE_MANUAL_REVIEW",result)
        self.assertTrue(result.synthetic_policy_signatures_valid)
        self.assertTrue(result.generation_checked_against_caller_anchor)
        self.assertTrue(result.mathematical_three_source_match)
        return result

    def test_01_genesis_current_floors_only_quarantine(self):
        self.quarantine()

    def test_02_genesis_cryptographic_policy_chain_checks(self):
        state=self.verify()
        self.assertIs(type(state),VerifiedPolicyLAB)
        self.assertEqual(state.generation,1)
        self.assertEqual(state.d1_key,pub(self.d1))
        self.assertFalse(state.terminal_revoked)

    def test_03_enroll_domains_are_separate(self):
        ev=self.records[0].event
        self.assertTrue(canonical_policy_bytes(ev).startswith(POLICY_DOMAIN))
        self.assertNotEqual(POP_DOMAIN,RETIRE_DOMAIN)

    def test_04_rotate_both_keys_current_floor_quarantines(self):
        self.rotate()
        self.quarantine()

    def test_05_rotate_changes_generation_and_digest(self):
        before=self.anchor()
        self.rotate()
        after=self.anchor()
        self.assertEqual(after.generation,2)
        self.assertNotEqual(before.chain_digest,after.chain_digest)

    def test_06_second_consecutive_rotation_works_with_new_key_material(self):
        self.rotate()
        self.rotate()
        self.quarantine()
        self.assertEqual(self.verify().generation,3)

    def test_07_three_successful_rotations_with_all_keys_distinct(self):
        for _ in range(3):self.rotate()
        self.quarantine()
        self.assertEqual(self.verify().generation,4)

    def test_08_old_floor_signature_denied_after_rotation(self):
        old1,old2=self.rotate()
        a,b=self.floors(old1,old2)
        self.denied("a162_three_source_rejected",d1=a,d2=b)

    def test_09_old_d1_signature_denied_after_rotation(self):
        old1,_=self.rotate()
        a,b=self.floors(old1,self.d2)
        self.denied(d1=a,d2=b)

    def test_10_old_d2_signature_denied_after_rotation(self):
        _,old2=self.rotate()
        a,b=self.floors(self.d1,old2)
        self.denied(d1=a,d2=b)

    def test_11_revocation_current_floor_even_if_signed_is_blocked(self):
        self.revoke()
        self.denied("terminal_revocation_blocks_all_floor_signers")

    def test_12_revocation_does_not_create_new_custody_keys(self):
        self.revoke()
        state=self.verify()
        self.assertTrue(state.terminal_revoked)
        self.assertEqual(state.d1_key,b"")
        self.assertEqual(state.d2_key,b"")

    def test_13_rotate_then_revoke_blocks_new_floor(self):
        self.rotate()
        self.revoke()
        self.denied("terminal_revocation_blocks_all_floor_signers")

    def test_14_revocation_followed_by_enroll_is_forbidden(self):
        self.revoke()
        r=self.make_record("ENROLL",Ed25519PrivateKey.generate(),
                           Ed25519PrivateKey.generate())
        with self.assertRaises(CustodyRejected):
            self.verify(records=[*self.records,r],
                        anchor=PolicyAnchor(self.ledger,self.epoch,3,
                                           policy_event_digest(r)))

    def test_15_revocation_followed_by_rotation_is_forbidden(self):
        self.revoke()
        self.rotate()
        self.denied("terminal_revocation_forbids_reenrollment")

    def test_16_genesis_cannot_be_revocation(self):
        record=self.make_record("REVOKE_ALL",None,None,generation=1,
                                previous_digest="0"*64)
        with self.assertRaises(CustodyRejected):
            self.verify(records=[record],anchor=PolicyAnchor(
                self.ledger,self.epoch,1,policy_event_digest(record)))

    def test_17_old_anchor_after_rotation_fails_closed(self):
        stale=self.anchor()
        self.rotate()
        self.denied("out_of_band_anchor_does_not_match_latest_generation",anchor=stale)

    def test_18_old_policy_records_with_new_anchor_fail_closed(self):
        old=list(self.records)
        self.rotate()
        self.denied("out_of_band_anchor_does_not_match_latest_generation",records=old)

    def test_19_new_policy_records_signed_under_unpinned_issuer_denied(self):
        self.rotate()
        self.denied(issuer_key=pub(Ed25519PrivateKey.generate()))

    def test_20_missing_anchor_is_hard_block(self):
        self.denied(anchor=False)

    def test_21_replacement_anchor_not_same_digest_denied(self):
        anchor=replace(self.anchor(),chain_digest="f"*64)
        self.denied(anchor=anchor)

    def test_22_anchor_old_ledger_denied(self):
        anchor=replace(self.anchor(),ledger_id="different")
        self.denied(anchor=anchor)

    def test_23_anchor_old_epoch_denied(self):
        anchor=replace(self.anchor(),epoch="f"*32)
        self.denied(anchor=anchor)

    def test_24_duplicate_issuer_key_used_for_custodian_denied(self):
        same=self.issuer
        forged=self.make_record("ENROLL",same,self.d2,generation=1,
                                previous_digest="0"*64)
        self.denied(records=[forged],anchor=PolicyAnchor(
            self.ledger,self.epoch,1,policy_event_digest(forged)))

    def test_25_same_d1_and_d2_key_is_denied(self):
        forged=self.make_record("ENROLL",self.d1,self.d1,generation=1,
                                previous_digest="0"*64)
        self.denied(records=[forged],anchor=PolicyAnchor(
            self.ledger,self.epoch,1,policy_event_digest(forged)))

    def test_26_reusing_retired_d1_key_denied(self):
        old1,_=self.rotate()
        self.rotate(d1=old1)
        self.denied("reused_or_shared_custodian_key")

    def test_27_reusing_retired_d2_key_denied(self):
        _,old2=self.rotate()
        self.rotate(d2=old2)
        self.denied("reused_or_shared_custodian_key")

    def test_28_reusing_retired_d1_as_new_d2_denied(self):
        old1,_=self.rotate()
        self.rotate(d2=old1)
        self.denied("reused_or_shared_custodian_key")

    def test_29_rotation_missing_old_d1_ack_denied(self):
        self.rotate()
        x=self.records[-1]
        mod=replace(x,old_d1_retire_b64="")
        self.denied("previous_d1_retirement_ack",records=[*self.records[:-1],mod])

    def test_30_rotation_missing_old_d2_ack_denied(self):
        self.rotate()
        x=self.records[-1]
        mod=replace(x,old_d2_retire_b64="")
        self.denied("previous_d2_retirement_ack",records=[*self.records[:-1],mod])

    def test_31_rotation_wrong_old_d1_ack_denied(self):
        self.rotate()
        x=self.records[-1]
        mod=replace(x,old_d1_retire_b64=signature(self.issuer,b"bad"))
        self.denied("previous_d1_retirement_ack",records=[*self.records[:-1],mod])

    def test_32_rotation_wrong_old_d2_ack_denied(self):
        self.rotate()
        x=self.records[-1]
        mod=replace(x,old_d2_retire_b64=signature(self.issuer,b"bad"))
        self.denied("previous_d2_retirement_ack",records=[*self.records[:-1],mod])

    def test_33_rotation_missing_new_d1_pop_denied(self):
        self.rotate()
        r=self.records[-1]
        self.denied("d1_proof_of_possession",records=[*self.records[:-1],
                                                      replace(r,d1_pop_b64="")])

    def test_34_rotation_missing_new_d2_pop_denied(self):
        self.rotate()
        r=self.records[-1]
        self.denied("d2_proof_of_possession",records=[*self.records[:-1],
                                                      replace(r,d2_pop_b64="")])

    def test_35_genesis_missing_new_d1_pop_denied(self):
        r=self.records[0]
        self.denied("d1_proof_of_possession",records=[
            replace(r,d1_pop_b64="")])

    def test_36_genesis_missing_new_d2_pop_denied(self):
        r=self.records[0]
        self.denied("d2_proof_of_possession",records=[
            replace(r,d2_pop_b64="")])

    def test_37_genesis_with_fake_prior_ack_denied(self):
        r=self.records[0]
        self.denied("genesis_cannot_have_previous_ack",records=[
            replace(r,old_d1_retire_b64="X")])

    def test_38_issuer_signature_corrupted_denied(self):
        r=self.records[0]
        self.denied("issuer_signature_invalid",records=[
            replace(r,issuer_signature_b64=signature(self.d1,b"forged"))])

    def test_39_signed_generation_gap_denied(self):
        self.rotate()
        r=self.records[-1]
        ev=replace(r.event,generation=3)
        sign=replace(r,event=ev,issuer_signature_b64=signature(
            self.issuer,canonical_policy_bytes(ev)))
        self.denied("policy_generation_gap_or_fork",records=[self.records[0],sign])

    def test_40_signed_previous_digest_fork_denied(self):
        self.rotate()
        r=self.records[-1]
        ev=replace(r.event,previous_digest="f"*64)
        sign=replace(r,event=ev,issuer_signature_b64=signature(
            self.issuer,canonical_policy_bytes(ev)))
        self.denied("policy_history_digest_mismatch",records=[self.records[0],sign])

    def test_41_duplicate_nonce_after_rotation_denied(self):
        self.rotate()
        r=self.records[-1]
        ev=replace(r.event,request_nonce=self.records[0].event.request_nonce)
        sign=replace(r,event=ev,issuer_signature_b64=signature(
            self.issuer,canonical_policy_bytes(ev)))
        self.denied("reused_enrollment_request_nonce",records=[self.records[0],sign])

    def test_42_issued_timestamp_out_of_order_denied(self):
        self.rotate()
        r=self.records[-1]
        ev=replace(r.event,issued_ns=self.records[0].event.issued_ns)
        sign=replace(r,event=ev,issuer_signature_b64=signature(
            self.issuer,canonical_policy_bytes(ev)))
        self.denied("policy_timestamp_not_strictly_increasing",records=[self.records[0],sign])

    def test_43_unknown_policy_action_denied(self):
        r=self.records[0]
        ev=replace(r.event,action="RESTORE_AND_GO")
        self.denied(records=[replace(r,event=ev)])

    def test_44_old_signed_floor_under_same_public_epoch_cannot_pass_new_gen(self):
        oldfloor=self.floors()
        self.rotate()
        self.denied(d1=oldfloor[0],d2=oldfloor[1])

    def test_45_old_d1_key_with_new_nonce_still_not_authorized(self):
        old1,old2=self.rotate()
        fresh=replace(self.floors()[0].claim,request_nonce=self.nonce)
        a,b=self.floors(old1,old2,claim=fresh)
        self.denied(d1=a,d2=b)

    def test_46_lost_local_journal_never_auto_rebootstraps(self):
        # Cache VALID checkpoint and current dual-signed floor before loss:
        # prove that actual journal absence (rather than a fake checkpoint)
        # is what causes the fail-closed decision.
        cp=self.checkpoint()
        one,two=self.floors()
        self.journal.path.unlink()
        result=assess_enrollment_and_recovery(
            signed_events=self.records,trusted_issuer_public_key=pub(self.issuer),
            required_anchor=self.anchor(),ledger_id=self.ledger,epoch=self.epoch,
            journal=self.journal,local_witness=self.witness,
            checkpoint=cp,checkpoint_pins={"checkpoint":pub(self.cp_signer)},
            floor_d1=one,floor_d2=two,request_nonce=self.nonce,now_ns=self.now,
        )
        self.invariant(result)
        self.assertEqual(result.verdict,"LAB_HARD_BLOCKED")
        self.assertIn("missing_or_linked_journal",result.reason)
        self.assertFalse(self.journal.path.exists())

    def test_47_snapshot_both_policy_and_anchor_to_old_generation_still_quarantine(self):
        old_policy=list(self.records)
        old_anchor=self.anchor()
        old_floor=self.floors()
        self.rotate()
        # Critical impossibility: attacker controls caller-provided "trusted"
        # head AND old keys, so both may appear self-consistent again.
        r=self.quarantine(records=old_policy,anchor=old_anchor,
                          d1=old_floor[0],d2=old_floor[1])
        self.assertFalse(r.out_of_band_irreversible_anchor_verified)

    def test_48_external_anchor_newer_than_restored_policy_blocks(self):
        old_policy=list(self.records)
        self.rotate()
        self.denied("out_of_band_anchor_does_not_match_latest_generation",
                    records=old_policy)

    def test_49_out_of_band_issuer_pin_must_be_passed_not_read_from_event(self):
        self.denied(issuer_key=pub(Ed25519PrivateKey.generate()))

    def test_50_no_embedded_vendor_approval_or_worker_authority_fields(self):
        result=self.quarantine()
        self.assertFalse(result.live_enrollment_performed)
        self.assertFalse(result.worker_allowed)

    def test_51_revoke_requires_zero_new_custodian_keys(self):
        self.revoke()
        r=self.records[-1]
        ev=replace(r.event,d1_public_hex=pub(self.d1).hex())
        self.denied(records=[*self.records[:-1],replace(r,event=ev)])

    def test_52_revoke_rejects_forged_new_key_proof(self):
        self.revoke()
        r=self.records[-1]
        self.denied("revoke_must_not_claim_new_key_proofs",
                    records=[*self.records[:-1],replace(r,d1_pop_b64="fake")])

    def test_53_signed_revoke_under_other_issuer_denied(self):
        self.revoke()
        r=self.records[-1]
        ev=r.event
        self.denied("issuer_signature_invalid",records=[
            *self.records[:-1],replace(r,issuer_signature_b64=signature(
                Ed25519PrivateKey.generate(),canonical_policy_bytes(ev)))])

    def test_54_two_revocations_in_same_epoch_forbidden(self):
        self.revoke()
        self.revoke()
        self.denied("terminal_revocation_forbids_reenrollment")

    def test_55_genesis_wrong_initial_previous_digest_denied(self):
        r=self.records[0]
        ev=replace(r.event,previous_digest="f"*64)
        self.denied("policy_history_digest_mismatch",records=[replace(r,event=ev)])

    def test_56_empty_signed_policy_chain_denied(self):
        self.denied(records=[])

    def test_57_fake_signed_event_string_denied(self):
        self.denied(records=["I approve production"])

    def test_58_negative_issuer_root_can_sign_old_keys_if_anchor_also_stale(self):
        # Valid root signature is not proof of independent administration.
        self.quarantine()
        self.assertFalse(self.decision().actual_independent_issuer_custody_verified)

    def test_59_rotation_of_only_one_custodian_reusing_other_key_denied(self):
        self.rotate(d1=Ed25519PrivateKey.generate(),d2=self.d2)
        self.denied("reused_or_shared_custodian_key")

    def test_60_approved_issuer_is_not_a_real_human_owner_attestation(self):
        self.quarantine()
        self.assertFalse(self.decision().owner_consent_verified)


_MUTATIONS=[
    ("ledger_empty",{"ledger_id":""}),
    ("ledger_bool",{"ledger_id":True}),
    ("ledger_spaces",{"ledger_id":"ledger A"}),
    ("epoch_upper",{"epoch":"F"*32}),
    ("epoch_short",{"epoch":"0"*16}),
    ("epoch_bool",{"epoch":True}),
    ("generation_bool",{"generation":True}),
    ("generation_zero",{"generation":0}),
    ("generation_negative",{"generation":-1}),
    ("generation_overflow",{"generation":2**70}),
    ("previous_digest_short",{"previous_digest":"f"*63}),
    ("previous_digest_upper",{"previous_digest":"F"*64}),
    ("d1_hex_short",{"d1_public_hex":"f"*63}),
    ("d2_hex_upper",{"d2_public_hex":"F"*64}),
    ("request_nonce_short",{"request_nonce":"f"*31}),
    ("request_nonce_upper",{"request_nonce":"F"*32}),
    ("request_nonce_bool",{"request_nonce":False}),
    ("issued_ns_bool",{"issued_ns":True}),
    ("issued_ns_zero",{"issued_ns":0}),
    ("issued_ns_overflow",{"issued_ns":2**70}),
]
assert len(_MUTATIONS)==20


def _make_mutation(fields):
    def check(self):
        record=self.records[0]
        event=replace(record.event,**fields)
        # Even with authentic original issuer/d1/d2 signatures on a
        # different payload, malformed declarations MUST fail closed.
        changed=replace(record,event=event)
        result=self.decision(records=[changed])
        self.invariant(result)
        self.assertEqual(result.verdict,"LAB_HARD_BLOCKED",result)
    return check


for n,(slug,fields) in enumerate(_MUTATIONS,start=61):
    setattr(A163CustodyEnrollmentRotationRevocationLAB,
            f"test_{n:02d}_invalid_{slug}",_make_mutation(fields))


if __name__=="__main__":
    unittest.main()
