"""A190 G141: conservative CUSTODIAN DESIGN proposal guard (offline LAB only).

This does not authenticate a provider, owner, cloud account, KMS root, SQLite
VFS, payment effect, or provenance. Every verdict is HARD_NO_GO regardless of
caller-supplied claims. It reviews only obvious architectural anti-patterns.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

SCHEMA = "AION_A190_G141_CUSTODIAN_PROPOSAL_LAB_V1"
VENDORS = frozenset({"AWS_CANDIDATE", "GCP_CANDIDATE", "VENDOR_NEUTRAL"})
EXPECTED_FIELDS = frozenset({
    "schema", "vendor", "writer_regions", "multi_active_event_writes",
    "manual_failover_with_external_epoch", "original_business_key_claimed",
    "atomic_unique_reservation_claimed", "relies_on_short_client_token",
    "provider_effect_inside_transaction_callback",
    "immutable_archive_version_pinned_claimed", "ack_loss_auto_resend",
    "offline_new_effect_allowed", "host_can_repin_custodian_root",
})
BOOLEAN_FIELDS = EXPECTED_FIELDS - {"schema", "vendor", "writer_regions"}
REGION_ID = re.compile(r"[a-z0-9][a-z0-9-]{1,63}\Z")

REQUIRED_REAL_TESTS = (
    "T9_MULTI_REGION_SAME_ECONOMIC_EVENT",
    "T10_TRANSACTION_CALLBACK_REEXECUTION_NO_EFFECT",
    "T11_WORM_VERSION_AND_DELETE_MARKER_PROVENANCE",
    "T12_SHORT_TOKEN_EXPIRED_WITH_HOST_ROLLBACK",
    "T13_REGION_OUTAGE_FAIL_CLOSED_NO_AUTO_RESEND",
)


@dataclass(frozen=True)
class DesignVerdict:
    status: str
    risks: tuple[str, ...]
    requires_independent_review: bool
    externally_verified: bool = False
    p0_homologated: int = 0
    p0_total: int = 6
    allows_worker: bool = False
    allows_provider_send: bool = False
    allows_retry: bool = False
    safe_to_install: bool = False


def _deny(status: str, risks: tuple[str, ...]) -> DesignVerdict:
    return DesignVerdict(
        status=status,
        risks=risks,
        requires_independent_review=(
            status == "DESIGN_REVIEW_ONLY_EXTERNAL_PROOF_MISSING_HARD_NO_GO"
        ),
    )


def review_custodian_proposal_lab(proposal: Any) -> DesignVerdict:
    """Reject known UNSAFE designs; a passing PAPER design is never a GO."""
    if type(proposal) is not dict or set(proposal) != EXPECTED_FIELDS:
        return _deny("DENY_INVALID_DESIGN_HARD_NO_GO", ("EXACT_FIELDS_REQUIRED",))
    if proposal["schema"] != SCHEMA or proposal["vendor"] not in VENDORS:
        return _deny("DENY_INVALID_DESIGN_HARD_NO_GO", ("SCHEMA_OR_VENDOR_INVALID",))
    if any(type(proposal[name]) is not bool for name in BOOLEAN_FIELDS):
        return _deny("DENY_INVALID_DESIGN_HARD_NO_GO", ("EXACT_BOOLEAN_TYPES_REQUIRED",))
    regions = proposal["writer_regions"]
    if (type(regions) is not list or not regions or
            any(type(v) is not str or not REGION_ID.fullmatch(v) for v in regions)):
        return _deny("DENY_INVALID_DESIGN_HARD_NO_GO", ("VALID_WRITER_REGIONS_REQUIRED",))

    problems: list[str] = []
    if len(regions) != 1 or len(set(regions)) != 1 or proposal["multi_active_event_writes"]:
        problems.append("MULTI_WRITER_NOT_A_GLOBAL_UNIQUE_RESERVATION")
    if not proposal["manual_failover_with_external_epoch"]:
        problems.append("FAILOVER_WITHOUT_EXTERNAL_FENCE")
    if not proposal["original_business_key_claimed"]:
        problems.append("CLIENT_CAN_RENAME_ECONOMIC_EVENT")
    if not proposal["atomic_unique_reservation_claimed"]:
        problems.append("NO_ATOMIC_SINGLE_USE_RESERVATION")
    if proposal["relies_on_short_client_token"]:
        problems.append("FINITE_TOKEN_WINDOW_NOT_DURABLE_IDEMPOTENCY")
    if proposal["provider_effect_inside_transaction_callback"]:
        problems.append("TRANSACTION_CALLBACK_MAY_REEXECUTE_EFFECT")
    if not proposal["immutable_archive_version_pinned_claimed"]:
        problems.append("WORM_VERSION_NOT_INDEPENDENTLY_PINNED")
    if proposal["ack_loss_auto_resend"]:
        problems.append("ACK_LOSS_MUST_NOT_TRIGGER_RETRY")
    if proposal["offline_new_effect_allowed"]:
        problems.append("OFFLINE_MODE_MUST_NOT_ENABLE_FIRST_SEND")
    if proposal["host_can_repin_custodian_root"]:
        problems.append("HOST_CONTROLLED_ROOT_IS_NOT_INDEPENDENT")
    if problems:
        return _deny("DENY_UNSAFE_PROPOSED_DESIGN_HARD_NO_GO", tuple(problems))
    return _deny(
        "DESIGN_REVIEW_ONLY_EXTERNAL_PROOF_MISSING_HARD_NO_GO",
        (
            "CLAIMS_NOT_VERIFIED_BY_INDEPENDENT_OPERATOR",
            "NATIVE_SQLITE_AND_ORIGINAL_OWNER_STILL_UNPROVEN",
            "PROVIDER_CAUSAL_RECEIPT_AND_NO_EFFECT_FENCE_MISSING",
            "G122_FIVE_GENUINE_EXTERNAL_TESTS_STILL_RED",
        ),
    )


__all__ = [
    "SCHEMA", "VENDORS", "REQUIRED_REAL_TESTS", "DesignVerdict",
    "review_custodian_proposal_lab",
]
