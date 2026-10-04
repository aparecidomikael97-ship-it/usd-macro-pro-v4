"""Opt-in actual PostgreSQL 16 read-only audit/recovery contracts.

CI-only synthetic PostgreSQL. No real customer databases or secrets.
"""
import os
import unittest
from dataclasses import replace

from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from aion_core.library_recovery_gate import LibraryRecoveryGate, SignedCheckpoint
from aion_core.library_security_runtime import ExternalIdentityBridge, VerifiedSession
from aion_core.library_atomic_store import AtomicLibraryStore, MIGRATION_POSTGRESQL
from aion_core.library_foundation import LibraryCatalog
import test_aion_core_library_atomic_store as atomic_test

DSN = os.environ.get('AION_LIB_TEST_PG_DSN')
TOKEN = 'synthetic-ci-token-not-deployed'


@unittest.skipUnless(DSN, 'synthetic PostgreSQL integration DSN not configured')
class PostgresRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DSN: return
        try: import psycopg
        except ImportError as exc: raise unittest.SkipTest('psycopg unavailable') from exc
        cls.pg=psycopg
        # CI must explicitly point at its ephemeral PostgreSQL service.
        if 'localhost' not in DSN and '127.0.0.1' not in DSN:
            raise unittest.SkipTest('recovery tests restricted to local ephemeral PostgreSQL')
        with cls.pg.connect(DSN, autocommit=True) as db:
            with db.cursor() as cur:
                cur.execute("SELECT to_regclass('public.aion_library_documents')")
                if cur.fetchone()[0] is None:
                    cur.execute(MIGRATION_POSTGRESQL)

    def setUp(self):
        with self.pg.connect(DSN,autocommit=True) as db:
            with db.cursor() as cur:
                cur.execute('TRUNCATE TABLE aion_library_atomic_audit, '
                            'aion_library_atomic_approval_burns, aion_library_documents RESTART IDENTITY CASCADE')
        self.now=atomic_test.NOW
        self.allowed={('reviewer','T-A','TRADER'):('LIBRARY_ADMIN',)}
        self.sessions={TOKEN:VerifiedSession('idp','app','reviewer',self.now-10,self.now+100)}
        self.verifier=AttestationVerifier(identity_issuers={'authz':atomic_test.IK},
                    approval_issuers={'human':atomic_test.AK},rights_issuers={'license':atomic_test.RK},
                    clock=lambda:self.now)
        self.bridge=ExternalIdentityBridge(
             verify_token=lambda token:self.sessions[token],
             lookup_roles=lambda subject,tenant,domain:self.allowed.get((subject,tenant,domain),()),
             trusted_issuer='idp',token_audience='app',attestation_issuer='authz',
             signing_key=atomic_test.IK,clock=lambda:self.now)
        self.connect=lambda:self.pg.connect(DSN)
        self.gate=LibraryRecoveryGate(identities=self.bridge,verifier=self.verifier,
                         connect=self.connect,checkpoint_key=b'c'*32,clock=lambda:self.now)
        self.store=AtomicLibraryStore(connect=self.connect,verifier=self.verifier,clock=lambda:self.now)
        catalog=LibraryCatalog()
        e=catalog.register_document(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',
              version=1,sha256='a'*64,source_type='BOOK',source_reference='isbn:123',
              license_kind='CC_BY',rights_holder='publisher',usage_scope='INTERNAL',
              human_approved_by='reviewer')
        self.entry=catalog.transition(tenant_id='T-A',domain_id='TRADER',entry_id=e.entry_id,
                        to_state='METADATA_REVIEW',actor='reviewer')
        self.store.import_reviewed(trusted_entry=self.entry)

    def inspect(self,**kw):
        d=dict(token=TOKEN,tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id)
        d.update(kw)
        return self.gate.inspect(**d)

    def checkpoint(self):
        return self.gate.admin_checkpoint(token=TOKEN,tenant_id='T-A',
                                domain_id='TRADER',entry_id=self.entry.entry_id)

    def compare(self,cp):
        return self.gate.compare_archived_checkpoint(token=TOKEN,tenant_id='T-A',
                            domain_id='TRADER',entry_id=self.entry.entry_id,archived=cp)

    def approve(self):
        ident, approval, rights = atomic_test.make_proofs(self.entry)
        return self.store.approve(tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id,
                    identity_envelope=ident,approval_envelope=approval,rights_envelope=rights)

    def mutate(self,sql,params=()):
        with self.pg.connect(DSN,autocommit=True) as db:
            with db.cursor() as cur: cur.execute(sql,params)

    def test_real_postgresql_consistent_genesis_checkpoint(self):
        r=self.inspect()
        self.assertEqual(r.state,'METADATA_REVIEW')
        cp=self.checkpoint()
        self.assertEqual(self.compare(cp),r)

    def test_real_postgresql_approval_chain_burn(self):
        self.approve()
        r=self.inspect()
        self.assertEqual((r.state,r.event_count),('APPROVED_FOR_INDEXING',2))
        self.assertEqual(self.compare(self.checkpoint()),r)

    def test_real_postgresql_genesis_tamper_denied(self):
        self.mutate('UPDATE aion_library_atomic_audit SET event_hash=%s',('f'*64,))
        with self.assertRaises(AuthorizationDenied):self.inspect()

    def test_real_postgresql_missing_burn_denied(self):
        self.approve()
        self.mutate('DELETE FROM aion_library_atomic_approval_burns')
        with self.assertRaises(AuthorizationDenied):self.inspect()

    def test_real_postgresql_stale_checkpoint_denied(self):
        cp=self.checkpoint()
        self.approve()
        with self.assertRaises(AuthorizationDenied):self.compare(cp)
        self.assertEqual(self.compare(self.checkpoint()).state,'APPROVED_FOR_INDEXING')

    def test_real_postgresql_scope_and_revoked_membership_denied(self):
        with self.assertRaises(AuthorizationDenied):self.inspect(tenant_id='T-B')
        self.allowed.clear()
        with self.assertRaises(AuthorizationDenied):self.inspect()

if __name__=='__main__':unittest.main()
