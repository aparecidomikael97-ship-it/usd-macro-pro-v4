"""Evidence validator for future multi-instance coordination.

This module never runs a live probe and never activates a worker. It validates a
caller-supplied operational probe receipt against a caller-supplied evidence
verifier. A canonical fingerprint proves integrity only; verified evidence is
still required before the result may be called operationally verified.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence


SCHEMA = "ATLASQUANT_AION_COORDINATION_OPERATIONAL_VERIFICATION_V1"
RECEIPT_SCHEMA = "ATLASQUANT_AION_COORDINATION_OPERATIONAL_RECEIPT_V1"
RECEIPT_VERSION = 1
MAX_RECEIPT_TTL_SECONDS = 900
_REQUIRED_CAPABILITIES = (
    "shared_across_instances",
    "atomic_compare_and_swap",
    "monotonic_versions",
    "atomic_monotonic_fencing_token",
    "ttl_expiry",
    "atomic_delete",
    "durable_outside_browser",
)
_RECEIPT_FIELDS = (
    "schema",
    "receipt_version",
    "adapter_identity_digest",
    "scope_digest",
    "issued_at",
    "expires_at",
    "probe_run_id",
    "namespace",
    "namespace_is_ephemeral",
    "production_mutation_count",
    "isolated_mutation_count",
    "concurrent_probe_count",
    "observed_capabilities",
    "evidence_refs",
    "receipt_fingerprint",
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _clean(value: Any, limit: int = 180) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _refs(values: Sequence[Any] | None) -> list[str]:
    out: list[str] = []
    for value in list(values or [])[:32]:
        item = _clean(value, 220)
        if item and item not in out:
            out.append(item)
    return out


def operational_receipt_fingerprint(receipt: Mapping[str, Any]) -> str:
    body = {
        key: receipt.get(key)
        for key in _RECEIPT_FIELDS
        if key != "receipt_fingerprint"
    }
    return sha256(_canonical(body).encode("utf-8")).hexdigest()


def seal_operational_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Attach integrity metadata only. This does not verify live operations."""
    body = {
        key: receipt.get(key)
        for key in _RECEIPT_FIELDS
        if key != "receipt_fingerprint"
    }
    body["receipt_fingerprint"] = operational_receipt_fingerprint(body)
    return body


def _evidence_status(
    refs: Sequence[str],
    verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None,
) -> str:
    if not refs:
        return "MISSING"
    if not callable(verifier):
        return "UNVERIFIED"
    try:
        result = verifier(list(refs))
    except Exception:
        return "UNVERIFIED"
    if not isinstance(result, Mapping):
        return "UNVERIFIED"
    if _clean(result.get("state"), 40).upper() != "VERIFIED":
        return "UNVERIFIED"
    bound = _refs(result.get("bound_refs"))
    if sorted(bound) != sorted(refs) or len(bound) != len(refs):
        return "UNVERIFIED"
    return "VERIFIED"


def validate_coordination_operational_verification(
    receipt: Mapping[str, Any] | None,
    *,
    expected_adapter_identity_digest: Any,
    expected_scope_digest: Any,
    now: datetime | None,
    evidence_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate external live-probe evidence without running the probe."""
    raw = dict(receipt or {})
    blockers: list[str] = []
    unknown = sorted(set(raw) - set(_RECEIPT_FIELDS))
    missing = [key for key in _RECEIPT_FIELDS if key not in raw]
    if unknown:
        blockers.append("RECEIPT_UNKNOWN_FIELD:" + str(unknown[0]))
    if missing:
        blockers.append("RECEIPT_MISSING:" + str(missing[0]))

    if raw.get("schema") != RECEIPT_SCHEMA:
        blockers.append("RECEIPT_SCHEMA_INVALID")
    version = raw.get("receipt_version")
    if type(version) is not int or version != RECEIPT_VERSION:
        blockers.append("RECEIPT_VERSION_INVALID")

    expected_adapter = _clean(expected_adapter_identity_digest, 128)
    adapter = _clean(raw.get("adapter_identity_digest"), 128)
    if not expected_adapter or adapter != expected_adapter:
        blockers.append("ADAPTER_IDENTITY_MISMATCH")

    expected_scope = _clean(expected_scope_digest, 128)
    scope = _clean(raw.get("scope_digest"), 128)
    if not expected_scope or scope != expected_scope:
        blockers.append("SCOPE_DIGEST_MISMATCH")

    stored_fingerprint = _clean(raw.get("receipt_fingerprint"), 128)
    if not stored_fingerprint:
        blockers.append("RECEIPT_FINGERPRINT_REQUIRED")
    elif operational_receipt_fingerprint(raw) != stored_fingerprint:
        blockers.append("RECEIPT_FINGERPRINT_MISMATCH")

    issued = _aware(raw.get("issued_at"))
    expires = _aware(raw.get("expires_at"))
    current = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None
        else None
    )
    if issued is None or expires is None or current is None:
        blockers.append("RECEIPT_TIMESTAMP_INVALID")
    else:
        ttl = (expires - issued).total_seconds()
        if ttl <= 0 or ttl > MAX_RECEIPT_TTL_SECONDS:
            blockers.append("RECEIPT_TTL_INVALID")
        if issued > current:
            blockers.append("RECEIPT_FROM_FUTURE")
        elif current >= expires:
            blockers.append("RECEIPT_EXPIRED")

    if not _clean(raw.get("probe_run_id"), 120):
        blockers.append("PROBE_RUN_ID_REQUIRED")
    if not _clean(raw.get("namespace"), 180):
        blockers.append("PROBE_NAMESPACE_REQUIRED")
    if raw.get("namespace_is_ephemeral") is not True:
        blockers.append("EPHEMERAL_NAMESPACE_REQUIRED")
    if type(raw.get("production_mutation_count")) is not int or raw.get("production_mutation_count") != 0:
        blockers.append("PRODUCTION_MUTATION_DETECTED")
    if type(raw.get("isolated_mutation_count")) is not int or raw.get("isolated_mutation_count") < 1:
        blockers.append("ISOLATED_MUTATION_EVIDENCE_REQUIRED")
    if type(raw.get("concurrent_probe_count")) is not int or raw.get("concurrent_probe_count") < 2:
        blockers.append("MULTI_INSTANCE_PROBE_REQUIRED")

    observed = raw.get("observed_capabilities")
    if not isinstance(observed, Mapping):
        blockers.append("OBSERVED_CAPABILITIES_INVALID")
        observed_view = {}
    else:
        observed_view = {
            key: observed.get(key)
            for key in _REQUIRED_CAPABILITIES
        }
        if set(observed) != set(_REQUIRED_CAPABILITIES):
            blockers.append("OBSERVED_CAPABILITIES_INVALID")
        elif any(observed.get(key) is not True for key in _REQUIRED_CAPABILITIES):
            blockers.append("OPERATIONAL_CAPABILITY_NOT_VERIFIED")

    evidence_refs = _refs(raw.get("evidence_refs"))
    evidence_status = _evidence_status(evidence_refs, evidence_verifier)
    if evidence_status == "MISSING":
        blockers.append("OPERATIONAL_EVIDENCE_MISSING")
    elif evidence_status != "VERIFIED":
        blockers.append("OPERATIONAL_EVIDENCE_UNVERIFIED")

    blockers = list(dict.fromkeys(blockers))
    verified = not blockers
    return {
        "schema": SCHEMA,
        "state": "VERIFIED" if verified else "BLOCK",
        "operational_verification": "VERIFIED" if verified else "UNVERIFIED",
        "blockers": blockers,
        "adapter_identity_digest": adapter,
        "scope_digest": scope,
        "probe_run_id": _clean(raw.get("probe_run_id"), 120),
        "namespace": _clean(raw.get("namespace"), 180),
        "evidence_refs": evidence_refs,
        "evidence_status": evidence_status,
        "observed_capabilities": observed_view,
        "multi_instance_verified": verified,
        "probe_executed_by_this_module": False,
        "worker_activated": False,
        "activation_authorized": False,
        "changes_feature_flag": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "RECEIPT_SCHEMA",
    "RECEIPT_VERSION",
    "MAX_RECEIPT_TTL_SECONDS",
    "operational_receipt_fingerprint",
    "seal_operational_receipt",
    "validate_coordination_operational_verification",
]
