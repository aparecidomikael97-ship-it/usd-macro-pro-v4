"""A165: 80 adversarial *synthetic* evidence intake tests against A164.

Only separate key bytes and self-declared IDs are exercised. The test
process controls EVERY issuer and administrator, proving a negative:
signed independent-looking metadata cannot establish REAL independent
custody. No network, secrets, remote accounts or external receipts.
"""
import base64
from dataclasses import replace
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import test_aion_p0_a164_independent_revocation_floor_lab as prior
from aion_p0_a165_external_custody_evidence_lab import (
    SCHEMA, DOMAIN, POSSESSION_DOMAIN, AUDIENCE,
    CustodyClaim, SignedCustodyClaim, CustodyEvidenceReview,
    CustodyEvidenceRejected, canonical_custody_claim_bytes,
    verify_synthetic_custody_claims, assess_custodian_evidence_and_h0,
)


def pub(key):
    return prior.public(key)


def sign(key,msg):
    return base64.b64encode(key.sign(msg)).decode("ascii")


class A165SyntheticCustodyEvidenceLAB(unittest.TestCase):
    def setUp(self):
        self.a=prior.A164SignedPolicyRevocationFloorLAB(
            methodName="test_01_genesis_valid_never_go"
        )
        self.a.setUp()
        self.addCleanup(self.a.doCleanups)
        self.issuers={
            "v1":Ed25519PrivateKey.generate(),
            "v2":Ed25519PrivateKey.generate(),
        }
        self.issuer_pins={k:pub(v) for k,v in self.issuers.items()}

    def claim(self,role,**changes):
        fl=self.a.floor()
        label="one" if role=="r1" else "two"
        base=CustodyClaim(
            role=role,ledger_id=fl.ledger_id,epoch=fl.epoch,
            policy_generation=fl.generation,policy_digest=fl.chain_digest,
            terminal_revoked=fl.terminal_revoked,challenge_nonce=fl.request_nonce,
            audience=AUDIENCE,auditor_public_hex=self.a.keys[role].hex(),
            organization_id="org_"+label,administrator_id="admin_"+label,
            provider_account_id="tenant_"+label,
            storage_failure_domain_id="zone_"+label,
            custody_request_id="ref_"+label,
            asserted_separate_administration=True,
            asserted_nonrollbackable_storage=True,
            observed_ns=fl.observed_ns,expires_ns=fl.valid_until_ns,
        )
        return replace(base,**changes)

    def seal(self,role,claim=None,issuer=None,auditor=None):
        claim=self.claim(role) if claim is None else claim
        payload=canonical_custody_claim_bytes(claim)
        authority=self.issuers["v1" if role=="r1" else "v2"] if issuer is None else issuer
        signer=(self.a.r1 if role=="r1" else self.a.r2) if auditor is None else auditor
        return SignedCustodyClaim(
            claim,sign(authority,payload),sign(signer,POSSESSION_DOMAIN+payload),
        )

    def pair(self,c1=None,c2=None):
        return self.seal("r1",c1),self.seal("r2",c2)

    def full(self,*,entry1=None,entry2=None,issuer_pins=None,auditor_pins=None,
             root_key=None,challenge=None,ledger=None,epoch=None,now=None,
             policy_events=None,anchor=None,revocation1=None,revocation2=None,
             journal=None,witness=None,checkpoint=None,checkpoint_pins=None,
             floor_d1=None,floor_d2=None,request_nonce=None):
        # All valid inputs produced BEFORE optional attacks to avoid
        # reporting fixture failures as real cryptographic denials.
        a,b=self.pair()
        r1,r2=self.a.signpair()
        local_d1,local_d2=self.a.fx.floors()
        return assess_custodian_evidence_and_h0(
            signed_r1=a if entry1 is None else entry1,
            signed_r2=b if entry2 is None else entry2,
            pinned_review_issuer_keys=self.issuer_pins if issuer_pins is None else issuer_pins,
            signed_floor_r1=r1 if revocation1 is None else revocation1,
            signed_floor_r2=r2 if revocation2 is None else revocation2,
            pinned_auditor_keys=self.a.keys if auditor_pins is None else auditor_pins,
            trusted_issuer_public_key=pub(self.a.fx.issuer) if root_key is None else root_key,
            challenge_nonce=self.a.nonce if challenge is None else challenge,
            ledger_id=self.a.fx.ledger if ledger is None else ledger,
            epoch=self.a.fx.epoch if epoch is None else epoch,
            now_ns=self.a.now if now is None else now,
            signed_events=self.a.fx.records if policy_events is None else policy_events,
            local_anchor=self.a.fx.anchor() if anchor is None else anchor,
            journal=self.a.fx.journal if journal is None else journal,
            local_witness=self.a.fx.witness if witness is None else witness,
            checkpoint=self.a.fx.checkpoint() if checkpoint is None else checkpoint,
            checkpoint_pins=({"checkpoint":pub(self.a.fx.cp_signer)}
                              if checkpoint_pins is None else checkpoint_pins),
            floor_d1=local_d1 if floor_d1 is None else floor_d1,
            floor_d2=local_d2 if floor_d2 is None else floor_d2,
            request_nonce=self.a.fx.nonce if request_nonce is None else request_nonce,
        )

    def invariant(self,r):
        self.assertIs(type(r),CustodyEvidenceReview)
        self.assertEqual(r.schema,SCHEMA)
        self.assertIn(r.verdict,("LAB_HARD_BLOCKED","LAB_QUARANTINE_MANUAL_REVIEW"))
        for x in (
            "actual_independent_operator_identity_verified",
            "actual_independent_administrator_control_verified",
            "actual_nonrollbackable_storage_verified",
            "real_issuer_provenance_verified",
            "real_owner_identity_and_approval_verified",
            "actual_provider_effect_or_no_effect_verified",
            "checkpoint_restore_allowed",
            "external_execution_allowed","worker_allowed",
            "automatic_retry_allowed","automatic_resend_allowed",
        ):
            self.assertIs(getattr(r,x),False,x)
        self.assertEqual(r.homologated_p0_count,0)

    def denied(self,expect=None,**k):
        r=self.full(**k)
        self.invariant(r)
        self.assertEqual(r.verdict,"LAB_HARD_BLOCKED",r)
        if expect:
            self.assertIn(expect,r.reason)
        return r

    def quarantine(self,**k):
        r=self.full(**k)
        self.invariant(r)
        self.assertEqual(r.verdict,"LAB_QUARANTINE_MANUAL_REVIEW",r)
        self.assertTrue(r.synthetic_two_issuer_signatures_checked)
        self.assertTrue(r.synthetic_two_auditor_pop_signatures_checked)
        self.assertTrue(r.claims_syntactically_disjoint)
        self.assertTrue(r.a164_mathematical_floor_checked)
        return r

    def test_01_full_synthetic_claims_are_only_quarantine(self):
        self.quarantine()

    def test_02_four_distinct_synthetic_signer_keys(self):
        keys=list(self.issuer_pins.values())+list(self.a.keys.values())
        self.assertEqual(len(keys),len(set(keys)))
        self.quarantine()

    def test_03_issuer_roots_are_distinct_from_policy_issuer(self):
        self.assertNotIn(pub(self.a.fx.issuer),self.issuer_pins.values())
        self.quarantine()

    def test_04_signed_metadata_domain_separated(self):
        b=canonical_custody_claim_bytes(self.claim("r1"))
        self.assertTrue(b.startswith(DOMAIN))
        self.assertNotEqual(DOMAIN,POSSESSION_DOMAIN)

    def test_05_live_synthetic_signature_verification_valid(self):
        a,b=self.pair()
        proof=verify_synthetic_custody_claims(
            signed_r1=a,signed_r2=b,
            pinned_review_issuer_keys=self.issuer_pins,
            pinned_auditor_keys=self.a.keys,
            trusted_issuer_public_key=pub(self.a.fx.issuer),
            expected_floor=self.a.floor(),expected_ledger=self.a.fx.ledger,
            expected_epoch=self.a.fx.epoch,
            expected_challenge_nonce=self.a.nonce,now_ns=self.a.now,
        )
        self.assertEqual(len(proof),2)
        self.assertNotEqual(proof[0].organization_id,proof[1].organization_id)

    def test_06_one_valid_policy_rotation_still_not_authority(self):
        self.a.fx.rotate()
        self.quarantine()

    def test_07_two_valid_rotations_still_not_authority(self):
        self.a.fx.rotate()
        self.a.fx.rotate()
        self.quarantine()

    def test_08_terminal_revocation_still_hard_blocks(self):
        self.a.fx.revoke()
        self.denied("terminal_revocation_signed_by_two_auditors")

    def test_09_revocation_after_rotation_still_hard_blocks(self):
        self.a.fx.rotate()
        self.a.fx.revoke()
        self.denied("terminal_revocation_signed_by_two_auditors")

    def test_10_newer_external_floor_detects_both_policy_and_anchor_restored(self):
        stale_events=list(self.a.fx.records)
        stale_anchor=self.a.fx.anchor()
        self.a.fx.rotate()
        self.denied("local_policy_and_anchor_rolled_back_below_signed_floor",
                    policy_events=stale_events,anchor=stale_anchor)

    def test_11_newer_revocation_detects_old_policy_and_anchor(self):
        stale_events=list(self.a.fx.records)
        stale_anchor=self.a.fx.anchor()
        self.a.fx.revoke()
        self.denied("local_policy_and_anchor_rolled_back_below_signed_floor",
                    policy_events=stale_events,anchor=stale_anchor)

    def test_12_signed_wrong_r1_role(self):
        a,_=self.pair()
        self.denied(entry1=replace(a,claim=replace(a.claim,role="r2")))

    def test_13_signed_wrong_r2_role(self):
        _,b=self.pair()
        self.denied(entry2=replace(b,claim=replace(b.claim,role="r1")))

    def test_14_missing_r1_claim_denied(self):
        self.denied(entry1="not-signed")

    def test_15_missing_r2_claim_denied(self):
        self.denied(entry2="not-signed")

    def test_16_missing_v1_review_signature_denied(self):
        a,_=self.pair()
        self.denied("signature_missing",entry1=replace(a,review_issuer_signature_b64=""))

    def test_17_missing_v2_review_signature_denied(self):
        _,b=self.pair()
        self.denied("signature_missing",entry2=replace(b,review_issuer_signature_b64=""))

    def test_18_missing_r1_pop_denied(self):
        a,_=self.pair()
        self.denied("signature_missing",entry1=replace(a,auditor_possession_signature_b64=""))

    def test_19_missing_r2_pop_denied(self):
        _,b=self.pair()
        self.denied("signature_missing",entry2=replace(b,auditor_possession_signature_b64=""))

    def test_20_wrong_v1_root_key_denied(self):
        self.denied(issuer_pins={**self.issuer_pins,
                                 "v1":pub(Ed25519PrivateKey.generate())})

    def test_21_wrong_v2_root_key_denied(self):
        self.denied(issuer_pins={**self.issuer_pins,
                                 "v2":pub(Ed25519PrivateKey.generate())})

    def test_22_missing_v2_root_pin_denied(self):
        self.denied(issuer_pins={"v1":self.issuer_pins["v1"]})

    def test_23_extra_v3_root_pin_denied(self):
        self.denied(issuer_pins={**self.issuer_pins,
                                 "v3":pub(Ed25519PrivateKey.generate())})

    def test_24_shared_v1_v2_root_key_denied(self):
        self.denied("cross_role_key_reuse",
                    issuer_pins={"v1":self.issuer_pins["v1"],
                                 "v2":self.issuer_pins["v1"]})

    def test_25_review_root_reused_as_r1_key_denied(self):
        self.denied("cross_role_key_reuse",
                    issuer_pins={**self.issuer_pins,"v1":self.a.keys["r1"]})

    def test_26_review_root_reused_as_a163_policy_root_denied(self):
        self.denied("cross_role_key_reuse",
                    issuer_pins={**self.issuer_pins,"v2":pub(self.a.fx.issuer)})

    def test_27_r1_auditor_public_pin_substituted_denied(self):
        self.denied(auditor_pins={**self.a.keys,
                                  "r1":pub(Ed25519PrivateKey.generate())})

    def test_28_r2_auditor_public_pin_substituted_denied(self):
        self.denied(auditor_pins={**self.a.keys,
                                  "r2":pub(Ed25519PrivateKey.generate())})

    def test_29_both_auditor_keys_reused_denied(self):
        self.denied(auditor_pins={"r1":self.a.keys["r1"],
                                  "r2":self.a.keys["r1"]})

    def test_30_claim_has_wrong_auditor_public_key_denied(self):
        claim=self.claim("r1",auditor_public_hex=pub(Ed25519PrivateKey.generate()).hex())
        self.denied("auditor_public_pin_mismatch",
                    entry1=self.seal("r1",claim))

    def test_31_claim_generation_ahead_denied(self):
        claim=self.claim("r1",policy_generation=2)
        self.denied("custody_claim_not_bound_to_floor",entry1=self.seal("r1",claim))

    def test_32_claim_digest_wrong_denied(self):
        claim=self.claim("r1",policy_digest="f"*64)
        self.denied("custody_claim_not_bound_to_floor",entry1=self.seal("r1",claim))

    def test_33_claim_revoked_flag_wrong_denied(self):
        claim=self.claim("r1",terminal_revoked=True)
        self.denied("custody_claim_not_bound_to_floor",entry1=self.seal("r1",claim))

    def test_34_claim_ledger_wrong_denied(self):
        claim=self.claim("r1",ledger_id="different")
        self.denied("custody_claim_not_bound_to_floor",entry1=self.seal("r1",claim))

    def test_35_claim_epoch_wrong_denied(self):
        claim=self.claim("r1",epoch="f"*32)
        self.denied("custody_claim_not_bound_to_floor",entry1=self.seal("r1",claim))

    def test_36_claim_nonce_wrong_denied(self):
        claim=self.claim("r1",challenge_nonce="f"*32)
        self.denied("custody_claim_not_bound_to_floor",entry1=self.seal("r1",claim))

    def test_37_expected_fresh_nonce_wrong_denied(self):
        self.denied(challenge="f"*32)

    def test_38_claim_observed_before_floor_denied(self):
        claim=self.claim("r1",observed_ns=self.a.floor().observed_ns-1)
        self.denied("custody_claim_stale_or_outside_floor_window",
                    entry1=self.seal("r1",claim))

    def test_39_claim_expiry_beyond_floor_denied(self):
        claim=self.claim("r1",expires_ns=self.a.floor().valid_until_ns+1)
        self.denied("custody_claim_stale_or_outside_floor_window",
                    entry1=self.seal("r1",claim))

    def test_40_review_at_exact_expiry_denied(self):
        self.denied(now=self.a.floor().valid_until_ns)

    def test_41_review_from_before_observation_denied(self):
        self.denied(now=self.a.floor().observed_ns-1)

    def test_42_reviewer_signature_from_wrong_key_denied(self):
        a,_=self.pair()
        signed=replace(a,review_issuer_signature_b64=sign(
            Ed25519PrivateKey.generate(),canonical_custody_claim_bytes(a.claim)))
        self.denied(entry1=signed)

    def test_43_possession_signature_from_wrong_key_denied(self):
        a,_=self.pair()
        signed=replace(a,auditor_possession_signature_b64=sign(
            Ed25519PrivateKey.generate(),
            POSSESSION_DOMAIN+canonical_custody_claim_bytes(a.claim)))
        self.denied(entry1=signed)

    def test_44_review_signature_from_other_domain_denied(self):
        a,_=self.pair()
        forged=replace(a,review_issuer_signature_b64=sign(
            self.issuers["v1"],b"ANOTHER-DOMAIN"+canonical_custody_claim_bytes(a.claim)))
        self.denied(entry1=forged)

    def test_45_pop_signature_from_other_domain_denied(self):
        a,_=self.pair()
        forged=replace(a,auditor_possession_signature_b64=sign(
            self.a.r1,canonical_custody_claim_bytes(a.claim)))
        self.denied(entry1=forged)

    def test_46_identical_org_claims_denied_even_if_both_signed(self):
        a=self.claim("r1")
        b=self.claim("r2",organization_id=a.organization_id)
        self.denied("shared_claimed_failure_domain:organization_id",
                    entry2=self.seal("r2",b))

    def test_47_identical_admin_claims_denied_even_if_both_signed(self):
        self.denied("shared_claimed_failure_domain:administrator_id",
                    entry2=self.seal("r2",self.claim(
                        "r2",administrator_id=self.claim("r1").administrator_id)))

    def test_48_identical_provider_account_claims_denied(self):
        self.denied("shared_claimed_failure_domain:provider_account_id",
                    entry2=self.seal("r2",self.claim(
                        "r2",provider_account_id=self.claim("r1").provider_account_id)))

    def test_49_identical_storage_failure_domain_denied(self):
        self.denied("shared_claimed_failure_domain:storage_failure_domain_id",
                    entry2=self.seal("r2",self.claim(
                        "r2",storage_failure_domain_id=self.claim("r1").storage_failure_domain_id)))

    def test_50_identical_custody_reference_denied(self):
        self.denied("shared_claimed_failure_domain:custody_request_id",
                    entry2=self.seal("r2",self.claim(
                        "r2",custody_request_id=self.claim("r1").custody_request_id)))

    def test_51_forged_distinct_org_names_still_not_independent(self):
        r=self.quarantine()
        self.assertFalse(r.actual_independent_operator_identity_verified)

    def test_52_forged_distinct_account_names_still_not_external_custody(self):
        r=self.quarantine()
        self.assertFalse(r.actual_nonrollbackable_storage_verified)

    def test_53_custody_claim_self_reports_no_immutability_denied(self):
        valid,_=self.pair()
        bad=replace(valid,claim=replace(
            valid.claim,asserted_nonrollbackable_storage=False))
        self.denied("nonrollbackable_storage_not_claimed",entry1=bad)

    def test_54_custody_claim_self_reports_no_independence_denied(self):
        valid,_=self.pair()
        bad=replace(valid,claim=replace(
            valid.claim,asserted_separate_administration=False))
        self.denied("separate_administration_not_claimed",entry1=bad)

    def test_55_both_colluding_issuers_can_sign_false_disjoint_claims(self):
        # NEGATIVE PROOF: every key and identity is manufactured by this
        # very process. Even valid V1/V2/R1/R2 cannot prove independent
        # ownership, immutable storage, provider action or owner consent.
        r=self.quarantine()
        self.assertFalse(r.real_issuer_provenance_verified)
        self.assertFalse(r.actual_independent_administrator_control_verified)

    def test_56_latest_floor_missing_r1_signature_denied(self):
        a,_=self.a.signpair()
        self.denied(revocation1=replace(a,signature_b64=""))

    def test_57_latest_floor_wrong_r2_signer_denied(self):
        _,b=self.a.signpair(r2=self.a.r1)
        self.denied(revocation2=b)

    def test_58_local_policy_revoked_and_4_signed_claims_still_block(self):
        self.a.fx.revoke()
        r=self.denied("terminal_revocation_signed_by_two_auditors")
        self.assertTrue(r.synthetic_two_issuer_signatures_checked)

    def test_59_one_custodian_claim_valid_other_missing_denied(self):
        self.denied(entry2=False)

    def test_60_no_auto_retry_when_crypto_all_matches(self):
        r=self.quarantine()
        self.assertFalse(r.automatic_retry_allowed)


_BAD_FIELDS=[
    ("role_unknown",{"role":"r3"}),
    ("ledger_empty",{"ledger_id":""}),
    ("ledger_space",{"ledger_id":"ledger A"}),
    ("epoch_short",{"epoch":"f"*31}),
    ("epoch_upper",{"epoch":"F"*32}),
    ("generation_bool",{"policy_generation":True}),
    ("generation_zero",{"policy_generation":0}),
    ("digest_upper",{"policy_digest":"F"*64}),
    ("revoked_not_boolean",{"terminal_revoked":"false"}),
    ("nonce_short",{"challenge_nonce":"a"*31}),
    ("audience_wrong",{"audience":"AION-H0-SEND"}),
    ("key_upper",{"auditor_public_hex":"F"*64}),
    ("org_empty",{"organization_id":""}),
    ("admin_spaces",{"administrator_id":"admin one"}),
    ("account_bool",{"provider_account_id":False}),
    ("domain_empty",{"storage_failure_domain_id":""}),
    ("request_space",{"custody_request_id":"ref one"}),
    ("claimed_immutable_int",{"asserted_nonrollbackable_storage":1}),
    ("observed_bool",{"observed_ns":True}),
    ("expiry_overflow",{"expires_ns":2**70}),
]
assert len(_BAD_FIELDS)==20


def _bad_case(fields):
    def check(self):
        # Construct an INVALID claim but keep the original signature.
        # The A165 verifier must deny before any possible grant.
        valid,_=self.pair()
        changed=replace(valid,claim=replace(valid.claim,**fields))
        self.denied(entry1=changed)
    return check


for i,(name,fields) in enumerate(_BAD_FIELDS,start=61):
    setattr(A165SyntheticCustodyEvidenceLAB,
            f"test_{i:02d}_malformed_{name}",_bad_case(fields))


if __name__=="__main__":
    unittest.main()
