"""Offline custody evidence for synthetic Library backup rehearsals.

Not a backup engine, durable archive, restore endpoint or production signature.
The trusted host must keep evidence/HMAC key outside the archived DB and must
supply and vet archive streams; an attacker with custody of both backup and
signing key can forge this record. Never accept paths from untrusted clients.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import time
from dataclasses import dataclass
from typing import BinaryIO, Callable

from .library_authorization import AuthorizationDenied, _encode
from .library_recovery_gate import SignedCheckpoint

SCHEMA = "AION_LIBRARY_BACKUP_CUSTODY_V1"
_HEX = re.compile(r"[a-f0-9]{64}\Z")
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024  # demo cap; actual backups need reviewed config
_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class ArchiveDigest:
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class SealedBackupEvidence:
    payload: dict
    mac_sha256: str


def archive_digest(stream: BinaryIO, *, max_bytes: int = MAX_ARCHIVE_BYTES) -> ArchiveDigest:
    """Stream bounded bytes without buffering or exposing source content."""
    if (not callable(getattr(stream, "read", None)) or type(max_bytes) is not int
            or not 1 <= max_bytes <= MAX_ARCHIVE_BYTES):
        raise AuthorizationDenied("trusted bounded archive stream required")
    size, digest = 0, hashlib.sha256()
    while True:
        try:
            block = stream.read(min(_CHUNK, max_bytes - size + 1))
        except Exception as exc:
            raise AuthorizationDenied("archive unreadable") from exc
        if type(block) is not bytes:
            raise AuthorizationDenied("archive stream did not return bytes")
        if not block:
            break
        size += len(block)
        if size > max_bytes:
            raise AuthorizationDenied("archive size limit exceeded")
        digest.update(block)
    if size == 0:
        raise AuthorizationDenied("empty archive is invalid")
    return ArchiveDigest(digest.hexdigest(), size)


def _checkpoint_digest(checkpoint: SignedCheckpoint) -> str:
    if (type(checkpoint) is not SignedCheckpoint or type(checkpoint.payload) is not dict
            or type(checkpoint.mac_sha256) is not str or
            _HEX.fullmatch(checkpoint.mac_sha256) is None):
        raise AuthorizationDenied("checkpoint required")
    try:
        return hashlib.sha256(_encode({"payload": checkpoint.payload,
                                       "mac_sha256": checkpoint.mac_sha256})).hexdigest()
    except Exception as exc:
        raise AuthorizationDenied("invalid checkpoint") from exc


def _key(key: bytes):
    if type(key) is not bytes or len(key) < 32:
        raise AuthorizationDenied("independent evidence signing key required")


def seal_backup(*, archive: ArchiveDigest, checkpoint: SignedCheckpoint,
                signing_key: bytes, clock: Callable[[], int] | None = None) -> SealedBackupEvidence:
    """Trusted host operation. Keep result OFF the backed-up database."""
    _key(signing_key)
    if (type(archive) is not ArchiveDigest or type(archive.sha256) is not str or
            _HEX.fullmatch(archive.sha256) is None or type(archive.size_bytes) is not int
            or not 1 <= archive.size_bytes <= MAX_ARCHIVE_BYTES):
        raise AuthorizationDenied("invalid archive digest")
    stamp = (clock or (lambda: int(time.time())))()
    if type(stamp) is not int or stamp < 0:
        raise AuthorizationDenied("trusted clock required")
    payload = {"schema": SCHEMA, "archive_sha256": archive.sha256,
               "archive_size_bytes": archive.size_bytes,
               "checkpoint_sha256": _checkpoint_digest(checkpoint),
               "issued_at": stamp}
    mac = hmac.new(signing_key, _encode(payload), hashlib.sha256).hexdigest()
    return SealedBackupEvidence(payload, mac)


def verify_backup(*, evidence: SealedBackupEvidence, archive: ArchiveDigest,
                  checkpoint: SignedCheckpoint, trusted_key: bytes,
                  clock: Callable[[], int] | None = None) -> bool:
    """Validate *external* evidence + stream digest; restore must independently
    compare checkpoint to restored DB via LibraryRecoveryGate afterward.
    """
    _key(trusted_key)
    if (type(evidence) is not SealedBackupEvidence or type(evidence.payload) is not dict
            or set(evidence.payload) != {"schema", "archive_sha256", "archive_size_bytes",
                                          "checkpoint_sha256", "issued_at"}
            or type(evidence.mac_sha256) is not str
            or _HEX.fullmatch(evidence.mac_sha256) is None):
        raise AuthorizationDenied("malformed backup evidence")
    fields = evidence.payload
    now = (clock or (lambda: int(time.time())))()
    if (type(now) is not int or now < 0 or fields["schema"] != SCHEMA or
            type(fields["issued_at"]) is not int or not 0 <= fields["issued_at"] <= now or
            type(fields["archive_sha256"]) is not str or
            _HEX.fullmatch(fields["archive_sha256"]) is None or
            type(fields["archive_size_bytes"]) is not int or
            not 1 <= fields["archive_size_bytes"] <= MAX_ARCHIVE_BYTES or
            type(fields["checkpoint_sha256"]) is not str or
            _HEX.fullmatch(fields["checkpoint_sha256"]) is None):
        raise AuthorizationDenied("invalid backup custody metadata")
    expected_mac = hmac.new(trusted_key, _encode(fields), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_mac, evidence.mac_sha256):
        raise AuthorizationDenied("backup evidence signature mismatch")
    if (type(archive) is not ArchiveDigest or type(archive.sha256) is not str
            or _HEX.fullmatch(archive.sha256) is None or type(archive.size_bytes) is not int
            or not hmac.compare_digest(archive.sha256, fields["archive_sha256"]) or
            archive.size_bytes != fields["archive_size_bytes"] or
            not hmac.compare_digest(_checkpoint_digest(checkpoint), fields["checkpoint_sha256"])):
        raise AuthorizationDenied("backup archive or checkpoint mismatch")
    return True
