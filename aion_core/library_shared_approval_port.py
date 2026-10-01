"""PostgreSQL shared approval-burn storage *port* for AION Library (sandbox).

The trusted server supplies a PostgreSQL DB-API connection factory. This module
never connects to a network, stores credentials, creates schema or exposes a
production endpoint. It commits a unique approval burn atomically across
workers sharing one correctly managed PostgreSQL primary. It deliberately does
NOT mutate the in-memory catalog or claim atomicity with document state.
"""
from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable

from .library_authorization import AuthorizationDenied, _encode

# Migration performed by a privileged operator OUTSIDE the application runtime.
# Use dedicated restricted DB credentials for runtime; no automatic DDL.
MIGRATION_POSTGRESQL = """\
CREATE TABLE aion_library_approval_burns (
    approval_key CHAR(64) PRIMARY KEY,
    binding_sha256 CHAR(64) NOT NULL,
    burned_at_unix BIGINT NOT NULL,
    CONSTRAINT aion_library_burn_sha CHECK (
        approval_key ~ '^[0-9a-f]{64}$' AND
        binding_sha256 ~ '^[0-9a-f]{64}$' AND burned_at_unix >= 0
    )
);
"""

_INSERT = ("INSERT INTO aion_library_approval_burns "
           "(approval_key, binding_sha256, burned_at_unix) VALUES (%s, %s, %s) "
           "ON CONFLICT (approval_key) DO NOTHING RETURNING approval_key")
_IDENT = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


class SharedApprovalBurnPort:
    """At-most-once burn, with transaction ownership limited to this table.

    `connect` MUST be a trusted host-owned connection factory yielding a fresh
    connection to the same PostgreSQL primary for every operation. A connection
    pool may be used if connections are returned with no open transaction.
    Multiple independent PostgreSQL primaries do NOT meet this contract.
    """

    def __init__(self, *, connect: Callable[[], object], clock: Callable[[], int] | None = None):
        if not callable(connect):
            raise AuthorizationDenied("shared approval connection factory required")
        if clock is not None and not callable(clock):
            raise AuthorizationDenied("trusted clock must be callable")
        self._connect = connect
        self._clock = clock if clock is not None else lambda: int(time.time())

    def burn(self, *, issuer: str, approval_id: str, binding_sha256: str) -> str:
        """Commit a unique opaque burn; fail closed on duplicate or DB failure.

        An unavailable database never permits an approval. A committed burn is
        intentionally NOT rolled back if a later in-memory transition fails.
        Do not use this method before fully validating signature/scope/rights.
        """
        if (type(issuer) is not str or not _IDENT.fullmatch(issuer) or
                type(approval_id) is not str or not _IDENT.fullmatch(approval_id) or
                type(binding_sha256) is not str or not _HEX.fullmatch(binding_sha256)):
            raise AuthorizationDenied("invalid approval scope or binding")
        now = self._clock()
        if type(now) is not int or now < 0:
            raise AuthorizationDenied("trusted clock invalid")
        opaque = hashlib.sha256(_encode([issuer, approval_id])).hexdigest()
        conn = None
        cursor = None
        try:
            conn = self._connect()
            if conn is None or getattr(conn, "autocommit", None) is not False:
                raise AuthorizationDenied("transactional shared connection required")
            cursor = conn.cursor()
            cursor.execute(_INSERT, (opaque, binding_sha256, now))
            returned = cursor.fetchone()
            if returned != (opaque,):
                raise AuthorizationDenied("approval already used or reserved")
            conn.commit()
            return opaque
        except AuthorizationDenied:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        except Exception as exc:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise AuthorizationDenied("shared approval storage unavailable; operation denied") from exc
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
