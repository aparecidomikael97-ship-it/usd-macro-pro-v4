"""AION Library tenant ACL lookup backed by authoritative PostgreSQL, sandbox V1.

No provisioning route, no credentials, no migration execution and no implicit
ADMIN powers. Inject a trusted PostgreSQL connection factory with a SELECT-only
DB role; the host passes `roles_for` as its membership_provider. Every lookup
uses a fresh READ COMMITTED READ ONLY transaction, never an in-process cache.
"""
from __future__ import annotations

import re
from collections.abc import Callable

from aion_core.library_authorization import AuthorizationDenied
from atlasquant_access_control import normalize_username

SCHEMA = 'ATLASQUANT_AION_LIBRARY_PG_ACL_SANDBOX_V1'
ROLES = frozenset({'LIBRARY_READER', 'LIBRARY_REVIEWER', 'LIBRARY_ADMIN'})
_SCOPE = re.compile(r'[A-Za-z0-9_.:-]{1,64}\Z')

# Migration is DOCUMENTATION ONLY. Never run this statement from read code.
# Privileged provisioning/revocation must be reviewed, audited and isolated
# from public Streamlit sessions and this SELECT-only membership adapter.
MIGRATION_POSTGRESQL = '''
CREATE TABLE aion_library_tenant_acl (
  username VARCHAR(64) NOT NULL,
  tenant_id VARCHAR(64) NOT NULL,
  domain_id VARCHAR(64) NOT NULL,
  library_role VARCHAR(32) NOT NULL
    CHECK (library_role IN ('LIBRARY_READER','LIBRARY_REVIEWER','LIBRARY_ADMIN')),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  revoked_at_unix BIGINT NULL CHECK (revoked_at_unix > 0),
  PRIMARY KEY(username, tenant_id, domain_id, library_role),
  CHECK ((active AND revoked_at_unix IS NULL)
         OR (NOT active AND revoked_at_unix IS NOT NULL)),
  CHECK (username = LOWER(username))
);
CREATE INDEX aion_library_tenant_acl_scope_idx
  ON aion_library_tenant_acl (username, tenant_id, domain_id);
-- Revoke by a separate privileged, audited control plane only:
-- UPDATE aion_library_tenant_acl
-- SET active = FALSE, revoked_at_unix = :trusted_now
-- WHERE username = :subject AND tenant_id = :tenant
--   AND domain_id = :domain AND library_role = :role;
-- Grant/regrant, role change and user deletion require separate review.
-- Runtime role: SELECT privilege on THIS table only, no UPDATE/INSERT/DELETE.
'''

_SELECT = '''SELECT library_role, active, revoked_at_unix
 FROM aion_library_tenant_acl
 WHERE username=%s AND tenant_id=%s AND domain_id=%s
 ORDER BY library_role'''


def _valid_scope(v: object) -> bool:
    return type(v) is str and _SCOPE.fullmatch(v) is not None


class PostgresLibraryMembership:
    """Independent, non-caching membership source for AtlasQuantLibraryHostAccess.

    This port does not accept a caller's role claim. It returns trusted rows
    only when *all* rows for the requested scope are internally consistent.
    Returned roles are further narrowed against USER/SALES/ADMIN's host role
    by AtlasQuantLibraryHostAccess._lookup_roles.
    """

    def __init__(self, *, connect: Callable[[], object]):
        if not callable(connect):
            raise AuthorizationDenied('trusted membership DB configuration required')
        self._connect = connect

    def roles_for(self, username: str, tenant_id: str, domain_id: str) -> tuple[str, ...]:
        if (type(username) is not str or not username or
                username != normalize_username(username) or
                not _valid_scope(tenant_id) or not _valid_scope(domain_id)):
            raise AuthorizationDenied('invalid membership scope')
        db = cur = None
        try:
            db = self._connect()
            if db is None or getattr(db, 'autocommit', None) is not False:
                raise AuthorizationDenied('transactional membership connection required')
            cur = db.cursor()
            # Must precede SELECT. An old snapshot/cached result is forbidden.
            cur.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY')
            cur.execute(_SELECT, (username, tenant_id, domain_id))
            rows = cur.fetchmany(4)  # at most three possible roles; detect schema drift
            if type(rows) not in (list, tuple) or len(rows) > len(ROLES):
                raise AuthorizationDenied('library membership schema inconsistent')
            allowed = set()
            seen = set()
            for row in rows:
                if type(row) not in (tuple, list) or len(row) != 3:
                    raise AuthorizationDenied('library membership row invalid')
                role, active, revoked = row
                if (type(role) is not str or role not in ROLES or role in seen or
                        type(active) is not bool or
                        not ((active and revoked is None) or
                             (not active and type(revoked) is int and revoked > 0))):
                    raise AuthorizationDenied('library membership row inconsistent')
                seen.add(role)
                if active:
                    allowed.add(role)
            return tuple(sorted(allowed))
        except Exception as exc:
            raise AuthorizationDenied('trusted library membership unavailable') from exc
        finally:
            # All read transactions are rolled back; no writes, cached sessions
            # or connection reuse are allowed by this implementation.
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    pass
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass


__all__ = ['SCHEMA', 'ROLES', 'MIGRATION_POSTGRESQL', 'PostgresLibraryMembership']
