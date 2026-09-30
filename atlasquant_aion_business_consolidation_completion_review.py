"""AION BUSINESS final consolidation completion review V1.

Validates the final evidence after the canonical #394–#412 stack has been
sequentially merged and verified by the progress ledger. This module is a
read-only administrative gate. It never merges, deploys, rolls back, publishes,
contacts clients or activates runtime.

A complete ledger is necessary but not sufficient: final main CI, UI/mobile,
final main SHA, BUSINESS runtime OFF and a separate deploy decision boundary
must all be proven before the state can become READY_FOR_FINAL_ADMIN_REVIEW.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_consolidation_progress_ledger import (
    SCHEMA as LEDGER_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_COMPLETION_REVIEW_V1"
VERSION = "1"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_FINAL_CHECKS = (
    "quality_tests",
    "release_readiness",
    "core_security_gate",
    "supply_chain_audit",
    "ui_smoke",
    "mobile_dom",
)

FINAL_REQUIREMENTS = (
    "ledger_complete",
    "final_main_sha_matches_ledger",
    "all_required_final_checks_success",
    "ui_mobile_success",
    "business_runtime_off",
    "deploy_decision_separate",
    "final_evidence_reference_present",
)

FINAL_ACKNOWLEDGEMENTS = (
    "technical_consolidation_is_not_deploy_authority",
    "technical_consolidation_is_not_runtime_authority",
    "business_runtime_remains_off",
    "deploy_requires_separate_explicit_decision",
    "client_real_actions_remain_out_of_scope",
)

REQUIRED_DECISION_TOKEN = "ACKNOWLEDGE_BUSINESS_CONSOLIDATION_COMPLETE"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def completion_review_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "COMPLETION_EVIDENCE_REQUIRED",
        "requirements": list(FINAL_REQUIREMENTS),
        "required_checks": list(REQUIRED_FINAL_CHECKS),
        "required_decision_token": REQUIRED_DECISION_TOKEN,
        "required_acknowledgements": list(FINAL_ACKNOWLEDGEMENTS),
        "ready_for_final_admin_review": False,
        "technical_consolidation_complete": False,
        "deploy_authorized": False,
        "production_release_authorized": False,
        "runtime_activation_authorized": False,
        "pilot_authorized": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def validate_completion_evidence(
    ledger: Mapping[str, Any] | None,
    *,
    final_main_sha: Any,
    check_results: Mapping[str, Any] | None,
    business_runtime_off: Any,
    deploy_decision_separate: Any,
    final_evidence_ref: Any,
) -> dict[str, Any]:
    ledger_row = _mapping(ledger)
    checks = _mapping(check_results)

    ledger_digest = _clean(ledger_row.get("ledger_digest"), 128).lower()
    ledger_main_sha = _clean(ledger_row.get("current_main_sha"), 80).lower()
    observed_main_sha = _clean(final_main_sha, 80).lower()
    evidence_ref = _clean(final_evidence_ref, 300)

    ledger_ok = bool(
        ledger_row.get("schema") == LEDGER_SCHEMA
        and ledger_row.get("state") == "CONSOLIDATION_COMPLETE_REVIEW_REQUIRED"
        and ledger_row.get("ledger_complete") is True
        and ledger_row.get("completion_review_required") is True
        and ledger_row.get("completed_count") == ledger_row.get("total_steps") == 19
        and _DIGEST64.fullmatch(ledger_digest)
        and _SHA40.fullmatch(ledger_main_sha)
        and ledger_row.get("deploy_authorized") is False
        and ledger_row.get("runtime_activation_authorized") is False
        and ledger_row.get("executes_action") is False
    )

    main_sha_ok = bool(
        ledger_ok
        and _SHA40.fullmatch(observed_main_sha)
        and observed_main_sha == ledger_main_sha
    )

    normalized_checks = {
        name: _clean(checks.get(name), 40).lower()
        for name in REQUIRED_FINAL_CHECKS
    }
    checks_complete = bool(checks and all(normalized_checks.values()))
    checks_ok = bool(
        checks_complete
        and all(value == "success" for value in normalized_checks.values())
    )
    ui_mobile_ok = bool(
        normalized_checks.get("ui_smoke") == "success"
        and normalized_checks.get("mobile_dom") == "success"
    )
    runtime_ok = type(business_runtime_off) is bool and business_runtime_off is True
    deploy_boundary_ok = (
        type(deploy_decision_separate) is bool and deploy_decision_separate is True
    )
    evidence_ok = bool(evidence_ref)

    requirements = {
        "ledger_complete": ledger_ok,
        "final_main_sha_matches_ledger": main_sha_ok,
        "all_required_final_checks_success": checks_ok,
        "ui_mobile_success": ui_mobile_ok,
        "business_runtime_off": runtime_ok,
        "deploy_decision_separate": deploy_boundary_ok,
        "final_evidence_reference_present": evidence_ok,
    }
    blockers = [name for name, passed in requirements.items() if not passed]

    evidence_supplied = bool(
        ledger_row
        or observed_main_sha
        or checks
        or business_runtime_off is not None
        or deploy_decision_separate is not None
        or evidence_ref
    )

    if not evidence_supplied:
        state = "COMPLETION_EVIDENCE_REQUIRED"
    elif blockers:
        state = "COMPLETION_BLOCKED"
    else:
        state = "READY_FOR_FINAL_ADMIN_REVIEW"

    payload = {
        "ledger_digest": ledger_digest,
        "final_main_sha": observed_main_sha,
        "checks": normalized_checks,
        "business_runtime_off": runtime_ok,
        "deploy_decision_separate": deploy_boundary_ok,
        "final_evidence_ref": evidence_ref,
    } if state == "READY_FOR_FINAL_ADMIN_REVIEW" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "requirements": requirements,
        "blockers": blockers,
        "ledger_digest": ledger_digest if ledger_ok else "",
        "final_main_sha": observed_main_sha if main_sha_ok else "",
        "checks": normalized_checks,
        "final_evidence_ref": evidence_ref if evidence_ok else "",
        "completion_review_digest": _digest(payload) if payload else "",
        "ready_for_final_admin_review": state == "READY_FOR_FINAL_ADMIN_REVIEW",
        "technical_consolidation_complete": False,
        "deploy_authorized": False,
        "production_release_authorized": False,
        "runtime_activation_authorized": False,
        "pilot_authorized": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def final_admin_decision_request(
    review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(review)
    review_digest = _clean(row.get("completion_review_digest"), 128).lower()
    final_main_sha = _clean(row.get("final_main_sha"), 80).lower()

    ready = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "READY_FOR_FINAL_ADMIN_REVIEW"
        and row.get("ready_for_final_admin_review") is True
        and _DIGEST64.fullmatch(review_digest)
        and _SHA40.fullmatch(final_main_sha)
        and row.get("deploy_authorized") is False
        and row.get("runtime_activation_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_FINAL_ADMIN_DECISION_REQUEST_V1",
        "state": "FINAL_ADMIN_ACKNOWLEDGEMENT_REQUIRED" if ready else "NOT_READY",
        "completion_review_digest": review_digest if ready else "",
        "final_main_sha": final_main_sha if ready else "",
        "required_decision_token": REQUIRED_DECISION_TOKEN if ready else "",
        "required_acknowledgements": list(FINAL_ACKNOWLEDGEMENTS) if ready else [],
        "generic_confirmation_is_authorization": False,
        "technical_consolidation_complete": False,
        "deploy_authorized": False,
        "production_release_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def record_final_admin_acknowledgement(
    request: Mapping[str, Any] | None,
    *,
    decision_token: Any,
    acknowledgements: Mapping[str, Any] | None,
    actor: Any,
) -> dict[str, Any]:
    request_row = _mapping(request)
    ack = _mapping(acknowledgements)
    token = _clean(decision_token, 120)
    actor_text = _clean(actor, 120)

    request_ok = bool(
        request_row.get("state") == "FINAL_ADMIN_ACKNOWLEDGEMENT_REQUIRED"
        and request_row.get("required_decision_token") == REQUIRED_DECISION_TOKEN
        and _DIGEST64.fullmatch(
            _clean(request_row.get("completion_review_digest"), 128).lower()
        )
        and _SHA40.fullmatch(_clean(request_row.get("final_main_sha"), 80).lower())
    )
    token_ok = token == REQUIRED_DECISION_TOKEN
    acknowledgements_ok = bool(
        all(ack.get(name) is True for name in FINAL_ACKNOWLEDGEMENTS)
    )
    actor_ok = bool(actor_text)

    accepted = bool(request_ok and token_ok and acknowledgements_ok and actor_ok)
    payload = {
        "completion_review_digest": _clean(
            request_row.get("completion_review_digest"), 128
        ).lower(),
        "final_main_sha": _clean(request_row.get("final_main_sha"), 80).lower(),
        "decision_token": token,
        "acknowledgements": {name: True for name in FINAL_ACKNOWLEDGEMENTS},
        "actor": actor_text,
    } if accepted else {}

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_FINAL_ADMIN_ACKNOWLEDGEMENT_V1",
        "state": "TECHNICAL_CONSOLIDATION_ACKNOWLEDGED" if accepted else "BLOCKED",
        "technical_consolidation_complete": accepted,
        "acknowledgement_digest": _digest(payload) if payload else "",
        "actor": actor_text if accepted else "",
        "final_main_sha": payload.get("final_main_sha", ""),
        "deploy_decision_required_separately": True,
        "deploy_authorized": False,
        "production_release_authorized": False,
        "runtime_activation_authorized": False,
        "pilot_authorized": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REQUIRED_FINAL_CHECKS",
    "FINAL_REQUIREMENTS",
    "FINAL_ACKNOWLEDGEMENTS",
    "REQUIRED_DECISION_TOKEN",
    "completion_review_template",
    "validate_completion_evidence",
    "final_admin_decision_request",
    "record_final_admin_acknowledgement",
]
