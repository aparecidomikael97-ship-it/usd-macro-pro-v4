"""Bind 28 archived MT5 D1 CSV bytes to the seven-stage FX precision LAB gate.

Local SHA/manifest agreement is documentary only, not broker provenance or
proof of historical point-in-time availability. Historical recaptures AFTER a
claimed decision are refused, even if all hashes match. Read-only; no MT5,
signals, network, orders, scheduling, model fitting or file writes.
"""
from __future__ import annotations

import csv
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import gzip
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any

from atlasquant_trader_precision_gate_orchestrator_lab import (
    FX28_CANONICAL_SYMBOLS, ResearchPacket,
    inspect_fx_precision_orchestrator_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_D1_ARCHIVE_PRECISION_JOIN_LAB_V1"
MANIFEST_SCHEMA = "ATLASQUANT_MT5_CLOSED_BARS_LOCAL_LAB_V1"
CSV_FIELDS = ("time_utc_epoch", "open", "high", "low", "close",
              "tick_volume", "spread", "real_volume")
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_MANIFEST_BYTES = 90000
MAX_COMPRESSED_BYTES = 120000
MAX_CSV_BYTES = 120000
ROWS_D1 = 500


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _stamp(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (OverflowError, ValueError, TypeError):
        return None


def _no(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_D1_ARCHIVE_PRECISION_JOIN_BLOCKED",
        "reason": reason, "d1_archive_series_bytes_matched": 0,
        "d1_archive_bars_checked": 0, "manifest_records_reconciled": 0,
        "d1_date_coverage_from_archive": None,
        "latest_archive_capture_at_utc_claim": None,
        "precision_stage_reports": None, "research_candidate_direction": None,
        "source_and_historical_capture_independently_attested": False,
        "market_data_pit_independently_verified": False,
        "calendar_and_ny_close_broker_verified": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in pairs:
        if name in out:
            raise ValueError("DUPLICATE_JSON_KEYS")
        out[name] = value
    return out


def _csv_dates(raw: bytes, cutoff: datetime, declared_count: int) -> set:
    reader = csv.DictReader(StringIO(raw.decode("utf-8", "strict"), newline=""))
    if tuple(reader.fieldnames or ()) != CSV_FIELDS:
        raise ValueError("INVALID_D1_CSV_FIELDS")
    dates: set = set()
    last = -1
    n = 0
    for row in reader:
        if (not isinstance(row, dict) or None in row
                or set(row) != set(CSV_FIELDS)
                or any(type(v) is not str or not v for v in row.values())):
            raise ValueError("INVALID_D1_CSV_ROW")
        raw_epoch = row["time_utc_epoch"]
        if not raw_epoch.isascii() or not raw_epoch.isdigit():
            raise ValueError("INVALID_D1_EPOCH")
        epoch = int(raw_epoch)
        if epoch <= last or epoch % 86400 != 0:
            raise ValueError("D1_EPOCH_DUPLICATE_OUT_OF_ORDER_OR_OFF_GRID")
        bar_open = datetime.fromtimestamp(epoch, timezone.utc)
        if bar_open + timedelta(days=1) > cutoff:
            raise ValueError("UNFINISHED_OR_FUTURE_D1_BAR")
        try:
            o, h, l, c = (Decimal(row[k]) for k in ("open", "high", "low", "close"))
            if (not all(x.is_finite() and x > 0 for x in (o, h, l, c))
                    or h < max(o, c) or l > min(o, c) or h < l):
                raise ValueError("INVALID_D1_OHLC")
            for k in ("tick_volume", "spread", "real_volume"):
                v = row[k]
                if not v.isascii() or not v.isdigit():
                    raise ValueError("INVALID_D1_VOLUME_OR_SPREAD")
        except InvalidOperation as exc:
            raise ValueError("INVALID_D1_PRICE_NUMBER") from exc
        dt = bar_open.date()
        if dt in dates:
            raise ValueError("DUPLICATE_D1_CALENDAR_DATE")
        dates.add(dt)
        n += 1
        last = epoch
    if n != ROWS_D1 or n != declared_count:
        raise ValueError("D1_ROW_COUNT_MISMATCH")
    return dates


def inspect_d1_archive_precision_join_lab(
    *, archive_root: Any, packet: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Require 7 manifests/84 enumerated slots/28 hash-pinned D1 histories.

    The archive receipt must be captured before the *claimed* decision.
    All 28 CSVs are read even if one lacks the requested trading date.
    The orchestrator is recomputed with extracted attendance, not trusting
    an alleged 28-pair list from an upstream caller.
    """
    now = _utc(inspected_at_utc)
    if (not isinstance(packet, ResearchPacket) or now is None
            or not isinstance(archive_root, (str, Path))):
        return _no("INVALID_ARCHIVE_PACKET_OR_CLOCK")
    day = packet.d1_coverage_trading_date
    decision = _utc(packet.daily_decision_at_utc)
    if (type(day).__name__ != "date" or decision is None or decision > now):
        return _no("INVALID_TRADING_DATE_OR_DECISION_CLOCK")
    root = Path(archive_root)
    if not root.is_dir() or root.is_symlink():
        return _no("ARCHIVE_DIRECTORY_NOT_AVAILABLE_OR_SYMLINK")
    records: dict[str, dict] = {}
    all_slots: set[tuple[str, str]] = set()
    try:
        for offset in range(0, 28, 4):
            file = root / f"batch_{offset:02d}_manifest.json"
            if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_MANIFEST_BYTES:
                raise ValueError("MISSING_OR_UNSAFE_MANIFEST")
            manifest = json.loads(file.read_text("utf-8"), object_pairs_hook=_unique_pairs)
            rows = manifest.get("records")
            if (manifest.get("schema") != MANIFEST_SCHEMA
                    or manifest.get("research_only") is not True
                    or manifest.get("trade_authorized") is not False
                    or manifest.get("broker_identity_independently_verified") is not False
                    or manifest.get("historical_point_in_time_verified") is not False
                    or manifest.get("batch_start") != offset
                    or manifest.get("batch_count") != 4
                    or manifest.get("record_count") != 12
                    or not isinstance(rows, list) or len(rows) != 12):
                raise ValueError("INVALID_MANIFEST_BATCH_OR_SAFETY_FIELDS")
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("INVALID_MANIFEST_RECORD")
                sym, tf = row.get("symbol"), row.get("timeframe")
                if (sym not in FX28_CANONICAL_SYMBOLS or tf not in ("M15", "D1", "W1")
                        or (sym, tf) in all_slots):
                    raise ValueError("DUPLICATED_OR_UNKNOWN_COHORT_SLOT")
                all_slots.add((sym, tf))
                if tf == "D1":
                    records[sym] = row
        if (len(all_slots) != 84
                or len(records) != 28
                or all_slots != {(sym, tf) for sym in FX28_CANONICAL_SYMBOLS
                                 for tf in ("M15", "D1", "W1")}):
            raise ValueError("INCOMPLETE_28FX_3TF_MANIFEST_CENSUS")
        dates_by_symbol: dict[str, set] = {}
        capture_times = []
        for sym in FX28_CANONICAL_SYMBOLS:
            row = records[sym]
            path = root / f"{sym}_D1_closedbar.csv.gz"
            captured = _stamp(row.get("observed_at_utc"))
            digest = row.get("sha256_uncompressed_csv")
            if (row.get("snapshot_file") != path.name
                    or row.get("bar_position_start") != 1
                    or row.get("requested") != ROWS_D1
                    or row.get("returned") != ROWS_D1
                    or row.get("validation_errors") != []
                    or not isinstance(digest, str) or HEX.fullmatch(digest) is None
                    or captured is None or captured > decision
                    or path.is_symlink() or not path.is_file()
                    or path.stat().st_size > MAX_COMPRESSED_BYTES):
                raise ValueError("INVALID_OR_LATE_D1_MANIFEST_OR_ARCHIVE")
            with gzip.open(path, "rb") as stream:
                raw = stream.read(MAX_CSV_BYTES + 1)
            if len(raw) > MAX_CSV_BYTES:
                raise ValueError("D1_ARCHIVE_DECOMPRESSION_LIMIT")
            if sha256(raw).hexdigest() != digest:
                raise ValueError("D1_CSV_SHA256_DOES_NOT_MATCH_MANIFEST")
            dates = _csv_dates(raw, decision, row["returned"])
            if not dates or captured < (datetime.fromordinal(max(dates).toordinal())
                                        .replace(tzinfo=timezone.utc) + timedelta(days=1)):
                raise ValueError("D1_ARCHIVE_CAPTURE_PREDATES_BAR_CLOSE")
            if (_stamp(row.get("earliest_open_utc")) !=
                    datetime.combine(min(dates), datetime.min.time(), timezone.utc)
                    or _stamp(row.get("latest_open_utc")) !=
                    datetime.combine(max(dates), datetime.min.time(), timezone.utc)):
                raise ValueError("D1_ARCHIVE_FIRST_LAST_MANIFEST_MISMATCH")
            dates_by_symbol[sym] = dates
            capture_times.append(captured)
    except (KeyError, TypeError, ValueError, OSError, EOFError, UnicodeError,
            OverflowError, json.JSONDecodeError) as exc:
        return _no(f"ARCHIVE_REJECTED_{type(exc).__name__}_{str(exc)[:80]}")
    found = tuple(sym for sym in FX28_CANONICAL_SYMBOLS if day in dates_by_symbol[sym])
    latest = max(capture_times)
    # If caller provided coverage assertions, they must exactly agree with
    # the extracted cohort; it cannot override missing historical bars.
    caller_list = packet.d1_coverage_present_symbols
    caller_time = _utc(packet.d1_coverage_observed_at_utc)
    if caller_list is not None and (
            not isinstance(caller_list, (list, tuple))
            or tuple(caller_list) != found):
        return _no("CALLER_COVERAGE_DISAGREES_WITH_ARCHIVED_CSV_DATES")
    if caller_time is not None and caller_time != latest:
        return _no("CALLER_CAPTURE_TIME_DISAGREES_WITH_MANIFESTS")
    fresh_packet = replace(
        packet, d1_coverage_present_symbols=found,
        d1_coverage_observed_at_utc=latest)
    precision = inspect_fx_precision_orchestrator_lab(
        packet=fresh_packet, inspected_at_utc=now)
    complete = precision.get("state") == "LAB_PRECISION_RESEARCH_CANDIDATE_UNATTESTED"
    output = _no("SOURCE_AND_MACRO_UNATTESTED_EVEN_WHEN_ARCHIVE_BYTES_MATCH")
    output.update({
        "state": ("LAB_D1_ARCHIVE_PRECISION_DOCUMENTARY_CANDIDATE_NO_GO" if complete
                  else "LAB_D1_ARCHIVE_PRECISION_ABSTAIN"),
        "reason": ("CONSISTENT_LOCAL_BYTES_AND_SEVEN_RESEARCH_STAGES_ONLY" if complete
                   else "ARCHIVE_OR_OTHER_RESEARCH_GATE_REJECTS_CANDIDATE"),
        "d1_archive_series_bytes_matched": 28,
        "d1_archive_bars_checked": ROWS_D1 * 28,
        "manifest_records_reconciled": 84,
        "d1_date_coverage_from_archive": {
            "date": day.isoformat(), "present": len(found),
            "missing": [s for s in FX28_CANONICAL_SYMBOLS if s not in found],
        },
        "latest_archive_capture_at_utc_claim": latest.isoformat(),
        "precision_stage_reports": precision["stage_reports"],
        "research_candidate_direction": (
            precision["research_candidate_direction"] if complete else None),
    })
    return output


__all__ = ["SCHEMA", "inspect_d1_archive_precision_join_lab"]
