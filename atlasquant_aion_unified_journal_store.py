"""Physical durable store for the AION unified request journal.

The logical journal remains authoritative for event semantics and integrity.
This module only persists verified journal events and reconstructs verified
state after restart. Persistence never grants approval, executes an action,
promotes memory, or writes Checkpoint Mestre.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import errno
import json
import os
from pathlib import Path, PureWindowsPath
import re
import time
import unicodedata
from typing import Any, Callable, Mapping
from uuid import uuid4

from aion_chat.models import Scope
from atlasquant_aion_unified_journal import (
    GENESIS,
    SCHEMA as JOURNAL_SCHEMA,
    verify_request_journal,
)


STORE_SCHEMA = "ATLASQUANT_AION_UNIFIED_JOURNAL_STORE_V2"
PERSISTENCE_VERSION = 2

STAGED = "STAGED"
JOURNALED = "JOURNALED"
DURABLE = "DURABLE"
ACKNOWLEDGED = "ACKNOWLEDGED"
QUARANTINED = "QUARANTINED"
REJECTED = "REJECTED"
PERSISTENCE_STATES = frozenset(
    {STAGED, JOURNALED, DURABLE, ACKNOWLEDGED, QUARANTINED, REJECTED}
)

MAX_EVENT_BYTES = 128 * 1024
MAX_METADATA_BYTES = 64 * 1024
MAX_INDEX_BYTES = 256 * 1024
MAX_IDEMPOTENCY_KEY = 256
MAX_RECOVERY_EVENTS = 256
DEFAULT_LOCK_TIMEOUT = 5.0

_EVENT_NAME = re.compile(r"^(?P<sequence>[0-9]{8})_(?P<digest>[0-9a-f]{64})\.json$")
_DIGEST = re.compile(r"^sha256:(?P<hex>[0-9a-f]{64})$")


class JournalStoreError(RuntimeError):
    """Base error for durable journal persistence."""

    reason_code = "UNSAFE_PATH"

    def __init__(self, detail: str = "", *, reason_code: str | None = None):
        self.reason_detail = _reason_detail(detail)
        if reason_code is not None:
            self.reason_code = str(reason_code)
        super().__init__(self.reason_detail or self.reason_code)


class JournalStoreIntegrityError(JournalStoreError):
    """Raised when durable state cannot be trusted."""


class JournalStoreConflict(JournalStoreError):
    """Raised when an idempotency key or immutable record conflicts."""


class JournalStoreLockTimeout(JournalStoreError):
    """Raised when a per-request lock cannot be acquired in time."""

    reason_code = "LOCK_TIMEOUT"


class SimulatedCrash(BaseException):
    """Test-only fault used to model process death without cleanup."""


REASON_CODES = frozenset({
    "CORRUPT_JSON",
    "RECORD_DIGEST_MISMATCH",
    "EVENT_DIGEST_MISMATCH",
    "PREV_DIGEST_MISMATCH",
    "SEQUENCE_MISMATCH",
    "SCOPE_MISMATCH",
    "REQUEST_MISMATCH",
    "PERSISTENCE_VERSION_MISMATCH",
    "HEAD_POINTS_TO_MISSING_EVENT",
    "ACK_INVALID",
    "IDEMPOTENCY_INDEX_MISMATCH",
    "SYMLINK_ESCAPE",
    "UNSAFE_PATH",
    "ORPHAN_TEMP",
    "STALE_HEAD",
    "LOCK_TIMEOUT",
    "RECOVERY_LIMIT_EXCEEDED",
    "IDEMPOTENCY_INDEX_STALE",
    "REQUEST_QUARANTINED",
})
# Hard failures block safe_to_resume; everything else is a warning.
HARD_FAILURE_CODES = frozenset({
    "CORRUPT_JSON",
    "RECORD_DIGEST_MISMATCH",
    "EVENT_DIGEST_MISMATCH",
    "PREV_DIGEST_MISMATCH",
    "SEQUENCE_MISMATCH",
    "SCOPE_MISMATCH",
    "REQUEST_MISMATCH",
    "PERSISTENCE_VERSION_MISMATCH",
    "HEAD_POINTS_TO_MISSING_EVENT",
    "ACK_INVALID",
    "IDEMPOTENCY_INDEX_MISMATCH",
    "SYMLINK_ESCAPE",
    "UNSAFE_PATH",
})
QUARANTINE_MANIFEST_SCHEMA = "ATLASQUANT_AION_UNIFIED_JOURNAL_QUARANTINE_MANIFEST_V1"
QUARANTINE_MANIFEST_MAX_BYTES = 256 * 1024


def _reason_code(message: str) -> str:
    text = str(message or "").strip().lower()
    if "corrupt" in text:
        return "CORRUPT_JSON"
    if "record digest" in text:
        return "RECORD_DIGEST_MISMATCH"
    if "event digest" in text or "digest reference" in text or "filename digest" in text:
        return "EVENT_DIGEST_MISMATCH"
    if "previous digest" in text or "chain mismatch" in text or "prev_digest" in text:
        return "PREV_DIGEST_MISMATCH"
    if "sequence" in text:
        return "SEQUENCE_MISMATCH"
    if "scope" in text:
        return "SCOPE_MISMATCH"
    if "request" in text or "conversation" in text:
        return "REQUEST_MISMATCH"
    if "version" in text:
        return "PERSISTENCE_VERSION_MISMATCH"
    if "symlink" in text:
        return "SYMLINK_ESCAPE"
    if "path" in text or "unsafe" in text:
        return "UNSAFE_PATH"
    if "capacity" in text or "limit" in text:
        return "RECOVERY_LIMIT_EXCEEDED"
    if "head" in text and ("missing" in text or "different" in text):
        return "HEAD_POINTS_TO_MISSING_EVENT"
    if "head" in text:
        return "STALE_HEAD"
    if "ack" in text:
        return "ACK_INVALID"
    if "idempotency" in text:
        return "IDEMPOTENCY_INDEX_MISMATCH"
    return "UNSAFE_PATH" if "path" in text else "CORRUPT_JSON"


def _reason_detail(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    return text[:limit]


class JournalStoreRejected(JournalStoreConflict):
    """Operation rejected by contract (no persisted corruption implied)."""

    state = REJECTED

    def __init__(self, reason_code: str, detail: str = ""):
        self.reason_code = str(reason_code)
        self.reason_detail = _reason_detail(detail)
        super().__init__(f"{self.reason_code}: {self.reason_detail}" or self.reason_code)


def _scan_failure(reasons: list[str]) -> "JournalStoreIntegrityError":
    """Build a scan failure carrying the first causal reason code."""
    exc = JournalStoreIntegrityError(";".join(reasons))
    exc.reason_code = str(reasons[0]) if reasons else "CORRUPT_JSON"
    return exc


def _integrity_failure(reason_code: str, detail: str) -> JournalStoreIntegrityError:
    error = JournalStoreIntegrityError(_reason_detail(detail))
    error.reason_code = str(reason_code)
    error.reason_detail = _reason_detail(detail)
    return error




def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _raw_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _scope_payload(scope: Scope) -> dict[str, str]:
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    return {
        "owner_id": scope.owner_id,
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
    }


def _validate_identifier(value: Any, label: str, *, limit: int = 256) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        raise ValueError(f"{label} required")
    if len(normalized) > limit:
        raise ValueError(f"{label} too long")
    if "\x00" in normalized:
        raise ValueError(f"{label} contains NUL")
    win = PureWindowsPath(normalized)
    if (
        "/" in normalized
        or "\\" in normalized
        or normalized in {".", ".."}
        or win.is_absolute()
        or bool(win.drive)
        or normalized.startswith("//")
        or normalized.startswith("\\\\")
    ):
        raise ValueError(f"{label} contains unsafe path syntax")
    return normalized


def _event_digest_hex(value: str) -> str:
    match = _DIGEST.fullmatch(str(value or ""))
    if not match:
        raise JournalStoreIntegrityError("invalid event digest")
    return match.group("hex")


def _safe_id(prefix: str, value: str) -> str:
    return f"{prefix}-{_raw_digest(value)[:40]}"


def _record_digest(record: Mapping[str, Any]) -> str:
    body = dict(record)
    body.pop("record_digest", None)
    return _digest(body)


def _bounded_json(value: Mapping[str, Any], limit: int, label: str) -> bytes:
    data = (_canonical(dict(value)) + "\n").encode("utf-8")
    if len(data) > limit:
        raise ValueError(f"{label} exceeds persistence limit")
    return data


def _fsync_dir(path: Path) -> None:
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        fd = os.open(str(path), flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError as exc:
        if exc.errno not in {
            errno.EBADF,
            errno.EINVAL,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }:
            raise
    finally:
        os.close(fd)


class _FileLock:
    def __init__(self, path: Path, timeout: float):
        self.path = path
        self.timeout = timeout
        self.handle = None

    def __enter__(self):
        deadline = time.monotonic() + self.timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a+b")
        if self.handle.tell() == 0:
            self.handle.write(b"\0")
            self.handle.flush()
        while True:
            try:
                self._acquire()
                return self
            except (BlockingIOError, OSError) as exc:
                if isinstance(exc, OSError) and exc.errno not in {
                    errno.EACCES,
                    errno.EAGAIN,
                    getattr(errno, "EDEADLK", errno.EAGAIN),
                }:
                    self.handle.close()
                    self.handle = None
                    raise
                if time.monotonic() >= deadline:
                    self.handle.close()
                    self.handle = None
                    raise JournalStoreLockTimeout("request lock timeout") from exc
                time.sleep(0.02)

    def _acquire(self):
        if os.name == "nt":
            import msvcrt

            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def __exit__(self, exc_type, exc, tb):
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


class UnifiedJournalStore:
    """Append-only physical persistence for verified unified journal events."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT,
        max_event_bytes: int = MAX_EVENT_BYTES,
        max_metadata_bytes: int = MAX_METADATA_BYTES,
        max_recovery_events: int = MAX_RECOVERY_EVENTS,
        fault_injector: Callable[[str, Mapping[str, Any]], None] | None = None,
    ):
        raw_root = Path(root)
        if raw_root.exists() and raw_root.is_symlink():
            raise ValueError("journal store root cannot be a symlink")
        raw_root.mkdir(parents=True, exist_ok=True)
        self.root = raw_root.resolve()
        if not self.root.is_dir():
            raise ValueError("journal store root must be a directory")
        self.lock_timeout = float(lock_timeout)
        if self.lock_timeout <= 0:
            raise ValueError("lock_timeout must be positive")
        self.max_event_bytes = int(max_event_bytes)
        self.max_metadata_bytes = int(max_metadata_bytes)
        self.max_recovery_events = min(int(max_recovery_events), MAX_RECOVERY_EVENTS)
        if min(self.max_event_bytes, self.max_metadata_bytes, self.max_recovery_events) <= 0:
            raise ValueError("persistence limits must be positive")
        self.fault_injector = fault_injector

    def _fault(self, stage: str, context: Mapping[str, Any]) -> None:
        if self.fault_injector is not None:
            self.fault_injector(stage, dict(context))

    def _scope_key(self, scope: Scope) -> tuple[dict[str, str], str]:
        identity = _scope_payload(scope)
        for key, value in identity.items():
            _validate_identifier(value, key, limit=256)
        fingerprint = _digest(identity)
        return identity, _safe_id("scope", fingerprint)

    def _request_key(self, request_id: str) -> tuple[str, str]:
        request_id = _validate_identifier(request_id, "request_id", limit=256)
        return request_id, _safe_id("request", request_id)

    def _request_dir(self, scope: Scope, request_id: str, *, create: bool) -> Path:
        _, scope_id = self._scope_key(scope)
        _, request_key = self._request_key(request_id)
        scope_dir = self.root / scope_id
        requests_dir = scope_dir / "requests"
        request_dir = requests_dir / request_key
        for path in (scope_dir, requests_dir, request_dir):
            if path.exists() and path.is_symlink():
                raise _integrity_failure("SYMLINK_ESCAPE", "symlink escape rejected")
            self._assert_within_root(path)
            if create:
                path.mkdir(exist_ok=True)
        self._assert_within_root(request_dir)
        return request_dir

    def _assert_within_root(self, path: Path) -> None:
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise _integrity_failure("UNSAFE_PATH", "path escaped journal store root") from exc

    def _ensure_layout(self, request_dir: Path) -> dict[str, Path]:
        paths = {
            "events": request_dir / "events",
            "quarantine": request_dir / "quarantine",
            "head": request_dir / "head.json",
            "metadata": request_dir / "metadata.json",
            "idempotency": request_dir / "idempotency.json",
            "acks": request_dir / "acks.json",
            "lock": request_dir / ".request.lock",
            "manifest": request_dir / "quarantine" / "manifest.jsonl",
        }
        for key in ("events", "quarantine"):
            path = paths[key]
            if path.exists() and path.is_symlink():
                raise _integrity_failure("SYMLINK_ESCAPE", "symlink escape rejected")
            self._assert_within_root(path)
            path.mkdir(exist_ok=True)
        return paths

    def _check_file_path(self, path: Path) -> None:
        self._assert_within_root(path)
        if path.exists() and path.is_symlink():
            raise _integrity_failure("SYMLINK_ESCAPE", "symlink file rejected")

    def _atomic_write(
        self,
        path: Path,
        value: Mapping[str, Any],
        *,
        limit: int,
        immutable: bool = False,
        fault_stage: str = "",
    ) -> None:
        self._check_file_path(path)
        data = _bounded_json(value, limit, path.name)
        if immutable and path.exists():
            current = path.read_bytes()
            if current == data:
                return
            raise JournalStoreConflict("immutable durable record conflict")

        temp = path.parent / f".{path.name}.{uuid4().hex}.tmp"
        self._check_file_path(temp)
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        preserve_temp = False
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if fault_stage:
                try:
                    self._fault(
                        fault_stage,
                        {"path": str(path), "temp_path": str(temp)},
                    )
                except SimulatedCrash:
                    preserve_temp = True
                    raise
            if immutable and path.exists():
                current = path.read_bytes()
                if current != data:
                    raise JournalStoreConflict("immutable durable record conflict")
                temp.unlink(missing_ok=True)
                return
            os.replace(temp, path)
            _fsync_dir(path.parent)
        finally:
            if not preserve_temp and temp.exists():
                temp.unlink(missing_ok=True)

    def _read_json(self, path: Path, *, limit: int) -> dict[str, Any]:
        self._check_file_path(path)
        data = path.read_bytes()
        if len(data) > limit:
            raise _integrity_failure("RECOVERY_LIMIT_EXCEEDED", f"{path.name} exceeds persistence limit")
        try:
            value = json.loads(data.decode("utf-8"))
        except Exception as exc:
            raise _integrity_failure("CORRUPT_JSON", f"{path.name} is corrupt") from exc
        if not isinstance(value, dict):
            raise _integrity_failure("CORRUPT_JSON", f"{path.name} must contain an object")
        return value

    def _metadata_record(
        self,
        scope: Scope,
        request_id: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        identity, _ = self._scope_key(scope)
        request_id, _ = self._request_key(request_id)
        conversation_id = _validate_identifier(conversation_id, "conversation_id", limit=256)
        body = {
            "schema": STORE_SCHEMA,
            "kind": "metadata",
            "persistence_version": PERSISTENCE_VERSION,
            **identity,
            "scope_fingerprint": _digest(identity),
            "request_id": request_id,
            "conversation_id": conversation_id,
            "created_at": _now(),
            "external_action_executed": False,
            "automatic_checkpoint_write": False,
            "memory_promoted": False,
        }
        return {**body, "record_digest": _record_digest(body)}

    def _validate_metadata(
        self,
        record: Mapping[str, Any],
        *,
        scope: Scope,
        request_id: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        row = dict(record)
        if row.get("schema") != STORE_SCHEMA or row.get("kind") != "metadata":
            raise _integrity_failure("CORRUPT_JSON", "metadata schema mismatch")
        if row.get("persistence_version") != PERSISTENCE_VERSION:
            raise _integrity_failure("PERSISTENCE_VERSION_MISMATCH", "unknown persistence version")
        # Specific semantic checks take precedence over the outer record digest envelope.
        identity, _ = self._scope_key(scope)
        if any(row.get(k) != v for k, v in identity.items()):
            raise _integrity_failure("SCOPE_MISMATCH", "metadata scope mismatch")
        if row.get("scope_fingerprint") != _digest(identity):
            raise _integrity_failure("SCOPE_MISMATCH", "metadata scope fingerprint mismatch")
        expected_request, _ = self._request_key(request_id)
        if row.get("request_id") != expected_request:
            raise _integrity_failure("REQUEST_MISMATCH", "metadata request mismatch")
        if row.get("record_digest") != _record_digest(row):
            raise _integrity_failure("RECORD_DIGEST_MISMATCH", "metadata digest mismatch")
        if conversation_id is not None and row.get("conversation_id") != _validate_identifier(
            conversation_id, "conversation_id", limit=256
        ):
            raise _integrity_failure("REQUEST_MISMATCH", "metadata conversation mismatch")
        for invariant in (
            "external_action_executed",
            "automatic_checkpoint_write",
            "memory_promoted",
        ):
            if row.get(invariant) is not False:
                raise _integrity_failure("RECORD_DIGEST_MISMATCH", f"metadata {invariant} invariant violated")
        return row

    def _ensure_metadata(
        self,
        paths: Mapping[str, Path],
        *,
        scope: Scope,
        request_id: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        path = paths["metadata"]
        if path.exists():
            return self._validate_metadata(
                self._read_json(path, limit=self.max_metadata_bytes),
                scope=scope,
                request_id=request_id,
                conversation_id=conversation_id,
            )
        record = self._metadata_record(scope, request_id, conversation_id)
        self._atomic_write(path, record, limit=self.max_metadata_bytes, immutable=True)
        return record

    def _event_record(
        self,
        event: Mapping[str, Any],
        *,
        scope: Scope,
        request_id: str,
        conversation_id: str,
        idempotency_key: str,
        correlation_id: str | None,
        causation_id: str | None,
        origin: str,
    ) -> dict[str, Any]:
        identity, _ = self._scope_key(scope)
        request_id, _ = self._request_key(request_id)
        conversation_id = _validate_identifier(conversation_id, "conversation_id", limit=256)
        idempotency_key = _validate_identifier(
            idempotency_key, "idempotency_key", limit=MAX_IDEMPOTENCY_KEY
        )
        correlation = _validate_identifier(
            correlation_id or request_id, "correlation_id", limit=256
        )
        event_digest = str(event.get("event_digest") or "")
        _event_digest_hex(event_digest)
        previous = str(event.get("prev_digest") or "")
        if previous != GENESIS:
            _event_digest_hex(previous)
        cause = causation_id or previous
        if cause != GENESIS:
            cause = _validate_identifier(cause, "causation_id", limit=256)
        origin = _validate_identifier(origin, "origin", limit=128)
        metadata = event.get("metadata") if isinstance(event.get("metadata"), Mapping) else {}
        approval_refs = metadata.get("approval_refs")
        if not isinstance(approval_refs, list):
            approval_refs = []
        checkpoint_refs = metadata.get("checkpoint_refs")
        if not isinstance(checkpoint_refs, list):
            checkpoint_refs = []

        stable = {
            "scope_fingerprint": _digest(identity),
            "request_id": request_id,
            "sequence": event.get("sequence"),
            "event_digest": event_digest,
            "payload_digest": _digest(dict(event)),
            "correlation_id": correlation,
            "causation_id": cause,
        }
        body = {
            "schema": STORE_SCHEMA,
            "kind": "event",
            "persistence_version": PERSISTENCE_VERSION,
            "persistence_state": DURABLE,
            **identity,
            "scope_fingerprint": stable["scope_fingerprint"],
            "request_id": request_id,
            "conversation_id": conversation_id,
            "sequence": event.get("sequence"),
            "event_id": "evt-" + _event_digest_hex(event_digest),
            "event_type": event.get("event_type"),
            "event_digest": event_digest,
            "prev_digest": previous,
            "payload_digest": stable["payload_digest"],
            "correlation_id": correlation,
            "causation_id": cause,
            "idempotency_key_digest": _digest(idempotency_key),
            "idempotency_payload_digest": _digest(stable),
            "origin": origin,
            "actor_role": str(event.get("selected_role") or ""),
            "approval_refs": list(approval_refs)[:32],
            "checkpoint_refs": list(checkpoint_refs)[:32],
            "observed_at": str(event.get("observed_at") or ""),
            "persisted_at": _now(),
            "event": dict(event),
            "external_action_executed": False,
            "automatic_checkpoint_write": False,
            "memory_promoted": False,
        }
        return {**body, "record_digest": _record_digest(body)}

    def _validate_event_record(
        self,
        row: Mapping[str, Any],
        *,
        scope: Scope,
        request_id: str,
        conversation_id: str,
        expected_sequence: int | None = None,
        expected_prev: str | None = None,
    ) -> dict[str, Any]:
        record = dict(row)
        if record.get("schema") != STORE_SCHEMA or record.get("kind") != "event":
            raise _integrity_failure("CORRUPT_JSON", "event persistence schema mismatch")
        if record.get("persistence_version") != PERSISTENCE_VERSION:
            raise _integrity_failure("PERSISTENCE_VERSION_MISMATCH", "unknown persistence version")
        if record.get("persistence_state") != DURABLE:
            raise _integrity_failure("RECORD_DIGEST_MISMATCH", "durable event state mismatch")
        # Specific semantic checks take precedence over the outer record digest envelope.
        identity, _ = self._scope_key(scope)
        if any(record.get(k) != v for k, v in identity.items()):
            raise _integrity_failure("SCOPE_MISMATCH", "event scope mismatch")
        if record.get("scope_fingerprint") != _digest(identity):
            raise _integrity_failure("SCOPE_MISMATCH", "event scope fingerprint mismatch")
        expected_request, _ = self._request_key(request_id)
        if record.get("request_id") != expected_request:
            raise _integrity_failure("REQUEST_MISMATCH", "event request mismatch")
        if record.get("conversation_id") != _validate_identifier(
            conversation_id, "conversation_id", limit=256
        ):
            raise _integrity_failure("REQUEST_MISMATCH", "event conversation mismatch")
        sequence = record.get("sequence")
        if type(sequence) is not int or sequence < 1:
            raise _integrity_failure("SEQUENCE_MISMATCH", "event sequence invalid")
        if expected_sequence is not None and sequence != expected_sequence:
            raise _integrity_failure("SEQUENCE_MISMATCH", "event sequence mismatch")
        event = record.get("event")
        if not isinstance(event, Mapping):
            raise _integrity_failure("CORRUPT_JSON", "event payload invalid")
        event = dict(event)
        if event.get("sequence") != sequence:
            raise _integrity_failure("SEQUENCE_MISMATCH", "logical event sequence mismatch")
        if event.get("prev_digest") != record.get("prev_digest"):
            raise _integrity_failure("PREV_DIGEST_MISMATCH", "event previous digest mismatch")
        if expected_prev is not None and record.get("prev_digest") != expected_prev:
            raise _integrity_failure("PREV_DIGEST_MISMATCH", "durable chain mismatch")
        if event.get("event_digest") != record.get("event_digest"):
            raise _integrity_failure("EVENT_DIGEST_MISMATCH", "event digest reference mismatch")
        if _digest(event) != record.get("payload_digest"):
            raise _integrity_failure("EVENT_DIGEST_MISMATCH", "event payload digest mismatch")
        try:
            _event_digest_hex(str(record.get("event_digest") or ""))
            key_digest = str(record.get("idempotency_key_digest") or "")
            _event_digest_hex(key_digest)
            payload_digest = str(record.get("idempotency_payload_digest") or "")
            _event_digest_hex(payload_digest)
        except JournalStoreIntegrityError as exc:
            exc.reason_code = "EVENT_DIGEST_MISMATCH"
            raise
        if record.get("record_digest") != _record_digest(record):
            raise _integrity_failure("RECORD_DIGEST_MISMATCH", "durable record digest mismatch")
        for invariant in (
            "external_action_executed",
            "automatic_checkpoint_write",
            "memory_promoted",
        ):
            if record.get(invariant) is not False:
                raise _integrity_failure("RECORD_DIGEST_MISMATCH", f"event {invariant} invariant violated")
        return record

    def _load_index(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        data = self._read_json(path, limit=MAX_INDEX_BYTES)
        if data.get("schema") != STORE_SCHEMA or data.get("kind") != "idempotency":
            raise _integrity_failure("IDEMPOTENCY_INDEX_MISMATCH", "idempotency index schema mismatch")
        if data.get("persistence_version") != PERSISTENCE_VERSION:
            raise _integrity_failure("PERSISTENCE_VERSION_MISMATCH", "idempotency index version mismatch")
        entries = data.get("entries")
        if not isinstance(entries, dict):
            raise _integrity_failure("IDEMPOTENCY_INDEX_MISMATCH", "idempotency index invalid")
        if data.get("record_digest") != _record_digest(data):
            raise _integrity_failure("IDEMPOTENCY_INDEX_MISMATCH", "idempotency index digest mismatch")
        return dict(entries)

    def _write_index(self, path: Path, entries: Mapping[str, Any]) -> None:
        body = {
            "schema": STORE_SCHEMA,
            "kind": "idempotency",
            "persistence_version": PERSISTENCE_VERSION,
            "entries": dict(entries),
            "updated_at": _now(),
        }
        record = {**body, "record_digest": _record_digest(body)}
        self._atomic_write(path, record, limit=MAX_INDEX_BYTES)

    def _load_acks(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        data = self._read_json(path, limit=MAX_INDEX_BYTES)
        if data.get("schema") != STORE_SCHEMA or data.get("kind") != "acks":
            raise _integrity_failure("ACK_INVALID", "ack index schema mismatch")
        if data.get("persistence_version") != PERSISTENCE_VERSION:
            raise _integrity_failure("PERSISTENCE_VERSION_MISMATCH", "ack index version mismatch")
        if data.get("record_digest") != _record_digest(data):
            raise _integrity_failure("ACK_INVALID", "ack index digest mismatch")
        entries = data.get("entries")
        if not isinstance(entries, dict):
            raise _integrity_failure("ACK_INVALID", "ack index invalid")
        return dict(entries)

    def _write_acks(
        self,
        path: Path,
        entries: Mapping[str, Any],
        *,
        acked_through_sequence: int | None = None,
        acked_head_digest: str | None = None,
        scope_fingerprint: str = "",
        request_id_safe: str = "",
    ) -> None:
        body = {
            "schema": STORE_SCHEMA,
            "kind": "acks",
            "persistence_version": PERSISTENCE_VERSION,
            "entries": dict(entries),
            "updated_at": _now(),
        }
        if acked_through_sequence is not None:
            body["acked_through_sequence"] = int(acked_through_sequence)
            body["acked_head_digest"] = str(acked_head_digest or "")
            body["scope_fingerprint"] = scope_fingerprint
            body["request_id_safe"] = request_id_safe
        record = {**body, "record_digest": _record_digest(body)}
        self._atomic_write(path, record, limit=MAX_INDEX_BYTES)

    def _event_files(self, events_dir: Path) -> list[Path]:
        files = []
        for path in events_dir.iterdir():
            if path.name.startswith(".") and path.name.endswith(".tmp"):
                continue
            if not path.is_file() or path.is_symlink():
                continue
            if _EVENT_NAME.fullmatch(path.name):
                files.append(path)
        files.sort(key=lambda p: p.name)
        if len(files) > self.max_recovery_events:
            raise _integrity_failure("RECOVERY_LIMIT_EXCEEDED", "recovery event capacity exceeded")
        return files

    def _scan_valid_records(
        self,
        paths: Mapping[str, Path],
        *,
        scope: Scope,
        request_id: str,
        conversation_id: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        records: list[dict[str, Any]] = []
        reasons: list[str] = []
        previous = GENESIS
        expected = 1
        for path in self._event_files(paths["events"]):
            match = _EVENT_NAME.fullmatch(path.name)
            try:
                row = self._read_json(path, limit=self.max_event_bytes)
                row = self._validate_event_record(
                    row,
                    scope=scope,
                    request_id=request_id,
                    conversation_id=conversation_id,
                    expected_sequence=expected,
                    expected_prev=previous,
                )
                if int(match.group("sequence")) != expected:
                    raise _integrity_failure("SEQUENCE_MISMATCH", "event filename sequence mismatch")
                if match.group("digest") != _event_digest_hex(row["event_digest"]):
                    raise _integrity_failure("EVENT_DIGEST_MISMATCH", "event filename digest mismatch")
            except JournalStoreIntegrityError as exc:
                code = getattr(exc, "reason_code", None) or _reason_code(str(exc))
                reasons.append(code)
                break
            records.append(row)
            previous = row["event_digest"]
            expected += 1
        return records, reasons

    def _head_record(self, event_record: Mapping[str, Any]) -> dict[str, Any]:
        body = {
            "schema": STORE_SCHEMA,
            "kind": "head",
            "persistence_version": PERSISTENCE_VERSION,
            "sequence": event_record["sequence"],
            "event_digest": event_record["event_digest"],
            "event_id": event_record["event_id"],
            "updated_at": _now(),
        }
        return {**body, "record_digest": _record_digest(body)}

    def _is_request_quarantined(self, paths: Mapping[str, Path]) -> bool:
        """Deterministic quarantine check from persisted evidence (no text heuristics).

        Any valid manifest record means persisted integrity evidence exists for this
        request: a new operation must be rejected until a human review resolves it.
        An unreadable/invalid manifest is fail-closed as well.
        """
        try:
            manifest_records = self._load_quarantine_manifest(paths["manifest"])
        except JournalStoreError:
            return True  # unreadable/invalid manifest = unresolved integrity state
        return len(manifest_records) > 0

    def _reject_if_quarantined(self, paths: Mapping[str, Path]) -> None:
        if self._is_request_quarantined(paths):
            raise JournalStoreRejected(
                "REQUEST_QUARANTINED", "request requires integrity review"
            )

    def persist_event(
        self,
        journal: Mapping[str, Any],
        *,
        scope: Scope,
        request_id: str,
        sequence: int,
        idempotency_key: str,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        origin: str = "AION_UNIFIED_JOURNAL",
        acknowledge: bool = False,
    ) -> dict[str, Any]:
        request_id = _validate_identifier(request_id, "request_id", limit=256)
        idempotency_key = _validate_identifier(
            idempotency_key, "idempotency_key", limit=MAX_IDEMPOTENCY_KEY
        )
        verified = verify_request_journal(journal, scope=scope, request_id=request_id)
        if verified.get("valid") is not True:
            raise JournalStoreIntegrityError(
                "logical journal integrity mismatch: " + ",".join(verified.get("reasons") or [])
            )
        events = journal.get("events")
        if type(sequence) is not int or sequence < 1 or sequence > len(events):
            raise ValueError("sequence outside journal")
        conversation_id = _validate_identifier(
            str(journal.get("conversation_id") or ""), "conversation_id", limit=256
        )
        event = dict(events[sequence - 1])

        request_dir = self._request_dir(scope, request_id, create=True)
        paths = self._ensure_layout(request_dir)
        with _FileLock(paths["lock"], self.lock_timeout):
            self._reject_if_quarantined(paths)
            self._ensure_metadata(
                paths,
                scope=scope,
                request_id=request_id,
                conversation_id=conversation_id,
            )
            records, reasons = self._scan_valid_records(
                paths,
                scope=scope,
                request_id=request_id,
                conversation_id=conversation_id,
            )
            if reasons:
                raise _scan_failure(reasons)

            key_digest = _digest(idempotency_key)
            event_record = self._event_record(
                event,
                scope=scope,
                request_id=request_id,
                conversation_id=conversation_id,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                causation_id=causation_id,
                origin=origin,
            )

            discovered: dict[str, dict[str, Any]] = {}
            for existing in records:
                existing_key = existing["idempotency_key_digest"]
                prior = discovered.get(existing_key)
                if prior and prior["idempotency_payload_digest"] != existing["idempotency_payload_digest"]:
                    raise JournalStoreConflict("persisted idempotency conflict")
                discovered[existing_key] = existing

            prior = discovered.get(key_digest)
            if prior is not None:
                if prior["idempotency_payload_digest"] != event_record["idempotency_payload_digest"]:
                    raise JournalStoreRejected(
                        "IDEMPOTENCY_INDEX_MISMATCH", "idempotency key reused with different payload"
                    )
                if prior["event_digest"] != event_record["event_digest"]:
                    raise JournalStoreRejected(
                        "IDEMPOTENCY_INDEX_MISMATCH", "idempotency key reused for different event"
                    )
                state = ACKNOWLEDGED if self._is_acked(paths, prior) else DURABLE
                return {
                    "schema": STORE_SCHEMA,
                    "status": "IDEMPOTENT",
                    "persistence_state": state,
                    "sequence": prior["sequence"],
                    "event_digest": prior["event_digest"],
                    "idempotency_key_digest": key_digest,
                    "transitions": [STAGED, JOURNALED, DURABLE]
                    + ([ACKNOWLEDGED] if state == ACKNOWLEDGED else []),
                    "external_action_executed": False,
                    "automatic_checkpoint_write": False,
                    "memory_promoted": False,
                }

            if sequence <= len(records):
                existing = records[sequence - 1]
                if existing["event_digest"] == event_record["event_digest"]:
                    raise JournalStoreConflict(
                        "event already persisted under a different idempotency key"
                    )
                raise JournalStoreConflict("immutable sequence already occupied")
            if sequence != len(records) + 1:
                raise JournalStoreIntegrityError("durable sequence gap")
            expected_prev = GENESIS if not records else records[-1]["event_digest"]
            if event_record["prev_digest"] != expected_prev:
                raise JournalStoreIntegrityError("durable previous digest mismatch")

            digest_hex = _event_digest_hex(event_record["event_digest"])
            final_path = paths["events"] / f"{sequence:08d}_{digest_hex}.json"
            self._fault(
                "BEFORE_DURABLE_COMMIT",
                {"sequence": sequence, "event_digest": event_record["event_digest"]},
            )
            self._atomic_write(
                final_path,
                event_record,
                limit=self.max_event_bytes,
                immutable=True,
                fault_stage="AFTER_TEMP_FSYNC",
            )
            self._fault(
                "AFTER_EVENT_COMMIT",
                {"sequence": sequence, "event_digest": event_record["event_digest"]},
            )

            index = self._load_index(paths["idempotency"])
            existing_index = index.get(key_digest)
            index_entry = {
                "sequence": sequence,
                "event_digest": event_record["event_digest"],
                "idempotency_payload_digest": event_record["idempotency_payload_digest"],
                "event_file": final_path.name,
            }
            if existing_index and existing_index != index_entry:
                raise JournalStoreConflict("idempotency index conflict")
            index[key_digest] = index_entry
            self._write_index(paths["idempotency"], index)

            self._atomic_write(
                paths["head"],
                self._head_record(event_record),
                limit=self.max_metadata_bytes,
            )
            self._fault(
                "AFTER_HEAD_COMMIT",
                {"sequence": sequence, "event_digest": event_record["event_digest"]},
            )

            state = DURABLE
            transitions = [STAGED, JOURNALED, DURABLE]
            if acknowledge:
                identity, _ = self._scope_key(scope)
                _, request_id_safe = self._request_key(request_id)
                self._ack_locked(
                    paths,
                    event_record,
                    scope_fingerprint=_digest(identity),
                    request_id_safe=request_id_safe,
                )
                state = ACKNOWLEDGED
                transitions.append(ACKNOWLEDGED)

            return {
                "schema": STORE_SCHEMA,
                "status": "PERSISTED",
                "persistence_state": state,
                "sequence": sequence,
                "event_digest": event_record["event_digest"],
                "idempotency_key_digest": key_digest,
                "transitions": transitions,
                "external_action_executed": False,
                "automatic_checkpoint_write": False,
                "memory_promoted": False,
            }

    def persist_journal(
        self,
        journal: Mapping[str, Any],
        *,
        scope: Scope,
        request_id: str,
        idempotency_key: str,
        acknowledge: bool = False,
        origin: str = "AION_UNIFIED_JOURNAL",
    ) -> dict[str, Any]:
        base_key = _validate_identifier(
            idempotency_key, "idempotency_key", limit=MAX_IDEMPOTENCY_KEY - 12
        )
        verified = verify_request_journal(journal, scope=scope, request_id=request_id)
        if verified.get("valid") is not True:
            raise JournalStoreIntegrityError("logical journal integrity mismatch")
        results = []
        for event in journal.get("events") or []:
            sequence = event["sequence"]
            results.append(
                self.persist_event(
                    journal,
                    scope=scope,
                    request_id=request_id,
                    sequence=sequence,
                    idempotency_key=f"{base_key}:{sequence}",
                    correlation_id=request_id,
                    causation_id=event.get("prev_digest") or GENESIS,
                    origin=origin,
                    acknowledge=acknowledge,
                )
            )
        return {
            "schema": STORE_SCHEMA,
            "status": "PERSISTED",
            "persistence_state": (
                ACKNOWLEDGED if results and acknowledge else DURABLE if results else STAGED
            ),
            "event_count": len(results),
            "events": results,
            "external_action_executed": False,
            "automatic_checkpoint_write": False,
            "memory_promoted": False,
        }

    def _is_acked(self, paths: Mapping[str, Path], event_record: Mapping[str, Any]) -> bool:
        acks = self._load_acks(paths["acks"])
        row = acks.get(str(event_record["sequence"]))
        return bool(
            isinstance(row, Mapping)
            and row.get("event_digest") == event_record["event_digest"]
            and row.get("state") == ACKNOWLEDGED
        )

    def _ack_locked(
        self,
        paths: Mapping[str, Path],
        event_record: Mapping[str, Any],
        *,
        scope_fingerprint: str = "",
        request_id_safe: str = "",
    ) -> None:
        acks = self._load_acks(paths["acks"])
        key = str(event_record["sequence"])
        value = {
            "state": ACKNOWLEDGED,
            "event_digest": event_record["event_digest"],
            "acknowledged_at": _now(),
        }
        prior = acks.get(key)
        if prior is not None and prior.get("event_digest") != event_record["event_digest"]:
            raise JournalStoreConflict("acknowledgement conflict")
        acks[key] = value
        self._write_acks(
            paths["acks"],
            acks,
            acked_through_sequence=int(event_record["sequence"]),
            acked_head_digest=str(event_record["event_digest"]),
            scope_fingerprint=scope_fingerprint,
            request_id_safe=request_id_safe,
        )
        self._fault(
            "AFTER_ACK_COMMIT",
            {
                "sequence": event_record["sequence"],
                "event_digest": event_record["event_digest"],
            },
        )

    def acknowledge(
        self,
        *,
        scope: Scope,
        request_id: str,
        sequence: int,
        event_digest: str,
    ) -> dict[str, Any]:
        request_dir = self._request_dir(scope, request_id, create=False)
        if not request_dir.exists():
            raise LookupError("durable request unavailable for scope")
        paths = self._ensure_layout(request_dir)
        with _FileLock(paths["lock"], self.lock_timeout):
            self._reject_if_quarantined(paths)
            metadata = self._validate_metadata(
                self._read_json(paths["metadata"], limit=self.max_metadata_bytes),
                scope=scope,
                request_id=request_id,
            )
            records, reasons = self._scan_valid_records(
                paths,
                scope=scope,
                request_id=request_id,
                conversation_id=metadata["conversation_id"],
            )
            if reasons:
                raise _scan_failure(reasons)
            if type(sequence) is not int or sequence < 1:
                raise JournalStoreRejected("ACK_INVALID", "ack sequence must be a positive integer")
            if sequence > len(records):
                raise JournalStoreRejected("ACK_INVALID", "ack references future event")
            record = records[sequence - 1]
            if record["event_digest"] != event_digest:
                raise JournalStoreRejected("ACK_INVALID", "ack event digest mismatch")
            current = self._acked_through(paths, records)
            if sequence < current:
                raise JournalStoreRejected("ACK_INVALID", "ack downgrade rejected")
            identity, _ = self._scope_key(scope)
            _, request_id_safe = self._request_key(request_id)
            self._ack_locked(
                paths,
                record,
                scope_fingerprint=_digest(identity),
                request_id_safe=request_id_safe,
            )
            return {
                "schema": STORE_SCHEMA,
                "status": "ACKNOWLEDGED",
                "persistence_state": ACKNOWLEDGED,
                "sequence": sequence,
                "event_digest": event_digest,
                "acked_through_sequence": max(current, sequence),
                "external_action_executed": False,
                "automatic_checkpoint_write": False,
                "memory_promoted": False,
            }

    def _acked_through(self, paths: Mapping[str, Path], records: list[dict[str, Any]]) -> int:
        """Normalized cumulative ACK position (legacy per-sequence format supported)."""
        try:
            acks = self._load_acks(paths["acks"])
        except JournalStoreError:
            return 0
        if isinstance(acks.get("acked_through_sequence"), int):
            return int(acks["acked_through_sequence"])
        entries = acks.get("entries") if isinstance(acks.get("entries"), dict) else {}
        if not entries and acks:
            entries = {k: v for k, v in acks.items() if k.isdigit()}
        highest = 0
        for key, row in entries.items():
            try:
                seq = int(key)
            except (TypeError, ValueError):
                continue
            if isinstance(row, Mapping) and row.get("state") == ACKNOWLEDGED:
                highest = max(highest, seq)
        return highest

    def _quarantine_temp_files(
        self,
        paths: Mapping[str, Path],
        *,
        scope_fingerprint: str,
        request_id_safe: str,
        recovery_attempt_id: str,
    ) -> list[dict[str, Any]]:
        quarantined: list[dict[str, Any]] = []
        for temp in list(paths["events"].glob(".*.tmp")):
            self._check_file_path(temp)
            target = paths["quarantine"] / f"orphan-{uuid4().hex}.tmp"
            self._check_file_path(target)
            status = "MOVED"
            try:
                self._fault("BEFORE_QUARANTINE_FILE_MOVE", {"source": str(temp), "target": str(target)})
                os.replace(temp, target)
                _fsync_dir(paths["quarantine"])
                self._fault("AFTER_QUARANTINE_FILE_MOVE", {"source": str(temp), "target": str(target)})
            except SimulatedCrash:
                raise
            except Exception:
                status = "PENDING"
            records = self._load_quarantine_manifest(paths["manifest"])
            previous = GENESIS if not records else str(records[-1]["manifest_record_digest"])
            entry = self._append_quarantine_manifest(
                paths,
                scope_fingerprint=scope_fingerprint,
                request_id_safe=request_id_safe,
                original_relative_path=f"events/{temp.name}",
                quarantine_relative_path=f"quarantine/{target.name}" if status == "MOVED" else f"events/{temp.name}",
                quarantine_status=status,
                reason_code="ORPHAN_TEMP",
                reason_detail="orphan temp file quarantined",
                observed_digest="",
                expected_digest="",
                sequence=None,
                event_digest="",
                detection_phase="RECOVERY_SCAN",
                recovery_attempt_id=recovery_attempt_id,
                previous_manifest_digest=previous,
            )
            quarantined.append(entry)
        return quarantined

    def _manifest_path(self, request_dir: Path) -> Path:
        return request_dir / "quarantine" / "manifest.jsonl"

    def _manifest_record_digest(self, record: Mapping[str, Any]) -> str:
        body = dict(record)
        body.pop("manifest_record_digest", None)
        return _digest(body)

    def _load_quarantine_manifest(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        previous = GENESIS
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception as exc:
                raise _integrity_failure("CORRUPT_JSON", "quarantine manifest line is corrupt") from exc
            if not isinstance(row, dict):
                raise _integrity_failure("CORRUPT_JSON", "quarantine manifest line must be an object")
            if row.get("schema") != QUARANTINE_MANIFEST_SCHEMA:
                raise _integrity_failure("CORRUPT_JSON", "quarantine manifest schema mismatch")
            if row.get("persistence_version") != PERSISTENCE_VERSION:
                raise _integrity_failure("PERSISTENCE_VERSION_MISMATCH", "quarantine manifest version mismatch")
            if row.get("previous_manifest_digest") != previous:
                raise _integrity_failure("RECORD_DIGEST_MISMATCH", "quarantine manifest chain broken")
            if row.get("manifest_record_digest") != self._manifest_record_digest(row):
                raise _integrity_failure("RECORD_DIGEST_MISMATCH", "quarantine manifest digest mismatch")
            records.append(dict(row))
            previous = str(row["manifest_record_digest"])
        return records

    def _append_quarantine_manifest(
        self,
        paths: Mapping[str, Path],
        *,
        scope_fingerprint: str,
        request_id_safe: str,
        original_relative_path: str,
        quarantine_relative_path: str,
        quarantine_status: str,
        reason_code: str,
        reason_detail: str,
        observed_digest: str,
        expected_digest: str,
        sequence: int | None,
        event_digest: str,
        detection_phase: str,
        recovery_attempt_id: str,
        previous_manifest_digest: str,
    ) -> dict[str, Any]:
        record = {
            "schema": QUARANTINE_MANIFEST_SCHEMA,
            "persistence_version": PERSISTENCE_VERSION,
            "timestamp_utc": _now(),
            "scope_fingerprint": scope_fingerprint,
            "request_id_safe": request_id_safe,
            "original_relative_path": original_relative_path,
            "quarantine_relative_path": quarantine_relative_path,
            "quarantine_status": quarantine_status,
            "reason_code": reason_code,
            "reason_detail": _reason_detail(reason_detail),
            "observed_digest": observed_digest or "",
            "expected_digest": expected_digest or "",
            "sequence": sequence,
            "event_digest": event_digest or "",
            "detection_phase": detection_phase,
            "recovery_attempt_id": recovery_attempt_id,
            "previous_manifest_digest": previous_manifest_digest,
        }
        record["manifest_record_digest"] = self._manifest_record_digest(record)
        manifest = paths["manifest"]
        self._check_file_path(manifest.parent)
        existing = manifest.read_bytes() if manifest.exists() else b""
        data = existing + (_canonical(record) + "\n").encode("utf-8")
        if len(data) > QUARANTINE_MANIFEST_MAX_BYTES:
            raise _integrity_failure("RECOVERY_LIMIT_EXCEEDED", "quarantine manifest exceeds persistence limit")
        temp = manifest.parent / f".{manifest.name}.{uuid4().hex}.tmp"
        self._fault("BEFORE_QUARANTINE_MANIFEST_COMMIT", {"path": str(manifest)})
        try:
            fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, manifest)
            _fsync_dir(manifest.parent)
        finally:
            temp.unlink(missing_ok=True)
        self._fault("AFTER_QUARANTINE_MANIFEST_COMMIT", {"path": str(manifest)})
        return record

    def _quarantine_copy_evidence(
        self,
        paths: Mapping[str, Path],
        source: Path,
        *,
        name_prefix: str,
    ) -> tuple[Path, str]:
        """Copy evidence into quarantine and verify bytes. Original is preserved."""
        self._check_file_path(source)
        target = paths["quarantine"] / f"{name_prefix}-{uuid4().hex}.json"
        self._check_file_path(target)
        self._fault("BEFORE_QUARANTINE_FILE_MOVE", {"source": str(source), "target": str(target)})
        temp = paths["quarantine"] / f".{target.name}.{uuid4().hex}.tmp"
        try:
            with open(source, "rb") as src, os.fdopen(os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as dst:
                dst.write(src.read())
                dst.flush()
                os.fsync(dst.fileno())
            os.replace(temp, target)
            _fsync_dir(paths["quarantine"])
        finally:
            temp.unlink(missing_ok=True)
        if target.read_bytes() != source.read_bytes():
            raise _integrity_failure("RECORD_DIGEST_MISMATCH", "quarantine copy verification failed")
        self._fault("AFTER_QUARANTINE_FILE_MOVE", {"source": str(source), "target": str(target)})
        return target, "COPIED"

    def _quarantine_corrupt_event(
        self,
        paths: Mapping[str, Path],
        *,
        event_path: Path,
        scope_fingerprint: str,
        request_id_safe: str,
        reason_code: str,
        reason_detail: str,
        observed_digest: str,
        expected_digest: str,
        sequence: int | None,
        event_digest: str,
        detection_phase: str,
        recovery_attempt_id: str,
    ) -> dict[str, Any]:
        match = _EVENT_NAME.fullmatch(event_path.name)
        name_prefix = f"event-{int(match.group('sequence')) if match else 'unknown'}"
        try:
            target, status = self._quarantine_copy_evidence(
                paths,
                event_path,
                name_prefix=name_prefix,
            )
        except SimulatedCrash:
            raise
        except Exception:
            target = event_path
            status = "PENDING"
        try:
            records = self._load_quarantine_manifest(paths["manifest"])
            previous = GENESIS if not records else str(records[-1]["manifest_record_digest"])
        except JournalStoreError:
            previous = GENESIS
        try:
            return self._append_quarantine_manifest(
            paths,
            scope_fingerprint=scope_fingerprint,
            request_id_safe=request_id_safe,
            original_relative_path=f"events/{event_path.name}",
            quarantine_relative_path=f"quarantine/{target.name}",
            quarantine_status=status,
            reason_code=reason_code,
            reason_detail=reason_detail,
            observed_digest=observed_digest,
            expected_digest=expected_digest,
            sequence=sequence,
            event_digest=event_digest,
            detection_phase=detection_phase,
            recovery_attempt_id=recovery_attempt_id,
            previous_manifest_digest=previous,
        )
        except JournalStoreError:
            return {
                "quarantine_status": status,
                "quarantine_relative_path": f"quarantine/{Path(target).name}" if status != "PENDING" else f"events/{event_path.name}",
                "reason_code": reason_code,
            }

    def recover(
        self,
        *,
        scope: Scope,
        request_id: str,
    ) -> dict[str, Any]:
        request_id = _validate_identifier(request_id, "request_id", limit=256)
        request_dir = self._request_dir(scope, request_id, create=False)
        if not request_dir.exists():
            raise LookupError("durable request unavailable for scope")
        paths = self._ensure_layout(request_dir)
        recovery_attempt_id = uuid4().hex
        with _FileLock(paths["lock"], self.lock_timeout):
            identity, _ = self._scope_key(scope)
            scope_fingerprint = _digest(identity)
            _, request_id_safe = self._request_key(request_id)
            try:
                metadata = self._validate_metadata(
                    self._read_json(paths["manifest"].parent.parent / "metadata.json", limit=self.max_metadata_bytes),
                    scope=scope,
                    request_id=request_id,
                )
            except JournalStoreIntegrityError as exc:
                code = getattr(exc, "reason_code", None) or _reason_code(str(exc))
                return self._recovery_report(
                    paths, scope_fingerprint=scope_fingerprint, request_id_safe=request_id_safe,
                    request_id=request_id, conversation_id="", records=[], head_status="EMPTY",
                    ack_status="NONE", quarantined=[], warnings=[], hard_codes=[code],
                    logical={"valid": False, "reasons": [code]}, recovery_attempt_id=recovery_attempt_id,
                    status="QUARANTINED", state=QUARANTINED,
                    extra={
                        "scope_valid": code != "SCOPE_MISMATCH",
                        "request_valid": code not in {"REQUEST_MISMATCH", "SCOPE_MISMATCH"},
                        "version_accepted": code != "PERSISTENCE_VERSION_MISMATCH",
                        "chain_valid": False,
                        "head_consistent": False,
                        "idempotency_consistent": False,
                        "ack_consistent": False,
                        "quarantine_clear": False,
                        "deterministic_recovery": False,
                        "safe_to_resume": False,
                    },
                )
            quarantined = self._quarantine_temp_files(
                paths,
                scope_fingerprint=scope_fingerprint,
                request_id_safe=request_id_safe,
                recovery_attempt_id=recovery_attempt_id,
            )
            records, scan_reasons = self._scan_valid_records(
                paths,
                scope=scope,
                request_id=request_id,
                conversation_id=metadata["conversation_id"],
            )
            # Copy corrupted finalized evidence into quarantine (original preserved).
            if scan_reasons:
                corrupt_path = None
                for path in self._event_files(paths["events"]):
                    match = _EVENT_NAME.fullmatch(path.name)
                    if match and int(match.group("sequence")) == len(records) + 1:
                        corrupt_path = path
                        break
                if corrupt_path is not None:
                    try:
                        self._quarantine_corrupt_event(
                            paths,
                            event_path=corrupt_path,
                            scope_fingerprint=scope_fingerprint,
                            request_id_safe=request_id_safe,
                            reason_code=scan_reasons[0],
                            reason_detail="finalized event failed integrity scan",
                            observed_digest="",
                            expected_digest="",
                            sequence=len(records) + 1,
                            event_digest="",
                            detection_phase="RECOVERY_SCAN",
                            recovery_attempt_id=recovery_attempt_id,
                        )
                    except JournalStoreError:
                        pass  # manifest failure is recorded below via manifest validation
            warnings: list[dict[str, str]] = []
            hard_codes: list[str] = []
            for code in scan_reasons:
                (hard_codes if code in HARD_FAILURE_CODES else warnings).append({"reason_code": code, "detail": ""})

            idempotency_consistent = True
            index_error = False
            index_missing = False
            try:
                index = self._load_index(paths["idempotency"])
            except JournalStoreIntegrityError as exc:
                index = {}
                idempotency_consistent = False
                index_error = True
                hard_codes.append({"reason_code": getattr(exc, "reason_code", "IDEMPOTENCY_INDEX_MISMATCH"), "detail": ""})
            if not paths["idempotency"].exists() and records:
                # Crash window between event commit and index commit: index lagging is expected, not corruption.
                index_missing = True
                warnings.append({"reason_code": "IDEMPOTENCY_INDEX_STALE", "detail": "index not yet committed after crash window"})
            seen_payloads: dict[str, str] = {}
            for record in records:
                key = record["idempotency_key_digest"]
                payload = record["idempotency_payload_digest"]
                if key in seen_payloads and seen_payloads[key] != payload:
                    idempotency_consistent = False
                    hard_codes.append({"reason_code": "IDEMPOTENCY_INDEX_MISMATCH", "detail": "conflicting payloads"})
                    break
                seen_payloads[key] = payload
            if not index_error and not index_missing:
                for record in records:
                    row = index.get(record["idempotency_key_digest"])
                    if row is None or (
                        row.get("event_digest") != record["event_digest"]
                        or row.get("idempotency_payload_digest") != record["idempotency_payload_digest"]
                    ):
                        idempotency_consistent = False
                        hard_codes.append({"reason_code": "IDEMPOTENCY_INDEX_MISMATCH", "detail": "index entry diverges from event"})
                        break

            head_status = "EMPTY"
            head_consistent = True
            if records:
                last = records[-1]
                if not paths["head"].exists():
                    head_status = "STALE"
                    head_consistent = False
                    warnings.append({"reason_code": "STALE_HEAD", "detail": "head missing after crash window"})
                else:
                    try:
                        head = self._read_json(paths["head"], limit=self.max_metadata_bytes)
                        if (
                            head.get("schema") != STORE_SCHEMA
                            or head.get("kind") != "head"
                            or head.get("persistence_version") != PERSISTENCE_VERSION
                            or head.get("record_digest") != _record_digest(head)
                        ):
                            raise _integrity_failure("CORRUPT_JSON", "head integrity mismatch")
                        if head.get("sequence") < last["sequence"]:
                            head_status = "STALE"
                            head_consistent = False
                            warnings.append({"reason_code": "STALE_HEAD", "detail": "events advanced beyond head"})
                        elif (
                            head.get("sequence") > last["sequence"]
                            or head.get("event_digest") != last["event_digest"]
                        ):
                            head_status = "INVALID"
                            head_consistent = False
                            hard_codes.append({"reason_code": "HEAD_POINTS_TO_MISSING_EVENT", "detail": "head references unknown event"})
                    except JournalStoreIntegrityError as exc:
                        head_status = "INVALID"
                        head_consistent = False
                        hard_codes.append({"reason_code": getattr(exc, "reason_code", "CORRUPT_JSON"), "detail": ""})

            ack_status = "NONE"
            ack_consistent = True
            try:
                acks = self._load_acks(paths["acks"])
            except JournalStoreIntegrityError as exc:
                acks = {}
                ack_consistent = False
                hard_codes.append({"reason_code": getattr(exc, "reason_code", "ACK_INVALID"), "detail": ""})
            if records:
                last = records[-1]
                ack = acks.get(str(last["sequence"]))
                if (
                    isinstance(ack, Mapping)
                    and ack.get("event_digest") == last["event_digest"]
                    and ack.get("state") == ACKNOWLEDGED
                ):
                    ack_status = ACKNOWLEDGED
                else:
                    ack_status = "PENDING"

            manifest_error = False
            quarantine_count = 0
            quarantine_pending_count = 0
            try:
                manifest_records = self._load_quarantine_manifest(paths["manifest"])
                quarantine_count = len(manifest_records)
                quarantine_pending_count = sum(1 for r in manifest_records if r.get("quarantine_status") == "PENDING")
            except JournalStoreIntegrityError as exc:
                manifest_error = True
                hard_codes.append({"reason_code": getattr(exc, "reason_code", "CORRUPT_JSON"), "detail": "quarantine manifest invalid"})
            # ORPHAN_TEMP MOVED is a warning (temp outside the logical chain); only PENDING blocks resume.
            for entry in quarantined:
                if entry.get("reason_code") == "ORPHAN_TEMP" and entry.get("quarantine_status") == "MOVED":
                    warnings.append({"reason_code": "ORPHAN_TEMP", "detail": "orphan temp quarantined outside chain"})
            quarantine_clear = not manifest_error and quarantine_pending_count == 0

            journal = {
                "schema": JOURNAL_SCHEMA,
                "owner_id": metadata["owner_id"],
                "tenant_id": metadata["tenant_id"],
                "workspace_id": metadata["workspace_id"],
                "scope_fingerprint": metadata["scope_fingerprint"],
                "request_id": metadata["request_id"],
                "conversation_id": metadata["conversation_id"],
                "revision": len(records),
                "events": [dict(record["event"]) for record in records],
                "head_digest": "" if not records else records[-1]["event_digest"],
                "external_persisted": bool(records),
                "automatic_checkpoint_write": False,
                "memory_promoted": False,
                "external_action_executed": False,
            }
            logical = verify_request_journal(journal, scope=scope, request_id=request_id)
            chain_valid = logical.get("valid") is True
            if not chain_valid:
                for reason in logical.get("reasons") or []:
                    code = _reason_code(str(reason))
                    hard_codes.append({"reason_code": code, "detail": str(reason)[:240]})

            all_codes = [w["reason_code"] for w in warnings] + [h["reason_code"] for h in hard_codes]
            reason_codes = list(dict.fromkeys(all_codes))
            hard_failures = [dict(h) for h in hard_codes]
            deterministic_recovery = (
                chain_valid
                and idempotency_consistent
                and not manifest_error
            )
            safe_to_resume = bool(
                chain_valid
                and idempotency_consistent
                and head_consistent
                and ack_consistent
                and quarantine_clear
                and deterministic_recovery
                and not hard_failures
            )
            if hard_failures or not quarantine_clear:
                state = QUARANTINED
                status = "QUARANTINED"
            elif records and ack_status == ACKNOWLEDGED:
                state = ACKNOWLEDGED
                status = "RECOVERED"
            elif records:
                state = DURABLE
                status = "RECOVERED_WITH_STALE_HEAD" if head_status == "STALE" else "RECOVERED"
            else:
                state = STAGED
                status = "RECOVERED"
            return self._recovery_report(
                paths, scope_fingerprint=scope_fingerprint, request_id_safe=request_id_safe,
                request_id=request_id, conversation_id=metadata["conversation_id"], records=records,
                head_status=head_status, ack_status=ack_status, quarantined=quarantined,
                warnings=warnings, hard_codes=hard_codes, logical=logical,
                recovery_attempt_id=recovery_attempt_id, status=status, state=state,
                manifest_quarantine_count=quarantine_count,
                manifest_pending_count=quarantine_pending_count,
                extra={
                    "journal": journal,
                    "journal_integrity": logical,
                    "scope_valid": True,
                    "request_valid": True,
                    "version_accepted": True,
                    "head_consistent": head_consistent,
                    "idempotency_consistent": idempotency_consistent,
                    "ack_consistent": ack_consistent,
                    "quarantine_clear": quarantine_clear,
                    "deterministic_recovery": deterministic_recovery,
                    "chain_valid": chain_valid,
                    "safe_to_resume": safe_to_resume,
                },
            )

    def _recovery_report(
        self,
        paths: Mapping[str, Path],
        *,
        scope_fingerprint: str,
        request_id_safe: str,
        request_id: str,
        conversation_id: str,
        records: list[dict[str, Any]],
        head_status: str,
        ack_status: str,
        quarantined: list[dict[str, Any]],
        warnings: list[dict[str, str]],
        hard_codes: list[dict[str, str]],
        logical: dict[str, Any],
        recovery_attempt_id: str,
        status: str,
        state: str,
        extra: dict[str, Any] | None = None,
        manifest_quarantine_count: int | None = None,
        manifest_pending_count: int | None = None,
    ) -> dict[str, Any]:
        all_codes = [w["reason_code"] for w in warnings] + [h["reason_code"] for h in hard_codes]
        report = {
            "schema": STORE_SCHEMA,
            "persistence_version": PERSISTENCE_VERSION,
            "status": status,
            "persistence_state": state,
            "request_id": request_id,
            "request_id_safe": request_id_safe,
            "conversation_id": conversation_id,
            "scope_fingerprint": scope_fingerprint,
            "recovery_attempt_id": recovery_attempt_id,
            "event_count": len(records),
            "events_scanned": len(records),
            "last_valid_sequence": records[-1]["sequence"] if records else 0,
            "recovered_head_digest": records[-1]["event_digest"] if records else "",
            "head_status": head_status,
            "ack_status": ack_status,
            "ack_pending": bool(records and ack_status != ACKNOWLEDGED),
            "quarantined_files": [q.get("quarantine_relative_path", "") for q in quarantined],
            "quarantine_count": (
                manifest_quarantine_count
                if manifest_quarantine_count is not None
                else len(quarantined)
            ),
            "quarantine_pending_count": (
                manifest_pending_count
                if manifest_pending_count is not None
                else sum(1 for q in quarantined if q.get("quarantine_status") == "PENDING")
            ),
            "warnings": [dict(w) for w in warnings],
            "hard_failures": [dict(h) for h in hard_codes],
            "reason_codes": list(dict.fromkeys(all_codes)),
            "reasons": list(dict.fromkeys(all_codes + (["ORPHAN_TEMP_QUARANTINED"] if any(w["reason_code"] == "ORPHAN_TEMP" for w in warnings) else []))),
            "restores_state_only": True,
            "automatic_resume_executes": False,
            "checkpoint_written": False,
            "external_action_executed": False,
            "memory_promoted": False,
        }
        if extra:
            report.update(extra)
        return report


__all__ = [
    "STORE_SCHEMA",
    "PERSISTENCE_VERSION",
    "STAGED",
    "JOURNALED",
    "DURABLE",
    "ACKNOWLEDGED",
    "QUARANTINED",
    "REJECTED",
    "PERSISTENCE_STATES",
    "JournalStoreError",
    "JournalStoreIntegrityError",
    "JournalStoreConflict",
    "JournalStoreLockTimeout",
    "SimulatedCrash",
    "UnifiedJournalStore",
]
