"""Read-only, fail-closed documentary outcome from an AM12 MT5 snapshot.

This is a *single-closed-bar label*, not an entry signal or a validation of
historical point-in-time features. It never connects to MT5, reads credentials,
or writes into the snapshot. Existing full-archive and calendar audits remain
mandatory and independent. A hash from the local archive is not broker proof.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import gzip
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any

from atlasquant_instrument_registry import FX_28
from atlasquant_trader_w1_ny17_dst_guard_lab import w1_ny17_dst_crossing_lab

SCHEMA = "ATLASQUANT_TRADER_MT5_CLOSED_BAR_OUTCOME_LAB_V1"
MT5_SCHEMA = "ATLASQUANT_MT5_CLOSED_BARS_LOCAL_LAB_V1"
COLUMNS = ("time_utc_epoch", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")
STEPS = {"D1": 86400, "W1": 604800}
COUNTS = {"D1": 500, "W1": 200}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_MANIFEST_BYTES = 200_000
MAX_COMPRESSED_BYTES = 1_000_000
MAX_DECOMPRESSED_BYTES = 800_000


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _price(value: Any) -> Decimal | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 40:
        return None
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and 0 < number < Decimal("1000000000") else None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_MT5_OUTCOME_BLOCKED", "reason": reason,
        "asset": None, "horizon": None, "target_open_utc": None,
        "target_close_utc": None, "outcome_direction_documentary": None,
        "start_price_documentary": None, "end_price_documentary": None,
        "raw_csv_sha256_verified": False, "raw_csv_sha256": None,
        "manifest_observed_at_utc": None, "target_prior_edge_nominal": False,
        "full_archive_84_series_reaudited_here": False,
        "broker_calendar_verified": False,
        "market_price_vintage_at_decision_verified": False,
        "prediction_precommit_externally_attested": False,
        "historical_directional_accuracy_validated": False,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0, "file_writes": 0,
        "research_only": True,
    }


def _load_json_no_duplicates(raw: bytes) -> Any:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError("DUPLICATE_JSON_KEY")
            out[k] = v
        return out
    return json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def _read_series_raw(root: Path, symbol: str, horizon: str) -> tuple[dict[str, Any], bytes]:
    manifests = sorted(root.glob("batch_??_manifest.json"))
    if len(manifests) != 7:
        raise ValueError("REQUIRES_SEVEN_BATCH_MANIFESTS")
    matching = []
    seen: set[tuple[str, str]] = set()
    for file in manifests:
        if file.is_symlink() or file.stat().st_size > MAX_MANIFEST_BYTES:
            raise ValueError("MANIFEST_UNSAFE_OR_OVERSIZED")
        document = _load_json_no_duplicates(file.read_bytes())
        if (not isinstance(document, dict) or document.get("schema") != MT5_SCHEMA
                or document.get("trade_authorized") is not False
                or document.get("research_only") is not True
                or document.get("prediction_available") is not False
                or document.get("broker_identity_independently_verified") is not False
                or document.get("historical_point_in_time_verified") is not False
                or not isinstance(document.get("records"), list)):
            raise ValueError("MANIFEST_SCHEMA_OR_PROVENANCE_INVALID")
        for record in document["records"]:
            if not isinstance(record, dict):
                raise ValueError("MANIFEST_RECORD_INVALID")
            s, tf = record.get("symbol"), record.get("timeframe")
            if s not in FX_28 or tf not in ("M15", "D1", "W1"):
                raise ValueError("MANIFEST_SYMBOL_OR_FRAME_INVALID")
            if (s, tf) in seen:
                raise ValueError("DUPLICATE_MANIFEST_SERIES")
            seen.add((s, tf))
            if (s, tf) == (symbol, horizon):
                matching.append(record)
    if len(matching) != 1:
        raise ValueError("TARGET_SERIES_MANIFEST_MISSING")
    record = matching[0]
    filename = f"{symbol}_{horizon}_closedbar.csv.gz"
    expected = COUNTS[horizon]
    if (record.get("snapshot_file") != filename
            or type(record.get("requested")) is not int
            or record["requested"] != expected
            or type(record.get("returned")) is not int
            or record["returned"] != expected
            or type(record.get("bar_position_start")) is not int
            or record["bar_position_start"] != 1
            or record.get("validation_errors") != []
            or not isinstance(record.get("sha256_uncompressed_csv"), str)
            or HEX64.fullmatch(record["sha256_uncompressed_csv"]) is None):
        raise ValueError("TARGET_MANIFEST_INCOMPLETE_OR_INVALID")
    path = root / filename
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_COMPRESSED_BYTES:
        raise ValueError("SNAPSHOT_FILE_MISSING_OR_UNSAFE")
    try:
        with gzip.open(path, "rb") as handle:
            raw = handle.read(MAX_DECOMPRESSED_BYTES + 1)
            if len(raw) > MAX_DECOMPRESSED_BYTES:
                raise ValueError("SNAPSHOT_DECOMPRESSED_OVERSIZED")
            # Detect concatenated or trailing gzip payload rather than silently ignoring.
            if handle.read(1):
                raise ValueError("SNAPSHOT_TRAILING_PAYLOAD")
    except (EOFError, OSError) as exc:
        raise ValueError("SNAPSHOT_GZIP_CORRUPT") from exc
    if sha256(raw).hexdigest() != record["sha256_uncompressed_csv"]:
        raise ValueError("SNAPSHOT_HASH_MISMATCH")
    return record, raw


def inspect_mt5_closedbar_outcome_lab(
    *, archive_root: Any, symbol: Any, horizon: Any, target_open_epoch: Any,
    decided_at: Any, prediction_locked_at: Any, as_of_utc: Any,
    prediction_sha256_claim: Any,
) -> dict[str, Any]:
    """Return one documentary D1/W1 bar label, never a tradable/validated bias.

    Caller must provide an already frozen prediction. This function does not
    certify that the claimed prediction timestamp/hash was independently locked.
    A nominal prior edge proves only *one* local interval; 32-bar regime
    context, 84-file archive integrity, broker calendar and PIT are separate.
    """
    out = _blocked("INVALID_INPUT_OR_CHRONOLOGY")
    decided, locked, now = (_utc(decided_at), _utc(prediction_locked_at), _utc(as_of_utc))
    if (not isinstance(symbol, str) or symbol not in FX_28
            or horizon not in STEPS or type(target_open_epoch) is not int
            or target_open_epoch <= 0 or any(v is None for v in (decided, locked, now))
            or not isinstance(prediction_sha256_claim, str)
            or HEX64.fullmatch(prediction_sha256_claim) is None):
        return out
    try:
        opened = datetime.fromtimestamp(target_open_epoch, tz=timezone.utc)
        closed = opened + timedelta(seconds=STEPS[horizon])
    except (OverflowError, ValueError, OSError):
        return out
    if not locked <= decided < opened < closed <= now:
        return out
    if horizon == "W1":
        dst_risk = w1_ny17_dst_crossing_lab(opened, closed)
        if dst_risk is not False:
            out["reason"] = ("W1_NY17_DST_CLOSE_REQUIRES_BROKER_VERIFICATION"
                             if dst_risk else "W1_NY_ZONEINFO_MISSING_OR_INVALID")
            return out
    if horizon == "D1" and target_open_epoch % 86400:
        return out
    if not isinstance(archive_root, (str, Path)):
        return out
    root = Path(archive_root)
    if not root.is_dir() or root.is_symlink():
        out["reason"] = "SNAPSHOT_ROOT_MISSING_OR_SYMLINK"
        return out
    try:
        record, raw = _read_series_raw(root, symbol, horizon)
        observed_text = record.get("observed_at_utc")
        if not isinstance(observed_text, str):
            raise ValueError("MANIFEST_CAPTURE_TIME_MISSING")
        observed = _utc(datetime.fromisoformat(observed_text.replace("Z", "+00:00")))
        if observed is None or not closed <= observed <= now:
            raise ValueError("CAPTURE_BEFORE_TARGET_CLOSE_OR_FUTURE")
        reader = csv.DictReader(StringIO(raw.decode("utf-8"), newline=""))
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError("CSV_FIELD_SCHEMA_INVALID")
        times: list[int] = []
        data: list[dict[str, Decimal]] = []
        for row in reader:
            if None in row or len(row) != len(COLUMNS):
                raise ValueError("CSV_ROW_SCHEMA_INVALID")
            stamp = row.get("time_utc_epoch")
            if not isinstance(stamp, str) or not stamp.isascii() or not stamp.isdecimal():
                raise ValueError("CSV_TIMESTAMP_INVALID")
            epoch = int(stamp)
            if epoch <= 0 or times and epoch <= times[-1]:
                raise ValueError("CSV_TIME_NOT_MONOTONIC")
            if horizon == "D1" and epoch % 86400:
                raise ValueError("D1_OFF_UTC_GRID")
            values = {field: _price(row[field]) for field in ("open", "high", "low", "close")}
            if any(v is None for v in values.values()):
                raise ValueError("CSV_INVALID_PRICE")
            if (values["high"] < max(values["open"], values["close"])
                    or values["low"] > min(values["open"], values["close"])):
                raise ValueError("CSV_BAD_OHLC")
            for field in ("tick_volume", "spread", "real_volume"):
                v = row.get(field)
                if not isinstance(v, str) or not v.isascii() or not v.isdecimal() or len(v) > 24:
                    raise ValueError("CSV_INVALID_VOLUME_OR_SPREAD")
            times.append(epoch)
            data.append(values)
        if len(times) != COUNTS[horizon]:
            raise ValueError("CSV_ROW_COUNT_INVALID")
        if datetime.fromtimestamp(times[-1], tz=timezone.utc) + timedelta(seconds=STEPS[horizon]) > observed:
            raise ValueError("CAPTURE_BEFORE_LATEST_CLOSED_BAR")
        if (record.get("earliest_open_utc") != _iso(datetime.fromtimestamp(times[0], timezone.utc))
                or record.get("latest_open_utc") != _iso(datetime.fromtimestamp(times[-1], timezone.utc))):
            raise ValueError("CSV_MANIFEST_TIME_MISMATCH")
        try:
            idx = times.index(target_open_epoch)
        except ValueError:
            raise ValueError("TARGET_BAR_NOT_IN_ARCHIVE") from None
        if idx == 0:
            raise ValueError("TARGET_WITHOUT_PRECEDING_BAR")
        if times[idx] - times[idx - 1] != STEPS[horizon]:
            raise ValueError("UNVERIFIED_GAP_DIRECTLY_BEFORE_TARGET")
        row = data[idx]
    except (ValueError, UnicodeError, TypeError, KeyError, IndexError, OverflowError, OSError, csv.Error) as exc:
        out["reason"] = str(exc) if isinstance(exc, ValueError) and str(exc) else "SNAPSHOT_PARSE_OR_IO_FAILED"
        return out
    direction = "ALTA" if row["close"] > row["open"] else (
        "BAIXA" if row["close"] < row["open"] else "SEM_VARIACAO")
    out.update({
        "state": "LAB_ARCHIVED_BAR_DOCUMENTARY_ONLY_NO_GO",
        "reason": "LOCAL_HASH_AND_SINGLE_BAR_LABEL_NOT_PIT_OR_BROKER_PROOF",
        "asset": f"{symbol[:3]}/{symbol[3:]}", "horizon": horizon,
        "target_open_utc": _iso(opened), "target_close_utc": _iso(closed),
        "outcome_direction_documentary": direction,
        "start_price_documentary": str(row["open"]),
        "end_price_documentary": str(row["close"]),
        "raw_csv_sha256_verified": True,
        "raw_csv_sha256": sha256(raw).hexdigest(),
        "manifest_observed_at_utc": _iso(observed),
        "target_prior_edge_nominal": True,
    })
    return out


__all__ = ["SCHEMA", "inspect_mt5_closedbar_outcome_lab"]
