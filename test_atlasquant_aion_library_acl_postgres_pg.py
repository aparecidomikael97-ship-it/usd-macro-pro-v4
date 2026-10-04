"""Opt-in PostgreSQL 16 sandbox tests of persisted AION tenant memberships.

Only runs in CI against the exact synthetic local DSN. Creates a synthetic
SELECT-only DB role to verify that the adapter has no write authority.
"""
import os
import unittest
from urllib.parse import quote, urlsplit, urlunsplit

from aion_core.library_authorization import AuthorizationDenied
from atlasquant_aion_library_acl_postgres import MIGRATION_POSTGRESQL, PostgresLibraryMembership

DSN = os.getenv('AION_LIB_TEST_PG_DSN')
EXPECTED = ('postgresql://library_sandbox:synthetic_ci_only_not_for_production'
            '@localhost:5432/aion_library_sandbox')
ENABLED = os.getenv('CI', '').lower() == 'true' and DSN == EXPECTED


@unittest.skipUnless(ENABLED, 'strict CI-only synthetic PostgreSQL DSN required')
class PostgreSQLMembershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ENABLED:
            return
        try:
            import psycopg
        except ImportError as exc:
            raise unittest.SkipTest('psycopg unavailable') from exc
        cls.pg = psycopg
        cls.admin_dsn = EXPECTED
        # Fixture has unique table/role names and no external configuration.
        with psycopg.connect(EXPECTED, autocommit=True) as db:
            with db.cursor() as cur:
                cur.execute(MIGRATION_POSTGRESQL)
                cur.execute('''DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aion_acl_ci_reader') THEN
                        CREATE ROLE aion_acl_ci_reader LOGIN PASSWORD 'synthetic_reader_only';
                    END IF;
                END $$''')
                cur.execute('GRANT CONNECT ON DATABASE aion_library_sandbox TO aion_acl_ci_reader')
                cur.execute('GRANT USAGE ON SCHEMA public TO aion_acl_ci_reader')
                cur.execute('GRANT SELECT ON aion_library_tenant_acl TO aion_acl_ci_reader')
        host = urlsplit(EXPECTED)
        cls.reader_dsn=urlunsplit((host.scheme,'aion_acl_ci_reader:synthetic_reader_only@localhost:5432',
                                   host.path,'',''))

    def setUp(self):
        with self.pg.connect(self.admin_dsn,autocommit=True) as db:
            with db.cursor() as cur:
                cur.execute('TRUNCATE aion_library_tenant_acl')
        self.adapter=PostgresLibraryMembership(connect=lambda:self.pg.connect(self.reader_dsn))

    def seed(self, username='reader.1', tenant='T-A', role='LIBRARY_READER', domain='LIBRARY'):
        with self.pg.connect(self.admin_dsn) as db:
            with db.cursor() as cur:
                cur.execute('''INSERT INTO aion_library_tenant_acl
                   (username,tenant_id,domain_id,library_role)
                   VALUES (%s,%s,%s,%s)''',(username,tenant,domain,role))

    def revoke(self, username='reader.1', tenant='T-A', role='LIBRARY_READER'):
        with self.pg.connect(self.admin_dsn) as db:
            with db.cursor() as cur:
                cur.execute('''UPDATE aion_library_tenant_acl SET active=FALSE,revoked_at_unix=2000000000
                               WHERE username=%s AND tenant_id=%s AND library_role=%s''',
                            (username,tenant,role))

    def test_real_pg_grant_and_scope(self):
        self.seed()
        self.assertEqual(self.adapter.roles_for('reader.1','T-A','LIBRARY'),('LIBRARY_READER',))
        self.assertEqual(self.adapter.roles_for('reader.1','T-B','LIBRARY'),())
        self.assertEqual(self.adapter.roles_for('reader.1','T-A','NEGOCIOS'),())
        self.assertEqual(self.adapter.roles_for('other.1','T-A','LIBRARY'),())

    def test_real_pg_revoke_immediate_fresh_query(self):
        self.seed()
        self.assertEqual(self.adapter.roles_for('reader.1','T-A','LIBRARY'),('LIBRARY_READER',))
        self.revoke()
        self.assertEqual(self.adapter.roles_for('reader.1','T-A','LIBRARY'),())

    def test_real_pg_other_worker_revoke_sees_latest(self):
        self.seed()
        other=PostgresLibraryMembership(connect=lambda:self.pg.connect(self.reader_dsn))
        self.assertEqual(other.roles_for('reader.1','T-A','LIBRARY'),('LIBRARY_READER',))
        self.revoke()
        self.assertEqual(other.roles_for('reader.1','T-A','LIBRARY'),())
        self.assertEqual(self.adapter.roles_for('reader.1','T-A','LIBRARY'),())

    def test_real_pg_admin_role_not_inherited_across_tenants(self):
        self.seed(username='admin.1',role='LIBRARY_ADMIN')
        self.assertEqual(self.adapter.roles_for('admin.1','T-A','LIBRARY'),('LIBRARY_ADMIN',))
        self.assertEqual(self.adapter.roles_for('admin.1','T-B','LIBRARY'),())

    def test_real_pg_reader_db_role_cannot_write(self):
        self.seed()
        with self.pg.connect(self.reader_dsn) as db:
            with db.cursor() as cur:
                with self.assertRaises(self.pg.errors.InsufficientPrivilege):
                    cur.execute('''UPDATE aion_library_tenant_acl SET active=FALSE
                                   WHERE username='reader.1' ''')

    def test_real_pg_invalid_acl_constraints_enforced(self):
        with self.pg.connect(self.admin_dsn) as db:
            with db.cursor() as cur:
                with self.assertRaises(self.pg.errors.CheckViolation):
                    cur.execute('''INSERT INTO aion_library_tenant_acl
                    (username,tenant_id,domain_id,library_role)
                    VALUES ('reader.1','T-A','LIBRARY','GLOBAL_ADMIN')''')

    def _preview_host(self):
        from atlasquant_access_control import AccessUser, authenticate, hash_password
        from atlasquant_aion_library_host_access import AtlasQuantLibraryHostAccess
        from atlasquant_aion_library_postgres_preview import LibraryPostgresReadFacade
        from aion_core.library_authorization import AttestationVerifier
        from aion_core.library_recovery_gate import IntegrityReport
        from unittest.mock import Mock
        now=2_000_000_000
        pw='SyntheticStrongPassword!'
        user=AccessUser('reader.1','USER',hash_password(pw,salt=b'z'*16,iterations=200_000))
        users={'reader.1':user}
        ses=authenticate('reader.1',pw,users)
        access={'allowed':True,'mode':'AUTHENTICATED','role':'USER',
                'session':dict(ses,authenticated_at=now-10,last_seen=now-1)}
        key=b'i'*32
        host=AtlasQuantLibraryHostAccess(
            access_provider=lambda:access,users_provider=lambda:users,
            membership_provider=self.adapter.roles_for,
            trusted_issuer='atlasquant.local',token_audience='library',
            attestation_issuer='atlasquant-library',signing_key=key,clock=lambda:now)
        verifier=AttestationVerifier(identity_issuers={'atlasquant-library':key},
            approval_issuers={'human':b'p'*32},rights_issuers={'license':b'r'*32},
            clock=lambda:now)
        service=LibraryPostgresReadFacade(
            host=host,verifier=verifier,connect=lambda:None,
            checkpoint_key=b'c'*32,clock=lambda:now)
        report=IntegrityReport('T-A','LIBRARY','LIB-1',1,'APPROVED_FOR_INDEXING',
                               'a'*64,2,'b'*64,2,'c'*64)
        service._gate.inspect=Mock(return_value=report)
        return service

    def test_real_pg_reader_adapter_to_preview_facade(self):
        self.seed()
        svc=self._preview_host()
        report=svc.read_preview(tenant_id='T-A',domain_id='LIBRARY',entry_id='LIB-1')
        self.assertEqual(report.state,'APPROVED_FOR_INDEXING')
        self.assertEqual(report.entry_id,'LIB-1')

    def test_real_pg_revoke_during_preview_fails_closed(self):
        self.seed()
        svc=self._preview_host()
        report=svc._gate.inspect.return_value
        def lose_membership(**kwargs):
            self.revoke()
            return report
        svc._gate.inspect.side_effect=lose_membership
        with self.assertRaises(AuthorizationDenied):
            svc.read_preview(tenant_id='T-A',domain_id='LIBRARY',entry_id='LIB-1')

    def test_real_pg_host_denies_revoked_membership(self):
        from atlasquant_access_control import AccessUser, authenticate, hash_password
        from atlasquant_aion_library_host_access import AtlasQuantLibraryHostAccess
        now=2_000_000_000
        pw='SyntheticStrongPassword!'
        user=AccessUser('reader.1','USER',hash_password(pw,salt=b'z'*16,iterations=200_000))
        users={'reader.1':user}
        ses=authenticate('reader.1',pw,users)
        access={'allowed':True,'mode':'AUTHENTICATED','role':'USER',
                'session':dict(ses,authenticated_at=now-10,last_seen=now-1)}
        host=AtlasQuantLibraryHostAccess(
            access_provider=lambda:access,users_provider=lambda:users,
            membership_provider=self.adapter.roles_for,
            trusted_issuer='atlasquant.local',token_audience='library',
            attestation_issuer='atlasquant-library',signing_key=b'k'*32,
            clock=lambda:now)
        self.seed()
        self.assertEqual(host._lookup_roles('reader.1','T-A','LIBRARY'),('LIBRARY_READER',))
        self.revoke()
        with self.assertRaises(AuthorizationDenied):
            host._lookup_roles('reader.1','T-A','LIBRARY')

if __name__=='__main__':unittest.main()
