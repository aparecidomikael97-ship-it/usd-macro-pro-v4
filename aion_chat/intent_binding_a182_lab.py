"""A182 opt-in LAB binding guard. No external authority is established here.

The original decision, expected trust fingerprint and minimum custody ordinal
must be supplied BEFORE dispatch from retained enrollment fixtures. They must
never be learned from the candidate intent or a receipt. Replacing all of these
inputs defeats this guard: local hashes are not a trust root or anti-rollback.
"""
from hashlib import sha256
import json
from threading import Lock

from aion_chat.first_attempt_witness_lab import PinnedFirstAttemptWitnessLab
from aion_chat.signed_receipt_lab import canonical_bytes

# Only transport-generated identifiers/order are excluded. All authority,
# payload, scope, time and schema fields remain bound, including unknown fields.
_TECHNICAL = frozenset({"intent_ref", "decision_id", "idempotency_key", "aggregate_seq"})
_REQUIRED = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id", "action", "aggregate_key",
    "payload", "payload_digest", "policy_version", "authorization_ref",
    "valid_until", "created_at", "requires_reauth", "reauth_ref", "transaction_id",
    "authority_budget_ref", "risk_points", "capability_class", "grants_authority",
})


def semantic_bytes(decision):
    """Exact JSON identity, no unsafe inference about provider equivalence."""
    if type(decision) is not dict or not _REQUIRED <= decision.keys():
        raise ValueError("ORIGINAL_INTENT_BINDING_REQUIRED")
    if type(decision["payload"]) is not dict:
        raise ValueError("PAYLOAD_OBJECT_REQUIRED")
    # Match the existing Outbox payload encoding, without default=str/NaN.
    encoded = json.dumps(decision["payload"], sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    if sha256(encoded).hexdigest() != decision["payload_digest"]:
        raise ValueError("PAYLOAD_DIGEST_MISMATCH")
    return canonical_bytes({k: v for k, v in decision.items() if k not in _TECHNICAL})


def trust_fingerprint(*, issuer, key_id, public_key, revoked=False):
    if type(public_key) is not bytes or len(public_key) != 32 or type(revoked) is not bool:
        raise ValueError("INVALID_TRUST_CONFIGURATION")
    return sha256(canonical_bytes({
        "schema": "A182:LAB:TRUST_V1", "issuer": issuer, "key_id": key_id,
        "public_key_hex": public_key.hex(), "revoked": revoked,
    })).hexdigest()


class BoundFirstAttemptWitnessLab:
    """Opt-in first_attempt_guard, not a mandatory Worker security boundary.

    Exact original bytes are copied once; source dict mutation cannot rebind.
    A retained local ordinal catches older/missing custody relative to that
    fixture only. Restoring fixture AND custody or repinning both trust inputs
    is still possible. This object is not resistant to privileged Python code.
    """
    def __init__(self, *, original_decision, issuer, key_id, public_key,
                 expected_trust_sha256, minimum_sequence, checkpoint,
                 reserve, now, revoked=False):
        self._original = semantic_bytes(original_decision)
        actual = trust_fingerprint(issuer=issuer, key_id=key_id,
                                   public_key=public_key, revoked=revoked)
        if type(expected_trust_sha256) is not str or actual != expected_trust_sha256:
            raise ValueError("TRUST_CONFIGURATION_CHANGED_DENY")
        if type(minimum_sequence) is not int or minimum_sequence < 0:
            raise ValueError("RETAINED_CUSTODY_ORDINAL_REQUIRED")
        if not callable(checkpoint):
            raise TypeError("CUSTODY_CHECKPOINT_REQUIRED")
        self._minimum = minimum_sequence
        self._checkpoint = checkpoint
        self._lock = Lock()
        self._verifier = PinnedFirstAttemptWitnessLab(
            issuer=issuer, key_id=key_id, public_key=public_key, reserve=reserve,
            now=now, high_water=minimum_sequence, revoked=revoked)

    def __call__(self, intent):
        # Serializes this guard's in-memory verifier only. Multi-process
        # uniqueness remains the A181 custody transaction's responsibility.
        with self._lock:
            try:
                if type(intent) is not dict or semantic_bytes(intent.get("decision")) != self._original:
                    return False
                if intent.get("idempotency_key") != intent["decision"].get("idempotency_key"):
                    return False
                checkpoint = self._checkpoint()
                if type(checkpoint) is not dict or set(checkpoint) != {"high_water", "count"}:
                    return False
                ordinal, count = checkpoint["high_water"], checkpoint["count"]
                if (type(ordinal) is not int or type(count) is not int
                        or ordinal != count or ordinal < self._minimum):
                    return False
                return self._verifier(intent) is True
            except (KeyError, ValueError, TypeError, RuntimeError, OSError):
                return False

