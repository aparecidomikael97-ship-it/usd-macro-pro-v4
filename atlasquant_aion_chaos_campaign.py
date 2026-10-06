"""AION evidence-bound chaos engineering campaign gate.

The gate aggregates deterministic staging drills across existing AION
resilience, durable-store, outbox, saga and integrity components. It never
injects faults into production and never executes an external action.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_CHAOS_CAMPAIGN_V1"
DOMAINS = (
    "PROVIDER",
    "NETWORK",
    "STORE",
    "QUEUE",
    "TOOL",
    "AGENT",
    "STATE_CORRUPTION",
)
MAX_OBSERVATIONS = 64


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(item.get("owner_id") or item.get("actor_id"), 120),
        "tenant_id": _text(item.get("tenant_id"), 120),
        "workspace_id": _text(item.get("workspace_id"), 120),
    }


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer() and value > 0:
        return int(value)
    return None


def _nonnegative_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out < 0:
        return None
    return out


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _refs(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:80]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "sha256:" + sha256(raw.encode("utf-8")).hexdigest()


def normalize_chaos_policy(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    trusted = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_REQUIRED")
    if item.get("state") != "VERIFIED":
        blockers.append("POLICY_NOT_VERIFIED")
    if any(_text(item.get(key), 120) != trusted[key] for key in trusted):
        blockers.append("POLICY_SCOPE_MISMATCH")

    policy_id = _text(item.get("policy_id"), 120)
    revision = _positive_int(item.get("revision"))
    max_age = _positive_int(item.get("max_observation_age_seconds"))
    if not policy_id:
        blockers.append("POLICY_ID_REQUIRED")
    if revision is None:
        blockers.append("POLICY_REVISION_INVALID")
    if max_age is None:
        blockers.append("MAX_OBSERVATION_AGE_INVALID")

    required = item.get("required_domains")
    domains: list[str] = []
    if not isinstance(required, (list, tuple)):
        blockers.append("REQUIRED_DOMAINS_INVALID")
    else:
        for raw_domain in required:
            domain = _text(raw_domain, 60).upper()
            if domain not in DOMAINS or domain in domains:
                blockers.append("REQUIRED_DOMAINS_INVALID")
            elif domain:
                domains.append(domain)
    if set(domains) != set(DOMAINS):
        blockers.append("ALL_CHAOS_DOMAINS_REQUIRED")

    recovery = item.get("max_recovery_seconds_by_domain")
    limits: dict[str, int] = {}
    if not isinstance(recovery, Mapping):
        blockers.append("RECOVERY_LIMITS_INVALID")
    else:
        for domain in DOMAINS:
            value = _positive_int(recovery.get(domain))
            if value is None:
                blockers.append("RECOVERY_LIMIT_INVALID:" + domain)
            else:
                limits[domain] = value

    return {
        "schema": SCHEMA,
        "state": "VERIFIED" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "policy_id": policy_id,
        "revision": revision,
        **trusted,
        "required_domains": domains,
        "max_observation_age_seconds": max_age,
        "max_recovery_seconds_by_domain": limits,
        "production_fault_injection_allowed": False,
        "external_action_allowed": False,
        "automatic_recovery_authority": False,
        "executes_action": False,
    }


def evaluate_chaos_campaign(
    *,
    trusted_scope: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None,
    observations: Sequence[Mapping[str, Any]] | None,
    checked_at: Any,
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    normalized_policy = normalize_chaos_policy(policy, trusted_scope=trusted)
    blockers = list(normalized_policy["blockers"])
    checked = _parse_ts(checked_at)
    if checked is None:
        blockers.append("CHECKED_AT_INVALID")
        checked = datetime(1970, 1, 1, tzinfo=timezone.utc)

    source = observations if isinstance(observations, (list, tuple)) else []
    if observations is not None and not isinstance(observations, (list, tuple)):
        blockers.append("OBSERVATIONS_COLLECTION_INVALID")
    if len(source) > MAX_OBSERVATIONS:
        blockers.append("OBSERVATION_BUDGET_EXCEEDED")
        source = source[:MAX_OBSERVATIONS]

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in source:
        row = dict(raw) if isinstance(raw, Mapping) else {}
        row_blockers: list[str] = []
        domain = _text(row.get("domain"), 60).upper()
        if domain not in DOMAINS:
            row_blockers.append("DOMAIN_INVALID")
        elif domain in seen:
            row_blockers.append("DUPLICATE_DOMAIN")
        else:
            seen.add(domain)

        if any(_text(row.get(key), 120) != trusted[key] for key in trusted):
            row_blockers.append("OBSERVATION_SCOPE_MISMATCH")
        if row.get("failure_observed") is not True:
            row_blockers.append("FAILURE_NOT_OBSERVED")
        if row.get("containment_verified") is not True:
            row_blockers.append("CONTAINMENT_NOT_VERIFIED")
        if row.get("recovery_verified") is not True:
            row_blockers.append("RECOVERY_NOT_VERIFIED")
        if row.get("production_mutation") is not False:
            row_blockers.append("PRODUCTION_MUTATION_FORBIDDEN")
        if row.get("external_action_executed") is not False:
            row_blockers.append("EXTERNAL_ACTION_FORBIDDEN")
        if row.get("automatic_authority") is not False:
            row_blockers.append("AUTOMATIC_AUTHORITY_FORBIDDEN")

        observed_at = _parse_ts(row.get("observed_at"))
        age_seconds = None
        if observed_at is None:
            row_blockers.append("OBSERVED_AT_INVALID")
        else:
            age_seconds = (checked - observed_at).total_seconds()
            if age_seconds < 0:
                row_blockers.append("OBSERVED_AT_FUTURE")
            elif (
                normalized_policy["state"] == "VERIFIED"
                and age_seconds > int(normalized_policy["max_observation_age_seconds"])
            ):
                row_blockers.append("OBSERVATION_STALE")

        recovery_seconds = _nonnegative_number(row.get("recovery_seconds"))
        if recovery_seconds is None:
            row_blockers.append("RECOVERY_SECONDS_INVALID")
        elif (
            normalized_policy["state"] == "VERIFIED"
            and domain in normalized_policy["max_recovery_seconds_by_domain"]
            and recovery_seconds > normalized_policy["max_recovery_seconds_by_domain"][domain]
        ):
            row_blockers.append("RECOVERY_TIME_EXCEEDED")

        refs = _refs(row.get("evidence_refs"))
        if not refs:
            row_blockers.append("EVIDENCE_REQUIRED")

        rows.append({
            "domain": domain or "UNKNOWN",
            "state": "VERIFIED" if not row_blockers else "BLOCKED",
            "failure_mode": _text(row.get("failure_mode"), 240),
            "containment": _text(row.get("containment"), 320),
            "recovery": _text(row.get("recovery"), 320),
            "observed_at": _text(row.get("observed_at"), 80),
            "age_seconds": age_seconds,
            "recovery_seconds": recovery_seconds,
            "evidence_refs": refs,
            "blockers": list(dict.fromkeys(row_blockers)),
        })

    missing = [domain for domain in DOMAINS if domain not in seen]
    blockers.extend("DOMAIN_MISSING:" + domain for domain in missing)
    for row in rows:
        blockers.extend(f"{row['domain']}:{reason}" for reason in row["blockers"])

    blockers = list(dict.fromkeys(blockers))
    ready = (
        not blockers
        and normalized_policy["state"] == "VERIFIED"
        and len(rows) == len(DOMAINS)
        and all(row["state"] == "VERIFIED" for row in rows)
    )
    material = {
        "scope": trusted,
        "policy_id": normalized_policy["policy_id"],
        "policy_revision": normalized_policy["revision"],
        "checked_at": _text(checked_at, 80),
        "observations": rows,
        "blockers": blockers,
    }
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_HUMAN_REVIEW" if ready else "BLOCKED",
        "blockers": blockers,
        "scope": trusted,
        "policy": normalized_policy,
        "observations": rows,
        "covered_domains": sorted(seen),
        "missing_domains": missing,
        "campaign_digest": _digest(material),
        "requires_human_review": ready,
        "production_fault_injection_authorized": False,
        "production_recovery_authorized": False,
        "automatic_retry_authorized": False,
        "automatic_compensation_authorized": False,
        "automatic_worker_restart_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def chaos_campaign_contract() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "required_domains": list(DOMAINS),
        "evidence_required": True,
        "scope_binding_required": True,
        "production_fault_injection_allowed": False,
        "automatic_recovery_authority": False,
        "automatic_compensation": False,
        "automatic_retry_after_ambiguity": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "DOMAINS",
    "normalize_chaos_policy",
    "evaluate_chaos_campaign",
    "chaos_campaign_contract",
]
