"""AION Library read-only *host service* for an eventual opt-in app panel.

This is intentionally not mounted in Streamlit, FastAPI or any public route.
The host owns access/registry/ACL callbacks, verification keys, and a SELECT-only
PostgreSQL connection factory. Only the PostgreSQL integrity report is used:
there is NO fallback to the legacy in-memory catalog. Not a content downloader.
"""
from __future__ import annotations

import hmac
import re
from collections.abc import Callable
from dataclasses import dataclass

from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from aion_core.library_recovery_gate import LibraryRecoveryGate
from atlasquant_aion_library_host_access import AtlasQuantLibraryHostAccess

_ID = re.compile(r'[A-Za-z0-9_.:-]{1,128}\Z')


def _deny() -> AuthorizationDenied:
    # Do not distinguish missing documents, scopes, review state or DB errors.
    return AuthorizationDenied('library read unavailable or access denied')


def _scope(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


@dataclass(frozen=True)
class LibraryPanelPreview:
    """Minimal metadata for a trusted app to display, never document bytes."""
    entry_id: str
    version: int
    state: str
    integrity_checked: bool


class LibraryPostgresReadFacade:
    """Host-only read path: live login + explicit ACL + authoritative PG audit.

    `read_preview` must be invoked on each request and **not cached**. Both the
    local-login registry and tenant ACL are rechecked after PostgreSQL inspection.
    The underlying consistency check is point-in-time; external revocations or
    concurrent writes AFTER this method's last check cannot be prevented here.
    Public activation additionally requires trusted host routing and DB access
    with SELECT-only credentials, independent audit anchoring and E2E review.
    """

    def __init__(self, *, host: AtlasQuantLibraryHostAccess,
                 verifier: AttestationVerifier, connect: Callable[[], object],
                 checkpoint_key: bytes, clock: Callable[[], int] | None = None):
        if type(host) is not AtlasQuantLibraryHostAccess or type(verifier) is not AttestationVerifier:
            raise AuthorizationDenied('trusted host login and verifier required')
        bridge = host.identity_bridge
        # A wrong verifier could cause proof failures in confusing places. Do
        # not even construct the integration if the host attestor is not trusted.
        issuer = bridge._attestation_issuer
        trusted_key = verifier._keys['identity'].get(issuer)
        if (type(trusted_key) is not bytes or
                not hmac.compare_digest(trusted_key, bridge._key)):
            raise AuthorizationDenied('host identity issuer must match verifier')
        self._host = host
        self._gate = LibraryRecoveryGate(
            identities=bridge, verifier=verifier, connect=connect,
            checkpoint_key=checkpoint_key, clock=clock,
        )

    def read_preview(self, *, tenant_id: str, domain_id: str,
                     entry_id: str) -> LibraryPanelPreview:
        if not all(_scope(v) for v in (tenant_id, domain_id, entry_id)):
            raise _deny()
        handle = None
        try:
            # This principal is created from a server-owned current session,
            # never a client-submitted username, role or tenant membership.
            before = self._host._principal()
            roles_before = frozenset(self._host._lookup_roles(
                before.username, tenant_id, domain_id))
            if not roles_before.intersection({'LIBRARY_READER', 'LIBRARY_REVIEWER', 'LIBRARY_ADMIN'}):
                raise _deny()
            # A handle is process-local and never leaves this private method.
            handle = self._host._new_handle()
            report = self._gate.inspect(
                token=handle, tenant_id=tenant_id, domain_id=domain_id,
                entry_id=entry_id,
            )
            if ((report.tenant_id, report.domain_id, report.entry_id) !=
                    (tenant_id, domain_id, entry_id) or
                    type(report.version) is not int or report.version < 1 or
                    report.state not in {'METADATA_REVIEW', 'APPROVED_FOR_INDEXING'}):
                raise _deny()
            # Readers must not learn even whether a review-state entry exists.
            if (report.state != 'APPROVED_FOR_INDEXING' and
                    not roles_before.intersection({'LIBRARY_REVIEWER', 'LIBRARY_ADMIN'})):
                raise _deny()
            after = self._host._principal()
            roles_after = frozenset(self._host._lookup_roles(
                after.username, tenant_id, domain_id))
            if (before.username != after.username or before.role != after.role or
                    not hmac.compare_digest(before.fingerprint, after.fingerprint) or
                    not roles_after.intersection({'LIBRARY_READER', 'LIBRARY_REVIEWER', 'LIBRARY_ADMIN'}) or
                    (report.state != 'APPROVED_FOR_INDEXING' and
                     not roles_after.intersection({'LIBRARY_REVIEWER', 'LIBRARY_ADMIN'}))):
                raise _deny()
            return LibraryPanelPreview(
                entry_id=report.entry_id,
                version=report.version,
                state=report.state,
                integrity_checked=True,
            )
        except Exception as exc:
            # No sensitive DB error or document existence leaks to the view.
            raise _deny() from exc
        finally:
            if handle is not None:
                with self._host._lock:
                    self._host._sessions.pop(handle, None)
