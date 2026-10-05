"""AION V2.13 trust-root registry.

Loads only public Ed25519 verification keys from a bounded, local JSON file.
This module never creates, reads, stores, or exports private-key material.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "ATLASQUANT_AION_TRUST_ROOT_V1"
MAX_FILE_BYTES = 131_072
MAX_ROOTS = 128
ALGORITHM = "Ed25519"
STATUSES = {"ACTIVE", "RETIRED", "REVOKED"}


def _strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _parse_ts(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC3339 UTC")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc


def _b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("base64url value required")
    try:
        raw = value.encode("ascii")
        return base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except Exception as exc:
        raise ValueError("invalid base64url") from exc


@dataclass(frozen=True)
class TrustRootEntry:
    key_id: str
    key_version: int
    algorithm: str
    public_key_b64: str
    status: str
    not_before: str
    not_after: str

    def public_key(self) -> Ed25519PublicKey:
        raw = _b64url_decode(self.public_key_b64)
        if len(raw) != 32:
            raise ValueError("Ed25519 public key must be 32 bytes")
        return Ed25519PublicKey.from_public_bytes(raw)

    def active_at(self, now_ts: str) -> bool:
        now = _parse_ts(now_ts)
        return (
            self.status == "ACTIVE"
            and _parse_ts(self.not_before) <= now <= _parse_ts(self.not_after)
        )


class TrustRootRegistry:
    def __init__(self, entries: tuple[TrustRootEntry, ...], revoked_key_ids=frozenset()):
        if not entries:
            raise ValueError("at least one trust root is required")
        if len(entries) > MAX_ROOTS:
            raise ValueError("too many trust roots")
        seen = set()
        mapping = {}
        for entry in entries:
            key = (entry.key_id, entry.key_version)
            if key in seen:
                raise ValueError("duplicate key id/version")
            seen.add(key)
            if not entry.key_id or len(entry.key_id) > 128:
                raise ValueError("invalid key_id")
            if not isinstance(entry.key_version, int) or isinstance(entry.key_version, bool) or entry.key_version < 1:
                raise ValueError("invalid key_version")
            if entry.algorithm != ALGORITHM:
                raise ValueError("unsupported algorithm")
            if entry.status not in STATUSES:
                raise ValueError("invalid key status")
            if _parse_ts(entry.not_before) > _parse_ts(entry.not_after):
                raise ValueError("invalid key validity window")
            entry.public_key()
            mapping[key] = entry
        self._entries = mapping
        self._revoked = frozenset(str(v) for v in revoked_key_ids if str(v))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "TrustRootRegistry":
        if not isinstance(payload, Mapping):
            raise ValueError("trust root payload must be a mapping")
        if payload.get("schema") != SCHEMA:
            raise ValueError("trust root schema mismatch")
        roots = payload.get("roots")
        if not isinstance(roots, list):
            raise ValueError("roots must be a list")
        entries = []
        allowed = {
            "key_id", "key_version", "algorithm", "public_key_b64",
            "status", "not_before", "not_after",
        }
        for item in roots:
            if not isinstance(item, Mapping) or set(item) != allowed:
                raise ValueError("trust root entry shape mismatch")
            entries.append(TrustRootEntry(**dict(item)))
        revoked = payload.get("revoked_key_ids", [])
        if not isinstance(revoked, list):
            raise ValueError("revoked_key_ids must be a list")
        return cls(tuple(entries), frozenset(revoked))

    @classmethod
    def from_json_file(cls, path: str | Path) -> "TrustRootRegistry":
        p = Path(path)
        if p.is_symlink():
            raise ValueError("trust root file must not be a symlink")
        data = p.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("trust root file oversized")
        try:
            payload = json.loads(data.decode("utf-8"), object_pairs_hook=_strict_pairs)
        except Exception as exc:
            raise ValueError("invalid trust root JSON") from exc
        return cls.from_mapping(payload)

    def lookup(self, key_id: str, key_version: int) -> TrustRootEntry | None:
        return self._entries.get((key_id, key_version))

    def is_revoked(self, entry: TrustRootEntry) -> bool:
        return entry.status == "REVOKED" or entry.key_id in self._revoked

    def verify_key_available(self, key_id: str, key_version: int, now_ts: str) -> tuple[TrustRootEntry | None, str | None]:
        entry = self.lookup(key_id, key_version)
        if entry is None:
            return None, "TRUST_KEY_UNKNOWN"
        if self.is_revoked(entry):
            return entry, "TRUST_KEY_REVOKED"
        if not entry.active_at(now_ts):
            return entry, "TRUST_KEY_NOT_ACTIVE"
        return entry, None

    @property
    def key_count(self) -> int:
        return len(self._entries)
