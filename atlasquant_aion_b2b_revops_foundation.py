"""AION B2B RevOps Foundation V1.

Pure/offline CRM hygiene, funnel and permission-readiness contract for AION
Negócios. It validates records and returns evidence-bound readiness summaries.

It does not write to a CRM, send outreach, advance stages, assign owners,
commit pricing, sign contracts, delete records or contact customers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

SCHEMA = "ATLASQUANT_AION_B2B_REVOPS_FOUNDATION_V1"

PIPELINE_STAGES = (
    "LEAD",
    "DIAGNOSTIC",
    "DEMO",
    "PROPOSAL",
    "CONTRACT",
    "PAYMENT",
    "IMPLEMENTATION",
    "APPROVAL",
    "PUBLISHED",
    "FOLLOWUP",
    "ACTIVE_SERVICE",
    "CLOSED_LOST",
)

TERMINAL_STAGES = frozenset({"ACTIVE_SERVICE", "CLOSED_LOST"})
CONTACT_STATES = (
    "EVIDENCE_PRESENT",
    "UNKNOWN",
    "DO_NOT_CONTACT",
    "NOT_REQUIRED",
)
ROLES = (
    "OWNER",
    "DELEGATED_ADMIN",
    "SALES",
    "OPERATIONS",
    "VIEWER",
)
ACTIONS = (
    "CRM_READ",
    "CRM_EDIT",
    "STAGE_CHANGE",
    "ASSIGN_OWNER",
    "EXPORT",
    "DELETE",
    "OUTREACH",
    "PRICE_COMMITMENT",
    "CONTRACT_COMMITMENT",
)

_PERMISSION_MATRIX = {
    "OWNER": {
        "CRM_READ",
        "CRM_EDIT",
        "STAGE_CHANGE",
        "ASSIGN_OWNER",
        "EXPORT",
        "OUTREACH",
        "PRICE_COMMITMENT",
        "CONTRACT_COMMITMENT",
    },
    "DELEGATED_ADMIN": {
        "CRM_READ",
        "CRM_EDIT",
        "STAGE_CHANGE",
        "ASSIGN_OWNER",
        "EXPORT",
        "OUTREACH",
    },
    "SALES": {
        "CRM_READ",
        "CRM_EDIT",
        "STAGE_CHANGE",
        "OUTREACH",
    },
    "OPERATIONS": {
        "CRM_READ",
        "CRM_EDIT",
    },
    "VIEWER": {
        "CRM_READ",
    },
}

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _safe_id(value: Any) -> str:
    text = _text(value, 128)
    return text if _SAFE_ID.fullmatch(text) else ""


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _refs(value: Any, limit: int = 40) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 240)
        if item and item not in out:
            out.append(item)
    return out


def _aware(value: Any) -> datetime | None:
    text = _text(value, 96)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def revops_permission(role: Any, action: Any) -> dict[str, Any]:
    """Return role eligibility only; never execution authority."""
    normalized_role = _text(role, 40).upper()
    normalized_action = _text(action, 60).upper()
    blockers: list[str] = []
    if normalized_role not in ROLES:
        blockers.append("ROLE_INVALID")
    if normalized_action not in ACTIONS:
        blockers.append("ACTION_INVALID")
    eligible = (
        not blockers
        and normalized_action in _PERMISSION_MATRIX.get(normalized_role, set())
    )
    if normalized_action == "DELETE":
        eligible = False
        blockers.append("DESTRUCTIVE_DELETE_NOT_SUPPORTED")
    if (
        normalized_action in {"PRICE_COMMITMENT", "CONTRACT_COMMITMENT"}
        and normalized_role != "OWNER"
    ):
        eligible = False
        blockers.append("OWNER_ONLY_CRITICAL_COMMERCIAL_DECISION")
    if not eligible and not blockers:
        blockers.append("ROLE_NOT_ELIGIBLE")
    return {
        "schema": SCHEMA,
        "role": normalized_role,
        "action": normalized_action,
        "eligible": eligible,
        "blockers": list(dict.fromkeys(blockers)),
        "requires_live_authority_revalidation": True,
        "grants_authority": False,
        "executes_action": False,
    }


def normalize_revops_record(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize one B2B CRM/funnel record without trusting caller scope."""
    item = dict(raw) if isinstance(raw, Mapping) else {}
    scope = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    for key, expected in scope.items():
        claimed = _text(item.get(key), 120)
        if claimed and claimed != expected:
            blockers.append("RECORD_SCOPE_MISMATCH")

    lead_id = _safe_id(item.get("lead_id"))
    company_key = _safe_id(item.get("company_key"))
    company_label = _text(item.get("company_label"), 180)
    stage = _text(item.get("stage"), 40).upper()
    record_owner_ref = _safe_id(item.get("record_owner_ref"))
    source = _text(item.get("source"), 120).lower()
    next_action = _text(item.get("next_action"), 240)
    next_action_at = _text(item.get("next_action_at"), 96)
    updated_at = _text(item.get("updated_at"), 96)
    contact_state = _text(item.get("contact_state"), 40).upper()
    contact_evidence_refs = _refs(item.get("contact_evidence_refs"))
    evidence_refs = _refs(item.get("evidence_refs"))

    if not lead_id:
        blockers.append("LEAD_ID_INVALID")
    if not company_key:
        blockers.append("COMPANY_KEY_INVALID")
    if not company_label:
        blockers.append("COMPANY_LABEL_REQUIRED")
    if stage not in PIPELINE_STAGES:
        blockers.append("PIPELINE_STAGE_INVALID")
    if not record_owner_ref:
        blockers.append("RECORD_OWNER_REQUIRED")
    if not source:
        blockers.append("SOURCE_REQUIRED")
    if _aware(updated_at) is None:
        blockers.append("UPDATED_AT_INVALID")
    if contact_state not in CONTACT_STATES:
        blockers.append("CONTACT_STATE_INVALID")
    if contact_state == "EVIDENCE_PRESENT" and not contact_evidence_refs:
        blockers.append("CONTACT_EVIDENCE_REQUIRED")
    if stage not in TERMINAL_STAGES:
        if not next_action:
            blockers.append("NEXT_ACTION_REQUIRED")
        if _aware(next_action_at) is None:
            blockers.append("NEXT_ACTION_AT_INVALID")
    if not evidence_refs:
        blockers.append("RECORD_EVIDENCE_REQUIRED")

    identity = {
        **scope,
        "lead_id": lead_id,
        "company_key": company_key,
        "company_label": company_label,
        "stage": stage,
        "record_owner_ref": record_owner_ref,
        "source": source,
        "next_action": next_action,
        "next_action_at": next_action_at,
        "updated_at": updated_at,
        "contact_state": contact_state,
        "contact_evidence_refs": contact_evidence_refs,
        "evidence_refs": evidence_refs,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        **identity,
        "state": "ACCEPTED" if not blockers else "REJECTED",
        "blockers": blockers,
        "record_digest": _digest(identity),
        "automatic_outreach": False,
        "automatic_stage_change": False,
        "automatic_owner_assignment": False,
        "crm_write": False,
        "executes_action": False,
    }


def build_revops_foundation(
    records: Sequence[Mapping[str, Any]] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
    now: Any,
    stale_after_days: int = 14,
) -> dict[str, Any]:
    """Audit CRM hygiene and RevOps readiness without mutating any record."""
    scope = _scope(trusted_scope)
    blockers: list[str] = []
    warnings: list[str] = []

    current = _aware(now)
    if current is None:
        blockers.append("NOW_INVALID")
    if (
        isinstance(stale_after_days, bool)
        or not isinstance(stale_after_days, int)
        or stale_after_days < 1
        or stale_after_days > 365
    ):
        blockers.append("STALE_WINDOW_INVALID")
        stale_after_days = 14
    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_lead_ids: dict[str, str] = {}
    company_to_leads: dict[str, list[str]] = {}

    for raw in list(records or [])[:5000]:
        if not isinstance(raw, Mapping):
            rejected.append({
                "state": "REJECTED",
                "blockers": ["RECORD_INVALID"],
            })
            continue
        row = normalize_revops_record(raw, trusted_scope=scope)
        if row["state"] != "ACCEPTED":
            rejected.append(row)
            continue

        lead_id = row["lead_id"]
        prior = seen_lead_ids.get(lead_id)
        if prior is not None:
            if prior == row["record_digest"]:
                warnings.append("EXACT_RECORD_REPLAY")
            else:
                blockers.append("LEAD_ID_CONFLICT")
            continue

        seen_lead_ids[lead_id] = row["record_digest"]
        accepted.append(row)
        company_to_leads.setdefault(row["company_key"], []).append(lead_id)

    duplicate_company_candidates = {
        key: ids
        for key, ids in company_to_leads.items()
        if len(ids) > 1
    }
    if duplicate_company_candidates:
        warnings.append("COMPANY_DUPLICATE_CANDIDATES")

    stale_lead_ids: list[str] = []
    due_next_action_lead_ids: list[str] = []
    do_not_contact_lead_ids: list[str] = []
    unknown_contact_lead_ids: list[str] = []
    stage_counts = {stage: 0 for stage in PIPELINE_STAGES}

    for row in accepted:
        stage_counts[row["stage"]] += 1
        updated = _aware(row["updated_at"])
        if current is not None and updated is not None:
            age_days = (current - updated).total_seconds() / 86400.0
            if age_days > stale_after_days:
                stale_lead_ids.append(row["lead_id"])
        next_at = _aware(row["next_action_at"])
        if (
            current is not None
            and row["stage"] not in TERMINAL_STAGES
            and next_at is not None
            and next_at <= current
        ):
            due_next_action_lead_ids.append(row["lead_id"])
        if row["contact_state"] == "DO_NOT_CONTACT":
            do_not_contact_lead_ids.append(row["lead_id"])
        elif row["contact_state"] == "UNKNOWN":
            unknown_contact_lead_ids.append(row["lead_id"])

    if stale_lead_ids:
        warnings.append("STALE_RECORDS_PRESENT")
    if due_next_action_lead_ids:
        warnings.append("NEXT_ACTION_DUE")
    if unknown_contact_lead_ids:
        warnings.append("CONTACT_EVIDENCE_UNKNOWN")

    total = len(accepted)
    contact_evidence_count = sum(
        1 for row in accepted if row["contact_state"] == "EVIDENCE_PRESENT"
    )
    next_action_ready_count = sum(
        1
        for row in accepted
        if row["stage"] in TERMINAL_STAGES
        or (bool(row["next_action"]) and _aware(row["next_action_at"]) is not None)
    )
    owner_ready_count = sum(1 for row in accepted if row["record_owner_ref"])

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))

    if blockers:
        state = "BLOCKED"
    elif rejected:
        state = "PARTIAL"
    elif total == 0:
        state = "EMPTY"
    elif warnings:
        state = "READY_WITH_REVIEW"
    else:
        state = "READY"

    metrics = {
        "accepted_records": total,
        "rejected_records": len(rejected),
        "company_count": len(company_to_leads),
        "duplicate_company_candidate_count": len(duplicate_company_candidates),
        "stale_record_count": len(stale_lead_ids),
        "due_next_action_count": len(due_next_action_lead_ids),
        "do_not_contact_count": len(do_not_contact_lead_ids),
        "unknown_contact_count": len(unknown_contact_lead_ids),
        "contact_evidence_coverage_pct": (
            round(contact_evidence_count / total * 100.0, 4) if total else None
        ),
        "next_action_coverage_pct": (
            round(next_action_ready_count / total * 100.0, 4) if total else None
        ),
        "owner_coverage_pct": (
            round(owner_ready_count / total * 100.0, 4) if total else None
        ),
    }

    integrity_material = {
        "scope": scope,
        "records": [
            {
                "lead_id": row["lead_id"],
                "record_digest": row["record_digest"],
            }
            for row in accepted
        ],
        "state": state,
        "metrics": metrics,
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "scope": scope,
        "blockers": blockers,
        "warnings": warnings,
        "accepted_records": accepted,
        "rejected_records": rejected,
        "stage_counts": stage_counts,
        "duplicate_company_candidates": duplicate_company_candidates,
        "stale_lead_ids": stale_lead_ids,
        "due_next_action_lead_ids": due_next_action_lead_ids,
        "do_not_contact_lead_ids": do_not_contact_lead_ids,
        "unknown_contact_lead_ids": unknown_contact_lead_ids,
        "metrics": metrics,
        "snapshot_digest": _digest(integrity_material),
        "legal_contact_permission_certified": False,
        "automatic_outreach": False,
        "automatic_followup": False,
        "automatic_stage_change": False,
        "automatic_owner_assignment": False,
        "automatic_price_commitment": False,
        "automatic_contract_commitment": False,
        "destructive_delete_enabled": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PIPELINE_STAGES",
    "TERMINAL_STAGES",
    "CONTACT_STATES",
    "ROLES",
    "ACTIONS",
    "revops_permission",
    "normalize_revops_record",
    "build_revops_foundation",
]
