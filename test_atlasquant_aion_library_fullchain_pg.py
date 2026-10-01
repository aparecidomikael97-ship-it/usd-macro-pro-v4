"""CI-only REAL PostgreSQL integration of current AtlasQuant login + stored ACL
+ authoritative audited documents + internal host selection boundary.

NO production credential, real customer, UI endpoint, automatic migration or
network service is accepted. Tables and one restricted role exist only in the
fixed ephemeral PostgreSQL16 GitHub Actions service.
"""
import os
import unittest

from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from aion_core.library_atomic_store import AtomicLibraryStore, MIGRATION_POSTGRESQL as DOCUMENT_DDL
from aion_core.library_foundation import LibraryCatalog
from atlasquant_access_control import AccessUser, authenticate, hash_password
from atlasquant_aion_library_acl_postgres import MIGRATION_POSTGRESQL as ACL_DDL
from atlasquant_aion_library_internal_entry import TrustedLibraryAppSelection
from atlasquant_aion_library_server_assembly import SandboxLibraryServerReadAssembly
from test_aion_core_library_atomic_store import IK, AK, RK, NOW, make_proofs

EXPECTED = ('postgresql://library_sandbox:synthetic_ci_only_not_for_production'
            '@localhost:5432/aion_library_sandbox')
ENABLED = (os.getenv('CI') == 'true' and
           os.getenv('AION_LIB_FULL_CHAIN_TEST') == '1' and
           os.getenv('AION_LIB_TEST_PG_DSN') == EXPECTED)
READ_DSN = ('postgresql://aion_fullchain_ci_reader:synthetic_fullchain_readonly'
            '@localhost:5432/aion_library_sandbox')


@unittest.skipUnless(ENABLED, 'fixed ephemeral PostgreSQL CI service required')
class AtlasQuantFullChainPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ENABLED: return
        try:
            import psycopg
        except ImportError as exc:
            raise unittest.SkipTest('PostgreSQL integration driver not installed') from exc
        cls.psycopg = psycopg
        with psycopg.connect(EXPECTED, autocommit=True) as db:
            with db.cursor() as c:
                c.execute("SELECT to_regclass('public.aion_library_documents')")
                if c.fetchone()[0] is None:
                    c.execute(DOCUMENT_DDL)
                c.execute("SELECT to_regclass('public.aion_library_tenant_acl')")
                if c.fetchone()[0] is None:
                    c.execute(ACL_DDL)
                c.execute('''DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aion_fullchain_ci_reader') THEN
                      CREATE ROLE aion_fullchain_ci_reader LOGIN
                        PASSWORD 'synthetic_fullchain_readonly';
                    END IF; END $$''')
                c.execute('GRANT CONNECT ON DATABASE aion_library_sandbox TO aion_fullchain_ci_reader')
                c.execute('GRANT USAGE ON SCHEMA public TO aion_fullchain_ci_reader')
                for table in ('aion_library_tenant_acl','aion_library_documents',
                              'aion_library_atomic_audit','aion_library_atomic_approval_burns'):
                    # Fixed allowlist, not a runtime/table-name input.
                    c.execute('GRANT SELECT ON '+table+' TO aion_fullchain_ci_reader')

    def setUp(self):
        with self.psycopg.connect(EXPECTED, autocommit=True) as db:
            with db.cursor() as c:
                c.execute('TRUNCATE aion_library_atomic_audit, '
                          'aion_library_atomic_approval_burns, '
                          'aion_library_documents RESTART IDENTITY CASCADE')
                c.execute('TRUNCATE aion_library_tenant_acl')
        self.environment=['SANDBOX']
        self.enabled=[True]
        self.mapping={}
        self.password='SyntheticSandboxPassword2026!'
        self.users={
            'reader.1': AccessUser('reader.1','USER',
                                  hash_password(self.password,salt=b'fullchain-reader',iterations=200000)),
            'reviewer': AccessUser('reviewer','ADMIN',
                                  hash_password(self.password,salt=b'fullchain-admin-',iterations=200000)),
        }
        self.login('reader.1')
        self.verifier=AttestationVerifier(
            identity_issuers={'fullchain-id':IK, 'authz':IK},
            approval_issuers={'human':AK},
            rights_issuers={'license':RK}, clock=lambda:NOW)
        self.writer=AtomicLibraryStore(
            connect=lambda:self.psycopg.connect(EXPECTED),
            verifier=self.verifier,clock=lambda:NOW)
        catalog=LibraryCatalog()
        entry=catalog.register_document(
            tenant_id='T-A',domain_id='LIBRARY',document_id='DOC-1',
            version=1,sha256='a'*64,source_type='BOOK',source_reference='isbn:synthetic',
            license_kind='CC_BY',rights_holder='publisher',usage_scope='INTERNAL',
            human_approved_by='reviewer')
        self.entry=catalog.transition(
            tenant_id='T-A',domain_id='LIBRARY',entry_id=entry.entry_id,
            to_state='METADATA_REVIEW',actor='reviewer')
        self.writer.import_reviewed(trusted_entry=self.entry)
        self.proofs=make_proofs(self.entry)
        self.mapping['course'] = ('T-A','LIBRARY',self.entry.entry_id)
        self.grant('reader.1','T-A','LIBRARY_READER')
        self.service=self.new_service()
        self.selection=TrustedLibraryAppSelection(
            assembly=self.service,resolve_selection=lambda name:self.mapping[name])

    def login(self, username):
        session=authenticate(username,self.password,self.users)
        self.assertIsNotNone(session)
        self.access={
            'allowed':True,'mode':'AUTHENTICATED','role':session['role'],
            'session':dict(session,authenticated_at=NOW-25,last_seen=NOW-2),
        }

    def grant(self, who,tenant,role,domain='LIBRARY'):
        with self.psycopg.connect(EXPECTED) as db:
            with db.cursor() as c:
                c.execute('''INSERT INTO aion_library_tenant_acl
                    (username,tenant_id,domain_id,library_role)
                    VALUES (%s,%s,%s,%s)''',(who,tenant,domain,role))

    def revoke(self, who='reader.1'):
        with self.psycopg.connect(EXPECTED) as db:
            with db.cursor() as c:
                c.execute('''UPDATE aion_library_tenant_acl
                    SET active=FALSE,revoked_at_unix=%s WHERE username=%s''',(NOW,who))

    def approve(self):
        ident,approval,rights=self.proofs
        return self.writer.approve(
            tenant_id='T-A',domain_id='LIBRARY',entry_id=self.entry.entry_id,
            identity_envelope=ident,approval_envelope=approval,rights_envelope=rights)

    def new_service(self, **kwargs):
        args=dict(
            environment_provider=lambda:self.environment[0],
            enabled_provider=lambda:self.enabled[0],
            access_provider=lambda:self.access,
            users_provider=lambda:self.users,
            acl_connect=lambda:self.psycopg.connect(READ_DSN),
            document_connect=lambda:self.psycopg.connect(READ_DSN),
            trusted_issuer='atlasquant.local',token_audience='library',
            attestation_issuer='fullchain-id',identity_key=IK,
            verifier=self.verifier,checkpoint_key=b'c'*32,clock=lambda:NOW)
        args.update(kwargs)
        return SandboxLibraryServerReadAssembly(**args)

    def select(self,name='course'):
        return self.selection.preview_for_host(selection=name)

    def test_real_chain_reader_rejected_before_approval(self):
        with self.assertRaises(AuthorizationDenied):self.select()

    def test_real_chain_approved_reader_minimal_fields(self):
        self.approve()
        result=self.select()
        self.assertEqual((result.selection,result.state,result.version,result.integrity_checked),
                         ('course','APPROVED_FOR_INDEXING',1,True))
        self.assertEqual(set(result.__dict__),{'selection','state','version','integrity_checked'})
        self.assertEqual(self.service._host._sessions,{})

    def test_real_chain_admin_requires_scoped_membership(self):
        self.login('reviewer')
        with self.assertRaises(AuthorizationDenied):self.select()
        self.grant('reviewer','T-A','LIBRARY_REVIEWER')
        self.assertEqual(self.select().state,'METADATA_REVIEW')

    def test_real_chain_no_cross_tenant_document_disclosure(self):
        self.grant('reader.1','T-B','LIBRARY_READER')
        self.mapping['wrong']=('T-B','LIBRARY',self.entry.entry_id)
        self.approve()
        with self.assertRaises(AuthorizationDenied):self.select('wrong')
        self.assertEqual(self.select().state,'APPROVED_FOR_INDEXING')

    def test_real_chain_acl_revoke_denied_after_success(self):
        self.approve()
        self.select()
        self.revoke()
        with self.assertRaises(AuthorizationDenied):self.select()

    def test_real_chain_second_server_observes_revocation(self):
        self.approve()
        other=TrustedLibraryAppSelection(
            assembly=self.new_service(),resolve_selection=lambda name:self.mapping[name])
        self.select()
        other.preview_for_host(selection='course')
        self.revoke()
        for client in (self.selection,other):
            with self.assertRaises(AuthorizationDenied):client.preview_for_host(selection='course')

    def test_real_chain_audit_tamper_denied(self):
        self.approve()
        self.select()
        with self.psycopg.connect(EXPECTED) as db:
            with db.cursor() as c:
                c.execute('''UPDATE aion_library_atomic_audit SET event_hash=%s
                             WHERE entry_id=%s AND event_type='APPROVE_INDEX' ''',
                          ('f'*64,self.entry.entry_id))
        with self.assertRaises(AuthorizationDenied):self.select()

    def test_real_chain_disable_after_read_denied(self):
        self.approve()
        def switch():
            self.enabled[0]=False
            return self.psycopg.connect(READ_DSN)
        target=TrustedLibraryAppSelection(
            assembly=self.new_service(document_connect=switch),
            resolve_selection=lambda name:self.mapping[name])
        with self.assertRaises(AuthorizationDenied):target.preview_for_host(selection='course')
        self.assertFalse(self.enabled[0])

    def test_real_chain_rotated_credential_fails_closed(self):
        self.approve()
        self.select()
        self.users['reader.1']=AccessUser(
            'reader.1','USER',hash_password('DifferentSyntheticSecret',salt=b'rotate-reader-ci',iterations=200000))
        with self.assertRaises(AuthorizationDenied):self.select()

    def test_real_chain_read_account_cannot_write_any_of_four_tables(self):
        statements=(
            "UPDATE aion_library_tenant_acl SET active=FALSE",
            "DELETE FROM aion_library_atomic_approval_burns",
            "DELETE FROM aion_library_atomic_audit",
            "DELETE FROM aion_library_documents",
        )
        for statement in statements:
            with self.subTest(sql=statement):
                with self.psycopg.connect(READ_DSN) as db:
                    with db.cursor() as c:
                        with self.assertRaises(self.psycopg.errors.InsufficientPrivilege):
                            c.execute(statement)


if __name__=='__main__':unittest.main()
