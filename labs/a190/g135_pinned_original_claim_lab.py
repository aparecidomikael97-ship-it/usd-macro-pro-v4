"""G135: STRICT LAB-only identity-to-economic-payload admission seam.

Requires: retained original identity, retained immutable economic effect, and
A183 synthetic owner + identity-authority proof before the G134 local-process
custodian may stage one item in the *real* AION ExecutionOutbox.

EVERY dependency here is caller-supplied laboratory material. In particular,
the original, trusted keys, trust snapshot, floor, and clock are not externally
anchored. This is never an operational gate, never a credential authority,
and never permission to SEND or RETRY. An attacker able to replace the pinned
manifest AND keys can still self-re-enroll a fake original. HARD NO-GO.
"""
from copy import deepcopy
from hashlib import sha256
import re

from aion_chat.external_authority_a183_lab import ExternalAuthorityContractLab
from aion_chat.signed_receipt_lab import canonical_bytes


_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_EVENT = frozenset({"event_id", "original_sha256", "owner_id", "tenant_id", "workspace_id"})
_EFFECT = frozenset({"action", "kind", "target", "amount_minor", "currency"})


def _exact_event(event):
    return (
        type(event) is dict
        and set(event) == _EVENT
        and all(type(event[k]) is str and bool(_TOKEN.fullmatch(event[k]))
                for k in ("event_id", "owner_id", "tenant_id", "workspace_id"))
        and type(event.get("original_sha256")) is str
        and bool(_SHA.fullmatch(event["original_sha256"]))
    )


def _exact_effect(effect):
    return (
        type(effect) is dict
        and set(effect) == _EFFECT
        and all(type(v) is str and _TOKEN.fullmatch(v) for v in effect.values())
        and len(effect["amount_minor"]) <= 18
        and effect["amount_minor"].isdigit()
        and effect["amount_minor"].lstrip("0") != ""
        and effect["amount_minor"] == str(int(effect["amount_minor"]))
    )


class PinnedOriginalClaimLab:
    """Frozen LAB manifest and A183 two-role attestations for one synthetic intent."""

    def __init__(self, *, original_event, economic_effect, identity_verifier):
        if type(identity_verifier) is not ExternalAuthorityContractLab:
            raise ValueError("G135_EXACT_A183_LAB_VERIFIER_REQUIRED")
        if not _exact_event(original_event) or not _exact_effect(economic_effect):
            raise ValueError("G135_INVALID_RETAINED_MANIFEST")
        digest = sha256(canonical_bytes(economic_effect)).hexdigest()
        if original_event["original_sha256"] != digest:
            raise ValueError("G135_ORIGINAL_DIGEST_NOT_BOUND_TO_ECONOMIC_EFFECT")
        self._original = deepcopy(original_event)
        self._effect = deepcopy(economic_effect)
        self._verifier = identity_verifier
        self._consumed = False

    def inspect(self, *, claimed_event, proposed_economic_effect, evidence_query):
        """Return immutable original ONLY for exact claimed identity and signed proof.

        This is *permission to stage a synthetic fixture after G134 custody*,
        NOT permission to send, retry, attest externally, or operate a Worker.
        """
        if self._consumed or not _exact_event(claimed_event):
            return None
        if not _exact_effect(proposed_economic_effect):
            return None
        if claimed_event != self._original or proposed_economic_effect != self._effect:
            return None
        if sha256(canonical_bytes(proposed_economic_effect)).hexdigest() != self._original["original_sha256"]:
            return None
        receipt = self._verifier.admit("IDENTITY", deepcopy(self._original), evidence_query)
        if (
            type(receipt) is not dict or receipt.get("lab_verified") is not True
            or receipt.get("kind") != "IDENTITY"
            or receipt.get("permits_send") is not False
            or receipt.get("permits_retry") is not False
            or receipt.get("external_homologation") is not False
        ):
            return None
        self._consumed = True
        return deepcopy(self._original)


__all__ = ["PinnedOriginalClaimLab"]
