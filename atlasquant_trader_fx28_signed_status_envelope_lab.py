"""Pure, explicitly OFFLINE HMAC envelope for a sanitized FX28 Radar status.

Future transport DESIGN only: no keys configured, no listener, uploads, MT5,
disk reads, scheduler, GitHub posts, deployment or trading. The only allowed
payload is the exact 20-field LAB quarantined snapshot. Do not forward file
paths, prices, terminal/server identities, instruments or private metadata.

The HMAC verifies possession of a pre-shared secret, *not* AM12 hardware,
Pepperstone identity, broker clock, first-seen time or historical accuracy.
The receiver MUST supply a trusted, externally persisted sequence floor
to reject replay after restarts; no such store is implemented here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import re
from typing import Any, Mapping

from atlasquant_trader_fx28_temporal_radar_runtime_binding_lab import (
    SCHEMA as PAYLOAD_SCHEMA, STATE as PAYLOAD_STATE,
)

SCHEMA = "ATLASQUANT_FX28_SIGNED_MINIMAL_RADAR_ENVELOPE_LAB_V1"
AUDIENCE = "ATLASQUANT_TRADER_RADAR_PRIVATE_LAB_V1"
ISSUER = "AM12_FX28_LOCAL_RESEARCH_PUBLISHER_CLAIM_V1"
KEY_ID = "fx28-status-lab-v1"
TTL_SECONDS = 300
MAX_CLOCK_SKEW_SECONDS = 30
MAX_RAW_BYTES = 4096
UTC = timezone.utc
_NONCE = re.compile(r"[0-9a-f]{32}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_TIMESTAMP = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_ALLOWED_STATUS_KEYS = frozenset((
    "schema","state","frozen_total_slots",
    "first_nominal_window_slots_quarantined",
    "first_nominal_window_distinct_m15_prices_missing",
    "remaining_original_slots_unevaluated","first_window_horizons",
    "clock_p0_documentary_historical_claims_checked",
    "broker_source_independently_authenticated",
    "github_pre_event_witness_independently_authenticated",
    "verified_directional_accuracy","calibrated_probability",
    "score_allowed","trade_authorized","publishable",
    "has_local_price_data_exposed","file_writes","mt5_calls",
    "http_requests","operational_bias",
))
_ENVELOPE_KEYS = frozenset((
    "schema","audience","issuer_claim","key_id","sequence",
    "nonce","issued_at_utc","expires_at_utc","payload",
    "hmac_sha256",
))
_SIGNED_KEYS = _ENVELOPE_KEYS - {"hmac_sha256"}


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None or value.microsecond:
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(UTC)
    except (OverflowError, ValueError, TypeError):
        return None


def _timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _decode_timestamp(value: Any) -> datetime | None:
    if type(value) is not str or _TIMESTAMP.fullmatch(value) is None:
        return None
    try:
        result=datetime.fromisoformat(value[:-1]+"+00:00")
        return result if _timestamp(result) == value else None
    except (OverflowError, ValueError, TypeError):
        return None


def _duplicate_reject(items: list[tuple[str, Any]]) -> dict[str, Any]:
    obj = {}
    for key, value in items:
        if key in obj:
            raise ValueError("DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def _json(data: Any) -> bytes:
    return json.dumps(data,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False).encode("ascii")


def _valid_key(key: Any) -> bool:
    return type(key) is bytes and 32 <= len(key) <= 64


def _safe_payload(payload: Any) -> bool:
    if type(payload) is not dict or frozenset(payload) != _ALLOWED_STATUS_KEYS:
        return False
    # Static, contradictory-free NO-GO content only. A new observation schema
    # needs a distinct version + review; do not silently generalize.
    expected = {
        "schema":PAYLOAD_SCHEMA,"state":PAYLOAD_STATE,
        "frozen_total_slots":672,
        "first_nominal_window_slots_quarantined":56,
        "first_nominal_window_distinct_m15_prices_missing":28,
        "remaining_original_slots_unevaluated":616,
        "first_window_horizons":{"D1":28,"W1":28},
        "clock_p0_documentary_historical_claims_checked":False,
        "broker_source_independently_authenticated":False,
        "github_pre_event_witness_independently_authenticated":False,
        "verified_directional_accuracy":None,
        "calibrated_probability":None,
        "score_allowed":False,"trade_authorized":False,
        "publishable":False,"has_local_price_data_exposed":False,
        "file_writes":0,"mt5_calls":0,"http_requests":0,
        "operational_bias":"AGUARDAR",
    }
    if payload != expected:
        return False
    # Python bool == 0/1: require exact types to prevent forged counts.
    if (any(type(payload[k]) is not int for k in (
            "frozen_total_slots","first_nominal_window_slots_quarantined",
            "first_nominal_window_distinct_m15_prices_missing",
            "remaining_original_slots_unevaluated",
            "file_writes","mt5_calls","http_requests"))
            or type(payload["first_window_horizons"]) is not dict
            or any(type(payload["first_window_horizons"][k]) is not int
                   for k in ("D1","W1"))
            or any(type(payload[k]) is not bool for k in (
                "clock_p0_documentary_historical_claims_checked",
                "broker_source_independently_authenticated",
                "github_pre_event_witness_independently_authenticated",
                "score_allowed","trade_authorized","publishable",
                "has_local_price_data_exposed"))):
        return False
    return True


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema":SCHEMA,
        "state":"LAB_FX28_SIGNED_RADAR_STATUS_REJECTED_NO_GO",
        "reason":reason,"sanitized_report":None,
        "hmac_checked":False,
        "key_holder_only_authenticated":False,
        "actual_am12_device_independently_authenticated":False,
        "broker_source_authenticated":False,
        "trade_authorized":False,
        "score_unlocked":False,"file_writes":0,
        "http_requests":0,"mt5_calls":0,
        "transport_configured":False,
        "trusted_replay_checkpoint_persisted_by_this_code":False,
        "publisher_private_key_configured_by_this_code":False,
    }


def sign_fx28_sanitized_radar_status_lab(
    *, report: Any, secret_key: Any, sequence: Any,
    nonce_hex: Any, issued_at_utc: Any,
) -> bytes | None:
    """Return <=4KiB canonical signed bytes; never persist/transmit them.

    The caller must supply a CSPRNG 128-bit nonce and securely injected key.
    This helper does not generate or store a key or nonce.
    """
    issued=_utc(issued_at_utc)
    if (not _safe_payload(report) or not _valid_key(secret_key)
            or type(sequence) is not int or not 1 <= sequence <= 2**63-1
            or type(nonce_hex) is not str or not _NONCE.fullmatch(nonce_hex)
            or issued is None):
        return None
    envelope={
        "schema":SCHEMA,"audience":AUDIENCE,"issuer_claim":ISSUER,
        "key_id":KEY_ID,"sequence":sequence,"nonce":nonce_hex,
        "issued_at_utc":_timestamp(issued),
        "expires_at_utc":_timestamp(issued+timedelta(seconds=TTL_SECONDS)),
        "payload":report,
    }
    signature=hmac.new(secret_key,_json(envelope),sha256).hexdigest()
    raw=_json({**envelope,"hmac_sha256":signature})
    return raw if len(raw)<=MAX_RAW_BYTES else None


def verify_fx28_sanitized_radar_status_lab(
    *, raw_envelope: Any, secret_key: Any,
    received_at_utc: Any, trusted_last_sequence: Any,
) -> dict[str, Any]:
    """Accept only a new, fresh signature with trusted caller replay floor.

    The receiver MUST load the last committed sequence from its own trusted
    durable store *before* validation and commit the newly accepted sequence
    atomically *before* displaying it. This function cannot enforce persistence
    or authenticate who installed the shared key.
    """
    out=_blocked("INVALID_CLOCK_KEY_OR_TRUSTED_REPLAY_FLOOR")
    now=_utc(received_at_utc)
    if (now is None or not _valid_key(secret_key)
            or type(trusted_last_sequence) is not int
            or not 0 <= trusted_last_sequence < 2**63):
        return out
    if (type(raw_envelope) is not bytes or not 100 <= len(raw_envelope) <= MAX_RAW_BYTES):
        out["reason"]="INVALID_ENVELOPE_BYTES_OR_SIZE"
        return out
    try:
        data=json.loads(raw_envelope.decode("ascii"),
                        object_pairs_hook=_duplicate_reject,
                        parse_constant=lambda _: (_ for _ in ()).throw(
                            ValueError("INVALID_JSON_CONSTANT")))
        if type(data) is not dict or frozenset(data) != _ENVELOPE_KEYS:
            raise ValueError("INVALID_ENVELOPE_KEYS")
        if _json(data) != raw_envelope:
            raise ValueError("UNCANONICAL_ENVELOPE_BYTES")
    except (UnicodeError,TypeError,ValueError,RecursionError,OverflowError):
        out["reason"]="INVALID_NONCANONICAL_DUPLICATE_OR_UNSAFE_JSON"
        return out
    sign=data["hmac_sha256"]
    signed={k:data[k] for k in _SIGNED_KEYS}
    if (type(sign) is not str or _HEX.fullmatch(sign) is None
            or data["schema"] != SCHEMA
            or data["audience"] != AUDIENCE
            or data["issuer_claim"] != ISSUER
            or data["key_id"] != KEY_ID):
        out["reason"]="BAD_ENVELOPE_ROUTING_OR_SIGNATURE_SHAPE"
        return out
    correct=hmac.new(secret_key,_json(signed),sha256).hexdigest()
    out["hmac_checked"]=True
    if not hmac.compare_digest(sign,correct):
        out["reason"]="MESSAGE_AUTHENTICATION_FAILED_NO_GO"
        return out
    out["key_holder_only_authenticated"]=True
    if not _safe_payload(data["payload"]):
        out["reason"]="SIGNED_PAYLOAD_CONTAINS_UNSAFE_OR_NON_LAB_FIELDS"
        return out
    issued=_decode_timestamp(data["issued_at_utc"])
    expires=_decode_timestamp(data["expires_at_utc"])
    sequence=data["sequence"]
    if (issued is None or expires is None
            or expires- issued != timedelta(seconds=TTL_SECONDS)
            or issued > now + timedelta(seconds=MAX_CLOCK_SKEW_SECONDS)
            or now >= expires
            or type(sequence) is not int
            or not trusted_last_sequence < sequence <= 2**63-1
            or type(data["nonce"]) is not str
            or _NONCE.fullmatch(data["nonce"]) is None):
        out["reason"]="EXPIRED_FUTURE_REPLAYED_OR_INVALID_SIGNED_CLOCK"
        return out
    out.update({
        "state":"LAB_FX28_SIGNED_RADAR_STATUS_KEY_HOLDER_ONLY_NO_GO",
        "reason":"FRESH_HMAC_WITH_EXTERNAL_REPLAY_FLOOR_NOT_BROKER_ATTESTATION",
        "sanitized_report":data["payload"],
        "proposed_new_sequence_for_external_atomic_commit":sequence,
    })
    return out


__all__=("SCHEMA","AUDIENCE","ISSUER","KEY_ID",
         "sign_fx28_sanitized_radar_status_lab",
         "verify_fx28_sanitized_radar_status_lab")
