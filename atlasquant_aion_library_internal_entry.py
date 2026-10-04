"""Internal, unmounted AtlasQuant AION Library selection boundary (SANDBOX V1).

A public route or Streamlit widget MUST NOT construct this class. A trusted
server chooses aliases -> (tenant, domain, entry) via a current server-owned
provider. Underlying assembly rechecks current login, real PostgreSQL tenant
membership and document audit for EVERY request; there is no cached decision.
No document content, hashes, signing keys, raw DB/identity objects or download
links can leave this boundary. Zero automatic activation or migrations.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from aion_core.library_authorization import AuthorizationDenied
from atlasquant_aion_library_postgres_preview import LibraryPanelPreview
from atlasquant_aion_library_server_assembly import SandboxLibraryServerReadAssembly

SCHEMA = "ATLASQUANT_AION_LIBRARY_INTERNAL_SELECTION_SANDBOX_V1"
_ALIAS = re.compile(r"[A-Za-z0-9_.:-]{1,48}\Z")
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_STATES = frozenset(("METADATA_REVIEW", "APPROVED_FOR_INDEXING"))


def _denied():
    return AuthorizationDenied("library selection unavailable")


@dataclass(frozen=True)
class LibrarySelectionStatus:
    """Allowlisted status only; no raw IDs/content or private audit details."""
    selection: str
    state: str
    version: int
    integrity_checked: bool


class TrustedLibraryAppSelection:
    """Trusted host-owned alias resolver and exact server assembly only.

    The resolver is a protected server callback, NEVER a browser-supplied
    mapping, session_state value or prompt-controlled function. A public UI
    must not expose this object or its constructor to remote callers.
    """

    def __init__(self, *, assembly: SandboxLibraryServerReadAssembly,
                 resolve_selection: Callable[[str], tuple[str, str, str]]):
        if type(assembly) is not SandboxLibraryServerReadAssembly or not callable(resolve_selection):
            raise _denied()
        self._assembly = assembly
        self._resolve = resolve_selection

    def _trusted_target(self, selection: str) -> tuple[str, str, str]:
        if type(selection) is not str or _ALIAS.fullmatch(selection) is None:
            raise _denied()
        try:
            result = self._resolve(selection)
        except Exception as exc:
            raise _denied() from exc
        if (type(result) is not tuple or len(result) != 3 or
                not all(type(value) is str and _ID.fullmatch(value) is not None for value in result)):
            raise _denied()
        return result

    def preview_for_host(self, *, selection: str) -> LibrarySelectionStatus:
        """No caching: authorizations/aliases are re-evaluated on each call."""
        target = self._trusted_target(selection)
        try:
            result = self._assembly.read_preview(
                tenant_id=target[0], domain_id=target[1], entry_id=target[2])
            # Don't reveal a result if the server's selection was withdrawn or
            # remapped during the DB read. Underlying assembly also rechecks
            # SANDBOX flag, login and fresh SQL ACL on its own return path.
            if self._trusted_target(selection) != target:
                raise _denied()
            if (type(result) is not LibraryPanelPreview or
                    result.entry_id != target[2] or
                    result.integrity_checked is not True or
                    type(result.version) is not int or result.version < 1 or
                    result.state not in _STATES):
                raise _denied()
            return LibrarySelectionStatus(selection, result.state, result.version, True)
        except Exception as exc:
            raise _denied() from exc


__all__ = ["SCHEMA", "LibrarySelectionStatus", "TrustedLibraryAppSelection"]
