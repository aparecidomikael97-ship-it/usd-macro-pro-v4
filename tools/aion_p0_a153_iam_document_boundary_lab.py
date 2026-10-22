"""A153 — static IAM JSON policy fence, isolated LAB; ALWAYS HARD NO-GO.

Checks only exact, extremely narrow *proposed* S3 role policy shapes for an
append-only third-domain anchor candidate. It does NOT parse/evaluate full
AWS IAM semantics, enforce cloud permissions, attest separate accounts,
verify MFA, prevent credential delegation, inspect Cloudflare IAM, validate
Object Lock or authorize AWS provider operations. Never calls cloud APIs.

No network, AWS SDK, credentials, policy deployment, Worker or provider.
It intentionally refuses complex IAM features (NotAction, NotResource,
Principal, wildcards in actions, variables, alternate Conditions, etc.).
Passing a static proposal proves NO externally enforced separation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

# Standalone CLI from tools/ must only resolve code within the checkout.
CHECKOUT_ROOT = Path(__file__).resolve().parents[1]
if str(CHECKOUT_ROOT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT_ROOT))

from atlasquant_aion_p0_h0_iam_finops_preflight_lab import AWS_ACTIONS_BY_ROLE

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "AION_P0_A153_IAM_DOCUMENT_FENCE_LAB_V1"
SOURCE = "OFFLINE_USER_OR_FIXTURE_SUPPLIED_UNVERIFIED_POLICY"
ROLE_NAMES = tuple(sorted(AWS_ACTIONS_BY_ROLE))
ACCOUNT = re.compile(r"[0-9]{12}\Z")
BUCKET = re.compile(r"[a-z0-9](?:[a-z0-9.-]{3,61})[a-z0-9]\Z")
LABEL = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{3,95}\Z")
PREFIX = "aion-h0/v1/"
POLICY_VERSION = "2012-10-17"
S3_WRITER = "s3:PutObject"
S3_READERS = (
    "s3:GetBucketObjectLockConfiguration", "s3:GetObjectRetention",
    "s3:GetObjectVersion", "s3:ListBucketVersions",
)
ALLOWED_PROPOSAL_FIELDS = {
    "schema", "d0_executor_aws_account_id", "d2_anchor_aws_account_id",
    "d0_administrator_label", "d1_custodian_administrator_label",
    "d2_anchor_administrator_label", "d2_recovery_administrator_label",
    "bucket_name", "object_prefix", "proposed_role_policies",
}
MAX_POLICY_BYTES = 20000


class PolicyInputRejected(ValueError):
    """Reject ambiguous JSON (especially duplicate keys), never silently GO."""


def _plain_dict(value: Any) -> bool:
    return type(value) is dict


def _record_unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise PolicyInputRejected("DUPLICATE_JSON_KEY")
        out[key] = value
    return out


def decode_proposal_json(text: str) -> Any:
    if type(text) is not str or len(text.encode("utf-8")) > MAX_POLICY_BYTES:
        raise PolicyInputRejected("PROPOSAL_TOO_LARGE_OR_INVALID")
    try:
        return json.loads(text, object_pairs_hook=_record_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              PolicyInputRejected("NONFINITE_JSON_NUMBER")
                          ))
    except (UnicodeError, ValueError, RecursionError, TypeError) as exc:
        raise PolicyInputRejected("PROPOSAL_JSON_INVALID_OR_AMBIGUOUS") from exc


def _expected_documents(bucket_name: str, prefix: str) -> dict[str, dict[str, Any]]:
    bucket_arn = "arn:aws:s3:::" + bucket_name
    object_arn = bucket_arn + "/" + prefix + "*"
    return {
        "aion_executor": {"Version": POLICY_VERSION, "Statement": []},
        "cloudflare_cas_runtime": {"Version": POLICY_VERSION, "Statement": []},
        "aws_anchor_writer": {
            "Version": POLICY_VERSION,
            "Statement": [
                {"Sid": "A153AppendOnlyCandidate",
                 "Effect": "Allow", "Action": [S3_WRITER],
                 "Resource": [object_arn]},
            ],
        },
        "aws_anchor_reader": {
            "Version": POLICY_VERSION,
            "Statement": [
                {"Sid": "A153ListAnchorVersions",
                 "Effect": "Allow", "Action": ["s3:ListBucketVersions"],
                 "Resource": [bucket_arn],
                 "Condition": {"StringLike": {"s3:prefix": [prefix + "*"]}}},
                {"Sid": "A153ReadRetentionConfiguration",
                 "Effect": "Allow",
                 "Action": ["s3:GetBucketObjectLockConfiguration"],
                 "Resource": [bucket_arn]},
                {"Sid": "A153ReadExactObjectVersions",
                 "Effect": "Allow",
                 "Action": ["s3:GetObjectRetention", "s3:GetObjectVersion"],
                 "Resource": [object_arn]},
            ],
        },
    }


def _shape_exact(lhs: Any, rhs: Any) -> bool:
    """Type-safe exact value match. No object coercion, no extra IAM fields."""
    if type(lhs) is not type(rhs):
        return False
    if type(rhs) is dict:
        return set(lhs) == set(rhs) and all(
            _shape_exact(lhs[key], rhs[key]) for key in rhs
        )
    if type(rhs) is list:
        return len(lhs) == len(rhs) and all(
            _shape_exact(a, b) for a, b in zip(lhs, rhs)
        )
    return lhs == rhs


def inspect_candidate_iam_lab(candidate: Any) -> dict[str, Any]:
    findings: list[str] = []
    # Exact schema and values are for *documentary static risk review only*.
    if not _plain_dict(candidate) or set(candidate) != ALLOWED_PROPOSAL_FIELDS:
        findings.append("PROPOSAL_SHAPE_INVALID")
        candidate = {}
    if candidate.get("schema") != SCHEMA:
        findings.append("SCHEMA_INVALID")
    d0 = candidate.get("d0_executor_aws_account_id")
    d2 = candidate.get("d2_anchor_aws_account_id")
    for name, value in (("D0", d0), ("D2", d2)):
        if type(value) is not str or ACCOUNT.fullmatch(value) is None:
            findings.append("ACCOUNT_ID_SYNTAX_INVALID:" + name)
    if type(d0) is str and type(d2) is str and d0 == d2:
        findings.append("SAME_ACCOUNT_LABEL_NOT_SEPARATED")

    admin_fields = (
        "d0_administrator_label", "d1_custodian_administrator_label",
        "d2_anchor_administrator_label", "d2_recovery_administrator_label",
    )
    admin_values = [candidate.get(k) for k in admin_fields]
    if not all(type(v) is str and LABEL.fullmatch(v) for v in admin_values):
        findings.append("ADMIN_CONTROLLER_LABEL_INVALID")
    elif len(set(admin_values)) != len(admin_values):
        findings.append("ADMIN_CONTROLLER_LABELS_OVERLAP")

    bucket = candidate.get("bucket_name")
    prefix = candidate.get("object_prefix")
    if (type(bucket) is not str or BUCKET.fullmatch(bucket) is None
            or ".." in bucket or bucket.startswith("xn--")):
        findings.append("BUCKET_NAME_INVALID")
    if prefix != PREFIX:
        findings.append("ANCHOR_PREFIX_CHANGED")
    roles = candidate.get("proposed_role_policies")
    if not _plain_dict(roles) or set(roles) != set(ROLE_NAMES):
        findings.append("PROPOSED_ROLE_SET_INVALID")
    elif "BUCKET_NAME_INVALID" not in findings and "ANCHOR_PREFIX_CHANGED" not in findings:
        expected = _expected_documents(bucket, PREFIX)
        for role in ROLE_NAMES:
            if not _shape_exact(roles[role], expected[role]):
                findings.append("IAM_POLICY_SCOPE_OR_SYNTAX_INVALID:" + role)
        # Cross check canonical existing role/action allowlist.
        if set([S3_WRITER]) != set(AWS_ACTIONS_BY_ROLE["aws_anchor_writer"]) \
                or set(S3_READERS) != set(AWS_ACTIONS_BY_ROLE["aws_anchor_reader"]) \
                or AWS_ACTIONS_BY_ROLE["aion_executor"] \
                or AWS_ACTIONS_BY_ROLE["cloudflare_cas_runtime"]:
            findings.append("IAM_CANONICAL_ALLOWLIST_DRIFT")

    findings = sorted(set(findings))
    return {
        "schema": SCHEMA,
        "source_classification": SOURCE,
        "static_proposal_matches_restrictive_template_lab": not findings,
        "findings": findings,
        "trust_limits": [
            "NO_REMOTE_IAM_POLICY_SIMULATION_OR_CLOUD_ENFORCEMENT",
            "NO_VERIFIED_D0_D1_D2_ACCOUNT_ADMINISTRATIVE_INDEPENDENCE",
            "NO_REAL_ACCOUNT_ID_PROVENANCE_OR_OWNER_RECOVERY_RIGHTS",
            "NO_WORM_OBJECT_LOCK_CONFIGURATION_OR_CURRENT_HEAD_ATTESTED",
            "NO_PROVEN_EXTERNAL_SIGNATURE_ISSUER_OR_KEY_CUSTODY",
            "NO_REAL_PROVIDER_EFFECT_OR_TERMINAL_NO_EFFECT_RECEIPT",
        ],
        "actual_account_separation_verified": False,
        "iam_live_enforcement_verified": False,
        "immutable_anchor_attested": False,
        "real_HUMAN_OWNER_consent_verified": False,
        "external_provider_effect_authenticated": False,
        "additional_spend_authorized_brl": 0,
        "first_effect_allowed": False,
        "worker_allowed": False,
        "automatic_resend_allowed": False,
        "homologated_p0_count": 0,
        "verdict": "HARD_NO_GO_E1_AWS_IAM_UNENROLLED",
    }


def audit_static_file(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise PolicyInputRejected("POLICY_FILE_MISSING_OR_SYMLINKED")
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PolicyInputRejected("POLICY_FILE_READ_FAILED") from exc
    return inspect_candidate_iam_lab(decode_proposal_json(raw))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A153 synthetic IAM preflight; always NO-GO")
    parser.add_argument("proposal_json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit_static_file(args.proposal_json)
        print(json.dumps(report, sort_keys=True, indent=2))
        # This is a static proposal check only, never IAM readiness.
        return 0 if report["static_proposal_matches_restrictive_template_lab"] else 3
    except (PolicyInputRejected, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"verdict": "HARD_NO_GO", "error": str(exc)}),file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
