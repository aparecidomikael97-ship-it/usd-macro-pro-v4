"""Unmounted, SELECT-only authoritative principal registry port for Library V2.

SANDBOX DESIGN CONTRACT: This is NOT a login system, token verifier, account
provisioner, production migration, user lifecycle engine, or a document route.
The trusted host must supply a freshly VERIFIED session that ALREADY includes
an independent stable issuer/subject/account generation. These fields cannot
be derived from username, password hash or client request data. The current
AtlasQuant V1 login does not supply them, so this port must not be mounted
until its host-side identity lifecycle and audit are independently reviewed.

The SQL schema below is DOCUMENTATION ONLY and is executed exclusively by
strict opt-in CI fixtures. V1 username ACL is never imported or inferred.
"""
from __future__ import annotations

import hmac
import re
from collections.abc import Callable
from dataclasses import dataclass

from aion_core.library_authorization import AuthorizationDenied
from atlasquant_access_control import normalize_username
from atlasquant_aion_library_principal_acl_sandbox import CurrentPrincipal

SCHEMA = "ATLASQUANT_AION_LIBRARY_PERSISTENT_PRINCIPAL_REGISTRY_SANDBOX_V1"
_ISSUER = re.compile(r"[a-z][a-z0-9._:-]{2,63}\Z")
_SUBJECT = re.compile(r"[A-Za-z0-9_.:-]{8,128}\Z")
_GENERATION = re.compile(r"[0-9a-f]{32}\Z")
_FINGERPRINT = re.compile(r"[0-9a-f]{24}\Z")

# New, separate table; NO V1 migration or privilege changes at import time.
# A privileged, audited identity control plane MUST:
#  * allocate a new cryptographically unpredictable account_generation on
#    delete/recreate, even if issuer/subject/username are reused;
#  * retire previous identities and synchronize durable revocation across DR;
#  * update credential_binding on rotation of the SAME principal, atomically
#    with trusted host credential changes, without reviving retired IDs.
# The read adapter below has no write path, no fallback and no DDL execution.
MIGRATION_PRINCIPAL_REGISTRY = """
CREATE TABLE aion_library_principal_registry_sandbox (
  principal_issuer VARCHAR(64) NOT NULL,
  principal_subject VARCHAR(128) NOT NULL,
  account_generation CHAR(32) NOT NULL,
  username VARCHAR(64) NOT NULL,
  credential_binding CHAR(24) NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  retired_at_unix BIGINT NULL CHECK (retired_at_unix > 0),
  PRIMARY KEY(principal_issuer, principal_subject, account_generation),
  CHECK ((active AND retired_at_unix IS NULL)
       OR (NOT active AND retired_at_unix IS NOT NULL)),
  CHECK (username = LOWER(username))
);
-- Prevent two simultaneously active generations sharing the same issuer
-- and username. Historical retired rows remain for audit/DR reconciliation.
CREATE UNIQUE INDEX aion_library_principal_registry_active_username
  ON aion_library_principal_registry_sandbox(principal_issuer, username)
  WHERE active;
"""

_SELECT = """SELECT username, credential_binding, active, retired_at_unix
 FROM aion_library_principal_registry_sandbox
 WHERE principal_issuer=%s AND principal_subject=%s
   AND account_generation=%s"""


@dataclass(frozen=True)
class VerifiedHostAccount:
    """Server-owned identity assertion, NOT to be accepted from clients."""

    username: str
    issuer: str
    subject: str
    account_generation: str
    credential_fingerprint: str
    active: bool


def _deny() -> AuthorizationDenied:
    return AuthorizationDenied("principal registry unavailable or access denied")


def _valid(snapshot: object) -> bool:
    return (
        type(snapshot) is VerifiedHostAccount
        and type(snapshot.username) is str
        and bool(snapshot.username)
        and snapshot.username == normalize_username(snapshot.username)
        and type(snapshot.issuer) is str
        and _ISSUER.fullmatch(snapshot.issuer) is not None
        and type(snapshot.subject) is str
        and _SUBJECT.fullmatch(snapshot.subject) is not None
        and type(snapshot.account_generation) is str
        and _GENERATION.fullmatch(snapshot.account_generation) is not None
        and type(snapshot.credential_fingerprint) is str
        and _FINGERPRINT.fullmatch(snapshot.credential_fingerprint) is not None
        and snapshot.active is True
    )


def _same(left: VerifiedHostAccount, right: VerifiedHostAccount) -> bool:
    return all(
        hmac.compare_digest(getattr(left, field), getattr(right, field))
        for field in ("username", "issuer", "subject",
                      "account_generation", "credential_fingerprint")
    )


class PostgresPrincipalRegistry:
    """Fresh SELECT-only lookup against a separate persistent identity table.

    Caller supplies a currently authenticated *server-side* identity binding
    from a source independent of this SQL table. This must not be built from
    the AtlasQuant V1 username alone. The returned CurrentPrincipal may feed
    PrincipalBoundPostgresMembership(current_principal=registry.current_principal).
    """

    def __init__(
        self, *, connect: Callable[[], object],
        verified_host_account: Callable[[], VerifiedHostAccount],
    ):
        if not callable(connect) or not callable(verified_host_account):
            raise _deny()
        self._connect = connect
        self._host = verified_host_account

    def _snapshot(self) -> VerifiedHostAccount:
        try:
            snapshot = self._host()
        except Exception as exc:
            raise _deny() from exc
        if not _valid(snapshot):
            raise _deny()
        return snapshot

    def current_principal(self) -> CurrentPrincipal:
        before = self._snapshot()
        db = cursor = None
        try:
            db = self._connect()
            if db is None or getattr(db, "autocommit", None) is not False:
                raise _deny()
            cursor = db.cursor()
            cursor.execute(
                "SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY"
            )
            cursor.execute(
                _SELECT, (before.issuer, before.subject, before.account_generation)
            )
            rows = cursor.fetchmany(2)
            if type(rows) not in (tuple, list) or len(rows) != 1:
                raise _deny()
            row = rows[0]
            if type(row) not in (list, tuple) or len(row) != 4:
                raise _deny()
            username, binding, enabled, retired = row
            if (
                type(username) is not str or type(binding) is not str
                or type(enabled) is not bool or enabled is not True
                or retired is not None
                or not hmac.compare_digest(before.username, username)
                or _FINGERPRINT.fullmatch(binding) is None
                or not hmac.compare_digest(before.credential_fingerprint, binding)
            ):
                raise _deny()
            after = self._snapshot()
            if not _same(before, after):
                raise _deny()
            return CurrentPrincipal(
                username=before.username, issuer=before.issuer,
                subject=before.subject,
                account_generation=before.account_generation, active=True,
            )
        except Exception as exc:
            raise _deny() from exc
        finally:
            # Ending each read-only transaction prevents cache/snapshot reuse.
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    pass
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass


__all__ = (
    "SCHEMA", "VerifiedHostAccount",
    "MIGRATION_PRINCIPAL_REGISTRY", "PostgresPrincipalRegistry",
)
