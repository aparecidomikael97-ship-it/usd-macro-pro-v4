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


class PrincipalBoundSandboxTests(unittest.TestCase):
    """Offline V2 tests. No migration, user provisioning or public route."""

    def setUp(self):
        from atlasquant_aion_library_principal_acl_sandbox import (
            CurrentPrincipal, PrincipalBoundPostgresMembership,
        )
        self.Principal = CurrentPrincipal
        self.issuer = "trusted.local"
        self.subject = "principal-old-0001"
        self.generation_a = "a" * 32
        self.generation_b = "b" * 32
        self.subject_b = "principal-new-0002"
        self.identity = CurrentPrincipal("reader.1", self.issuer, self.subject,
                                         self.generation_a, True)
        self.grants = {}
        self.connections = []
        self.on_fetch = lambda: None
        fixture = self

        class Cursor:
            def __init__(self):
                self.calls = []
                self.params = None
                self.closed = False

            def execute(self, sql, params=None):
                self.calls.append((sql, params))
                if params is not None:
                    self.params = params

            def fetchmany(self, size):
                fixture.on_fetch()
                return fixture.grants.get(self.params, ())[:size]

            def close(self):
                self.closed = True

        class Conn:
            autocommit = False
            def __init__(self):
                self.cur = Cursor()
                self.rolled = False
                self.closed = False

            def cursor(self):
                return self.cur

            def rollback(self):
                self.rolled = True

            def close(self):
                self.closed = True

        def connect():
            conn = Conn()
            fixture.connections.append(conn)
            return conn

        self.adapter = PrincipalBoundPostgresMembership(
            connect=connect, current_principal=lambda: self.identity,
        )

    def key(self, *, issuer=None, subject=None, generation=None,
            username="reader.1", tenant="T-A", domain="LIBRARY"):
        return (
            issuer or self.issuer, subject or self.subject,
            generation or self.generation_a, username, tenant, domain,
        )

    def grant(self, *, key=None, rows=(("LIBRARY_READER", True, None),)):
        self.grants[self.key() if key is None else key] = rows

    def read(self, *, tenant="T-A", domain="LIBRARY"):
        return self.adapter.roles_for("reader.1", tenant, domain)

    def test_v2_requires_durable_principal_and_no_username_only_fallback(self):
        # An old V1 username grant cannot be used by the V2 reader.
        self.grants[("reader.1", "T-A", "LIBRARY")] = (
            ("LIBRARY_READER", True, None),
        )
        self.assertEqual(self.read(), ())
        self.assertEqual(len(self.connections), 1)
        sql_params = self.connections[-1].cur.calls[1][1]
        self.assertEqual(sql_params, self.key())
        self.assertTrue(self.connections[-1].closed)
        self.assertTrue(self.connections[-1].rolled)

    def test_recreated_same_username_never_inherits_old_principal_acl(self):
        self.grant()
        self.assertEqual(self.read(), ("LIBRARY_READER",))
        self.identity = self.Principal(
            "reader.1", self.issuer, self.subject_b, self.generation_b, True
        )
        self.assertEqual(self.read(), ())
        self.assertEqual(self.connections[-1].cur.calls[1][1],
                         self.key(subject=self.subject_b,
                                  generation=self.generation_b))
        self.assertEqual(len(self.connections), 2)

    def test_reused_issuer_and_subject_with_new_generation_is_denied(self):
        self.grant()
        self.identity = self.Principal(
            "reader.1", self.issuer, self.subject, self.generation_b, True
        )
        self.assertEqual(self.read(), ())

    def test_regrant_to_new_principal_is_explicit_and_scoped(self):
        self.grant()
        self.identity = self.Principal(
            "reader.1", self.issuer, self.subject_b, self.generation_b, True
        )
        self.assertEqual(self.read(), ())
        self.grant(key=self.key(subject=self.subject_b,
                                generation=self.generation_b))
        self.assertEqual(self.read(), ("LIBRARY_READER",))
        self.assertEqual(self.read(tenant="T-B"), ())
        self.assertEqual(self.read(domain="NEGOCIOS"), ())

    def test_same_durable_account_may_reauthenticate_without_regrant(self):
        # Credential rotation belongs to the trusted identity registry. The
        # stable principal ID/generation must remain unchanged for this account.
        self.grant()
        self.assertEqual(self.read(), ("LIBRARY_READER",))
        self.assertEqual(self.read(), ("LIBRARY_READER",))
        self.assertEqual(len(self.connections), 2)

    def test_account_deleted_during_query_fails_closed(self):
        self.grant()
        self.on_fetch = lambda: setattr(
            self, "identity", self.Principal(
                "reader.1", self.issuer, self.subject_b, self.generation_b, True
            )
        )
        with self.assertRaises(AuthorizationDenied):
            self.read()
        self.assertTrue(self.connections[-1].closed)
        self.assertTrue(self.connections[-1].rolled)

    def test_deactivated_registry_principal_denied_before_sql(self):
        self.identity = self.Principal(
            "reader.1", self.issuer, self.subject, self.generation_a, False
        )
        with self.assertRaises(AuthorizationDenied):
            self.read()
        self.assertFalse(self.connections)

    def test_missing_or_malformed_registry_identity_denied(self):
        for bad in (
            None,
            {"username": "reader.1", "issuer": self.issuer},
            self.Principal("reader.1", self.issuer, self.subject, "bad", True),
            self.Principal("reader.2", self.issuer, self.subject,
                           self.generation_a, True),
            self.Principal("reader.1", self.issuer, self.subject,
                           self.generation_a, 1),
        ):
            with self.subTest(value=repr(bad)):
                self.identity = bad
                with self.assertRaises(AuthorizationDenied):
                    self.read()
        self.assertFalse(self.connections)

    def test_revocation_and_new_worker_recheck_fresh_rows(self):
        self.grant()
        self.assertEqual(self.read(), ("LIBRARY_READER",))
        self.grant(rows=(("LIBRARY_READER", False, 2000000000),))
        self.assertEqual(self.read(), ())
        self.assertEqual(len(self.connections), 2)

    def test_invalid_or_poisoned_roles_fail_closed(self):
        for rows in (
            (("GLOBAL_ADMIN", True, None),),
            (("LIBRARY_READER", True, None),) * 2,
            (("LIBRARY_READER", True, 123),),
            (("LIBRARY_READER", False, None),),
            (("LIBRARY_READER", True, None),) * 4,
        ):
            with self.subTest(rows=rows):
                self.grant(rows=rows)
                with self.assertRaises(AuthorizationDenied):
                    self.read()

    def test_existing_host_with_v2_provider_denies_recreated_real_login(self):
        from atlasquant_access_control import AccessUser, authenticate, hash_password
        from atlasquant_aion_library_host_access import AtlasQuantLibraryHostAccess
        now = 2_000_000_000
        old_pass, new_pass = "SyntheticV2OldPassword#A", "SyntheticV2NewPassword#B"
        old_hash = hash_password(old_pass, salt=b"z" * 16, iterations=200_000)
        new_hash = hash_password(new_pass, salt=b"y" * 16, iterations=200_000)
        users = {"reader.1": AccessUser("reader.1", "USER", old_hash)}
        old = authenticate("reader.1", old_pass, users)
        self.assertIsNotNone(old)
        access = {"allowed": True, "mode": "AUTHENTICATED", "role": "USER",
                  "session": dict(old, authenticated_at=now-10, last_seen=now-1)}
        host = AtlasQuantLibraryHostAccess(
            access_provider=lambda: access,
            users_provider=lambda: users,
            membership_provider=self.adapter.roles_for,
            trusted_issuer="atlasquant.local", token_audience="library",
            attestation_issuer="atlasquant-library", signing_key=b"k" * 32,
            clock=lambda: now,
        )
        self.grant()
        self.assertEqual(host._lookup_roles("reader.1", "T-A", "LIBRARY"),
                         ("LIBRARY_READER",))
        # Deprovision old account; re-create the SAME username, with a
        # different credential and a separate immutable account generation.
        users["reader.1"] = AccessUser("reader.1", "USER", new_hash)
        fresh = authenticate("reader.1", new_pass, users)
        self.assertIsNotNone(fresh)
        access["session"] = dict(fresh, authenticated_at=now-1, last_seen=now)
        self.identity = self.Principal(
            "reader.1", self.issuer, self.subject_b, self.generation_b, True
        )
        with self.assertRaises(AuthorizationDenied):
            host._lookup_roles("reader.1", "T-A", "LIBRARY")
        self.grant(key=self.key(subject=self.subject_b,
                                generation=self.generation_b))
        self.assertEqual(host._lookup_roles("reader.1", "T-A", "LIBRARY"),
                         ("LIBRARY_READER",))

    def test_v2_schema_is_separate_and_select_only_no_legacy_auto_migration(self):
        from atlasquant_aion_library_principal_acl_sandbox import (
            MIGRATION_PRINCIPAL_ACL_V2, _SELECT,
        )
        self.assertIn("CREATE TABLE aion_library_tenant_acl_principal_v2",
                      MIGRATION_PRINCIPAL_ACL_V2)
        self.assertIn("account_generation CHAR(32) NOT NULL",
                      MIGRATION_PRINCIPAL_ACL_V2)
        self.assertIn("PRIMARY KEY(principal_issuer, principal_subject, account_generation",
                      MIGRATION_PRINCIPAL_ACL_V2)
        self.assertIn("AND account_generation=%s AND username=%s", _SELECT)
        self.assertNotIn("INSERT ", _SELECT)
        self.assertNotIn("UPDATE ", _SELECT)


class PersistentPrincipalRegistrySandboxTests(unittest.TestCase):
    """Offline persistent-registry contract; never mints durable identities."""

    def setUp(self):
        from atlasquant_aion_library_principal_registry_sandbox import (
            PostgresPrincipalRegistry, VerifiedHostAccount,
        )
        self.Verified = VerifiedHostAccount
        self.account = VerifiedHostAccount(
            username="reader.1", issuer="trusted.local",
            subject="principal-old-0001", account_generation="a" * 32,
            credential_fingerprint="c" * 24, active=True,
        )
        self.rows = [("reader.1", "c" * 24, True, None)]
        self.fail_at = None
        self.on_fetch = lambda: None
        self.connections = []
        owner = self

        class RegistryCursor:
            closed = False
            def __init__(self):
                self.calls = []

            def execute(self, sql, params=None):
                self.calls.append((sql, params))
                if owner.fail_at == "sql":
                    raise RuntimeError("SECRET-REGISTRY-CONNECTION")

            def fetchmany(self, limit):
                owner.on_fetch()
                if owner.fail_at == "fetch":
                    raise RuntimeError("SECRET-REGISTRY-CONNECTION")
                return owner.rows[:limit]

            def close(self):
                self.closed = True

        class RegistryDB:
            autocommit = False
            def __init__(self):
                self.cur = RegistryCursor()
                self.closed = False
                self.rolled = False

            def cursor(self):
                return self.cur

            def rollback(self):
                self.rolled = True

            def close(self):
                self.closed = True

        def connect():
            instance = RegistryDB()
            owner.connections.append(instance)
            return instance

        self.connect = connect
        self.registry = PostgresPrincipalRegistry(
            connect=self.connect, verified_host_account=lambda: self.account,
        )

    def read(self):
        return self.registry.current_principal()

    def test_registry_reads_exact_persistent_principal_not_username_lookup(self):
        identity = self.read()
        self.assertEqual(
            (identity.username, identity.issuer, identity.subject,
             identity.account_generation, identity.active),
            ("reader.1", "trusted.local", "principal-old-0001", "a" * 32, True),
        )
        conn = self.connections[-1]
        self.assertIn("READ COMMITTED, READ ONLY", conn.cur.calls[0][0])
        self.assertEqual(
            conn.cur.calls[1][1],
            ("trusted.local", "principal-old-0001", "a" * 32),
        )
        self.assertTrue(conn.closed and conn.rolled and conn.cur.closed)

    def test_registry_missing_or_duplicate_row_denied(self):
        for rows in ([], self.rows * 2):
            with self.subTest(rows=rows):
                self.rows = rows
                with self.assertRaises(AuthorizationDenied):
                    self.read()
        self.assertTrue(all(c.closed and c.rolled for c in self.connections))

    def test_registry_inactive_retired_and_malformed_row_denied(self):
        for row in (
            ("reader.1", "c" * 24, False, 2000000000),
            ("reader.1", "c" * 24, True, 2000000000),
            ("reader.1", "c" * 24, False, None),
            ("reader.2", "c" * 24, True, None),
            ("reader.1", "d" * 24, True, None),
            ("reader.1", "c" * 24, 1, None),
            ("reader.1", "not-fingerprint", True, None),
            ("reader.1", "c" * 24, True),
        ):
            with self.subTest(row=row):
                self.rows = [row]
                with self.assertRaises(AuthorizationDenied):
                    self.read()

    def test_invalid_untrusted_identity_denied_before_sql(self):
        for invalid in (
            None,
            {"username": "reader.1"},
            self.Verified("reader.1", "trusted.local", "principal-old-0001",
                          "a" * 32, "bad", True),
            self.Verified("reader.1", "trusted.local", "principal-old-0001",
                          "a" * 32, "c" * 24, False),
            self.Verified("Reader.1", "trusted.local", "principal-old-0001",
                          "a" * 32, "c" * 24, True),
            self.Verified("reader.1", "trusted.local", "principal-old-0001",
                          "a" * 32, "c" * 24, 1),
        ):
            with self.subTest(identity=repr(invalid)):
                self.account = invalid
                with self.assertRaises(AuthorizationDenied):
                    self.read()
        self.assertEqual(self.connections, [])

    def test_registry_rejects_identity_switch_mid_query(self):
        self.on_fetch = lambda: setattr(
            self, "account", self.Verified(
                "reader.1", "trusted.local", "principal-new-0002",
                "b" * 32, "d" * 24, True,
            )
        )
        with self.assertRaises(AuthorizationDenied):
            self.read()
        self.assertTrue(self.connections[-1].closed)

    def test_registry_rotation_requires_fresh_privileged_binding_not_regrant(self):
        old = self.read()
        self.account = self.Verified(
            "reader.1", "trusted.local", "principal-old-0001",
            "a" * 32, "d" * 24, True,
        )
        with self.assertRaises(AuthorizationDenied):
            self.read()
        # In a real deployment only a separately audited privileged identity
        # control plane would update the registry binding atomically.
        self.rows = [("reader.1", "d" * 24, True, None)]
        rotated = self.read()
        self.assertEqual(rotated, old)

    def test_recreation_cannot_reuse_retired_identity_or_old_binding(self):
        old = self.read()
        self.account = self.Verified(
            "reader.1", "trusted.local", "principal-new-0002",
            "b" * 32, "d" * 24, True,
        )
        # Simulate the DB response for an old account: changed ID/generation
        # cannot be authenticated solely via username or old password binding.
        with self.assertRaises(AuthorizationDenied):
            self.read()
        # On the new principal's explicit row the lookup is distinct.
        self.rows = [("reader.1", "d" * 24, True, None)]
        fresh = self.read()
        self.assertNotEqual(
            (fresh.subject, fresh.account_generation),
            (old.subject, old.account_generation),
        )

    def test_registry_failure_is_fail_closed_and_never_leaks_db_errors(self):
        self.fail_at = "fetch"
        with self.assertRaises(AuthorizationDenied) as cm:
            self.read()
        self.assertNotIn("SECRET-REGISTRY", str(cm.exception))
        self.assertTrue(self.connections[-1].closed)

    def test_registry_configuration_and_autocommit_denied(self):
        from atlasquant_aion_library_principal_registry_sandbox import (
            PostgresPrincipalRegistry,
        )
        with self.assertRaises(AuthorizationDenied):
            PostgresPrincipalRegistry(
                connect=None, verified_host_account=lambda: self.account,
            )
        db = self.connect()
        db.autocommit = True
        self.registry = PostgresPrincipalRegistry(
            connect=lambda: db, verified_host_account=lambda: self.account,
        )
        with self.assertRaises(AuthorizationDenied):
            self.read()
        self.assertTrue(db.closed)

    def test_registry_to_acl_v2_adapter_revalidates_identity(self):
        from atlasquant_aion_library_principal_acl_sandbox import (
            PrincipalBoundPostgresMembership,
        )
        registry = self.registry
        grants = {
            ("trusted.local", "principal-old-0001", "a" * 32,
             "reader.1", "T-A", "LIBRARY"): (("LIBRARY_READER", True, None),)
        }

        def acl_connect():
            scope = ACLFakeDB()
            def fetchmany(limit):
                params = scope.cur.calls[1][1]
                return grants.get(params, ())[:limit]
            scope.cur.fetchmany = fetchmany
            return scope

        acl = PrincipalBoundPostgresMembership(
            connect=acl_connect, current_principal=registry.current_principal,
        )
        self.assertEqual(acl.roles_for("reader.1", "T-A", "LIBRARY"),
                         ("LIBRARY_READER",))
        self.account = self.Verified(
            "reader.1", "trusted.local", "principal-new-0002",
            "b" * 32, "d" * 24, True,
        )
        # Registry denies B until independently persisted and bound.
        with self.assertRaises(AuthorizationDenied):
            acl.roles_for("reader.1", "T-A", "LIBRARY")
        self.rows = [("reader.1", "d" * 24, True, None)]
        self.assertEqual(acl.roles_for("reader.1", "T-A", "LIBRARY"), ())
        grants[("trusted.local", "principal-new-0002", "b" * 32,
                "reader.1", "T-A", "LIBRARY")] = (
                    ("LIBRARY_READER", True, None),
                )
        self.assertEqual(acl.roles_for("reader.1", "T-A", "LIBRARY"),
                         ("LIBRARY_READER",))


class ExternalRetirementFenceSandboxTests(unittest.TestCase):
    """Offline independent authority port; intentionally no production source."""

    def setUp(self):
        from atlasquant_aion_library_principal_acl_sandbox import CurrentPrincipal
        from atlasquant_aion_library_external_retirement_fence_sandbox import (
            ExternalAuthorityHead, ExternalRetirementFence,
        )
        self.Principal = CurrentPrincipal
        self.Head = ExternalAuthorityHead
        self.Fence = ExternalRetirementFence
        self.a = CurrentPrincipal(
            "reader.1", "trusted.local", "principal-old-0001", "a" * 32, True,
        )
        self.b = CurrentPrincipal(
            "reader.1", "trusted.local", "principal-new-0002", "b" * 32, True,
        )
        self.registry = self.a
        self.head = self.head_for(self.a, revision=7)
        self.floor = 7
        self.calls = {"registry": 0, "head": 0, "floor": 0}
        self.on_registry = lambda: None
        self.on_head = lambda: None
        self.on_floor = lambda: None
        self.reader = self.make_fence()

    def head_for(self, p, *, revision, active=True):
        return self.Head(
            p.issuer, p.username, p.subject, p.account_generation,
            active, revision,
        )

    def registry_current(self):
        self.calls["registry"] += 1
        self.on_registry()
        return self.registry

    def current_external(self, issuer, username):
        self.assertEqual((issuer, username), ("trusted.local", "reader.1"))
        self.calls["head"] += 1
        self.on_head()
        return self.head

    def external_floor(self, issuer, username):
        self.assertEqual((issuer, username), ("trusted.local", "reader.1"))
        self.calls["floor"] += 1
        self.on_floor()
        return self.floor

    def make_fence(self):
        return self.Fence(
            registry_principal=self.registry_current,
            current_authority=self.current_external,
            minimum_revision=self.external_floor,
        )

    def test_current_external_head_and_independent_floor_allow_same_identity(self):
        self.assertEqual(self.reader.current_principal(), self.a)
        self.assertEqual(self.calls, {"registry": 2, "head": 2, "floor": 2})

    def test_external_retirement_denies_even_if_old_db_still_says_active(self):
        self.head = self.head_for(self.a, revision=8, active=False)
        self.floor = 8
        with self.assertRaises(AuthorizationDenied):
            self.reader.current_principal()

    def test_restored_old_account_denied_after_external_replacement(self):
        self.head = self.head_for(self.b, revision=8)
        self.floor = 8
        # Simulate stale/restored registry reporting A despite current B.
        with self.assertRaises(AuthorizationDenied):
            self.reader.current_principal()
        self.registry = self.b
        self.assertEqual(self.reader.current_principal(), self.b)

    def test_stale_external_head_lower_than_independent_floor_denied(self):
        # A previously signed/archived head MUST NOT override the external
        # durable monotonic floor. Both callbacks are independently trusted.
        self.floor = 8
        with self.assertRaises(AuthorizationDenied):
            self.reader.current_principal()

    def test_unavailable_authority_or_floor_denied_not_username_fallback(self):
        def failed():
            raise RuntimeError("EXTERNAL-RETIREMENT-SECRET")
        for change in ("current_authority", "minimum_revision"):
            with self.subTest(callback=change):
                kwargs = dict(
                    registry_principal=self.registry_current,
                    current_authority=self.current_external,
                    minimum_revision=self.external_floor,
                )
                kwargs[change] = lambda *args: failed()
                fence = self.Fence(**kwargs)
                with self.assertRaises(AuthorizationDenied) as err:
                    fence.current_principal()
                self.assertNotIn("EXTERNAL-RETIREMENT-SECRET", str(err.exception))

    def test_head_change_during_registry_resolution_denied(self):
        self.on_registry = lambda: setattr(
            self, "head", self.head_for(self.b, revision=8),
        ) if self.calls["registry"] == 2 else None
        with self.assertRaises(AuthorizationDenied):
            self.reader.current_principal()

    def test_external_minimum_advances_during_resolution_denied(self):
        self.on_floor = lambda: setattr(self, "floor", 8) \
            if self.calls["floor"] == 2 else None
        with self.assertRaises(AuthorizationDenied):
            self.reader.current_principal()

    def test_registry_identity_switch_during_resolution_denied(self):
        self.on_registry = lambda: setattr(self, "registry", self.b) \
            if self.calls["registry"] == 2 else None
        with self.assertRaises(AuthorizationDenied):
            self.reader.current_principal()

    def test_malformed_external_heads_and_floor_fail_closed(self):
        cases = (
            (None, 7),
            (dict(username="reader.1"), 7),
            (self.Head("wrong.local", "reader.1", self.a.subject,
                       self.a.account_generation, True, 7), 7),
            (self.Head("trusted.local", "reader.1", self.a.subject,
                       self.a.account_generation, 1, 7), 7),
            (self.head_for(self.a, revision=0), 0),
            (self.head_for(self.a, revision=True), 7),
            (self.head, True),
            (self.head, -1),
            (self.head, 8),
        )
        for head, floor in cases:
            with self.subTest(head=head, floor=floor):
                self.head, self.floor = head, floor
                with self.assertRaises(AuthorizationDenied):
                    self.reader.current_principal()

    def test_inactive_registry_and_untrusted_configuration_denied(self):
        with self.assertRaises(AuthorizationDenied):
            self.Fence(
                registry_principal=None,
                current_authority=self.current_external,
                minimum_revision=self.external_floor,
            )
        self.registry = self.Principal(
            self.a.username, self.a.issuer, self.a.subject,
            self.a.account_generation, False,
        )
        with self.assertRaises(AuthorizationDenied):
            self.reader.current_principal()
        self.assertEqual(self.calls["head"], 0)


class SeparateDatabaseWitnessSandboxTests(unittest.TestCase):
    """Offline SELECT-only witness adapter: the floor is deliberately separate."""

    def setUp(self):
        from atlasquant_aion_library_witness_pg_sandbox import (
            SeparateDatabaseWitnessReader,
        )
        self.rows = [
            ("principal-new-0002", "b" * 32, True, 8),
            ("principal-old-0001", "a" * 32, False, 7),
        ]
        self.connections = []
        self.fail_at = None
        fixture = self

        class Cursor:
            def __init__(self):
                self.calls = []
                self.closed = False

            def execute(self, query, params=None):
                self.calls.append((query, params))
                if fixture.fail_at == "execute":
                    raise RuntimeError("SYNTHETIC-WITNESS-SECRET")

            def fetchmany(self, amount):
                if fixture.fail_at == "fetch":
                    raise RuntimeError("SYNTHETIC-WITNESS-SECRET")
                return fixture.rows[:amount]

            def close(self):
                self.closed = True

        class DB:
            autocommit = False
            def __init__(self):
                self.cur = Cursor()
                self.rolled = False
                self.closed = False

            def cursor(self):
                return self.cur

            def rollback(self):
                self.rolled = True

            def close(self):
                self.closed = True

        def connect():
            db = DB()
            fixture.connections.append(db)
            return db

        self.connect = connect
        self.reader = SeparateDatabaseWitnessReader(connect=connect)

    def test_witness_fetches_latest_head_by_exact_issuer_username(self):
        current = self.reader.current_head("trusted.local", "reader.1")
        self.assertEqual(
            (current.subject, current.account_generation,
             current.active, current.revision),
            ("principal-new-0002", "b" * 32, True, 8),
        )
        db = self.connections[-1]
        self.assertIn("READ COMMITTED, READ ONLY", db.cur.calls[0][0])
        self.assertEqual(db.cur.calls[1][1], ("trusted.local", "reader.1"))
        self.assertTrue(db.rolled and db.closed and db.cur.closed)

    def test_witness_missing_out_of_order_or_corrupt_history_denied(self):
        for rows in (
            [],
            self.rows[::-1],
            [self.rows[0], self.rows[0]],
            [("principal-new-0002", "b" * 32, 1, 8)],
            [("principal-new-0002", "bad", True, 8)],
            [("principal-new-0002", "b" * 32, True, True)],
            [("principal-new-0002", "b" * 32, True, 0)],
            [("principal-new-0002", "b" * 32, True)],
        ):
            with self.subTest(rows=rows):
                self.rows = rows
                with self.assertRaises(AuthorizationDenied):
                    self.reader.current_head("trusted.local", "reader.1")
        self.assertTrue(all(x.closed and x.rolled for x in self.connections))

    def test_witness_rejects_invalid_scope_before_opening_database(self):
        for issuer, name in (
            ("", "reader.1"), ("Bad Issuer", "reader.1"),
            ("trusted.local", ""), ("trusted.local", "Reader.1"),
            ("trusted.local", "reader;drop"), (None, "reader.1"),
        ):
            with self.subTest(issuer=issuer, name=name):
                with self.assertRaises(AuthorizationDenied):
                    self.reader.current_head(issuer, name)
        self.assertEqual(self.connections, [])

    def test_witness_db_failure_never_leaks_details(self):
        for stage in ("execute", "fetch"):
            with self.subTest(stage=stage):
                self.fail_at = stage
                with self.assertRaises(AuthorizationDenied) as err:
                    self.reader.current_head("trusted.local", "reader.1")
                self.assertNotIn("SYNTHETIC-WITNESS-SECRET", str(err.exception))
                self.assertTrue(self.connections[-1].closed)

    def test_witness_autocommit_and_missing_factory_fail_closed(self):
        from atlasquant_aion_library_witness_pg_sandbox import (
            SeparateDatabaseWitnessReader,
        )
        with self.assertRaises(AuthorizationDenied):
            SeparateDatabaseWitnessReader(connect=None)
        db = self.connect()
        db.autocommit = True
        adapter = SeparateDatabaseWitnessReader(connect=lambda: db)
        with self.assertRaises(AuthorizationDenied):
            adapter.current_head("trusted.local", "reader.1")
        self.assertTrue(db.closed)

    def test_witness_ddl_only_documents_logical_separation_not_offsite(self):
        from atlasquant_aion_library_witness_pg_sandbox import (
            MIGRATION_WITNESS_PG, _SELECT,
        )
        self.assertIn("CREATE TABLE aion_library_witness_history_sandbox",
                      MIGRATION_WITNESS_PG)
        self.assertIn("PRIMARY KEY(principal_issuer, username, revision)",
                      MIGRATION_WITNESS_PG)
        self.assertIn("ORDER BY revision DESC LIMIT 2", _SELECT)
        self.assertNotIn("UPDATE ", _SELECT)
        self.assertNotIn("INSERT ", _SELECT)

if __name__=='__main__':unittest.main()
