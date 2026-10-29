"""A258 — external P0 proof-admission inventory; conservative OFFLINE DENY.

This deliberately does NOT infer independent authority from host-supplied
metadata, valid signatures or local anti-replay. No positive P0 completion
path exists until verified separate trust domains are implemented and audited.
This module is an audit companion, NOT the production Outbox authorization.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

SCHEMA = "ATLASQUANT_AION_A258_EXTERNAL_EVIDENCE_GAP_V1"

# Each missing proof is a distinct operational blocker, not a feature flag.
GAPS = (
    ("P0-1", "independent human owner identity and authorization"),
    ("P0-2", "independently rooted external authority and key custody"),
    ("P0-3", "origin-authenticated immutable business event ID and replay proof"),
    ("P0-4", "monotonic first-attempt reservation across host/witness rollback"),
    ("P0-5", "native SQLite FD/VFS identity and same-inode rollback protection"),
    ("P0-6", "post-COMMIT recovery and independently verified provider effect"),
)

UNTRUSTED_CLAIM_NAMES = frozenset({
    "trusted", "verified", "external_verified", "signed", "attested",
    "approval", "root_independent", "witness_independent", "human_owner",
    "p0_complete", "green", "ready", "ci_passed", "authorizes_send",
    "status", "receipt", "origin_signature", "witness_signature",
})


@dataclass(frozen=True)
class OfflineNoGoAssessment:
    """An immutable no-go result; never represents a credential or a token."""

    schema: str
    status: str
    p0_homologated: int
    p0_required: int
    missing_p0: tuple[str, ...]
    evidence_classification: str
    independent_authority_proven: bool
    authorizes_send: bool
    permits_worker: bool
    permits_deploy: bool
    permits_merge: bool

    def as_dict(self):
        return {
            "schema": self.schema, "status": self.status,
            "p0_homologated": self.p0_homologated,
            "p0_required": self.p0_required, "missing_p0": list(self.missing_p0),
            "evidence_classification": self.evidence_classification,
            "independent_authority_proven": self.independent_authority_proven,
            "authorizes_send": self.authorizes_send,
            "permits_worker": self.permits_worker,
            "permits_deploy": self.permits_deploy,
            "permits_merge": self.permits_merge,
        }


def assess_offline_claims(claims=None) -> OfflineNoGoAssessment:
    """Classify ALL caller-supplied evidence as unverified until external proof.

    An uploaded certificate, two signatures, CI green, outbox callback,
    host-pinned public keys, local clock, SQLite files or receipt-shaped
    object cannot prove independent provenance just by existing. No caller-
    controlled input can flip the result to GO. This is intentionally strict.
    """
    classification = "NO_EXTERNAL_EVIDENCE_SUBMITTED"
    if claims is not None:
        classification = "HOST_SUPPLIED_UNVERIFIED"
        # Access no properties, methods or user-controlled '__bool__' values
        # during security classification; even a malicious Mapping must not
        # be able to affect or crash our refusal.
        if type(claims) not in (dict, tuple, list, str, int, float, bytes, bool):
            classification = "OPAQUE_UNVERIFIED_INPUT"
    return OfflineNoGoAssessment(
        schema=SCHEMA, status="HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING",
        p0_homologated=0, p0_required=len(GAPS),
        missing_p0=tuple(p0 for p0, _ in GAPS),
        evidence_classification=classification,
        independent_authority_proven=False, authorizes_send=False,
        permits_worker=False, permits_deploy=False, permits_merge=False,
    )


__all__ = ["SCHEMA", "GAPS", "UNTRUSTED_CLAIM_NAMES",
           "OfflineNoGoAssessment", "assess_offline_claims"]
