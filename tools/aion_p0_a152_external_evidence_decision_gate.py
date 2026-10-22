"""AION A152 — ONE read-only, fail-closed decision across existing H0 evidence.

This gate does not enroll any issuer, authenticate a remote authority, reserve
an intent, validate real receipts, provision infrastructure or approve H0.
Passing its documentary checks is ALWAYS HARD_NO_GO. All input originates in
checked-in, self-declared JSON and prior historical observations, NOT remote
verification. It does not read secrets, talk to providers or alter anything.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

# Direct invocation from tools/ must resolve the checked-out repository root.
# This does not import any runtime worker, provider, or external service.
CHECKOUT_ROOT = Path(__file__).resolve().parents[1]
if str(CHECKOUT_ROOT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT_ROOT))

from atlasquant_aion_p0_h0_iam_finops_preflight_lab import (
    assess_h0_iam_finops_lab,
)
from tools.aion_p0_h0_vendor_custodian_documentary_gate import (
    audit as audit_two_roles,
)
from tools.aion_p0_h0_vendor_rfi_readonly_intake_gate import (
    audit as audit_rfi,
)
from tools.aion_p0_h0_provider_32_crosswalk_audit import (
    audit as audit_provider_crosswalk,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "AION_P0_A152_EXTERNAL_EVIDENCE_DECISION_NO_GO_V1"
SOURCE_PATHS = {
    "finops": "docs/aion/AION_P0_H0_IAM_FINOPS_UNPRICED_PROPOSAL_TEMPLATE_20261019.json",
    "roles": "docs/aion/evidence/aion_p0_h0_vendor_custodian_two_role_review_20261021.json",
    "rfi": "docs/aion/evidence/aion_p0_h0_vendor_rfi_34_open_questions_20261021.json",
    "rfi_template": "docs/aion/p0-h0-unsent-onesignal-cloudflare-aws-technical-rfi-20261021.md",
    "crosswalk": "docs/aion/evidence/aion_p0_h0_32_provider_errors_current_6895_crosswalk_20261021.json",
    "quality": "docs/aion/evidence/aion_p0_quality_85_red_baseline_20261021.json",
    "historical": "docs/aion/AION_P0_32_EXTERNAL_PRODUCER_EVIDENCE_MATRIX_20261020.json",
}
EXPECTED_QUALITY = {
    "tests": 6895,
    "pass": 6810,
    "fail": 51,
    "error": 34,
}
EXPECTED_PRODUCER_ERRORS = {
    "PRE_ADAPTER_PRODUCER_ENROLLMENT": 23,
    "CAUSAL_COMMITTED_EFFECT_RECEIPT": 8,
    "TERMINAL_NO_EFFECT_FENCE": 1,
}
FINOPS_PROHIBITIONS = (
    "verified_supplier_bill",
    "verified_iam_cloud_enforcement",
    "aws_cloudflare_accounts_enrolled",
    "third_anchor_remotely_authenticated",
    "external_highwater_verified",
    "first_effect_allowed",
    "worker_arming_allowed",
    "automatic_retry_allowed",
    "external_action_executed",
)
ROLE_PROHIBITIONS = (
    "actual_external_trust_verified",
    "effect_or_absence_proven",
    "worker_allowed",
    "automatic_resend_allowed",
)
CROSSWALK_PROHIBITIONS = (
    "evidence_complete",
    "identity_independently_enrolled",
    "provider_receipt_authentic",
    "terminal_no_effect_fenced",
    "worker_allowed",
    "automatic_resend_allowed",
)
RFI_PROHIBITIONS = (
    "technical_submission_performed",
    "external_proof_authenticated",
    "worker_allowed",
    "automatic_resend_allowed",
    "quality_85_waived",
)


class A152EvidenceError(ValueError):
    """Invalid source: do not even present a complete documentary picture."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise A152EvidenceError(code)


def _check_exact_false(record: Any, fields: tuple[str, ...], reason: str) -> None:
    _require(type(record) is dict, reason)
    _require(all(record.get(k) is False for k in fields), reason)


def load_readonly_sources(root: Path = ROOT) -> dict[str, Any]:
    """Load exactly named repository documents without following file symlinks."""
    root = Path(root).resolve()
    data: dict[str, Any] = {}
    for name, relative in SOURCE_PATHS.items():
        file = root / relative
        _require(not file.is_symlink() and file.is_file(),
                 "SOURCE_MISSING_OR_SYMLINKED:" + name)
        try:
            content = file.read_text(encoding="utf-8")
            data[name] = content if name == "rfi_template" else json.loads(content)
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise A152EvidenceError("SOURCE_UNREADABLE_OR_INVALID:" + name) from exc
    return data


def audit_documentary_sources(inputs: Any, *, as_of: date) -> dict[str, Any]:
    """Existing gates run together; their return values never mean authorization.

    Explicitly NO acceptance of caller-supplied proof-of-independence flags.
    The gate may report financial arithmetic as *provisional*, never pricing
    evidence or actual cost. Historical Quality counts are evidence of
    the old RED baseline, not necessarily the latest CI run.
    """
    _require(type(inputs) is dict and set(inputs) == set(SOURCE_PATHS),
             "A152_SOURCE_SET_INVALID")
    _require(type(as_of) is date, "AS_OF_INVALID")
    quality = inputs["quality"]
    _require(type(quality) is dict and type(quality.get("baseline")) is dict,
             "QUALITY_BASELINE_MISSING")
    q = quality["baseline"]
    _require(
        {k: q.get(k) for k in EXPECTED_QUALITY} == EXPECTED_QUALITY,
        "QUALITY_RED_BASELINE_CHANGED_REQUIRES_REVIEW",
    )
    _require(q.get("head_sha") == "0630441417fb1ec0e42a06ca0b104a311a6de399",
             "QUALITY_BASELINE_SHA_MISMATCH")
    _require(type(quality.get("entries")) is list and len(quality["entries"]) == 85,
             "QUALITY_RED_LEDGER_MISMATCH")
    financial = assess_h0_iam_finops_lab(inputs["finops"], as_of=as_of)
    _require(financial.get("state") == "HARD_NO_GO",
             "FINOPS_SOURCE_UNSAFE_STATUS")
    _check_exact_false(financial, FINOPS_PROHIBITIONS, "FINOPS_AUTHORITY_MINTED")

    # These are the mature, existing independent gates; do not reimplement
    # vendor endpoint assumptions or the Quality 32 exact join.
    try:
        roles = audit_two_roles(inputs["roles"])
        rfi = audit_rfi(inputs["rfi"], inputs["rfi_template"])
        cases = audit_provider_crosswalk(
            inputs["crosswalk"], quality, inputs["historical"],
        )
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        raise A152EvidenceError("EXISTING_DOCUMENTARY_GATE_REJECTED:" + str(exc)) from exc
    _check_exact_false(roles, ROLE_PROHIBITIONS, "ROLE_AUTHORITY_MINTED")
    _check_exact_false(rfi, RFI_PROHIBITIONS, "RFI_AUTHORITY_MINTED")
    _check_exact_false(cases, CROSSWALK_PROHIBITIONS, "PROVIDER_AUTHORITY_MINTED")
    _require(
        roles.get("verdict") == "HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING"
        and rfi.get("verdict") == "HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING"
        and cases.get("verdict") == "HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING",
        "SOURCE_VERDICT_CHANGED",
    )
    _require(roles.get("provider_count") == 3
             and roles.get("custodian_count") == 2
             and roles.get("pair_count") == 6,
             "VENDOR_CANDIDATE_CARDINALITY_CHANGED")
    _require(rfi.get("questions") == 34
             and rfi.get("pending") + rfi.get("vendor_answer_candidates_unverified") == 34,
             "RFI_COVERAGE_CHANGED")
    _require(cases.get("matched_32_provider_errors") == 32
             and cases.get("gates") == dict(sorted(EXPECTED_PRODUCER_ERRORS.items())),
             "PRODUCER_PROOF_COVERAGE_CHANGED")
    _require(
        all(record.get("homologated_p0_count") == 0 for record in (roles, rfi, cases)),
        "P0_PREMATURE_HOMOLOGATION",
    )

    # The diagnostic stages are intentionally NOT interchangeable:
    # "arithmetic ready" is not "vendor quoted", "IAM verified" or "live ready".
    unpriced = not financial["priced_inputs_complete"]
    documentary_consistent = True
    return {
        "schema": SCHEMA,
        "historical_quality_baseline_only": {
            "head_sha": q["head_sha"],
            "tests": q["tests"],
            "fail": q["fail"],
            "error": q["error"],
            "not_claimed_as_latest_ci": True,
        },
        "source_integrity": {
            "existing_documentary_gates_consistent": documentary_consistent,
            "RFI_questions": 34,
            "RFI_unanswered": rfi["pending"],
            "RFI_answer_claims_unverified": rfi["vendor_answer_candidates_unverified"],
            "provider_issues_open": cases["matched_32_provider_errors"],
            "producer_gate_breakdown": cases["gates"],
            "documentary_vendor_pairs": roles["pair_count"],
        },
        "finops": {
            "global_cap_brl": financial["global_cap_brl"],
            "review_threshold_brl": financial["review_threshold_brl"],
            "unpriced": unpriced,
            "projected_monthly_brl_UNVERIFIED_INPUTS": financial["projected_monthly_brl"],
            "iam_allowlist_documentary_only": financial["iam_proposal_allowlist_consistent"],
            "cloudflare_quota_documentary_only": financial["cloudflare_free_quota_projection_in_range"],
            "issues": list(financial["issues"]),
        },
        "evidence_gates": {
            "E0_FINANCE": "MISSING_AUTHENTIC_BILLING_AND_QUOTE_EVIDENCE",
            "E1_IAM_IDENTITY": "MISSING_INDEPENDENT_ACCOUNT_KEY_AND_ADMIN_EVIDENCE",
            "E2_IMMUTABLE_ANCHOR": "MISSING_THIRD_DOMAIN_WORM_READBACK_AND_FORK_PROOF",
            "E3_MONOTONIC_WITNESS": "MISSING_AUTHENTICATED_CURRENT_HEAD_AND_INDEPENDENT_CAS",
            "E4_CRASH_RECOVERY": "MISSING_REAL_REBOOT_RESTORE_AND_UNCERTAIN_ACK_EVIDENCE",
            "E5_FULL_H0_SIGNOFF": "MISSING_OWNER_PROVIDER_RECEIPTS_AND_CANONICAL_GREEN",
        },
        "next_evidence_no_spend": [
            "Verify existing monthly AtlasQuant spend and dates; do not invent a price.",
            "Review already drafted unsent RFI questions, do not mark them as sent.",
            "Define separate D0/D1/D2 account administrators and independent recovery.",
            "Demand explicit owner approval before any credentials, provisioning or paid test.",
            "Preserve 32 external producer proof blockers and historical Quality RED.",
        ],
        "authority": {
            "actual_cost_verified": False,
            "provider_enrolled": False,
            "independent_D1_D2_custody_verified": False,
            "producer_effect_or_terminal_no_effect_authenticated": False,
            "real_HUMAN_OWNER_consent_verified": False,
            "security_quality_canonic_green": False,
            "first_effect_allowed": False,
            "worker_allowed": False,
            "automatic_resend_allowed": False,
            "new_spend_authorized_brl": 0,
            "homologated_p0_count": 0,
        },
        "decision": "HARD_NO_GO_EXTERNAL_CUSTODY_AND_PRODUCER_EVIDENCE_MISSING",
    }


def run_offline(root: Path = ROOT, *, as_of: date | None = None) -> dict[str, Any]:
    return audit_documentary_sources(
        load_readonly_sources(root),
        as_of=as_of if as_of is not None else datetime.now(timezone.utc).date(),
    )


def main() -> int:
    try:
        result = run_offline()
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
        # Exit zero means only READ-ONLY DOCUMENTARY INTEGRITY, NOT production GO.
        return 0
    except (A152EvidenceError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({
            "schema": SCHEMA,
            "error": str(exc),
            "decision": "HARD_NO_GO_A152_SOURCE_INTEGRITY_FAILED",
        }), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
