"""M73 EXPERIMENTAL read-only incident observation fence (NOT production security).

The M71 original direct validator still accepts a pre-reopening READY gate.
This adapter exercises a proposed *additional* revision/freshness constraint
using in-memory observations in LAB. The observations and their alleged source
are injectable and NOT cryptographically attested. NEVER use this as an
activation gate or treat a coherent diagnostic as authorization. A future
operational integration requires an authenticated authoritative source,
monotonic persisted revisions, atomic recheck/fence with the writer, F1/T1,
owner approval, independent review and new whole-product CI.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Callable, Mapping

from atlasquant_aion_global_worker_reactivation_gate import (
    READY_STATUS,
    assess_post_incident_reactivation_gate,
    gate_integrity,
    validate_reactivation_gate_for_execution,
)

SCHEMA = "AION_M73_FRESH_INCIDENT_REVISION_DIAGNOSTIC_LAB_V1"
MAX_AGE = timedelta(seconds=5)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "authorization_issued": False,
        "reactivation_authorized": False,
        "feature_flag_modified": False,
        "global_worker_executed": False,
        "executes_action": False,
    }


def _parse_timestamp(value: Any) -> datetime | None:
    try:
        row = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if row.tzinfo is None or row.utcoffset() is None:
            return None
        return row.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _snapshot_digest(value: Mapping[str, Any]) -> str:
    # Content consistency only, NOT signature or independent provenance.
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _decode_observation(raw: Any, current: datetime) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(raw, Mapping):
        return None, "M73_OBSERVATION_INVALID"
    revision = raw.get("revision")
    if type(revision) is not int or revision < 1:
        return None, "M73_REVISION_INVALID"
    source = raw.get("source")
    if not isinstance(source, str) or not source.strip():
        return None, "M73_SOURCE_INVALID"
    observed_at = _parse_timestamp(raw.get("observed_at"))
    if observed_at is None:
        return None, "M73_OBSERVED_AT_INVALID"
    if observed_at > current:
        return None, "M73_OBSERVATION_FROM_FUTURE"
    if current - observed_at > MAX_AGE:
        return None, "M73_OBSERVATION_STALE"
    snapshot = raw.get("incident_snapshot")
    if not isinstance(snapshot, Mapping):
        return None, "M73_SNAPSHOT_UNAVAILABLE"
    recon = snapshot.get("global_worker_reconciliation")
    if not isinstance(recon, Mapping):
        return None, "M73_RECONCILIATION_MISSING"
    reconciled = _parse_timestamp(recon.get("reconciled_at"))
    if reconciled is None or reconciled != observed_at:
        return None, "M73_RECONCILIATION_TIME_MISMATCH"
    return {
        "revision": revision,
        "source": source,
        "observed_at": observed_at.isoformat(),
        "incident_snapshot": deepcopy(dict(snapshot)),
        "fingerprint": _snapshot_digest(snapshot),
    }, ""


def diagnose_fresh_gate_lab(
    runtime: Mapping[str, Any],
    readiness: Mapping[str, Any],
    flag: Mapping[str, Any],
    approval_shape_only: Mapping[str, Any],
    original_gate: Mapping[str, Any],
    *,
    issued_revision: int,
    issued_source: str,
    observation_reader: Callable[[], Mapping[str, Any]] | None,
    now: datetime,
) -> dict[str, Any]:
    """Fail closed on missing/changing evidence. Positive means DIAGNOSTIC ONLY.

    Both issued_revision and issued_source are untrusted fixture bindings in
    this prototype; the future real source MUST attest and persist them.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        return _blocked("M73_CLOCK_INVALID")
    current = now.astimezone(timezone.utc)
    if type(issued_revision) is not int or issued_revision < 1:
        return _blocked("M73_ISSUED_REVISION_INVALID")
    if not isinstance(issued_source, str) or not issued_source.strip():
        return _blocked("M73_ISSUED_SOURCE_INVALID")
    if gate_integrity(original_gate)["state"] != "MATCH":
        return _blocked("M73_OLD_GATE_INTEGRITY_MISMATCH")
    if str(original_gate.get("status") or "") != READY_STATUS:
        return _blocked("M73_OLD_GATE_NOT_READY")
    if not callable(observation_reader):
        return _blocked("M73_SOURCE_UNAVAILABLE")
    try:
        a_raw = observation_reader()
        b_raw = observation_reader()
    except Exception:
        return _blocked("M73_SOURCE_READ_FAILED")
    a, error_a = _decode_observation(a_raw, current)
    if error_a:
        return _blocked(error_a)
    b, error_b = _decode_observation(b_raw, current)
    if error_b:
        return _blocked(error_b)
    assert a is not None and b is not None
    if (
        a["source"] != b["source"]
        or a["revision"] != b["revision"]
        or a["fingerprint"] != b["fingerprint"]
        or a["observed_at"] != b["observed_at"]
    ):
        return _blocked("M73_TOCTOU_OBSERVATION_CHANGED")
    if a["source"] != issued_source:
        return _blocked("M73_SOURCE_CHANGED")
    if a["revision"] < issued_revision:
        return _blocked("M73_REVISION_ROLLBACK")
    if a["revision"] != issued_revision:
        return _blocked("M73_REVISION_CHANGED_AFTER_GATE")
    gate_current = assess_post_incident_reactivation_gate(
        runtime, a["incident_snapshot"], readiness, flag, now=current
    )
    if gate_current.get("status") != READY_STATUS:
        return _blocked("M73_CURRENT_INCIDENT_BLOCKED")
    # Always use recomputed gate in diagnostic instead of accepting replayed
    # original gate. This DOES NOT eliminate a race after the second read.
    diagnostic = validate_reactivation_gate_for_execution(
        runtime, flag, approval_shape_only, gate_current, now=current
    )
    if diagnostic.get("state") != "READY":
        return _blocked("M73_ORIGINAL_VALIDATION_BLOCKED")
    return {
        "schema": SCHEMA,
        "state": "DIAGNOSTIC_COHERENT_ONLY",
        "reason": "NO_ACTIVATION_AUTHORITY_OR_ATOMIC_FENCE",
        "source_revision_observed": a["revision"],
        "authorization_issued": False,
        "reactivation_authorized": False,
        "feature_flag_modified": False,
        "global_worker_executed": False,
        "executes_action": False,
    }
