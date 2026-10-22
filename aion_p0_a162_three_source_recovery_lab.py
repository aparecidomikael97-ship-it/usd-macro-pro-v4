"""A162 synthetic THREE-SOURCE read-only H0 reconciliation, always NO-GO.

Combines a real disposable A147 SQLite intent journal, authenticated A145
checkpoint, A150 lease-bound LOCAL witness head and A161 TWO Ed25519 signed
floor claims (d1/d2). Each of those older LAB parts could match internally
while another part diverged. This cross-check refuses unobserved local CAS,
deleted intent, mismatched ledger/epoch, role/key reuse and simple TOCTOU.

This is defense-in-depth evidence correlation, NOT proof of external
custodian independence, readback freshness, real operator identity or
real provider effect. All data and keys originate from a synthetic test
process. A jointly rolled-back journal, A150 head, and both custodians
can still match: successful mathematics is ONLY quarantine/manual review.

No API returns a GO/RETRY/RESEND grant. Never mutates state or contacts
network, real GitHub, producer or Worker. Only imported read-only APIs.
"""
from __future__ import annotations

from dataclasses import dataclass
import hmac
import os
from typing import Any

from aion_p0_a145_authenticated_checkpoint_lab import (
    SignedCheckpoint, verify_signed_checkpoint,
)
from aion_p0_a145_checkpoint_verifier_lab import (
    CheckpointRejected, canonical_history_digest,
)
from aion_p0_a147_sqlite_crash_journal_lab import (
    JournalUnavailable, SyntheticCrashJournalLAB,
)
from aion_p0_a149_authenticated_cas_lab import A149Denied
from aion_p0_a150_pinned_policy_lease_lab import LeasedPinnedWitnessLAB
from aion_p0_a161_dual_custodian_floor_lab import (
    FloorRejected, SignedFloor, HeadSnapshot,
    assess_restart_dual_floor, a150_read_only_head_snapshot,
)

SCHEMA = "AION_P0_A162_TRIPARTITE_H0_READ_ONLY_CORRELATION_NO_GO_V1"


@dataclass(frozen=True)
class ThreeSourceReview:
    schema: str
    verdict: str
    reason: str
    locally_consistent_in_lab: bool = False
    mathematical_floor_pair_checked_in_lab: bool = False
    # No path to an authorization result, even with all three agreeing.
    real_external_issuer_authenticity_verified: bool = False
    remotely_nonrollbackable_floor_verified: bool = False
    human_owner_critical_consent_verified: bool = False
    real_provider_committed_effect_verified: bool = False
    real_provider_no_effect_fenced: bool = False
    checkpoint_restore_authorized: bool = False
    automatic_retry_allowed: bool = False
    automatic_resend_allowed: bool = False
    external_execution_allowed: bool = False
    worker_allowed: bool = False
    homologated_p0_count: int = 0


class A162Invalid(ValueError):
    """Fail-closed only, no caller-promotable external authority."""


def _fail(reason: str, *, matched: bool = False) -> ThreeSourceReview:
    return ThreeSourceReview(
        SCHEMA, "LAB_HARD_BLOCKED", reason,
        locally_consistent_in_lab=matched,
    )


def _equal(a: Any, b: Any) -> bool:
    return type(a) is str and type(b) is str and hmac.compare_digest(a, b)


def _keys_exact(checkpoint: Any, signed_cp: Any,
                d1d2: Any, witness: LeasedPinnedWitnessLAB) -> None:
    """Pinned roles cannot re-use signer, publisher, checkpoint keys."""
    if type(signed_cp) is not SignedCheckpoint:
        raise A162Invalid("signed_checkpoint_missing")
    if (type(checkpoint) is not dict or len(checkpoint) != 1
            or type(signed_cp.key_id) is not str
            or set(checkpoint) != {signed_cp.key_id}):
        raise A162Invalid("exact_checkpoint_pin_required")
    if type(d1d2) is not dict or set(d1d2) != {"d1", "d2"}:
        raise A162Invalid("two_out_of_band_pins_missing")
    pubs = (
        checkpoint[signed_cp.key_id],
        d1d2["d1"], d1d2["d2"],
        witness.policy.publisher_public_key,
        witness.policy.witness_public_key,
    )
    if any(type(pub) is not bytes or len(pub) != 32 for pub in pubs):
        raise A162Invalid("invalid_key_material")
    if len(set(pubs)) != len(pubs):
        raise A162Invalid("cross_role_signer_key_reuse")
    # Enforcing distinct key bytes is NOT proof of different administrators.


def assess_three_source_restart(
    *,
    journal: SyntheticCrashJournalLAB,
    local_witness: LeasedPinnedWitnessLAB,
    checkpoint: SignedCheckpoint,
    checkpoint_pins: dict[str, bytes],
    floor_d1: SignedFloor,
    floor_d2: SignedFloor,
    floor_pins: dict[str, bytes],
    expected_ledger: str,
    expected_epoch: str,
    request_nonce: str,
    now_ns: int,
) -> ThreeSourceReview:
    """Correlate 3 local/signed sources; every successful path is quarantine.

    The journal is read twice and the A150 witness head is read twice to
    catch simple in-process read drift. This is NOT an atomic cross-database
    transaction and CANNOT defeat an adversary controlling both storages.
    """
    try:
        if (os.environ.get("AION_LAB_MODE") != "1"
                or os.environ.get("AION_WORKER_ENABLED") != "0"
                or os.environ.get("AION_EXTERNAL_EXECUTION_ENABLED") != "0"):
            raise A162Invalid("isolated_lab_mode_and_worker_off_required")
        if type(journal) is not SyntheticCrashJournalLAB:
            raise A162Invalid("real_a147_disposable_journal_required")
        if type(local_witness) is not LeasedPinnedWitnessLAB:
            raise A162Invalid("a150_synthetic_lease_witness_required")
        if (type(expected_ledger) is not str
                or not _equal(journal.ledger_id, expected_ledger)
                or not _equal(local_witness.policy.ledger_id, expected_ledger)):
            raise A162Invalid("ledger_identity_mismatch")
        if not _equal(local_witness.policy.epoch, expected_epoch):
            raise A162Invalid("out_of_band_epoch_policy_mismatch")
        _keys_exact(checkpoint_pins, checkpoint, floor_pins, local_witness)
        before_events = journal.read_events()
        before_head = a150_read_only_head_snapshot(local_witness)
        if (not _equal(before_head.ledger_id, expected_ledger)
                or not _equal(before_head.epoch, expected_epoch)):
            raise A162Invalid("head_ledger_epoch_drift")
        # Source 1: real A147 local journal, exact A145 signed checkpoint.
        verify_signed_checkpoint(
            ledger_id=expected_ledger, events=before_events,
            envelope=checkpoint, pinned_keys=checkpoint_pins,
        )
        # Source 2: real A150 local witness; it has its own schema/pin/lease.
        digest = canonical_history_digest(before_events)
        if (before_head.sequence != len(before_events)
                or not _equal(before_head.history_digest, digest)
                or checkpoint.checkpoint.sequence != before_head.sequence
                or not _equal(checkpoint.checkpoint.history_digest,
                              before_head.history_digest)):
            raise A162Invalid("a147_a150_checkpoint_state_disagreement")

        # Source 3: two distinct signed nonce-bound d1/d2 floor claims.
        # A161 always BLOCKS or QUARANTINES, never claims independent custody.
        evidence = assess_restart_dual_floor(
            local_head=before_head,
            d1=floor_d1,
            d2=floor_d2,
            pinned_custodian_keys=floor_pins,
            request_nonce=request_nonce,
            expected_ledger_id=expected_ledger,
            expected_epoch=expected_epoch,
            now_ns=now_ns,
        )
        if evidence.verdict != "LAB_QUARANTINE_MANUAL_REVIEW":
            return _fail("dual_custodian_floor:" + evidence.reason)

        # Catch straightforward time-of-check/time-of-use changes.
        after_events = journal.read_events()
        after_head = a150_read_only_head_snapshot(local_witness)
        if before_events != after_events or before_head != after_head:
            raise A162Invalid("multiple_source_read_drift")

        return ThreeSourceReview(
            schema=SCHEMA,
            verdict="LAB_QUARANTINE_MANUAL_REVIEW",
            reason=("first_uncertain_local_reservation_requires_provider_evidence"
                    if before_events else "genesis_consistency_not_authorized"),
            locally_consistent_in_lab=True,
            mathematical_floor_pair_checked_in_lab=True,
        )
    except (A162Invalid, FloorRejected, CheckpointRejected,
            JournalUnavailable, A149Denied, ValueError) as exc:
        return _fail(str(exc))
    except Exception:
        # Do not leak errors as a permissive state or retry the read.
        return _fail("unexpected_source_validation_failure")
