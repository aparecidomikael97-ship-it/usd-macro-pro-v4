"""One-time LOCAL custody of all 28 canonical forecast bytes; strict NO-GO.

A published hash-only GitHub comment becomes worthless when the exact
canonical 28-forecast JSON is lost. Here the byte-for-byte source of the
already-existing witness generator is optionally kept once, with an
exclusive filename per nominal horizon/window and a readback SHA check.

The callable does NOT make any forecast and does NOT publish to GitHub.
It cannot authenticate macro vintages, model inputs, issuer first-seen,
the local computer clock or broker data. The preserved content remains a
CALLER CLAIM, not independently verified prospective skill.

No network, MT5, trading, worker, prices, new expenses or probabilities.
Filesystem changes ONLY with allow_write=True and a pre-event clock.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Callable

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    CAMPAIGN_PUBLICATION_CLAIM_UTC,
    SCHEMA as ROSTER_SCHEMA,
)
from atlasquant_trader_fx28_github_public_witness_audit_lab import _anchor
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import CAMPAIGN_ID

SCHEMA = "ATLASQUANT_FX28_LOCAL_CANONICAL_ROSTER_PRESERVATION_LAB_V1"
_EXACT_TOP = {"schema", "campaign_id", "horizon", "start_utc", "end_utc", "pairs"}
_EXACT_ROW = {
    "pair", "direction_claim", "abstain_reason",
    "feature_cutoff_claim_utc", "forecast_issued_claim_utc",
    "model_sha256_claim", "evidence_sha256_claim",
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_DIR = "frozen_fx28_forecast_rosters"


def _clock(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


def _instant(value: Any) -> datetime | None:
    if type(value) is not str or _UTC.fullmatch(value) is None:
        return None
    try:
        obj = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        if obj.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
            return None
        return obj.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_LOCAL_CANONICAL_ROSTER_BLOCKED",
        "reason": reason,
        "filename_in_lab_only": None,
        "canonical_roster_sha256": None,
        "pairs_in_exact_recoverable_source": 0,
        "bytes_in_exact_recoverable_source": 0,
        "source_bytes_replayed_and_hash_checked": False,
        "local_file_write_attempted": False,
        "local_file_created_exclusively": False,
        "local_file_write_count": 0,
        "source_original_persisted_locally_claim_only": False,
        "github_anchor_body_prepared_not_posted": False,
        "github_anchor_body": None,
        "github_comment_posted": False,
        "github_first_seen_independently_attested": False,
        "publisher_time_independently_attested": False,
        "model_and_macro_vintages_authenticated": False,
        "independent_28_forecasts_authenticated": False,
        "real_price_verification_completed": False,
        "can_count_as_real_issued_forecasts": False,
        "trade_authorized": False,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "live_alert_allowed": False,
        "calibrated_probability": None,
        "verified_accuracy": None,
        "network_requests": 0,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "new_cost_brl": 0,
        "research_only": True,
    }


def _inspect_prepared(
    prepared: Any, *, prepared_at_utc: Any, inspected_at_utc: Any,
) -> tuple[dict[str, Any], bytes | None]:
    out = _base("PREPARED_ROSTER_INVALID_OR_AFTER_WINDOW")
    issued_at, now = _clock(prepared_at_utc), _clock(inspected_at_utc)
    if (type(prepared) is not dict
            or issued_at is None or now is None
            or not CAMPAIGN_PUBLICATION_CLAIM_UTC <= issued_at <= now
            or prepared.get("state") != "LAB_WITNESS_BODY_PREPARED_NOT_POSTED"
            or prepared.get("body_posted_on_github") is not False
            or prepared.get("external_precommit_verified") is not False
            or prepared.get("canonical_forecast_payload_retained_externally") is not False):
        return out, None
    parsed = _anchor(prepared.get("body"))
    supplied = prepared.get("canonical_forecast_json")
    digest = prepared.get("forecast_roster_sha256")
    if (parsed is None or type(supplied) is not str
            or not 100 <= len(supplied) <= 65536
            or not supplied.isascii() or type(digest) is not str
            or _SHA.fullmatch(digest) is None):
        return out, None
    horizon, start, end, anchored_sha = parsed
    if not issued_at < start or not now < start or anchored_sha != digest:
        return out, None
    raw = supplied.encode("ascii")
    if sha256(raw).hexdigest() != digest:
        out["reason"] = "CANONICAL_ROSTER_SHA_MISMATCH"
        return out, None
    try:
        payload = json.loads(supplied)
        if (type(payload) is not dict or set(payload) != _EXACT_TOP
                or payload.get("schema") != ROSTER_SCHEMA
                or payload.get("campaign_id") != CAMPAIGN_ID
                or payload.get("horizon") != horizon
                or _instant(payload.get("start_utc")) != start
                or _instant(payload.get("end_utc")) != end
                or type(payload.get("pairs")) is not list
                or len(payload["pairs"]) != 28
                or json.dumps(
                    payload, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=True,
                ) != supplied):
            return out, None
        codes = []
        for row in payload["pairs"]:
            if type(row) is not dict or set(row) != _EXACT_ROW:
                return out, None
            pair, direction = row["pair"], row["direction_claim"]
            feat, sent = (_instant(row[x]) for x in (
                "feature_cutoff_claim_utc", "forecast_issued_claim_utc"))
            if (type(pair) is not str or pair not in OFFICIAL_PAIRS
                    or direction not in ("UP", "DOWN", "ABSTAIN")
                    or feat is None or sent is None
                    or not feat <= sent <= issued_at
                    or not CAMPAIGN_PUBLICATION_CLAIM_UTC <= sent < start
                    or not isinstance(row["model_sha256_claim"], str)
                    or not _SHA.fullmatch(row["model_sha256_claim"])
                    or not isinstance(row["evidence_sha256_claim"], str)
                    or not _SHA.fullmatch(row["evidence_sha256_claim"])
                    or (direction == "ABSTAIN"
                        and row["abstain_reason"] not in (
                            "MISSING_MACRO", "CONFLICTING_EVIDENCE",
                            "LOW_CONFIDENCE", "STALE_DATA", "EVENT_BLACKOUT",
                            "UNVERIFIED_SOURCE", "OTHER"))
                    or (direction != "ABSTAIN"
                        and row["abstain_reason"] is not None)):
                return out, None
            codes.append(pair)
        if codes != sorted(OFFICIAL_PAIRS):
            return out, None
    except (TypeError, ValueError, KeyError, OverflowError):
        return out, None
    filename = f"{start.strftime('%Y%m%dT%H%M%SZ')}_{horizon}.json"
    out.update({
        "state": "LAB_FX28_CANONICAL_ROSTER_PREPARED_NOT_STORED_NO_GO",
        "reason": "EXACT_28_BYTE_ROSTER_CHECKED_BUT_NOT_PERSISTED",
        "filename_in_lab_only": filename,
        "canonical_roster_sha256": digest,
        "pairs_in_exact_recoverable_source": 28,
        "bytes_in_exact_recoverable_source": len(raw),
        "github_anchor_body_prepared_not_posted": True,
        # Returning a hash-only body is safe as a proposed artifact, not
        # a real posted/independently witnessed prediction.
        "github_anchor_body": prepared["body"],
    })
    return out, raw


def inspect_prepared_fx28_roster_lab(
    *, prepared: Any, prepared_at_utc: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Pure structural audit; never mistakes a SHA for proof of real forecast."""
    out, _raw = _inspect_prepared(
        prepared, prepared_at_utc=prepared_at_utc,
        inspected_at_utc=inspected_at_utc)
    return out


def _safe_local_folder(local_appdata: Any) -> Path | None:
    if type(local_appdata) is not str or not local_appdata:
        return None
    root = Path(local_appdata)
    if not root.is_absolute() or not root.exists() or not root.is_dir():
        return None
    # Check root ancestors, not only the final LAB destination. On Windows
    # reparse points/junctions require additional policy before production.
    if any(p.is_symlink() for p in (root, *root.parents)):
        return None
    path = root
    for component in ("AtlasQuant", "LAB", _DIR):
        path = path / component
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            return None
    if not path.resolve(strict=False).is_relative_to(root.resolve(strict=True)):
        return None
    return path


def store_canonical_fx28_roster_once_lab(
    *, prepared: Any, prepared_at_utc: Any, inspected_at_utc: Any,
    local_appdata: Any, allow_write: bool = False,
) -> dict[str, Any]:
    """Explicit exclusive local write once, then SHA-256 readback.

    A crash can leave a partial file: it will never be overwritten silently.
    This is not fully atomic durable archival or a timestamp authority.
    """
    out, raw = _inspect_prepared(
        prepared, prepared_at_utc=prepared_at_utc,
        inspected_at_utc=inspected_at_utc)
    if raw is None:
        return out
    if allow_write is not True:
        out["reason"] = "EXPLICIT_LOCAL_PRESERVATION_OPT_IN_REQUIRED"
        return out
    out["state"] = "LAB_FX28_LOCAL_CANONICAL_ROSTER_BLOCKED"
    out["reason"] = "LOCAL_STORAGE_ROOT_UNSAFE_OR_UNAVAILABLE"
    try:
        folder = _safe_local_folder(local_appdata)
        if folder is None:
            return out
        path = Path(local_appdata)
        for part in ("AtlasQuant", "LAB", _DIR):
            path = path / part
            if path.exists():
                if path.is_symlink() or not path.is_dir():
                    return out
            else:
                os.mkdir(path, mode=0o700)
        target = folder / out["filename_in_lab_only"]
        if target.is_symlink() or target.exists():
            out["reason"] = "WINDOW_FILE_ALREADY_EXISTS_NEVER_OVERWRITE"
            return out
        out["local_file_write_attempted"] = True
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(target, flags, 0o600)
        out["local_file_created_exclusively"] = True
        out["local_file_write_count"] = 1
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except (OSError, ValueError):
            # Keep any partial file for explicit manual review, never
            # replace it with a more convenient after-the-fact "forecast".
            out["reason"] = "PARTIAL_LOCAL_FILE_REQUIRES_MANUAL_REVIEW"
            return out
        if target.is_symlink() or not target.is_file():
            out["reason"] = "LOCAL_WRITE_REPLAY_UNSAFE"
            return out
        lst = target.stat(follow_symlinks=False)
        if not stat.S_ISREG(lst.st_mode) or lst.st_nlink != 1:
            out["reason"] = "LOCAL_WRITE_REPLAY_UNSAFE"
            return out
        readback = target.read_bytes()
        if readback != raw or sha256(readback).hexdigest() != out[
                "canonical_roster_sha256"]:
            out["reason"] = "LOCAL_WRITE_READBACK_HASH_MISMATCH"
            return out
    except (OSError, ValueError, TypeError, RuntimeError, OverflowError):
        out["reason"] = "LOCAL_STORAGE_OR_REPLAY_ERROR"
        return out
    out.update({
        "state": "LAB_FX28_LOCAL_CANONICAL_ROSTER_STORED_REPLAYED_NO_GO",
        "reason": "LOCAL_BYTES_PRESERVED_NOT_PUBLICATION_OR_ORIGIN_ATTESTATION",
        "source_bytes_replayed_and_hash_checked": True,
        "source_original_persisted_locally_claim_only": True,
    })
    return out


__all__ = ("SCHEMA", "inspect_prepared_fx28_roster_lab",
           "store_canonical_fx28_roster_once_lab")
