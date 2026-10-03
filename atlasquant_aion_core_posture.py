"""Read-only posture for AION core hardening.

Observability, staged release, rollback planning, audit records, provider
fallback and contract envelopes. Nothing here activates runtime, calls a
provider, writes outside the process, or turns a missing fact into HEALTHY.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_aion_core_intelligence.registry import Registry
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_CORE_POSTURE_V1"
OBSERVATION_STATES = ("HEALTHY", "DEGRADED", "BLOCKED", "UNKNOWN", "NOT_CONFIGURED", "NOT_EVIDENCED")
RELEASE_STAGES = ("DISABLED", "LAB", "SHADOW", "PAPER", "ADMIN", "PUBLIC")
ROLLBACK_STATES = ("READY", "BLOCKED", "UNKNOWN")
IMMUTABLE_OFF_FLAGS = (
    "REAL_TRADING_ENABLED",
    "AION_EXTERNAL_ACTIONS_ENABLED",
    "SPECIALIST_FUTURE_RUNTIME_ENABLED",
    "GLOBAL_WORKER_ENABLED",
    "PAYMENT_ENABLED",
    "PUBLICATION_ENABLED",
)
SECTIONS = (
    "specialist",
    "registry",
    "capability",
    "evidence",
    "memory",
    "checkpoint",
    "queue",
    "approvals",
    "executor",
    "provider",
    "degraded",
    "errors",
    "retries",
    "cost",
    "runtime_flags",
    "certification",
    "build_identity",
)
PROVIDER_CONDITIONS = (
    "provider_unavailable",
    "timeout",
    "quota",
    "invalid_response",
    "stale_response",
    "missing_evidence",
    "conflicting_sources",
)
_SHA = re.compile(r"^[0-9a-f]{7,64}$")
_MAX_RECORDS = 100
_MAX_TEXT = 240


def _clean(value: Any, limit: int = _MAX_TEXT) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _exact_true(value: Any) -> bool:
    return type(value) is bool and value is True


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _redacted(value: Any) -> str:
    return _clean(redact_text(_clean(value, 800)), _MAX_TEXT)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _section_state(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or not raw:
        return {"state": "NOT_EVIDENCED", "truncated": False}
    state = _clean(raw.get("state"), 40).upper()
    truncated = False
    if state not in OBSERVATION_STATES:
        state = "UNKNOWN"
    if state == "HEALTHY" and not _exact_true(raw.get("evidence_verified")):
        state = "UNKNOWN"
    detail = _redacted(raw.get("detail"))
    if len(str(raw.get("detail") or "")) > _MAX_TEXT:
        truncated = True
        if state == "HEALTHY":
            state = "UNKNOWN"
    return {
        "state": state,
        "detail": detail,
        "evidence_verified": _exact_true(raw.get("evidence_verified")),
        "truncated": truncated,
    }


def aion_core_observability_snapshot(evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Read local registry facts and caller-supplied evidence. Missing evidence stays unproven."""
    supplied = _mapping(evidence)
    sections = {name: _section_state(supplied.get(name)) for name in SECTIONS}
    registry = Registry(checkpoint_connected=False)
    specialists = []
    for name in ("TRADER_FUTURE", "BUSINESS_FUTURE", "INVESTMENTS_FUTURE"):
        row = registry.get(name)
        specialists.append({
            "name": name,
            "domain_recognized": row.get("domain_recognized") is True,
            "profile_registered": row.get("specialist_profile_registered") is True,
            "runtime_capability_available": row.get("runtime_capability_available") is True,
            "specialist_certified": row.get("specialist_certified") is True,
            "certification_state": row.get("certification_state") or "NOT_CERTIFIED",
            "state": "BLOCKED" if row.get("available") is False else "UNKNOWN",
            "reason": row.get("reason") or "UNKNOWN",
        })
    return {
        "schema": SCHEMA,
        "version": 1,
        "sections": sections,
        "specialists": specialists,
        "healthy_invented": False,
        "provider_called": False,
        "executes_action": False,
        "runtime_activated": False,
    }


def normalize_security_flag(name: Any, value: Any) -> dict[str, Any]:
    flag = _clean(name, 80).upper()
    immutable = flag in IMMUTABLE_OFF_FLAGS
    enabled = False if immutable or not flag else _exact_true(value)
    return {
        "schema": SCHEMA,
        "flag": flag or "UNKNOWN",
        "enabled": enabled,
        "immutable_off": immutable,
        "accepted_bool": _exact_true(value),
        "malformed": not isinstance(value, bool),
        "activates_runtime": False,
    }


def staged_release_plan(stage: Any, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Record a requested stage without promoting the effective stage off DISABLED."""
    requested = _clean(stage, 40).upper() or "DISABLED"
    known = requested in RELEASE_STAGES
    payload = _mapping(evidence)
    evidence_sufficient = _exact_true(payload.get("gate_passed")) and _exact_true(payload.get("human_release_approved"))
    return {
        "schema": SCHEMA,
        "requested_stage": requested if known else "DISABLED",
        "requested_stage_known": known,
        "effective_stage": "DISABLED",
        "promoted": False,
        "evidence_sufficient": evidence_sufficient,
        "activates_runtime": False,
        "real_trading_enabled": False,
        "external_actions_enabled": False,
    }


def build_rollback_plan(evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Describe a rollback. READY requires an intact checkpoint, version and artifact ref."""
    payload = _mapping(evidence)
    version = _clean(payload.get("known_good_version"), 80)
    artifact = _clean(payload.get("artifact_ref"), 180)
    reason = _redacted(payload.get("reason"))
    intact = _exact_true(payload.get("checkpoint_intact"))
    blockers = [_redacted(item) for item in list(payload.get("blockers") or [])[:20] if _clean(item, 20)]
    truncated = len(list(payload.get("blockers") or [])) > 20
    if not payload:
        state = "UNKNOWN"
    elif intact and version and artifact and not truncated:
        state = "READY"
    else:
        state = "BLOCKED"
        if truncated and "TRUNCATED_BLOCKERS" not in blockers:
            blockers.append("TRUNCATED_BLOCKERS")
    return {
        "schema": SCHEMA,
        "state": state,
        "ready": state == "READY",
        "executes_rollback": False,
        "last_intact_checkpoint": _clean(payload.get("checkpoint_ref"), 180) if intact else "",
        "known_good_version": version,
        "reason": reason,
        "artifact_ref": artifact,
        "blockers": blockers,
        "human_approval_required": True,
        "truncated": truncated,
        "provider_called": False,
    }


def normalize_audit_trail(records: Sequence[Any] | None) -> dict[str, Any]:
    """Bound and redact local audit rows. A row never authorizes an action."""
    rows = []
    truncated = len(list(records or [])) > _MAX_RECORDS
    for raw in list(records or [])[:_MAX_RECORDS]:
        if not isinstance(raw, Mapping):
            continue
        body = {
            "requester": _redacted(raw.get("requester")),
            "timestamp": _clean(raw.get("timestamp"), 80),
            "tenant": _clean(raw.get("tenant"), 80),
            "workspace": _clean(raw.get("workspace"), 80),
            "actor": _redacted(raw.get("actor")),
            "task": _clean(raw.get("task"), 80),
            "domain": _clean(raw.get("domain"), 40).upper(),
            "specialist": _clean(raw.get("specialist"), 80),
            "capability": _clean(raw.get("capability"), 80),
            "evidence_refs": [_clean(item, 180) for item in list(raw.get("evidence_refs") or [])[:10] if _clean(item, 20)],
            "authorization_result": _clean(raw.get("authorization_result"), 40).upper() or "UNKNOWN",
            "approval_required": raw.get("approval_required") is True,
            "execution_mode": _clean(raw.get("execution_mode"), 40).upper() or "READ_ONLY",
            "result_state": _clean(raw.get("result_state"), 40).upper() or "UNKNOWN",
            "blocker": _redacted(raw.get("blocker")),
            "correlation_id": _clean(raw.get("correlation_id"), 80),
        }
        body["fingerprint"] = sha256(_canonical(body).encode("utf-8")).hexdigest()
        body["authorizes_action"] = False
        rows.append(body)
    return {
        "schema": SCHEMA,
        "records": rows,
        "truncated": truncated,
        "authorizes_action": False,
        "external_write": False,
        "count": len(rows),
    }


def provider_degraded_decision(
    condition: Any,
    cached: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Choose a local fallback. Stale cache is not a current fact and nothing is invented."""
    name = _clean(condition, 60).lower()
    known = name in PROVIDER_CONDITIONS
    cache = _mapping(cached)
    fresh = _exact_true(cache.get("fresh"))
    use_cache = (
        known
        and name not in {"stale_response", "missing_evidence", "conflicting_sources", "invalid_response"}
        and fresh
        and cache.get("truth_state") == "CONFIRMED"
    )
    if name in {"missing_evidence", "conflicting_sources"} or not known:
        mode = "UNKNOWN"
    elif name == "stale_response" or (cache and not fresh):
        mode = "DEGRADED_SAFE"
    else:
        mode = "DEGRADED_SAFE"
    return {
        "schema": SCHEMA,
        "condition": name or "missing_evidence",
        "condition_known": known,
        "mode": mode,
        "fallback": "cached_verified_evidence" if use_cache else "local_truthful_summary" if known else "UNKNOWN",
        "cache_used_as_current_fact": use_cache,
        "cache_visible": use_cache,
        "invented_value": False,
        "provider_called": False,
        "simulated_provider_result": False,
        "truth_state": "CONFIRMED" if use_cache else "UNKNOWN",
    }


def validate_contract_envelope(
    payload: Mapping[str, Any] | None,
    *,
    schema: str,
    supported_versions: Sequence[Any],
    enum_fields: Mapping[str, Sequence[str]] | None = None,
    field_types: Mapping[str, type] | None = None,
) -> dict[str, Any]:
    """Fail closed on schema drift, missing version, unknown enum or type mismatch."""
    raw = payload if isinstance(payload, Mapping) else {}
    versions = {int(item) for item in supported_versions if isinstance(item, int) and not isinstance(item, bool)}
    errors = []
    if raw.get("schema") != schema:
        errors.append("SCHEMA_MISMATCH")
    version = raw.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        errors.append("VERSION_MISSING_OR_MALFORMED")
    elif version not in versions:
        errors.append("VERSION_UNSUPPORTED")
    for field, choices in _mapping(enum_fields).items():
        if field in raw and _clean(raw.get(field), 40).upper() not in {str(item).upper() for item in choices}:
            errors.append("ENUM_MISMATCH:" + field)
    for field, expected in _mapping(field_types).items():
        if field in raw and not isinstance(raw.get(field), expected):
            errors.append("TYPE_MISMATCH:" + field)
    return {
        "schema": SCHEMA,
        "accepted": not errors,
        "state": "ACCEPTED" if not errors else "REJECTED",
        "errors": errors,
        "executes_action": False,
    }


def executor_safety_posture() -> dict[str, Any]:
    """Report the existing local retry ceiling without starting a worker."""
    from atlasquant_aion_background_executor import MAX_ATTEMPTS, RETRY_BACKOFF_SECONDS
    bounded = isinstance(MAX_ATTEMPTS, int) and MAX_ATTEMPTS > 0 and MAX_ATTEMPTS <= 5
    return {
        "schema": SCHEMA,
        "max_attempts": MAX_ATTEMPTS if bounded else 0,
        "backoff_steps": len(RETRY_BACKOFF_SECONDS) if bounded else 0,
        "retry_bounded": bounded,
        "global_worker_enabled": False,
        "executes_action": False,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


def sha_is_reference(value: Any) -> bool:
    return bool(_SHA.fullmatch(_clean(value, 80).lower()))


__all__ = [
    "SCHEMA",
    "OBSERVATION_STATES",
    "RELEASE_STAGES",
    "ROLLBACK_STATES",
    "IMMUTABLE_OFF_FLAGS",
    "aion_core_observability_snapshot",
    "normalize_security_flag",
    "staged_release_plan",
    "build_rollback_plan",
    "normalize_audit_trail",
    "provider_degraded_decision",
    "validate_contract_envelope",
    "executor_safety_posture",
    "sha_is_reference",
]
