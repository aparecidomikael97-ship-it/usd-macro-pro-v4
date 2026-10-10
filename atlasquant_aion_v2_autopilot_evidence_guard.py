"""Conservative per-process Autopilot sink quarantine; NOT cross-process safe."""
from __future__ import annotations
from collections.abc import Callable, Mapping
from threading import RLock
from typing import Any

_LOCK = RLock()
_QUARANTINED: set[tuple[str, str, str]] = set()
_UNCERTAIN_REASONS = frozenset({
    "UNKNOWN_OUTCOME", "CONFLICT", "VALIDATION_REJECTED",
    "PENDING_RECONCILIATION", "UNVERIFIED_SUCCESS",
})

def _blocked(reason: str, *, error: str = "") -> dict[str, Any]:
    return {
        "ok": False, "reason": reason, "error": error, "write_outcome": "UNKNOWN",
        "reconciliation_required": True, "safe_to_retry": False,
        "verified": False, "remote_durability_certified": False,
    }

def guarded_autopilot_evidence_write(
    *, repo: str, branch: str, sink: str,
    write: Callable[[], Mapping[str, Any]],
) -> dict[str, Any]:
    """Serialize local callers; no retry/release after an uncertain write.

    A restart discards this memory. Independently witnessed durable CAS is
    required to prevent replay between processes/runners. NO GO #1117.
    """
    key = (str(repo).strip(), str(branch).strip(), str(sink).strip())
    if not all(key) or key[2] not in ("shadow", "flight"):
        return _blocked("INVALID_SINK_IDENTITY")
    with _LOCK:
        if key in _QUARANTINED:
            return _blocked("PENDING_RECONCILIATION")
        try:
            answer = write()
        except Exception as exc:
            _QUARANTINED.add(key)
            return _blocked("UNKNOWN_OUTCOME", error=type(exc).__name__)
        if not isinstance(answer, Mapping):
            _QUARANTINED.add(key)
            return _blocked("UNKNOWN_OUTCOME", error="MALFORMED_WRITER_RESULT")
        result = dict(answer)
        reason = str(result.get("reason") or "")
        if (
            result.get("reconciliation_required") is True
            or result.get("write_outcome") == "UNKNOWN"
            or reason in _UNCERTAIN_REASONS
        ):
            _QUARANTINED.add(key)
            result.update(_blocked("PENDING_RECONCILIATION", error=reason or "UNKNOWN_OUTCOME"))
            return result
        if result.get("ok") is True:
            if reason == "ALREADY_PRESENT":
                _QUARANTINED.add(key)
                result.update(_blocked("REMOTE_ALREADY_PRESENT_UNVERIFIED"))
                return result
            if reason != "SAVED" or result.get("verified") is not True:
                _QUARANTINED.add(key)
                result.update(_blocked("UNVERIFIED_SUCCESS"))
                return result
        if result.get("ok") is not True:
            result["ok"] = False
            result["safe_to_retry"] = False
        return result

__all__ = ["guarded_autopilot_evidence_write"]
