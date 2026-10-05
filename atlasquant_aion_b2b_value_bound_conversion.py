"""AION B2B value-bound conversion review gate.

Pure/offline decision support that binds Pilot Value Realization to the existing
commercial conversion/capacity gate. It produces review candidates only and
never changes package, price, contract, billing, provisioning, customer contact,
deployment, provider state, CRM, or production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json

SCHEMA = "ATLASQUANT_AION_B2B_VALUE_BOUND_CONVERSION_V1"
VALUE_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_VALUE_REALIZATION_V1"
CONVERSION_SCHEMA = "ATLASQUANT_AION_B2B_CONVERSION_CAPACITY_V1"

ELIGIBLE_VALUE = {
    ("STRONG_VALUE", "EXPANSION_REVIEW_CANDIDATE"),
    ("VALUE_CONFIRMED", "CONTINUE_REVIEW_CANDIDATE"),
}

VALUE_UNSAFE_FIELDS = (
    "automatic_renewal",
    "automatic_expansion",
    "automatic_pause",
    "automatic_termination",
    "automatic_scope_change",
    "automatic_contract_change",
    "automatic_billing",
    "automatic_customer_contact",
    "automatic_provisioning",
    "automatic_deploy",
    "crm_write",
    "provider_called",
    "production_mutation",
    "executes_action",
)

CONVERSION_UNSAFE_FIELDS = (
    "automatic_conversion",
    "automatic_package_change",
    "automatic_pricing_change",
    "automatic_contract",
    "automatic_billing",
    "automatic_provisioning",
    "automatic_customer_contact",
    "automatic_deploy",
    "production_mutation",
    "executes_action",
)


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


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


def _refs(value: Any, limit: int = 50) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def bind_value_to_conversion_review(
    *,
    trusted_scope: Mapping[str, Any],
    binding: Mapping[str, Any],
    value_realization: Mapping[str, Any],
    conversion_capacity: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    bind = dict(binding) if isinstance(binding, Mapping) else {}
    if _scope(bind) != trusted:
        blockers.append("BINDING_SCOPE_MISMATCH")

    customer_id = _text(bind.get("customer_id"), 120)
    pilot_id = _text(bind.get("pilot_id"), 120)
    if not customer_id:
        blockers.append("CUSTOMER_ID_REQUIRED")
    if not pilot_id:
        blockers.append("PILOT_ID_REQUIRED")

    binding_refs = _refs(bind.get("evidence_refs"))
    if len(binding_refs) < 3:
        blockers.append("BINDING_EVIDENCE_INSUFFICIENT")

    value = dict(value_realization) if isinstance(value_realization, Mapping) else {}
    if value.get("schema") != VALUE_SCHEMA:
        blockers.append("VALUE_SCHEMA_INVALID")
    if _scope(value.get("scope")) != trusted:
        blockers.append("VALUE_SCOPE_MISMATCH")
    if _text(value.get("pilot_id"), 120) != pilot_id:
        blockers.append("VALUE_PILOT_MISMATCH")
    if value.get("blockers"):
        blockers.append("VALUE_HAS_BLOCKERS")
    if value.get("owner_review_required") is not True:
        blockers.append("VALUE_OWNER_REVIEW_BOUNDARY_MISSING")
    if not _text(value.get("evidence_digest"), 180):
        blockers.append("VALUE_EVIDENCE_DIGEST_REQUIRED")
    if (value.get("state"), value.get("recommendation")) not in ELIGIBLE_VALUE:
        blockers.append("VALUE_NOT_CONVERSION_ELIGIBLE")
    for key in VALUE_UNSAFE_FIELDS:
        if value.get(key) is not False:
            blockers.append("VALUE_UNSAFE_FIELD:" + key)

    conversion = (
        dict(conversion_capacity)
        if isinstance(conversion_capacity, Mapping)
        else {}
    )
    if conversion.get("schema") != CONVERSION_SCHEMA:
        blockers.append("CONVERSION_SCHEMA_INVALID")
    if conversion.get("state") != "REVIEWABLE":
        blockers.append("CONVERSION_NOT_REVIEWABLE")
    if conversion.get("decision") != "COMMERCIAL_REVIEW_CANDIDATE":
        blockers.append("CONVERSION_DECISION_INVALID")
    if _text(conversion.get("customer_id"), 120) != customer_id:
        blockers.append("CONVERSION_CUSTOMER_MISMATCH")
    if conversion.get("blockers"):
        blockers.append("CONVERSION_HAS_BLOCKERS")
    if conversion.get("owner_commercial_approval_required") is not True:
        blockers.append("CONVERSION_OWNER_APPROVAL_BOUNDARY_MISSING")
    if not _text(conversion.get("evidence_digest"), 180):
        blockers.append("CONVERSION_EVIDENCE_DIGEST_REQUIRED")
    for key in CONVERSION_UNSAFE_FIELDS:
        if conversion.get(key) is not False:
            blockers.append("CONVERSION_UNSAFE_FIELD:" + key)

    if blockers:
        state = "BLOCKED"
        decision = "BLOCKED"
    elif value.get("recommendation") == "EXPANSION_REVIEW_CANDIDATE":
        state = "REVIEWABLE"
        decision = "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE"
    else:
        state = "REVIEWABLE"
        decision = "CONTINUE_COMMERCIAL_REVIEW_CANDIDATE"

    evidence = {
        "scope": trusted,
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "binding_evidence_refs": binding_refs,
        "value_evidence_digest": _text(value.get("evidence_digest"), 180),
        "conversion_evidence_digest": _text(conversion.get("evidence_digest"), 180),
        "value_state": value.get("state"),
        "value_recommendation": value.get("recommendation"),
        "conversion_state": conversion.get("state"),
        "conversion_decision": conversion.get("decision"),
        "recommended_package": conversion.get("recommended_package"),
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "decision": decision,
        "scope": trusted,
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "recommended_package": conversion.get("recommended_package"),
        "value_state": value.get("state"),
        "value_recommendation": value.get("recommendation"),
        "review_reasons": list(conversion.get("review_reasons") or []),
        "blockers": list(dict.fromkeys(blockers)),
        "evidence_digest": _digest(evidence),
        "owner_commercial_approval_required": True,
        "owner_review_required": True,
        "automatic_conversion": False,
        "automatic_expansion": False,
        "automatic_package_change": False,
        "automatic_pricing_change": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_customer_contact": False,
        "automatic_renewal": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VALUE_SCHEMA",
    "CONVERSION_SCHEMA",
    "ELIGIBLE_VALUE",
    "bind_value_to_conversion_review",
]
