"""Executable ceremony specification, not a WebAuthn verifier or enrollment."""
from .contracts import (
    MODE, ContractError, binding, digest, digest_value, exact, integer,
    result, token, tokens,
)

INTENT_FIELDS = frozenset({"schema", "mode", "binding", "request_id", "nonce", "not_before", "expires_at"})
ASSERTION_FIELDS = frozenset({
    "schema", "mode", "binding_digest", "request_id", "nonce",
    "credential_id", "role", "decision", "user_presence", "user_verification",
    "origin", "rp_id", "issued_at", "evidence_kind",
})

def prepare_intent(value):
    exact(value, INTENT_FIELDS)
    if value["schema"] != "AION_OWNER_DEVICE_INTENT_V1" or value["mode"] != MODE:
        raise ContractError("SIMULATION_ONLY_SCHEMA_REQUIRED")
    bound = binding(value["binding"])
    if (not token(value["request_id"]) or not digest_value(value["nonce"])
            or value["nonce"] == "0" * 64
            or not integer(value["not_before"]) or not integer(value["expires_at"])
            or not 1 <= value["expires_at"] - value["not_before"] <= 180):
        raise ContractError("CHALLENGE_OR_VALIDITY_INVALID")
    return {**value, "binding": bound}

def review_ceremony(intent, assertion, *, expected_binding, now,
                    revoked_credentials=None, consumed_nonces=None):
    """Positive output means fixture consistency only; no real identity claim."""
    try:
        request = prepare_intent(intent)
        expected = binding(expected_binding)
        if request["binding"] != expected:
            raise ContractError("EXPECTED_SCOPE_MISMATCH")
        if not integer(now) or not request["not_before"] <= now < request["expires_at"]:
            raise ContractError("CONSENT_EXPIRED_OR_NOT_YET_VALID")
        # Missing revocation/replay state is UNKNOWN, never default empty.
        if not tokens(revoked_credentials, 128):
            raise ContractError("REVOCATION_STATE_UNAVAILABLE")
        if (type(consumed_nonces) is not list or len(consumed_nonces) > 128
                or not all(digest_value(x) for x in consumed_nonces)
                or len(set(consumed_nonces)) != len(consumed_nonces)):
            raise ContractError("NONCE_HISTORY_UNAVAILABLE")
        if expected["credential_id"] in revoked_credentials:
            raise ContractError("CREDENTIAL_REVOKED")
        if request["nonce"] in consumed_nonces:
            raise ContractError("NONCE_REPLAY")
        exact(assertion, ASSERTION_FIELDS)
        if (assertion["schema"] != "AION_OWNER_DEVICE_ASSERTION_FIXTURE_V1"
                or assertion["mode"] != MODE
                or assertion["evidence_kind"] != "SIMULATED_NOT_A_SIGNATURE"
                or assertion["role"] != "OWNER_CEREMONY_FIXTURE"
                or assertion["decision"] != "APPROVE_THIS_SIMULATION_ONLY"
                or assertion["user_presence"] is not True
                or assertion["user_verification"] is not True):
            raise ContractError("REAL_AUTHORITY_OR_OWNER_PROOF_NOT_ESTABLISHED")
        if any(assertion[k] != request[k] for k in ("request_id", "nonce")):
            raise ContractError("REQUEST_CHALLENGE_MISMATCH")
        if (assertion["binding_digest"] != digest(request["binding"])
                or assertion["credential_id"] != expected["credential_id"]):
            raise ContractError("ASSERTION_BINDING_MISMATCH")
        if (assertion["origin"] != "https://offline-fixture.invalid"
                or assertion["rp_id"] != "offline-fixture.invalid"):
            raise ContractError("RP_OR_ORIGIN_MISMATCH")
        if (not integer(assertion["issued_at"])
                or not request["not_before"] <= assertion["issued_at"] <= now):
            raise ContractError("ASSERTION_TIME_INVALID")
        return result("REFERENCE_CEREMONY_CONSISTENT_UNTRUSTED",
                      "OWNER_DEVICE_EXTERNAL_ENROLLMENT_STILL_REQUIRED",
                      simulation_binding_consistent=True)
    except (ContractError, TypeError, ValueError):
        # Never echo payload, identity, raw exception or credentials.
        return result("BLOCKED", "CEREMONY_CONTRACT_REJECTED", simulation_binding_consistent=False)
