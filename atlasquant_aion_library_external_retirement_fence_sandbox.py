"""Unmounted external retirement fence for the AION Library sandbox.

This read-only adapter accepts no caller-supplied authorization facts.
The trusted host supplies a verified CURRENT principal from its independent
authentication+registry bridge, a LIVE independent retirement authority
head, and a separate trustworthy monotonic revision floor. Both external
sources must live OUTSIDE the PostgreSQL snapshot being restored.

This module CANNOT establish that a callback is actually independent,
fresh, authenticated or tamper-resistant: the host/operator must prove those
properties and prevent rollback of its independently archived monotonic
floor. Signed historical evidence ALONE is insufficient. The AtlasQuant V1
login has no durable principal, so DO NOT MOUNT this adapter into runtime.

No network, DDL, secrets, implicit grant, enrollment, retirement or deploy.
"""
from __future__ import annotations

import hmac
import re
from collections.abc import Callable
from dataclasses import dataclass

from aion_core.library_authorization import AuthorizationDenied
from atlasquant_access_control import normalize_username
from atlasquant_aion_library_principal_acl_sandbox import CurrentPrincipal

SCHEMA = "ATLASQUANT_AION_EXTERNAL_RETIREMENT_FENCE_SANDBOX_V1"
_ISSUER = re.compile(r"[a-z][a-z0-9._:-]{2,63}\Z")
_SUBJECT = re.compile(r"[A-Za-z0-9_.:-]{8,128}\Z")
_GENERATION = re.compile(r"[0-9a-f]{32}\Z")
_MAX_REVISION = (1 << 63) - 1


@dataclass(frozen=True)
class ExternalAuthorityHead:
    """Current external authority view, never a cached/signed old checkpoint."""

    issuer: str
    username: str
    subject: str
    account_generation: str
    active: bool
    revision: int


def _deny() -> AuthorizationDenied:
    return AuthorizationDenied("external principal retirement status unavailable")


def _principal_valid(value: object) -> bool:
    return (
        type(value) is CurrentPrincipal
        and type(value.username) is str
        and bool(value.username)
        and value.username == normalize_username(value.username)
        and type(value.issuer) is str
        and _ISSUER.fullmatch(value.issuer) is not None
        and type(value.subject) is str
        and _SUBJECT.fullmatch(value.subject) is not None
        and type(value.account_generation) is str
        and _GENERATION.fullmatch(value.account_generation) is not None
        and value.active is True
    )


def _matching(head: object, principal: CurrentPrincipal, floor: object) -> bool:
    return (
        type(head) is ExternalAuthorityHead
        and type(head.issuer) is str
        and hmac.compare_digest(head.issuer, principal.issuer)
        and type(head.username) is str
        and hmac.compare_digest(head.username, principal.username)
        and type(head.subject) is str
        and hmac.compare_digest(head.subject, principal.subject)
        and type(head.account_generation) is str
        and hmac.compare_digest(
            head.account_generation, principal.account_generation
        )
        and head.active is True
        and type(head.revision) is int
        and type(floor) is int
        and 1 <= floor <= head.revision <= _MAX_REVISION
    )


def _same_principal(left: CurrentPrincipal, right: CurrentPrincipal) -> bool:
    return (
        _principal_valid(right)
        and all(
            hmac.compare_digest(getattr(left, attr), getattr(right, attr))
            for attr in ("username", "issuer", "subject", "account_generation")
        )
    )


class ExternalRetirementFence:
    """A mandatory external read fence before/after registry resolution.

    Pass fence.current_principal to PrincipalBoundPostgresMembership, NEVER
    fall back to registry.current_principal on authority failure. The ACL
    adapter calls this callback twice (before/after each ACL database read).
    This is a sandbox proof of a *host contract*, not a deployed authority.
    """

    def __init__(
        self, *,
        registry_principal: Callable[[], CurrentPrincipal],
        current_authority: Callable[[str, str], ExternalAuthorityHead],
        minimum_revision: Callable[[str, str], int],
    ):
        if (
            not callable(registry_principal)
            or not callable(current_authority)
            or not callable(minimum_revision)
        ):
            raise _deny()
        self._registry = registry_principal
        self._current_authority = current_authority
        self._floor = minimum_revision

    def _external_check(
        self, principal: CurrentPrincipal,
    ) -> tuple[ExternalAuthorityHead, int]:
        # External authority and its monotonic floor are separately entrusted
        # to the SERVER, never derived from the restorable document/ACL DB.
        floor = self._floor(principal.issuer, principal.username)
        head = self._current_authority(principal.issuer, principal.username)
        if not _matching(head, principal, floor):
            raise _deny()
        return head, floor

    def current_principal(self) -> CurrentPrincipal:
        try:
            before = self._registry()
            if not _principal_valid(before):
                raise _deny()
            head1, floor1 = self._external_check(before)
            after = self._registry()
            if not _same_principal(before, after):
                raise _deny()
            head2, floor2 = self._external_check(after)
            if (
                head1 != head2 or floor2 < floor1
                or floor1 > head2.revision
                or floor2 > head2.revision
            ):
                # An external change during a read requires a fresh request.
                raise _deny()
            return after
        except Exception as exc:
            raise _deny() from exc


__all__ = ("SCHEMA", "ExternalAuthorityHead", "ExternalRetirementFence")
