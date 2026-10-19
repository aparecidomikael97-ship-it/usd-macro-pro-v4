"""AION P0 H0: offline IAM + FinOps proposal preflight. ALWAYS NO-GO.

No AWS/Cloudflare calls, no account enrollment, no IAM policy generator and no
production approval. Every field comes from untrusted proposal input. Even
with complete prices and exact IAM names, output CANNOT authenticate the
provider, a budget bill, a cryptographic custodian, or the HUMAN_OWNER.
Financial numbers are PROJECTIONS with caller supplied regional quotes.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any

SCHEMA = "AION_P0_H0_IAM_FINOPS_OFFLINE_PREFLIGHT_V1"
MAX_CAP_BRL = Decimal("200")
CAUTION_RATIO = Decimal("0.80")
DAYS_BILLED = Decimal("31")
GIGA = Decimal("1000000000")
AWS_ACTIONS_BY_ROLE = {
    "aion_executor": frozenset(),
    "cloudflare_cas_runtime": frozenset(),
    "aws_anchor_writer": frozenset({"s3:PutObject"}),
    "aws_anchor_reader": frozenset({
        "s3:GetObjectVersion", "s3:GetObjectRetention",
        "s3:GetBucketObjectLockConfiguration", "s3:ListBucketVersions",
    }),
}
DISALLOWED_ACTIONS = frozenset({
    "*", "s3:*", "iam:*", "kms:*", "s3:DeleteObject",
    "s3:DeleteObjectVersion", "s3:BypassGovernanceRetention",
    "s3:PutBucketObjectLockConfiguration", "s3:PutBucketVersioning",
    "s3:PutLifecycleConfiguration", "s3:PutBucketLifecycleConfiguration",
    "s3:PutObjectRetention", "s3:PutObjectLegalHold",
    "s3:DeleteBucket", "s3:PutBucketPolicy", "s3:PutBucketAcl",
    "s3:PutPublicAccessBlock",
})
QUOTES = (
    "s3_standard_gb_month_usd", "s3_put_per_1000_usd",
    "s3_get_per_1000_usd", "kms_key_month_usd",
    "kms_per_10000_usd", "audit_logging_monthly_usd",
    "other_cloud_monthly_usd", "usd_brl_stress_rate",
    "existing_ecosystem_monthly_brl",
    "tax_fx_uncertainty_fraction",
)
WORKLOAD = (
    "anchors_per_day", "retention_days", "versions_per_anchor",
    "bytes_per_version", "s3_puts_per_anchor", "s3_gets_per_anchor",
    "kms_calls_per_anchor", "cloudflare_account_requests_per_day",
    "cloudflare_account_gbs_per_day",
    "cloudflare_account_rows_read_per_day",
    "cloudflare_account_rows_written_per_day",
    "cloudflare_account_sqlite_gb",
    "workers_account_requests_per_day",
)
CF_FREE_LIMITS = {
    "cloudflare_account_requests_per_day": Decimal("100000"),
    "cloudflare_account_gbs_per_day": Decimal("13000"),
    "cloudflare_account_rows_read_per_day": Decimal("5000000"),
    "cloudflare_account_rows_written_per_day": Decimal("100000"),
    "cloudflare_account_sqlite_gb": Decimal("5"),
    "workers_account_requests_per_day": Decimal("100000"),
}
REQUIRED_CONTROLS = (
    "separate_aws_account_administration",
    "separate_cloudflare_administration",
    "s3_bucket_versioning_enabled",
    "s3_object_lock_default_compliance",
    "retention_floor_ceiling_reviewed",
    "exact_s3_version_id_readback",
    "check_delete_markers_and_forks",
    "deny_on_failed_anchor_readback",
    "deny_on_cf_free_quota",
    "avoid_pii_and_review_lgpd",
    "kms_and_key_recovery_plan_reviewed",
    "offline_no_auto_resend",
)


def _number(value: Any, *, min_value: Decimal = Decimal("0")) -> Decimal | None:
    if type(value) not in (str, int, float, Decimal):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, OverflowError):
        return None
    return result if result.is_finite() and result >= min_value else None


def _read_date(v: Any) -> date | None:
    if type(v) is not str:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def assess_h0_iam_finops_lab(proposal: Any, *, as_of: date | None = None) -> dict[str, Any]:
    """Fail closed; does not contact providers or trust claimed evidence."""
    issues: list[str] = []
    report: dict[str, Any] = {
        "schema": SCHEMA, "state": "HARD_NO_GO",
        "projected_monthly_brl": None,
        "projection_below_review_threshold": False,
        "review_threshold_brl": "160.00",
        "global_cap_brl": "200.00",
        "priced_inputs_complete": False,
        "iam_proposal_allowlist_consistent": False,
        "cloudflare_free_quota_projection_in_range": False,
        "verified_supplier_bill": False,
        "verified_iam_cloud_enforcement": False,
        "aws_cloudflare_accounts_enrolled": False,
        "third_anchor_remotely_authenticated": False,
        "external_highwater_verified": False,
        "first_effect_allowed": False,
        "worker_arming_allowed": False,
        "automatic_retry_allowed": False,
        "external_action_executed": False,
        "issues": issues,
    }
    if type(proposal) is not dict:
        issues.append("PROPOSAL_NOT_PLAIN_DICT")
        return report
    as_of = as_of or datetime.now(timezone.utc).date()
    if type(as_of) is not date:
        issues.append("AS_OF_DATE_INVALID")
        return report

    if proposal.get("schema") != SCHEMA:
        issues.append("SCHEMA_INVALID")
    if proposal.get("aws_region") != "sa-east-1":
        issues.append("AWS_REGION_NOT_PRICED_FOR_SAO_PAULO")
    if proposal.get("cloudflare_plan") != "Workers Free - SQLite Durable Objects":
        issues.append("CLOUDFLARE_PLAN_NOT_MODELED")
    if _number(proposal.get("global_cap_brl")) != MAX_CAP_BRL:
        issues.append("GLOBAL_CAP_CHANGE_NOT_AUTHORIZED")

    quote_date = _read_date(proposal.get("regional_aws_quote_date"))
    fx_date = _read_date(proposal.get("usd_brl_observed_date"))
    for label, value in (("AWS_QUOTE", quote_date), ("USD_BRL", fx_date)):
        if value is None or (as_of - value).days not in range(0, 15):
            issues.append(label + "_FRESH_EVIDENCE_MISSING")
    quotes = proposal.get("quotes")
    quote_values: dict[str, Decimal] = {}
    if type(quotes) is not dict:
        issues.append("COST_QUOTES_MISSING")
    else:
        for key in QUOTES:
            v = _number(quotes.get(key))
            if v is None:
                issues.append("COST_QUOTE_MISSING_OR_INVALID:" + key)
            else:
                quote_values[key] = v
        if quote_values.get("usd_brl_stress_rate", Decimal("0")) == 0:
            issues.append("STRESS_FX_RATE_MUST_BE_POSITIVE")
        if quote_values.get("tax_fx_uncertainty_fraction", Decimal("0")) > Decimal("1"):
            issues.append("UNCERTAINTY_MARGIN_INVALID")
        source = proposal.get("quotes_source")
        if type(source) is not str or not source.startswith("https://"):
            issues.append("AWS_REGIONAL_QUOTE_URL_NOT_RECORDED")

    workload = proposal.get("workload")
    volumes: dict[str, Decimal] = {}
    if type(workload) is not dict:
        issues.append("WORKLOAD_PROJECTION_MISSING")
    else:
        for key in WORKLOAD:
            v = _number(workload.get(key))
            if v is None:
                issues.append("WORKLOAD_MISSING_OR_INVALID:" + key)
            else:
                volumes[key] = v
        for key in ("anchors_per_day", "retention_days", "versions_per_anchor", "bytes_per_version"):
            if volumes.get(key, Decimal("0")) <= 0:
                issues.append("WORKLOAD_MUST_BE_POSITIVE:" + key)
        for key, lim in CF_FREE_LIMITS.items():
            if key in volumes and volumes[key] >= lim * Decimal("0.8"):
                issues.append("CLOUDFLARE_FREE_QUOTA_TOO_CLOSE:" + key)
        report["cloudflare_free_quota_projection_in_range"] = all(
            k in volumes and volumes[k] < ceiling * Decimal("0.8")
            for k, ceiling in CF_FREE_LIMITS.items()
        )
    if all(k in quote_values for k in QUOTES) and all(k in volumes for k in WORKLOAD):
        if (quote_values["usd_brl_stress_rate"] > 0
                and quote_values["tax_fx_uncertainty_fraction"] <= 1):
            retained_gb = (
                volumes["anchors_per_day"] * volumes["retention_days"]
                * volumes["versions_per_anchor"] * volumes["bytes_per_version"] / GIGA
            )
            requests_put = volumes["anchors_per_day"] * DAYS_BILLED * volumes["s3_puts_per_anchor"]
            requests_get = volumes["anchors_per_day"] * DAYS_BILLED * volumes["s3_gets_per_anchor"]
            kms_calls = volumes["anchors_per_day"] * DAYS_BILLED * volumes["kms_calls_per_anchor"]
            usd = (
                retained_gb * quote_values["s3_standard_gb_month_usd"]
                + requests_put / Decimal("1000") * quote_values["s3_put_per_1000_usd"]
                + requests_get / Decimal("1000") * quote_values["s3_get_per_1000_usd"]
                + kms_calls / Decimal("10000") * quote_values["kms_per_10000_usd"]
                + quote_values["kms_key_month_usd"]
                + quote_values["audit_logging_monthly_usd"]
                + quote_values["other_cloud_monthly_usd"]
            )
            projected = (
                quote_values["existing_ecosystem_monthly_brl"]
                + usd * quote_values["usd_brl_stress_rate"]
                * (Decimal("1") + quote_values["tax_fx_uncertainty_fraction"])
            )
            report["projected_monthly_brl"] = str(projected.quantize(Decimal("0.01")))
            report["priced_inputs_complete"] = True
            report["projection_below_review_threshold"] = projected < MAX_CAP_BRL * CAUTION_RATIO
            if projected >= MAX_CAP_BRL * CAUTION_RATIO:
                issues.append("PROJECTED_MONTHLY_COST_EXCEEDS_80_PERCENT_CAUTION_GATE")
            if projected >= MAX_CAP_BRL:
                issues.append("PROJECTED_MONTHLY_COST_EXCEEDS_GLOBAL_CAP")

    roles = proposal.get("proposed_aws_actions_by_role")
    iam_good = type(roles) is dict and set(roles) == set(AWS_ACTIONS_BY_ROLE)
    if not iam_good:
        issues.append("IAM_ROLES_MISSING_OR_EXTRA")
    else:
        for role, allowed in AWS_ACTIONS_BY_ROLE.items():
            selected = roles.get(role)
            if type(selected) is not list or any(type(x) is not str for x in selected):
                issues.append("IAM_ACTIONS_INVALID:" + role)
                iam_good = False
                continue
            if len(set(selected)) != len(selected):
                issues.append("IAM_DUPLICATE_ACTION:" + role)
                iam_good = False
            if set(selected) != allowed or set(selected) & DISALLOWED_ACTIONS:
                issues.append("IAM_OVERPERMISSIVE_OR_INCOMPLETE:" + role)
                iam_good = False
        report["iam_proposal_allowlist_consistent"] = iam_good

    controls = proposal.get("proposed_controls")
    if type(controls) is not dict:
        issues.append("SECURITY_CONTROLS_NOT_DOCUMENTED")
    else:
        for field in REQUIRED_CONTROLS:
            if controls.get(field) is not True:
                issues.append("CONTROL_NOT_PROVEN:" + field)
    if not report["priced_inputs_complete"]:
        issues.append("NO_COMPLETE_COST_PROJECTION")
    # Even a complete signed-looking JSON cannot prove cloud IAM, true billing,
    # custody, external receipts or whether the owner approved the experiment.
    return report


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="AION OFFLINE IAM/FinOps proposal audit; NEVER grants GO")
    p.add_argument("proposal_json", type=Path)
    args = p.parse_args()
    try:
        inp = json.loads(args.proposal_json.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        inp = None
    result = assess_h0_iam_finops_lab(inp)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(2)  # NO-GO always, including complete proposals.
