"""P0 H0 independent THIRD-ANCHOR design preflight, NOT an evidence verifier.

This is a *static architecture-review checklist*, not cloud storage,
a signed witness, an S3/R2 client, a trusted identity source or authority.
Every result remains BLOCKED even when all controls are self-declared.
Real AWS S3 Object Lock COMPLIANCE can retain an OBJECT VERSION, but newly
written versions and delete markers are permitted. Cloudflare R2 bucket
locks are removable by account administrators. Neither product alone proves
a high-water record existed, was written, or is fresh.

No network, credentials, signing, provider, worker, deploy or external effects.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "AION_P0_H0_THIRD_ANCHOR_STATIC_REVIEW_LAB_V1"
FIELDS = (
    "different_cloud_provider_from_cas",
    "independent_administration_and_root",
    "versioning_enabled",
    "exact_object_version_id_pinned_outside_executor_and_cas",
    "readback_uses_exact_version_id_not_latest_alias",
    "delete_markers_and_new_versions_checked",
    "immutable_version_retention_metadata_checked",
    "retention_horizon_covers_rollback_and_recovery",
    "encryption_key_custody_independent_and_recoverable",
    "append_only_scope_epoch_sequence_digest_binding",
    "no_pii_in_anchor",
    "durable_append_ack_before_first_external_effect",
    "authenticated_readback_after_append_before_effect",
    "ambiguous_write_or_readback_stays_blocked_no_retry",
    "account_closure_and_admin_compromise_risk_accepted_for_review",
)
FALSE_AUTHORITY = {
    "third_anchor_enrolled": False,
    "third_anchor_signature_authenticated": False,
    "third_anchor_retention_verified_remotely": False,
    "third_anchor_version_verified_remotely": False,
    "external_highwater_compared": False,
    "local_rollback_ruled_out": False,
    "custodian_rollback_ruled_out": False,
    "first_effect_allowed": False,
    "automatic_retry_allowed": False,
    "worker_arming_allowed": False,
    "producer_effect_authenticated": False,
    "external_action_executed": False,
}


def assess_third_anchor_design_lab(proposal: Any) -> dict[str, Any]:
    """Score proposed controls WITHOUT trusting them or opening a connection.

    Do not inspect hostile object properties/truthiness. Only an EXACT dict is
    accepted. A fully declared proposal means merely more external validation
    work is possible, not an enrolled/verifiable anchor.
    """
    findings: list[str] = []
    if type(proposal) is not dict:
        findings.append("PROPOSAL_NOT_PLAIN_DICT")
    else:
        vendor = proposal.get("technology")
        if type(vendor) is not str or vendor != "AWS_S3_OBJECT_LOCK":
            if vendor == "CLOUDFLARE_R2_BUCKET_LOCK":
                findings.append("R2_BUCKET_LOCK_RULES_ADMIN_REMOVABLE")
            elif vendor == "CLOUDFLARE_DURABLE_OBJECTS":
                findings.append("DO_PITR_SAME_CUSTODIAN_ROLLBACK_DOMAIN")
            else:
                findings.append("THIRD_ANCHOR_TECHNOLOGY_NOT_ASSESSED")
        if proposal.get("retention_mode") != "COMPLIANCE":
            findings.append("RETENTION_NOT_S3_COMPLIANCE")
        for control in FIELDS:
            if proposal.get(control) is not True:
                findings.append("DESIGN_REQUIREMENT_NOT_PROVEN:" + control)
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "review": (
            "PROPOSED_CONTROLS_REQUIRE_INDEPENDENT_REAL_VALIDATION"
            if not findings else "PROPOSAL_HAS_BLOCKING_DESIGN_GAPS"
        ),
        "findings": findings,
        "inputs_are_untrusted_self_declarations": True,
        "cloud_account_created": False,
        "cloud_service_contacted": False,
        "retention_mode_tested_in_cloud": False,
        "provider_receipt_verified": False,
        **FALSE_AUTHORITY,
    }
