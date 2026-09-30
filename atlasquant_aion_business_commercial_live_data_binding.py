"""AION BUSINESS Commercial Live Data Binding V1.

Read-only contract for binding externally verified commercial records to the
internal B2B pipeline without storing raw credentials or personal contact data.

This module does not connect to CRM/e-mail/forms/payments, write external data,
send messages, advance a real pipeline, charge, sign, onboard, deploy or
activate runtime. It only validates caller-supplied connector evidence and
builds a bounded observed-state snapshot for admin review.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

from atlasquant_aion_business_b2b_revenue_offer import PIPELINE_STAGES

SCHEMA = "ATLASQUANT_AION_BUSINESS_COMMERCIAL_LIVE_DATA_BINDING_V1"
VERSION = "1"

ALLOWED_SOURCES = (
    "CRM",
    "FORMS",
    "EMAIL",
    "CALENDAR",
    "PAYMENTS",
    "ANALYTICS",
)

CONTACT_PERMISSION_STATES = (
    "UNKNOWN",
    "PERMITTED",
    "OPT_IN",
    "DO_NOT_CONTACT",
)

MAX_RECORDS = 500
DEFAULT_MAX_AGE_HOURS = 24.0

FORBIDDEN_RAW_FIELDS = frozenset({
    "email",
    "email_address",
    "phone",
    "phone_number",
    "mobile",
    "whatsapp_number",
    "full_name",
    "first_name",
    "last_name",
    "credential",
    "credentials",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
    "card_number",
    "cvv",
})


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _parse_time(value: Any) -> datetime | None:
    token = _clean(value, 80)
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _num(value: Any, *, minimum: float = 0.0, maximum: float | None = None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def live_binding_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "LIVE_READ_BINDING_CONTRACT_DEFINED",
        "allowed_sources": list(ALLOWED_SOURCES),
        "max_records_per_snapshot": MAX_RECORDS,
        "default_max_age_hours": DEFAULT_MAX_AGE_HOURS,
        "raw_personal_contact_fields_allowed": False,
        "raw_credentials_allowed": False,
        "external_write_allowed": False,
        "pipeline_auto_advance": False,
        "automatic_contact": False,
        "automatic_billing": False,
        "automatic_onboarding": False,
        "executes_action": False,
    }


def source_attestation(
    *,
    integration: Any,
    connection_ref: Any,
    authentication_verified: Any,
    read_only_scope_verified: Any,
    write_scope_present: Any,
    credential_value_present: Any,
    observed_at: Any,
) -> dict[str, Any]:
    token = _clean(integration, 80).upper()
    ref = _clean(connection_ref, 240)
    when = _parse_time(observed_at)

    gates = {
        "integration_allowed": token in ALLOWED_SOURCES,
        "connection_ref_present": bool(ref),
        "authentication_verified": authentication_verified is True,
        "read_only_scope_verified": read_only_scope_verified is True,
        "write_scope_absent": write_scope_present is False,
        "credential_value_absent": credential_value_present is False,
        "observed_at_valid": when is not None,
    }
    ready = all(gates.values())

    payload = {
        "integration": token,
        "connection_ref": ref,
        "observed_at": when.isoformat() if when else "",
        "read_only_scope_verified": True,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "SOURCE_ATTESTATION_READY" if ready else "SOURCE_ATTESTATION_BLOCKED",
        "integration": token if ready else "",
        "connection_ref": ref if ready else "",
        "observed_at": when.isoformat() if ready and when else "",
        "gates": gates,
        "attestation_digest": _digest(payload) if payload else "",
        "write_scope_present": False if ready else None,
        "credential_value_present": False if ready else None,
        "external_connection_executed_by_module": False,
        "executes_action": False,
    }


def normalize_commercial_snapshot(
    records: Sequence[Mapping[str, Any]] | None,
    *,
    tenant_id: Any,
    source_attestations: Sequence[Mapping[str, Any]] | None,
    now: datetime | None = None,
    max_age_hours: Any = DEFAULT_MAX_AGE_HOURS,
) -> dict[str, Any]:
    tenant = _clean(tenant_id, 120)
    current = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
    age_limit = _num(max_age_hours, minimum=0.01, maximum=168.0)

    blockers: list[str] = []
    if not tenant:
        blockers.append("TENANT_ID_REQUIRED")
    if age_limit is None:
        blockers.append("MAX_AGE_INVALID")
        age_limit = DEFAULT_MAX_AGE_HOURS

    raw_records = (
        list(records)
        if isinstance(records, Sequence) and not isinstance(records, (str, bytes, bytearray))
        else []
    )
    if not raw_records:
        blockers.append("COMMERCIAL_RECORDS_REQUIRED")
    if len(raw_records) > MAX_RECORDS:
        blockers.append("COMMERCIAL_RECORD_LIMIT_EXCEEDED")
        raw_records = raw_records[:MAX_RECORDS]

    raw_attestations = (
        list(source_attestations)
        if isinstance(source_attestations, Sequence)
        and not isinstance(source_attestations, (str, bytes, bytearray))
        else []
    )
    attestations: dict[str, dict[str, Any]] = {}
    for raw in raw_attestations:
        row = _mapping(raw)
        if row.get("schema") != SCHEMA or row.get("state") != "SOURCE_ATTESTATION_READY":
            continue
        integration = _clean(row.get("integration"), 80).upper()
        if integration in ALLOWED_SOURCES:
            attestations[integration] = row

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for index, raw in enumerate(raw_records, start=1):
        row = _mapping(raw)
        lower_keys = {str(key).strip().casefold() for key in row.keys()}
        forbidden = sorted(lower_keys.intersection(FORBIDDEN_RAW_FIELDS))
        if forbidden:
            blockers.append(f"record_{index}_raw_sensitive_fields_forbidden")
            continue

        source = _clean(row.get("source"), 80).upper()
        record_ref = _clean(row.get("record_ref"), 180)
        subject_ref = _clean(row.get("subject_ref"), 180)
        source_ref = _clean(row.get("source_ref"), 240)
        stage = _clean(row.get("stage"), 80).upper()
        permission = _clean(row.get("contact_permission_state"), 40).upper()
        observed = _parse_time(row.get("observed_at"))

        if source not in ALLOWED_SOURCES:
            blockers.append(f"record_{index}_source_invalid")
            continue
        if source not in attestations:
            blockers.append(f"record_{index}_source_not_attested")
            continue
        if not record_ref or not subject_ref or not source_ref:
            blockers.append(f"record_{index}_references_incomplete")
            continue
        if stage not in PIPELINE_STAGES:
            blockers.append(f"record_{index}_stage_invalid")
            continue
        if permission not in CONTACT_PERMISSION_STATES:
            blockers.append(f"record_{index}_permission_invalid")
            continue
        if observed is None:
            blockers.append(f"record_{index}_observed_at_invalid")
            continue

        age_hours = max(0.0, (current - observed).total_seconds() / 3600)
        if age_hours > age_limit:
            blockers.append(f"record_{index}_stale")
            continue

        key = (source, record_ref)
        if key in seen:
            blockers.append(f"record_{index}_duplicate_record")
            continue
        seen.add(key)

        value_brl = _num(row.get("estimated_value_brl"), maximum=100_000_000)
        confidence_pct = _num(row.get("source_confidence_pct"), maximum=100)

        normalized.append({
            "tenant_id": tenant,
            "source": source,
            "record_ref": record_ref,
            "subject_ref": subject_ref,
            "source_ref": source_ref,
            "stage": stage,
            "contact_permission_state": permission,
            "observed_at": observed.isoformat(),
            "age_hours": round(age_hours, 3),
            "estimated_value_brl": value_brl,
            "source_confidence_pct": confidence_pct,
            "raw_personal_contact_data_present": False,
            "raw_credentials_present": False,
        })

    ready = bool(normalized and not blockers)
    payload = {
        "tenant_id": tenant,
        "records": normalized,
        "attestation_digests": sorted(
            str(row.get("attestation_digest") or "")
            for row in attestations.values()
        ),
        "max_age_hours": age_limit,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "COMMERCIAL_LIVE_SNAPSHOT_READY" if ready else "COMMERCIAL_LIVE_SNAPSHOT_BLOCKED",
        "tenant_id": tenant,
        "record_count": len(normalized),
        "records": normalized,
        "source_count": len({row["source"] for row in normalized}),
        "max_age_hours": age_limit,
        "blockers": blockers,
        "snapshot_digest": _digest(payload) if payload else "",
        "truth_state": "EXTERNALLY_ATTESTED_READ_ONLY_INPUT" if ready else "UNVERIFIED",
        "pipeline_auto_advance": False,
        "external_write_authorized": False,
        "automatic_contact": False,
        "automatic_billing": False,
        "executes_action": False,
    }


def observed_pipeline_state(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    row = _mapping(snapshot)
    records = row.get("records")
    if (
        row.get("schema") != SCHEMA
        or row.get("state") != "COMMERCIAL_LIVE_SNAPSHOT_READY"
        or not isinstance(records, list)
    ):
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "OBSERVED_PIPELINE_BLOCKED",
            "counts": {},
            "executes_action": False,
        }

    counts = {stage: 0 for stage in PIPELINE_STAGES}
    do_not_contact = 0
    total_value = 0.0
    valued_records = 0
    for item in records:
        if not isinstance(item, Mapping):
            continue
        stage = _clean(item.get("stage"), 80).upper()
        if stage in counts:
            counts[stage] += 1
        if item.get("contact_permission_state") == "DO_NOT_CONTACT":
            do_not_contact += 1
        value = _num(item.get("estimated_value_brl"), maximum=100_000_000)
        if value is not None:
            total_value += value
            valued_records += 1

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "OBSERVED_PIPELINE_READY",
        "tenant_id": row.get("tenant_id"),
        "snapshot_digest": row.get("snapshot_digest"),
        "counts": counts,
        "record_count": len(records),
        "do_not_contact_count": do_not_contact,
        "observed_estimated_value_brl": round(total_value, 2),
        "valued_record_count": valued_records,
        "value_is_forecast_or_guarantee": False,
        "pipeline_state_is_observation_only": True,
        "pipeline_auto_advance": False,
        "contact_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def live_binding_review_packet(
    snapshot: Mapping[str, Any] | None,
    observed_pipeline: Mapping[str, Any] | None,
    *,
    requested_by: Any,
) -> dict[str, Any]:
    snap = _mapping(snapshot)
    pipeline = _mapping(observed_pipeline)
    requester = _clean(requested_by, 120)

    gates = {
        "snapshot_ready": snap.get("state") == "COMMERCIAL_LIVE_SNAPSHOT_READY",
        "snapshot_digest_present": bool(_clean(snap.get("snapshot_digest"), 128)),
        "observed_pipeline_ready": pipeline.get("state") == "OBSERVED_PIPELINE_READY",
        "same_snapshot": (
            bool(snap.get("snapshot_digest"))
            and pipeline.get("snapshot_digest") == snap.get("snapshot_digest")
        ),
        "requester_present": bool(requester),
        "no_external_write": snap.get("external_write_authorized") is False,
        "no_auto_contact": snap.get("automatic_contact") is False,
        "no_auto_billing": snap.get("automatic_billing") is False,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    payload = {
        "snapshot_digest": snap.get("snapshot_digest"),
        "tenant_id": snap.get("tenant_id"),
        "requested_by": requester,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_LIVE_READ_BINDING_REVIEW"
            if ready
            else "LIVE_READ_BINDING_REVIEW_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "tenant_id": snap.get("tenant_id") if ready else "",
        "record_count": snap.get("record_count") if ready else 0,
        "review_digest": _digest(payload) if payload else "",
        "real_connector_configuration_authorized": False,
        "external_write_authorized": False,
        "pipeline_write_authorized": False,
        "contact_authorized": False,
        "proposal_send_authorized": False,
        "billing_authorized": False,
        "onboarding_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "ALLOWED_SOURCES",
    "CONTACT_PERMISSION_STATES",
    "MAX_RECORDS",
    "DEFAULT_MAX_AGE_HOURS",
    "FORBIDDEN_RAW_FIELDS",
    "live_binding_policy",
    "source_attestation",
    "normalize_commercial_snapshot",
    "observed_pipeline_state",
    "live_binding_review_packet",
]
