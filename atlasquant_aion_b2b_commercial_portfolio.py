"""Read-only multi-company commercial portfolio over Golden Path V1.

The portfolio intentionally consumes only opaque company references, validated
Golden Path journeys and an optional bounded administrative summary. It never
stores raw customer/payment data, performs CRM writes, contacts customers,
changes commercial stages, bills, activates services, deploys or mutates
production.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_b2b_commercial_golden_path import SCHEMA as JOURNEY_SCHEMA

SCHEMA = "ATLASQUANT_AION_B2B_COMMERCIAL_PORTFOLIO_V1"
MAX_COMPANIES = 200
ATTENTION_LIMIT = 50

PACKAGES = ("ESSENCIAL", "PROFISSIONAL", "COMPLETO")
SUBSCRIPTION_STATES = ("ACTIVE", "PENDING", "PAUSED", "CANCELLED", "NOT_APPLICABLE")
PAYMENT_STATES = ("PAID", "DUE", "OVERDUE", "NOT_APPLICABLE")
VALUE_STATES = ("STRONG_VALUE", "VALUE_CONFIRMED", "VALUE_AT_RISK", "LOW_VALUE")
HEALTH_STATES = ("HEALTHY", "REMEDIATION", "CAPACITY_HOLD", "INCIDENT_REVIEW")

ADMIN_SUMMARY_FIELDS = frozenset({
    "package",
    "subscription_state",
    "payment_state",
    "value_state",
    "observed_roi_pct",
    "health_state",
    "health_score",
    "capacity_utilization_pct",
    "source_evidence_digest",
})

_PRIORITY = {
    "BLOCKED": 0,
    "READY_WITH_GAPS": 1,
    "READY": 2,
    "EMPTY": 3,
}

_RISK_WEIGHT = {
    "PAYMENT_OVERDUE": 50,
    "CAPACITY_PRESSURE": 35,
    "INCIDENT_REVIEW": 30,
    "LOW_VALUE": 30,
    "VALUE_AT_RISK": 25,
    "REMEDIATION": 20,
    "SUBSCRIPTION_PAUSED": 15,
    "PAYMENT_DUE": 10,
}

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _text(value: Any, limit: int = 180) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _pct(value: Any) -> float | None:
    out = _number(value)
    if out is None or out < 0 or out > 100:
        return None
    return round(out, 2)


def _roi(value: Any) -> float | None:
    out = _number(value)
    if out is None or out < -1_000_000 or out > 1_000_000:
        return None
    return round(out, 2)


def _capacity_state(utilization_pct: float | None) -> str:
    if utilization_pct is None:
        return "UNKNOWN"
    if utilization_pct < 70:
        return "NORMAL"
    if utilization_pct < 90:
        return "WATCH"
    return "PRESSURE"


def _delinquency_signal(payment_state: str) -> str:
    return {
        "PAID": "CLEAR",
        "DUE": "DUE",
        "OVERDUE": "OVERDUE",
        "NOT_APPLICABLE": "NOT_APPLICABLE",
    }.get(payment_state, "UNKNOWN")


def _empty_admin_summary() -> dict[str, Any]:
    return {
        "package": "UNASSIGNED",
        "subscription_state": "UNKNOWN",
        "payment_state": "UNKNOWN",
        "delinquency_signal": "UNKNOWN",
        "value_state": "UNKNOWN",
        "observed_roi_pct": None,
        "health_state": "UNKNOWN",
        "health_score": None,
        "capacity_utilization_pct": None,
        "capacity_state": "UNKNOWN",
        "source_evidence_digest": "",
        "admin_summary_present": False,
        "admin_attention_reasons": [],
        "admin_attention_score": 0,
    }


def _safe_admin_summary(raw: Any) -> tuple[dict[str, Any], list[str]]:
    if raw is None:
        return _empty_admin_summary(), []
    if not isinstance(raw, Mapping):
        return _empty_admin_summary(), ["ADMIN_SUMMARY_INVALID"]

    data = dict(raw)
    extra = sorted(set(data) - ADMIN_SUMMARY_FIELDS)
    if extra:
        return _empty_admin_summary(), [
            "ADMIN_SUMMARY_FIELD_UNSAFE:" + ",".join(extra)
        ]

    blockers: list[str] = []
    package = _text(data.get("package"), 40).upper()
    subscription = _text(data.get("subscription_state"), 40).upper()
    payment = _text(data.get("payment_state"), 40).upper()
    value_state = _text(data.get("value_state"), 40).upper()
    health_state = _text(data.get("health_state"), 40).upper()
    evidence_digest = _text(data.get("source_evidence_digest"), 80).lower()

    if package and package not in PACKAGES:
        blockers.append("ADMIN_PACKAGE_INVALID")
    if subscription and subscription not in SUBSCRIPTION_STATES:
        blockers.append("ADMIN_SUBSCRIPTION_STATE_INVALID")
    if payment and payment not in PAYMENT_STATES:
        blockers.append("ADMIN_PAYMENT_STATE_INVALID")
    if value_state and value_state not in VALUE_STATES:
        blockers.append("ADMIN_VALUE_STATE_INVALID")
    if health_state and health_state not in HEALTH_STATES:
        blockers.append("ADMIN_HEALTH_STATE_INVALID")
    if not _SHA256_RE.fullmatch(evidence_digest):
        blockers.append("ADMIN_EVIDENCE_DIGEST_REQUIRED")

    roi = None
    if data.get("observed_roi_pct") is not None:
        roi = _roi(data.get("observed_roi_pct"))
        if roi is None:
            blockers.append("ADMIN_ROI_INVALID")

    health_score = None
    if data.get("health_score") is not None:
        health_score = _pct(data.get("health_score"))
        if health_score is None:
            blockers.append("ADMIN_HEALTH_SCORE_INVALID")

    capacity_pct = None
    if data.get("capacity_utilization_pct") is not None:
        capacity_pct = _pct(data.get("capacity_utilization_pct"))
        if capacity_pct is None:
            blockers.append("ADMIN_CAPACITY_UTILIZATION_INVALID")

    if blockers:
        return _empty_admin_summary(), blockers

    package = package or "UNASSIGNED"
    subscription = subscription or "UNKNOWN"
    payment = payment or "UNKNOWN"
    value_state = value_state or "UNKNOWN"
    health_state = health_state or "UNKNOWN"
    capacity_state = _capacity_state(capacity_pct)
    delinquency = _delinquency_signal(payment)

    attention: list[str] = []
    if payment == "OVERDUE":
        attention.append("PAYMENT_OVERDUE")
    elif payment == "DUE":
        attention.append("PAYMENT_DUE")
    if capacity_state == "PRESSURE":
        attention.append("CAPACITY_PRESSURE")
    if value_state in {"VALUE_AT_RISK", "LOW_VALUE"}:
        attention.append(value_state)
    if health_state in {"REMEDIATION", "INCIDENT_REVIEW"}:
        attention.append(health_state)
    if subscription == "PAUSED":
        attention.append("SUBSCRIPTION_PAUSED")

    return {
        "package": package,
        "subscription_state": subscription,
        "payment_state": payment,
        "delinquency_signal": delinquency,
        "value_state": value_state,
        "observed_roi_pct": roi,
        "health_state": health_state,
        "health_score": health_score,
        "capacity_utilization_pct": capacity_pct,
        "capacity_state": capacity_state,
        "source_evidence_digest": evidence_digest,
        "admin_summary_present": True,
        "admin_attention_reasons": attention,
        "admin_attention_score": sum(_RISK_WEIGHT.get(item, 0) for item in attention),
    }, []


def _safe_journey(raw: Any) -> tuple[dict[str, Any], list[str]]:
    row = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    if row.get("schema") != JOURNEY_SCHEMA:
        blockers.append("JOURNEY_SCHEMA_INVALID")
    if row.get("state") not in {"EMPTY", "READY", "READY_WITH_GAPS", "BLOCKED"}:
        blockers.append("JOURNEY_STATE_INVALID")
    if row.get("read_only") is not True:
        blockers.append("JOURNEY_READ_ONLY_REQUIRED")
    if row.get("grants_authority") is not False:
        blockers.append("JOURNEY_AUTHORITY_UNSAFE")
    if row.get("executes_action") is not False:
        blockers.append("JOURNEY_EXECUTION_UNSAFE")
    for key, value in row.items():
        if key.startswith("automatic_") and value is True:
            blockers.append("JOURNEY_AUTOMATION_UNSAFE:" + key)
    return row, blockers


def _counter(keys: Sequence[str]) -> dict[str, int]:
    return {key: 0 for key in keys}


def build_commercial_portfolio(
    *,
    portfolio_scope: Mapping[str, Any] | None,
    companies: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    scope = dict(portfolio_scope) if isinstance(portfolio_scope, Mapping) else {}
    owner_id = _text(scope.get("owner_id"), 120)
    workspace_id = _text(scope.get("workspace_id"), 120)
    blockers: list[str] = []
    if not owner_id or not workspace_id:
        blockers.append("PORTFOLIO_SCOPE_INVALID")

    rows = list(companies or [])
    if len(rows) > MAX_COMPANIES:
        blockers.append("COMPANY_LIMIT_EXCEEDED")
        rows = rows[:MAX_COMPANIES]

    items: list[dict[str, Any]] = []
    stage_counts: dict[str, int] = {}
    state_counts = _counter(("EMPTY", "READY", "READY_WITH_GAPS", "BLOCKED"))
    package_counts = _counter((*PACKAGES, "UNASSIGNED"))
    subscription_counts = _counter((*SUBSCRIPTION_STATES, "UNKNOWN"))
    payment_counts = _counter((*PAYMENT_STATES, "UNKNOWN"))
    value_counts = _counter((*VALUE_STATES, "UNKNOWN"))
    health_counts = _counter((*HEALTH_STATES, "UNKNOWN"))
    capacity_counts = _counter(("NORMAL", "WATCH", "PRESSURE", "UNKNOWN"))
    delinquency_counts = _counter(("CLEAR", "DUE", "OVERDUE", "NOT_APPLICABLE", "UNKNOWN"))
    seen_refs: set[str] = set()
    admin_summary_coverage_count = 0

    for index, raw in enumerate(rows):
        entry = dict(raw) if isinstance(raw, Mapping) else {}
        company_ref = _text(entry.get("company_ref"), 120)
        if not company_ref:
            blockers.append(f"COMPANY_REF_REQUIRED:{index}")
            continue
        if company_ref in seen_refs:
            blockers.append(f"COMPANY_REF_DUPLICATE:{company_ref}")
            continue
        seen_refs.add(company_ref)

        journey, journey_blockers = _safe_journey(entry.get("journey"))
        if journey_blockers:
            blockers.extend(f"{company_ref}:{item}" for item in journey_blockers)
            continue

        admin, admin_blockers = _safe_admin_summary(entry.get("admin_summary"))
        if admin_blockers:
            blockers.extend(f"{company_ref}:{item}" for item in admin_blockers)
            continue

        state = str(journey.get("state"))
        current_stage = _text(journey.get("current_stage"), 80)
        current_label = _text(journey.get("current_stage_label"), 140)
        next_action = _text(journey.get("next_human_action"), 140)
        gap_count = len(list(journey.get("lineage_gaps") or []))
        item = {
            "company_ref": company_ref,
            "state": state,
            "current_stage": current_stage,
            "current_stage_label": current_label,
            "next_human_action": next_action,
            "lineage_gap_count": gap_count,
            "blocked": state == "BLOCKED",
            "journey_evidence_digest": _text(journey.get("evidence_digest"), 180),
            **admin,
        }
        items.append(item)

        state_counts[state] += 1
        stage_key = current_stage or "not_started"
        stage_counts[stage_key] = stage_counts.get(stage_key, 0) + 1
        package_counts[admin["package"]] += 1
        subscription_counts[admin["subscription_state"]] += 1
        payment_counts[admin["payment_state"]] += 1
        value_counts[admin["value_state"]] += 1
        health_counts[admin["health_state"]] += 1
        capacity_counts[admin["capacity_state"]] += 1
        delinquency_counts[admin["delinquency_signal"]] += 1
        if admin["admin_summary_present"]:
            admin_summary_coverage_count += 1

    queue = sorted(
        items,
        key=lambda item: (
            _PRIORITY.get(item["state"], 9),
            -int(item["admin_attention_score"]),
            -int(item["lineage_gap_count"]),
            item["company_ref"],
        ),
    )[:ATTENTION_LIMIT]

    material = {
        "owner_id": owner_id,
        "workspace_id": workspace_id,
        "company_count": len(items),
        "state_counts": state_counts,
        "stage_counts": stage_counts,
        "package_counts": package_counts,
        "subscription_counts": subscription_counts,
        "payment_counts": payment_counts,
        "value_state_counts": value_counts,
        "health_state_counts": health_counts,
        "capacity_state_counts": capacity_counts,
        "delinquency_counts": delinquency_counts,
        "admin_summary_coverage_count": admin_summary_coverage_count,
        "attention_queue": queue,
    }
    state = "BLOCKED" if blockers else "READY"
    return {
        "schema": SCHEMA,
        "state": state,
        "scope": {"owner_id": owner_id, "workspace_id": workspace_id},
        "company_count": len(items),
        "state_counts": state_counts,
        "stage_counts": stage_counts,
        "package_counts": package_counts,
        "subscription_counts": subscription_counts,
        "payment_counts": payment_counts,
        "value_state_counts": value_counts,
        "health_state_counts": health_counts,
        "capacity_state_counts": capacity_counts,
        "delinquency_counts": delinquency_counts,
        "admin_summary_coverage_count": admin_summary_coverage_count,
        "attention_queue": queue,
        "blockers": list(dict.fromkeys(blockers)),
        "evidence_digest": _digest(material),
        "read_only": True,
        "company_ref_only": True,
        "admin_summary_only": True,
        "tenant_identity_exposed": False,
        "contact_data_exposed": False,
        "raw_customer_data_exposed": False,
        "raw_payment_data_exposed": False,
        "payment_amount_exposed": False,
        "banking_data_exposed": False,
        "crm_write": False,
        "automatic_outreach": False,
        "automatic_followup": False,
        "automatic_stage_change": False,
        "automatic_billing": False,
        "automatic_activation": False,
        "automatic_package_change": False,
        "automatic_quota_change": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PACKAGES",
    "SUBSCRIPTION_STATES",
    "PAYMENT_STATES",
    "VALUE_STATES",
    "HEALTH_STATES",
    "ADMIN_SUMMARY_FIELDS",
    "build_commercial_portfolio",
]
