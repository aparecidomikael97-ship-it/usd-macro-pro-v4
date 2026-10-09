"""AION HUMAN_OWNER-only, explicit-scope Windows silent CNG algorithm check.

Executable on owner Windows ONLY after independent conversational owner
approval for this exact read-only probe and device selection by the
authorized Remote Desktop Commander connection. An opt-in parameter is
NOT cryptographic owner identity and must not be treated as authorization
to enroll private keys, change configuration, resume or install.

Calls exactly the fixed native silent signature-algorithm enumeration core
from #1103, with no key enumeration, no file writes, no zero-flags retry.
"""
from __future__ import annotations

import re
import sys
from typing import Any

from atlasquant_aion_native_cng_silent_signature_algorithm_enum_v1 import (
    _base, _probe_silent_signature_algorithms_native_core,
)

PHYSICAL_SCOPE = "OWNER_APPROVED_SINGLE_READONLY_SILENT_SIGNATURE_ENUM_V1"
_NONCE = re.compile(r"[0-9a-f]{64}\Z")


def observe_owner_silent_signature_algorithms_readonly(
    challenge_nonce: str,
    *,
    explicit_owner_authorization_for_this_probe: bool = False,
    authorized_device_scope: str = "",
) -> dict[str, Any]:
    """One bounded diagnostic, not a protected owner authentication step."""
    if sys.platform != "win32":
        return _base("WINDOWS_REQUIRED")
    if (explicit_owner_authorization_for_this_probe is not True
        or authorized_device_scope != PHYSICAL_SCOPE):
        return _base("EXPLICIT_OWNER_SCOPED_READONLY_AUTHORIZATION_REQUIRED")
    if type(challenge_nonce) is not str or not _NONCE.fullmatch(challenge_nonce):
        return _base("EXPLICIT_256_BIT_CHALLENGE_REQUIRED")
    # Reuse the exact native code approved by CI without spoofing GitHub
    # environment variables or disabling #1103's CI-only wrapper.
    return _probe_silent_signature_algorithms_native_core()


__all__ = (
    "PHYSICAL_SCOPE", "observe_owner_silent_signature_algorithms_readonly",
)
