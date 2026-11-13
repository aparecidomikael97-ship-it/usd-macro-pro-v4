"""Offline, read-only replay of policy source archives in isolated AtlasQuant LAB.

The eight official-issuer collectors save an original public source body
and an adjacent JSON receipt in:
  <LOCALAPPDATA>/AtlasQuant/LAB/official_macro_receipts/

This reader verifies exact issuer-specific basenames, local receipt JSON,
original byte count and SHA-256 before invoking the existing 8-bank gate
and returning per-pair POLICY-SOURCE COVERAGE. It does not open network or
MetaTrader; it cannot independently prove who made the HTML/JSON or its
real first-available time. The caller-provided cutoff is not a trusted
clock. Selection is strictly the latest filename-stamped capture at or
before cutoff, never a silent fallback to an older record if the newest
one is corrupt. Every step remains LAB/AGUARDAR/NO-GO.

Running this on GitHub CI fixtures never proves any AM12 archive is online
or that local source files exist there. No broker orders, background
automation, production filesystem writes, calibrated probabilities, or
pre-event forecast witness.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_eight_policy_raw_source_join_lab import (
    inspect_eight_bank_policy_raw_source_join_lab,
)

SCHEMA = "ATLASQUANT_FX28_LOCAL_POLICY_SOURCE_ARCHIVE_REPLAY_LAB_V1"
RECEIPT_MAX_BYTES = 8192
MAX_RECEIPTS_PER_CURRENCY = 30

# These exact stems/extensions are emitted by each issuer-specific manual
# collector. The module parser still validates the economic instrument.
_ARCHIVES: dict[str, tuple[str, str, int]] = {
    "USD": ("USD_FED_BOARD_TARGET_RANGE", ".html", 240_000),
    "EUR": ("EUR_ECB_FM_B_DFR", ".csv", 48_000),
    "GBP": ("GBP_BOE_BANK_RATE", ".html", 400_000),
    "JPY": ("JPY_BOJ_CURRENT_GUIDELINE", ".html", 300_000),
    "CHF": ("CHF_SNB_CURRENT_POLICY", ".html", 350_000),
    "CAD": ("CAD_BOC_V39079", ".json", 48_000),
    "AUD": ("AUD_RBA_CASH_TARGET", ".html", 250_000),
    "NZD": ("NZD_RBNZ_OCR", ".html", 400_000),
}
RECEIPT_KEYS = frozenset((
    "source_url", "final_url", "http_status", "content_type",
    "body_sha256", "started_at_utc", "finished_at_utc",
    "https_validation_claim", "redirects_followed",
))
UTC_ISO = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")


def _bad_json_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in items:
        if key in out:
            raise ValueError("DUPLICATE_JSON_KEY")
        out[key] = value
    return out


def _bad_json_constant(text: str) -> None:
    raise ValueError("NONFINITE_JSON_VALUE")


def _decision(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_POLICY_ARCHIVE_REPLAY_BLOCKED",
        "reason": reason,
        "policy_issuer_contracts_available": len(_ARCHIVES),
        "currency_universe": sorted(CURRENCIES),
        "archive_root_checked_local_only": False,
        "folder_present_on_this_runtime": False,
        "currency_receipt_files_selected": 0,
        "currencies_with_local_original_bytes_validated": 0,
        "currencies_locally_checked": [],
        "currencies_missing": sorted(CURRENCIES),
        "currencies_rejected": {},
        "currency_archive_status": {},
        "future_stamped_receipts_ignored": {},
        "pairs_with_both_policy_originals_locally_checked": 0,
        "pairs_lacking_at_least_one_policy_original": len(OFFICIAL_PAIRS),
        "pair_policy_source_coverage": [],
        "source_original_bytes_from_AM12_independently_attested": False,
        "source_current_issuer_identity_independently_verified": False,
        "true_first_seen_time_independently_attested": False,
        "historical_point_in_time_vintage_verified": False,
        "cpi_for_all_eight_currencies_authenticated": False,
        "differing_policy_instruments_harmonized": False,
        "pre_event_forecast_witnessed": False,
        "outcome_price_available_and_authenticated": False,
        "operational_bias": "AGUARDAR",
        "directional_bias": None,
        "calibrated_probability": None,
        "validated_direction_accuracy": None,
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "http_requests": 0,
        "files_written": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_fx28_official_policy_archive_replay_lab(
    *, local_appdata: Any, decision_at_utc: Any,
) -> dict[str, Any]:
    """Read existing locally isolated public-source files; never modify.

    WARNING: This checks local archive CONSISTENCY only, not publisher
    signature or publisher's first-release clock; it cannot backdate
    historical visibility. A real AM12 result requires an actual run there.
    """
    out = _base("INVALID_ARCHIVE_ROOT_OR_DECISION_CLOCK")
    cutoff = _decision(decision_at_utc)
    if cutoff is None or type(local_appdata) is not str or not local_appdata:
        return out
    try:
        base = Path(local_appdata)
        if not base.is_absolute() or base.is_symlink():
            return out
        atlas = base / "AtlasQuant"
        lab = atlas / "LAB"
        folder = lab / "official_macro_receipts"
        if any(path.is_symlink() for path in (atlas, lab, folder)):
            out["reason"] = "LOCAL_LAB_DIRECTORY_SYMLINK_REFUSED"
            return out
        root = lab.resolve(strict=False)
        resolved = folder.resolve(strict=False)
        if not resolved.is_relative_to(root):
            out["reason"] = "SOURCE_FOLDER_OUTSIDE_LAB_REFUSED"
            return out
        out["archive_root_checked_local_only"] = True
        if not folder.is_dir():
            out["reason"] = "LOCAL_ISSUER_ARCHIVE_FOLDER_MISSING"
            return out
        out["folder_present_on_this_runtime"] = True
    except (OSError, RuntimeError, ValueError, TypeError):
        out["reason"] = "ARCHIVE_ROOT_FILESYSTEM_INVALID"
        return out

    packets: dict[str, dict[str, Any]] = {}
    rejected: dict[str, str] = {}
    status: dict[str, dict[str, Any]] = {}
    future_ignored: dict[str, int] = {}
    for currency in sorted(CURRENCIES):
        prefix, extension, max_body = _ARCHIVES[currency]
        expected_name = re.compile(
            re.escape(prefix)
            + r"_(20\d{6}T\d{6}Z)_([0-9a-f]{12})\.receipt\.json\Z"
        )
        try:
            found = list(folder.glob(prefix + "_*.receipt.json"))
        except (OSError, RuntimeError, ValueError):
            rejected[currency] = "ARCHIVE_RECEIPT_SEARCH_FAILED"
            continue
        if len(found) > MAX_RECEIPTS_PER_CURRENCY:
            rejected[currency] = "EXCESS_RECEIPT_FILES_FOR_ONE_ISSUER"
            continue
        if not found:
            status[currency] = {"status": "NO_LOCAL_RECEIPT_FOUND"}
            continue

        candidates: list[tuple[datetime, Path, str]] = []
        invalid_name = False
        for entry in found:
            match = expected_name.fullmatch(entry.name)
            if (match is None or entry.is_symlink()
                    or not entry.is_file()):
                invalid_name = True
                break
            stamp, digest_prefix = match.groups()
            try:
                dt = datetime.strptime(
                    stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                invalid_name = True
                break
            candidates.append((dt, entry, digest_prefix))
        if invalid_name:
            rejected[currency] = "UNSAFE_OR_MALFORMED_ISSUER_RECEIPT_FILENAME"
            continue

        eligible = [x for x in candidates if x[0] <= cutoff]
        future_ignored[currency] = len(candidates) - len(eligible)
        if not eligible:
            status[currency] = {"status": "ONLY_FUTURE_STAMPED_RECEIPTS"}
            continue

        last_time = max(item[0] for item in eligible)
        latest = [item for item in eligible if item[0] == last_time]
        if len(latest) != 1:
            rejected[currency] = "AMBIGUOUS_MULTIPLE_CAPTURES_AT_SAME_UTC_SECOND"
            continue

        captured, receipt_file, digest_prefix = latest[0]
        filename = receipt_file.name[:-len(".receipt.json")] + extension
        original_file = folder / filename
        info = {
            "selected_original_filename": filename,
            "selected_receipt_filename": receipt_file.name,
            "selected_local_capture_utc_claim":
                captured.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "PENDING_LOCAL_VALIDATION",
        }
        status[currency] = info
        try:
            if (original_file.is_symlink() or not original_file.is_file()
                    or receipt_file.is_symlink()):
                raise ValueError("LOCAL_SOURCE_OR_RECEIPT_FILE_MISSING_OR_SYMLINK")
            if not 20 <= original_file.stat().st_size <= max_body:
                raise ValueError("ORIGINAL_SOURCE_FILE_SIZE_INVALID")
            if not 10 <= receipt_file.stat().st_size <= RECEIPT_MAX_BYTES:
                raise ValueError("LOCAL_RECEIPT_JSON_SIZE_INVALID")
            body = original_file.read_bytes()
            receipt = json.loads(
                receipt_file.read_bytes().decode("utf-8-sig"),
                object_pairs_hook=_bad_json_duplicates,
                parse_constant=_bad_json_constant,
            )
            if type(receipt) is not dict or set(receipt) != RECEIPT_KEYS:
                raise ValueError("LOCAL_RECEIPT_JSON_SHAPE_INVALID")
            full_hash = sha256(body).hexdigest()
            if (receipt.get("body_sha256") != full_hash
                    or SHA64.fullmatch(full_hash) is None
                    or full_hash[:12] != digest_prefix):
                raise ValueError("SOURCE_FILE_SHA256_OR_FILENAME_MISMATCH")
            stamp_from_receipt = receipt.get("finished_at_utc")
            if (type(stamp_from_receipt) is not str
                    or UTC_ISO.fullmatch(stamp_from_receipt) is None
                    or stamp_from_receipt != info["selected_local_capture_utc_claim"]):
                raise ValueError("RECEIPT_FINISH_TIME_DIFFERS_FROM_FILENAME")
        except (OSError, RuntimeError, TypeError, ValueError, UnicodeError,
                RecursionError, OverflowError) as exc:
            # Never fall back to older data just because the selected
            # current pre-cutoff archive is altered or missing its raw file.
            reason = str(exc) if isinstance(exc, ValueError) else "FILE_READ_OR_JSON_PARSE_FAILED"
            rejected[currency] = (
                reason if reason in (
                    "LOCAL_SOURCE_OR_RECEIPT_FILE_MISSING_OR_SYMLINK",
                    "ORIGINAL_SOURCE_FILE_SIZE_INVALID",
                    "LOCAL_RECEIPT_JSON_SIZE_INVALID",
                    "LOCAL_RECEIPT_JSON_SHAPE_INVALID",
                    "SOURCE_FILE_SHA256_OR_FILENAME_MISMATCH",
                    "RECEIPT_FINISH_TIME_DIFFERS_FROM_FILENAME",
                ) else "LOCAL_RECEIPT_OR_SOURCE_FILE_UNREADABLE"
            )
            info["status"] = "REJECTED_LOCAL_ARCHIVE"
            continue

        packets[currency] = {"original_bytes": body, "receipt": receipt}
        info["status"] = "SUBMITTED_TO_ISSUER_PARSER"
        info["original_file_bytes"] = len(body)
        info["original_file_sha256"] = full_hash

    joined = inspect_eight_bank_policy_raw_source_join_lab(
        source_packets_by_currency=packets, decision_at_utc=cutoff,
    )
    for currency, reason in joined["rejected_currencies"].items():
        rejected[currency] = "ISSUER_SPECIFIC_VALIDATOR_REJECTED:" + reason
        status[currency]["status"] = "REJECTED_BY_ISSUER_SOURCE_PARSER"
    for currency in joined["locally_checked_currencies"]:
        status[currency]["status"] = "LOCALLY_CHECKED_ONLY_NOT_SOURCE_ATTESTATION"

    checked = joined["locally_checked_currencies"]
    out.update({
        "state": (
            "LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO"
            if len(checked) == len(CURRENCIES) else
            "LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO"
        ),
        "reason": (
            "LOCAL_ORIGINAL_AND_RECEIPT_CHECKS_NOT_ISSUER_PIT_OR_CPI"
            if len(checked) == len(CURRENCIES) else
            "ARCHIVE_MISSING_REJECTED_OR_NOT_YET_CAPTURED"
        ),
        "currency_receipt_files_selected": len(packets)
            + len([1 for s in status.values()
                   if s.get("status") == "REJECTED_LOCAL_ARCHIVE"]),
        "currencies_with_local_original_bytes_validated": len(checked),
        "currencies_locally_checked": checked,
        "currencies_missing": [
            c for c in sorted(CURRENCIES)
            if c not in checked and c not in rejected
        ],
        "currencies_rejected": rejected,
        "currency_archive_status": status,
        "future_stamped_receipts_ignored": future_ignored,
        "pairs_with_both_policy_originals_locally_checked":
            joined["pairs_with_both_policy_sources_locally_checked_count"],
        "pairs_lacking_at_least_one_policy_original":
            joined["pairs_missing_or_rejecting_any_policy_source_count"],
        "pair_policy_source_coverage": joined["pair_policy_source_coverage"],
    })
    return out


__all__ = ("SCHEMA", "inspect_fx28_official_policy_archive_replay_lab")
