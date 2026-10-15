"""Fail-closed staging boundary for action payload identity (A89 LAB).

This only validates local, future action intents. It does NOT enroll a
producer, authorize action execution, verify a signature, or prove no effect.
No secret-bearing original payload or derived secret digest is persisted.
"""
from __future__ import annotations

import json
from math import isfinite
from typing import Any, Mapping
from unicodedata import normalize

from aion_chat.privacy import redact

INVALID = "ACTION_PAYLOAD_NOT_CANONICAL_JSON"
REDACTED = "REDACTED_PAYLOAD_NOT_STAGEABLE"
MAX_PAYLOAD_DEPTH = 32
# A103 LAB: conservative admission budgets for future local action intents.
# Applied before redaction, digest, and persistent SQLite staging.
MAX_PAYLOAD_NODE_COUNT = 4096
MAX_PAYLOAD_TOTAL_UTF8_BYTES = 256 * 1024
MAX_PAYLOAD_SCALAR_UTF8_BYTES = 64 * 1024
MAX_PAYLOAD_KEY_UTF8_BYTES = 1024
MAX_INTEGER_BITS = 512

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


def _charge_text(value: str, *, limit: int, budget: list[int]) -> None:
    # len() first avoids an unbounded UTF-8 allocation for huge ASCII text.
    if len(value) > limit:
        raise ValueError(INVALID)
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        # Ill-formed Unicode is not a portable identity for an action.
        raise ValueError(INVALID) from None
    if size > limit or budget[1] + size > MAX_PAYLOAD_TOTAL_UTF8_BYTES:
        raise ValueError(INVALID)
    budget[1] += size


def _validate_json(
    value: Any, *, depth: int, active: set[int], budget: list[int],
) -> None:
    """Require native JSON types, bounded structure, valid UTF-8 and finite numbers."""
    if depth > MAX_PAYLOAD_DEPTH:
        raise ValueError(INVALID)
    budget[0] += 1
    if budget[0] > MAX_PAYLOAD_NODE_COUNT:
        raise ValueError(INVALID)
    kind = type(value)
    if kind is str:
        _charge_text(value, limit=MAX_PAYLOAD_SCALAR_UTF8_BYTES, budget=budget)
        return
    if kind is bool or value is None:
        return
    if kind is int:
        # Reject giant integer scalars before int->decimal conversion.
        if value.bit_length() > MAX_INTEGER_BITS:
            raise ValueError(INVALID)
        _charge_text(str(value), limit=MAX_PAYLOAD_SCALAR_UTF8_BYTES, budget=budget)
        return
    if kind is float:
        if not isfinite(value):
            raise ValueError(INVALID)
        _charge_text(repr(value), limit=MAX_PAYLOAD_SCALAR_UTF8_BYTES, budget=budget)
        return
    if kind is dict or kind is list:
        ident = id(value)
        if ident in active:
            raise ValueError(INVALID)
        active.add(ident)
        try:
            if kind is dict:
                for name, item in value.items():
                    if type(name) is not str:
                        raise ValueError(INVALID)
                    _charge_text(name, limit=MAX_PAYLOAD_KEY_UTF8_BYTES, budget=budget)
                    if _credential_key(name):
                        raise ValueError(REDACTED)
                    _validate_json(item, depth=depth + 1, active=active, budget=budget)
            else:
                for item in value:
                    _validate_json(item, depth=depth + 1, active=active, budget=budget)
        finally:
            active.remove(ident)
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
    _validate_json(raw, depth=0, active=set(), budget=[0, 0])
    safe = redact(raw)
    if safe != raw:
        raise ValueError(REDACTED)
    # Raw byte/node budgets prevent explosion during redact(); exact canonical
    # UTF-8 size additionally fences serialization expansion before the digest.
    encoded = json.dumps(
        safe, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_TOTAL_UTF8_BYTES:
        raise ValueError(INVALID)
    return safe
