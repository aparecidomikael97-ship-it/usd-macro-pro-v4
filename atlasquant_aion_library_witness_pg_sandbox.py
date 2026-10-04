"""Sandbox-only PostgreSQL retirement witness reader: a DIFFERENT DATABASE.

A read-only view of the latest authority revision, deliberately outside the
identity/ACL dump being restored. This is logical DB separation only: the CI
witness and restored databases still share ONE EPHEMERAL PostgreSQL SERVER.
Neither this reader nor an in-memory floor establishes offsite durability,
true independent failure domains, authenticated publication or custody.

Only a separately verified LIVE service may furnish the trusted connection.
MIGRATION_WITNESS_PG is documentation, executed only by opt-in synthetic tests.
Never mount into AtlasQuant V1, provision users or import V1 username ACL.
"""
from __future__ import annotations

import re
from collections.abc import Callable

from aion_core.library_authorization import AuthorizationDenied
from atlasquant_access_control import normalize_username
from atlasquant_aion_library_external_retirement_fence_sandbox import (
    ExternalAuthorityHead,
)

SCHEMA = "ATLASQUANT_LIBRARY_SEPARATE_DB_WITNESS_SANDBOX_V1"
_ISSUER = re.compile(r"[a-z][a-z0-9._:-]{2,63}\Z")
_SUBJECT = re.compile(r"[A-Za-z0-9_.:-]{8,128}\Z")
_GENERATION = re.compile(r"[0-9a-f]{32}\Z")
_MAX_REVISION = (1 << 63) - 1

# The operator, NOT this reader, must handle authenticated append, signed
# custody, anti-rollback floor, audit and external offsite delivery. Historical
# rows are retained to aid synthetic inspection, not proof of immutability.
MIGRATION_WITNESS_PG = """
CREATE TABLE aion_library_witness_history_sandbox (
  principal_issuer VARCHAR(64) NOT NULL,
  username VARCHAR(64) NOT NULL,
  principal_subject VARCHAR(128) NOT NULL,
  account_generation CHAR(32) NOT NULL,
  active BOOLEAN NOT NULL,
  revision BIGINT NOT NULL CHECK (revision > 0),
  PRIMARY KEY(principal_issuer, username, revision),
  CHECK (username = LOWER(username))
);
"""

_SELECT = """SELECT principal_subject, account_generation, active, revision
 FROM aion_library_witness_history_sandbox
 WHERE principal_issuer=%s AND username=%s
 ORDER BY revision DESC LIMIT 2"""


def _deny() -> AuthorizationDenied:
    return AuthorizationDenied("trusted retirement witness unavailable")


class SeparateDatabaseWitnessReader:
    """Read-only latest witness head, with NO implicit revision floor.

    Always compose current_head with an INDEPENDENT externally monotonic
    minimum_revision through ExternalRetirementFence. Returning latest SQL
    alone is not sufficient to defeat snapshot rollback of this database.
    """

    def __init__(self, *, connect: Callable[[], object]):
        if not callable(connect):
            raise _deny()
        self._connect = connect

    def current_head(self, issuer: str, username: str) -> ExternalAuthorityHead:
        if (
            type(issuer) is not str or _ISSUER.fullmatch(issuer) is None
            or type(username) is not str or not username
            or username != normalize_username(username)
        ):
            raise _deny()
        db = cur = None
        try:
            db = self._connect()
            if db is None or getattr(db, "autocommit", None) is not False:
                raise _deny()
            cur = db.cursor()
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY")
            cur.execute(_SELECT, (issuer, username))
            rows = cur.fetchmany(3)
            if type(rows) not in (list, tuple) or not 1 <= len(rows) <= 2:
                raise _deny()
            previous_revision = None
            for idx, row in enumerate(rows):
                if type(row) not in (tuple, list) or len(row) != 4:
                    raise _deny()
                subject, generation, active, revision = row
                if (
                    type(subject) is not str or _SUBJECT.fullmatch(subject) is None
                    or type(generation) is not str
                    or _GENERATION.fullmatch(generation) is None
                    or type(active) is not bool
                    or type(revision) is not int
                    or not 1 <= revision <= _MAX_REVISION
                ):
                    raise _deny()
                if idx == 0:
                    latest = ExternalAuthorityHead(
                        issuer, username, subject, generation, active, revision
                    )
                elif revision >= previous_revision:
                    # Fail if result ordering/monotonic history is inconsistent.
                    raise _deny()
                previous_revision = revision
            return latest
        except Exception as exc:
            raise _deny() from exc
        finally:
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


__all__ = ("SCHEMA", "MIGRATION_WITNESS_PG", "SeparateDatabaseWitnessReader")
