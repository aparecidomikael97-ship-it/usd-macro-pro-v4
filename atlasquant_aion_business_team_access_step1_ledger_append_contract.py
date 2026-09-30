"""AION BUSINESS Team Access Step 1 Ledger Append Contract V1.

Defines the explicit administrative decision contract for appending the already
validated canonical Step 1 lifecycle receipt to the persisted sandbox ledger.

This layer is read-only. It never writes the ledger and never authorizes Step 2.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    GENESIS_DIGEST,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_step1_preflight_package import (
    verify_step1_preflight_package,
)
from atlasquant_aion_business_team_access_step1_provider_receipt_review import (
    verify_provider_receipt_review,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_LEDGER_APPEND_CONTRACT_V1"
VERSION = "1"

REQUIRED_ACKNOWLEDGEMENTS = (
    "RECEIPT_REVIEW_DIGEST_VERIFIED",
    "SOURCE_LEDGER_GENESIS_VERIFIED",
    "CANONICAL_RECEIPT_VERIFIED",
    "TARGET_LEDGER_PREVIEW_VERIFIED",
    "NO_AUTOMATIC_APPEND",
    "STEP2_SEPARATE_AUTHORIZATION_REQUIRED",
)

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


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


def _timestamp_valid(value: Any) -> bool:
    token = _clean(value, 100)
    if not token:
        return False
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return False
    return parsed.tzinfo is not None


def _decision_token(
    receipt_review_digest: str,
    source_ledger_digest: str,
    target_ledger_digest: str,
) -> str:
    if not all(
        _DIGEST64.fullmatch(value)
        for value in (
            receipt_review_digest,
            source_ledger_digest,
            target_ledger_digest,
        )
    ):
        return ""
    return (
        "APPEND_SANDBOX_STEP1_LEDGER_"
        f"{receipt_review_digest}_"
        f"{source_ledger_digest}_"
        f"{target_ledger_digest}"
    )


def ledger_append_contract_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "STEP1_LEDGER_APPEND_DECISION_CONTRACT_DEFINED",
        "exact_token_required": True,
        "generic_language_is_authorization": False,
        "source_ledger_must_be_genesis": True,
        "target_ledger_must_complete_step1_only": True,
        "automatic_append_allowed": False,
        "ledger_append_authorized": False,
        "ledger_append_performed": False,
        "step2_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }


def build_ledger_append_decision_request(
    step1_preflight_packet: Mapping[str, Any] | None,
    receipt_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    packet = _mapping(step1_preflight_packet)
    review = _mapping(receipt_review)
    packet_binding = verify_step1_preflight_package(packet)
    review_binding = verify_provider_receipt_review(review)

    source = _mapping(packet.get("ledger"))
    target = _mapping(review.get("ledger_preview"))
    canonical = _mapping(review.get("canonical_lifecycle_receipt"))

    receipt_review_digest = _clean(
        review.get("receipt_review_digest"), 80
    ).lower()
    canonical_receipt_digest = _clean(
        canonical.get("receipt_digest"), 80
    ).lower()
    source_ledger_digest = _clean(
        source.get("ledger_digest"), 80
    ).lower()
    target_ledger_digest = _clean(
        target.get("ledger_digest"), 80
    ).lower()
    expected_decider = _clean(
        packet.get("observation_observed_by"), 120
    )

    gates = {
        "step1_packet_binding_match": packet_binding.get(
            "binding_match"
        ) is True,
        "receipt_review_binding_match": review_binding.get(
            "binding_match"
        ) is True,
        "receipt_review_digest_valid": bool(
            _DIGEST64.fullmatch(receipt_review_digest)
        ),
        "canonical_receipt_digest_valid": bool(
            _DIGEST64.fullmatch(canonical_receipt_digest)
        ),
        "source_ledger_digest_valid": bool(
            _DIGEST64.fullmatch(source_ledger_digest)
        ),
        "target_ledger_digest_valid": bool(
            _DIGEST64.fullmatch(target_ledger_digest)
        ),
        "source_ledger_exact_genesis": bool(
            source.get("state")
            == "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP"
            and source.get("completed_count") == 0
            and list(source.get("entries") or []) == []
            and source.get("chain_head_digest") == GENESIS_DIGEST
            and source.get("next_expected_step_order") == 1
            and source.get("next_expected_step_id")
            == LIFECYCLE_STEP_IDS[0]
        ),
        "canonical_receipt_is_step1": bool(
            canonical.get("state")
            == "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY"
            and canonical.get("step_order") == 1
            and _clean(canonical.get("step_id"), 120).upper()
            == LIFECYCLE_STEP_IDS[0]
            and _clean(
                canonical.get("previous_entry_digest"), 80
            ).lower()
            == GENESIS_DIGEST
            and canonical.get("mutation_observed") is True
            and canonical.get("sandbox_only") is True
            and canonical.get("production_targeted") is False
            and canonical.get("secret_material_included") is False
        ),
        "target_ledger_exact_step1_only": bool(
            target.get("state")
            == "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP"
            and target.get("completed_count") == 1
            and target.get("next_expected_step_order") == 2
            and target.get("next_expected_step_id")
            == LIFECYCLE_STEP_IDS[1]
            and target.get("automatic_next_step_authorized") is False
            and target.get("executor_enabled") is False
            and target.get("production_authorized") is False
            and target.get("executes_action") is False
        ),
        "review_does_not_pre_authorize_append": bool(
            review.get("ledger_append_authorized") is False
            and review.get("ledger_append_performed") is False
            and review.get("automatic_ledger_append") is False
            and review.get("step2_execution_authorized") is False
        ),
        "expected_decider_present": bool(expected_decider),
    }

    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers
    token = _decision_token(
        receipt_review_digest,
        source_ledger_digest,
        target_ledger_digest,
    ) if ready else ""

    payload = {
        "receipt_review_digest": receipt_review_digest,
        "canonical_receipt_digest": canonical_receipt_digest,
        "source_ledger_digest": source_ledger_digest,
        "target_ledger_digest": target_ledger_digest,
        "expected_decider": expected_decider,
        "required_decision_token": token,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_EXPLICIT_STEP1_LEDGER_APPEND_DECISION"
            if ready
            else "STEP1_LEDGER_APPEND_DECISION_REQUEST_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "receipt_review_digest": receipt_review_digest if ready else "",
        "canonical_receipt_digest": (
            canonical_receipt_digest if ready else ""
        ),
        "source_ledger_digest": source_ledger_digest if ready else "",
        "target_ledger_digest": target_ledger_digest if ready else "",
        "expected_decider": expected_decider if ready else "",
        "required_decision_token": token,
        "required_acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "decision_request_digest": _digest(payload) if ready else "",
        "ledger_append_authorized": False,
        "ledger_append_performed": False,
        "automatic_ledger_append": False,
        "step2_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }


def validate_ledger_append_decision(
    request: Mapping[str, Any] | None,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    req = _mapping(request)
    raw = _mapping(record)

    receipt_review_digest = _clean(
        req.get("receipt_review_digest"), 80
    ).lower()
    canonical_receipt_digest = _clean(
        req.get("canonical_receipt_digest"), 80
    ).lower()
    source_ledger_digest = _clean(
        req.get("source_ledger_digest"), 80
    ).lower()
    target_ledger_digest = _clean(
        req.get("target_ledger_digest"), 80
    ).lower()
    expected_decider = _clean(
        req.get("expected_decider"), 120
    )
    expected_token = _clean(
        req.get("required_decision_token"), 300
    )
    expected_request_payload = {
        "receipt_review_digest": receipt_review_digest,
        "canonical_receipt_digest": canonical_receipt_digest,
        "source_ledger_digest": source_ledger_digest,
        "target_ledger_digest": target_ledger_digest,
        "expected_decider": expected_decider,
        "required_decision_token": expected_token,
    }
    request_digest = _clean(
        req.get("decision_request_digest"), 80
    ).lower()

    acknowledgements = _mapping(raw.get("acknowledgements"))
    decided_by = _clean(raw.get("decided_by"), 120)
    decided_at = _clean(raw.get("decided_at"), 100)

    gates = {
        "request_schema_valid": req.get("schema") == SCHEMA,
        "request_state_ready": req.get("state")
        == "READY_FOR_EXPLICIT_STEP1_LEDGER_APPEND_DECISION",
        "decision_request_digest_valid": bool(
            _DIGEST64.fullmatch(request_digest)
        ),
        "decision_request_digest_integrity": bool(
            _DIGEST64.fullmatch(request_digest)
            and request_digest == _digest(expected_request_payload)
        ),
        "required_token_recomputed": bool(
            expected_token
            and expected_token == _decision_token(
                receipt_review_digest,
                source_ledger_digest,
                target_ledger_digest,
            )
        ),
        "decision_token_exact": _clean(
            raw.get("decision"), 300
        ) == expected_token,
        "receipt_review_digest_exact": _clean(
            raw.get("receipt_review_digest"), 80
        ).lower()
        == receipt_review_digest,
        "canonical_receipt_digest_exact": _clean(
            raw.get("canonical_receipt_digest"), 80
        ).lower()
        == canonical_receipt_digest,
        "source_ledger_digest_exact": _clean(
            raw.get("source_ledger_digest"), 80
        ).lower()
        == source_ledger_digest,
        "target_ledger_digest_exact": _clean(
            raw.get("target_ledger_digest"), 80
        ).lower()
        == target_ledger_digest,
        "decider_exact": bool(
            decided_by and decided_by == expected_decider
        ),
        "decided_at_valid": _timestamp_valid(decided_at),
        "sandbox_only": raw.get("sandbox_only") is True,
        "production_not_targeted": raw.get(
            "production_targeted"
        ) is False,
        "automatic_append_not_requested": raw.get(
            "automatic_ledger_append_requested"
        ) is False,
        "step2_not_requested": raw.get(
            "step2_execution_requested"
        ) is False,
        "secret_material_absent": raw.get(
            "secret_material_included"
        ) is False,
        "acknowledgements_complete": all(
            acknowledgements.get(name) is True
            for name in REQUIRED_ACKNOWLEDGEMENTS
        ),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    verified = not blockers

    payload = {
        "decision": expected_token,
        "receipt_review_digest": receipt_review_digest,
        "canonical_receipt_digest": canonical_receipt_digest,
        "source_ledger_digest": source_ledger_digest,
        "target_ledger_digest": target_ledger_digest,
        "decided_by": decided_by,
        "decided_at": decided_at,
        "sandbox_only": True,
        "production_targeted": False,
        "automatic_ledger_append_requested": False,
        "step2_execution_requested": False,
        "secret_material_included": False,
        "acknowledgements": {
            name: acknowledgements.get(name) is True
            for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    } if verified else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "EXPLICIT_STEP1_LEDGER_APPEND_DECISION_VERIFIED"
            if verified
            else "STEP1_LEDGER_APPEND_DECISION_REJECTED"
        ),
        "gates": gates,
        "blockers": blockers,
        "ledger_append_decision_verified": verified,
        "receipt_review_digest": receipt_review_digest
        if verified else "",
        "canonical_receipt_digest": canonical_receipt_digest
        if verified else "",
        "source_ledger_digest": source_ledger_digest
        if verified else "",
        "target_ledger_digest": target_ledger_digest
        if verified else "",
        "decided_by": decided_by if verified else "",
        "decided_at": decided_at if verified else "",
        "ledger_append_decision_digest": (
            _digest(payload) if verified else ""
        ),
        "ledger_append_authorized": verified,
        "ledger_append_performed": False,
        "automatic_ledger_append": False,
        "step2_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REQUIRED_ACKNOWLEDGEMENTS",
    "ledger_append_contract_policy",
    "build_ledger_append_decision_request",
    "validate_ledger_append_decision",
]
