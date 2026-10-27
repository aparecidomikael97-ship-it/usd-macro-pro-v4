"""G139 pre-enrolled original + distinct custody authority contract (LAB ONLY).

A mathematically valid first-reservation receipt is not meaningful without a
preexisting authenticated original. G139 requires *two distinct* synthetic
public keys and a signed original ENROLLMENT before the G138 custody challenge.
No auto-enroll, trust-on-first-use, root replacement or bootstrap-on-absence.

CRITICAL: the caller supplies BOTH retained roots and original. Thus a hostile
host may rewrite all of them and re-enroll a fake first operation. This is an
executable negative specification for future truly independent control plane,
NOT an independent source of truth or a production gate. No provider/SEND.
"""
from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aion_chat.signed_receipt_lab import canonical_bytes
from labs.a190.g138_signed_custody_wire_lab import (
    G138SignedCustodySessionLab, root_fingerprint_lab, valid_original_lab,
)


SCHEMA = "ATLASQUANT_AION_G139_ENROLLED_ORIGINAL_LAB_V1"
DOMAIN = b"ATLASQUANT:G139:SYNTHETIC_PRE_ENROLLMENT_V1\x00"
ENROLLMENT_FIELDS = frozenset({
    "schema", "enrollment_id", "issuer", "key_id", "enrollment_epoch",
    "enrollment_sequence", "issued_at", "custodian_root_sha256",
    "event_id", "original_sha256", "owner_id", "tenant_id", "workspace_id",
})
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def enrollment_root_lab(issuer: str, key_id: str, epoch: int, key: bytes) -> str:
    if not (type(issuer) is str and _TOKEN.fullmatch(issuer)
            and type(key_id) is str and _TOKEN.fullmatch(key_id)
            and type(epoch) is int and epoch >= 1
            and type(key) is bytes and len(key) == 32):
        raise ValueError("G139_INVALID_ENROLLMENT_PIN")
    return sha256(canonical_bytes({
        "issuer": issuer, "key_id": key_id, "epoch": epoch,
        "public_key_hex": key.hex(),
    })).hexdigest()


class G139OriginalEnrollmentBeforeCustodyLab:
    """Two pinned roles, one retained original, one-shot enrollment and custody."""

    def __init__(self, *, original: dict, enrollment_issuer: str,
                 enrollment_key_id: str, enrollment_epoch: int,
                 enrollment_public_key: bytes, expected_enrollment_root: str,
                 enrollment_floor: int, custody_authority_id: str,
                 custody_epoch: int, custody_public_key: bytes,
                 expected_custody_root: str, custody_floor: int,
                 now: datetime):
        if not valid_original_lab(original):
            raise ValueError("G139_RETAINED_ORIGINAL_REQUIRED")
        self._enrollment_root = enrollment_root_lab(
            enrollment_issuer, enrollment_key_id,
            enrollment_epoch, enrollment_public_key,
        )
        if type(expected_enrollment_root) is not str or expected_enrollment_root != self._enrollment_root:
            raise ValueError("G139_ENROLLMENT_ROOT_NOT_PREPINNED")
        custody_root = root_fingerprint_lab(
            custody_authority_id, custody_epoch, custody_public_key,
        )
        if type(expected_custody_root) is not str or expected_custody_root != custody_root:
            raise ValueError("G139_CUSTODY_ROOT_NOT_PREPINNED")
        if enrollment_public_key == custody_public_key:
            raise ValueError("G139_DISTINCT_CONTROL_AND_CUSTODY_KEYS_REQUIRED")
        if (type(enrollment_floor) is not int or enrollment_floor < 0
                or type(custody_floor) is not int or custody_floor < 0):
            raise ValueError("G139_EXPLICIT_RETAINED_FLOORS_REQUIRED")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("G139_TRUSTED_AWARE_CLOCK_REQUIRED")
        self._original = deepcopy(original)
        self._enrollment_issuer = enrollment_issuer
        self._enrollment_key_id = enrollment_key_id
        self._enrollment_epoch = enrollment_epoch
        self._enrollment_key = bytes(enrollment_public_key)
        self._custody_authority_id = custody_authority_id
        self._custody_epoch = custody_epoch
        self._custody_key = bytes(custody_public_key)
        self._custody_root = custody_root
        self._custody_floor = custody_floor
        self._enrollment_floor = enrollment_floor
        self._now = now.astimezone(timezone.utc)
        self._enrollment_attempted = False
        self._enrolled = False
        self._custody_session = None

    def admit_enrollment_once(self, envelope: object) -> bool:
        """No enrollment regeneration on failure; no TOFU; no implicit recovery."""
        if self._enrollment_attempted:
            return False
        self._enrollment_attempted = True
        try:
            if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
                return False
            payload, signature = envelope["payload"], envelope["signature"]
            if type(payload) is not dict or set(payload) != ENROLLMENT_FIELDS:
                return False
            if (payload["schema"] != SCHEMA
                    or payload["issuer"] != self._enrollment_issuer
                    or payload["key_id"] != self._enrollment_key_id
                    or type(payload["enrollment_epoch"]) is not int
                    or payload["enrollment_epoch"] != self._enrollment_epoch
                    or type(payload["enrollment_sequence"]) is not int
                    or payload["enrollment_sequence"] <= self._enrollment_floor
                    or payload["custodian_root_sha256"] != self._custody_root
                    or any(payload[k] != v for k, v in self._original.items())
                    or type(payload["enrollment_id"]) is not str
                    or not _TOKEN.fullmatch(payload["enrollment_id"])):
                return False
            if type(payload["issued_at"]) is not str:
                return False
            issued = datetime.fromisoformat(payload["issued_at"].replace("Z", "+00:00"))
            if issued.tzinfo is None:
                return False
            issued = issued.astimezone(timezone.utc)
            if not 0 <= (self._now - issued).total_seconds() <= 365 * 86400:
                return False
            if type(signature) is not str or len(signature) > 128:
                return False
            signed = base64.b64decode(signature, validate=True)
            if len(signed) != 64:
                return False
            Ed25519PublicKey.from_public_bytes(self._enrollment_key).verify(
                signed, DOMAIN + canonical_bytes(payload),
            )
            self._enrolled = True
            return True
        except (KeyError, ValueError, TypeError, OverflowError,
                binascii.Error, UnicodeError, InvalidSignature):
            return False

    def begin_custody_challenge(self) -> str | None:
        if not self._enrolled or self._custody_session is not None:
            return None
        self._custody_session = G138SignedCustodySessionLab(
            original=deepcopy(self._original),
            authority_id=self._custody_authority_id,
            authority_epoch=self._custody_epoch,
            pinned_public_key=self._custody_key,
            expected_root_sha256=self._custody_root,
            trusted_high_water=self._custody_floor,
            now=self._now,
        )
        return self._custody_session.challenge()

    def verify_custody_once(self, envelope: object) -> dict | None:
        if not self._enrolled or self._custody_session is None:
            return None
        response = self._custody_session.verify_once(envelope)
        if response is None or response.get("original") != self._original:
            return None
        return {
            "kind": "G139_TWO_SYNTHETIC_PROOFS_LAB_ONLY",
            "original": deepcopy(self._original),
            "custody_sequence": response["sequence"],
            "permits_local_test_staging": True,
            "permits_send": False,
            "permits_retry": False,
            "external_homologation": False,
        }


__all__ = [
    "SCHEMA", "DOMAIN", "ENROLLMENT_FIELDS",
    "enrollment_root_lab", "G139OriginalEnrollmentBeforeCustodyLab",
]
