"""P0/H0 LAB read-only recovery triage of the REAL ExecutionOutbox SQLite state.

A caller provides previously observed intent handles. This audit never trusts
the caller's handle history as an independent witness. The whole historical
record and these hints can roll back together. Even coherent local rows cannot
prove an external effect or its absence. NO network, adapter, dispatch, Worker,
state transition, retry, compensation, authority or external provider access.

This module only calls ExecutionOutbox.get() to observe existing local rows;
it never calls enqueue(), claim_next(), dispatch_claimed(), reconcile() or
any mutation. There is no status that authorizes a send or terminal transition.
"""
from __future__ import annotations

import re
from typing import Any

from atlasquant_aion_execution_outbox import ExecutionOutbox

SCHEMA = "AION_P0_H0_READONLY_RECOVERY_TRIAGE_LAB_V1"
MANIFEST_SCHEMA = "AION_P0_H0_CALLER_HISTORY_HINTS_LAB_V1"
MANIFEST_FIELDS = frozenset(("schema", "cases"))
CASE_FIELDS = frozenset((
    "idempotency_key", "last_known_state", "last_known_attempts",
    "last_known_dispatch_started_at",
))
STATES = frozenset((
    "PENDING", "RETRY", "CLAIMED", "SENT", "UNCERTAIN", "BLOCKED_PRODUCER",
    "CONFIRMED", "REVOKED", "FAILED", "BLOCKED_REAPPROVAL",
))
MAY_DISPATCH_LOCALLY = frozenset(("PENDING", "RETRY", "CLAIMED"))
KNOWN_AFTER_DISPATCH = frozenset((
    "UNCERTAIN", "SENT", "CONFIRMED", "BLOCKED_PRODUCER",
))
# Terminal local states must never silently revert or change identity on the
# same idempotency key. This is only a rollback *symptom*, not proof of effect.
TERMINAL_LOCAL_STATES = frozenset((
    "CONFIRMED", "REVOKED", "FAILED", "BLOCKED_REAPPROVAL",
))
HEX = re.compile(r"[0-9a-f]{64}\Z")
UTC = re.compile(
    r"(?:\d{4}-\d{2}-\d{2})T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d"
    r"(?:\.\d{1,6})?(?:Z|\+00:00)\Z"
)
BLOCKERS = (
    "LOCAL_EXECUTION_HISTORY_CAN_BE_ROLLED_BACK",
    "CALLER_HINTS_NOT_INDEPENDENT_EXTERNAL_EVIDENCE",
    "ABSENT_INTENT_IS_NOT_PROOF_OF_NO_EXTERNAL_EFFECT",
    "SENT_OR_UNKNOWN_NEEDS_PROVIDER_ORIGIN_CAUSAL_CONFIRMATION",
    "NO_REAL_EXTERNAL_ATOMIC_NONCE_OR_PROVIDER_FENCE",
    "NO_INDEPENDENT_LATEST_HEAD_OR_TRUSTED_PRODUCER",
    "HUMAN_OWNER_NOT_AUTHENTICATED",
    "HARD_NO_GO_UNTIL_SIX_P0_AND_CANONICAL_QUALITY_CLOSED",
)
FLAGS_FALSE = {
    "authenticated_external_producer_state": False,
    "history_complete_and_fresh": False,
    "independent_rollback_detection": False,
    "no_effect_fenced_by_real_provider": False,
    "effect_committed_by_real_provider": False,
    "safe_to_reconstruct_missing_intent": False,
    "safe_to_reclaim_stale_intent": False,
    "safe_to_repeat_first_attempt": False,
    "safe_to_release_next_aggregate_action": False,
    "outbox_terminal_transition_allowed": False,
    "manual_override_authorized": False,
    "automatic_retry_allowed": False,
    "worker_arming_allowed": False,
    "external_action_executed": False,
}


def _plain(value: Any, keys: frozenset[str]) -> bool:
    return (
        type(value) is dict
        and all(type(k) is str for k in value)
        and frozenset(value) == keys
    )


def _valid_case(item: Any) -> bool:
    if not _plain(item, CASE_FIELDS):
        return False
    key = item["idempotency_key"]
    state = item["last_known_state"]
    attempts = item["last_known_attempts"]
    dispatch = item["last_known_dispatch_started_at"]
    return (
        type(key) is str and HEX.fullmatch(key) is not None
        and type(state) is str and state in STATES
        and type(attempts) is int and 0 <= attempts <= 1_000_000
        and type(dispatch) is str and (
            dispatch == "" or
            (len(dispatch) <= 40 and UTC.fullmatch(dispatch) is not None)
        )
    )


def _valid_manifest(obj: Any) -> bool:
    if not _plain(obj, MANIFEST_FIELDS):
        return False
    if type(obj["schema"]) is not str or obj["schema"] != MANIFEST_SCHEMA:
        return False
    cases = obj["cases"]
    if (type(cases) is not list or not 1 <= len(cases) <= 32
            or not all(_valid_case(c) for c in cases)):
        return False
    handles = [item["idempotency_key"] for item in cases]
    if len(set(handles)) != len(handles):
        return False
    return handles == sorted(handles)


def _base(findings: list[dict[str, Any]], *, shape_valid: bool) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "HARD_NO_GO",
        "allowed": False,
        "simulation_only": True,
        "read_only": True,
        "manifest_shape_valid_lab": shape_valid,
        "external_truth": "UNVERIFIED",
        "reconciliation_state": "UNKNOWN_BLOCKED",
        "required_followup": "INDEPENDENT_PROVIDER_CAUSAL_RECONCILIATION_AND_HUMAN_REVIEW",
        "observations": tuple(findings),
        "blockers": BLOCKERS,
        **FLAGS_FALSE,
    }


def inspect_execution_outbox_recovery_readonly_lab(
    outbox: Any, caller_history_hints: Any,
) -> dict[str, Any]:
    """Read local Outbox rows only. Never assert a future effect is safe.

    Caller hints are NOT authenticated: 1. They may be forged; 2. a joint
    snapshot restore can roll back both the hints and SQLite at once;
    3. absence of a key after restore proves no fact about provider effects.
    """
    if type(outbox) is not ExecutionOutbox:
        return _base(
            [{"reason": "REAL_OUTBOX_INSTANCE_REQUIRED"}], shape_valid=False
        )
    if not _valid_manifest(caller_history_hints):
        return _base(
            [{"reason": "CALLER_HINTS_MALFORMED_OR_UNSAFE"}], shape_valid=False
        )
    observations: list[dict[str, Any]] = []
    for case in caller_history_hints["cases"]:
        handle = case["idempotency_key"]
        # Only a single SELECT via .get; do not inspect adapter or call any
        # method that changes a lease, state, effect ledger or queue.
        try:
            row = outbox.get(handle)
        except LookupError:
            observations.append({
                "idempotency_key": handle,
                "observed_local_state": "MISSING",
                "reason": "MISSING_LOCAL_INTENT_NOT_EVIDENCE_OF_NO_EFFECT",
                "local_regression_suspected": True,
            })
            continue
        except Exception:
            # Corrupt/unavailable local SQLite also fails closed. Deliberately
            # do not leak exception text, payloads, provider IDs or secrets.
            observations.append({
                "idempotency_key": handle,
                "observed_local_state": "UNREADABLE",
                "reason": "LOCAL_HISTORY_UNAVAILABLE_OR_CORRUPT",
                "local_regression_suspected": True,
            })
            continue
        if (type(row) is not dict
                or row.get("idempotency_key") != handle
                or type(row.get("state")) is not str
                or row["state"] not in STATES
                or type(row.get("attempts")) is not int
                or not 0 <= row["attempts"] <= 1_000_000
                or any(type(row.get(k)) is not str for k in (
                    "dispatch_started_at", "sent_at", "confirmed_at",
                    "effect_ref",
                ))
                or any(
                    row[k] != "" and (
                        len(row[k]) > 40 or UTC.fullmatch(row[k]) is None
                    )
                    for k in ("dispatch_started_at", "sent_at", "confirmed_at")
                )):
            observations.append({
                "idempotency_key": handle,
                "observed_local_state": "UNREADABLE",
                "reason": "LOCAL_HISTORY_SCHEMA_OR_VALUE_INVALID",
                "local_regression_suspected": True,
            })
            continue
        state = row["state"]
        # Even if both sides are local, a terminal intent becoming live or
        # changing to another terminal state is a regression symptom. Also
        # flag local dispatch/effect markers on supposedly reusable rows:
        # a recovered row with those markers MUST NOT be mistaken for safe.
        unexpected_terminal_change = (
            case["last_known_state"] in TERMINAL_LOCAL_STATES
            and state != case["last_known_state"]
        )
        local_effect_markers_on_reusable_state = (
            (
                state in ("PENDING", "RETRY")
                and any(row[k] != "" for k in (
                    "dispatch_started_at", "sent_at",
                    "confirmed_at", "effect_ref",
                ))
            )
            or (
                state == "CLAIMED"
                and any(row[k] != "" for k in (
                    "sent_at", "confirmed_at", "effect_ref",
                ))
            )
        )
        prior_dispatch = case["last_known_dispatch_started_at"]
        regression = (
            row["attempts"] < case["last_known_attempts"]
            or unexpected_terminal_change
            or local_effect_markers_on_reusable_state
            or (
                state in MAY_DISPATCH_LOCALLY
                and (
                    case["last_known_state"] in KNOWN_AFTER_DISPATCH
                    or prior_dispatch != ""
                )
            )
            or (prior_dispatch != "" and row["dispatch_started_at"] != prior_dispatch)
        )
        if regression:
            reason = "POSSIBLE_LOCAL_ROLLBACK_OR_STALE_RECLAIM"
        elif state in ("SENT", "UNCERTAIN"):
            reason = "UNKNOWN_EXTERNAL_EFFECT_REQUIRES_PROVIDER_RECONCILIATION"
        elif state == "CONFIRMED":
            reason = "LOCAL_CONFIRMED_NOT_EXTERNAL_PRODUCER_AUTHENTICATION"
        elif state == "BLOCKED_PRODUCER":
            reason = "UNENROLLED_PRODUCER_REMAINS_BLOCKED"
        else:
            reason = "LOCAL_RECORD_NOT_EXTERNAL_AUTHORITY"
        observations.append({
            "idempotency_key": handle,
            "observed_local_state": state,
            "reason": reason,
            "local_regression_suspected": regression,
        })
    return _base(observations, shape_valid=True)
