"""P0 LAB: real V2.24 owner signature canonical Base64URL and local nonce restore.

Uses existing historical preflight fixtures and ephemeral Ed25519 keypairs.
A mathematically valid signature under a TEST key does NOT authenticate the
actual HUMAN_OWNER. GREEN on the rollback counterexample means the P0 remains
OPEN. No owner decision, Worker, provider, network or production effects.
"""
from __future__ import annotations

import base64
from pathlib import Path
import sqlite3
import tempfile
import unittest

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_owner_signature_ceremony import (
    _decode_signature,
    canonical_owner_signature_bytes,
)
import test_atlasquant_aion_v224_owner_signature_ceremony as legacy


class OwnerSignatureCanonicalLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-owner-signature-canonical-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.secret, self.roots = legacy.owner_keypair()
        self.evidence, built = legacy.request_for(self.roots)
        self.assertEqual(built["state"], "READY_FOR_EXTERNAL_OWNER_SIGNATURE")
        self.request = built["request"]
        self.canonical = legacy.sign(self.secret, self.request)
        self.assertEqual(len(self.canonical), 86)
        self.nonce = PersistentNonceRegistry(self.root / "nonce.sqlite3")

    def verify(self, signature=None):
        return legacy.verify(
            self.request,
            self.canonical if signature is None else signature,
            self.roots, self.nonce, self.evidence,
        )

    def assert_denied_without_nonce_claim(self, signature):
        r=self.verify(signature)
        self.assertEqual(r["state"], "BLOCKED")
        self.assertIn("OWNER_SIGNATURE_INVALID", r["blockers"])
        self.assertIs(r["execution_allowed"], False)
        self.assertIs(r["worker_armed"], False)
        self.assertIs(r["owner_decision_ready"], False)
        self.assertEqual(self.nonce.count(), 0)
        return r

    def test_01_canonical_unpadded_signature_is_ready_for_decision_only(self):
        r=self.verify()
        self.assertEqual(r["state"], "READY_FOR_EXPLICIT_OWNER_DECISION")
        self.assertTrue(r["owner_signature_verified"])
        self.assertIs(r["owner_decision_ready"], True)
        self.assertEqual(r["owner_decision"], "UNDECIDED")
        self.assertFalse(r["execution_allowed"])
        self.assertFalse(r["core_freeze_authorized"])
        self.assertFalse(r["worker_armed"])
        self.assertEqual(self.nonce.count(), 1)

    def test_02_extra_base64_padding_cannot_alias_same_owner_signature(self):
        alt = self.canonical+"=="
        self.assertEqual(
            base64.urlsafe_b64decode(alt),
            base64.urlsafe_b64decode(self.canonical+"=="),
        )
        self.assert_denied_without_nonce_claim(alt)

    def test_03_ignored_punctuation_cannot_alias_same_signature(self):
        alt=self.canonical[:13]+"*"+self.canonical[13:]
        self.assertEqual(
            base64.urlsafe_b64decode(alt+"="*(-len(alt)%4)),
            base64.urlsafe_b64decode(self.canonical+"=="),
        )
        self.assert_denied_without_nonce_claim(alt)

    def test_04_ignored_newline_cannot_alias_same_signature(self):
        alt=self.canonical[:9]+"\n"+self.canonical[9:]
        self.assert_denied_without_nonce_claim(alt)

    def test_05_nonzero_unused_padding_bits_are_not_an_alias_signature(self):
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        last=alphabet.index(self.canonical[-1])
        alias=self.canonical[:-1]+alphabet[last ^ 1]
        self.assertNotEqual(alias,self.canonical)
        self.assertEqual(
            base64.urlsafe_b64decode(alias+"=="),
            base64.urlsafe_b64decode(self.canonical+"=="),
        )
        self.assert_denied_without_nonce_claim(alias)

    def test_06_unicode_signature_rejected_without_coercion(self):
        self.assert_denied_without_nonce_claim(self.canonical+"é")

    def test_07_empty_signature_rejected_without_nonce_claim(self):
        self.assert_denied_without_nonce_claim("")

    def test_08_object_signature_rejected_without_coercion(self):
        class Attack:
            def encode(self,*args,**kwargs):
                raise AssertionError("ATTACKER_ENCODE_INVOKED")
        self.assert_denied_without_nonce_claim(Attack())

    def test_09_valid_signature_with_one_byte_changed_is_denied(self):
        b=bytearray(base64.urlsafe_b64decode(self.canonical+"=="))
        b[0]^=1
        changed=base64.urlsafe_b64encode(bytes(b)).rstrip(b"=").decode()
        r=self.verify(changed)
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("OWNER_SIGNATURE_INVALID",r["blockers"])
        self.assertEqual(self.nonce.count(),0)

    def test_10_repeated_canonical_signature_is_rejected_by_local_nonce(self):
        self.assertEqual(self.verify()["state"],"READY_FOR_EXPLICIT_OWNER_DECISION")
        second=self.verify()
        self.assertEqual(second["state"],"BLOCKED")
        self.assertIn("OWNER_SIGNATURE_NONCE_REPLAYED", second["blockers"])
        self.assertEqual(self.nonce.count(),1)

    def test_11_64byte_signature_roundtrip_is_one_canonical_encoding(self):
        b=base64.urlsafe_b64decode(self.canonical+"==")
        self.assertEqual(len(b),64)
        self.assertEqual(_decode_signature(self.canonical),b)
        self.assertEqual(base64.urlsafe_b64encode(b).rstrip(b"=").decode(),self.canonical)

    def test_12_wrong_signature_with_valid_shape_cannot_create_owner_decision(self):
        other=legacy.owner_keypair()[0]
        fake=base64.urlsafe_b64encode(
            other.sign(canonical_owner_signature_bytes(self.request))
        ).rstrip(b"=").decode()
        r=self.verify(fake)
        self.assertEqual(r["state"],"BLOCKED")
        self.assertFalse(r["execution_allowed"])
        self.assertFalse(r["owner_decision_ready"])
        self.assertEqual(self.nonce.count(),0)


class OwnerNonceRollbackGapLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="aion-owner-nonce-sqlite-rollback-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root/"replay.sqlite3"
        self.registry=PersistentNonceRegistry(self.db)
        self.secret,self.roots=legacy.owner_keypair()
        self.evidence,built=legacy.request_for(self.roots)
        self.assertEqual(built["state"],"READY_FOR_EXTERNAL_OWNER_SIGNATURE")
        self.request=built["request"]
        self.signature=legacy.sign(self.secret,self.request)

    def verify(self):
        return legacy.verify(
            self.request,self.signature,self.roots,self.registry,self.evidence
        )

    def snapshot(self):
        backup=self.root/"before-first-nonce-claim.sqlite3"
        with sqlite3.connect(str(self.db)) as source:
            with sqlite3.connect(str(backup)) as dest:
                source.backup(dest)
        return backup

    def test_13_same_local_sqlite_nonce_db_denies_replay_without_rollback(self):
        self.assertEqual(self.verify()["state"],"READY_FOR_EXPLICIT_OWNER_DECISION")
        r=self.verify()
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("OWNER_SIGNATURE_NONCE_REPLAYED",r["blockers"])

    def test_14_restored_nonce_db_accepts_same_signature_again_OPEN_P0(self):
        backup=self.snapshot()
        first=self.verify()
        self.assertEqual(first["state"],"READY_FOR_EXPLICIT_OWNER_DECISION")
        self.assertEqual(self.registry.count(),1)
        with sqlite3.connect(str(backup)) as source:
            with sqlite3.connect(str(self.db)) as dest:
                source.backup(dest)
        self.assertEqual(self.registry.count(),0)
        again=self.verify()
        self.assertEqual(again["state"],"READY_FOR_EXPLICIT_OWNER_DECISION")
        self.assertTrue(again["owner_signature_verified"])
        self.assertFalse(again["execution_allowed"])
        self.assertFalse(again["worker_armed"])
        # This test PASSES by reproducing local replay on restored evidence;
        # an authentic out-of-rollback-domain nonce witness is still required.
        self.assertEqual(self.registry.count(),1)


if __name__=="__main__":
    unittest.main()
