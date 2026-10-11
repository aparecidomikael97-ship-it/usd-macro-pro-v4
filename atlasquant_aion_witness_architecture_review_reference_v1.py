"""Checkpoint witness architecture review — reference design, NEVER authority.

All fields are self-declared. A structural match cannot prove independent
enrollment, fresh challenge, protected monotonic storage, tenant ownership
or affordability. This module neither communicates nor accesses secrets.
"""
from __future__ import annotations
from typing import Any, Mapping

SCHEMA = "AION_CHECKPOINT_WITNESS_ARCHITECTURE_REVIEW_V1"
FIELDS = frozenset({
    "schema", "coordinator", "coordinator_control_domain",
    "retention_anchor", "retention_control_domain",
    "admin_separation", "key_custody_separation",
    "tenant_resource_binding", "nonce_fresh_head_protocol",
    "serialized_cas", "protected_append_history",
    "rollback_recovery", "restore_risk", "expiry_and_revocation",
    "cost_review", "owner_approval",
})
PROTOCOL = "SIGNED_NONCE_BOUND_CURRENT_HEAD"
RECOVERY = "BLOCK_UNKNOWN_RECONCILE_BOTH_DOMAINS"
BOOLEAN_CONTROLS = (
    "admin_separation", "key_custody_separation",
    "tenant_resource_binding", "serialized_cas",
    "protected_append_history", "expiry_and_revocation",
)
NO_AUTHORITY = {
    "owner_enrollment_verified": False,
    "independent_witness_production_verified": False,
    "source_trust_production_verified": False,
    "worker_authorized": False,
    "install_authorized": False,
    "deploy_authorized": False,
    "merge_authorized": False,
    "spending_approved": False,
    "automatic_retry_allowed": False,
}


def _result(blockers: list[str], *, research_only: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "RESEARCH_CANDIDATE_UNTRUSTED" if research_only else "REJECTED_DESIGN",
        "blockers": tuple(sorted(set(blockers))),
        "independently_verified_evidence": False,
        "requires_separate_owner_decision": True,
        "production_no_go": True,
        **NO_AUTHORITY,
    }


def review_witness_architecture(plan: Mapping[str, Any] | None) -> dict[str, Any]:
    """Reject missing design controls; never return a production pass.

    Caller-supplied distinct strings/accounts/roles are descriptions, not
    proof of custody or administrative independence.
    """
    if not isinstance(plan, Mapping) or set(plan) != FIELDS:
        return _result(["PLAN_SCHEMA_OR_FIELDS_INVALID"])
    reasons: list[str] = []
    if plan.get("schema") != SCHEMA:
        reasons.append("PLAN_SCHEMA_INVALID")
    if plan.get("coordinator") != "CLOUDFLARE_SQLITE_DURABLE_OBJECT":
        reasons.append("COORDINATOR_OUTSIDE_RESEARCH_SCOPE")
    if plan.get("retention_anchor") != "AWS_S3_OBJECT_LOCK_COMPLIANCE":
        reasons.append("NO_REVIEWED_WORM_SECOND_PROVIDER")
    for key in ("coordinator_control_domain", "retention_control_domain"):
        value = plan.get(key)
        if type(value) is not str or not value or len(value) > 128 or value.strip() != value:
            reasons.append("CONTROL_DOMAIN_INVALID")
    if plan.get("coordinator_control_domain") == plan.get("retention_control_domain"):
        reasons.append("SAME_CONTROL_DOMAIN")
    for field in BOOLEAN_CONTROLS:
        if plan.get(field) is not True:
            reasons.append("MISSING_DESIGN_CONTROL_" + field.upper())
    if plan.get("nonce_fresh_head_protocol") != PROTOCOL:
        reasons.append("FRESH_SIGNED_HEAD_PROTOCOL_ABSENT")
    if plan.get("rollback_recovery") != RECOVERY:
        reasons.append("UNKNOWN_OUTCOME_RECOVERY_NOT_SPECIFIED")
    if plan.get("restore_risk") != "COORDINATOR_CAN_BE_ADMIN_RESTORED":
        reasons.append("RESTORE_THREAT_NOT_MODELED")
    if plan.get("cost_review") != "UNQUOTED":
        reasons.append("COST_ASSUMPTION_NOT_REVIEWED")
    if plan.get("owner_approval") != "NOT_REQUESTED":
        reasons.append("OWNER_APPROVAL_MUST_REMAIN_SEPARATE")
    if reasons:
        return _result(reasons)
    # Even a design that meets every self-declared contract remains NO-GO.
    return _result([
        "REAL_PROVIDER_NOT_ENROLLED",
        "SECOND_ORIGIN_HEAD_NOT_INDEPENDENTLY_VERIFIED",
        "CURRENT_SIGNED_HEAD_CHALLENGE_NOT_TESTED",
        "TENANT_RESOURCE_REGISTRY_NOT_PHYSICALLY_ATTESTED",
        "COST_LGPD_OWNER_DECISIONS_PENDING",
        "SECURE_RECOVERY_AND_KEY_ROTATION_NOT_PROVEN",
    ], research_only=True)


__all__ = ["SCHEMA", "FIELDS", "NO_AUTHORITY", "review_witness_architecture"]
