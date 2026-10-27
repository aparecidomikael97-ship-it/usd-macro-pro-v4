"""G138 strict signed custody receipt WIRE contract — LAB ONLY, NOT AUTHORITY.

A real trusted custodian is NOT built here.  A test subprocess signs fixtures
using ephemeral caller-owned keys.  Successful mathematical verification
does not prove durable, off-host, independent reservation, genuine HUMAN_OWNER
or original enrollment.  Caller-pinned keys, clock and high-water can be
replaced/rolled back.  No production interface, Worker or SEND.

Challenge is generated independently inside a one-shot verifier; receipt MUST
bind immutable claimed original, economic digest, epoch, sequence, trust root,
timestamps and fixed issuer.  Unknown/lost-ACK outcome is UNCERTAIN without
automatic resend.
"""
from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import re
import secrets

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from aion_chat.signed_receipt_lab import canonical_bytes


SCHEMA = "ATLASQUANT_AION_G138_SYNTHETIC_CUSTODY_WIRE_LAB_V1"
DOMAIN = b"ATLASQUANT:G138:SYNTHETIC_CUSTODY_RECEIPT_V1\0"
STATUS = "FIRST_ATTEMPT_RESERVED_LAB_ONLY"
ORIGINAL_FIELDS = frozenset({
    "event_id", "original_sha256", "owner_id", "tenant_id", "workspace_id",
})
PAYLOAD_FIELDS = ORIGINAL_FIELDS | frozenset({
    "schema", "status", "authority_id", "authority_epoch", "sequence",
    "challenge", "root_sha256", "issued_at", "expires_at",
})
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CHALLENGE = re.compile(r"[0-9a-f]{64}\Z")


def root_fingerprint_lab(authority_id: str, authority_epoch: int,
                         raw_public_key: bytes) -> str:
    if not (type(authority_id) is str and _TOKEN.fullmatch(authority_id)
            and type(authority_epoch) is int and authority_epoch >= 1
            and type(raw_public_key) is bytes and len(raw_public_key) == 32):
        raise ValueError("G138_INVALID_SYNTHETIC_ROOT")
    return sha256(canonical_bytes({
        "authority_id": authority_id,
        "authority_epoch": authority_epoch,
        "public_key_hex": raw_public_key.hex(),
    })).hexdigest()


def valid_original_lab(original: object) -> bool:
    return (
        type(original) is dict and set(original) == ORIGINAL_FIELDS
        and all(type(original[k]) is str and bool(_TOKEN.fullmatch(original[k]))
                for k in ("event_id", "owner_id", "tenant_id", "workspace_id"))
        and type(original["original_sha256"]) is str
        and bool(_SHA256.fullmatch(original["original_sha256"]))
    )


class G138SignedCustodySessionLab:
    """Synthetic custodian response verifier; NOT a real trust anchor."""

    def __init__(self, *, original: dict, authority_id: str,
                 authority_epoch: int, pinned_public_key: bytes,
                 expected_root_sha256: str, trusted_high_water: int,
                 now: datetime):
        if not valid_original_lab(original):
            raise ValueError("G138_INVALID_RETAINED_ORIGINAL")
        root = root_fingerprint_lab(authority_id, authority_epoch, pinned_public_key)
        if type(expected_root_sha256) is not str or expected_root_sha256 != root:
            raise ValueError("G138_ROOT_NOT_RETAINED")
        if type(trusted_high_water) is not int or trusted_high_water < 0:
            raise ValueError("G138_TRUSTED_SEQUENCE_FLOOR_REQUIRED")
        if type(now) is not datetime or now.tzinfo is None:
            raise ValueError("G138_AWARE_INDEPENDENT_CLOCK_REQUIRED_LAB_FIXTURE")
        self._original = deepcopy(original)
        self._authority_id = authority_id
        self._epoch = authority_epoch
        self._public_key = bytes(pinned_public_key)
        self._root = root
        self._high = trusted_high_water
        self._now = now.astimezone(timezone.utc)
        self._challenge = None
        self._attempted = False

    def challenge(self) -> str:
        if self._challenge is not None or self._attempted:
            raise RuntimeError("G138_SINGLE_CHALLENGE_ONLY")
        self._challenge = secrets.token_hex(32)
        return self._challenge

    def verify_once(self, response: object) -> dict | None:
        """No second verification after an inconclusive/malformed response.

        This local one-shot property survives neither app process restart nor
        restoration of the caller-supplied monotonic floor.
        """
        if self._challenge is None or self._attempted:
            return None
        self._attempted = True
        try:
            if type(response) is not dict or set(response) != {"payload", "signature"}:
                return None
            payload, signature = response["payload"], response["signature"]
            if type(payload) is not dict or set(payload) != PAYLOAD_FIELDS:
                return None
            if (payload["schema"] != SCHEMA or payload["status"] != STATUS
                    or payload["authority_id"] != self._authority_id
                    or type(payload["authority_epoch"]) is not int
                    or payload["authority_epoch"] != self._epoch
                    or payload["challenge"] != self._challenge
                    or payload["root_sha256"] != self._root
                    or any(payload[k] != v for k, v in self._original.items())):
                return None
            if type(payload["sequence"]) is not int or payload["sequence"] <= self._high:
                return None
            if type(payload["issued_at"]) is not str or type(payload["expires_at"]) is not str:
                return None
            issued = datetime.fromisoformat(payload["issued_at"].replace("Z", "+00:00"))
            expires = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
            if issued.tzinfo is None or expires.tzinfo is None:
                return None
            issued, expires = issued.astimezone(timezone.utc), expires.astimezone(timezone.utc)
            duration = (expires - issued).total_seconds()
            if not (0 < duration <= 60 and issued <= self._now <= expires):
                return None
            if type(signature) is not str or len(signature) > 128:
                return None
            signed = base64.b64decode(signature, validate=True)
            if len(signed) != 64:
                return None
            Ed25519PublicKey.from_public_bytes(self._public_key).verify(
                signed, DOMAIN + canonical_bytes(payload)
            )
            self._high = payload["sequence"]
            return {
                "lab_verified": True,
                "kind": "SYNTHETIC_FIRST_CUSTODY_ACK",
                "original": deepcopy(self._original),
                "sequence": self._high,
                "permits_stage_in_laboratory": True,
                "permits_send": False,
                "permits_retry": False,
                "external_homologation": False,
            }
        except (KeyError, ValueError, TypeError, OverflowError, binascii.Error,
                UnicodeError, InvalidSignature):
            return None


__all__ = [
    "SCHEMA", "DOMAIN", "STATUS", "PAYLOAD_FIELDS",
    "root_fingerprint_lab", "G138SignedCustodySessionLab",
]
