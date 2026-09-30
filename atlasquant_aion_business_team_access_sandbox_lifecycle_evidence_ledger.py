"""AION BUSINESS Team Access Sandbox Lifecycle Evidence Ledger V1.

Append-only, hash-chained ledger for the ten-step sandbox lifecycle.

The ledger never performs the lifecycle. It accepts only sanitized evidence
receipts bound to one verified lifecycle authorization record and enforces
strict order, unique evidence digests and previous-entry continuity.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    SCHEMA as PLAN_SCHEMA,
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_authorization import (
    SCHEMA as AUTH_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_LIFECYCLE_LEDGER_V1"
RECEIPT_SCHEMA = (
    "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_LIFECYCLE_EVIDENCE_RECEIPT_V1"
)
VERSION = "1"
GENESIS_DIGEST = "0" * 64

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE = re.compile(
    r"(password|passwd|secret|token|authorization|credential|private[_-]?key)",
    re.I,
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        return []
    rows: list[dict[str, Any]] = []
    for item in list(value)[:limit]:
        if not isinstance(item, Mapping):
            return []
        rows.append(dict(item))
    return rows


def _timestamp_valid(value: Any) -> bool:
    token = _clean(value, 100)
    if not token:
        return False
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return False
    return parsed.tzinfo is not None


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _authorization_matches(
    plan: Mapping[str, Any],
    auth: Mapping[str, Any],
) -> bool:
    plan_digest = _clean(plan.get("plan_digest"), 80).lower()
    baseline_digest = _clean(plan.get("baseline_evidence_digest"), 80).lower()
    return bool(
        plan.get("schema") == PLAN_SCHEMA
        and plan.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION"
        and _DIGEST64.fullmatch(plan_digest)
        and _DIGEST64.fullmatch(baseline_digest)
        and auth.get("schema") == AUTH_SCHEMA
        and auth.get("state")
        == "EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED"
        and auth.get("authorization_record_verified") is True
        and auth.get("sandbox_lifecycle_manual_execution_authorized") is True
        and _clean(auth.get("plan_digest"), 80).lower() == plan_digest
        and _clean(auth.get("baseline_evidence_digest"), 80).lower()
        == baseline_digest
        and _DIGEST64.fullmatch(_clean(auth.get("record_digest"), 80).lower())
        and auth.get("executor_enabled") is False
        and auth.get("production_authorized") is False
        and auth.get("executes_action") is False
    )


def evidence_receipt_template(
    plan: Mapping[str, Any] | None,
    authorization_record: Mapping[str, Any] | None,
    *,
    step_order: Any,
) -> dict[str, Any]:
    plan_row = _mapping(plan)
    auth = _mapping(authorization_record)
    order = (
        step_order
        if isinstance(step_order, int) and not isinstance(step_order, bool)
        else None
    )
    authorized = _authorization_matches(plan_row, auth)
    step_id = (
        LIFECYCLE_STEP_IDS[order - 1]
        if authorized and order is not None and 1 <= order <= len(LIFECYCLE_STEP_IDS)
        else ""
    )
    return {
        "schema": RECEIPT_SCHEMA,
        "version": VERSION,
        "state": "SANDBOX_LIFECYCLE_STEP_EVIDENCE_REQUIRED"
        if step_id
        else "BLOCKED",
        "step_order": order if step_id else None,
        "step_id": step_id,
        "plan_digest": _clean(plan_row.get("plan_digest"), 80).lower()
        if step_id
        else "",
        "authorization_record_digest": _clean(
            auth.get("record_digest"), 80
        ).lower()
        if step_id
        else "",
        "required_fields": [
            "evidence_digest",
            "observed_at",
            "previous_entry_digest",
            "mutation_observed",
            "sandbox_only",
            "production_targeted",
            "secret_material_included",
        ]
        if step_id
        else [],
        "executes_action": False,
    }


def build_evidence_receipt(
    plan: Mapping[str, Any] | None,
    authorization_record: Mapping[str, Any] | None,
    *,
    step_order: Any,
    step_id: Any,
    evidence_digest: Any,
    observed_at: Any,
    previous_entry_digest: Any,
    mutation_observed: Any,
    sandbox_only: Any,
    production_targeted: Any,
    secret_material_included: Any,
) -> dict[str, Any]:
    plan_row = _mapping(plan)
    auth = _mapping(authorization_record)
    order = (
        step_order
        if isinstance(step_order, int) and not isinstance(step_order, bool)
        else None
    )
    expected_step = (
        LIFECYCLE_STEP_IDS[order - 1]
        if order is not None and 1 <= order <= len(LIFECYCLE_STEP_IDS)
        else ""
    )
    supplied_step = _clean(step_id, 120).upper()
    evidence = _clean(evidence_digest, 80).lower()
    previous = _clean(previous_entry_digest, 80).lower()
    plan_steps = _rows(plan_row.get("steps"), len(LIFECYCLE_STEP_IDS))
    expected_mutation = (
        plan_steps[order - 1].get("mutation")
        if order is not None
        and 1 <= order <= len(plan_steps)
        and plan_steps[order - 1].get("id") == expected_step
        else None
    )

    blockers: list[str] = []
    if not _authorization_matches(plan_row, auth):
        blockers.append("authorization_binding")
    if supplied_step != expected_step or not expected_step:
        blockers.append("step_id")
    if len(plan_steps) != len(LIFECYCLE_STEP_IDS):
        blockers.append("plan_steps")
    if not _DIGEST64.fullmatch(evidence):
        blockers.append("evidence_digest")
    if not _DIGEST64.fullmatch(previous):
        blockers.append("previous_entry_digest")
    if not _timestamp_valid(observed_at):
        blockers.append("observed_at")
    if type(mutation_observed) is not bool or mutation_observed is not expected_mutation:
        blockers.append("mutation_observed")
    if sandbox_only is not True:
        blockers.append("sandbox_only")
    if production_targeted is not False:
        blockers.append("production_targeted")
    if secret_material_included is not False:
        blockers.append("secret_material_included")

    ready = not blockers
    payload = {
        "schema": RECEIPT_SCHEMA,
        "version": VERSION,
        "step_order": order,
        "step_id": expected_step,
        "plan_digest": _clean(plan_row.get("plan_digest"), 80).lower(),
        "authorization_record_digest": _clean(
            auth.get("record_digest"), 80
        ).lower(),
        "evidence_digest": evidence,
        "observed_at": _clean(observed_at, 100),
        "previous_entry_digest": previous,
        "mutation_observed": mutation_observed,
        "sandbox_only": True,
        "production_targeted": False,
        "secret_material_included": False,
    } if ready else {}

    return {
        **payload,
        "schema": RECEIPT_SCHEMA,
        "version": VERSION,
        "state": (
            "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY"
            if ready
            else "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_REJECTED"
        ),
        "blockers": blockers,
        "receipt_digest": _digest(payload) if ready else "",
        "raw_evidence_stored": False,
        "automatic_next_step_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def lifecycle_ledger_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "PLAN_AND_AUTHORIZATION_REQUIRED",
        "step_ids": list(LIFECYCLE_STEP_IDS),
        "total_steps": len(LIFECYCLE_STEP_IDS),
        "completed_count": 0,
        "next_expected_step_order": 1,
        "next_expected_step_id": LIFECYCLE_STEP_IDS[0],
        "ledger_complete": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def build_lifecycle_evidence_ledger(
    plan: Mapping[str, Any] | None,
    authorization_record: Mapping[str, Any] | None,
    receipts: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    plan_row = _mapping(plan)
    auth = _mapping(authorization_record)
    rows = _rows(receipts, len(LIFECYCLE_STEP_IDS) + 1)

    blockers: list[str] = []
    if not _authorization_matches(plan_row, auth):
        blockers.append("authorization_binding")

    normalized: list[dict[str, Any]] = []
    previous_digest = GENESIS_DIGEST
    seen_evidence: set[str] = set()
    seen_receipts: set[str] = set()

    for index, row in enumerate(rows):
        expected_order = index + 1
        expected_step = (
            LIFECYCLE_STEP_IDS[index]
            if index < len(LIFECYCLE_STEP_IDS)
            else ""
        )
        evidence = _clean(row.get("evidence_digest"), 80).lower()
        receipt = _clean(row.get("receipt_digest"), 80).lower()
        previous = _clean(row.get("previous_entry_digest"), 80).lower()

        expected_receipt = build_evidence_receipt(
            plan_row,
            auth,
            step_order=row.get("step_order"),
            step_id=row.get("step_id"),
            evidence_digest=row.get("evidence_digest"),
            observed_at=row.get("observed_at"),
            previous_entry_digest=row.get("previous_entry_digest"),
            mutation_observed=row.get("mutation_observed"),
            sandbox_only=row.get("sandbox_only"),
            production_targeted=row.get("production_targeted"),
            secret_material_included=row.get("secret_material_included"),
        )

        row_blockers: list[str] = []
        if row.get("schema") != RECEIPT_SCHEMA:
            row_blockers.append("schema")
        if row.get("state") != "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY":
            row_blockers.append("state")
        if row.get("step_order") != expected_order:
            row_blockers.append("step_order")
        if _clean(row.get("step_id"), 120).upper() != expected_step:
            row_blockers.append("step_id")
        if _clean(row.get("plan_digest"), 80).lower() != _clean(
            plan_row.get("plan_digest"), 80
        ).lower():
            row_blockers.append("plan_digest")
        if _clean(row.get("authorization_record_digest"), 80).lower() != _clean(
            auth.get("record_digest"), 80
        ).lower():
            row_blockers.append("authorization_record_digest")
        if not _DIGEST64.fullmatch(evidence):
            row_blockers.append("evidence_digest")
        if evidence in seen_evidence:
            row_blockers.append("duplicate_evidence")
        if not _DIGEST64.fullmatch(receipt):
            row_blockers.append("receipt_digest")
        if (
            expected_receipt.get("state")
            != "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY"
            or _clean(expected_receipt.get("receipt_digest"), 80).lower()
            != receipt
        ):
            row_blockers.append("receipt_integrity")
        if receipt in seen_receipts:
            row_blockers.append("duplicate_receipt")
        if previous != previous_digest:
            row_blockers.append("previous_entry_digest")
        if row.get("raw_evidence_stored") is not False:
            row_blockers.append("raw_evidence_stored")
        if row.get("executor_enabled") is not False:
            row_blockers.append("executor_enabled")
        if row.get("production_authorized") is not False:
            row_blockers.append("production_authorized")
        if row.get("executes_action") is not False:
            row_blockers.append("unexpected_execution_path")

        normalized.append(
            {
                "step_order": expected_order,
                "step_id": expected_step,
                "evidence_digest": evidence,
                "receipt_digest": receipt,
                "previous_entry_digest": previous,
                "passed": not row_blockers,
                "blockers": row_blockers,
            }
        )

        if row_blockers:
            blockers.append(f"step_{expected_order}")
            break

        seen_evidence.add(evidence)
        seen_receipts.add(receipt)
        previous_digest = receipt

    if len(rows) > len(LIFECYCLE_STEP_IDS):
        blockers.append("too_many_receipts")

    completed_count = 0
    for row in normalized:
        if not row["passed"]:
            break
        completed_count += 1

    if blockers:
        state = "SANDBOX_LIFECYCLE_EVIDENCE_LEDGER_BLOCKED"
    elif completed_count == len(LIFECYCLE_STEP_IDS):
        state = "SANDBOX_LIFECYCLE_EVIDENCE_COMPLETE_REVIEW_REQUIRED"
    elif completed_count == 0:
        state = "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP"
    else:
        state = "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP"

    next_order = (
        completed_count + 1
        if state
        in (
            "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP",
            "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP",
        )
        else None
    )
    next_step = (
        LIFECYCLE_STEP_IDS[next_order - 1]
        if next_order is not None
        else ""
    )

    ledger_payload = {
        "plan_digest": _clean(plan_row.get("plan_digest"), 80).lower(),
        "authorization_record_digest": _clean(
            auth.get("record_digest"), 80
        ).lower(),
        "entries": normalized[:completed_count],
        "completed_count": completed_count,
        "chain_head_digest": previous_digest,
    } if not blockers else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "entries": normalized,
        "completed_count": completed_count,
        "total_steps": len(LIFECYCLE_STEP_IDS),
        "next_expected_step_order": next_order,
        "next_expected_step_id": next_step,
        "blockers": blockers,
        "chain_head_digest": previous_digest if not blockers else "",
        "ledger_digest": _digest(ledger_payload) if ledger_payload else "",
        "ledger_complete": state
        == "SANDBOX_LIFECYCLE_EVIDENCE_COMPLETE_REVIEW_REQUIRED",
        "automatic_next_step_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "RECEIPT_SCHEMA",
    "VERSION",
    "GENESIS_DIGEST",
    "evidence_receipt_template",
    "build_evidence_receipt",
    "lifecycle_ledger_template",
    "build_lifecycle_evidence_ledger",
]
