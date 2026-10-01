"""Synthetic, offline security tests. These fixtures are NOT real backup secrets."""
import hashlib
import io
import unittest
from dataclasses import replace
from aion_core.library_authorization import AuthorizationDenied
from aion_core.library_backup_evidence import (archive_digest, seal_backup, verify_backup,
                                                ArchiveDigest, SealedBackupEvidence)
from aion_core.library_recovery_gate import SignedCheckpoint

KEY = b'e' * 32
CHECKPOINT = SignedCheckpoint({'schema':'synthetic','report':{'last_event_hash':'f'*64}}, 'a'*64)
NOW = 2_000_000_000


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.archive = archive_digest(io.BytesIO(b'synthetic archive bytes'))
        self.evidence = seal_backup(archive=self.archive, checkpoint=CHECKPOINT,
                                    signing_key=KEY, clock=lambda: NOW)

    def check(self, **kwargs):
        base = dict(evidence=self.evidence, archive=self.archive,
                    checkpoint=CHECKPOINT, trusted_key=KEY, clock=lambda: NOW)
        base.update(kwargs)
        return verify_backup(**base)

    def denied(self, **kw):
        with self.assertRaises(AuthorizationDenied): self.check(**kw)

    def test_happy_path(self): self.assertTrue(self.check())
    def test_streamed_digest_correct(self):
        self.assertEqual(self.archive.sha256, hashlib.sha256(b'synthetic archive bytes').hexdigest())
        self.assertEqual(self.archive.size_bytes, len(b'synthetic archive bytes'))
    def test_multi_read_large(self):
        v=b'abc'*350000
        self.assertEqual(archive_digest(io.BytesIO(v)).sha256, hashlib.sha256(v).hexdigest())
    def test_tampered_archive(self):
        self.denied(archive=archive_digest(io.BytesIO(b'synthetic altered bytes')))
    def test_truncated_archive(self):
        self.denied(archive=archive_digest(io.BytesIO(b'synthetic archive')))
    def test_mismatched_checkpoint(self):
        self.denied(checkpoint=SignedCheckpoint({'report':{'last_event_hash':'b'*64}}, 'a'*64))
    def test_mismatched_checkpoint_mac(self):
        self.denied(checkpoint=replace(CHECKPOINT, mac_sha256='b'*64))
    def test_wrong_signing_key(self): self.denied(trusted_key=b'x'*32)
    def test_missing_signing_key(self): self.denied(trusted_key=b'x'*31)
    def test_invalid_signing_key(self):
        with self.assertRaises(AuthorizationDenied):seal_backup(archive=self.archive,checkpoint=CHECKPOINT,signing_key='plain')
    def test_expired_future_evidence(self): self.denied(clock=lambda: NOW-1)
    def test_invalid_clock_type(self): self.denied(clock=lambda: True)
    def test_empty_stream(self):
        with self.assertRaises(AuthorizationDenied):archive_digest(io.BytesIO(b''))
    def test_archive_oversize(self):
        with self.assertRaises(AuthorizationDenied):archive_digest(io.BytesIO(b'12345'),max_bytes=4)
    def test_archive_invalid_limits(self):
        for bad in (0,-1,True,600_000_000,'many'):
            with self.subTest(bad=bad), self.assertRaises(AuthorizationDenied):
                archive_digest(io.BytesIO(b'ok'),max_bytes=bad)
    def test_nonbinary_stream(self):
        with self.assertRaises(AuthorizationDenied):archive_digest(io.StringIO('text'))
    def test_stream_io_failure(self):
        class Fault:
            def read(self,_):raise OSError('private path')
        with self.assertRaises(AuthorizationDenied) as ctx:archive_digest(Fault())
        self.assertNotIn('private path',str(ctx.exception))
    def test_no_stream_reader(self):
        with self.assertRaises(AuthorizationDenied):archive_digest(object())
    def test_evidence_modified_payload(self):
        self.denied(evidence=replace(self.evidence,payload={**self.evidence.payload,'archive_size_bytes':10}))
    def test_evidence_extra_field(self):
        self.denied(evidence=replace(self.evidence,payload={**self.evidence.payload,'role':'ADMIN'}))
    def test_evidence_invalid_signature_format(self):
        self.denied(evidence=replace(self.evidence,mac_sha256='xxx'))
    def test_evidence_bad_timestamp(self):
        self.denied(evidence=replace(self.evidence,payload={**self.evidence.payload,'issued_at':True}))
    def test_evidence_invalid_size_type(self):
        self.denied(evidence=replace(self.evidence,payload={**self.evidence.payload,'archive_size_bytes':True}))
    def test_evidence_invalid_schema(self):
        self.denied(evidence=replace(self.evidence,payload={**self.evidence.payload,'schema':'other'}))
    def test_different_size_same_hash_does_not_match(self):
        self.denied(archive=ArchiveDigest(self.archive.sha256,self.archive.size_bytes+1))
    def test_bad_checkpoint_encoding(self):
        with self.assertRaises(AuthorizationDenied):seal_backup(archive=self.archive,
            checkpoint=SignedCheckpoint({'bad':object()},'a'*64),signing_key=KEY,clock=lambda:NOW)

if __name__=='__main__':unittest.main()
