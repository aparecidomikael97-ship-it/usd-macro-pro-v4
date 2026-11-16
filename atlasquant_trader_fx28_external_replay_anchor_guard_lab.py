"""LAB-only external-anchor comparison for FX28 Radar replay rollback.

A local SQLite replay database may be restored to an old but internally
well-formed copy. Its current high-water counter is NOT sufficient proof
against a backup rollback. The proposed solution needs an independently
durable, monotonic authority that signs a FRESH nonce challenge and its
highest recorded sequence + last envelope digest, with an anchor key
separate from the envelope HMAC key.

THIS FILE DOES NOT PROVIDE THE EXTERNAL AUTHORITY OR ISSUE TRUSTED KEYS.
Its checkpoint signer is a PURE SYNTHETIC TEST HELPER only. Neither it nor
the verifier reads the network, contacts MT5, provisions credentials,
grants trades, advances local/external sequences, or deploys services.
A matched checkpoint is still LAB / NO-GO and cannot unlock the Radar.

Replay or rollback of BOTH databases, clock spoofing, stolen anchor key,
restoring anchor backups, or a compromised anchor issuer cannot be
excluded without independently operated infrastructure and attestation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
import hmac
import json
import re
import sqlite3

from atlasquant_trader_fx28_durable_replay_floor_sqlite_lab import (
    TABLE, APP_ID, _conn_ready,
)
from atlasquant_trader_fx28_signed_status_envelope_lab import (
    AUDIENCE, ISSUER, KEY_ID,
)

SCHEMA = "ATLASQUANT_FX28_EXTERNAL_REPLAY_ANCHOR_PROBE_LAB_V1"
ANCHOR_AUDIENCE = "ATLASQUANT_FX28_PRIVATE_REPLAY_ANCHOR_PROBE_LAB"
ANCHOR_ISSUER = "INDEPENDENT_MONOTONIC_SERVICE_NOT_CONFIGURED"
ANCHOR_KEY_ID = "fx28-anchor-probe-not-installed-v1"
TTL_SECONDS = 120
FUTURE_CLOCK_SKEW_SECONDS = 15
MAX_BYTES = 1400
UTC = timezone.utc
NONCE = re.compile(r"[a-f0-9]{32}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
ISO = re.compile(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
FIELDS = frozenset((
    "schema", "audience", "issuer_claim", "anchor_key_id", "channel_key_id",
    "sequence", "last_envelope_sha256", "challenge_nonce",
    "issued_at_utc", "expires_at_utc", "hmac_sha256",
))


def _utf8(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _pairs_unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None or value.microsecond:
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def _ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value: Any) -> datetime | None:
    if type(value) is not str or ISO.fullmatch(value) is None:
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        return parsed if _ts(parsed) == value else None
    except (ValueError, TypeError, OverflowError):
        return None


def _key_valid(key: Any) -> bool:
    return type(key) is bytes and 32 <= len(key) <= 64


def _floor_valid(seq: Any, digest: Any) -> bool:
    return (type(seq) is int and 0 <= seq < 2**63
            and ((seq == 0 and digest is None)
                 or (seq > 0 and type(digest) is str
                     and DIGEST.fullmatch(digest) is not None)))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_EXTERNAL_REPLAY_ANCHOR_BLOCKED_NO_GO",
        "reason": reason,
        "anchor_hmac_valid": False,
        "local_and_external_high_water_match": False,
        "local_database_rollback_suspected": False,
        "external_anchor_stale_or_rollback_suspected": False,
        "same_sequence_digest_conflict": False,
        "anchor_sequence_claim_only": None,
        "local_sequence_read_only": None,
        "local_database_writes": 0,
        "external_anchor_writes": 0,
        "mt5_calls": 0,
        "http_requests": 0,
        "sanitized_report": None,
        "external_anchor_service_independently_authenticated": False,
        "external_anchor_monotonic_storage_implemented_here": False,
        "anchor_verification_key_provisioned_here": False,
        "clock_independently_attested": False,
        "trusted_restoration_fencing_implemented": False,
        "rollback_protection_deployed": False,
        "trade_authorized": False,
        "score_unlocked": False,
        "operational_bias": "AGUARDAR",
    }


def synthesize_fx28_anchor_checkpoint_for_offline_tests_lab(
    *, sequence: Any, last_envelope_sha256: Any, challenge_nonce: Any,
    issued_at_utc: Any, separate_test_anchor_key: Any,
) -> bytes | None:
    """Pure test fixture: NEVER a deployed monotonic external service."""
    issued = _utc(issued_at_utc)
    if (not _floor_valid(sequence, last_envelope_sha256)
            or type(challenge_nonce) is not str
            or NONCE.fullmatch(challenge_nonce) is None
            or issued is None or not _key_valid(separate_test_anchor_key)):
        return None
    body = {
        "schema": SCHEMA,
        "audience": ANCHOR_AUDIENCE,
        "issuer_claim": ANCHOR_ISSUER,
        "anchor_key_id": ANCHOR_KEY_ID,
        "channel_key_id": KEY_ID,
        "sequence": sequence,
        "last_envelope_sha256": last_envelope_sha256,
        "challenge_nonce": challenge_nonce,
        "issued_at_utc": _ts(issued),
        "expires_at_utc": _ts(issued + timedelta(seconds=TTL_SECONDS)),
    }
    mac = hmac.new(separate_test_anchor_key, _utf8(body), sha256).hexdigest()
    result = _utf8({**body, "hmac_sha256": mac})
    return result if len(result) <= MAX_BYTES else None


def inspect_fx28_sqlite_vs_external_anchor_lab(
    *, conn: Any, raw_anchor_checkpoint: Any, separate_anchor_verification_key: Any,
    expected_fresh_challenge_nonce: Any, checked_at_utc: Any,
) -> dict[str, Any]:
    """Fail-closed read-only comparison. Matching records NEVER authorize UI.

    A real receiver must obtain an independently fresh nonce and live,
    challenge-bound response from an independently administered monotonic
    service, then fence against restoration before any acceptance. This
    code accepts caller-supplied bytes as UNTRUSTED and never marks that
    external service as verified or configured.
    """
    out = _blocked("EXTERNAL_ANCHOR_EVIDENCE_OR_LOCAL_DB_INVALID")
    now = _utc(checked_at_utc)
    if (not _conn_ready(conn) or now is None
            or not _key_valid(separate_anchor_verification_key)
            or type(expected_fresh_challenge_nonce) is not str
            or NONCE.fullmatch(expected_fresh_challenge_nonce) is None):
        return out
    if (type(raw_anchor_checkpoint) is not bytes
            or not 200 <= len(raw_anchor_checkpoint) <= MAX_BYTES):
        out["reason"] = "ANCHOR_CHECKPOINT_NOT_VALID_BYTES"
        return out
    try:
        snapshot = json.loads(raw_anchor_checkpoint.decode("ascii"),
                              object_pairs_hook=_pairs_unique,
                              parse_constant=lambda _:
                                  (_ for _ in ()).throw(ValueError("NONFINITE")))
        if (type(snapshot) is not dict or frozenset(snapshot) != FIELDS
                or _utf8(snapshot) != raw_anchor_checkpoint):
            raise ValueError("MALFORMED_CHECKPOINT")
    except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
        out["reason"] = "ANCHOR_CHECKPOINT_JSON_NOT_CANONICAL"
        return out
    if (snapshot["schema"] != SCHEMA
            or snapshot["audience"] != ANCHOR_AUDIENCE
            or snapshot["issuer_claim"] != ANCHOR_ISSUER
            or snapshot["anchor_key_id"] != ANCHOR_KEY_ID
            or snapshot["channel_key_id"] != KEY_ID
            or type(snapshot["hmac_sha256"]) is not str
            or DIGEST.fullmatch(snapshot["hmac_sha256"]) is None):
        out["reason"] = "ANCHOR_CHANNEL_OR_SIGNATURE_STRUCTURE_MISMATCH"
        return out
    body = {k: v for k, v in snapshot.items() if k != "hmac_sha256"}
    expected = hmac.new(separate_anchor_verification_key,
                        _utf8(body), sha256).hexdigest()
    if not hmac.compare_digest(expected, snapshot["hmac_sha256"]):
        out["reason"] = "ANCHOR_HMAC_MISMATCH"
        return out
    out["anchor_hmac_valid"] = True
    anchor_seq = snapshot["sequence"]
    anchor_digest = snapshot["last_envelope_sha256"]
    issued, expires = (_parse_ts(snapshot["issued_at_utc"]),
                       _parse_ts(snapshot["expires_at_utc"]))
    if (not _floor_valid(anchor_seq, anchor_digest)
            or snapshot["challenge_nonce"] != expected_fresh_challenge_nonce
            or issued is None or expires is None
            or expires - issued != timedelta(seconds=TTL_SECONDS)
            or issued > now + timedelta(seconds=FUTURE_CLOCK_SKEW_SECONDS)
            or now >= expires):
        out["reason"] = "ANCHOR_CHALLENGE_CLOCK_OR_SEQUENCE_INVALID"
        return out
    out["anchor_sequence_claim_only"] = anchor_seq

    try:
        conn.execute("BEGIN")  # consistent read-only DB snapshot
        row = conn.execute(
            f"SELECT key_id,audience,issuer_claim,"
            f"highest_accepted_sequence,last_envelope_sha256 "
            f"FROM {TABLE} WHERE id=1").fetchone()
        count = conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()
        app_id = conn.execute("PRAGMA main.application_id").fetchone()
        version = conn.execute("PRAGMA main.user_version").fetchone()
        valid = (row is not None and count is not None and count[0] == 1
                 and row[:3] == (KEY_ID, AUDIENCE, ISSUER)
                 and _floor_valid(row[3], row[4])
                 and app_id and app_id[0] == APP_ID
                 and version and version[0] == 1)
        conn.rollback()
    except sqlite3.Error:
        if conn.in_transaction:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
        out["reason"] = "SQLITE_READ_ONLY_ANCHOR_COMPARISON_FAILED"
        return out
    if not valid:
        out["reason"] = "LOCAL_REPLAY_DB_IDENTITY_OR_FLOOR_INVALID"
        return out
    local_seq, local_digest = row[3], row[4]
    out["local_sequence_read_only"] = local_seq
    if local_seq < anchor_seq:
        out["local_database_rollback_suspected"] = True
        out["reason"] = "LOCAL_DB_BEHIND_EXTERNAL_ANCHOR_POSSIBLE_RESTORE"
        return out
    if anchor_seq < local_seq:
        out["external_anchor_stale_or_rollback_suspected"] = True
        out["reason"] = "EXTERNAL_ANCHOR_BEHIND_LOCAL_DB_POSSIBLE_RESTORE"
        return out
    if local_digest != anchor_digest:
        out["same_sequence_digest_conflict"] = True
        out["reason"] = "SAME_SEQUENCE_DIFFERENT_ENVELOPE_DIGEST"
        return out
    out.update({
        "state": "LAB_FX28_EXTERNAL_ANCHOR_HMAC_MATCH_LOCAL_CLAIM_ONLY_NO_GO",
        "reason": "MATCHED_CALLER_SUPPLIED_ANCHOR_NOT_INDEPENDENTLY_ATTESTED",
        "local_and_external_high_water_match": True,
    })
    return out


__all__ = (
    "SCHEMA", "ANCHOR_AUDIENCE", "ANCHOR_ISSUER", "ANCHOR_KEY_ID",
    "synthesize_fx28_anchor_checkpoint_for_offline_tests_lab",
    "inspect_fx28_sqlite_vs_external_anchor_lab",
)
