"""Fail-closed server-bound selection for the AION Library sandbox reader.

This is NOT an endpoint. Host must own the selection provider; it must NEVER
be constructed from a client-supplied tuple, session state, query parameter,
prompt, or document search result. No content bytes or document discovery.
"""
from __future__ import annotations

import re
from collections.abc import Callable

from aion_core.library_authorization import AuthorizationDenied
from atlasquant_aion_library_postgres_preview import LibraryPanelPreview
from atlasquant_aion_library_server_assembly import SandboxLibraryServerReadAssembly

SCHEMA = "ATLASQUANT_AION_LIBRARY_TRUSTED_SELECTION_SANDBOX_V1"
_SCOPE = re.compile(r"[A-Za-z0-9_.:-]{1,64}\Z")
_ENTRY = re.compile(r"[A-Za-z0-9_.:-]{1,28}\Z")


def _denied() -> AuthorizationDenied:
    return AuthorizationDenied("sandbox Library selection unavailable")


class SandboxServerSelectedRead:
    """Server-held exact scope, checked both before and after an audited read.

    Security depends on keeping the assembly and selection provider private to
    a trusted host. Constructing this class does NOT grant a role or create a
    trusted selection. The reader has no caller-controlled scope arguments.
    """

    def __init__(self, *, assembly: SandboxLibraryServerReadAssembly,
                 trusted_selection_provider: Callable[[], tuple[str, str, str]]):
        if (type(assembly) is not SandboxLibraryServerReadAssembly or
                not callable(trusted_selection_provider)):
            raise _denied()
        self._assembly = assembly
        self._selection_provider = trusted_selection_provider

    def _current_selection(self) -> tuple[str, str, str]:
        try:
            selection = self._selection_provider()
        except Exception as exc:
            raise _denied() from exc
        if (type(selection) is not tuple or len(selection) != 3 or
                any(type(value) is not str for value in selection) or
                _SCOPE.fullmatch(selection[0]) is None or
                _SCOPE.fullmatch(selection[1]) is None or
                _ENTRY.fullmatch(selection[2]) is None):
            raise _denied()
        return selection

    def read_selected(self) -> LibraryPanelPreview:
        """Returns four bounded metadata fields; never document content or IDs selected by caller."""
        before = self._current_selection()
        try:
            result = self._assembly.read_preview(
                tenant_id=before[0], domain_id=before[1], entry_id=before[2],
            )
            after = self._current_selection()
            if (before != after or type(result) is not LibraryPanelPreview or
                    result.entry_id != before[2] or type(result.version) is not int or
                    result.version < 1 or result.integrity_checked is not True or
                    result.state not in {"METADATA_REVIEW", "APPROVED_FOR_INDEXING"}):
                raise _denied()
            return result
        except Exception as exc:
            # Do not reveal whether the entry, tenant, user, license or audit exists.
            raise _denied() from exc


__all__ = ["SCHEMA", "SandboxServerSelectedRead"]
