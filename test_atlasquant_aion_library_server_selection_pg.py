"""CI-only full synthetic integration: native login + real PostgreSQL ACL and audit.

Uses exactly the ephemeral localhost PostgreSQL DSN in the PR workflow, with
separate, SELECT-only roles for membership and document inspection. Does not
mount a Streamlit route and must NEVER point at user/production databases.
"""
import os
import unittest
from urllib.parse import urlsplit, urlunsplit

from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from aion_core.library_atomic_store import AtomicLibraryStore, MIGRATION_POSTGRESQL as DOC_DDL
from aion_core.library_foundation import LibraryCatalog
from atlasquant_access_control import AccessUser, authenticate, hash_password
from atlasquant_aion_library_acl_postgres import MIGRATION_POSTGRESQL as ACL_DDL
from atlasquant_aion_library_server_assembly import SandboxLibraryServerReadAssembly
from atlasquant_aion_library_server_selection import SandboxServerSelectedRead
from test_aion_core_library_atomic_store import IK, AK, RK, NOW, make_proofs

DSN = ("postgresql://library_sandbox:synthetic_ci_only_not_for_production"
       "@localhost:5432/aion_library_sandbox")
ENABLED = (os.getenv("CI", "").lower() == "true" and
           os.getenv("AION_LIB_TEST_PG_DSN") == DSN and
           os.getenv("AION_LIB_JOINT_E2E") == "1")


@unittest.skipUnless(ENABLED, "strict synthetic GitHub CI PostgreSQL required")
class JointNativeLoginDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ENABLED:
            return
        try:
            import psycopg
        except ImportError as exc:
            raise unittest.SkipTest("sandbox psycopg driver missing") from exc
        cls.psycopg = psycopg
        cls.password = "OnlySyntheticJointIntegration!"
        cls.password_hash = hash_password(cls.password, salt=b"joint-e2e-salt-26", iterations=200_000)
        with psycopg.connect(DSN, autocommit=True) as db:
            with db.cursor() as cur:
                cur.execute("SELECT to_regclass('public.aion_library_documents')")
                if cur.fetchone()[0] is None:
                    cur.execute(DOC_DDL)
                cur.execute("SELECT to_regclass('public.aion_library_tenant_acl')")
                if cur.fetchone()[0] is None:
                    cur.execute(ACL_DDL)
                for username, password in (("aion_joint_acl_reader", "synthetic_joint_acl"),
                                           ("aion_joint_doc_reader", "synthetic_joint_doc")):
                    # Fixed identifiers, never interpolate caller input in DDL.
                    cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (username,))
                    if cur.fetchone() is None:
                        if username == "aion_joint_acl_reader":
                            cur.execute("CREATE ROLE aion_joint_acl_reader LOGIN PASSWORD 'synthetic_joint_acl'")
                        else:
                            cur.execute("CREATE ROLE aion_joint_doc_reader LOGIN PASSWORD 'synthetic_joint_doc'")
                for role in ("aion_joint_acl_reader", "aion_joint_doc_reader"):
                    cur.execute("GRANT CONNECT ON DATABASE aion_library_sandbox TO " + role)
                    cur.execute("GRANT USAGE ON SCHEMA public TO " + role)
                cur.execute("GRANT SELECT ON aion_library_tenant_acl TO aion_joint_acl_reader")
                cur.execute("GRANT SELECT ON aion_library_documents, "
                            "aion_library_atomic_approval_burns, "
                            "aion_library_atomic_audit TO aion_joint_doc_reader")
        parsed = urlsplit(DSN)
        cls.acl_dsn = urlunsplit((parsed.scheme,
            "aion_joint_acl_reader:synthetic_joint_acl@localhost:5432", parsed.path, "", ""))
        cls.doc_dsn = urlunsplit((parsed.scheme,
            "aion_joint_doc_reader:synthetic_joint_doc@localhost:5432", parsed.path, "", ""))

    def setUp(self):
        with self.psycopg.connect(DSN, autocommit=True) as db:
            with db.cursor() as cur:
                cur.execute("TRUNCATE aion_library_atomic_audit, "
                            "aion_library_atomic_approval_burns, "
                            "aion_library_documents RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE aion_library_tenant_acl")
        self.now = NOW
        self.environment = "SANDBOX"
        self.enabled = True
        self.users = {
            "reviewer": AccessUser("reviewer", "ADMIN", self.password_hash),
            "client.1": AccessUser("client.1", "USER", self.password_hash),
        }
        self.login("reviewer")
        self.verifier = AttestationVerifier(
            identity_issuers={"authz": IK}, approval_issuers={"human": AK},
            rights_issuers={"license": RK}, clock=lambda: self.now)
        self.assembly = SandboxLibraryServerReadAssembly(
            environment_provider=lambda: self.environment,
            enabled_provider=lambda: self.enabled,
            access_provider=lambda: self.access,
            users_provider=lambda: self.users,
            acl_connect=lambda: self.psycopg.connect(self.acl_dsn),
            document_connect=lambda: self.psycopg.connect(self.doc_dsn),
            trusted_issuer="atlasquant.local", token_audience="aion-library",
            attestation_issuer="authz", identity_key=IK,
            verifier=self.verifier, checkpoint_key=b"c" * 32,
            clock=lambda: self.now,
        )
        catalog = LibraryCatalog()
        original = catalog.register_document(
            tenant_id="T-A", domain_id="TRADER", document_id="DOC-1",
            version=1, sha256="a" * 64, source_type="BOOK",
            source_reference="synthetic:isbn:123", license_kind="CC_BY",
            rights_holder="synthetic-publisher", usage_scope="INTERNAL",
            human_approved_by="reviewer")
        self.entry = catalog.transition(
            tenant_id="T-A", domain_id="TRADER", entry_id=original.entry_id,
            to_state="METADATA_REVIEW", actor="reviewer")
        self.store = AtomicLibraryStore(
            connect=lambda: self.psycopg.connect(DSN),
            verifier=self.verifier, clock=lambda: self.now)
        self.store.import_reviewed(trusted_entry=self.entry)
        self.selected = [("T-A", "TRADER", self.entry.entry_id)]
        self.reader = SandboxServerSelectedRead(
            assembly=self.assembly, trusted_selection_provider=lambda: self.selected[0])

    def login(self, username):
        session = authenticate(username, self.password, self.users)
        self.assertIsNotNone(session)
        self.access = {"allowed": True, "mode": "AUTHENTICATED", "role": session["role"],
                       "session": dict(session, authenticated_at=self.now-25,
                                       last_seen=self.now-1)}

    def grant(self, username="reviewer", tenant="T-A", role="LIBRARY_ADMIN", domain="TRADER"):
        with self.psycopg.connect(DSN) as db:
            with db.cursor() as cur:
                cur.execute("INSERT INTO aion_library_tenant_acl "
                            "(username, tenant_id, domain_id, library_role) VALUES (%s,%s,%s,%s)",
                            (username, tenant, domain, role))

    def revoke(self, username="client.1"):
        with self.psycopg.connect(DSN) as db:
            with db.cursor() as cur:
                cur.execute("UPDATE aion_library_tenant_acl SET active=FALSE, "
                            "revoked_at_unix=%s WHERE username=%s", (self.now, username))

    def approve(self):
        identity, approval, rights = make_proofs(self.entry)
        return self.store.approve(
            tenant_id="T-A", domain_id="TRADER", entry_id=self.entry.entry_id,
            identity_envelope=identity, approval_envelope=approval, rights_envelope=rights)

    def test_admin_review_then_reader_only_after_atomic_approval(self):
        self.grant()
        self.assertEqual(self.reader.read_selected().state, "METADATA_REVIEW")
        self.grant("client.1", role="LIBRARY_READER")
        self.login("client.1")
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()
        self.approve()
        result = self.reader.read_selected()
        self.assertEqual((result.entry_id, result.state, result.integrity_checked),
                         (self.entry.entry_id, "APPROVED_FOR_INDEXING", True))

    def test_no_implicit_admin_grants_cross_tenant(self):
        self.grant()
        self.selected[0] = ("T-B", "TRADER", self.entry.entry_id)
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()

    def test_revocation_visible_after_commit_in_next_read(self):
        self.grant("client.1", role="LIBRARY_READER")
        self.approve()
        self.login("client.1")
        self.assertTrue(self.reader.read_selected().integrity_checked)
        self.revoke()
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()

    def test_revocation_during_document_inspection_does_not_respond(self):
        self.grant("client.1", role="LIBRARY_READER")
        self.approve()
        self.login("client.1")
        original = self.assembly._facade._gate.inspect
        def revoked_during_inspect(**kwargs):
            report = original(**kwargs)
            self.revoke()
            return report
        self.assembly._facade._gate.inspect = revoked_during_inspect
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()

    def test_corrupted_postgres_audit_blocked_end_to_end(self):
        self.grant("client.1", role="LIBRARY_READER")
        self.approve()
        self.login("client.1")
        with self.psycopg.connect(DSN) as db:
            with db.cursor() as cur:
                cur.execute("UPDATE aion_library_atomic_audit SET event_hash=%s "
                            "WHERE entry_id=%s AND event_type='GENESIS'",
                            ("f"*64, self.entry.entry_id))
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()

    def test_switch_to_production_during_document_inspection_denies(self):
        self.grant("client.1", role="LIBRARY_READER")
        self.approve()
        self.login("client.1")
        original = self.assembly._facade._gate.inspect
        def changed(**kwargs):
            result = original(**kwargs)
            self.environment = "PRODUCTION"
            return result
        self.assembly._facade._gate.inspect = changed
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()

    def test_selection_changed_mid_read_denied_without_content(self):
        self.grant("client.1", role="LIBRARY_READER")
        self.approve()
        self.login("client.1")
        original = self.assembly._facade._gate.inspect
        def changed(**kwargs):
            report = original(**kwargs)
            self.selected[0] = ("T-B", "TRADER", self.entry.entry_id)
            return report
        self.assembly._facade._gate.inspect = changed
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()

    def test_reader_database_credentials_cannot_mutate_acl_or_documents(self):
        with self.psycopg.connect(self.acl_dsn) as db:
            with db.cursor() as cur:
                with self.assertRaises(self.psycopg.errors.InsufficientPrivilege):
                    cur.execute("UPDATE aion_library_tenant_acl SET active=FALSE")
        with self.psycopg.connect(self.doc_dsn) as db:
            with db.cursor() as cur:
                with self.assertRaises(self.psycopg.errors.InsufficientPrivilege):
                    cur.execute("UPDATE aion_library_documents SET state='REVOKED'")


if __name__ == "__main__": unittest.main()
