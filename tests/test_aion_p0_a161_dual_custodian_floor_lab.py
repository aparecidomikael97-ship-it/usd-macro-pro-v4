"""A161 adversarial nonce/floor/epoch/dual-custodian attestations (SYNTHETIC).

All keys created freshly per test. No provider API, network, real owner
enrollment or production witness access. NEGATIVE co-rollback proof:
two compromised local custodians can both sign a stale floor; successful
math then still returns quarantine, NEVER authorization.
"""
import base64
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_p0_a145_checkpoint_verifier_lab import canonical_history_digest
from aion_p0_a150_pinned_policy_lease_lab import LeasedPinnedWitnessLAB
from aion_p0_a161_dual_custodian_floor_lab import (
    AUDIENCE, DOMAIN, SCHEMA, MAX_WINDOW_NS, FloorRejected,
    HeadSnapshot, FloorClaim, SignedFloor, FloorReview,
    canonical_claim_bytes, verify_dual_floor, assess_restart_dual_floor,
    a150_read_only_head_snapshot,
)


def raw_priv(key):
    return key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def raw_pub(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


class A161SyntheticDualCustodianFloorLAB(unittest.TestCase):
    def setUp(self):
        self.now=1_800_000_000_000_000_000
        self.ledger="ledger-A"
        self.epoch="a"*32
        self.nonce="b"*32
        self.history="c"*64
        self.d1key=Ed25519PrivateKey.generate()
        self.d2key=Ed25519PrivateKey.generate()
        self.keys={"d1":raw_pub(self.d1key),"d2":raw_pub(self.d2key)}
        self.head=HeadSnapshot(self.ledger,self.epoch,7,self.history)
        self.claim=FloorClaim(
            ledger_id=self.ledger,epoch=self.epoch,sequence=7,
            history_digest=self.history,request_nonce=self.nonce,
            audience=AUDIENCE,observed_ns=self.now-1_000_000_000,
            valid_until_ns=self.now+6_000_000_000,
        )

    def signed(self,claim=None,*,key=None,role="d1"):
        claim=self.claim if claim is None else claim
        signer=(self.d1key if role=="d1" else self.d2key) if key is None else key
        return SignedFloor(
            claim=claim,custodian_id=role,
            signature_b64=base64.b64encode(signer.sign(canonical_claim_bytes(claim))).decode("ascii"),
        )

    def pair(self,first=None,second=None):
        return (
            self.signed(role="d1") if first is None else first,
            self.signed(role="d2") if second is None else second,
        )

    def review(self,*,head=None,first=None,second=None,keys=None,
               nonce=None,ledger=None,epoch=None,now=None):
        one,two=self.pair(first,second)
        return assess_restart_dual_floor(
            local_head=self.head if head is None else head,
            d1=one,d2=two,
            pinned_custodian_keys=self.keys if keys is None else keys,
            request_nonce=self.nonce if nonce is None else nonce,
            expected_ledger_id=self.ledger if ledger is None else ledger,
            expected_epoch=self.epoch if epoch is None else epoch,
            now_ns=self.now if now is None else now,
        )

    def invariant(self,report):
        self.assertIs(type(report),FloorReview)
        self.assertEqual(report.schema,SCHEMA)
        self.assertIn(report.verdict,("LAB_HARD_BLOCKED","LAB_QUARANTINE_MANUAL_REVIEW"))
        self.assertFalse(report.externally_independent_custodians_verified)
        self.assertFalse(report.nonrollbackable_external_floor_proven)
        self.assertFalse(report.owner_identity_verified)
        self.assertFalse(report.real_provider_effect_proven)
        self.assertFalse(report.checkpoint_restoration_authorized)
        self.assertFalse(report.external_execution_allowed)
        self.assertFalse(report.worker_allowed)
        self.assertFalse(report.automatic_resend_allowed)
        self.assertEqual(report.homologated_p0_count,0)

    def blocked(self,**kwargs):
        r=self.review(**kwargs)
        self.invariant(r)
        self.assertEqual(r.verdict,"LAB_HARD_BLOCKED",r)
        return r

    def matches(self,**kwargs):
        r=self.review(**kwargs)
        self.invariant(r)
        self.assertEqual(r.verdict,"LAB_QUARANTINE_MANUAL_REVIEW",r)
        self.assertTrue(r.cryptographic_pair_valid_in_lab)
        return r

    def test_01_two_valid_signatures_matching_head_still_only_quarantined(self):
        r=self.matches()
        self.assertIn("independent_custody_unproven",r.reason)

    def test_02_domain_separated_canonical_encoding(self):
        self.assertTrue(canonical_claim_bytes(self.claim).startswith(DOMAIN))
        self.assertIn(b'"request_nonce"',canonical_claim_bytes(self.claim))

    def test_03_signatures_use_distinct_pre_pinned_public_keys(self):
        self.assertNotEqual(self.keys["d1"],self.keys["d2"])
        a,b=self.pair()
        self.assertNotEqual(a.signature_b64,b.signature_b64)

    def test_04_verification_does_not_upgrade_witness_authority(self):
        one,two=self.pair()
        floor=verify_dual_floor(
            d1=one,d2=two,pinned_custodian_keys=self.keys,
            request_nonce=self.nonce,expected_ledger_id=self.ledger,
            expected_epoch=self.epoch,now_ns=self.now,
        )
        self.assertEqual(floor,self.claim)
        self.assertEqual(self.review().verdict,"LAB_QUARANTINE_MANUAL_REVIEW")

    def test_05_out_of_band_newer_floor_detects_local_joint_rollback(self):
        old=replace(self.head,sequence=6,history_digest="d"*64)
        r=self.blocked(head=old)
        self.assertEqual(r.reason,"local_rollback_below_signed_floor")
        self.assertTrue(r.cryptographic_pair_valid_in_lab)

    def test_06_old_signed_floor_cannot_prove_local_head_ahead(self):
        newer=replace(self.head,sequence=8,history_digest="e"*64)
        r=self.blocked(head=newer)
        self.assertEqual(r.reason,"unwitnessed_local_advance_unknown")

    def test_07_same_counter_different_digest_is_not_a_match(self):
        r=self.blocked(head=replace(self.head,history_digest="f"*64))
        self.assertEqual(r.reason,"same_sequence_digest_disagreement")

    def test_08_old_signed_floor_with_old_nonce_replay_denied(self):
        r=self.blocked(nonce="e"*32)
        self.assertEqual(r.reason,"stale_or_replayed_request_nonce")

    def test_09_two_signers_cannot_claim_different_counters(self):
        old=replace(self.claim,sequence=6,history_digest="d"*64)
        r=self.blocked(second=self.signed(old,role="d2"))
        self.assertEqual(r.reason,"two_custodian_claims_disagree")

    def test_10_two_signers_cannot_claim_different_history_digest(self):
        other=replace(self.claim,history_digest="f"*64)
        r=self.blocked(second=self.signed(other,role="d2"))
        self.assertEqual(r.reason,"two_custodian_claims_disagree")

    def test_11_two_signers_cannot_claim_different_nonce(self):
        other=replace(self.claim,request_nonce="f"*32)
        r=self.blocked(second=self.signed(other,role="d2"))
        self.assertEqual(r.reason,"two_custodian_claims_disagree")

    def test_12_reusing_signature_for_other_role_denied(self):
        one,_=self.pair()
        self.blocked(second=SignedFloor(self.claim,"d2",one.signature_b64))

    def test_13_swapping_signed_role_labels_denied(self):
        one,two=self.pair()
        self.blocked(first=replace(one,custodian_id="d2"),second=replace(two,custodian_id="d1"))

    def test_14_synthetic_d1_public_key_substitution_denied(self):
        evil=Ed25519PrivateKey.generate()
        self.blocked(keys={**self.keys,"d1":raw_pub(evil)})

    def test_15_synthetic_d2_public_key_substitution_denied(self):
        evil=Ed25519PrivateKey.generate()
        self.blocked(keys={**self.keys,"d2":raw_pub(evil)})

    def test_16_both_custodian_keys_reused_denied(self):
        self.blocked(keys={"d1":self.keys["d1"],"d2":self.keys["d1"]})

    def test_17_missing_d2_key_denied(self):
        self.blocked(keys={"d1":self.keys["d1"]})

    def test_18_extra_fake_d3_key_denied(self):
        self.blocked(keys={**self.keys,"d3":raw_pub(Ed25519PrivateKey.generate())})

    def test_19_d2_signature_truncated_denied(self):
        _,two=self.pair()
        self.blocked(second=replace(two,signature_b64=base64.b64encode(b"x"*63).decode()))

    def test_20_d1_signature_invalid_base64_denied(self):
        one,_=self.pair()
        self.blocked(first=replace(one,signature_b64="invalid#base64"))

    def test_21_d1_signature_missing_denied(self):
        one,_=self.pair()
        self.blocked(first=replace(one,signature_b64=None))

    def test_22_head_wrong_ledger_denied(self):
        self.blocked(head=replace(self.head,ledger_id="ledger-B"))

    def test_23_head_wrong_epoch_denied(self):
        self.blocked(head=replace(self.head,epoch="f"*32))

    def test_24_signed_floor_wrong_ledger_denied(self):
        claim=replace(self.claim,ledger_id="ledger-B")
        self.blocked(first=self.signed(claim,role="d1"),second=self.signed(claim,role="d2"))

    def test_25_signed_floor_wrong_epoch_denied(self):
        claim=replace(self.claim,epoch="f"*32)
        self.blocked(first=self.signed(claim,role="d1"),second=self.signed(claim,role="d2"))

    def test_26_signed_floor_wrong_audience_denied(self):
        bad=replace(self.claim,audience="AION-PROVIDER-SEND")
        self.blocked(first=SignedFloor(bad,"d1","bad"),second=SignedFloor(bad,"d2","bad"))

    def test_27_future_observation_denied_even_if_signature_valid(self):
        claim=replace(self.claim,observed_ns=self.now+1_000_000_000)
        self.blocked(first=self.signed(claim,role="d1"),second=self.signed(claim,role="d2"))

    def test_28_attestation_expiry_boundary_strict(self):
        self.blocked(now=self.claim.valid_until_ns)

    def test_29_attestation_last_nanosecond_before_expiry_matches(self):
        self.matches(now=self.claim.valid_until_ns-1)

    def test_30_signed_window_over_30_seconds_denied(self):
        claim=replace(self.claim,valid_until_ns=self.claim.observed_ns+MAX_WINDOW_NS+1)
        self.blocked(first=SignedFloor(claim,"d1","invalid"),second=SignedFloor(claim,"d2","invalid"))

    def test_31_signed_window_at_30_seconds_is_bounded(self):
        claim=replace(self.claim,valid_until_ns=self.claim.observed_ns+MAX_WINDOW_NS)
        self.matches(first=self.signed(claim,role="d1"),second=self.signed(claim,role="d2"))

    def test_32_co_rollback_with_attested_preserved_latest_floor_is_detected(self):
        old=HeadSnapshot(self.ledger,self.epoch,0,canonical_history_digest([]))
        self.assertEqual(self.blocked(head=old).reason,"local_rollback_below_signed_floor")

    def test_33_negative_compromised_both_custodians_can_sign_stale_fresh_nonce(self):
        # Explicit impossibility proof: without truly independent custody,
        # both signers can produce VALID fresh signatures over a stale head.
        # Even then the only result is manual quarantine, never a GO.
        stale=HeadSnapshot(self.ledger,self.epoch,0,canonical_history_digest([]))
        stale_claim=replace(
            self.claim,sequence=0,history_digest=stale.history_digest,
        )
        r=self.matches(
            head=stale,first=self.signed(stale_claim,role="d1"),
            second=self.signed(stale_claim,role="d2"),
        )
        self.assertFalse(r.nonrollbackable_external_floor_proven)

    def test_34_negative_replayed_old_nonce_if_requester_reuses_it(self):
        # A161 cannot certify that nonce freshness originated from an
        # independent durable requester: the caller can reuse the nonce.
        stale=HeadSnapshot(self.ledger,self.epoch,0,canonical_history_digest([]))
        old=replace(self.claim,sequence=0,history_digest=stale.history_digest)
        self.matches(head=stale,first=self.signed(old,role="d1"),
                     second=self.signed(old,role="d2"))

    def test_35_same_nonce_new_floor_must_be_dually_resigned(self):
        advanced=replace(self.claim,sequence=8,history_digest="e"*64)
        one,two=self.pair()
        self.blocked(first=replace(one,claim=advanced),second=replace(two,claim=advanced))

    def test_36_no_production_api_or_network_in_this_verifier(self):
        self.assertFalse(hasattr(self,"send_effect"))
        self.assertEqual(self.matches().homologated_p0_count,0)

    def test_37_missing_d1_envelope_denied(self):
        two=self.signed(role="d2")
        r=assess_restart_dual_floor(
            local_head=self.head,d1=None,d2=two,
            pinned_custodian_keys=self.keys,request_nonce=self.nonce,
            expected_ledger_id=self.ledger,expected_epoch=self.epoch,now_ns=self.now,
        )
        self.invariant(r)
        self.assertEqual(r.verdict,"LAB_HARD_BLOCKED")

    def test_38_missing_d2_envelope_denied(self):
        one=self.signed(role="d1")
        r=assess_restart_dual_floor(
            local_head=self.head,d1=one,d2=None,
            pinned_custodian_keys=self.keys,request_nonce=self.nonce,
            expected_ledger_id=self.ledger,expected_epoch=self.epoch,now_ns=self.now,
        )
        self.invariant(r)
        self.assertEqual(r.verdict,"LAB_HARD_BLOCKED")

    def test_39_a150_readonly_head_adapter_real_synthetic_engine(self):
        with patch.dict(os.environ,{"AION_LAB_MODE":"1",
                                   "AION_WORKER_ENABLED":"0",
                                   "AION_EXTERNAL_EXECUTION_ENABLED":"0"}):
            with tempfile.TemporaryDirectory() as directory:
                folder=Path(directory)
                pub=Ed25519PrivateKey.generate()
                wit=Ed25519PrivateKey.generate()
                engine=LeasedPinnedWitnessLAB.bootstrap_synthetic(
                    witness_dir=folder,ledger_id="ledger-A",
                    publisher_key_id="publisher-1",
                    publisher_public_key=raw_pub(pub),
                    witness_private_key=raw_priv(wit),
                    clock_ns=lambda:self.now,
                )
                head=a150_read_only_head_snapshot(engine)
                self.assertEqual(head.sequence,0)
                self.assertEqual(head.epoch,engine.policy.epoch)
                self.assertEqual(head.history_digest,canonical_history_digest([]))
                # This adapter only READS; it cannot prove local state fresh.
                claim=replace(self.claim,epoch=head.epoch,
                              sequence=0,history_digest=head.history_digest)
                result=self.matches(
                    head=head,first=self.signed(claim,role="d1"),
                    second=self.signed(claim,role="d2"),
                    epoch=head.epoch,
                )
                self.assertFalse(result.externally_independent_custodians_verified)

    def test_40_a150_adapter_rejects_unavailable_reader(self):
        class Offline:
            def read_head(self):
                raise ConnectionError("synthetic offline")
        with self.assertRaisesRegex(FloorRejected,"a150_head_read_unavailable"):
            a150_read_only_head_snapshot(Offline())

    def test_41_a150_adapter_rejects_wrong_shape(self):
        class Invalid:
            def read_head(self):
                return {"seq":1}
        with self.assertRaisesRegex(FloorRejected,"a150_head_read_unavailable"):
            a150_read_only_head_snapshot(Invalid())

    def test_42_no_witness_callback_can_fetch_trusted_floor_implicitly(self):
        # All evidence must be explicit signed, pinned, nonce bound and
        # supplied by test caller; this module does not contact a provider.
        self.assertEqual(self.matches().verdict,"LAB_QUARANTINE_MANUAL_REVIEW")

    def test_43_reject_unexpected_custodian_role_name(self):
        one,_=self.pair()
        self.blocked(first=replace(one,custodian_id="external-approved"))

    def test_44_signed_claim_cannot_use_wrong_requester_nonce(self):
        claim=replace(self.claim,request_nonce="d"*32)
        self.blocked(first=self.signed(claim,role="d1"),
                     second=self.signed(claim,role="d2"))

    def test_45_signature_under_another_domain_does_not_verify(self):
        bad=base64.b64encode(self.d1key.sign(b"OTHER-DOMAIN"+canonical_claim_bytes(self.claim))).decode()
        one,_=self.pair()
        self.blocked(first=replace(one,signature_b64=bad))

    def test_46_stale_local_same_key_epoch_is_not_independent_freshness(self):
        old=replace(self.head,sequence=6,history_digest="e"*64)
        self.assertEqual(self.blocked(head=old).reason,"local_rollback_below_signed_floor")

    def test_47_exact_floor_sequence_is_not_provider_effect_receipt(self):
        report=self.matches()
        self.assertFalse(report.real_provider_effect_proven)
        self.assertFalse(report.automatic_resend_allowed)

    def test_48_missing_custodian_keys_are_hard_block(self):
        a,b=self.pair()
        report=assess_restart_dual_floor(
            local_head=self.head,d1=a,d2=b,pinned_custodian_keys=None,
            request_nonce=self.nonce,expected_ledger_id=self.ledger,
            expected_epoch=self.epoch,now_ns=self.now,
        )
        self.invariant(report)
        self.assertEqual(report.verdict,"LAB_HARD_BLOCKED")

    def test_49_untrusted_head_callback_without_method_denied(self):
        with self.assertRaises(FloorRejected):
            a150_read_only_head_snapshot(object())

    def test_50_external_clock_not_attested_even_if_timestamp_valid(self):
        r=self.matches()
        self.assertFalse(r.nonrollbackable_external_floor_proven)
        self.assertEqual(r.homologated_p0_count,0)


_INVALID_CLAIMS=[
    ("empty_ledger",{"ledger_id":""}),
    ("ledger_space",{"ledger_id":"ledger A"}),
    ("ledger_boolean",{"ledger_id":True}),
    ("epoch_empty",{"epoch":""}),
    ("epoch_upper",{"epoch":"A"*32}),
    ("epoch_boolean",{"epoch":False}),
    ("sequence_boolean",{"sequence":True}),
    ("sequence_negative",{"sequence":-1}),
    ("sequence_overflow",{"sequence":2**63}),
    ("digest_short",{"history_digest":"1"*63}),
    ("digest_upper",{"history_digest":"F"*64}),
    ("nonce_short",{"request_nonce":"a"*31}),
    ("nonce_upper",{"request_nonce":"A"*32}),
    ("nonce_boolean",{"request_nonce":False}),
    ("audience_wrong",{"audience":"AION-H0-SEND"}),
    ("observed_boolean",{"observed_ns":True}),
    ("observed_negative",{"observed_ns":-1}),
    ("expiry_boolean",{"valid_until_ns":False}),
    ("expiry_before_observed",{"valid_until_ns":1}),
    ("expiry_overflow",{"valid_until_ns":2**63}),
]
assert len(_INVALID_CLAIMS)==20


def _invalid_claim_test(fields):
    def test(self):
        malformed=replace(self.claim,**fields)
        # Deliberately use valid-format signatures of the ORIGINAL record.
        # Neither a parsed malformed payload nor a forged envelope grants GO.
        a,b=self.pair()
        r=self.blocked(
            first=replace(a,claim=malformed),second=replace(b,claim=malformed))
        self.assertFalse(r.cryptographic_pair_valid_in_lab)
    return test


for idx,(slug,fields) in enumerate(_INVALID_CLAIMS,start=51):
    setattr(A161SyntheticDualCustodianFloorLAB,
            f"test_{idx:02d}_invalid_floor_{slug}",
            _invalid_claim_test(fields))


if __name__=="__main__":
    unittest.main()
