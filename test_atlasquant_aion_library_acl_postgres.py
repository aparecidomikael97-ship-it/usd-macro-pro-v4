"""Offline adversarial checks for fresh PostgreSQL ACL membership reads."""
import unittest
from unittest.mock import Mock

from aion_core.library_authorization import AuthorizationDenied
from atlasquant_aion_library_acl_postgres import (
    MIGRATION_POSTGRESQL, PostgresLibraryMembership,
)


class ACLFakeCursor:
    def __init__(self, rows=(), fail_at=None):
        self.rows=rows
        self.fail_at=fail_at
        self.calls=[]
        self.closed=False
    def execute(self,sql,params=None):
        self.calls.append((sql,params))
        if self.fail_at=='execute': raise ConnectionError('DB-SECRET')
    def fetchmany(self,n):
        if self.fail_at=='fetch': raise ConnectionError('DB-SECRET')
        return self.rows[:n]
    def close(self): self.closed=True

class ACLFakeDB:
    def __init__(self,rows=(), autocommit=False, fail_at=None):
        self.autocommit=autocommit
        self.cur=ACLFakeCursor(rows,fail_at=fail_at)
        self.closed=False
        self.rolled=False
    def cursor(self): return self.cur
    def rollback(self):self.rolled=True
    def close(self):self.closed=True

class MembershipTests(unittest.TestCase):
    def setUp(self):
        self.db=ACLFakeDB([('LIBRARY_READER',True,None)])
        self.store=PostgresLibraryMembership(connect=lambda:self.db)
    def lookup(self,**kw):
        p=dict(username='reader.1',tenant_id='T-A',domain_id='LIBRARY')
        p.update(kw)
        return self.store.roles_for(**p)
    def denial(self,**kw):
        with self.assertRaises(AuthorizationDenied) as e:self.lookup(**kw)
        self.assertNotIn('DB-SECRET',str(e.exception))

    def test_single_role(self):
        self.assertEqual(self.lookup(),('LIBRARY_READER',))
        self.assertIn('READ COMMITTED, READ ONLY',self.db.cur.calls[0][0])
        self.assertEqual(self.db.cur.calls[1][1],('reader.1','T-A','LIBRARY'))
        self.assertTrue(self.db.closed and self.db.rolled and self.db.cur.closed)

    def test_no_membership_fails_closed_in_host(self):
        self.db.cur.rows=[]
        self.assertEqual(self.lookup(),())

    def test_revoked_role_does_not_grant(self):
        self.db.cur.rows=[('LIBRARY_READER',False,2000000000)]
        self.assertEqual(self.lookup(),())

    def test_revoked_and_remaining_role(self):
        self.db.cur.rows=[('LIBRARY_ADMIN',False,2000000000),('LIBRARY_READER',True,None)]
        self.assertEqual(self.lookup(),('LIBRARY_READER',))

    def test_role_order_deterministic(self):
        self.db.cur.rows=[('LIBRARY_REVIEWER',True,None),('LIBRARY_ADMIN',True,None)]
        self.assertEqual(self.lookup(),('LIBRARY_ADMIN','LIBRARY_REVIEWER'))

    def test_not_trusting_supplied_role_claim(self):
        self.denial(username='admin;DROP')
        self.assertFalse(self.db.cur.calls)

    def test_invalid_tenant_domain_rejected_before_sql(self):
        for bad in ('',None,'T;DROP','A'*65,1,False):
            with self.subTest(bad=bad):
                self.denial(tenant_id=bad)
                self.denial(domain_id=bad)
        self.assertFalse(self.db.cur.calls)

    def test_invalid_username_rejected_before_sql(self):
        for bad in (None,'','Reader.1',' x','x', 'a'*65,1):
            with self.subTest(bad=bad):self.denial(username=bad)
        self.assertFalse(self.db.cur.calls)

    def test_no_autocommit(self):
        self.db.autocommit=True
        self.denial()
        self.assertTrue(self.db.closed)

    def test_factory_failure(self):
        self.store=PostgresLibraryMembership(connect=lambda:(_ for _ in ()).throw(RuntimeError('DB-SECRET')))
        self.denial()

    def test_no_connection(self):
        self.store=PostgresLibraryMembership(connect=lambda:None)
        self.denial()

    def test_unknown_role_poisoning_denied(self):
        self.db.cur.rows=[('LIBRARY_READER',True,None),('GLOBAL_ADMIN',True,None)]
        self.denial()

    def test_malformed_boolean_row_denied(self):
        for v in (1,'true',None):
            self.db.cur.rows=[('LIBRARY_READER',v,None)]
            self.denial()

    def test_active_with_revocation_timestamp_denied(self):
        self.db.cur.rows=[('LIBRARY_READER',True,5)]
        self.denial()

    def test_inactive_without_revocation_timestamp_denied(self):
        self.db.cur.rows=[('LIBRARY_READER',False,None)]
        self.denial()

    def test_duplicate_rows_denied(self):
        self.db.cur.rows=[('LIBRARY_READER',True,None)]*2
        self.denial()

    def test_more_than_three_rows_denied(self):
        self.db.cur.rows=[('LIBRARY_READER',True,None)]*4
        self.denial()

    def test_fetch_failure_fails_closed(self):
        self.db.cur.fail_at='fetch';self.denial()
        self.assertTrue(self.db.closed and self.db.cur.closed)

    def test_query_failure_fails_closed(self):
        self.db.cur.fail_at='execute';self.denial()
        self.assertTrue(self.db.closed and self.db.cur.closed)

    def test_connection_scope_is_ephemeral_per_call(self):
        calls=[]
        def factory():
            db=ACLFakeDB([('LIBRARY_READER',True,None)] if not calls else [])
            calls.append(db)
            return db
        self.store=PostgresLibraryMembership(connect=factory)
        self.assertEqual(self.lookup(),('LIBRARY_READER',))
        self.assertEqual(self.lookup(),())
        self.assertEqual(len(calls),2)
        self.assertTrue(all(x.closed for x in calls))

    def test_bad_factory_configuration(self):
        with self.assertRaises(AuthorizationDenied):PostgresLibraryMembership(connect=None)

    def test_ddl_separate_from_read_path(self):
        from atlasquant_aion_library_acl_postgres import _SELECT
        self.assertIn('PRIMARY KEY(username, tenant_id, domain_id, library_role)',MIGRATION_POSTGRESQL)
        self.assertIn('CHECK ((active AND revoked_at_unix IS NULL)',MIGRATION_POSTGRESQL)
        self.assertIn('SELECT library_role, active, revoked_at_unix',_SELECT)
        self.assertNotIn('INSERT INTO',_SELECT)
        self.assertNotIn('UPDATE ',_SELECT)

    def test_host_remains_authority(self):
        from atlasquant_access_control import AccessUser, authenticate, hash_password
        from atlasquant_aion_library_host_access import AtlasQuantLibraryHostAccess
        now=2_000_000_000
        pw_hash=hash_password('SyntheticLibraryPass##',salt=b'z'*16,iterations=200_000)
        users={'reader.1':AccessUser('reader.1','USER',pw_hash)}
        ses=authenticate('reader.1','SyntheticLibraryPass##',users)
        access={'allowed':True,'mode':'AUTHENTICATED','role':'USER',
                'session':dict(ses,authenticated_at=now-10,last_seen=now-1)}
        host=AtlasQuantLibraryHostAccess(
            access_provider=lambda:access, users_provider=lambda:users,
            membership_provider=self.store.roles_for,
            trusted_issuer='atlasquant.local', token_audience='library',
            attestation_issuer='atlasquant-library',signing_key=b'k'*32,
            clock=lambda:now)
        self.assertEqual(host._lookup_roles('reader.1','T-A','LIBRARY'),('LIBRARY_READER',))
        self.db.cur.rows=[]
        with self.assertRaises(AuthorizationDenied):host._lookup_roles('reader.1','T-A','LIBRARY')

if __name__=='__main__':unittest.main()
