"""P0 LAB: tighten local public trust-root registry intake, NOT owner enrollment.

RED before candidate fix: Python permissive Base64 accepts aliases and
from_json_file reads an oversized file before the size check. No private
owner material, real accounts, external requests or execution rights used.
"""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_trust_root import (
    MAX_FILE_BYTES, SCHEMA, TrustRootRegistry,
)

class RealTrustRootLocalInputFencesLAB(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="aion-trust-root-p0-")
        self.addCleanup(self.dir.cleanup)
        self.root = pathlib.Path(self.dir.name)
        # Deterministic synthetic Ed25519 key; no real owner identity.
        self.key = Ed25519PrivateKey.from_private_bytes(b"\x37"*32)
        pub = self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.pub = pub
        self.canonical = base64.urlsafe_b64encode(pub).rstrip(b"=").decode("ascii")
        self.entry = {
            "key_id":"synthetic-owner-public-001", "key_version":1,
            "algorithm":"Ed25519","public_key_b64":self.canonical,
            "status":"ACTIVE",
            "not_before":"2026-10-19T00:00:00Z",
            "not_after":"2026-10-22T00:00:00Z",
        }
        self.doc = {"schema":SCHEMA,"roots":[self.entry],"revoked_key_ids":[]}

    def mapping(self,value=None):
        doc=dict(self.doc)
        doc["roots"]=[dict(self.entry,public_key_b64=self.canonical if value is None else value)]
        return doc

    def file(self, content):
        p=self.root/"roots.json"
        p.write_bytes(content)
        return p

    def test_01_valid_canonical_unpadded_base64_root_verifies_ephemeral_signature(self):
        p=self.file(json.dumps(self.doc,sort_keys=True).encode("utf-8"))
        original=hashlib.sha256(p.read_bytes()).digest()
        roots=TrustRootRegistry.from_json_file(p)
        entry,issue=roots.verify_key_available(
            "synthetic-owner-public-001",1,"2026-10-20T12:00:00Z")
        self.assertIsNone(issue)
        self.assertIsNotNone(entry)
        data=b"P0 LAB signature form only, no owner approval"
        entry.public_key().verify(self.key.sign(data),data)
        self.assertEqual(original,hashlib.sha256(p.read_bytes()).digest())

    def test_02_extra_base64_padding_is_not_one_canonical_public_key_encoding(self):
        with self.assertRaises(ValueError):
            TrustRootRegistry.from_mapping(self.mapping(self.canonical+"="))

    def test_03_ignored_nonbase64_character_cannot_alias_same_root(self):
        dirty=self.canonical[:7]+"*"+self.canonical[7:]
        with self.assertRaises(ValueError):
            TrustRootRegistry.from_mapping(self.mapping(dirty))

    def test_04_embedded_newline_in_key_must_not_be_ignored(self):
        dirty=self.canonical[:4]+"\n"+self.canonical[4:]
        with self.assertRaises(ValueError):
            TrustRootRegistry.from_mapping(self.mapping(dirty))

    def test_05_nonzero_unused_pad_bits_cannot_alias_valid_public_key(self):
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        last=alphabet.index(self.canonical[-1])
        # The last Base64URL character of 32 bytes represents four data
        # bits and two unused padding bits; toggling those retains the bytes.
        alias=self.canonical[:-1]+alphabet[last ^ 1]
        self.assertEqual(
            base64.urlsafe_b64decode(alias+"="),
            self.pub,
        )
        self.assertNotEqual(alias,self.canonical)
        with self.assertRaises(ValueError):
            TrustRootRegistry.from_mapping(self.mapping(alias))

    def test_06_invalid_unicode_key_rejected_without_coercion(self):
        with self.assertRaises(ValueError):
            TrustRootRegistry.from_mapping(self.mapping(self.canonical+"é"))

    def test_07_oversized_root_file_rejected_before_unbounded_read(self):
        p=self.file(b"x"*(MAX_FILE_BYTES+1))
        original=hashlib.sha256(p.read_bytes()).digest()
        with mock.patch.object(pathlib.Path,"read_bytes",
                side_effect=AssertionError("WHOLE_FILE_READ_WAS_NOT_BOUNDED")):
            with self.assertRaises(ValueError):
                TrustRootRegistry.from_json_file(p)
        self.assertEqual(original,hashlib.sha256(p.read_bytes()).digest())

    def test_08_symlink_root_is_rejected(self):
        target=self.root/"source.json"
        target.write_text(json.dumps(self.doc),encoding="utf-8")
        link=self.root/"linked.json"
        try:link.symlink_to(target)
        except (NotImplementedError,OSError):
            self.skipTest("symlink creation denied by OS permissions")
        with self.assertRaises(ValueError):
            TrustRootRegistry.from_json_file(link)

    def test_09_duplicate_json_member_is_denied(self):
        raw=json.dumps(self.doc,separators=(",",":")).replace(
            '"schema":', '"schema":"FORGED-OTHER-SCHEMA","schema":',1)
        p=self.file(raw.encode())
        with self.assertRaises(ValueError):
            TrustRootRegistry.from_json_file(p)

    def test_10_missing_root_file_is_denied(self):
        with self.assertRaises((ValueError,OSError)):
            TrustRootRegistry.from_json_file(self.root/"absent.json")

    def test_11_directory_is_not_a_root_file(self):
        with self.assertRaises((ValueError,OSError)):
            TrustRootRegistry.from_json_file(self.root)

    def test_12_revoked_entry_never_verifies_as_current_owner(self):
        revoked=dict(self.entry,status="REVOKED")
        roots=TrustRootRegistry.from_mapping(
            {**self.doc,"roots":[revoked]})
        entry,issue=roots.verify_key_available(
            self.entry["key_id"],1,"2026-10-20T12:00:00Z")
        self.assertEqual(issue,"TRUST_KEY_REVOKED")

    def test_13_source_with_wrong_key_size_rejected(self):
        small=base64.urlsafe_b64encode(self.pub[:-1]).rstrip(b"=").decode("ascii")
        with self.assertRaises(ValueError):
            TrustRootRegistry.from_mapping(self.mapping(small))

    def test_14_synthetic_proof_never_enrolls_external_owner_or_worker(self):
        roots=TrustRootRegistry.from_mapping(self.mapping())
        self.assertEqual(roots.key_count,1)
        self.assertFalse(hasattr(roots,"enable_worker"))
        self.assertFalse(hasattr(roots,"verify_external_highwater"))
        self.assertFalse(hasattr(roots,"issuer_enrolled"))


if __name__=="__main__":
    unittest.main()
