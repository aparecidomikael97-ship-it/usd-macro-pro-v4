"""Fail-closed staging boundary for action payload identity (A89 LAB).

This only validates local, future action intents. It does NOT enroll a
producer, authorize action execution, verify a signature, or prove no effect.
No secret-bearing original payload or derived secret digest is persisted.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping
from unicodedata import normalize

from aion_chat.privacy import redact

INVALID = "ACTION_PAYLOAD_NOT_CANONICAL_JSON"
REDACTED = "REDACTED_PAYLOAD_NOT_STAGEABLE"
MAX_PAYLOAD_DEPTH = 32

# Names of credential-bearing JSON fields in common HTTP/API payloads.
# This is an intentionally conservative staging gate, NOT general DLP.
# Do not redact first and hash/store a credential-derived action identity.
CREDENTIAL_KEY_ALIASES = frozenset({
    "authorization", "accesstoken", "refreshtoken", "clientsecret",
    "privatekey", "sessiontoken", "bearertoken", "authtoken",
    "apikey", "xapikey", "cookie", "setcookie",
    "password", "senha", "token", "credential", "secret",
    # A96: concrete credential-bearing HTTP and cloud API field names.
    # Do not confuse these with harmless *_ref metadata fields.
    "proxyauthorization", "xauthtoken", "xamzsecuritytoken",
    "xgoogapikey", "awssecretaccesskey",
})


def _credential_key(name: str) -> bool:
    # Recognize ordinary snake/kebab/camel/HTTP-header variants, including
    # Unicode compatibility forms. Benign suffixes (e.g. authorization_ref)
    # are NOT matched; field-name matching is exact after normalization.
    normalized = normalize("NFKC", name).casefold()
    compact = "".join(c for c in normalized if c.isascii() and c.isalnum())
    return compact in CREDENTIAL_KEY_ALIASES


def _validate_json(value: Any, *, depth: int, active: set[int]) -> None:
    """Require native, finite JSON types; never stringify unknown objects."""
    if depth > MAX_PAYLOAD_DEPTH:
        raise ValueError(INVALID)
    kind = type(value)
    if kind in (str, int, bool) or value is None:
        return
    if kind is float:
        if not isfinite(value):
            raise ValueError(INVALID)
        return
    if kind is dict or kind is list:
        key = id(value)
        if key in active:
            raise ValueError(INVALID)
        active.add(key)
        try:
            if kind is dict:
                for name, item in value.items():
                    if type(name) is not str:
                        raise ValueError(INVALID)
                    # A95: privacy.redact does not recognize every standard
                    # credential HEADER/KEY. Deny before any SQLite mutation
                    # regardless of the value's formatting or nesting.
                    if _credential_key(name):
                        raise ValueError(REDACTED)
                    _validate_json(item, depth=depth + 1, active=active)
            else:
                for item in value:
                    _validate_json(item, depth=depth + 1, active=active)
        finally:
            active.remove(key)
        return
    raise ValueError(INVALID)


def clean_action_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Reject lossy or redacted intent BEFORE its digest or SQLite write.

    A JSON-native value is necessary, not sufficient, for complete DLP.
    If any credential redaction changes the payload, there is no canonical
    identity-preserving commitment for it in this staging implementation.
    """
    if payload is None:
        raw: dict[str, Any] = {}
    elif isinstance(payload, Mapping):
        raw = dict(payload)
    else:
        raise ValueError(INVALID)
    _validate_json(raw, depth=0, active=set())
    safe = redact(raw)
    if safe != raw:
        raise ValueError(REDACTED)
    return safe
