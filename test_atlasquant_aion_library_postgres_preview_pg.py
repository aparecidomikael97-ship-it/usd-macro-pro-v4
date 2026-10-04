"""Opt-in real PostgreSQL16 CI-only tests of native-login preview against authoritative data.

The DSN MUST be the exact synthetic GitHub service; never direct to a real DB.
"""
import os
import unittest

from atlasquant_access_control import AccessUser, authenticate, hash_password
from atlasquant_aion_library_host_access import AtlasQuantLibraryHostAccess
from atlasquant_aion_library_postgres_preview import LibraryPostgresReadFacade
from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from aion_core.library_atomic_store import AtomicLibraryStore, MIGRATION_POSTGRESQL
from aion_core.library_foundation import LibraryCatalog
from test_aion_core_library_atomic_store import IK, AK, RK, NOW, make_proofs

DSN='postgresql://library_sandbox:synthetic_ci_only_not_for_production@localhost:5432/aion_library_sandbox'
ENABLED=os.environ.get('CI','').lower()=='true' and os.environ.get('AION_LIB_TEST_PG_DSN')==DSN


@unittest.skipUnless(ENABLED,'dedicated synthetic GitHub PostgreSQL required')
class NativeLoginPostgreSQLPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ENABLED: return
        try: import psycopg
        except ImportError as exc: raise unittest.SkipTest('sandbox driver unavailable') from exc
        cls.pg=psycopg
        cls.pw='SyntheticPassword!2026'
        cls.pw_hash=hash_password(cls.pw,salt=b'z'*16,iterations=200_000)
        with psycopg.connect(DSN,autocommit=True) as db:
            with db.cursor() as c:
                c.execute("SELECT to_regclass('public.aion_library_documents')")
                if c.fetchone()[0] is None: c.execute(MIGRATION_POSTGRESQL)

    def setUp(self):
        with self.pg.connect(DSN,autocommit=True) as db:
            with db.cursor() as c:
                c.execute('TRUNCATE TABLE aion_library_atomic_audit, aion_library_atomic_approval_burns, '
                          'aion_library_documents RESTART IDENTITY CASCADE')
        self.users={'reviewer':AccessUser('reviewer','ADMIN',self.pw_hash),
                    'client.1':AccessUser('client.1','USER',self.pw_hash)}
        self.members={('reviewer','T-A','TRADER'):('LIBRARY_ADMIN',),
                      ('client.1','T-A','TRADER'):('LIBRARY_READER',)}
        self.now=NOW
        self.sign_in('reviewer')
        self.host=AtlasQuantLibraryHostAccess(
            access_provider=lambda:self.access,users_provider=lambda:self.users,
            membership_provider=lambda u,t,d:self.members.get((u,t,d),()),
            trusted_issuer='atlasquant.local',token_audience='aion-library',
            attestation_issuer='authz',signing_key=IK,clock=lambda:self.now)
        self.verifier=AttestationVerifier(identity_issuers={'authz':IK},
            approval_issuers={'human':AK},rights_issuers={'license':RK},clock=lambda:self.now)
        self.connect=lambda:self.pg.connect(DSN)
        self.preview=LibraryPostgresReadFacade(host=self.host,verifier=self.verifier,
                               connect=self.connect,checkpoint_key=b'c'*32,clock=lambda:self.now)
        self.store=AtomicLibraryStore(connect=self.connect,verifier=self.verifier,clock=lambda:self.now)
        catalog=LibraryCatalog()
        e=catalog.register_document(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',
              version=1,sha256='a'*64,source_type='BOOK',source_reference='isbn:synthetic',
              license_kind='CC_BY',rights_holder='synthetic-rights',usage_scope='INTERNAL',
              human_approved_by='reviewer')
        self.entry=catalog.transition(tenant_id='T-A',domain_id='TRADER',entry_id=e.entry_id,
                                      to_state='METADATA_REVIEW',actor='reviewer')
        self.store.import_reviewed(trusted_entry=self.entry)

    def sign_in(self,name):
        s=authenticate(name,self.pw,self.users)
        self.access={'allowed':True,'mode':'AUTHENTICATED','role':s['role'],
                    'session':dict(s,authenticated_at=self.now-30,last_seen=self.now-1)}

    def read(self,**kw):
        args=dict(tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id)
        args.update(kw)
        return self.preview.read_preview(**args)

    def approve(self):
        ident,approval,rights=make_proofs(self.entry)
        return self.store.approve(tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id,
                                  identity_envelope=ident,approval_envelope=approval,rights_envelope=rights)

    def test_real_db_admin_review_and_reader_only_after_approval(self):
        self.assertEqual(self.read().state,'METADATA_REVIEW')
        self.sign_in('client.1')
        with self.assertRaises(AuthorizationDenied): self.read()
        self.approve()
        v=self.read()
        self.assertEqual((v.state,v.integrity_checked),('APPROVED_FOR_INDEXING',True))

    def test_real_db_scope_requires_membership(self):
        self.approve()
        with self.assertRaises(AuthorizationDenied): self.read(tenant_id='T-B')
        with self.assertRaises(AuthorizationDenied): self.read(domain_id='NEGOCIOS')
        self.members.clear()
        with self.assertRaises(AuthorizationDenied): self.read()

    def test_real_db_tampered_audit_denied(self):
        self.approve()
        with self.pg.connect(DSN,autocommit=True) as db:
            with db.cursor() as c:
                c.execute("UPDATE aion_library_atomic_audit SET event_hash=%s "
                          "WHERE event_type='GENESIS'",('f'*64,))
        with self.assertRaises(AuthorizationDenied):self.read()

    def test_real_db_missing_consumed_approval_denied(self):
        self.approve()
        with self.pg.connect(DSN,autocommit=True) as db:
            with db.cursor() as c:c.execute('DELETE FROM aion_library_atomic_approval_burns')
        with self.assertRaises(AuthorizationDenied):self.read()

    def test_real_db_login_revoked_does_not_expose_document(self):
        self.approve()
        self.sign_in('client.1')
        self.users['client.1']=AccessUser('client.1','USER',self.pw_hash,active=False)
        with self.assertRaises(AuthorizationDenied):self.read()


if __name__=='__main__':unittest.main()
