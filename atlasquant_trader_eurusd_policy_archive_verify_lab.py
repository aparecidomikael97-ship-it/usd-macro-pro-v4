"""Offline replay of a manually captured ECB/Fed policy-level evidence ZIP.

An externally recorded ZIP SHA prevents unnoticed *file* replacement, but a
hash is NOT a bank signature, release-time witness, consensus, or vintage.
This module reads only, makes no HTTP requests, and never yields an FX signal.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Any
from zipfile import BadZipFile, ZipFile, ZIP_STORED

from atlasquant_trader_eurusd_policy_capture_once_lab import (
    SCHEMA as CAPTURE_SCHEMA, SOURCES,
)
from atlasquant_trader_eurusd_policy_levels_lab import MAX_BYTES

SCHEMA = "ATLASQUANT_TRADER_EURUSD_POLICY_ZIP_OFFLINE_REPLAY_LAB_V1"
MAX_ZIP_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 256 * 1024
EXPECTED_ENTRIES = {"response.csv", "observation_receipt.json"}
_HEX = re.compile(r"[a-f0-9]{64}\Z")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_ARCHIVE_VERIFY_BLOCKED",
        "reason": reason, "raw_response_sha256_matched": False,
        "archive_sha256_matched": False,
        "replay_parser_consistent": False,
        "external_http_requests": 0,
        "source_origin_independently_authenticated": False,
        "publication_instant_independently_verified": False,
        "consensus_before_decision_verified": False,
        "historical_point_in_time_availability_verified": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


def verify_policy_capture_zip_offline_lab(
    archive_path: Any, *, expected_zip_sha256: Any,
    evaluated_at_utc: datetime,
) -> dict[str, Any]:
    """Require a separately recorded SHA and replay the original CSV bytes."""
    if (not isinstance(evaluated_at_utc, datetime)
            or evaluated_at_utc.tzinfo is None
            or evaluated_at_utc.utcoffset() is None):
        raise ValueError("Timezone-aware evaluation clock required")
    if not isinstance(expected_zip_sha256, str) or not _HEX.fullmatch(expected_zip_sha256):
        return _blocked("EXPECTED_EXTERNAL_ZIP_SHA256_REQUIRED")
    try:
        path = Path(archive_path)
        if (path.is_symlink() or not path.is_file()
                or not 1 <= path.stat().st_size <= MAX_ZIP_BYTES):
            return _blocked("ARCHIVE_NOT_REGULAR_BOUNDED_FILE")
        # Bound reads and parse the SAME bytes that matched the external SHA:
        # reopening the path for ZIP parsing would permit a replacement race.
        with path.open("rb") as stream:
            archive_bytes = stream.read(MAX_ZIP_BYTES + 1)
    except (OSError, TypeError, ValueError):
        return _blocked("ARCHIVE_NOT_READABLE")
    if len(archive_bytes) > MAX_ZIP_BYTES or sha256(archive_bytes).hexdigest() != expected_zip_sha256:
        return _blocked("ARCHIVE_EXTERNAL_SHA256_MISMATCH")
    try:
        with ZipFile(BytesIO(archive_bytes), mode="r") as z:
            info = z.infolist()
            if (len(info) != 2 or {i.filename for i in info} != EXPECTED_ENTRIES
                    or any(i.compress_type != ZIP_STORED or (i.flag_bits & 1)
                           or i.is_dir() for i in info)):
                return _blocked("ZIP_ENTRIES_OR_COMPRESSION_INVALID")
            sizes = {i.filename: i.file_size for i in info}
            if (not 1 <= sizes["response.csv"] <= MAX_BYTES
                    or not 1 <= sizes["observation_receipt.json"] <= MAX_RECEIPT_BYTES):
                return _blocked("ZIP_MEMBER_SIZE_INVALID")
            raw = z.read("response.csv")
            metadata_bytes = z.read("observation_receipt.json")
        receipt = json.loads(metadata_bytes.decode("utf-8"))
    except (OSError, BadZipFile, RuntimeError, ValueError, UnicodeError,
            TypeError, KeyError, OverflowError):
        return _blocked("ZIP_CONTENT_INVALID")
    if not isinstance(receipt, dict):
        return _blocked("ZIP_RECEIPT_NOT_OBJECT")
    source_id = receipt.get("source_id")
    if not isinstance(source_id, str) or source_id not in SOURCES:
        return _blocked("ZIP_SOURCE_NOT_ALLOWLISTED")
    source_url, parser = SOURCES[source_id]
    stamp = receipt.get("observed_at_local_system_utc")
    if not isinstance(stamp, str):
        return _blocked("ZIP_COLLECTION_CLOCK_INVALID")
    try:
        observed = datetime.fromisoformat(stamp)
    except (ValueError, OverflowError):
        return _blocked("ZIP_COLLECTION_CLOCK_INVALID")
    if (observed.tzinfo is None or observed.utcoffset() is None
            or observed.utcoffset().total_seconds() != 0
            or observed > evaluated_at_utc.astimezone(timezone.utc)):
        return _blocked("ZIP_COLLECTION_CLOCK_INVALID_OR_FUTURE")

    flags = {
        "http_response_observed": True,
        "exact_url_and_status_checked": True,
        "default_ca_validation_requested": True,
        "redirects_followed": False,
        "source_origin_independently_authenticated": False,
        "publication_instant_independently_verified": False,
        "historical_point_in_time_availability_verified": False,
        "consensus_before_decision_verified": False,
        "can_feed_live_radar": False,
        "trade_authorized": False,
        "publishable": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
    }
    if (receipt.get("schema") != CAPTURE_SCHEMA
            or receipt.get("requested_url") != source_url
            or receipt.get("http_status") != 200
            or type(receipt.get("external_http_requests")) is not int
            or receipt["external_http_requests"] != 1
            or receipt.get("operational_bias") != "AGUARDAR"
            or type(receipt.get("new_cost_brl")) is not int
            or receipt["new_cost_brl"] != 0
            or receipt.get("raw_snapshot_archive_path") is not None
            or any(receipt.get(k) is not value for k, value in flags.items())
            or type(receipt.get("raw_response_bytes")) is not int
            or receipt["raw_response_bytes"] != len(raw)
            or receipt.get("raw_response_sha256") != sha256(raw).hexdigest()):
        return _blocked("ZIP_RECEIPT_IDENTITY_OR_FLAGS_MISMATCH")
    if (receipt.get("http_content_type") not in (
            "text/csv", "application/csv", "text/plain",
            "application/vnd.ecb.data+csv", "application/octet-stream")):
        return _blocked("ZIP_MEDIA_TYPE_INVALID")
    replay = parser(raw, observed_at_utc=observed)
    accepted = replay["state"] != "LAB_BLOCKED"
    expected_state = ("LAB_CAPTURE_PARSER_ACCEPTED_QUARANTINED" if accepted
                      else "LAB_CAPTURE_RAW_FORMAT_REJECTED_QUARANTINED")
    if (receipt.get("state") != expected_state
            or receipt.get("parser_state") != replay["state"]
            or receipt.get("parser_reason") != replay.get("reason")
            or receipt.get("parser_receipt") != replay):
        return _blocked("ZIP_PARSER_REPLAY_MISMATCH")
    return {
        **_blocked("SOURCE_ORIGIN_AND_EXANTE_STILL_UNVERIFIED"),
        "state": "LAB_ARCHIVE_INTERNAL_INTEGRITY_REPLAYED_QUARANTINED",
        "source_id": source_id,
        "parser_state": replay["state"],
        "parser_accepted": accepted,
        "archive_sha256_matched": True,
        "raw_response_sha256_matched": True,
        "replay_parser_consistent": True,
        "collection_clock_utc_from_receipt": stamp,
        "archive_sha256": expected_zip_sha256,
        "raw_response_sha256": sha256(raw).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Read-only LAB policy ZIP replay")
    cli.add_argument("--archive", required=True)
    cli.add_argument("--expected-sha256", required=True)
    args = cli.parse_args(argv)
    result = verify_policy_capture_zip_offline_lab(
        args.archive, expected_zip_sha256=args.expected_sha256,
        evaluated_at_utc=datetime.now(timezone.utc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "LAB_ARCHIVE_INTERNAL_INTEGRITY_REPLAYED_QUARANTINED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
