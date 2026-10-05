"""Read-only customer portal records for B2B managed services.

Normalizes tenant-scoped integration, CRM-summary, document and billing metadata.
No secrets, payment links, provider actions, signatures, billing mutation or account
changes are permitted.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_CUSTOMER_PORTAL_RECORDS_V1"

INTEGRATION_STATES = {"CONNECTED", "DEGRADED", "DISCONNECTED", "PENDING"}
DOCUMENT_TYPES = {"CONTRACT", "PROPOSAL", "REPORT", "INVOICE", "OTHER"}
DOCUMENT_STATES = {"DRAFT", "ACTIVE", "SIGNED", "ISSUED", "EXPIRED", "SUPERSEDED"}
SUBSCRIPTION_STATES = {"ACTIVE", "PENDING", "PAUSED", "CANCELLED", "NOT_APPLICABLE"}
PAYMENT_STATES = {"PAID", "DUE", "OVERDUE", "NOT_APPLICABLE"}
FORBIDDEN_KEY_PARTS = ("password", "secret", "token", "api_key", "credential", "authorization")


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(value: Any, limit: int = 50) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _contains_forbidden_key(value: Any, depth: int = 0) -> bool:
    if depth > 8:
        return True
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key or "").strip().casefold()
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                return True
            if _contains_forbidden_key(item, depth + 1):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(item, depth + 1) for item in value[:100])
    return False


def build_customer_portal_records(
    *,
    trusted_scope: Mapping[str, Any],
    customer_id: str,
    package: str,
    raw: Mapping[str, Any] | None,
) -> dict[str, Any]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    trusted = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if _scope(data) != trusted:
        blockers.append("PORTAL_RECORD_SCOPE_MISMATCH")

    expected_customer = _text(customer_id, 120)
    expected_package = _text(package, 40).upper()
    if _text(data.get("customer_id"), 120) != expected_customer:
        blockers.append("PORTAL_RECORD_CUSTOMER_MISMATCH")
    if _text(data.get("package"), 40).upper() != expected_package:
        blockers.append("PORTAL_RECORD_PACKAGE_MISMATCH")

    if _contains_forbidden_key(data):
        blockers.append("PORTAL_RECORD_SECRET_LIKE_FIELD_REJECTED")

    evidence_refs = _refs(data.get("evidence_refs"))
    if len(evidence_refs) < 4:
        blockers.append("PORTAL_RECORD_EVIDENCE_INSUFFICIENT")

    integrations: list[dict[str, Any]] = []
    raw_integrations = data.get("integrations")
    if raw_integrations is not None and not isinstance(raw_integrations, (list, tuple)):
        blockers.append("INTEGRATIONS_INVALID")
    for raw_item in list(raw_integrations or [])[:20]:
        if not isinstance(raw_item, Mapping):
            blockers.append("INTEGRATION_ITEM_INVALID")
            continue
        integration_id = _text(raw_item.get("integration_id"), 100)
        name = _text(raw_item.get("name"), 120)
        state = _text(raw_item.get("state"), 40).upper()
        last_checked_at = _text(raw_item.get("last_checked_at"), 96)
        if not integration_id or not name or state not in INTEGRATION_STATES or not last_checked_at:
            blockers.append("INTEGRATION_ITEM_INVALID")
            continue
        integrations.append({
            "integration_id": integration_id,
            "name": name,
            "state": state,
            "last_checked_at": last_checked_at,
        })

    crm = data.get("crm")
    crm = dict(crm) if isinstance(crm, Mapping) else {}
    crm_enabled = crm.get("enabled") is True
    crm_summary: dict[str, Any] = {"enabled": crm_enabled}
    if crm_enabled:
        for key in ("contacts", "open_opportunities", "open_tasks", "won_this_cycle"):
            value = _nonnegative_int(crm.get(key))
            if value is None:
                blockers.append(f"CRM_{key.upper()}_INVALID")
            crm_summary[key] = value

    documents: list[dict[str, Any]] = []
    raw_docs = data.get("documents")
    if raw_docs is not None and not isinstance(raw_docs, (list, tuple)):
        blockers.append("DOCUMENTS_INVALID")
    seen_doc_ids: set[str] = set()
    for raw_item in list(raw_docs or [])[:50]:
        if not isinstance(raw_item, Mapping):
            blockers.append("DOCUMENT_ITEM_INVALID")
            continue
        document_id = _text(raw_item.get("document_id"), 120)
        title = _text(raw_item.get("title"), 180)
        doc_type = _text(raw_item.get("type"), 40).upper()
        state = _text(raw_item.get("state"), 40).upper()
        issued_at = _text(raw_item.get("issued_at"), 96)
        version = _text(raw_item.get("version"), 40)
        if (
            not document_id
            or document_id in seen_doc_ids
            or not title
            or doc_type not in DOCUMENT_TYPES
            or state not in DOCUMENT_STATES
            or not issued_at
        ):
            blockers.append("DOCUMENT_ITEM_INVALID")
            continue
        seen_doc_ids.add(document_id)
        documents.append({
            "document_id": document_id,
            "title": title,
            "type": doc_type,
            "state": state,
            "issued_at": issued_at,
            "version": version,
        })

    billing = data.get("billing")
    billing = dict(billing) if isinstance(billing, Mapping) else {}
    subscription_state = _text(billing.get("subscription_state"), 40).upper()
    payment_state = _text(billing.get("payment_state"), 40).upper()
    next_due_date = _text(billing.get("next_due_date"), 40)
    amount_due = _number(billing.get("amount_due_brl"))
    if subscription_state not in SUBSCRIPTION_STATES:
        blockers.append("SUBSCRIPTION_STATE_INVALID")
    if payment_state not in PAYMENT_STATES:
        blockers.append("PAYMENT_STATE_INVALID")
    if amount_due is None or amount_due < 0:
        blockers.append("AMOUNT_DUE_INVALID")
    if payment_state in {"DUE", "OVERDUE"} and not next_due_date:
        blockers.append("NEXT_DUE_DATE_REQUIRED")

    billing_summary = {
        "subscription_state": subscription_state,
        "payment_state": payment_state,
        "next_due_date": next_due_date,
        "amount_due_brl": round(amount_due, 2) if amount_due is not None else None,
        "currency": "BRL",
    }

    core = {
        "scope": trusted,
        "customer_id": expected_customer,
        "package": expected_package,
        "integrations": integrations,
        "crm": crm_summary,
        "documents": documents,
        "billing": billing_summary,
        "evidence_refs": evidence_refs,
    }

    return {
        "schema": SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        **core,
        "blockers": list(dict.fromkeys(blockers)),
        "evidence_digest": _digest(core),
        "read_only": True,
        "secret_material_exposed": False,
        "payment_link_created": False,
        "document_signed": False,
        "automatic_billing": False,
        "automatic_subscription_change": False,
        "automatic_crm_write": False,
        "automatic_integration_change": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "INTEGRATION_STATES",
    "DOCUMENT_TYPES",
    "DOCUMENT_STATES",
    "SUBSCRIPTION_STATES",
    "PAYMENT_STATES",
    "build_customer_portal_records",
]
