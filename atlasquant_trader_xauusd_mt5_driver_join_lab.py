"""Offline bridge from audited XAUUSD MT5 bars to claimed macro readiness.

Gold prices are read from a local collector archive. Macro claims are supplied
by the caller. Neither is independently source/timestamp authenticated; this
module never returns a direction, probability, signal or trade authorization.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import gzip
from hashlib import sha256
from io import StringIO
from pathlib import Path
import re
from typing import Any

from atlasquant_mt5_xauusd_archive_audit_lab import (
    MAX_CSV_BYTES, audit_xauusd_closedbar_archive_lab,
)
from atlasquant_trader_xauusd_macro_readiness_lab import (
    DRIVER_SPECS, GoldDriverClaim, inspect_xauusd_macro_driver_readiness_lab,
)

SCHEMA = "ATLASQUANT_TRADER_XAUUSD_MT5_PRICE_MACRO_JOIN_LAB_V1"
MAX_CAPTURE_AGE = timedelta(hours=1)
MAX_BAR_CLOSE_AGE_AT_CAPTURE = timedelta(minutes=45)
BAR_SPAN = timedelta(minutes=15)
PRICE_FORMAT = re.compile(r"[1-9][0-9]{0,3}(?:\.[0-9]{1,6})?\Z")
MACRO_DRIVERS = frozenset(("US_REAL_YIELD_10Y", "US_BROAD_DOLLAR"))


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_XAUUSD_PRICE_MACRO_JOIN_BLOCKED",
        "reason": reason, "asset": "METAL:XAUUSD",
        "audited_local_bars": 0, "price_claims_derived": 0,
        "price_claim_rows": [], "macro_claims_supplied": 0,
        "all_three_driver_claims_present": False,
        "macro_driver_readiness_state": None,
        "price_manifest_and_csv_locally_consistent": False,
        "broker_identity_authenticated": False,
        "price_capture_time_independently_authenticated": False,
        "macro_release_times_independently_authenticated": False,
        "historical_point_in_time_verified": False,
        "out_of_sample_gold_accuracy_validated": False,
        "research_candidate_direction": None, "gold_bias": None,
        "calibrated_probability": None, "validated_accuracy": None,
        "operational_bias": "AGUARDAR", "can_feed_live_radar": False,
        "publishable": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "file_writes": 0, "http_requests": 0, "new_cost_brl": 0,
    }


def join_xauusd_price_archive_to_macro_claims_lab(
    capture_directory: Any, *, macro_claims: Any,
    horizon: Any, decision_at_utc: Any, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Derive TWO M15 closes from a verified archive; abstain operationally.

    The archive clock is local, alleged UTC. Bar closing time is *assumed*
    as opening epoch + 15 minutes; it is not an MT5/broker publication receipt.
    """
    out = _blocked("INVALID_INPUT_HORIZON_OR_CLOCK")
    decision = _utc(decision_at_utc)
    evaluated = _utc(evaluated_at_utc)
    if (not isinstance(capture_directory, Path)
            or horizon not in ("D1", "W1")
            or decision is None or evaluated is None or decision > evaluated
            or not isinstance(macro_claims, (tuple, list))
            or len(macro_claims) > 4
            or any(not isinstance(v, GoldDriverClaim)
                   or v.driver not in MACRO_DRIVERS for v in macro_claims)):
        return out
    audit = audit_xauusd_closedbar_archive_lab(capture_directory)
    if audit["status"] != "LOCAL_XAUUSD_ARCHIVE_INTEGRITY_PASS_UNATTESTED":
        out["reason"] = "PRICE_ARCHIVE_LOCAL_INTEGRITY_NOT_PASSED"
        return out
    out["audited_local_bars"] = audit["verified_bars"]
    out["price_manifest_and_csv_locally_consistent"] = True

    try:
        stamp = datetime.strptime(capture_directory.name, "XAUUSD_%Y%m%dT%H%M%SZ")
        captured = stamp.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        out["reason"] = "CAPTURE_DIRECTORY_CLOCK_INVALID"
        return out
    if not captured <= decision <= captured + MAX_CAPTURE_AGE:
        out["reason"] = "PRICE_SNAPSHOT_NOT_PREDECISION_OR_STALE"
        return out

    price_path = capture_directory / "XAUUSD_M15_closedbar.csv.gz"
    try:
        with gzip.open(price_path, "rb") as archived:
            raw = archived.read(MAX_CSV_BYTES + 1)
        if (len(raw) > MAX_CSV_BYTES
                or sha256(raw).hexdigest() !=
                audit["timeframes"]["M15"]["sha256_uncompressed_csv"]):
            raise ValueError("POST_AUDIT_CSV_CHANGED_OR_OVERSIZED")
        rows = list(csv.DictReader(StringIO(raw.decode("utf-8"))))
        if len(rows) != 3000:
            raise ValueError("M15_ROW_COUNT_CHANGED_AFTER_AUDIT")
        last_two = rows[-2:]
        opens = [datetime.fromtimestamp(int(row["time_utc_epoch"]), timezone.utc)
                 for row in last_two]
    except (OSError, EOFError, ValueError, TypeError, UnicodeError, KeyError,
            OverflowError) as exc:
        out["reason"] = "PRICE_ARCHIVE_CHANGED_DURING_JOIN:" + str(exc)[:55]
        return out
    if (opens[1] - opens[0] != BAR_SPAN
            or opens[1].isoformat() != audit["timeframes"]["M15"]["last_open_utc"]
            or opens[0] + BAR_SPAN > captured
            or opens[1] + BAR_SPAN > captured
            or captured - (opens[1] + BAR_SPAN) > MAX_BAR_CLOSE_AGE_AT_CAPTURE):
        out["reason"] = "M15_RECENT_TWO_BARS_NOT_SEQUENTIAL_CLOSED_AND_FRESH"
        return out

    claimed: list[GoldDriverClaim] = []
    summaries: list[dict[str, Any]] = []
    digest = audit["timeframes"]["M15"]["sha256_uncompressed_csv"]
    for row, opened in zip(last_two, opens):
        raw_close = row["close"]
        # Do not silently round non-representable MT5 numbers to 6dp.
        if type(raw_close) is not str or PRICE_FORMAT.fullmatch(raw_close) is None:
            out["reason"] = "GOLD_PRICE_PRECISION_NOT_SUPPORTED_WITHOUT_ROUNDING"
            return out
        try:
            if Decimal(raw_close) <= 0:
                raise ValueError("NONPOSITIVE_CLOSE")
        except (InvalidOperation, ValueError):
            out["reason"] = "GOLD_CLOSE_VALUE_INVALID"
            return out
        label = opened.strftime("%Y-%m-%dT%H:%M:%SZ")
        claim = GoldDriverClaim(
            driver="XAUUSD_BROKER_PRICE",
            source_id=DRIVER_SPECS["XAUUSD_BROKER_PRICE"][0],
            unit=DRIVER_SPECS["XAUUSD_BROKER_PRICE"][1],
            sampling="M15", observation_label=label,
            value_claim=raw_close, published_at=opened + BAR_SPAN,
            captured_at=captured, original_sha256_claim=digest,
        )
        claimed.append(claim)
        summaries.append({
            "m15_open_utc_local_claim": label,
            "assumed_closed_at_utc_not_attested": (opened + BAR_SPAN).isoformat(),
            "captured_at_utc_local_claim": captured.isoformat(),
            "close_usd_claim_from_locally_audited_csv": raw_close,
            "batch_csv_sha256_self_consistency_only": digest,
        })
    checked = inspect_xauusd_macro_driver_readiness_lab(
        tuple(macro_claims) + tuple(claimed),
        instrument="METAL:XAUUSD", horizon=horizon,
        decision_at_utc=decision, evaluated_at_utc=evaluated,
    )
    out.update({
        "price_claims_derived": 2,
        "price_claim_rows": summaries,
        "macro_claims_supplied": len(macro_claims),
        "macro_driver_readiness_state": checked["state"],
        "all_three_driver_claims_present": checked["all_three_driver_claims_present"],
    })
    if checked["state"] == "LAB_XAUUSD_DRIVER_READINESS_BLOCKED":
        out["reason"] = "MACRO_READINESS_BLOCKED:" + checked["reason"]
        return out
    out["state"] = "LAB_XAUUSD_PRICE_MACRO_CLAIMS_ONLY_NO_GO"
    out["reason"] = (
        "ALL_DRIVER_CLAIMS_PRESENT_BUT_ORIGIN_TIMES_OOS_AND_NEWS_UNATTESTED"
        if checked["all_three_driver_claims_present"]
        else "PRICE_CLAIMS_LOCAL_ONLY_MACRO_TWO_OBSERVATIONS_PER_DRIVER_MISSING"
    )
    return out


__all__ = ["SCHEMA", "join_xauusd_price_archive_to_macro_claims_lab"]
