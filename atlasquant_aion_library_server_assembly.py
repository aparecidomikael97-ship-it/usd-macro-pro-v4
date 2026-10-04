"""Server-side sandbox composition of the REAL local login + persisted ACL + PG audit.

NOT mounted by any Streamlit/FastAPI route. Requires trusted callback injection
and explicit opt-in at construction and EACH read. No network credentials are
loaded from app requests, and no migrations, uploads or approvals are performed.
"""
from __future__ import annotations

import hmac
from collections.abc import Callable, Mapping

from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from atlasquant_aion_library_acl_postgres import PostgresLibraryMembership
from atlasquant_aion_library_host_access import AtlasQuantLibraryHostAccess
from atlasquant_aion_library_postgres_preview import LibraryPostgresReadFacade, LibraryPanelPreview

SCHEMA = "ATLASQUANT_AION_LIBRARY_SERVER_ASSEMBLY_SANDBOX_V1"


def _denied() -> AuthorizationDenied:
    return AuthorizationDenied("sandbox Library read unavailable")


class SandboxLibraryServerReadAssembly:
    """Host-only callable assembly. No cached ACL, no global client-accessible API.

    ``access_provider`` must return the host's current authenticated access
    decision, never a user-submitted mapping. Both connection factories must
    issue restricted SELECT-only connections to the authoritative PG primary.
    The server must guard access to the assembly and its signing/verifier keys.
    """

    def __init__(self, *, environment_provider: Callable[[], str],
                 enabled_provider: Callable[[], bool],
                 access_provider: Callable[[], Mapping],
                 users_provider: Callable[[], Mapping],
                 acl_connect: Callable[[], object],
                 document_connect: Callable[[], object],
                 trusted_issuer: str, token_audience: str,
                 attestation_issuer: str, identity_key: bytes,
                 verifier: AttestationVerifier, checkpoint_key: bytes,
                 clock: Callable[[], int] | None = None):
        for callback in (environment_provider, enabled_provider, access_provider,
                         users_provider, acl_connect, document_connect):
            if not callable(callback):
                raise _denied()
        if (type(identity_key) is not bytes or len(identity_key) < 32 or
                type(checkpoint_key) is not bytes or len(checkpoint_key) < 32 or
                hmac.compare_digest(identity_key, checkpoint_key) or
                type(verifier) is not AttestationVerifier):
            raise _denied()
        self._environment = environment_provider
        self._enabled = enabled_provider
        self._preflight()
        # No default role grant. Every membership lookup must hit the DB.
        self._membership = PostgresLibraryMembership(connect=acl_connect)
        self._host = AtlasQuantLibraryHostAccess(
            access_provider=access_provider, users_provider=users_provider,
            membership_provider=self._membership.roles_for,
            trusted_issuer=trusted_issuer, token_audience=token_audience,
            attestation_issuer=attestation_issuer, signing_key=identity_key,
            clock=clock,
        )
        self._facade = LibraryPostgresReadFacade(
            host=self._host, verifier=verifier, connect=document_connect,
            checkpoint_key=checkpoint_key, clock=clock,
        )

    def _preflight(self):
        try:
            # Check exactly-typed values. A truthy string, OPEN or PRODUCTION
            # is never a substitute for explicit SANDBOX server configuration.
            env = self._environment()
            active = self._enabled()
            if type(env) is not str or env != "SANDBOX" or active is not True:
                raise _denied()
        except Exception as exc:
            raise _denied() from exc

    def read_preview(self, *, tenant_id: str, domain_id: str,
                     entry_id: str) -> LibraryPanelPreview:
        self._preflight()
        try:
            result = self._facade.read_preview(
                tenant_id=tenant_id, domain_id=domain_id, entry_id=entry_id)
            # Disable the feature even when config changes DURING DB inspection.
            self._preflight()
        except Exception as exc:
            raise _denied() from exc
        return result


__all__ = ["SCHEMA", "SandboxLibraryServerReadAssembly"]
