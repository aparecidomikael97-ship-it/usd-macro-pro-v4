"""G140 genuine external P0 evidence intake and anti-greenwash gate. LAB ONLY.

This validator does NOT authenticate an external custodian, trustee, reviewer,
provider or native SQLite VFS. All JSON input is caller-controlled. Therefore
even an apparently perfect evidence dossier returns HARD_NO_GO and can only
be triaged for *independent external review*, never approved or used to SEND.

No network, credentials, services, real customer effects, Worker or deploy.
Five identifiers are pinned to the unchanged real G122 RED test names; six P0
remain open. Do not remove or replace the canonical G122 job to get CI green.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any

SCHEMA = "AION_G140_EXTERNAL_EVIDENCE_INTAKE_LAB_V1"
RED_G122_IDS = (
    "test_custody_plus_checkpoint_rollback_must_not_reauthorize",
    "test_replacement_original_enrollment_must_be_detected",
    "test_replacement_trust_root_and_fingerprint_must_be_detected",
    "test_live_restore_same_inode_must_be_attested_before_read",
    "test_live_restore_same_inode_must_not_reopen_write_authority",
)
EXPECTED_TOP = frozenset({"schema", "repository_commit", "evidence"})
EXPECTED_ROW = frozenset({
    "case_id", "claimed_result", "source_kind", "source_identifier",
    "artifact_sha256", "independence_claimed", "reviewer_claimed",
})
_SHA = re.compile(r"[0-9a-f]{40,64}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}\Z")
_ASSERTION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}\Z")
CLAIMED_RESULTS = frozenset({"unmet", "pass_claimed", "not_tested"})
SOURCE_TYPES = frozenset({
    "synthetic_lab", "same_host", "self_attested", "ci_fixture",
    "independent_external_claimed",
})

@dataclass(frozen=True)
class IntakeVerdict:
    status: str
    externally_verified: bool
    p0_homologated: int
    p0_total: int
    allows_worker: bool
    allows_provider_send: bool
    allows_retry: bool
    requires_independent_review: bool
    checks: tuple[str, ...]


def _result(status: str, checks: tuple[str, ...],
            review: bool = False) -> IntakeVerdict:
    # This is an intake TRIAGE ONLY, not a proof verifier. There is no
    # accepted-success state or caller-supplied hook that can grant authority.
    return IntakeVerdict(
        status=status,
        externally_verified=False,
        p0_homologated=0,
        p0_total=6,
        allows_worker=False,
        allows_provider_send=False,
        allows_retry=False,
        requires_independent_review=review,
        checks=checks,
    )


def evaluate_p0_external_evidence_lab(dossier: Any) -> IntakeVerdict:
    """Conservatively classify caller-provided artifacts WITHOUT trusting them.

    All fields, even a sha256 and external-sounding issuer, are unverified
    CLAIMS. A self-attested claim of independence never qualifies for P0.
    """
    if type(dossier) is not dict or set(dossier) != EXPECTED_TOP:
        return _result("DENY_INVALID_DOSSIER_HARD_NO_GO", ("exact_top_schema",))
    if dossier["schema"] != SCHEMA:
        return _result("DENY_INVALID_DOSSIER_HARD_NO_GO", ("schema_version",))
    commit = dossier["repository_commit"]
    if type(commit) is not str or not _SHA.fullmatch(commit):
        return _result("DENY_INVALID_DOSSIER_HARD_NO_GO", ("exact_commit_id",))
    rows = dossier["evidence"]
    if type(rows) is not list or len(rows) != len(RED_G122_IDS):
        return _result("DENY_INCOMPLETE_G122_HARD_NO_GO", ("five_canonical_g122_cases",))
    seen = set()
    has_local = False
    untested = []
    for row in rows:
        if type(row) is not dict or set(row) != EXPECTED_ROW:
            return _result("DENY_INVALID_DOSSIER_HARD_NO_GO", ("exact_case_fields",))
        case_id = row["case_id"]
        if type(case_id) is not str or case_id not in RED_G122_IDS or case_id in seen:
            return _result("DENY_INVALID_DOSSIER_HARD_NO_GO", ("unique_canonical_g122_id",))
        seen.add(case_id)
        if type(row["claimed_result"]) is not str or row["claimed_result"] not in CLAIMED_RESULTS:
            return _result("DENY_INVALID_DOSSIER_HARD_NO_GO", ("claimed_result_enum",))
        source = row["source_kind"]
        if type(source) is not str or source not in SOURCE_TYPES:
            return _result("DENY_INVALID_DOSSIER_HARD_NO_GO", ("source_kind_enum",))
        for key in ("source_identifier", "reviewer_claimed"):
            value = row[key]
            if type(value) is not str or not _REFERENCE.fullmatch(value):
                return _result("DENY_INVALID_DOSSIER_HARD_NO_GO", (key,))
        proof_hash = row["artifact_sha256"]
        if type(proof_hash) is not str or not _HASH.fullmatch(proof_hash):
            return _result("DENY_INVALID_DOSSIER_HARD_NO_GO", ("artifact_sha256_format_only",))
        if type(row["independence_claimed"]) is not bool:
            return _result("DENY_INVALID_DOSSIER_HARD_NO_GO", ("exact_independence_boolean",))
        if source != "independent_external_claimed":
            has_local = True
        if row["claimed_result"] != "pass_claimed":
            untested.append(case_id)
    if seen != set(RED_G122_IDS):
        return _result("DENY_INCOMPLETE_G122_HARD_NO_GO", ("canonical_G122_ID_set",))
    if has_local:
        return _result(
            "DENY_SELF_ATTESTED_EVIDENCE_HARD_NO_GO",
            ("local_or_synthetic_evidence_never_external", "no_SEND", "no_P0"),
        )
    if untested:
        return _result(
            "DENY_G122_STILL_UNMET_HARD_NO_GO",
            tuple(sorted(untested)),
        )
    return _result(
        "EXTERNAL_CLAIMS_REQUIRE_INDEPENDENT_ADJUDICATION_HARD_NO_GO",
        ("file_hash_does_not_prove_independence",
         "reviewer_name_is_not_cryptographic_attestation",
         "claimed_external_status_not_trusted",
         "native_same_inode_and_first_owner_not_proven"),
        review=True,
    )


__all__ = [
    "SCHEMA", "RED_G122_IDS", "IntakeVerdict",
    "evaluate_p0_external_evidence_lab",
]
