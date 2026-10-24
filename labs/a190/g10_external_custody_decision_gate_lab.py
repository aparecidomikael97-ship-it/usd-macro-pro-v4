"""A190 G10 offline procurement preflight: never an authorization or certification.

Reads ONLY fixed public-feature fixtures and untrusted caller claims. No
vendor SDK, login, API token, payment, Worker, external effects or network.
It is impossible for this program to return effect GO: an off-host human/
independent witness must verify P0 evidence beyond self-reported JSON.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

REQUIRED_EXTERNAL_PROOFS = (
    "human_owner_independent_auth",
    "original_event_issuer_signed",
    "immutable_independent_public_pin",
    "app_host_admin_denied_recovery_and_restore",
    "external_monotonic_floor_attested",
    "semantic_intent_idempotency_provider",
    "first_attempt_journal_and_ack_uncertainty",
    "real_effect_provider_receipt",
    "read_only_authenticated_reconciliation",
    "h0_fail_closed_and_freshness",
    "cross_platform_real_adversarial_evidence",
    "cost_sla_and_lgpd_owner_approval",
)

# "documented" means an official page describes a FEATURE, not that our
# trust-root architecture or the feature's entitlement has been verified.
CANDIDATES = {
    "cloudflare_do_sqlite": {
        "classification": "REMOTE_STATE_RESEARCH_ONLY",
        "documented": ["SQLITE_TRANSACTIONAL_STORAGE", "FREE_QUOTAS"],
        "known_blockers": [
            "ACCOUNT_WORKER_ADMIN_CAN_MODIFY_DATA",
            "PITR_SUPPORTS_RESTORING_PRIOR_STATE",
            "NOT_A_REAL_EFFECT_PROVIDER_RECEIPT",
        ],
        "source": "https://developers.cloudflare.com/durable-objects/platform/pricing/",
    },
    "aws_dynamodb_conditional": {
        "classification": "REMOTE_ATOMIC_CONDITION_RESEARCH_ONLY",
        "documented": ["CONDITIONAL_WRITE", "IAM_POLICIES", "PAY_PER_REQUEST"],
        "known_blockers": [
            "ACCOUNT_ADMIN_OR_OVERPRIVILEGED_TOKEN_CAN_CHANGE_STATE",
            "NO_ATTESTED_EXTERNAL_MONOTONIC_FLOOR",
            "NOT_A_REAL_EFFECT_PROVIDER_RECEIPT",
        ],
        "source": "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html",
    },
    "google_firestore": {
        "classification": "REMOTE_ATOMIC_PRECONDITION_RESEARCH_ONLY",
        "documented": ["EXISTS_FALSE_PRECONDITION", "FREE_QUOTAS"],
        "known_blockers": [
            "ACCOUNT_ADMIN_CAN_CHANGE_OR_REMOVE_RECORDS",
            "NO_ATTESTED_EXTERNAL_MONOTONIC_FLOOR",
            "NOT_A_REAL_EFFECT_PROVIDER_RECEIPT",
        ],
        "source": "https://docs.cloud.google.com/firestore/docs/reference/rest/v1/Precondition",
    },
    "supabase_free": {
        "classification": "HOSTED_POSTGRES_NOT_H0_CUSTODY_RECOMMENDATION",
        "documented": ["FREE_POSTGRES", "UNIQUE_CONSTRAINT_CAPABLE"],
        "known_blockers": [
            "FREE_PROJECT_INACTIVITY_PAUSE",
            "FREE_NO_AUTOMATIC_BACKUPS_OR_UPTIME_SLA",
            "HOSTED_DATABASE_ADMIN_CAN_CHANGE_STATE",
            "NOT_A_REAL_EFFECT_PROVIDER_RECEIPT",
        ],
        "source": "https://supabase.com/pricing",
    },
}


def _money(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount


def budget_preflight(existing_brl=None, new_usd=None, effective_fx=None,
                     tax_brl=None, cap_brl="200"):
    """Numerical affordability check, NOT approval of a service."""
    parts = [_money(x) for x in (
        existing_brl, new_usd, effective_fx, tax_brl, cap_brl,
    )]
    if any(x is None for x in parts) or parts[2] == 0:
        return {"status": "UNKNOWN_DENY_PROVISIONING",
                "owner_approval": False}
    existing, new, exchange, tax, cap = parts
    total = existing + new * exchange + tax
    return {
        "status": ("OVER_LIMIT_DENY_PROVISIONING" if total > cap
                   else "WITHIN_ESTIMATE_STILL_NOT_AUTHORIZED"),
        "estimated_total_brl": str(total),
        "cap_brl": str(cap),
        "owner_approval": False,
    }


def assess(candidate, supplied_evidence=None, *, cost=None):
    """No JSON claim can bootstrap real proof of an external trust domain."""
    if candidate not in CANDIDATES:
        return {
            "decision": "HARD_NO_GO",
            "reason": "UNRECOGNIZED_CANDIDATE",
            "effect_allowed": False,
            "auto_resend": False,
        }
    features = CANDIDATES[candidate]
    supplied = supplied_evidence if isinstance(supplied_evidence, dict) else {}
    # Offline reviewer cannot authenticate the asserted signers/host or logs.
    # Even forged documents claiming every gate pass remain UNVERIFIED.
    claims_present = sorted(set(REQUIRED_EXTERNAL_PROOFS) & set(supplied))
    return {
        "candidate": candidate,
        "decision": "HARD_NO_GO",
        "confidence": "DOCUMENTARY_FEATURE_RESEARCH_ONLY",
        "known_blockers": features["known_blockers"],
        "documented_capabilities_not_evidence": features["documented"],
        "externally_proven_gates": 0,
        "required_external_gate_count": len(REQUIRED_EXTERNAL_PROOFS),
        "unverifiable_self_claims_present": claims_present,
        "remaining_gates": list(REQUIRED_EXTERNAL_PROOFS),
        "budget": budget_preflight(**(cost or {})),
        "owner_approval": False,
        "effect_allowed": False,
        "auto_resend": False,
        "on_authority_unavailable": "DENY_NEW_EFFECT",
        "on_ack_uncertain": "UNCERTAIN_ZERO_AUTO_RESEND",
        "on_read_only_reservation": "NOT_PROVIDER_EFFECT_PROOF",
        "primary_source": features["source"],
        "p0_homologated": 0,
        "state": "LAB_DRAFT_ONLY",
    }


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="A190 G10 offline no-go evaluator")
    parser.add_argument("--candidate", choices=sorted(CANDIDATES),
                        required=True)
    args = parser.parse_args(argv)
    print(json.dumps(assess(args.candidate), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
