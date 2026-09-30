"""AION BUSINESS post-merge verification and rollback review gate V1.

This module verifies evidence after a separately authorized physical merge. It
never executes merge, rollback, rebase, deploy or runtime activation.

No merge evidence means POST_MERGE_EVIDENCE_REQUIRED.
Successful evidence means STEP_VERIFIED_FOR_NEXT_PREFLIGHT.
Any material drift means ROLLBACK_REVIEW_REQUIRED.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_consolidation_execution_review_packet import (
    SCHEMA as REVIEW_PACKET_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_POST_MERGE_VERIFICATION_V1"
VERSION = "1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_POST_MERGE_CHECKS = (
    "quality_tests",
    "release_readiness",
    "core_security_gate",
    "ui_smoke",
    "mobile_dom",
)

ROLLBACK_REVIEW_REASONS = (
    "merge_result_sha_mismatch",
    "required_check_not_success",
    "runtime_posture_changed",
    "deploy_authority_present",
    "rollback_reference_missing",
    "review_packet_binding_invalid",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def post_merge_verification_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "POST_MERGE_EVIDENCE_REQUIRED",
        "required_checks": list(REQUIRED_POST_MERGE_CHECKS),
        "rollback_review_reasons": list(ROLLBACK_REVIEW_REASONS),
        "step_verified": False,
        "next_preflight_allowed": False,
        "automatic_rollback": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def verify_post_merge_step(
    review_packet: Mapping[str, Any] | None,
    *,
    target_pr: Any,
    expected_merge_sha: Any,
    observed_main_sha: Any,
    pre_merge_main_sha: Any,
    rollback_reference_sha: Any,
    check_results: Mapping[str, Any] | None,
    business_runtime_off: Any,
    deploy_authority_absent: Any,
    evidence_ref: Any,
) -> dict[str, Any]:
    packet = _mapping(review_packet)
    checks = _mapping(check_results)

    packet_digest = _clean(packet.get("packet_digest"), 128).lower()
    packet_payload = _mapping(packet.get("payload"))
    packet_target = packet.get("target_pr")
    packet_rollback = _clean(packet.get("rollback_reference_sha"), 80).lower()

    target = target_pr if isinstance(target_pr, int) and not isinstance(target_pr, bool) else None
    expected = _clean(expected_merge_sha, 80).lower()
    observed = _clean(observed_main_sha, 80).lower()
    pre_merge = _clean(pre_merge_main_sha, 80).lower()
    rollback = _clean(rollback_reference_sha, 80).lower()
    evidence = _clean(evidence_ref, 300)

    packet_binding_ok = bool(
        packet.get("schema") == REVIEW_PACKET_SCHEMA
        and packet.get("state") == "READY_FOR_HUMAN_EXECUTION_REVIEW"
        and packet.get("ready_for_human_execution_review") is True
        and packet.get("merge_execution_authorized") is False
        and _DIGEST64.fullmatch(packet_digest)
        and packet_payload
        and _digest(packet_payload) == packet_digest
        and packet_target == target
    )
    merge_sha_ok = bool(
        _SHA40.fullmatch(expected)
        and _SHA40.fullmatch(observed)
        and _SHA40.fullmatch(pre_merge)
        and observed == expected
        and observed != pre_merge
    )
    rollback_ok = bool(
        _SHA40.fullmatch(rollback)
        and packet_rollback == rollback
        and rollback == pre_merge
    )
    checks_ok = bool(
        checks
        and all(_clean(checks.get(name), 40).lower() == "success" for name in REQUIRED_POST_MERGE_CHECKS)
    )
    runtime_ok = type(business_runtime_off) is bool and business_runtime_off is True
    deploy_ok = type(deploy_authority_absent) is bool and deploy_authority_absent is True
    evidence_ok = bool(evidence)

    failures = []
    if not packet_binding_ok:
        failures.append("review_packet_binding_invalid")
    if not merge_sha_ok:
        failures.append("merge_result_sha_mismatch")
    if not checks_ok:
        failures.append("required_check_not_success")
    if not runtime_ok:
        failures.append("runtime_posture_changed")
    if not deploy_ok:
        failures.append("deploy_authority_present")
    if not rollback_ok:
        failures.append("rollback_reference_missing")
    if not evidence_ok:
        failures.append("evidence_ref_missing")

    complete_evidence = bool(
        target is not None
        and expected
        and observed
        and pre_merge
        and rollback
        and checks
        and evidence
    )
    if not complete_evidence:
        state = "POST_MERGE_EVIDENCE_REQUIRED"
    elif failures:
        state = "ROLLBACK_REVIEW_REQUIRED"
    else:
        state = "STEP_VERIFIED_FOR_NEXT_PREFLIGHT"

    receipt_payload = {
        "target_pr": target,
        "expected_merge_sha": expected,
        "observed_main_sha": observed,
        "pre_merge_main_sha": pre_merge,
        "rollback_reference_sha": rollback,
        "packet_digest": packet_digest,
        "checks": {name: _clean(checks.get(name), 40).lower() for name in REQUIRED_POST_MERGE_CHECKS},
        "business_runtime_off": runtime_ok,
        "deploy_authority_absent": deploy_ok,
        "evidence_ref": evidence,
    } if state == "STEP_VERIFIED_FOR_NEXT_PREFLIGHT" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "step_verified": state == "STEP_VERIFIED_FOR_NEXT_PREFLIGHT",
        "next_preflight_allowed": state == "STEP_VERIFIED_FOR_NEXT_PREFLIGHT",
        "target_pr": target,
        "failures": failures,
        "observed_main_sha": observed if complete_evidence else "",
        "rollback_reference_sha": rollback if complete_evidence else "",
        "verification_receipt_digest": _digest(receipt_payload) if receipt_payload else "",
        "required_checks": list(REQUIRED_POST_MERGE_CHECKS),
        "automatic_rollback": False,
        "rollback_execution_authorized": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def rollback_review_packet(
    verification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(verification)
    required = row.get("state") == "ROLLBACK_REVIEW_REQUIRED"
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_ROLLBACK_REVIEW_PACKET_V1",
        "state": "HUMAN_ROLLBACK_REVIEW_REQUIRED" if required else "NOT_REQUIRED",
        "reasons": list(row.get("failures") or []) if required else [],
        "rollback_reference_sha": _clean(row.get("rollback_reference_sha"), 80) if required else "",
        "automatic_rollback": False,
        "rollback_execution_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REQUIRED_POST_MERGE_CHECKS",
    "ROLLBACK_REVIEW_REASONS",
    "post_merge_verification_template",
    "verify_post_merge_step",
    "rollback_review_packet",
]
