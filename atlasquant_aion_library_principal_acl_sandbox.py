"""Opt-in, UNMOUNTED principal-bound Library ACL contract (SANDBOX V2).

The V1 username ACL remains unchanged. This is NOT an identity provider,
migration runner, user-provisioning route or production activation. Only a
trusted host registry may produce CurrentPrincipal; never construct it from
browser data, prompt content, JWT claims without independent verification, or
a fallback username. Account generation must change on delete/recreate and
remain stable on password rotation for the SAME account.

V1 grants are deliberately NOT recognized by this reader. Actual integration
needs separately reviewed lifecycle/provisioning, migration, DB grants and E2E.
"""
from __future__ import annotations

import hmac
import re
from collections.abc import Callable
from dataclasses import dataclass

from aion_core.library_authorization import AuthorizationDenied
from atlasquant_access_control import normalize_username
from atlasquant_aion_library_acl_postgres import ROLES

SCHEMA = "ATLASQUANT_AION_LIBRARY_PRINCIPAL_ACL_SANDBOX_V2"
_ISSUER = re.compile(r"[a-z][a-z0-9._:-]{2,63}\Z")
_SUBJECT = re.compile(r"[A-Za-z0-9_.:-]{8,128}\Z")
_GENERATION = re.compile(r"[0-9a-f]{32}\Z")
_SCOPE = re.compile(r"[A-Za-z0-9_.:-]{1,64}\Z")

# REVIEW-ONLY: never execute this DDL from the reader or mount it in the app.
# New table, not an automatic migration of username-only V1 ACL. Operators must
# separately define who mints durable principal IDs and account generations.
MIGRATION_PRINCIPAL_ACL_V2 = """
CREATE TABLE aion_library_tenant_acl_principal_v2 (
  principal_issuer VARCHAR(64) NOT NULL,
  principal_subject VARCHAR(128) NOT NULL,
  account_generation CHAR(32) NOT NULL,
  username VARCHAR(64) NOT NULL,
  tenant_id VARCHAR(64) NOT NULL,
  domain_id VARCHAR(64) NOT NULL,
  library_role VARCHAR(32) NOT NULL
    CHECK (library_role IN ('LIBRARY_READER','LIBRARY_REVIEWER','LIBRARY_ADMIN')),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  revoked_at_unix BIGINT NULL CHECK (revoked_at_unix > 0),
  PRIMARY KEY(principal_issuer, principal_subject, account_generation,
              tenant_id, domain_id, library_role),
  CHECK ((active AND revoked_at_unix IS NULL)
         OR (NOT active AND revoked_at_unix IS NOT NULL)),
  CHECK (username = LOWER(username))
);
CREATE INDEX aion_library_acl_principal_v2_scope_idx
  ON aion_library_tenant_acl_principal_v2
     (principal_issuer, principal_subject, account_generation,
      username, tenant_id, domain_id);
"""

_SELECT = """SELECT library_role, active, revoked_at_unix
 FROM aion_library_tenant_acl_principal_v2
 WHERE principal_issuer=%s AND principal_subject=%s
   AND account_generation=%s AND username=%s
   AND tenant_id=%s AND domain_id=%s
 ORDER BY library_role"""


@dataclass(frozen=True)
class CurrentPrincipal:
    """Server-verified account lifecycle identity. Not client claims."""

    username: str
    issuer: str
    subject: str
    account_generation: str
    active: bool


def _deny() -> AuthorizationDenied:
    return AuthorizationDenied("trusted principal membership unavailable")


def _valid(principal: object, username: object) -> bool:
    return (
        type(principal) is CurrentPrincipal
        and type(username) is str
        and bool(username)
        and username == normalize_username(username)
        and type(principal.username) is str
        and hmac.compare_digest(principal.username, username)
        and type(principal.issuer) is str
        and _ISSUER.fullmatch(principal.issuer) is not None
        and type(principal.subject) is str
        and _SUBJECT.fullmatch(principal.subject) is not None
        and type(principal.account_generation) is str
        and _GENERATION.fullmatch(principal.account_generation) is not None
        and principal.active is True
    )


class PrincipalBoundPostgresMembership:
    """Read-only ACL V2. Fresh trusted identity + fresh SQL scope on EVERY call.

    The injected current_principal callback must resolve the currently
    authenticated *server-side* account from an independently trusted durable
    registry. Its identity must not change within one read; changed/deleted
    accounts fail closed. No username-only fallback or cached ACL is allowed.
    """

    def __init__(
        self, *, connect: Callable[[], object],
        current_principal: Callable[[], CurrentPrincipal]
    ):
        if not callable(connect) or not callable(current_principal):
            raise _deny()
        self._connect = connect
        self._current_principal = current_principal

    def _principal(self, username: str) -> CurrentPrincipal:
        try:
            current = self._current_principal()
        except Exception as exc:
            raise _deny() from exc
        if not _valid(current, username):
            raise _deny()
        return current

    def roles_for(self, username: str, tenant_id: str, domain_id: str) -> tuple[str, ...]:
        if (
            type(tenant_id) is not str or _SCOPE.fullmatch(tenant_id) is None
            or type(domain_id) is not str or _SCOPE.fullmatch(domain_id) is None
        ):
            raise _deny()
        before = self._principal(username)
        db = cur = None
        try:
            db = self._connect()
            if db is None or getattr(db, "autocommit", None) is not False:
                raise _deny()
            cur = db.cursor()
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY")
            cur.execute(
                _SELECT,
                (before.issuer, before.subject, before.account_generation,
                 before.username, tenant_id, domain_id),
            )
            rows = cur.fetchmany(4)  # More than three roles indicates corruption.
            if type(rows) not in (list, tuple) or len(rows) > len(ROLES):
                raise _deny()
            seen: set[str] = set()
            active: set[str] = set()
            for row in rows:
                if type(row) not in (tuple, list) or len(row) != 3:
                    raise _deny()
                role, enabled, revoked = row
                if (
                    type(role) is not str or role not in ROLES or role in seen
                    or type(enabled) is not bool
                    or not (
                        enabled is True and revoked is None
                        or enabled is False and type(revoked) is int and revoked > 0
                    )
                ):
                    raise _deny()
                seen.add(role)
                if enabled:
                    active.add(role)
            after = self._principal(username)
            if (
                not hmac.compare_digest(before.issuer, after.issuer)
                or not hmac.compare_digest(before.subject, after.subject)
                or not hmac.compare_digest(
                    before.account_generation, after.account_generation
                )
            ):
                raise _deny()
            return tuple(sorted(active))
        except Exception as exc:
            raise _deny() from exc
        finally:
            # Explicitly end the SELECT-only transaction. Never cache handles.
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


__all__ = [
    "SCHEMA", "CurrentPrincipal", "MIGRATION_PRINCIPAL_ACL_V2",
    "PrincipalBoundPostgresMembership",
]
