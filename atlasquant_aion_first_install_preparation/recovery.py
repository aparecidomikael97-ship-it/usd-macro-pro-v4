"""Readback/recovery contract. Actual CAS/journal remain in existing references."""
from .contracts import MODE, ContractError, binding, digest, digest_value, exact, integer, result, token, tokens

HEAD_FIELDS = frozenset({
    "mode", "domain_id", "credential_id", "binding_digest", "operation_id",
    "request_digest", "epoch", "sequence", "snapshot_digest", "previous_digest",
    "nonce", "observed_at", "outcome", "causal_effect_digest",
})
FLOOR_FIELDS = frozenset({"epoch", "sequence", "snapshot_digest"})

def review_recovery(heads, *, expected_binding, operation_id, request_digest,
                    nonce, floor, now, revoked_credentials=None, consumed_nonces=None):
    """Two supplied heads are simulation consistency, never independent custody."""
    try:
        scope = digest(binding(expected_binding))
        exact(floor, FLOOR_FIELDS)
        if (not integer(floor["epoch"], 1) or not integer(floor["sequence"], 1)
                or not digest_value(floor["snapshot_digest"]) or not integer(now)
                or not token(operation_id) or not digest_value(request_digest)
                or not digest_value(nonce) or nonce == "0"*64):
            raise ContractError("RECOVERY_EXPECTATION_INVALID")
        if not tokens(revoked_credentials, 128):
            raise ContractError("REVOCATION_STATE_UNKNOWN")
        if (type(consumed_nonces) is not list or len(consumed_nonces) > 128
                or not all(digest_value(x) for x in consumed_nonces)
                or len(set(consumed_nonces)) != len(consumed_nonces) or nonce in consumed_nonces):
            raise ContractError("NONCE_HISTORY_UNKNOWN_OR_REPLAY")
        if type(heads) is not list or len(heads) != 2:
            raise ContractError("DUAL_HEAD_ABSENT")
        for head in heads:
            exact(head, HEAD_FIELDS)
            if (head["mode"] != MODE or not token(head["domain_id"])
                    or not token(head["credential_id"]) or head["credential_id"] in revoked_credentials):
                raise ContractError("HEAD_CREDENTIAL_UNTRUSTED_OR_REVOKED")
            if (head["binding_digest"] != scope or head["operation_id"] != operation_id
                    or head["request_digest"] != request_digest or head["nonce"] != nonce):
                raise ContractError("READBACK_SCOPE_OR_CAUSAL_BINDING_MISMATCH")
            if (not integer(head["observed_at"]) or not 0 <= now-head["observed_at"] < 60
                    or not integer(head["epoch"], 1) or not integer(head["sequence"], 1)):
                raise ContractError("HEAD_STALE_OR_COUNTER_INVALID")
            if head["epoch"] != floor["epoch"] or head["sequence"] < floor["sequence"]:
                raise ContractError("ROLLBACK_OR_UNPROVEN_EPOCH_TRANSITION")
            if head["sequence"] > floor["sequence"]+1:
                raise ContractError("CHAIN_GAP_REQUIRES_FULL_HISTORY")
            if not all(digest_value(head[k]) for k in ("snapshot_digest", "previous_digest", "causal_effect_digest")):
                raise ContractError("HEAD_DIGEST_INVALID")
            if head["sequence"] == floor["sequence"] and head["snapshot_digest"] != floor["snapshot_digest"]:
                raise ContractError("FORK_AT_FLOOR")
            if head["sequence"] == floor["sequence"]+1 and head["previous_digest"] != floor["snapshot_digest"]:
                raise ContractError("UNBOUND_NEXT_CHECKPOINT")
            if head["outcome"] != "SIMULATED_CAUSAL_EFFECT_FOUND":
                raise ContractError("UNKNOWN_OUTCOME_NOT_RECONCILED")
        a, b = heads
        if a["domain_id"] == b["domain_id"] or a["credential_id"] == b["credential_id"]:
            raise ContractError("SELF_REFERRED_WITNESS")
        for key in HEAD_FIELDS - {"domain_id", "credential_id", "observed_at"}:
            if a[key] != b[key]:
                raise ContractError("CROSS_DOMAIN_PARTIAL_COMMIT_OR_FORK")
        return result("REFERENCE_CAUSAL_MATCH_UNTRUSTED", "REAL_WITNESS_CUSTODY_AND_LATEST_HEAD_UNPROVEN",
                      simulation_causal_match=True, needs_independent_reconciliation=True)
    except (ContractError, TypeError, ValueError):
        return result("BLOCKED", "RECOVERY_CONTRACT_REJECTED", simulation_causal_match=False,
                      needs_independent_reconciliation=True)
