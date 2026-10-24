"""A190 G21: real AION Outbox read-only recovery bridge, LAB only.

No dispatch, no provider, no mutation, no claimed P0 closure. The witness is
injected and can be synthetic; real trust must be independently provisioned.
"""
from typing import Any
from g20_independent_witness_recovery_contract_lab import (
    Admission, RecoveryDenied, recovery_admission,
)


def inspect_outbox_recovery(*, outbox: Any, idempotency_key: str,
                            witness: Any, pinned_root_id: str) -> Admission:
    """Read a REAL ExecutionOutbox row and fail closed against witness.

    Never creates a reservation or dispatches. A missing or mismatched external
    statement denies. Even a matching statement returns UNCERTAIN, not SEND.
    The local journal schema is projected into a minimal canonical envelope;
    the trusted witness must sign that same envelope with a separately pinned
    key and monotonic sequence. This lab cannot attest true host independence.
    """
    if not isinstance(idempotency_key, str) or not idempotency_key:
        raise RecoveryDenied("G21_INVALID_IDEMPOTENCY_KEY")
    try:
        row = outbox.get(idempotency_key)
    except LookupError as exc:
        raise RecoveryDenied("G21_REAL_OUTBOX_ROW_MISSING") from exc
    except Exception as exc:
        raise RecoveryDenied("G21_REAL_OUTBOX_READ_FAILED") from exc
    if not row:
        raise RecoveryDenied("G21_REAL_OUTBOX_ROW_MISSING")
    if row.get("idempotency_key") != idempotency_key:
        raise RecoveryDenied("G21_REAL_OUTBOX_KEY_MISMATCH")
    # No caller-controlled request_id may be substituted as a semantic key.
    # This is a diagnostic key, NOT yet an independently attested semantic ID.
    try:
        sequence = row["attempts"] + 1
        if type(row["attempts"]) is not int or row["attempts"] < 0:
            raise ValueError("bad attempts")
        phase = "UNCERTAIN" if row["state"] == "UNCERTAIN" else "RESERVED"
        if row["state"] not in {"PENDING", "CLAIMED", "UNCERTAIN"}:
            raise ValueError("not recoverable phase")
        journal = {
            "semantic_key": idempotency_key,
            "sequence": sequence,
            "phase": phase,
            "outbox_state": row["state"],
            "outbox_idempotency_key": row["idempotency_key"],
            "outbox_attempts": row["attempts"],
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise RecoveryDenied("G21_REAL_OUTBOX_ROW_UNSUPPORTED") from exc
    return recovery_admission(
        semantic_key=idempotency_key,
        local_journal=journal,
        witness=witness,
        pinned_root_id=pinned_root_id,
    )
