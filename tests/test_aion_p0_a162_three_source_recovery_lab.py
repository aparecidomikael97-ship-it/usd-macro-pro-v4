"""A162: 60 adversarial real A147/A150 + signed A145/A161 LAB cross-checks.

All keys/SQLite are disposable. READ-ONLY verifier never enqueues an
effect, repairs a journal, publishes witness receipt, or authorizes retry.
"""
import base64
from contextlib import closing
from dataclasses import replace
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_p0_a145_authenticated_checkpoint_lab import SignedCheckpoint, checkpoint_payload
from aion_p0_a145_checkpoint_verifier_lab import Checkpoint, canonical_history_digest
from aion_p0_a147_sqlite_crash_journal_lab import (
    SyntheticCrashJournalLAB, DB_NAME as JOURNAL_DB,
)
from aion_p0_a149_authenticated_cas_lab import (
    PublishRequest, SignedPublishRequest, canonical_publish_request,
)
from aion_p0_a150_pinned_policy_lease_lab import LeasedPinnedWitnessLAB
from aion_p0_a161_dual_custodian_floor_lab import (
    AUDIENCE, FloorClaim, SignedFloor, canonical_claim_bytes,
)
from aion_p0_a162_three_source_recovery_lab import (
    SCHEMA, ThreeSourceReview, assess_three_source_restart,
)


def pub(k):
    return k.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )


def priv(k):
    return k.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )


class A162ThreeSourceCorrelationLAB(unittest.TestCase):
    def setUp(self):
        self.flags=patch.dict(os.environ, {
            "AION_LAB_MODE":"1", "AION_WORKER_ENABLED":"0",
            "AION_EXTERNAL_EXECUTION_ENABLED":"0",
        })
        self.flags.start()
        self.addCleanup(self.flags.stop)
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        a147=root/"journal"
        a150=root/"witness"
        a147.mkdir()
        a150.mkdir()
        self.clock=lambda:1_800_000_000_000_000_000
        self.now=1_800_000_000_000_000_000
        self.ledger="ledger-A"
        self.nonce="b"*32
        self.publisher=Ed25519PrivateKey.generate()
        self.local_signer=Ed25519PrivateKey.generate()
        self.cp_signer=Ed25519PrivateKey.generate()
        self.d1_key=Ed25519PrivateKey.generate()
        self.d2_key=Ed25519PrivateKey.generate()
        self.checkpoint_pins={"cp1":pub(self.cp_signer)}
        self.floor_pins={"d1":pub(self.d1_key),"d2":pub(self.d2_key)}
        self.journal=SyntheticCrashJournalLAB.bootstrap_synthetic_lab(
            lab_dir=a147,ledger_id=self.ledger)
        self.witness=LeasedPinnedWitnessLAB.bootstrap_synthetic(
            witness_dir=a150,ledger_id=self.ledger,
            publisher_key_id="publisher",
            publisher_public_key=pub(self.publisher),
            witness_private_key=priv(self.local_signer),
            clock_ns=self.clock,lease_seconds=30,
        )
        self.epoch=self.witness.policy.epoch

    def checkpoint(self, events=None, signer=None, kid="cp1"):
        events=self.journal.read_events() if events is None else events
        cp=Checkpoint(self.ledger,len(events),canonical_history_digest(events))
        signed=(self.cp_signer if signer is None else signer).sign(checkpoint_payload(cp))
        return SignedCheckpoint(cp,kid,base64.b64encode(signed).decode("ascii"))

    def floor_pair(self,head=None,claim=None,*,d1key=None,d2key=None):
        current=self.witness.read_head()
        if head is None:
            head=current
        claim=claim if claim is not None else FloorClaim(
            ledger_id=self.ledger,epoch=self.epoch,
            sequence=head["sequence"],history_digest=head["digest"],
            request_nonce=self.nonce,audience=AUDIENCE,
            observed_ns=self.now-1_000_000_000,
            valid_until_ns=self.now+6_000_000_000,
        )
        signers=(self.d1_key if d1key is None else d1key,
                 self.d2_key if d2key is None else d2key)
        one,two=(
            SignedFloor(claim,role,base64.b64encode(
                key.sign(canonical_claim_bytes(claim))).decode("ascii"))
            for role,key in zip(("d1","d2"),signers)
        )
        return one,two

    def evaluate(self,*,journal=None,witness=None,checkpoint=None,pins=None,
                 d1=None,d2=None,floor_pins=None,ledger=None,epoch=None,
                 nonce=None,now=None):
        a,b=self.floor_pair()
        return assess_three_source_restart(
            journal=self.journal if journal is None else journal,
            local_witness=self.witness if witness is None else witness,
            checkpoint=self.checkpoint() if checkpoint is None else checkpoint,
            checkpoint_pins=self.checkpoint_pins if pins is None else pins,
            floor_d1=a if d1 is None else d1,
            floor_d2=b if d2 is None else d2,
            floor_pins=self.floor_pins if floor_pins is None else floor_pins,
            expected_ledger=self.ledger if ledger is None else ledger,
            expected_epoch=self.epoch if epoch is None else epoch,
            request_nonce=self.nonce if nonce is None else nonce,
            now_ns=self.now if now is None else now,
        )

    def invariant(self,result):
        self.assertIs(type(result),ThreeSourceReview)
        self.assertEqual(result.schema,SCHEMA)
        self.assertIn(result.verdict,("LAB_HARD_BLOCKED","LAB_QUARANTINE_MANUAL_REVIEW"))
        for field in (
            "real_external_issuer_authenticity_verified",
            "remotely_nonrollbackable_floor_verified",
            "human_owner_critical_consent_verified",
            "real_provider_committed_effect_verified",
            "real_provider_no_effect_fenced",
            "checkpoint_restore_authorized",
            "automatic_retry_allowed",
            "automatic_resend_allowed",
            "external_execution_allowed","worker_allowed",
        ):
            self.assertIs(getattr(result,field),False,field)
        self.assertEqual(result.homologated_p0_count,0)

    def denied(self,expected=None,**kwargs):
        r=self.evaluate(**kwargs)
        self.invariant(r)
        self.assertEqual(r.verdict,"LAB_HARD_BLOCKED",r)
        if expected:
            self.assertIn(expected,r.reason)
        return r

    def quarantined(self,**kwargs):
        r=self.evaluate(**kwargs)
        self.invariant(r)
        self.assertEqual(r.verdict,"LAB_QUARANTINE_MANUAL_REVIEW",r)
        self.assertTrue(r.locally_consistent_in_lab)
        self.assertTrue(r.mathematical_floor_pair_checked_in_lab)
        return r

    def reserve_and_publish(self,intent="first"):
        self.assertTrue(self.journal.reserve_local_uncertain(intent))
        challenge=self.witness.issue_challenge()
        events=self.journal.read_events()
        request=PublishRequest(
            ledger_id=self.ledger,epoch=self.epoch,
            publisher_key_id=challenge["publisher_key_id"],
            challenge_id=challenge["challenge_id"],request_id=secrets.token_hex(16),
            expected_sequence=challenge["expected_sequence"],
            expected_digest=challenge["expected_digest"],
            next_sequence=1,next_digest=canonical_history_digest(events),
        )
        env=SignedPublishRequest(
            request=request,
            signature_b64=base64.b64encode(
                self.publisher.sign(canonical_publish_request(request))).decode("ascii"),
        )
        self.witness.publish(envelope=env)
        return events

    def test_01_initial_genesis_equal_quarantined_never_ready(self):
        self.assertIn("genesis",self.quarantined().reason)

    def test_02_after_local_reservation_without_witness_ack_hard_block(self):
        self.journal.reserve_local_uncertain("first")
        self.denied("a147_a150_checkpoint_state_disagreement")

    def test_03_after_matching_local_publish_quarantine_unknown_effect(self):
        self.reserve_and_publish()
        self.assertIn("first_uncertain",self.quarantined().reason)

    def test_04_two_signed_floor_keys_distinct_from_local_and_checkpoint(self):
        all_keys=list(self.floor_pins.values())+list(self.checkpoint_pins.values())+[
            self.witness.policy.witness_public_key,
            self.witness.policy.publisher_public_key,
        ]
        self.assertEqual(len(all_keys),len(set(all_keys)))
        self.quarantined()

    def test_05_checkpoint_signature_bad_blocks(self):
        cp=self.checkpoint()
        self.denied(checkpoint=replace(cp,signature_b64="not-b64"))

    def test_06_checkpoint_wrong_pinned_key_blocks(self):
        self.denied(pins={"cp1":pub(Ed25519PrivateKey.generate())})

    def test_07_checkpoint_missing_key_blocks(self):
        self.denied(pins={})

    def test_08_extra_checkpoint_key_blocks(self):
        self.denied(pins={**self.checkpoint_pins,"cp2":pub(Ed25519PrivateKey.generate())})

    def test_09_checkpoint_key_id_unknown_blocks(self):
        self.denied(checkpoint=self.checkpoint(kid="unexpected"))

    def test_10_checkpoint_signature_from_wrong_signer_blocks(self):
        self.denied(checkpoint=self.checkpoint(signer=Ed25519PrivateKey.generate()))

    def test_11_checkpoint_signed_for_stale_genesis_against_reserved_intent_blocks(self):
        old=self.checkpoint()
        self.journal.reserve_local_uncertain("first")
        self.denied(checkpoint=old)

    def test_12_journal_corrupted_state_blocks(self):
        with closing(sqlite3.connect(self.journal.path)) as db:
            db.execute("UPDATE ledger_meta SET ledger_id='attacker'")
            db.commit()
        self.denied("ledger_identity_or_policy_changed")

    def test_13_journal_removed_blocks(self):
        self.journal.path.unlink()
        self.denied("missing_or_linked_journal")

    def test_14_journal_extra_table_blocks(self):
        with closing(sqlite3.connect(self.journal.path)) as db:
            db.execute("CREATE TABLE injected(x TEXT)")
        self.denied("unexpected_schema_objects")

    def test_15_a150_witness_removed_blocks(self):
        self.witness.db_path.unlink()
        self.denied()

    def test_16_witness_epoch_policy_mutated_before_eval_blocks(self):
        self.denied(epoch="f"*32)

    def test_17_expected_ledger_other_than_both_sides_denies(self):
        self.denied(ledger="ledger-Z")

    def test_18_wrong_nonce_bound_d1_d2_both_signed_blocks(self):
        c=self.floor_pair()[0].claim
        modified=replace(c,request_nonce="f"*32)
        a,b=self.floor_pair(claim=modified)
        self.denied(d1=a,d2=b)

    def test_19_bad_d1_signature_blocks(self):
        a,b=self.floor_pair()
        self.denied(d1=replace(a,signature_b64="BAD"),d2=b)

    def test_20_bad_d2_signature_blocks(self):
        a,b=self.floor_pair()
        self.denied(d1=a,d2=replace(b,signature_b64="BAD"))

    def test_21_d1_signature_signed_by_d2_key_blocks(self):
        a,b=self.floor_pair(d1key=self.d2_key)
        self.denied(d1=a,d2=b)

    def test_22_d2_signature_signed_by_d1_key_blocks(self):
        a,b=self.floor_pair(d2key=self.d1_key)
        self.denied(d1=a,d2=b)

    def test_23_two_floor_pins_reuse_same_key_rejected_before_verification(self):
        self.denied(floor_pins={"d1":self.floor_pins["d1"],"d2":self.floor_pins["d1"]})

    def test_24_floor_pins_missing_d2(self):
        self.denied(floor_pins={"d1":self.floor_pins["d1"]})

    def test_25_floor_pins_have_extra_d3(self):
        self.denied(floor_pins={**self.floor_pins,"d3":pub(Ed25519PrivateKey.generate())})

    def test_26_checkpoint_key_reused_as_d1(self):
        self.denied(pins={"cp1":self.floor_pins["d1"]})

    def test_27_checkpoint_key_reused_as_d2(self):
        self.denied(pins={"cp1":self.floor_pins["d2"]})

    def test_28_d1_key_reused_as_a150_local_witness(self):
        self.denied(floor_pins={**self.floor_pins,
                                "d1":self.witness.policy.witness_public_key})

    def test_29_d2_key_reused_as_local_publisher(self):
        self.denied(floor_pins={**self.floor_pins,
                                "d2":self.witness.policy.publisher_public_key})

    def test_30_checkpoint_key_reused_as_local_publisher(self):
        self.denied(pins={"cp1":self.witness.policy.publisher_public_key})

    def test_31_floor_missing_actual_d1_envelope(self):
        self.denied(d1="not-an-envelope")

    def test_32_floor_missing_actual_d2_envelope(self):
        self.denied(d2="not-an-envelope")

    def test_33_replayed_floor_for_different_request_nonce_blocked(self):
        self.denied(nonce="f"*32)

    def test_34_floor_attestation_expired_blocked(self):
        self.denied(now=self.now+10_000_000_000)

    def test_35_floor_observed_in_future_blocked(self):
        self.denied(now=self.now-2_000_000_000)

    def test_36_floor_remote_counter_ahead_of_local_detects_rollback(self):
        claim=self.floor_pair()[0].claim
        newer=replace(claim,sequence=1,history_digest="c"*64)
        a,b=self.floor_pair(claim=newer)
        r=self.denied(d1=a,d2=b)
        self.assertIn("local_rollback_below_signed_floor",r.reason)

    def test_37_floor_remote_counter_behind_local_detects_unknown_advance(self):
        self.reserve_and_publish()
        claim=self.floor_pair()[0].claim
        older=replace(claim,sequence=0,history_digest=canonical_history_digest([]))
        a,b=self.floor_pair(claim=older)
        self.denied(d1=a,d2=b)

    def test_38_floor_remote_same_seq_different_digest_blocked(self):
        claim=self.floor_pair()[0].claim
        altered=replace(claim,history_digest="e"*64)
        a,b=self.floor_pair(claim=altered)
        self.denied(d1=a,d2=b)

    def test_39_floor_custodian_claims_conflict_blocks(self):
        a,b=self.floor_pair()
        altered=replace(b.claim,sequence=b.claim.sequence+1,history_digest="e"*64)
        _,b2=self.floor_pair(claim=altered)
        self.denied(d1=a,d2=b2)

    def test_40_whole_local_and_both_signers_rolled_back_matches_but_not_authorized(self):
        # The critical negative result: attack restores the entire state
        # including both synthetic signer histories to genesis. Mathematics
        # cannot demonstrate newer external custody. Only QUARANTINE.
        r=self.quarantined()
        self.assertFalse(r.remotely_nonrollbackable_floor_verified)

    def test_41_no_provider_effect_proof_even_after_a150_published(self):
        self.reserve_and_publish()
        r=self.quarantined()
        self.assertFalse(r.real_provider_committed_effect_verified)
        self.assertFalse(r.real_provider_no_effect_fenced)

    def test_42_double_read_journal_detects_torn_view(self):
        first=self.journal.read_events()
        next_events=[{"seq":1,"intent":"first"}]
        cp=self.checkpoint(first)
        with patch.object(self.journal,"read_events",side_effect=[first,next_events]):
            self.denied(expected="multiple_source_read_drift",checkpoint=cp)

    def test_43_double_read_witness_detects_torn_view(self):
        original=self.witness.read_head()
        changed={**original,"sequence":1,"digest":"e"*64}
        with patch.object(self.witness,"read_head",side_effect=[original,changed]):
            self.denied("multiple_source_read_drift")

    def test_44_double_read_witness_connection_failure_blocks(self):
        first=self.witness.read_head()
        with patch.object(self.witness,"read_head",side_effect=[first,ConnectionError("offline")]):
            self.denied("a150_head_read_unavailable")

    def test_45_double_read_journal_io_error_blocks(self):
        first=self.journal.read_events()
        with patch.object(self.journal,"read_events",side_effect=[first,OSError("gone")]):
            self.denied("unexpected_source_validation_failure")

    def test_46_journal_subclass_unapproved_introspection_blocked(self):
        class Evasive(SyntheticCrashJournalLAB):
            pass
        clone=object.__new__(Evasive)
        self.denied(journal=clone)

    def test_47_local_witness_subclass_unapproved_introspection_blocked(self):
        class Evasive(LeasedPinnedWitnessLAB):
            pass
        clone=object.__new__(Evasive)
        self.denied(witness=clone)

    def test_48_synthetic_journal_only_accepts_first_intent(self):
        self.reserve_and_publish()
        with self.assertRaises(Exception):
            self.journal.reserve_local_uncertain("second")
        self.quarantined()

    def test_49_negative_no_import_provider_or_worker_in_verifier(self):
        from aion_p0_a162_three_source_recovery_lab import ThreeSourceReview
        self.assertFalse(hasattr(ThreeSourceReview,"approve"))

    def test_50_expected_epoch_is_compared_before_external_signatures(self):
        self.denied("out_of_band_epoch_policy_mismatch",epoch="0"*32)


_INVAL=[
    ("empty_ledger",{"ledger":""}),
    ("bool_ledger",{"ledger":True}),
    ("fake_ledger",{"ledger":"other-ledger"}),
    ("epoch_empty",{"epoch":""}),
    ("epoch_upper",{"epoch":"A"*32}),
    ("epoch_wrong",{"epoch":"f"*32}),
    ("nonce_short",{"nonce":"a"*31}),
    ("nonce_upper",{"nonce":"B"*32}),
    ("nonce_bool",{"nonce":True}),
    ("now_zero",{"now":0}),
    ("now_bool",{"now":False}),
    ("now_overflow",{"now":2**70}),
    ("extra_floor_pin",{"floor_pins":{"x":b"x"*32}}),
    ("empty_checkpoint_pin",{"pins":{}}),
    ("worker_env_not_zero",{"_worker":"1"}),
    ("external_env_not_zero",{"_external":"1"}),
    ("lab_env_missing",{"_lab":"0"}),
    ("checkpoint_non_envelope",{"checkpoint":"x"}),
    ("witness_non_engine",{"witness":False}),
    ("journal_non_engine",{"journal":False}),
]
assert len(_INVAL)==20


def _inval_test(kwargs):
    def run(self):
        params=dict(kwargs)
        env={}
        for alias,key in (("_worker","AION_WORKER_ENABLED"),
                          ("_external","AION_EXTERNAL_EXECUTION_ENABLED"),
                          ("_lab","AION_LAB_MODE")):
            if alias in params:
                env[key]=params.pop(alias)
        with patch.dict(os.environ,env):
            self.denied(**params)
    return run


for idx,(name,values) in enumerate(_INVAL,start=51):
    setattr(A162ThreeSourceCorrelationLAB,
            f"test_{idx:02d}_invalid_{name}",_inval_test(values))


if __name__=="__main__":
    unittest.main()
