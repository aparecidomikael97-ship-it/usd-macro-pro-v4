"""A295 LAB: two local volatile HMAC witnesses simulate an authority contract.

Two child PIDs each generate a private ephemeral key (via A294). This shows
required request bindings, quorum refusals and reset/partial-signature gaps.
Neither PID is an independently controlled owner, trusted authority, durable
custodian, or provider for real effects. The verifier is NOT wired to AION.
"""
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
import time

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from labs.a294_volatile_witness_sim_lab import (
    GENESIS, VolatileWitnessClient, sqlite_semantic_digest,
)

SCHEMA = "ATLASQUANT_AION_DUAL_LOCAL_AUTHORITY_CONTRACT_LAB_V1"
ACTION = "CHAT_CHECKPOINT_LAB"
SCOPE = {
    "owner_id": "owner-a295",
    "tenant_id": "tenant-a295",
    "workspace_id": "workspace-a295",
}
ENVELOPE_FIELDS = frozenset((
    "schema", "intent_id", "scope", "action", "payload_digest",
    "history_digest", "epoch", "sequence", "previous_head",
    "nonce", "expires_at",
))
HEX = frozenset("0123456789abcdef")


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "two_same_host_volatile_pids": True,
        "independent_real_owner_verified": False,
        "externally_durable_authority_epoch": False,
        "public_key_identity_attested": False,
        "provider_worker_deploy_orders_disabled": True,
        "no_new_paid_services": True,
        "zero_auto_resend": True,
        "can_authorize_real_effect": False,
        "p0_homologated": 0,
        "hard_no_go": True,
    }


def _valid_hex(value, size):
    return (
        type(value) is str and len(value) == size
        and all(c in HEX for c in value)
    )


def validate_intent(envelope, *, now=None):
    """Exact typed, bounded LAB-only envelope; no ambient default authority."""
    if type(envelope) is not dict or frozenset(envelope) != ENVELOPE_FIELDS:
        raise ValueError("INTENT_FIELDS_INVALID")
    if envelope["schema"] != SCHEMA or envelope["action"] != ACTION:
        raise ValueError("INTENT_ACTION_BLOCKED")
    for k in ("intent_id",):
        v = envelope[k]
        if type(v) is not str or not v.strip() or len(v) > 128:
            raise ValueError("INTENT_ID_INVALID")
    scope = envelope["scope"]
    if (
        type(scope) is not dict
        or frozenset(scope) != frozenset(SCOPE)
        or any(type(v) is not str or not v.strip() or len(v) > 128
               for v in scope.values())
    ):
        raise ValueError("INTENT_SCOPE_INVALID")
    for f in ("payload_digest", "history_digest"):
        if not _valid_hex(envelope[f], 64):
            raise ValueError("INTENT_DIGEST_INVALID")
    if not _valid_hex(envelope["epoch"], 32):
        raise ValueError("INTENT_EPOCH_INVALID")
    if not _valid_hex(envelope["nonce"], 32):
        raise ValueError("INTENT_NONCE_INVALID")
    if type(envelope["sequence"]) is not int or envelope["sequence"] < 1:
        raise ValueError("INTENT_SEQUENCE_INVALID")
    parent = envelope["previous_head"]
    if parent != GENESIS and not _valid_hex(parent, 64):
        raise ValueError("INTENT_PREVIOUS_HEAD_INVALID")
    expires = envelope["expires_at"]
    if type(expires) is not int or expires < 1:
        raise ValueError("INTENT_EXPIRY_INVALID")
    checked_at = int(time.time()) if now is None else now
    if type(checked_at) is not int:
        raise ValueError("INTENT_TIME_INVALID")
    if checked_at >= expires:
        raise ValueError("INTENT_EXPIRED")
    if expires > checked_at + 300:
        raise ValueError("INTENT_EXPIRY_TOO_FAR")
    return True


def intent_digest(envelope, *, now=None):
    validate_intent(envelope, now=now)
    body = json.dumps(
        envelope, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


class LocalDualSignerContract:
    """Cooperative model. Explicit bool approvals are NOT authenticated."""

    def __init__(self, *, epoch=None):
        self.epoch = secrets.token_hex(16) if epoch is None else epoch
        if not _valid_hex(self.epoch, 32):
            raise ValueError("INVALID_SIMULATED_EPOCH")
        self.owner = VolatileWitnessClient()
        try:
            self.custodian = VolatileWitnessClient()
        except BaseException:
            self.owner.close()
            raise
        self.sequence = 0
        self.head = GENESIS
        self.last_receipt = None
        self.nonces = set()
        self.semantic_effects = set()
        self.failed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.owner.close()
        self.custodian.close()

    def make_intent(
        self, *, payload_digest, history_digest,
        nonce=None, intent_id=None, expires_at=None, scope=None,
    ):
        return {
            "schema": SCHEMA,
            "intent_id": secrets.token_hex(16) if intent_id is None else intent_id,
            "scope": dict(SCOPE) if scope is None else scope,
            "action": ACTION,
            "payload_digest": payload_digest,
            "history_digest": history_digest,
            "epoch": self.epoch,
            "sequence": self.sequence + 1,
            "previous_head": self.head,
            "nonce": secrets.token_hex(16) if nonce is None else nonce,
            "expires_at": (
                int(time.time()) + 300 if expires_at is None else expires_at
            ),
        }

    @staticmethod
    def _refuse(reason):
        return {"ok": False, "reason": reason}

    def _semantic_key(self, envelope):
        return (
            json.dumps(envelope["scope"], sort_keys=True),
            envelope["action"], envelope["payload_digest"],
            envelope["history_digest"],
        )

    def approve(self, envelope, *, owner_approved=False, custodian_approved=False):
        """Both local simulation switches must be explicit and True."""
        if self.failed:
            return self._refuse("PARTIAL_SIGNATURE_UNKNOWN_STOP")
        if type(owner_approved) is not bool or type(custodian_approved) is not bool:
            return self._refuse("APPROVAL_FLAG_INVALID")
        if not owner_approved or not custodian_approved:
            return self._refuse("SIMULATED_DUAL_APPROVAL_MISSING")
        try:
            digest = intent_digest(envelope)
        except ValueError as exc:
            return self._refuse(str(exc))
        if envelope["epoch"] != self.epoch:
            return self._refuse("EPOCH_MISMATCH")
        if envelope["sequence"] != self.sequence + 1:
            return self._refuse("SEQUENCE_NOT_MONOTONIC")
        if envelope["previous_head"] != self.head:
            return self._refuse("PREVIOUS_HEAD_MISMATCH")
        if envelope["nonce"] in self.nonces:
            return self._refuse("NONCE_REPLAY")
        semantic = self._semantic_key(envelope)
        if semantic in self.semantic_effects:
            return self._refuse("SEMANTIC_EFFECT_REPLAY")
        left_previous = (
            self.last_receipt["owner"]["head"]
            if self.last_receipt else GENESIS
        )
        right_previous = (
            self.last_receipt["custodian"]["head"]
            if self.last_receipt else GENESIS
        )
        # These two separate local PIDs have no verified external identity.
        left = self.owner.call(
            "anchor", seq=self.sequence + 1,
            digest=digest, previous=left_previous
        )
        if not left["ok"]:
            self.failed = True
            return self._refuse("PARTIAL_SIGNATURE_UNKNOWN_STOP")
        right = self.custodian.call(
            "anchor", seq=self.sequence + 1,
            digest=digest, previous=right_previous
        )
        if not right["ok"]:
            # Owner may already have signed. No auto retry or 'known rollback'.
            self.failed = True
            return self._refuse("PARTIAL_SIGNATURE_UNKNOWN_STOP")
        owner_receipt = left["receipt"]
        custodian_receipt = right["receipt"]
        head = hashlib.sha256(json.dumps(
            [self.head, digest, owner_receipt["head"],
             custodian_receipt["head"]],
            separators=(",", ":"),
        ).encode()).hexdigest()
        receipt = {
            "epoch": self.epoch,
            "sequence": self.sequence + 1,
            "digest": digest,
            "previous_head": self.head,
            "owner": owner_receipt,
            "custodian": custodian_receipt,
            "joint_head": head,
        }
        self.sequence += 1
        self.head = head
        self.last_receipt = receipt
        self.nonces.add(envelope["nonce"])
        self.semantic_effects.add(semantic)
        return {"ok": True, "reason": "DUAL_SIMULATED_ACK", "receipt": receipt}

    def verify(self, envelope, receipt):
        if self.failed:
            return self._refuse("PARTIAL_SIGNATURE_UNKNOWN_STOP")
        try:
            digest = intent_digest(envelope)
        except ValueError as exc:
            return self._refuse(str(exc))
        if envelope["epoch"] != self.epoch:
            return self._refuse("EPOCH_MISMATCH")
        if type(receipt) is not dict:
            return self._refuse("RECEIPT_INVALID")
        if receipt.get("digest") != digest:
            return self._refuse("INTENT_CHANGED")
        if receipt != self.last_receipt:
            return self._refuse("STALE_OR_REPLACED_RECEIPT")
        left = self.owner.call(
            "verify", digest=digest, receipt=receipt["owner"]
        )
        right = self.custodian.call(
            "verify", digest=digest, receipt=receipt["custodian"]
        )
        if not left["ok"] or not right["ok"]:
            return self._refuse("LOCAL_QUORUM_UNAVAILABLE_OR_INVALID")
        return {"ok": True, "reason": "SIMULATED_QUORUM_MATCH"}


def _sample_history_digest():
    with tempfile.TemporaryDirectory(prefix="a295-history-") as raw:
        path = Path(raw) / "synthetic.db"
        store = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            store.create_conversation(
                Scope(**SCOPE), "a295-only-synthetic"
            )
        finally:
            store.close()
        return sqlite_semantic_digest(path)


def probe_dual_contract_tamper_replay():
    result = _base()
    history = _sample_history_digest()
    with LocalDualSignerContract() as pair:
        intent = pair.make_intent(
            payload_digest="a" * 64, history_digest=history
        )
        missing_approval = pair.approve(
            intent, owner_approved=True, custodian_approved=False
        )
        initial = pair.approve(
            intent, owner_approved=True, custodian_approved=True
        )
        receipt1 = initial["receipt"]
        verified = pair.verify(intent, receipt1)
        tampered = dict(intent, payload_digest="b" * 64)
        tamper_result = pair.verify(tampered, receipt1)
        replay = pair.approve(
            intent, owner_approved=True, custodian_approved=True
        )
        reused_nonce = pair.make_intent(
            payload_digest="c" * 64, history_digest=history,
            nonce=intent["nonce"],
        )
        nonce_result = pair.approve(
            reused_nonce, owner_approved=True, custodian_approved=True
        )
        same_semantic = pair.make_intent(
            payload_digest=intent["payload_digest"], history_digest=history,
        )
        semantic_result = pair.approve(
            same_semantic, owner_approved=True, custodian_approved=True
        )
        wrong_parent = pair.make_intent(
            payload_digest="d" * 64, history_digest=history
        )
        wrong_parent["previous_head"] = GENESIS
        parent_result = pair.approve(
            wrong_parent, owner_approved=True, custodian_approved=True
        )
        expired = pair.make_intent(
            payload_digest="e" * 64, history_digest=history,
            expires_at=int(time.time()) - 1,
        )
        expiry_result = pair.approve(
            expired, owner_approved=True, custodian_approved=True
        )
        second = pair.make_intent(
            payload_digest="f" * 64, history_digest=history
        )
        next_ack = pair.approve(
            second, owner_approved=True, custodian_approved=True
        )
        verified_second = pair.verify(second, next_ack["receipt"])
        old_now = pair.verify(intent, receipt1)
        result.update({
            "single_approval_denied": (
                missing_approval["reason"] == "SIMULATED_DUAL_APPROVAL_MISSING"
            ),
            "first_quorum_accepted": initial["ok"],
            "first_quorum_verified": verified["ok"],
            "changed_payload_denied": (
                tamper_result["reason"] == "INTENT_CHANGED"
            ),
            "replayed_intent_denied": (
                replay["reason"] == "SEQUENCE_NOT_MONOTONIC"
            ),
            "nonce_reuse_denied": nonce_result["reason"] == "NONCE_REPLAY",
            "semantic_duplicate_denied": (
                semantic_result["reason"] == "SEMANTIC_EFFECT_REPLAY"
            ),
            "wrong_parent_denied": (
                parent_result["reason"] == "PREVIOUS_HEAD_MISMATCH"
            ),
            "expired_intent_denied": (
                expiry_result["reason"] == "INTENT_EXPIRED"
            ),
            "second_quorum_accepted": next_ack["ok"],
            "second_quorum_verified": verified_second["ok"],
            "old_receipt_stale": (
                old_now["reason"] == "STALE_OR_REPLACED_RECEIPT"
            ),
        })
    return result


def probe_partial_signer_failure():
    result = _base()
    with LocalDualSignerContract() as pair:
        intent = pair.make_intent(
            payload_digest="1" * 64, history_digest="2" * 64
        )
        pair.custodian._child.kill()
        pair.custodian._child.wait(timeout=5)
        partial = pair.approve(
            intent, owner_approved=True, custodian_approved=True
        )
        # Observe partial state via child refusal of another seq-1 anchor.
        owner_repeat = pair.owner.call(
            "anchor", seq=1, digest=intent_digest(intent), previous=GENESIS
        )
        another = pair.approve(
            intent, owner_approved=True, custodian_approved=True
        )
        result.update({
            "first_partial_denied": (
                partial["reason"] == "PARTIAL_SIGNATURE_UNKNOWN_STOP"
            ),
            "owner_side_effect_may_have_occurred": (
                owner_repeat["reason"] == "NON_MONOTONIC_SEQUENCE"
            ),
            "further_requests_sticky_denied": (
                another["reason"] == "PARTIAL_SIGNATURE_UNKNOWN_STOP"
            ),
            "no_known_rollback_of_owner_signature": True,
        })
    return result


def probe_untrusted_approval_flag():
    """A caller can falsely toggle both Python booleans: no real identity."""
    result = _base()
    with LocalDualSignerContract() as pair:
        fake_scope = dict(SCOPE, owner_id="self-claimed-unauthorized-owner")
        intent = pair.make_intent(
            payload_digest="7" * 64, history_digest="8" * 64,
            scope=fake_scope,
        )
        approved = pair.approve(
            intent, owner_approved=True, custodian_approved=True
        )
        proof = pair.verify(intent, approved.get("receipt"))
        result.update({
            "structural_envelope_valid": validate_intent(intent),
            "fake_owner_scope_accepted_by_local_flags": approved["ok"],
            "fake_owner_verifies_with_same_host_children": proof["ok"],
            "real_owner_identity_not_authenticated": True,
        })
    return result


def probe_same_host_reset_bootstrap():
    """Both local signers may be restarted and re-sign the identical effect."""
    result = _base()
    history = _sample_history_digest()
    epoch = secrets.token_hex(16)
    with LocalDualSignerContract(epoch=epoch) as old_pair:
        intent = old_pair.make_intent(
            payload_digest="c" * 64, history_digest=history
        )
        first = old_pair.approve(
            intent, owner_approved=True, custodian_approved=True
        )
        first_receipt = first["receipt"]
    with LocalDualSignerContract(epoch=epoch) as reset_pair:
        second = reset_pair.approve(
            intent, owner_approved=True, custodian_approved=True
        )
        second_receipt = second["receipt"]
        forged_continuity = reset_pair.verify(intent, first_receipt)
        newly_bootstrapped = reset_pair.verify(intent, second_receipt)
        result.update({
            "original_simulated_quorum_accepted": first["ok"],
            "same_intent_reaccepted_after_host_reset": second["ok"],
            "new_keys_reject_old_receipt": (
                forged_continuity["reason"] == "STALE_OR_REPLACED_RECEIPT"
            ),
            "newly_reset_signers_approve_duplicate": newly_bootstrapped["ok"],
            "old_and_new_receipts_differ": first_receipt != second_receipt,
            "host_reset_breaks_independent_authority": True,
        })
    return result


__all__ = [
    "SCHEMA", "ACTION", "SCOPE", "ENVELOPE_FIELDS",
    "validate_intent", "intent_digest", "LocalDualSignerContract",
    "probe_dual_contract_tamper_replay", "probe_partial_signer_failure",
    "probe_same_host_reset_bootstrap", "probe_untrusted_approval_flag",
]
