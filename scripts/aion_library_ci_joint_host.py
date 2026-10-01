"""STRICT CI-only host and fake PostgreSQL fixture for the actual-app browser drill.

Imported ONLY by scripts/aion_library_ci_instrumented_app.py and its runner.
Never import or mount this module in production. No document bytes are created.
"""
from __future__ import annotations

import os
import re
import time

OWNER_DSN = ("postgresql://library_sandbox:synthetic_ci_only_not_for_production"
             "@localhost:5432/aion_library_sandbox")
ACL_DSN = ("postgresql://aion_browser_acl_reader:synthetic_browser_acl"
           "@localhost:5432/aion_library_sandbox")
DOC_DSN = ("postgresql://aion_browser_doc_reader:synthetic_browser_doc"
           "@localhost:5432/aion_library_sandbox")
HOST_KEY = b"j" * 32  # Fictitious CI fixtures, never deployed or used with real data.
CHECKPOINT_KEY = b"c" * 32
SCOPE = ("T-A", "TRADER")
ENTRY_RE = re.compile(r"[A-Za-z0-9_.:-]{1,28}\Z")


def require_synthetic(*, writer=False):
    if (os.environ.get("CI") != "true" or
        os.environ.get("AION_LIB_BROWSER_PG_E2E") != "1" or
        os.environ.get("ATLASQUANT_ENV") != "SANDBOX" or
        os.environ.get("ATLASQUANT_REAL_APP_SYNTHETIC") != "1"):
        raise RuntimeError("synthetic CI-only Library browser/PostgreSQL drill")
    if writer and os.environ.get("AION_LIB_TEST_PG_DSN") != OWNER_DSN:
        raise RuntimeError("writer requires fixed ephemeral CI PostgreSQL DSN")


def initialize_fixture():
    """Runner-only owner operations, before app launches; not callable by browser."""
    require_synthetic(writer=True)
    import psycopg
    from aion_core.library_atomic_store import AtomicLibraryStore, MIGRATION_POSTGRESQL
    from aion_core.library_foundation import LibraryCatalog
    from aion_core.library_authorization import AttestationVerifier
    from atlasquant_aion_library_acl_postgres import MIGRATION_POSTGRESQL as ACL_DDL
    from test_aion_core_library_atomic_store import IK, AK, RK, sign

    with psycopg.connect(OWNER_DSN, autocommit=True) as db:
        with db.cursor() as c:
            c.execute(MIGRATION_POSTGRESQL)
            c.execute(ACL_DDL)
            for role, password in (
                ("aion_browser_acl_reader", "synthetic_browser_acl"),
                ("aion_browser_doc_reader", "synthetic_browser_doc"),
            ):
                c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
                if c.fetchone() is None:
                    # Both SQL identifiers are allowlisted constant strings above.
                    if role == "aion_browser_acl_reader":
                        c.execute("CREATE ROLE aion_browser_acl_reader LOGIN PASSWORD 'synthetic_browser_acl'")
                    else:
                        c.execute("CREATE ROLE aion_browser_doc_reader LOGIN PASSWORD 'synthetic_browser_doc'")
                c.execute("GRANT CONNECT ON DATABASE aion_library_sandbox TO " + role)
                c.execute("GRANT USAGE ON SCHEMA public TO " + role)
            c.execute("GRANT SELECT ON aion_library_tenant_acl TO aion_browser_acl_reader")
            c.execute("GRANT SELECT ON aion_library_documents, aion_library_atomic_audit, "
                      "aion_library_atomic_approval_burns TO aion_browser_doc_reader")
            c.execute("INSERT INTO aion_library_tenant_acl "
                      "(username, tenant_id, domain_id, library_role) "
                      "VALUES (%s,%s,%s,%s)",
                      ("admin.ci", SCOPE[0], SCOPE[1], "LIBRARY_ADMIN"))

    now = int(time.time())
    verifier = AttestationVerifier(
        identity_issuers={"authz": IK, "browser-host": HOST_KEY},
        approval_issuers={"human": AK},
        rights_issuers={"license": RK},
        clock=lambda: int(time.time()),
    )
    catalog = LibraryCatalog()
    entry = catalog.register_document(
        tenant_id=SCOPE[0], domain_id=SCOPE[1], document_id="DOC-1",
        version=1, sha256="a" * 64, source_type="BOOK",
        source_reference="synthetic:fixture", license_kind="CC_BY",
        rights_holder="synthetic-publisher", usage_scope="INTERNAL",
        human_approved_by="reviewer",
    )
    entry = catalog.transition(
        tenant_id=SCOPE[0], domain_id=SCOPE[1],
        entry_id=entry.entry_id, to_state="METADATA_REVIEW", actor="reviewer",
    )
    if ENTRY_RE.fullmatch(entry.entry_id) is None:
        raise RuntimeError("unexpected synthetic document selector")
    store = AtomicLibraryStore(
        connect=lambda: psycopg.connect(OWNER_DSN),
        verifier=verifier, clock=lambda: int(time.time()),
    )
    store.import_reviewed(trusted_entry=entry)

    common = dict(
        tenant_id=entry.tenant_id, domain_id=entry.domain_id,
        document_id=entry.document_id, version=entry.version,
        sha256=entry.sha256, license_kind=entry.license_kind,
        usage_scope=entry.usage_scope,
    )
    proofs = (
        sign("identity", dict(
            issuer="authz", subject="reviewer", tenant_id=entry.tenant_id,
            domain_id=entry.domain_id, roles=["LIBRARY_REVIEWER"],
            action="APPROVE_INDEX"), IK, now=now),
        sign("approval", dict(
            common, issuer="human", reviewer="reviewer",
            action="APPROVE_INDEX", approval_id="BROWSER-CI-APR-1"), AK, now=now),
        sign("rights", dict(
            common, issuer="license", rights_holder=entry.rights_holder,
            rights_action="INDEX", grant_id="BROWSER-CI-GRANT-1"), RK, now=now),
    )
    return entry, store, proofs


def approve_fixture(entry, store, proofs):
    require_synthetic(writer=True)
    identity, approval, rights = proofs
    return store.approve(
        tenant_id=SCOPE[0], domain_id=SCOPE[1], entry_id=entry.entry_id,
        identity_envelope=identity, approval_envelope=approval,
        rights_envelope=rights,
    )


def revoke_admin():
    require_synthetic(writer=True)
    import psycopg
    with psycopg.connect(OWNER_DSN) as db:
        with db.cursor() as c:
            c.execute("UPDATE aion_library_tenant_acl SET active=FALSE, "
                      "revoked_at_unix=%s WHERE username=%s",
                      (int(time.time()), "admin.ci"))


def assert_read_only_roles():
    require_synthetic(writer=True)
    import psycopg
    for dsn, table in ((ACL_DSN, "aion_library_tenant_acl"),
                       (DOC_DSN, "aion_library_documents")):
        with psycopg.connect(dsn) as db:
            with db.cursor() as c:
                try:
                    c.execute("UPDATE " + table + " SET state=state" if table == "aion_library_documents"
                              else "UPDATE aion_library_tenant_acl SET active=active")
                except psycopg.errors.InsufficientPrivilege:
                    db.rollback()
                else:
                    raise AssertionError("CI reader unexpectedly has SQL write permission")


def read_from_real_app_session():
    """Server-owned boundary. No browser parameters or caller-supplied IDs."""
    require_synthetic()
    from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
    from atlasquant_aion_library_server_assembly import SandboxLibraryServerReadAssembly
    from atlasquant_aion_library_server_selection import SandboxServerSelectedRead
    from atlasquant_access_panel import current_session, configured_users, session_time_status
    from atlasquant_access_control import session_is_current
    from test_aion_core_library_atomic_store import IK, AK, RK
    import psycopg

    entry_id = os.environ.get("AION_CI_TRUSTED_ENTRY", "")
    if ENTRY_RE.fullmatch(entry_id) is None:
        raise AuthorizationDenied("sandbox Library selection unavailable")

    def host_access():
        session = current_session()
        users = configured_users()
        if (not isinstance(session, dict) or
            session.get("username") != "admin.ci" or
            session.get("role") != "ADMIN" or
            not session_is_current(session, users) or
            session_time_status(session, time.time()).get("valid") is not True):
            raise AuthorizationDenied("sandbox Library read unavailable")
        return {"allowed": True, "mode": "AUTHENTICATED",
                "role": session["role"], "session": session}

    verifier = AttestationVerifier(
        identity_issuers={"authz": IK, "browser-host": HOST_KEY},
        approval_issuers={"human": AK}, rights_issuers={"license": RK},
        clock=lambda: int(time.time()),
    )
    assembly = SandboxLibraryServerReadAssembly(
        environment_provider=lambda: os.environ.get("ATLASQUANT_ENV"),
        enabled_provider=lambda: os.environ.get("AION_LIB_BROWSER_PG_E2E") == "1",
        access_provider=host_access, users_provider=configured_users,
        acl_connect=lambda: psycopg.connect(ACL_DSN),
        document_connect=lambda: psycopg.connect(DOC_DSN),
        trusted_issuer="atlasquant.local", token_audience="aion-library",
        attestation_issuer="browser-host", identity_key=HOST_KEY,
        verifier=verifier, checkpoint_key=CHECKPOINT_KEY,
        clock=lambda: int(time.time()),
    )
    selection = SandboxServerSelectedRead(
        assembly=assembly,
        trusted_selection_provider=lambda: (SCOPE[0], SCOPE[1], entry_id),
    )
    return selection.read_selected()
