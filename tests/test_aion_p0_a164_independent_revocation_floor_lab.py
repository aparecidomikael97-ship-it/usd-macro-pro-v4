"""A164: 80 cryptographic version-floor adversaries, no real custody.

Uses the prior A163 synthetic fixture via a MODULE import rather than
re-exporting its unittest class; independent CI runners count only A164 tests.
All signatures, nonce, time, DB/keys generated in one ephemeral test host.
"""
import base64
from dataclasses import replace
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import test_aion_p0_a163_custody_enrollment_revocation_lab as old_fixture
from aion_p0_a164_independent_revocation_floor_lab import (
    AUDIENCE, DOMAIN, MAX_WINDOW_NS, SCHEMA,
    RevocationFloor, SignedRevocationFloor, RevocationFloorReview,
    RevocationFloorRejected, canonical_revocation_floor_bytes,
    verify_signed_revocation_floor, assess_external_revocation_floor,
)


def public(k):
    return old_fixture.pub(k)


def sign(k,blob):
    return base64.b64encode(k.sign(blob)).decode("ascii")


class A164SignedPolicyRevocationFloorLAB(unittest.TestCase):
    def setUp(self):
        self.fx=old_fixture.A163CustodyEnrollmentRotationRevocationLAB(
            methodName="test_01_genesis_current_floors_only_quarantine"
        )
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.r1=Ed25519PrivateKey.generate()
        self.r2=Ed25519PrivateKey.generate()
        self.keys={"r1":public(self.r1),"r2":public(self.r2)}
        self.nonce="d"*32
        self.now=self.fx.now

    def floor(self,anchor=None,revoked=None):
        anchor=self.fx.anchor() if anchor is None else anchor
        revoked=(self.fx.verify().terminal_revoked if revoked is None else revoked)
        return RevocationFloor(
            ledger_id=anchor.ledger_id,epoch=anchor.epoch,
            generation=anchor.generation,chain_digest=anchor.chain_digest,
            terminal_revoked=revoked,request_nonce=self.nonce,
            audience=AUDIENCE,observed_ns=self.now-1_000_000_000,
            valid_until_ns=self.now+5_000_000_000,
        )

    def signpair(self,floor=None,*,r1=None,r2=None):
        floor=self.floor() if floor is None else floor
        key1=self.r1 if r1 is None else r1
        key2=self.r2 if r2 is None else r2
        return (
            SignedRevocationFloor(floor,"r1",sign(key1,canonical_revocation_floor_bytes(floor))),
            SignedRevocationFloor(floor,"r2",sign(key2,canonical_revocation_floor_bytes(floor))),
        )

    def review(self,*,anchor=None,events=None,sign1=None,sign2=None,keys=None,
               challenge=None,now=None,issuer=None,ledger=None,epoch=None,
               d1=None,d2=None,cp=None,cp_pins=None,
               journal=None,witness=None,request_nonce=None):
        # Build valid fixture evidence BEFORE a corrupt requested state,
        # so fail-closed evaluation is not accidentally fixture failure.
        claim1,claim2=self.signpair()
        local1,local2=self.fx.floors()
        return assess_external_revocation_floor(
            signed_events=self.fx.records if events is None else events,
            trusted_issuer_public_key=public(self.fx.issuer) if issuer is None else issuer,
            local_anchor=self.fx.anchor() if anchor is None else anchor,
            signed_r1=claim1 if sign1 is None else sign1,
            signed_r2=claim2 if sign2 is None else sign2,
            pinned_auditor_keys=self.keys if keys is None else keys,
            challenge_nonce=self.nonce if challenge is None else challenge,
            ledger_id=self.fx.ledger if ledger is None else ledger,
            epoch=self.fx.epoch if epoch is None else epoch,
            now_ns=self.now if now is None else now,
            journal=self.fx.journal if journal is None else journal,
            local_witness=self.fx.witness if witness is None else witness,
            checkpoint=self.fx.checkpoint() if cp is None else cp,
            checkpoint_pins={"checkpoint":public(self.fx.cp_signer)} if cp_pins is None else cp_pins,
            floor_d1=local1 if d1 is None else d1,
            floor_d2=local2 if d2 is None else d2,
            request_nonce=self.fx.nonce if request_nonce is None else request_nonce,
        )

    def assert_no_effect(self,result):
        self.assertIs(type(result),RevocationFloorReview)
        self.assertEqual(result.schema,SCHEMA)
        self.assertIn(result.verdict,("LAB_HARD_BLOCKED","LAB_QUARANTINE_MANUAL_REVIEW"))
        for flag in (
            "latest_external_generation_verified",
            "actual_independent_auditor_administration_verified",
            "actual_nonrollbackable_revocation_floor_verified",
            "actual_owner_identity_and_consent_verified",
            "actual_provider_effect_or_no_effect_verified",
            "checkpoint_restore_allowed",
            "external_execution_allowed",
            "worker_allowed",
            "automatic_retry_allowed",
            "automatic_resend_allowed",
        ):
            self.assertIs(getattr(result,flag),False,flag)
        self.assertEqual(result.homologated_p0_count,0)

    def deny(self,reason=None,**opts):
        result=self.review(**opts)
        self.assert_no_effect(result)
        self.assertEqual(result.verdict,"LAB_HARD_BLOCKED",result)
        if reason:
            self.assertIn(reason,result.reason)
        return result

    def quarantine(self,**opts):
        result=self.review(**opts)
        self.assert_no_effect(result)
        self.assertEqual(result.verdict,"LAB_QUARANTINE_MANUAL_REVIEW",result)
        self.assertTrue(result.two_synthetic_auditor_signatures_verified)
        self.assertTrue(result.local_policy_chain_verified)
        return result

    def test_01_genesis_valid_never_go(self):
        self.quarantine()

    def test_02_two_pre_pinned_key_materials_distinct(self):
        self.assertNotEqual(self.keys["r1"],self.keys["r2"])
        self.quarantine()

    def test_03_domain_separator_is_not_a161_nor_a163(self):
        self.assertTrue(canonical_revocation_floor_bytes(self.floor()).startswith(DOMAIN))
        self.assertIn(b"terminal_revoked",canonical_revocation_floor_bytes(self.floor()))

    def test_04_one_rotation_updates_head_and_matches_two_auditors(self):
        self.fx.rotate()
        self.quarantine()

    def test_05_two_rotations_validate_latest_only(self):
        self.fx.rotate()
        self.fx.rotate()
        self.quarantine()

    def test_06_three_rotations_no_go(self):
        for _ in range(3):self.fx.rotate()
        self.quarantine()

    def test_07_external_newer_floor_detects_restored_both_local_policy_and_anchor(self):
        old_events=list(self.fx.records)
        old_anchor=self.fx.anchor()
        self.fx.rotate()
        result=self.deny("local_policy_and_anchor_rolled_back_below_signed_floor",
                         events=old_events,anchor=old_anchor)
        self.assertTrue(result.two_synthetic_auditor_signatures_verified)

    def test_08_external_revocation_floor_detects_restored_pre_revoke_anchor(self):
        old_events=list(self.fx.records)
        old_anchor=self.fx.anchor()
        self.fx.revoke()
        self.deny("local_policy_and_anchor_rolled_back_below_signed_floor",
                  events=old_events,anchor=old_anchor)

    def test_09_after_rotate_and_revoke_stale_policy_and_anchor_block(self):
        self.fx.rotate()
        old=list(self.fx.records)
        old_anchor=self.fx.anchor()
        self.fx.revoke()
        self.deny("local_policy_and_anchor_rolled_back_below_signed_floor",
                  events=old,anchor=old_anchor)

    def test_10_latest_revocation_blocks_even_under_valid_remote_signatures(self):
        self.fx.revoke()
        self.deny("terminal_revocation_signed_by_two_auditors")

    def test_11_revocation_after_rotation_blocks(self):
        self.fx.rotate()
        self.fx.revoke()
        self.deny("terminal_revocation_signed_by_two_auditors")

    def test_12_emergency_stop_when_only_issuer_revoked_keys(self):
        self.fx.revoke()
        self.assertTrue(self.deny().two_synthetic_auditor_signatures_verified)

    def test_13_remote_auditors_newer_rotation_floor_local_old_anchors_deny(self):
        old=list(self.fx.records)
        old_anchor=self.fx.anchor()
        self.fx.rotate()
        self.fx.rotate()
        self.deny("local_policy_and_anchor_rolled_back_below_signed_floor",
                  events=old,anchor=old_anchor)

    def test_14_remote_floor_behind_local_rotation_blocks(self):
        old_floor=self.floor()
        a,b=self.signpair(old_floor)
        self.fx.rotate()
        self.deny("unwitnessed_policy_generation_ahead_of_signed_floor",
                  sign1=a,sign2=b)

    def test_15_remote_floor_behind_local_revocation_blocks(self):
        older=self.floor()
        a,b=self.signpair(older)
        self.fx.revoke()
        self.deny("unwitnessed_policy_generation_ahead_of_signed_floor",
                  sign1=a,sign2=b)

    def test_16_same_generation_different_signed_digest_denied(self):
        wrong=replace(self.floor(),chain_digest="a"*64)
        a,b=self.signpair(wrong)
        self.deny("equal_generation_chain_digest_fork",sign1=a,sign2=b)

    def test_17_same_generation_revocation_flag_disagreement_denied(self):
        wrong=replace(self.floor(),terminal_revoked=True)
        a,b=self.signpair(wrong)
        self.deny("signed_revocation_state_disagreement",sign1=a,sign2=b)

    def test_18_same_generation_signed_active_flag_after_revoke_denied(self):
        self.fx.revoke()
        wrong=replace(self.floor(),terminal_revoked=False)
        a,b=self.signpair(wrong)
        self.deny("signed_revocation_state_disagreement",sign1=a,sign2=b)

    def test_19_two_auditors_disagree_different_generation_denied(self):
        a,b=self.signpair()
        future=replace(self.floor(),generation=2)
        _,b2=self.signpair(future)
        self.deny("two_auditors_disagree_on_policy_floor",sign1=a,sign2=b2)

    def test_20_two_auditors_disagree_revoked_flag_denied(self):
        a,_=self.signpair()
        _,b=self.signpair(replace(self.floor(),terminal_revoked=True))
        self.deny("two_auditors_disagree_on_policy_floor",sign1=a,sign2=b)

    def test_21_two_auditors_disagree_same_counter_digest_denied(self):
        a,_=self.signpair()
        _,b=self.signpair(replace(self.floor(),chain_digest="f"*64))
        self.deny("two_auditors_disagree_on_policy_floor",sign1=a,sign2=b)

    def test_22_wrong_challenge_nonce_denied(self):
        self.deny("replayed_or_wrong_challenge_nonce",challenge="c"*32)

    def test_23_signed_wrong_nonce_same_local_claim_denied(self):
        claim=replace(self.floor(),request_nonce="c"*32)
        a,b=self.signpair(claim)
        self.deny("replayed_or_wrong_challenge_nonce",sign1=a,sign2=b)

    def test_24_signed_wrong_ledger_denied(self):
        claim=replace(self.floor(),ledger_id="other")
        a,b=self.signpair(claim)
        self.deny("signed_floor_ledger_epoch_mismatch",sign1=a,sign2=b)

    def test_25_signed_wrong_epoch_denied(self):
        claim=replace(self.floor(),epoch="f"*32)
        a,b=self.signpair(claim)
        self.deny("signed_floor_ledger_epoch_mismatch",sign1=a,sign2=b)

    def test_26_expected_wrong_epoch_denied(self):
        self.deny(epoch="f"*32)

    def test_27_expected_wrong_ledger_denied(self):
        self.deny(ledger="ledger-X")

    def test_28_wrong_r1_key_pin_denied(self):
        wrong=Ed25519PrivateKey.generate()
        self.deny(keys={**self.keys,"r1":public(wrong)})

    def test_29_wrong_r2_key_pin_denied(self):
        wrong=Ed25519PrivateKey.generate()
        self.deny(keys={**self.keys,"r2":public(wrong)})

    def test_30_missing_r2_key_pin_denied(self):
        self.deny(keys={"r1":self.keys["r1"]})

    def test_31_extra_r3_key_pin_denied(self):
        self.deny(keys={**self.keys,"r3":public(Ed25519PrivateKey.generate())})

    def test_32_auditor_roles_reused_same_key_denied(self):
        self.deny(keys={"r1":self.keys["r1"],"r2":self.keys["r1"]})

    def test_33_auditor_r1_reuses_policy_issuer_key_denied(self):
        self.deny("auditor_key_reuses_policy_signer",
                  keys={**self.keys,"r1":public(self.fx.issuer)})

    def test_34_auditor_r2_reuses_current_d2_key_denied(self):
        self.deny("auditor_key_reuses_policy_signer",
                  keys={**self.keys,"r2":public(self.fx.d2)})

    def test_35_auditor_r1_reuses_retired_d1_key_denied(self):
        old,_=self.fx.rotate()
        self.deny("auditor_key_was_retired_policy_key",
                  keys={**self.keys,"r1":public(old)})

    def test_36_auditor_r2_reuses_retired_d2_key_denied(self):
        _,old=self.fx.rotate()
        self.deny("auditor_key_was_retired_policy_key",
                  keys={**self.keys,"r2":public(old)})

    def test_37_swapped_signed_r1_role_denied(self):
        a,_=self.signpair()
        self.deny("auditor_role_mismatch",sign1=replace(a,role="r2"))

    def test_38_swapped_signed_r2_role_denied(self):
        _,b=self.signpair()
        self.deny("auditor_role_mismatch",sign2=replace(b,role="r1"))

    def test_39_r1_signed_by_r2_private_key_denied(self):
        a,b=self.signpair(r1=self.r2)
        self.deny(sign1=a,sign2=b)

    def test_40_r2_signed_by_r1_private_key_denied(self):
        a,b=self.signpair(r2=self.r1)
        self.deny(sign1=a,sign2=b)

    def test_41_missing_r1_envelope_denied(self):
        self.deny(sign1="no-envelope")

    def test_42_missing_r2_envelope_denied(self):
        self.deny(sign2="no-envelope")

    def test_43_empty_r1_signature_denied(self):
        a,_=self.signpair()
        self.deny("required_auditor_signature_missing",sign1=replace(a,signature_b64=""))

    def test_44_invalid_base64_r2_signature_denied(self):
        _,b=self.signpair()
        self.deny("auditor_signature_bad_base64",sign2=replace(b,signature_b64="???"))

    def test_45_wrong_domain_signature_denied(self):
        a,_=self.signpair()
        wrong=sign(self.r1,b"OTHER-DOMAIN"+canonical_revocation_floor_bytes(a.floor))
        self.deny("auditor_signature_invalid",sign1=replace(a,signature_b64=wrong))

    def test_46_signature_under_other_floor_payload_denied(self):
        a,b=self.signpair()
        altered=replace(a.floor,terminal_revoked=True)
        self.deny("auditor_signature_invalid",sign1=replace(a,floor=altered),sign2=b)

    def test_47_exact_valid_until_is_expired_denied(self):
        self.deny("signed_floor_expired",now=self.floor().valid_until_ns)

    def test_48_one_nanosecond_before_expiry_quarantined(self):
        self.quarantine(now=self.floor().valid_until_ns-1)

    def test_49_time_before_observation_denied(self):
        self.deny("signed_floor_observation_in_future",now=self.floor().observed_ns-1)

    def test_50_expired_generation_cannot_reauthorize_revocation(self):
        self.fx.revoke()
        self.deny("signed_floor_expired",now=self.floor().valid_until_ns+1)

    def test_51_altered_local_policy_signature_still_denied(self):
        record=self.fx.records[0]
        bad=replace(record,issuer_signature_b64=sign(
            Ed25519PrivateKey.generate(),b"wrong"))
        self.deny(events=[bad])

    def test_52_old_local_anchor_only_vs_current_chain_denied(self):
        old=self.fx.anchor()
        self.fx.rotate()
        self.deny(anchor=old)

    def test_53_policy_events_old_anchor_new_without_matching_signed_chain_denied(self):
        old=list(self.fx.records)
        self.fx.rotate()
        self.deny(events=old)

    def test_54_local_witness_missing_after_signed_policy_still_denied(self):
        a,b=self.signpair()
        self.fx.witness.db_path.unlink()
        result=self.review(sign1=a,sign2=b,cp="bad")
        self.assert_no_effect(result)
        self.assertEqual(result.verdict,"LAB_HARD_BLOCKED")

    def test_55_a162_hash_mismatch_cannot_be_cleared_by_policy_floor(self):
        # Present valid policy+auditors but corrupt D1 floor signature.
        local1,local2=self.fx.floors()
        self.deny("a163_issuer_or_h0_rejected",
                  d1=replace(local1,signature_b64="???"),d2=local2)

    def test_56_attestation_key_freshness_not_attested_by_local_origin(self):
        self.assertFalse(self.quarantine().actual_nonrollbackable_revocation_floor_verified)

    def test_57_compromised_both_auditors_can_sign_old_floor_with_new_nonce(self):
        # Explicit negative proof. Replaying old policy+anchor and getting
        # both LOCAL auditors to re-sign old floor still yields quarantine.
        old_anchor=self.fx.anchor()
        old_events=list(self.fx.records)
        old_floor=self.floor(old_anchor)
        self.fx.rotate()
        a,b=self.signpair(old_floor)
        self.quarantine(anchor=old_anchor,events=old_events,sign1=a,sign2=b)

    def test_58_compromised_both_auditors_can_hide_revocation(self):
        old_anchor=self.fx.anchor()
        old_events=list(self.fx.records)
        old_floor=self.floor(old_anchor)
        self.fx.revoke()
        a,b=self.signpair(old_floor)
        self.quarantine(anchor=old_anchor,events=old_events,sign1=a,sign2=b)

    def test_59_no_automatic_grants_even_if_r1_r2_valid(self):
        r=self.quarantine()
        self.assertFalse(r.worker_allowed)
        self.assertFalse(r.automatic_resend_allowed)

    def test_60_raw_verifier_requires_exact_pins(self):
        a,b=self.signpair()
        got=verify_signed_revocation_floor(
            signed_r1=a,signed_r2=b,pinned_auditor_keys=self.keys,
            challenge_nonce=self.nonce,expected_ledger=self.fx.ledger,
            expected_epoch=self.fx.epoch,now_ns=self.now,
        )
        self.assertEqual(got,self.floor())


_BAD_FLOORS=[
    ("ledger_empty",{"ledger_id":""}),
    ("ledger_bool",{"ledger_id":True}),
    ("ledger_space",{"ledger_id":"ledger A"}),
    ("epoch_short",{"epoch":"0"*31}),
    ("epoch_upper",{"epoch":"F"*32}),
    ("generation_bool",{"generation":True}),
    ("generation_zero",{"generation":0}),
    ("generation_overflow",{"generation":2**70}),
    ("digest_short",{"chain_digest":"f"*63}),
    ("digest_upper",{"chain_digest":"F"*64}),
    ("revoked_string",{"terminal_revoked":"False"}),
    ("revoked_int",{"terminal_revoked":0}),
    ("nonce_upper",{"request_nonce":"B"*32}),
    ("nonce_short",{"request_nonce":"a"*31}),
    ("audience_wrong",{"audience":"AION-H0-SEND"}),
    ("issued_zero",{"observed_ns":0}),
    ("issued_bool",{"observed_ns":False}),
    ("expiry_bool",{"valid_until_ns":True}),
    ("expiry_before",{"valid_until_ns":1}),
    ("expiry_over_max",{"valid_until_ns":2**70}),
]
assert len(_BAD_FLOORS)==20


def _case(fields):
    def check(self):
        a,b=self.signpair()
        mutant=replace(a.floor,**fields)
        # Keep original signatures: the verifier must reject the malformed
        # fields before or during signature evaluation, not silently coerce.
        r=self.deny(sign1=replace(a,floor=mutant),sign2=replace(b,floor=mutant))
        self.assertFalse(r.two_synthetic_auditor_signatures_verified)
    return check


for number,(name,values) in enumerate(_BAD_FLOORS,start=61):
    setattr(A164SignedPolicyRevocationFloorLAB,
            f"test_{number:02d}_malformed_{name}",_case(values))


if __name__=="__main__":
    unittest.main()
