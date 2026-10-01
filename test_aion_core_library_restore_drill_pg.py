"""Opt-in REAL pg_dump/pg_restore rehearsal on disposable GitHub PostgreSQL.

Only runs when CI=true, AION_LIB_RESTORE_DRILL=1 AND DSN equals the exact
synthetic ephemeral GitHub service credential. Uses a separate target DB.
Never run this procedure against a user-owned or production database.
"""
import io
import os
import shutil
import subprocess
import unittest

from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from aion_core.library_atomic_store import AtomicLibraryStore, MIGRATION_POSTGRESQL
from aion_core.library_backup_evidence import archive_digest, seal_backup, verify_backup
from aion_core.library_foundation import LibraryCatalog
from aion_core.library_recovery_gate import LibraryRecoveryGate
from aion_core.library_security_runtime import ExternalIdentityBridge, VerifiedSession
from test_aion_core_library_atomic_store import IK, AK, RK, NOW, make_proofs

DSN = os.environ.get('AION_LIB_TEST_PG_DSN', '')
ALLOWED = 'postgresql://library_sandbox:synthetic_ci_only_not_for_production@localhost:5432/aion_library_sandbox'
ENABLED = (os.environ.get('CI', '').lower() == 'true' and
           os.environ.get('AION_LIB_RESTORE_DRILL') == '1' and DSN == ALLOWED)
TOKEN = 'synthetic-ci-restore-token-no-production'
BACKUP_KEY = b'e' * 32


@unittest.skipUnless(ENABLED, 'exact synthetic ephemeral PostgreSQL CI restore configuration required')
class PostgresRestoreDrillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ENABLED:
            return
        import psycopg
        if shutil.which('docker') is None:
            raise RuntimeError('ephemeral pg_dump/pg_restore Docker client required; cannot skip drill')
        cls.pg = psycopg
        cls.target = 'aion_library_restore_sandbox'
        cls.target_dsn = ALLOWED.rsplit('/', 1)[0] + '/' + cls.target
        with cls.pg.connect(DSN, autocommit=True) as db:
            with db.cursor() as c:
                c.execute('SELECT current_database(), current_user')
                if c.fetchone() != ('aion_library_sandbox', 'library_sandbox'):
                    raise RuntimeError('not connected to designated ephemeral database')
                c.execute("SELECT to_regclass('public.aion_library_documents')")
                if c.fetchone()[0] is None:
                    c.execute(MIGRATION_POSTGRESQL)
                c.execute('DROP DATABASE IF EXISTS aion_library_restore_sandbox WITH (FORCE)')
                c.execute('CREATE DATABASE aion_library_restore_sandbox')

    @classmethod
    def tearDownClass(cls):
        if not ENABLED:
            return
        with cls.pg.connect(DSN, autocommit=True) as db:
            db.execute('DROP DATABASE IF EXISTS aion_library_restore_sandbox WITH (FORCE)')

    def setUp(self):
        with self.pg.connect(DSN, autocommit=True) as db:
            db.execute('TRUNCATE TABLE aion_library_atomic_audit, '
                       'aion_library_atomic_approval_burns, aion_library_documents RESTART IDENTITY CASCADE')
        with self.pg.connect(DSN, autocommit=True) as db:
            db.execute('DROP DATABASE IF EXISTS aion_library_restore_sandbox WITH (FORCE)')
            db.execute('CREATE DATABASE aion_library_restore_sandbox')
        self.verifier = AttestationVerifier(identity_issuers={'authz': IK},
            approval_issuers={'human': AK}, rights_issuers={'license': RK}, clock=lambda: NOW)
        self.roles = {('reviewer', 'T-A', 'TRADER'): ('LIBRARY_ADMIN',)}
        self.bridge = ExternalIdentityBridge(
            verify_token=lambda token: VerifiedSession('idp', 'app', 'reviewer', NOW - 10, NOW + 100)
                if token == TOKEN else (_ for _ in ()).throw(ValueError('not verified')),
            lookup_roles=lambda subject, tenant, domain: self.roles.get((subject, tenant, domain), ()),
            trusted_issuer='idp', token_audience='app', attestation_issuer='authz',
            signing_key=IK, clock=lambda: NOW)
        self.source_gate = self.make_gate(DSN)
        self.restored_gate = self.make_gate(self.target_dsn)
        self.store = AtomicLibraryStore(connect=lambda: self.pg.connect(DSN),
                                        verifier=self.verifier, clock=lambda: NOW)
        catalog = LibraryCatalog()
        entry = catalog.register_document(tenant_id='T-A', domain_id='TRADER', document_id='DOC-1',
            version=1, sha256='a' * 64, source_type='BOOK', source_reference='isbn:123',
            license_kind='CC_BY', rights_holder='publisher', usage_scope='INTERNAL',
            human_approved_by='reviewer')
        self.entry = catalog.transition(tenant_id='T-A', domain_id='TRADER',
            entry_id=entry.entry_id, to_state='METADATA_REVIEW', actor='reviewer')
        self.store.import_reviewed(trusted_entry=self.entry)

    def make_gate(self, dsn):
        return LibraryRecoveryGate(identities=self.bridge, verifier=self.verifier,
            connect=lambda: self.pg.connect(dsn), checkpoint_key=b'c' * 32,
            clock=lambda: NOW)

    def admin_kw(self):
        return dict(token=TOKEN, tenant_id='T-A', domain_id='TRADER', entry_id=self.entry.entry_id)

    def approve(self):
        ident, app, rights = make_proofs(self.entry)
        self.store.approve(tenant_id='T-A', domain_id='TRADER', entry_id=self.entry.entry_id,
                           identity_envelope=ident, approval_envelope=app, rights_envelope=rights)

    @staticmethod
    def docker_pg_tool(tool, db, *, archive=None):
        if tool not in ('pg_dump', 'pg_restore') or db not in (
                'aion_library_sandbox', 'aion_library_restore_sandbox'):
            raise ValueError('invalid synthetic drill command')
        cmd = ['docker', 'run', '--rm', '--network', 'host']
        if archive is not None:
            cmd.append('-i')
        cmd += ['-e', 'PGPASSWORD=synthetic_ci_only_not_for_production',
                'postgres:16', tool, '-h', 'localhost', '-U', 'library_sandbox', '-d', db]
        if tool == 'pg_dump':
            cmd += ['-Fc', '--table=public.aion_library_documents',
                    '--table=public.aion_library_atomic_approval_burns',
                    '--table=public.aion_library_atomic_audit']
        else:
            cmd += ['--no-owner', '--no-privileges', '--exit-on-error']
        result = subprocess.run(cmd, input=archive, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=100, check=False)
        if result.returncode != 0:
            # Never echo raw command, connection info or database contents in errors.
            raise RuntimeError('synthetic pg_dump/pg_restore subprocess failed')
        return result.stdout

    def capture(self, *, checkpoint=None):
        archived = checkpoint or self.source_gate.admin_checkpoint(**self.admin_kw())
        blob = self.docker_pg_tool('pg_dump', 'aion_library_sandbox')
        fingerprint = archive_digest(io.BytesIO(blob))
        sidecar = seal_backup(archive=fingerprint, checkpoint=archived,
                               signing_key=BACKUP_KEY, clock=lambda: NOW)
        return blob, fingerprint, sidecar, archived

    def restore(self, blob, sidecar, checkpoint):
        # Always hash exactly the bytes being restored; NEVER trust a separately supplied digest.
        fresh_fingerprint = archive_digest(io.BytesIO(blob))
        self.assertTrue(verify_backup(evidence=sidecar, archive=fresh_fingerprint,
            checkpoint=checkpoint, trusted_key=BACKUP_KEY, clock=lambda: NOW))
        self.docker_pg_tool('pg_restore', 'aion_library_restore_sandbox', archive=blob)
        return self.restored_gate.compare_archived_checkpoint(**self.admin_kw(),
                                                               archived=checkpoint)

    def test_approved_document_survives_real_pg_dump_restore(self):
        self.approve()
        blob, fp, sidecar, cp = self.capture()
        expected = self.source_gate.inspect(**self.admin_kw())
        self.assertEqual(self.restore(blob, sidecar, cp), expected)
        with self.pg.connect(self.target_dsn) as db:
            doc = db.execute('SELECT state FROM aion_library_documents').fetchone()[0]
            self.assertEqual(doc, 'APPROVED_FOR_INDEXING')
            n = db.execute('SELECT COUNT(*) FROM aion_library_atomic_audit').fetchone()[0]
            self.assertEqual(n, 2)
            burned = db.execute('SELECT COUNT(*) FROM aion_library_atomic_approval_burns').fetchone()[0]
            self.assertEqual(burned, 1)

    def test_reviewed_document_survives_real_dump_restore(self):
        blob, fp, sidecar, cp = self.capture()
        self.assertEqual(self.restore(blob, sidecar, cp).state, 'METADATA_REVIEW')

    def test_tampered_archive_denied_before_restore(self):
        blob, _, sidecar, cp = self.capture()
        modified = blob[:-1] + bytes([blob[-1] ^ 1])
        self.assertNotEqual(blob, modified)
        with self.assertRaises(AuthorizationDenied):
            self.restore(modified, sidecar, cp)

    def test_altered_restored_audit_rejected(self):
        self.approve()
        blob, fp, sidecar, cp = self.capture()
        self.restore(blob, sidecar, cp)
        with self.pg.connect(self.target_dsn, autocommit=True) as db:
            db.execute('UPDATE aion_library_atomic_audit SET event_hash=%s WHERE event_type=%s',
                       ('f' * 64, 'GENESIS'))
        with self.assertRaises(AuthorizationDenied):
            self.restored_gate.compare_archived_checkpoint(**self.admin_kw(), archived=cp)

    def test_checkpoint_from_before_approval_rejected_after_restore(self):
        stale = self.source_gate.admin_checkpoint(**self.admin_kw())
        self.approve()
        blob, fp, sidecar, cp = self.capture(checkpoint=stale)
        with self.assertRaises(AuthorizationDenied):
            self.restore(blob, sidecar, cp)

    def test_tenant_membership_removed_rejects_restored_checkpoint(self):
        blob, fp, sidecar, cp = self.capture()
        self.restore(blob, sidecar, cp)
        self.roles.clear()
        with self.assertRaises(AuthorizationDenied):
            self.restored_gate.compare_archived_checkpoint(**self.admin_kw(), archived=cp)

if __name__ == '__main__': unittest.main()
