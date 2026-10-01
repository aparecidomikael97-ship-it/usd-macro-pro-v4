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


@unittest.skipUnless(ENABLED, "strict ephemeral PostgreSQL V2 principal drill required")
class PrincipalBoundPostgreSQLTests(unittest.TestCase):
    """Real PG sandbox: no V1 migration, no auth registry or production data."""

    @classmethod
    def setUpClass(cls):
        from atlasquant_aion_library_principal_acl_sandbox import (
            MIGRATION_PRINCIPAL_ACL_V2,
        )
        import psycopg
        cls.pg = psycopg
        cls.reader_dsn = (
            "postgresql://aion_acl_ci_principal_reader:synthetic_principal_reader_only"
            "@localhost:5432/aion_library_sandbox"
        )
        with cls.pg.connect(EXPECTED, autocommit=True) as db:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT to_regclass('public.aion_library_tenant_acl_principal_v2')"
                )
                if cur.fetchone()[0] is None:
                    cur.execute(MIGRATION_PRINCIPAL_ACL_V2)
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname=%s",
                    ("aion_acl_ci_principal_reader",),
                )
                if cur.fetchone() is None:
                    cur.execute(
                        "CREATE ROLE aion_acl_ci_principal_reader LOGIN "
                        "PASSWORD 'synthetic_principal_reader_only'"
                    )
                cur.execute(
                    "GRANT CONNECT ON DATABASE aion_library_sandbox "
                    "TO aion_acl_ci_principal_reader"
                )
                cur.execute(
                    "GRANT USAGE ON SCHEMA public TO aion_acl_ci_principal_reader"
                )
                cur.execute(
                    "GRANT SELECT ON aion_library_tenant_acl_principal_v2 "
                    "TO aion_acl_ci_principal_reader"
                )

    def setUp(self):
        from atlasquant_aion_library_principal_acl_sandbox import (
            CurrentPrincipal, PrincipalBoundPostgresMembership,
        )
        self.Principal = CurrentPrincipal
        self.subject_a = "principal-old-0001"
        self.subject_b = "principal-new-0002"
        self.identity = CurrentPrincipal(
            "reader.1", "trusted.local", self.subject_a, "a" * 32, True
        )
        with self.pg.connect(EXPECTED, autocommit=True) as db:
            db.execute("TRUNCATE TABLE aion_library_tenant_acl_principal_v2")
        self.reader = PrincipalBoundPostgresMembership(
            connect=lambda: self.pg.connect(self.reader_dsn),
            current_principal=lambda: self.identity,
        )

    def grant(self, *, subject="principal-old-0001", generation="a" * 32,
              tenant="T-A", domain="LIBRARY", role="LIBRARY_READER"):
        with self.pg.connect(EXPECTED) as db:
            db.execute(
                """INSERT INTO aion_library_tenant_acl_principal_v2
                 (principal_issuer,principal_subject,account_generation,
                  username,tenant_id,domain_id,library_role)
                 VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                ("trusted.local", subject, generation, "reader.1",
                 tenant, domain, role),
            )

    def read(self, *, tenant="T-A", domain="LIBRARY"):
        return self.reader.roles_for("reader.1", tenant, domain)

    def test_real_pg_recreated_username_does_not_inherit_old_acl(self):
        self.grant()
        self.assertEqual(self.read(), ("LIBRARY_READER",))
        self.identity = self.Principal(
            "reader.1", "trusted.local", self.subject_b, "b" * 32, True
        )
        self.assertEqual(self.read(), ())
        self.assertEqual(self.read(tenant="T-B"), ())

    def test_real_pg_same_subject_new_generation_does_not_inherit(self):
        self.grant()
        self.identity = self.Principal(
            "reader.1", "trusted.local", self.subject_a, "b" * 32, True
        )
        self.assertEqual(self.read(), ())

    def test_real_pg_explicit_new_grant_is_tenant_domain_scoped(self):
        self.grant()
        self.identity = self.Principal(
            "reader.1", "trusted.local", self.subject_b, "b" * 32, True
        )
        self.assertEqual(self.read(), ())
        self.grant(subject=self.subject_b, generation="b" * 32)
        self.assertEqual(self.read(), ("LIBRARY_READER",))
        self.assertEqual(self.read(tenant="T-B"), ())
        self.assertEqual(self.read(domain="NEGOCIOS"), ())

    def test_real_pg_revocation_visible_to_second_worker(self):
        self.grant()
        self.assertEqual(self.read(), ("LIBRARY_READER",))
        with self.pg.connect(EXPECTED) as db:
            db.execute(
                """UPDATE aion_library_tenant_acl_principal_v2
                   SET active=FALSE, revoked_at_unix=2000000000
                   WHERE username='reader.1' AND tenant_id='T-A'"""
            )
        from atlasquant_aion_library_principal_acl_sandbox import (
            PrincipalBoundPostgresMembership,
        )
        second = PrincipalBoundPostgresMembership(
            connect=lambda: self.pg.connect(self.reader_dsn),
            current_principal=lambda: self.identity,
        )
        self.assertEqual(second.roles_for("reader.1", "T-A", "LIBRARY"), ())
        self.assertEqual(self.read(), ())

    def test_real_pg_principal_reader_cannot_update_acl(self):
        self.grant()
        with self.pg.connect(self.reader_dsn) as db:
            with self.assertRaises(self.pg.errors.InsufficientPrivilege):
                db.execute(
                    """UPDATE aion_library_tenant_acl_principal_v2
                       SET active=FALSE WHERE username='reader.1'"""
                )

    def test_real_pg_registry_replacement_during_read_is_denied(self):
        self.grant()
        from atlasquant_aion_library_principal_acl_sandbox import (
            PrincipalBoundPostgresMembership,
        )
        counter = {"calls": 0}
        def current():
            counter["calls"] += 1
            if counter["calls"] == 2:
                self.identity = self.Principal(
                    "reader.1", "trusted.local", self.subject_b, "b" * 32, True
                )
            return self.identity
        reader = PrincipalBoundPostgresMembership(
            connect=lambda: self.pg.connect(self.reader_dsn),
            current_principal=current,
        )
        with self.assertRaises(AuthorizationDenied):
            reader.roles_for("reader.1", "T-A", "LIBRARY")


@unittest.skipUnless(ENABLED, "strict ephemeral PostgreSQL registry integration required")
class PersistentRegistryPostgreSQLTests(unittest.TestCase):
    """Opt-in actual PostgreSQL registry + principal ACL, synthetic roles only."""

    @classmethod
    def setUpClass(cls):
        from atlasquant_aion_library_principal_registry_sandbox import (
            MIGRATION_PRINCIPAL_REGISTRY,
        )
        from atlasquant_aion_library_principal_acl_sandbox import (
            MIGRATION_PRINCIPAL_ACL_V2,
        )
        import psycopg
        cls.pg = psycopg
        cls.reader_dsn = (
            "postgresql://aion_principal_registry_ci_reader:synthetic_registry_only"
            "@localhost:5432/aion_library_sandbox"
        )
        with cls.pg.connect(EXPECTED, autocommit=True) as db:
            for table, ddl in (
                ("aion_library_principal_registry_sandbox",
                 MIGRATION_PRINCIPAL_REGISTRY),
                ("aion_library_tenant_acl_principal_v2",
                 MIGRATION_PRINCIPAL_ACL_V2),
            ):
                with db.cursor() as cur:
                    cur.execute("SELECT to_regclass(%s)", ("public." + table,))
                    if cur.fetchone()[0] is None:
                        cur.execute(ddl)
            with db.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname=%s",
                    ("aion_principal_registry_ci_reader",),
                )
                if cur.fetchone() is None:
                    cur.execute(
                        "CREATE ROLE aion_principal_registry_ci_reader LOGIN "
                        "PASSWORD 'synthetic_registry_only'"
                    )
                cur.execute(
                    "GRANT CONNECT ON DATABASE aion_library_sandbox "
                    "TO aion_principal_registry_ci_reader"
                )
                cur.execute(
                    "GRANT USAGE ON SCHEMA public TO aion_principal_registry_ci_reader"
                )
                cur.execute(
                    "GRANT SELECT ON aion_library_principal_registry_sandbox,"
                    "aion_library_tenant_acl_principal_v2 "
                    "TO aion_principal_registry_ci_reader"
                )

    def setUp(self):
        from atlasquant_aion_library_principal_registry_sandbox import (
            PostgresPrincipalRegistry, VerifiedHostAccount,
        )
        from atlasquant_aion_library_principal_acl_sandbox import (
            PrincipalBoundPostgresMembership,
        )
        self.Verified = VerifiedHostAccount
        self.account_a = VerifiedHostAccount(
            "reader.1", "trusted.local", "principal-old-0001",
            "a" * 32, "c" * 24, True,
        )
        self.account_b = VerifiedHostAccount(
            "reader.1", "trusted.local", "principal-new-0002",
            "b" * 32, "d" * 24, True,
        )
        self.account = self.account_a
        self.on_verify = lambda: None
        with self.pg.connect(EXPECTED, autocommit=True) as db:
            db.execute(
                "TRUNCATE TABLE aion_library_principal_registry_sandbox,"
                " aion_library_tenant_acl_principal_v2"
            )
        self.make_ports()

    def make_ports(self):
        from atlasquant_aion_library_principal_registry_sandbox import (
            PostgresPrincipalRegistry,
        )
        from atlasquant_aion_library_principal_acl_sandbox import (
            PrincipalBoundPostgresMembership,
        )
        self.registry = PostgresPrincipalRegistry(
            connect=lambda: self.pg.connect(self.reader_dsn),
            verified_host_account=self.get_verified,
        )
        self.acl = PrincipalBoundPostgresMembership(
            connect=lambda: self.pg.connect(self.reader_dsn),
            current_principal=self.registry.current_principal,
        )

    def get_verified(self):
        self.on_verify()
        return self.account

    def enroll(self, identity):
        with self.pg.connect(EXPECTED) as db:
            db.execute(
                """INSERT INTO aion_library_principal_registry_sandbox
                   (principal_issuer,principal_subject,account_generation,
                    username,credential_binding)
                   VALUES (%s,%s,%s,%s,%s)""",
                (identity.issuer, identity.subject, identity.account_generation,
                 identity.username, identity.credential_fingerprint),
            )

    def grant(self, identity):
        with self.pg.connect(EXPECTED) as db:
            db.execute(
                """INSERT INTO aion_library_tenant_acl_principal_v2
                   (principal_issuer,principal_subject,account_generation,
                    username,tenant_id,domain_id,library_role)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (identity.issuer, identity.subject, identity.account_generation,
                 identity.username, "T-A", "LIBRARY", "LIBRARY_READER"),
            )

    def retire(self, identity):
        with self.pg.connect(EXPECTED) as db:
            db.execute(
                """UPDATE aion_library_principal_registry_sandbox
                   SET active=FALSE, retired_at_unix=2000000000
                   WHERE principal_issuer=%s AND principal_subject=%s
                     AND account_generation=%s""",
                (identity.issuer, identity.subject, identity.account_generation),
            )

    def roles(self):
        return self.acl.roles_for("reader.1", "T-A", "LIBRARY")

    def test_real_pg_registry_same_username_recreated_requires_explicit_regrant(self):
        self.enroll(self.account_a)
        self.grant(self.account_a)
        self.assertEqual(self.roles(), ("LIBRARY_READER",))
        self.retire(self.account_a)
        self.account = self.account_b
        # Previous V2 ACL row still exists but is NOT transferable to B.
        with self.assertRaises(AuthorizationDenied):
            self.roles()
        self.enroll(self.account_b)
        self.assertEqual(self.roles(), ())
        self.grant(self.account_b)
        self.assertEqual(self.roles(), ("LIBRARY_READER",))
        self.assertEqual(self.acl.roles_for("reader.1", "T-B", "LIBRARY"), ())

    def test_real_pg_registry_retired_principal_denied_even_if_old_acl_is_active(self):
        self.enroll(self.account_a)
        self.grant(self.account_a)
        self.assertEqual(self.roles(), ("LIBRARY_READER",))
        self.retire(self.account_a)
        with self.assertRaises(AuthorizationDenied):
            self.roles()

    def test_real_pg_registry_password_rotation_requires_authoritative_rebinding(self):
        self.enroll(self.account_a)
        self.grant(self.account_a)
        self.assertEqual(self.roles(), ("LIBRARY_READER",))
        new_credential = self.Verified(
            "reader.1", "trusted.local", "principal-old-0001",
            "a" * 32, "f" * 24, True,
        )
        self.account = new_credential
        with self.assertRaises(AuthorizationDenied):
            self.roles()
        # Privileged test fixture updates only credential binding, not
        # the stable subject/generation or ACL.
        with self.pg.connect(EXPECTED) as db:
            db.execute(
                """UPDATE aion_library_principal_registry_sandbox
                   SET credential_binding=%s
                   WHERE principal_issuer=%s AND principal_subject=%s
                     AND account_generation=%s""",
                ("f" * 24, "trusted.local", "principal-old-0001", "a" * 32),
            )
        self.assertEqual(self.roles(), ("LIBRARY_READER",))

    def test_real_pg_registry_retirement_visible_to_independent_worker(self):
        self.enroll(self.account_a)
        self.grant(self.account_a)
        self.assertEqual(self.roles(), ("LIBRARY_READER",))
        from atlasquant_aion_library_principal_registry_sandbox import (
            PostgresPrincipalRegistry,
        )
        second = PostgresPrincipalRegistry(
            connect=lambda: self.pg.connect(self.reader_dsn),
            verified_host_account=self.get_verified,
        )
        self.assertEqual(second.current_principal().username, "reader.1")
        self.retire(self.account_a)
        for worker in (self.registry, second):
            with self.assertRaises(AuthorizationDenied):
                worker.current_principal()

    def test_real_pg_registry_read_role_cannot_update_or_provision(self):
        self.enroll(self.account_a)
        with self.pg.connect(self.reader_dsn) as db:
            with self.assertRaises(self.pg.errors.InsufficientPrivilege):
                db.execute(
                    """UPDATE aion_library_principal_registry_sandbox
                       SET active=FALSE WHERE username='reader.1'"""
                )
        with self.pg.connect(self.reader_dsn) as db:
            with self.assertRaises(self.pg.errors.InsufficientPrivilege):
                db.execute(
                    """INSERT INTO aion_library_principal_registry_sandbox
                       (principal_issuer,principal_subject,account_generation,
                        username,credential_binding)
                       VALUES ('trusted.local','principal-other-0003',%s,
                               'reader.2',%s)""",
                    ("d" * 32, "f" * 24),
                )

    def test_real_pg_registry_enforces_one_active_generation_per_issuer_username(self):
        self.enroll(self.account_a)
        with self.assertRaises(self.pg.errors.UniqueViolation):
            self.enroll(self.account_b)
        self.retire(self.account_a)
        self.enroll(self.account_b)
        self.account = self.account_b
        self.assertEqual(self.registry.current_principal().subject,
                         self.account_b.subject)

    def test_real_pg_registry_switch_during_live_read_is_denied(self):
        self.enroll(self.account_a)
        calls = {"n": 0}
        def switch():
            calls["n"] += 1
            if calls["n"] == 2:
                self.account = self.account_b
        self.on_verify = switch
        with self.assertRaises(AuthorizationDenied):
            self.registry.current_principal()


    def external_acl(self, shared):
        """The witness/floor are synthetic independent authority ports.

        SQL is real PostgreSQL, but this fixture is NOT a real offsite witness.
        """
        from atlasquant_aion_library_external_retirement_fence_sandbox import (
            ExternalRetirementFence,
        )
        from atlasquant_aion_library_principal_acl_sandbox import (
            PrincipalBoundPostgresMembership,
        )
        fence = ExternalRetirementFence(
            registry_principal=self.registry.current_principal,
            current_authority=lambda issuer, username: shared["head"],
            minimum_revision=lambda issuer, username: shared["floor"],
        )
        return PrincipalBoundPostgresMembership(
            connect=lambda: self.pg.connect(self.reader_dsn),
            current_principal=fence.current_principal,
        )

    def external_head(self, account, *, revision=7, active=True):
        from atlasquant_aion_library_external_retirement_fence_sandbox import (
            ExternalAuthorityHead,
        )
        return ExternalAuthorityHead(
            account.issuer, account.username, account.subject,
            account.account_generation, active, revision,
        )

    def test_real_pg_external_retirement_denies_old_active_registry_and_acl(self):
        self.enroll(self.account_a)
        self.grant(self.account_a)
        shared = {"head": self.external_head(self.account_a),
                  "floor": 7}
        reader = self.external_acl(shared)
        self.assertEqual(reader.roles_for("reader.1", "T-A", "LIBRARY"),
                         ("LIBRARY_READER",))
        # External retirement is newer than this PostgreSQL snapshot. The
        # registry/ACL still say A is active but the independent port vetoes.
        shared["head"] = self.external_head(self.account_a,
                                            revision=8, active=False)
        shared["floor"] = 8
        with self.assertRaises(AuthorizationDenied):
            reader.roles_for("reader.1", "T-A", "LIBRARY")

    def test_real_pg_simulated_old_snapshot_replay_stays_denied(self):
        # Not pg_restore: deliberately rewind only the ephemeral DB fixture.
        # Issue #501 still requires a real offsite witness + pg_dump/pg_restore.
        self.enroll(self.account_a)
        self.grant(self.account_a)
        shared = {"head": self.external_head(self.account_a),
                  "floor": 7}
        reader = self.external_acl(shared)
        self.assertEqual(reader.roles_for("reader.1", "T-A", "LIBRARY"),
                         ("LIBRARY_READER",))
        self.retire(self.account_a)
        self.account = self.account_b
        self.enroll(self.account_b)
        shared["head"] = self.external_head(self.account_b, revision=8)
        shared["floor"] = 8
        self.assertEqual(reader.roles_for("reader.1", "T-A", "LIBRARY"), ())
        # Simulate PostgreSQL being reverted to the exact pre-retirement
        # identity while leaving the old ACL row in place.
        with self.pg.connect(EXPECTED, autocommit=True) as db:
            db.execute("TRUNCATE TABLE aion_library_principal_registry_sandbox")
        self.enroll(self.account_a)
        self.account = self.account_a
        with self.assertRaises(AuthorizationDenied):
            reader.roles_for("reader.1", "T-A", "LIBRARY")
        # Switching to a current B session still cannot access old ACL.
        self.account = self.account_b
        with self.assertRaises(AuthorizationDenied):
            reader.roles_for("reader.1", "T-A", "LIBRARY")
        # Only privileged fixture reconciliation + separate B grant restores.
        self.retire(self.account_a)
        self.enroll(self.account_b)
        self.assertEqual(reader.roles_for("reader.1", "T-A", "LIBRARY"), ())
        self.grant(self.account_b)
        self.assertEqual(reader.roles_for("reader.1", "T-A", "LIBRARY"),
                         ("LIBRARY_READER",))

    def test_real_pg_historical_authority_head_below_external_floor_denied(self):
        self.enroll(self.account_a)
        self.grant(self.account_a)
        shared = {"head": self.external_head(self.account_a, revision=7),
                  "floor": 8}
        with self.assertRaises(AuthorizationDenied):
            self.external_acl(shared).roles_for("reader.1", "T-A", "LIBRARY")

    def test_real_pg_missing_external_authority_denied_without_fallback(self):
        self.enroll(self.account_a)
        self.grant(self.account_a)
        from atlasquant_aion_library_external_retirement_fence_sandbox import (
            ExternalRetirementFence,
        )
        from atlasquant_aion_library_principal_acl_sandbox import (
            PrincipalBoundPostgresMembership,
        )
        fence = ExternalRetirementFence(
            registry_principal=self.registry.current_principal,
            current_authority=lambda issuer, name: (
                (_ for _ in ()).throw(ConnectionError("EXTERNAL-SECRET"))
            ),
            minimum_revision=lambda issuer, name: 7,
        )
        reader = PrincipalBoundPostgresMembership(
            connect=lambda: self.pg.connect(self.reader_dsn),
            current_principal=fence.current_principal,
        )
        with self.assertRaises(AuthorizationDenied) as cm:
            reader.roles_for("reader.1", "T-A", "LIBRARY")
        self.assertNotIn("EXTERNAL-SECRET", str(cm.exception))

    def test_real_pg_external_retirement_during_acl_read_denied(self):
        self.enroll(self.account_a)
        self.grant(self.account_a)
        from atlasquant_aion_library_external_retirement_fence_sandbox import (
            ExternalRetirementFence,
        )
        from atlasquant_aion_library_principal_acl_sandbox import (
            PrincipalBoundPostgresMembership,
        )
        shared = {"head": self.external_head(self.account_a), "floor": 7}
        calls = {"n": 0}
        def latest(issuer, username):
            calls["n"] += 1
            # The first two checks surround the registry read. The third
            # happens after the ACL SQL query and must veto the old role.
            if calls["n"] == 3:
                shared["head"] = self.external_head(
                    self.account_a, revision=8, active=False,
                )
                shared["floor"] = 8
            return shared["head"]
        fence = ExternalRetirementFence(
            registry_principal=self.registry.current_principal,
            current_authority=latest,
            minimum_revision=lambda issuer, username: shared["floor"],
        )
        reader = PrincipalBoundPostgresMembership(
            connect=lambda: self.pg.connect(self.reader_dsn),
            current_principal=fence.current_principal,
        )
        with self.assertRaises(AuthorizationDenied):
            reader.roles_for("reader.1", "T-A", "LIBRARY")

if __name__=='__main__':unittest.main()
