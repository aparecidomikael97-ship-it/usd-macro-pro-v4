"""A75 LAB: inspect caller-supplied F1/T1 witness-shaped data, NEVER authorize.

This is a deliberately non-authoritative *intake/diagnostic* boundary.
It does not read GitHub, verify signed custody, enroll keys, verify a remote
monotonic high-water mark, consume a nonce, or activate a worker.
A locally consistent claim is NOT evidence of an independently held witness.
"""
from __future__ import annotations

from datetime import datetime, timezone
import base64
import binascii
import re
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_F1_T1_UNTRUSTED_WITNESS_CLAIM_LAB_V1"
_REQUIRED = frozenset({
    "schema", "repo_id", "owner_id", "branch", "path", "tenant_id",
    "workspace_id", "head_sha", "checkpoint_blob_sha",
    "checkpoint_digest", "epoch", "sequence", "previous_sequence",
    "previous_head_sha", "nonce", "issued_at", "expires_at",
    "witness_issuer", "key_id", "signature_b64",
})
_SCOPE = ("repo_id", "owner_id", "branch", "path", "tenant_id", "workspace_id")
_GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
_NONCE = re.compile(r"[A-Za-z0-9_-]{24,128}\Z")
_HEX_LIMIT = 2**63 - 1


def _time(value: Any) -> datetime | None:
    if type(value) is not str or not _UTC.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError:
        return None


def _str(value: Any, maximum: int = 256) -> bool:
    return type(value) is str and 0 < len(value) <= maximum and value == value.strip()


def _uint(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= _HEX_LIMIT


def _canonical_signature_b64(value: Any) -> bool:
    """Strict RFC4648 canonical Base64 syntax ONLY; never signature trust.

    Signature algorithm/key/issuer is deliberately not inferred. There are
    no key reads, cryptographic signature verification or authority grants.
    """
    if not _str(value):
        return False
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError):
        return False
    # The existing maximum text size bounds decoded data to <= 192 bytes.
    # Non-empty payload and round-trip reject empty and non-canonical pad bits.
    return bool(raw) and base64.b64encode(raw).decode("ascii") == value


def inspect_untrusted_witness_claim(
    claim: Any,
    *,
    expected_scope: Any,
    now_ts: str,
    observed_snapshot: Any = None,
    locally_known_high_water: Any = None,
) -> dict[str, Any]:
    """Deny-only offline diagnostic. Every return keeps operational authority false.

    ALL inputs, including expected_scope, observed_snapshot and high_water, can
    be supplied by the caller: their apparent consistency is not custody.
    This function is intentionally incapable of returning READY or VERIFIED.
    """
    errors: list[str] = []
    data: dict[str, Any] = {}
    if not isinstance(claim, Mapping):
        errors.append("WITNESS_CLAIM_NOT_MAPPING")
    else:
        try:
            data = dict(claim)
        except Exception:
            errors.append("WITNESS_CLAIM_NOT_READABLE")
        else:
            if set(data) != _REQUIRED:
                errors.append("WITNESS_CLAIM_SHAPE_MISMATCH")

    if isinstance(expected_scope, Mapping):
        try:
            expected = dict(expected_scope)
        except Exception:
            expected = {}
    else:
        expected = {}
    if set(expected) != set(_SCOPE):
        errors.append("EXPECTED_SCOPE_INCOMPLETE_OR_UNTRUSTED")
    else:
        if not _uint(expected["repo_id"], 1) or not _uint(expected["owner_id"], 1):
            errors.append("EXPECTED_SCOPE_ID_INVALID")
        for key in ("branch", "path", "tenant_id", "workspace_id"):
            if not _str(expected[key]):
                errors.append("EXPECTED_SCOPE_TEXT_INVALID")

    now = _time(now_ts)
    if now is None:
        errors.append("CLOCK_INVALID")

    if set(data) == _REQUIRED:
        if data["schema"] != SCHEMA:
            errors.append("WITNESS_SCHEMA_INVALID")
        for key in ("repo_id", "owner_id"):
            if not _uint(data[key], 1):
                errors.append(f"WITNESS_ID_INVALID:{key}")
        for key in ("branch", "path", "tenant_id", "workspace_id",
                    "witness_issuer", "key_id", "signature_b64"):
            if not _str(data[key]):
                errors.append(f"WITNESS_TEXT_INVALID:{key}")
        if not _canonical_signature_b64(data["signature_b64"]):
            errors.append("WITNESS_SIGNATURE_BASE64_INVALID")
        for key in ("head_sha", "checkpoint_blob_sha"):
            if type(data[key]) is not str or not _GIT_SHA.fullmatch(data[key]):
                errors.append(f"WITNESS_GIT_SHA_INVALID:{key}")
        if type(data["checkpoint_digest"]) is not str or not _DIGEST.fullmatch(data["checkpoint_digest"]):
            errors.append("WITNESS_DIGEST_INVALID")
        for key, minimum in (("epoch", 1), ("sequence", 1), ("previous_sequence", 0)):
            if not _uint(data[key], minimum):
                errors.append(f"WITNESS_SEQUENCE_INVALID:{key}")
        if _uint(data["sequence"], 1) and _uint(data["previous_sequence"]):
            if data["sequence"] != data["previous_sequence"] + 1:
                errors.append("WITNESS_SEQUENCE_GAP_OR_ROLLBACK")
        if not _str(data["nonce"], 128) or not _NONCE.fullmatch(data["nonce"]):
            errors.append("WITNESS_NONCE_INVALID")
        if _uint(data["previous_sequence"]):
            expected_prev = "GENESIS" if data["previous_sequence"] == 0 else "SHA"
            prev_sha = data["previous_head_sha"]
            if expected_prev == "GENESIS":
                if prev_sha != "GENESIS":
                    errors.append("WITNESS_GENESIS_CHAIN_INVALID")
            elif type(prev_sha) is not str or not _GIT_SHA.fullmatch(prev_sha):
                errors.append("WITNESS_PREVIOUS_HEAD_INVALID")
        issued, expires = _time(data["issued_at"]), _time(data["expires_at"])
        if now is None or issued is None or expires is None:
            errors.append("WITNESS_TIME_INVALID")
        elif issued > now or expires <= now or expires <= issued:
            errors.append("WITNESS_EXPIRED_OR_FROM_FUTURE")
        elif (now - issued).total_seconds() > 300 or (expires - issued).total_seconds() > 300:
            errors.append("WITNESS_WINDOW_TOO_OLD_OR_LONG")
        if set(expected) == set(_SCOPE):
            for field in _SCOPE:
                if data[field] != expected[field]:
                    errors.append(f"WITNESS_SCOPE_MISMATCH:{field}")

        # This is ONLY a consistency comparison of two caller-controlled
        # mappings. It is not a fresh authenticated GitHub GET.
        if observed_snapshot is not None:
            if (not isinstance(observed_snapshot, Mapping)
                    or set(observed_snapshot) != {"head_sha", "checkpoint_blob_sha"}):
                errors.append("OBSERVED_SNAPSHOT_SHAPE_INVALID")
            else:
                for field in ("head_sha", "checkpoint_blob_sha"):
                    if data[field] != observed_snapshot[field]:
                        errors.append(f"WITNESS_SNAPSHOT_MISMATCH:{field}")
        if locally_known_high_water is not None:
            if not _uint(locally_known_high_water):
                errors.append("LOCAL_HIGH_WATER_INVALID")
            elif _uint(data["sequence"], 1) and data["sequence"] <= locally_known_high_water:
                errors.append("LOCAL_REPLAY_OR_ROLLBACK_SUSPECTED")

    # Absolutely no path to operational trust, even if all fields are internally
    # consistent, the issuer looks official, or a caller alleges signature OK.
    blockers = ["INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED",
                "EXTERNAL_CUSTODY_AND_FRESHNESS_UNPROVEN"] + errors
    return {
        "schema": "ATLASQUANT_AION_F1_T1_INTAKE_DIAGNOSTIC_LAB_V1",
        "status": "BLOCKED",
        "reason": "INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED",
        "blockers": blockers,
        "local_format_consistent": not errors,
        "claim_signature_verified": False,
        "external_custody_verified": False,
        "fresh_github_head_independently_verified": False,
        "monotonic_high_water_independently_verified": False,
        "replay_prevented_independently": False,
        "source_authenticity_verified": False,
        "independent_witness_verified": False,
        "external_activation_allowed": False,
        "worker_execution_allowed": False,
        "runtime_modified": False,
        "network_called": False,
    }
