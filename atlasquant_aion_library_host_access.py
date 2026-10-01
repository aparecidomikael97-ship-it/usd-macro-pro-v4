"""Opt-in AION Library adapter for the EXISTING AtlasQuant local login.

No HTTP route, IdP, registry, secrets, DB migration, or production activation.
The HOST must own every provider; never expose this adapter, its signing key,
attestation-minting method or mutable registry callbacks to client requests.
The normal AtlasQuant OPEN/bootstrap PREVIEW modes NEVER grant library access.
"""
from __future__ import annotations

import hmac
import math
import secrets
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from atlasquant_access_control import (
    ROLE_PERMISSIONS, normalize_username, session_is_current,
)
from aion_core.library_authorization import AuthorizationDenied
from aion_core.library_security_runtime import ExternalIdentityBridge, VerifiedSession

SCHEMA = "ATLASQUANT_AION_LIBRARY_HOST_ACCESS_SANDBOX_V1"
# Match the host's current atlasquant_access_panel session policy; integration
# MUST centrally share these constants before any public library routes exist.
MAX_SESSION_AGE = 12 * 60 * 60
MAX_SESSION_IDLE = 2 * 60 * 60
TOKEN_TTL = 120
MAX_PENDING = 128
_HOST_ROLES = {
    "USER": frozenset(("LIBRARY_READER",)),
    "SALES": frozenset(("LIBRARY_READER",)),
    "ADMIN": frozenset(("LIBRARY_READER", "LIBRARY_REVIEWER", "LIBRARY_ADMIN")),
}


@dataclass(frozen=True)
class HostPrincipal:
    username: str
    role: str
    fingerprint: str
    expires_at: int


class AtlasQuantLibraryHostAccess:
    """Server-owned contract coupling actual local login to a signed library proof.

    The existing access_provider MUST read the latest host-side authenticated
    render_access_gate result (not JSON from a user). users_provider MUST load
    the current trusted AccessUser registry. membership_provider MUST consult a
    separate server-side per-tenant/domain ACL and return a tuple/frozenset of
    library roles; never use caller-provided claims or infer access from ADMIN.

    Scope authorization is rechecked on EVERY requested identity proof. The
    short-lived random handle is held only inside this process, and neither it
    nor the HMAC keys should ever be returned by a public route.
    """

    def __init__(self, *, access_provider: Callable[[], Mapping],
                 users_provider: Callable[[], Mapping],
                 membership_provider: Callable[[str, str, str], object],
                 trusted_issuer: str, token_audience: str,
                 attestation_issuer: str, signing_key: bytes,
                 clock: Callable[[], int] | None = None):
        if not all(callable(f) for f in (access_provider, users_provider, membership_provider)):
            raise AuthorizationDenied("trusted host access providers required")
        self._access = access_provider
        self._users = users_provider
        self._membership = membership_provider
        self._clock = clock if clock is not None else lambda: int(time.time())
        if not callable(self._clock):
            raise AuthorizationDenied("trusted host clock required")
        self._sessions: dict[str, tuple[HostPrincipal, int]] = {}
        self._lock = threading.Lock()
        self.identity_bridge = ExternalIdentityBridge(
            verify_token=self._verify_handle,
            lookup_roles=self._lookup_roles,
            trusted_issuer=trusted_issuer,
            token_audience=token_audience,
            attestation_issuer=attestation_issuer,
            signing_key=signing_key,
            clock=self._now,
        )
        self._issuer = trusted_issuer
        self._audience = token_audience

    def _now(self) -> int:
        try:
            v = self._clock()
        except Exception as exc:
            raise AuthorizationDenied("trusted time unavailable") from exc
        if type(v) is not int or v <= 0:
            raise AuthorizationDenied("trusted clock invalid")
        return v

    def _principal(self) -> HostPrincipal:
        now = self._now()
        try:
            access, users = self._access(), self._users()
        except Exception as exc:
            raise AuthorizationDenied("trusted login unavailable") from exc
        if not isinstance(access, Mapping) or not isinstance(users, Mapping):
            raise AuthorizationDenied("trusted login required")
        # Never inherit the main app's OPEN / PREVIEW fallback for the Library.
        if access.get("allowed") is not True or access.get("mode") != "AUTHENTICATED":
            raise AuthorizationDenied("authenticated login required")
        session = access.get("session")
        if not isinstance(session, Mapping):
            raise AuthorizationDenied("authenticated login required")
        user = normalize_username(session.get("username"))
        role = session.get("role")
        if (not user or type(role) is not str or role not in _HOST_ROLES or
                access.get("role") != role or not session_is_current(session, users)):
            raise AuthorizationDenied("local login expired, changed or revoked")
        permissions = session.get("permissions")
        if (type(permissions) not in (tuple, list) or
                not all(type(p) is str for p in permissions) or
                set(permissions) != set(ROLE_PERMISSIONS[role]) or
                len(permissions) != len(ROLE_PERMISSIONS[role])):
            raise AuthorizationDenied("local login permission mismatch")
        issued, last = session.get("authenticated_at"), session.get("last_seen")
        if (type(issued) not in (int, float) or type(last) not in (int, float) or
                not math.isfinite(issued) or not math.isfinite(last) or
                not 0 < issued <= last <= now or
                now - issued > MAX_SESSION_AGE or now - last > MAX_SESSION_IDLE):
            raise AuthorizationDenied("local login idle or expired")
        fingerprint = session.get("credential_fingerprint")
        if type(fingerprint) is not str or not fingerprint:
            raise AuthorizationDenied("login credential identity missing")
        return HostPrincipal(user, role, fingerprint,
                             min(int(issued + MAX_SESSION_AGE), int(last + MAX_SESSION_IDLE)))

    def _new_handle(self) -> str:
        principal = self._principal()
        now = self._now()
        expires = min(now + TOKEN_TTL, principal.expires_at)
        if expires <= now:
            raise AuthorizationDenied("login session expired")
        with self._lock:
            self._sessions = {k: v for k, v in self._sessions.items() if v[1] > now}
            if len(self._sessions) >= MAX_PENDING:
                raise AuthorizationDenied("pending library session limit reached")
            handle = secrets.token_urlsafe(32)
            self._sessions[handle] = (principal, expires)
        return handle

    def _verify_handle(self, handle: str) -> VerifiedSession:
        now = self._now()
        if type(handle) is not str:
            raise AuthorizationDenied("invalid library session handle")
        with self._lock:
            stored = self._sessions.get(handle)
        if stored is None or not now < stored[1]:
            raise AuthorizationDenied("unknown or expired library handle")
        current = self._principal()  # Revalidate active registry, role, expiry and fingerprint.
        prior, expires = stored
        if (prior.username != current.username or prior.role != current.role or
                not hmac.compare_digest(prior.fingerprint, current.fingerprint)):
            raise AuthorizationDenied("library session revoked or changed")
        expiry = min(expires, current.expires_at)
        if expiry <= now:
            raise AuthorizationDenied("library session expired")
        return VerifiedSession(self._issuer, self._audience, current.username, now, expiry)

    def _lookup_roles(self, subject: str, tenant_id: str, domain_id: str) -> object:
        current = self._principal()  # No cached ACL or inherited ADMIN cross-tenant power.
        if subject != current.username:
            raise AuthorizationDenied("authenticated subject changed")
        try:
            allowed = self._membership(subject, tenant_id, domain_id)
        except Exception as exc:
            raise AuthorizationDenied("trusted library membership unavailable") from exc
        if (type(allowed) not in (tuple, frozenset) or not allowed or
                not all(type(v) is str and v in _HOST_ROLES[current.role] for v in allowed)):
            raise AuthorizationDenied("no matching trusted library membership")
        return tuple(sorted(set(allowed)))

    def signed_identity_for_host(self, *, tenant_id: str, domain_id: str,
                                 action: str) -> dict:
        """Trusted host only; user input must never control issuer, key or ACL."""
        return self.identity_bridge.identity_envelope(
            token=self._new_handle(), tenant_id=tenant_id,
            domain_id=domain_id, action=action,
        )

    def read_catalog_for_host(self, *, boundary, tenant_id: str,
                              domain_id: str, entry_id: str):
        """Host-only sandbox read; do not expose raw boundary or this to clients.

        Live login and server ACL are rechecked for each call. Plain reader roles
        may only inspect APPROVED_FOR_INDEXING metadata. Reviewer/admin roles
        with a separate explicit tenant/domain membership may inspect review
        states. This is not a production document-indexing/content endpoint.
        """
        from aion_core.library_authorization import SecuredLibraryBoundary
        if type(boundary) is not SecuredLibraryBoundary:
            raise AuthorizationDenied("trusted document boundary required")
        envelope = self.signed_identity_for_host(
            tenant_id=tenant_id, domain_id=domain_id, action="READ")
        entry = boundary.read(
            tenant_id=tenant_id, domain_id=domain_id, entry_id=entry_id,
            identity_envelope=envelope)
        roles = set(envelope["payload"]["roles"])
        if (entry is not None and entry.state != "APPROVED_FOR_INDEXING" and
                not roles.intersection(("LIBRARY_ADMIN", "LIBRARY_REVIEWER"))):
            return None
        return entry
