"""A160 P0/H0: explicit base-class CAS bypass probes on A150 witness.

No real producer, Worker, network, identity enrollment or external service.
All signatures and SQLite files are generated inside synthetic temp directories.
RED-first: the unmodified A149 method can be explicitly invoked against
an A150 object, bypassing lease / witness clock and creating orphan challenges.
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

from aion_p0_a145_checkpoint_verifier_lab import canonical_history_digest
from aion_p0_a149_authenticated_cas_lab import (
    A149Denied, AuthenticatedWitnessLAB, PublishRequest,
    SignedPublishRequest, canonical_publish_request,
)
from aion_p0_a150_pinned_policy_lease_lab import (
    LeasedPinnedWitnessLAB, NANOSECONDS_PER_SECOND,
)


def raw_private(key):
    return key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def raw_public(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


class SyntheticClock:
    def __init__(self):
        self.value=1_800_000_000_000_000_000

    def __call__(self):
        return self.value

    def forward(self, seconds):
        self.value += seconds * NANOSECONDS_PER_SECOND


class A160BaseMutationBypassLAB(unittest.TestCase):
    def setUp(self):
        self.flags=patch.dict(os.environ,{
            "AION_LAB_MODE":"1",
            "AION_WORKER_ENABLED":"0",
            "AION_EXTERNAL_EXECUTION_ENABLED":"0",
        })
        self.flags.start()
        self.addCleanup(self.flags.stop)
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.wdir=Path(folder.name)/"a150"
        self.wdir.mkdir()
        self.publisher=Ed25519PrivateKey.generate()
        self.witness_key=Ed25519PrivateKey.generate()
        self.clock=SyntheticClock()
        self.engine=LeasedPinnedWitnessLAB.bootstrap_synthetic(
            witness_dir=self.wdir,ledger_id="ledger-A",
            publisher_key_id="publisher-1",
            publisher_public_key=raw_public(self.publisher),
            witness_private_key=raw_private(self.witness_key),
            clock_ns=self.clock,lease_seconds=30,
        )
        self.events=[{"seq":1,"intent":"first"}]

    def _rows(self, table):
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            return db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]

    def signed(self):
        challenge=self.engine.issue_challenge()
        request=PublishRequest(
            ledger_id=challenge["ledger_id"],
            epoch=challenge["epoch"],
            publisher_key_id=challenge["publisher_key_id"],
            challenge_id=challenge["challenge_id"],
            request_id=secrets.token_hex(16),
            expected_sequence=challenge["expected_sequence"],
            expected_digest=challenge["expected_digest"],
            next_sequence=challenge["expected_sequence"]+1,
            next_digest=canonical_history_digest(self.events),
        )
        return SignedPublishRequest(
            request=request,
            signature_b64=base64.b64encode(
                self.publisher.sign(canonical_publish_request(request))
            ).decode("ascii"),
        )

    def denied(self,fn):
        with self.assertRaisesRegex(A149Denied,"base_mutator_on_subclass_forbidden"):
            fn()
        self.assertEqual(self.engine.read_head()["sequence"],0)

    def test_01_direct_base_challenge_cannot_create_orphan(self):
        self.denied(lambda:AuthenticatedWitnessLAB.issue_challenge(self.engine))
        self.assertEqual(self._rows("challenges"),0)
        self.assertEqual(self._rows("challenge_lease"),0)

    def test_02_base_method_descriptor_cannot_create_orphan(self):
        bound=AuthenticatedWitnessLAB.__dict__["issue_challenge"].__get__(self.engine)
        self.denied(bound)
        self.assertEqual(self._rows("challenges"),0)

    def test_03_explicit_super_issue_challenge_denied(self):
        self.denied(lambda:super(LeasedPinnedWitnessLAB,self.engine).issue_challenge())
        self.assertEqual(self._rows("challenges"),0)

    def test_04_base_challenge_rejects_even_if_clock_is_expired(self):
        self.clock.forward(301)
        self.denied(lambda:AuthenticatedWitnessLAB.issue_challenge(self.engine))
        self.assertEqual(self._rows("challenges"),0)

    def test_05_base_challenge_cannot_bypass_tampered_lease_policy(self):
        self.clock.value=1
        self.denied(lambda:AuthenticatedWitnessLAB.issue_challenge(self.engine))

    def test_06_base_challenge_denies_twice_without_side_effect(self):
        for _ in range(2):
            self.denied(lambda:AuthenticatedWitnessLAB.issue_challenge(self.engine))
        self.assertEqual(self._rows("challenges"),0)

    def test_07_base_publish_rejected_with_valid_unexpired_request(self):
        envelope=self.signed()
        self.denied(lambda:AuthenticatedWitnessLAB.publish(self.engine,envelope=envelope))
        self.assertEqual(self._rows("receipts"),0)

    def test_08_base_publish_cannot_bypass_expired_lease(self):
        envelope=self.signed()
        self.clock.forward(31)
        self.denied(lambda:AuthenticatedWitnessLAB.publish(self.engine,envelope=envelope))
        self.assertEqual(self._rows("receipts"),0)

    def test_09_base_publish_descriptor_rejected(self):
        envelope=self.signed()
        bound=AuthenticatedWitnessLAB.__dict__["publish"].__get__(self.engine)
        self.denied(lambda:bound(envelope=envelope))

    def test_10_explicit_super_publish_rejected(self):
        envelope=self.signed()
        self.denied(lambda:super(LeasedPinnedWitnessLAB,self.engine).publish(envelope=envelope))

    def test_11_base_publish_denies_unknown_result_before_any_signature_parse(self):
        self.denied(lambda:AuthenticatedWitnessLAB.publish(self.engine,envelope=None))

    def test_12_base_publish_denies_before_fault_injection(self):
        envelope=self.signed()
        self.denied(lambda:AuthenticatedWitnessLAB.publish(
            self.engine,envelope=envelope,fault="before_commit"))

    def test_13_base_publish_rejects_replayed_completed_receipt(self):
        envelope=self.signed()
        self.engine.publish(envelope=envelope)
        with self.assertRaisesRegex(A149Denied,"base_mutator_on_subclass_forbidden"):
            AuthenticatedWitnessLAB.publish(self.engine,envelope=envelope)
        self.assertEqual(self.engine.read_head()["sequence"],1)
        self.assertEqual(self._rows("receipts"),1)

    def test_14_base_issue_rejects_after_completed_head(self):
        envelope=self.signed()
        self.engine.publish(envelope=envelope)
        with self.assertRaisesRegex(A149Denied,"base_mutator_on_subclass_forbidden"):
            AuthenticatedWitnessLAB.issue_challenge(self.engine)
        self.assertEqual(self._rows("challenges"),1)

    def test_15_base_publish_rejects_bad_signature_before_sqlite(self):
        env=self.signed()
        forged=replace(env,signature_b64="not_base64")
        self.denied(lambda:AuthenticatedWitnessLAB.publish(self.engine,envelope=forged))
        self.assertEqual(self._rows("receipts"),0)

    def test_16_base_publish_rejects_different_request_id_before_sqlite(self):
        env=self.signed()
        new=replace(env.request,request_id="a"*32)
        altered=replace(env,request=new)
        self.denied(lambda:AuthenticatedWitnessLAB.publish(self.engine,envelope=altered))

    def test_17_base_issue_rejected_after_reopen_with_valid_pin(self):
        clone=LeasedPinnedWitnessLAB(
            witness_dir=self.wdir,ledger_id="ledger-A",
            pinned_policy=self.engine.policy,clock_ns=self.clock,lease_seconds=30)
        with self.assertRaisesRegex(A149Denied,"base_mutator_on_subclass_forbidden"):
            AuthenticatedWitnessLAB.issue_challenge(clone)
        self.assertEqual(self._rows("challenges"),0)

    def test_18_base_publish_rejected_after_reopen_with_valid_pin(self):
        env=self.signed()
        clone=LeasedPinnedWitnessLAB(
            witness_dir=self.wdir,ledger_id="ledger-A",
            pinned_policy=self.engine.policy,clock_ns=self.clock,lease_seconds=30)
        with self.assertRaisesRegex(A149Denied,"base_mutator_on_subclass_forbidden"):
            AuthenticatedWitnessLAB.publish(clone,envelope=env)
        self.assertEqual(self._rows("receipts"),0)

    def test_19_base_challenge_legacy_A149_instance_still_works(self):
        other_dir=self.wdir.parent/"a149"
        other_dir.mkdir()
        simple=AuthenticatedWitnessLAB.bootstrap_synthetic(
            witness_dir=other_dir,ledger_id="ledger-Z",
            publisher_key_id="publisher-legacy",
            publisher_public_key=raw_public(self.publisher),
            witness_private_key=raw_private(self.witness_key))
        ch=simple.issue_challenge()
        self.assertEqual(ch["ledger_id"],"ledger-Z")

    def test_20_a150_real_subclass_lease_challenge_still_works(self):
        ch=self.engine.issue_challenge()
        self.assertEqual(ch["ledger_id"],"ledger-A")
        self.assertEqual(self._rows("challenges"),1)
        self.assertEqual(self._rows("challenge_lease"),1)

    def test_21_a150_real_subclass_publish_still_works(self):
        env=self.signed()
        receipt=self.engine.publish(envelope=env)
        self.assertEqual(receipt.receipt.sequence,1)

    def test_22_a150_real_expired_lease_still_denies(self):
        env=self.signed()
        self.clock.forward(31)
        with self.assertRaisesRegex(A149Denied,"challenge_lease_expired"):
            self.engine.publish(envelope=env)
        self.assertEqual(self._rows("receipts"),0)

    def test_23_a150_real_unexpected_clock_rewind_denied(self):
        self.clock.forward(2)
        self.engine.issue_challenge()
        self.clock.value-=5*NANOSECONDS_PER_SECOND
        with self.assertRaises(A149Denied):
            self.engine.issue_challenge()

    def test_24_a150_read_only_base_head_api_remains_allowed(self):
        head=AuthenticatedWitnessLAB.read_head(self.engine)
        self.assertEqual(head["sequence"],0)
        self.assertEqual(head["epoch"],self.engine.policy.epoch)

    def test_25_a150_read_only_base_receipt_lookup_remains_allowed(self):
        self.assertIsNone(AuthenticatedWitnessLAB.read_receipt(self.engine,"f"*32))

    def test_26_declared_worker_go_and_external_issuer_not_proven(self):
        self.assertTrue(os.environ["AION_LAB_MODE"]=="1")
        self.assertEqual(os.environ["AION_EXTERNAL_EXECUTION_ENABLED"],"0")
        self.assertEqual(self.engine.read_head()["sequence"],0)

    def test_27_inheritance_is_original_route_not_new_production_API(self):
        self.assertTrue(issubclass(LeasedPinnedWitnessLAB,AuthenticatedWitnessLAB))
        self.assertIsNot(LeasedPinnedWitnessLAB.publish,AuthenticatedWitnessLAB.publish)
        self.assertIsNot(LeasedPinnedWitnessLAB.issue_challenge,
                         AuthenticatedWitnessLAB.issue_challenge)

    def test_28_operator_pin_cannot_be_replaced_by_base_mutation(self):
        env=self.signed()
        prior=self.engine.policy
        self.denied(lambda:AuthenticatedWitnessLAB.publish(self.engine,envelope=env))
        self.assertEqual(self.engine.policy,prior)

    def test_29_base_challenge_cannot_advance_local_clock_floor(self):
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            before=db.execute("SELECT floor_ns FROM witness_clock").fetchone()[0]
        self.denied(lambda:AuthenticatedWitnessLAB.issue_challenge(self.engine))
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            after=db.execute("SELECT floor_ns FROM witness_clock").fetchone()[0]
        self.assertEqual(before,after)

    def test_30_base_publish_cannot_advance_local_clock_floor(self):
        env=self.signed()
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            before=db.execute("SELECT floor_ns FROM witness_clock").fetchone()[0]
        self.denied(lambda:AuthenticatedWitnessLAB.publish(self.engine,envelope=env))
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            after=db.execute("SELECT floor_ns FROM witness_clock").fetchone()[0]
        self.assertEqual(before,after)


if __name__=="__main__":
    unittest.main()
