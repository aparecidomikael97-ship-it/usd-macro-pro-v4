"""AtlasQuant FX28 FIRST Sunday M15 read-only archive census (LAB).

Counts attempts, never retries a source read. Rejects duplicated/partial archives.
Uses the frozen original hash verifier AND a separate semantic OHLC checker.
An empty but verified M15 CSV is not a real observed candle; an API None
error cannot be certified as an empty response. This census cannot prove
the broker, initial release time, pre-event forecasts or profitable trades.

NO network, MT5, orders, new sources, archive writes, scheduler or deploy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import re
from hashlib import sha256
from atlasquant_trader_fx28_first_m15_atomic_claim_lab import (
    CLAIM_NAME, SCHEMA as CLAIM_SCHEMA,
)

from atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab import (
    PAIRS, SCHEMA as ARCHIVE_SCHEMA, verify_archive_lab,
)
from atlasquant_trader_fx28_m15_semantic_postcheck_lab import assert_semantics

SCHEMA = "ATLASQUANT_FX28_FIRST_M15_ARCHIVE_CENSUS_READONLY_LAB_V1"
WINDOW = "CAMPAIGN_FIRST_M15_20261115"
START = datetime(2026, 11, 15, 22, 0, tzinfo=timezone.utc)
END = datetime(2026, 11, 15, 22, 15, tzinfo=timezone.utc)
ARCHIVE_SUFFIX = re.compile(
    r"CAMPAIGN_FIRST_M15_20261115_(20\d{6}T\d{6}\d{6}Z)\Z",
    re.IGNORECASE,
)

def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_FIRST_M15_ARCHIVE_CENSUS_BLOCKED_NO_GO",
        "reason": reason,
        "window": WINDOW,
        "frozen_start_utc": START.isoformat(),
        "frozen_end_exclusive_utc": END.isoformat(),
        "expected_pair_count": 28,
        "expected_candles_in_frozen_window": 28,
        "candidate_window_artifact_count": None,
        "candidate_artifact_names": [],
        "attempt_claim_marker_present": False,
        "attempt_claim_marker_sha256": None,
        "attempt_claim_marker_is_not_broker_attestation": True,
        "archive_manifest_sha256": None,
        "symbol_hashes_verified": 0,
        "m15_rows_semantically_verified": 0,
        "missing_expected_m15_open_count": None,
        "all_28_nominal_m15_missing": None,
        "source_observation_class": "UNKNOWN",
        "pre_event_forecast_witness_checked": False,
        "archive_created_does_not_prove_market_price_available": True,
        "retrieved_at_os_clock_is_not_broker_first_seen": True,
        "broker_source_independently_authenticated": False,
        "point_in_time_source_authenticated": False,
        "valid_directional_bias": None,
        "validated_accuracy": None,
        "campaign_672_slots_untouched": True,
        "trade_authorized": False,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "http_requests": 0,
        "mt5_calls": 0,
        "file_writes": 0,
    }

def _aware_utc(now: Any) -> datetime | None:
    if not isinstance(now, datetime) or now.tzinfo is None:
        return None
    try:
        if now.utcoffset() is None:
            return None
        return now.astimezone(timezone.utc)
    except (TypeError, OverflowError, ValueError):
        return None

def _safe_absolute_root(root: Any) -> bool:
    if not isinstance(root, Path) or not root.is_absolute():
        return False
    try:
        return not any(p.is_symlink() for p in (root, *root.parents))
    except (OSError, RuntimeError, ValueError, TypeError):
        return False

def inspect_first_m15_archive_census_lab(*, archive_root: Any,
                                         inspected_at_utc: Any) -> dict[str, Any]:
    result = _base("INVALID_ROOT_OR_INSPECTION_CLOCK")
    now = _aware_utc(inspected_at_utc)
    if now is None or not _safe_absolute_root(archive_root):
        return result
    if now < END:
        result["state"] = "LAB_FX28_FIRST_M15_WINDOW_NOT_CLOSED_NO_GO"
        result["reason"] = "NO_PREMATURE_ARCHIVE_INSPECTION_OR_FORECAST"
        return result

    root: Path = archive_root
    try:
        if not root.exists():
            result.update({
                "state": "LAB_FX28_FIRST_M15_ARCHIVE_NOT_OBSERVED_NO_GO",
                "reason": "NO_ARCHIVE_DIRECTORY_VISIBLE_NOT_PROOF_NO_ATTEMPT",
                "candidate_window_artifact_count": 0,
            })
            return result
        if not root.is_dir():
            result["reason"] = "ARCHIVE_ROOT_NOT_DIRECTORY"
            return result
        prefix = WINDOW.casefold() + "_"
        candidates = sorted(
            (item for item in root.iterdir()
             if item.name.casefold() == WINDOW.casefold()
             or item.name.casefold().startswith(prefix)),
            key=lambda item: item.name.casefold(),
        )
        # The atomic attempt marker is not an archive.  When the claimed
        # driver is used, a normal single capture produces BOTH one marker
        # and one timestamped archive.  Counting them as two captures is a
        # false duplicate; ignoring a malformed marker is also unsafe.
        markers = [p for p in candidates if p.name.casefold() == CLAIM_NAME.casefold()]
        archives = [p for p in candidates if p.name.casefold() != CLAIM_NAME.casefold()]
        result["candidate_window_artifact_count"] = len(archives)
        result["candidate_artifact_names"] = [p.name for p in archives[:16]]
        result["attempt_claim_marker_present"] = bool(markers)
        if len(markers) > 1:
            result["reason"] = "MULTIPLE_CASE_VARIANT_CLAIM_MARKERS_FAIL_CLOSED"
            return result
        claimed_at = None
        if markers:
            marker = markers[0]
            if marker.name != CLAIM_NAME or marker.is_symlink() or not marker.is_file():
                result["reason"] = "CLAIM_MARKER_NAME_OR_TYPE_UNSAFE"
                return result
            raw = marker.read_bytes()
            if not raw or len(raw) > 2048:
                result["reason"] = "CLAIM_MARKER_EMPTY_OR_TOO_LARGE_FAIL_CLOSED"
                return result
            claim = json.loads(raw.decode("utf-8", "strict"))
            value = claim.get("claimed_at_utc_local_clock_unattested")
            if type(value) is not str:
                result["reason"] = "CLAIM_MARKER_TIMESTAMP_INVALID"
                return result
            claimed_at = _aware_utc(datetime.fromisoformat(value))
            if (claim.get("schema") != CLAIM_SCHEMA or claim.get("window") != WINDOW
                    or claim.get("window_open_utc") != START.isoformat()
                    or claim.get("window_end_utc") != END.isoformat()
                    or claim.get("one_attempt_only") is not True
                    or claim.get("never_retry_without_human_review") is not True
                    or claim.get("source_first_seen_attested") is not False
                    or claim.get("broker_identity_authenticated") is not False
                    or claim.get("trading_authorized") is not False
                    or claimed_at is None or not END <= claimed_at <= now):
                result["reason"] = "CLAIM_MARKER_CONTENT_OR_CLOCK_INVALID"
                return result
            result["attempt_claim_marker_sha256"] = sha256(raw).hexdigest()
        if not archives:
            result.update({
                "state": "LAB_FX28_FIRST_M15_ARCHIVE_NOT_OBSERVED_NO_GO",
                "reason": ("ATTEMPT_CLAIM_EXISTS_WITHOUT_ARCHIVE_NO_RETRY"
                           if markers else
                           "NO_WINDOW_ARTIFACT_VISIBLE_MAY_HAVE_FAILED_BEFORE_WRITE"),
            })
            return result
        if len(archives) > 1:
            result["reason"] = "MULTIPLE_WINDOW_ARTIFACTS_NO_GO_NO_SECOND_CAPTURE"
            return result
        one = archives[0]
        if one.is_symlink() or not one.is_dir():
            result["reason"] = "WINDOW_ARTIFACT_SYMLINK_OR_NOT_DIRECTORY"
            return result
        match = ARCHIVE_SUFFIX.fullmatch(one.name)
        if match is None:
            result["reason"] = "WINDOW_ARCHIVE_NAME_NOT_CANONICAL"
            return result
        name_timestamp = datetime.strptime(
            match.group(1), "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        if name_timestamp < END or name_timestamp > now:
            result["reason"] = "ARCHIVE_NAMED_TIME_OUTSIDE_COMPLETED_WINDOW"
            return result
        if claimed_at is not None and name_timestamp < claimed_at:
            result["reason"] = "ARCHIVE_CLOCK_PREDATES_ATTEMPT_CLAIM"
            return result

        # Independently verify ALL 28 raw CSVs and the frozen bar grid.
        base = verify_archive_lab(one)
        extra = assert_semantics(one)
        if (base.get("window") != WINDOW
                or base.get("symbol_hashes_verified") != len(PAIRS)
                or extra.get("symbols_structurally_verified") != len(PAIRS)
                or base.get("manifest_sha256") != extra.get("manifest_sha256")
                or base.get("source_first_seen_attested") is not False
                or base.get("forecast_witness_authenticated") is not False
                or base.get("trade_authorized") is not False
                or extra.get("trading_authorized") is not False):
            result["reason"] = "INCONSISTENT_BASE_AND_SEMANTIC_ARCHIVE_PROOF"
            return result
        manifest_path = one / "manifest.json"
        if manifest_path.is_symlink():
            result["reason"] = "MANIFEST_SYMLINK_NOT_ACCEPTED"
            return result
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        captured = datetime.fromisoformat(
            manifest["retrieved_at_utc_local_clock_claim"])
        captured_utc = _aware_utc(captured)
        if captured_utc is None or captured_utc != name_timestamp:
            result["reason"] = "ARCHIVE_NAME_AND_RETRIEVAL_CLOCK_DISAGREE"
            return result
        if manifest.get("schema") != ARCHIVE_SCHEMA:
            result["reason"] = "ARCHIVE_SCHEMA_DRIFT"
            return result
        count = extra["m15_rows_semantically_checked"]
        missing = base["missing_m15_total"]
        if (type(count) is not int or type(missing) is not int
                or count + missing != 28 or count < 0 or missing < 0):
            result["reason"] = "FROZEN_SINGLE_M15_PER_PAIR_COUNT_CONTRADICTION"
            return result

        result.update({
            "symbol_hashes_verified": 28,
            "m15_rows_semantically_verified": count,
            "missing_expected_m15_open_count": missing,
            "all_28_nominal_m15_missing": missing == 28,
            "archive_manifest_sha256": base["manifest_sha256"],
        })
        if missing == 28:
            result.update({
                "state": "LAB_FX28_FIRST_M15_ALL_28_MISSING_PRICE_INSUFFICIENT_NO_GO",
                "reason": "ALL_NOMINAL_SUNDAY_FIRST_BARS_UNAVAILABLE_NO_FILL_OR_RETIME",
                "source_observation_class": "28_VALID_EMPTY_ARRAY_CLAIMS_LOCAL_ONLY",
            })
        elif missing > 0:
            result.update({
                "state": "LAB_FX28_FIRST_M15_PARTIAL_MISSING_PRICE_NO_GO",
                "reason": "PARTIAL_BROKER_HISTORY_GAPS_NOT_SOURCE_ATTESTED",
                "source_observation_class": "SOME_M15_ROWS_AND_GAPS_LOCALLY_VERIFIED",
            })
        else:
            result.update({
                "state": "LAB_FX28_FIRST_M15_STRUCTURAL_BARS_ONLY_NO_GO",
                "reason": "ALL_M15_ROWS_STRUCTURAL_NOT_SOURCE_OR_PIT_AUTHENTICATED",
                "source_observation_class": "28_M15_ROWS_LOCALLY_VERIFIED_ONLY",
            })
        return result
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            OverflowError, RuntimeError, AttributeError, json.JSONDecodeError):
        result["reason"] = "ARCHIVE_INSPECTION_EXCEPTION_FAIL_CLOSED"
        return result

__all__ = ("SCHEMA", "WINDOW", "inspect_first_m15_archive_census_lab")
