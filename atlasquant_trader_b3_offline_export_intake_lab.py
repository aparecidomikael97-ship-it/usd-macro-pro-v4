"""Offline candidate CSV intake for post-Copom B3 futures LAB (not market data).

No fetching, scraping, API, scheduled task, terminal connection, file write,
Render or trading. Only user-provided CSV or synthetic fixtures may be
inspected after their clock, source claims and format are validated.
The SHA-256 of user-controlled bytes is NOT a source-origin proof; neither
the last pre-event tick nor first next-session tick can be identified from
only two sample rows. All such outputs are UNVERIFIED / NOT ACTIONABLE.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping

from atlasquant_trader_copom_b3_session_reaction_lab import (
    SCHEDULE, SESSION_START, PROPOSED_NEXT_START,
)

SCHEMA = "ATLASQUANT_TRADER_B3_OFFLINE_USER_EXPORT_INTAKE_LAB_V1"
DENIED = "LAB_B3_OFFLINE_EXPORT_REFUSED"
PENDING = "LAB_B3_OFFLINE_EXPORT_SOURCE_RIGHTS_UNATTESTED"
SYNTHETIC = "LAB_B3_OFFLINE_SYNTHETIC_CSV_VALIDATED"
COLUMNS = ("instrument", "contract_id", "session_role", "quote_type",
           "observed_at_utc", "price_points")
MANIFEST_KEYS = frozenset((
    "schema", "declared_collection_method", "declared_origin_label",
    "declared_source_reference", "declared_rights_status",
    "collection_was_automated", "csv_sha256", "fixture_mode",
))
SOURCE_METHODS = frozenset(("USER_MANUAL_EXPORT_UNVERIFIED",
                            "SYNTHETIC_FIXTURE"))
RIGHTS_STATUS = "NOT_INDEPENDENTLY_REVIEWED"
SAFE_USER_SOURCE_LABEL = re.compile(r"^[A-Za-z0-9 _.-]{4,80}$")
SAFE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
PRICE_RE = re.compile(r"^[1-9][0-9]{0,8}(?:\.[0-9]{1,4})?$")
TZ = timezone.utc


def _base(status: str, reason: str | None) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": status, "reason": reason,
        "csv_fields_valid": False,
        "csv_integrity_matches_claim": False,
        "matched_pairs": 0, "pair_rows": [],
        "user_provided_origin_independently_verified": False,
        "market_data_access_rights_independently_verified": False,
        "manual_export_allowed_by_provider_verified": False,
        "source_terms_for_cloud_storage_reviewed": False,
        "b3_official_raw_trades_authenticated": False,
        "full_market_tick_history_available": False,
        "pre_row_is_last_actual_trade_proven": False,
        "post_row_is_first_actual_trade_proven": False,
        "same_contract_claim_independently_confirmed": False,
        "first_next_session_liquidity_verified": False,
        "market_reaction_real_verified": False,
        "copom_caused_the_gap": False,
        "market_price_prediction_accuracy": None,
        "directional_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "automated_collection_enabled": False,
        "b3_boletins_ai_scraping_enabled": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "render_configuration_changed": False,
        "paid_provider_approved": False,
    }


def _clock(x: Any) -> datetime | None:
    if not isinstance(x, str) or not x.endswith("Z") or len(x) > 40:
        return None
    try:
        d = datetime.fromisoformat(x[:-1] + "+00:00")
    except (ValueError, OverflowError):
        return None
    return d.astimezone(TZ) if d.utcoffset() is not None else None


def _price(x: Any) -> Decimal | None:
    if not isinstance(x, str) or not PRICE_RE.fullmatch(x):
        return None
    try:
        d = Decimal(x)
    except InvalidOperation:
        return None
    return d if d.is_finite() and 0 < d <= 100000000 else None


def inspect_b3_offline_price_export_lab(
    csv_content: Any, manifest: Any, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Inspect at most four sample rows. No real-price source claim is proven."""
    if (not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None):
        raise ValueError("Evaluation time must carry timezone")
    now = evaluated_at.astimezone(TZ)
    if now < datetime(2026, 11, 3, 15, tzinfo=TZ):
        return _base(DENIED, "Cannot backdate intake research")
    if (not isinstance(csv_content, bytes) or not 50 <= len(csv_content) <= 4000
            or b"\x00" in csv_content or b"\r" in csv_content):
        return _base(DENIED, "CSV byte size, encoding or line endings invalid")
    if (not isinstance(manifest, Mapping) or set(manifest) != MANIFEST_KEYS):
        return _base(DENIED, "Missing provenance manifest or injected authority")
    if (manifest["schema"] != SCHEMA
            or type(manifest["declared_collection_method"]) is not str
            or manifest["declared_collection_method"] not in SOURCE_METHODS
            or manifest["declared_rights_status"] != RIGHTS_STATUS
            or manifest["collection_was_automated"] is not False
            or not isinstance(manifest["fixture_mode"], bool)
            or not isinstance(manifest["declared_origin_label"], str)
            or not SAFE_USER_SOURCE_LABEL.fullmatch(manifest["declared_origin_label"])
            or not isinstance(manifest["declared_source_reference"], str)
            or len(manifest["declared_source_reference"]) > 180
            or re.fullmatch(r"USER_NOTE:[A-Za-z0-9 _./-]{1,160}",
                                manifest["declared_source_reference"]) is None
            or not isinstance(manifest["csv_sha256"], str)
            or not SAFE_DIGEST.fullmatch(manifest["csv_sha256"])
            or sha256(csv_content).hexdigest() != manifest["csv_sha256"]):
        return _base(DENIED, "Source claim, source method or local CSV digest altered")
    fixture = manifest["fixture_mode"]
    if (fixture and manifest["declared_collection_method"] != "SYNTHETIC_FIXTURE"
            or not fixture and manifest["declared_collection_method"]
            != "USER_MANUAL_EXPORT_UNVERIFIED"):
        return _base(DENIED, "Synthetic sample and manual-export provenance mislabeled")
    try:
        text = csv_content.decode("utf-8", errors="strict")
    except UnicodeError:
        return _base(DENIED, "CSV must be UTF-8 strict")
    if (not text.endswith("\n") or "\n\n" in text or "\t" in text
            or "\ufeff" in text or any(ord(c) < 32 and c not in "\n\t" for c in text)):
        return _base(DENIED, "Unsafe CSV control characters or layout")
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if reader.fieldnames != list(COLUMNS):
            return _base(DENIED, "Column names and order must match offline trade schema")
        rows = list(reader)
    except (csv.Error, ValueError):
        return _base(DENIED, "Malformed CSV quoting or table")
    if len(rows) not in (2, 4):
        return _base(DENIED, "Expected one pre and one post row for each of one or two instruments")
    data = {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != set(COLUMNS)
                or any(not isinstance(row[k], str) for k in COLUMNS)):
            return _base(DENIED, "Blank or malformed CSV fields")
        instrument = row["instrument"]
        if instrument not in ("WIN", "WDO"):
            return _base(DENIED, "Unsupported instrument")
        if row["session_role"] not in ("PRE_20261104", "POST_20261105"):
            return _base(DENIED, "Session role must be explicit")
        symbol = (SCHEDULE[instrument]["synthetic_contract"] if fixture
                  else SCHEDULE[instrument]["real_contract_candidate"])
        kind = ("SIMULATED_REGULAR_TRADE_TICK" if fixture else
                "PROVIDER_DECLARED_EXECUTED_TRADE_UNVERIFIED")
        if row["contract_id"] != symbol or row["quote_type"] != kind:
            return _base(DENIED, "Mixed contract, price adjustment, settlement or false provenance")
        time,price = _clock(row["observed_at_utc"]),_price(row["price_points"])
        if time is None or price is None or time > now:
            return _base(DENIED, "Invalid, unavailable or future alleged trade")
        limit = SCHEDULE[instrument]
        if row["session_role"] == "PRE_20261104":
            if not (SESSION_START.astimezone(TZ) <= time <
                    limit["pre_window_end"].astimezone(TZ)):
                return _base(DENIED, "PRE price outside regular session before Copom")
        else:
            if not (PROPOSED_NEXT_START.astimezone(TZ) <= time <
                    limit["next_window_end"].astimezone(TZ)):
                return _base(DENIED, "POST price outside candidate following regular session")
        key = (instrument, row["session_role"])
        if key in data:
            return _base(DENIED, "Repeated tick/session role, possible cherry-picking")
        data[key] = {"contract": symbol, "clock": time, "price": price}
    instruments = {x[0] for x in data}
    if len(data) != 2 * len(instruments):
        return _base(DENIED, "One pre and one post tick per instrument required")
    output = []
    for instrument in sorted(instruments):
        pre = data[(instrument, "PRE_20261104")]
        post = data[(instrument, "POST_20261105")]
        if pre["contract"] != post["contract"]:
            return _base(DENIED, "Cross-contract comparison")
        # Session-boundary distances describe only how the two supplied
        # samples relate to SCHEDULED boundaries, NOT whether they were
        # actual last/first exchange trades or a tradable opening gap.
        schedule = SCHEDULE[instrument]
        pre_close_utc = schedule["pre_window_end"].astimezone(TZ)
        post_open_utc = PROPOSED_NEXT_START.astimezone(TZ)
        pre_seconds_to_close = int((pre_close_utc - pre["clock"]).total_seconds())
        post_seconds_from_open = int((post["clock"] - post_open_utc).total_seconds())
        elapsed_seconds = int((post["clock"] - pre["clock"]).total_seconds())
        gap = ((post["price"] / pre["price"] - 1) * Decimal(100))
        output.append({
            "instrument": instrument,
            "declared_contract": pre["contract"],
            "contract_is_synthetic": fixture,
            "pre_trade_claimed_at_utc": pre["clock"].isoformat(),
            "post_trade_claimed_at_utc": post["clock"].isoformat(),
            "pre_sample_seconds_before_scheduled_close": pre_seconds_to_close,
            "post_sample_seconds_after_candidate_open": post_seconds_from_open,
            "calendar_elapsed_seconds_between_samples": elapsed_seconds,
            "label": "SAMPLED_POINTS_NOT_VERIFIED_OPENING_GAP",
            "sample_timestamps_are_exchange_attested": False,
            "official_session_exception_calendar_checked": False,
            "is_verified_opening_gap": False,
            "pre_price_claimed": str(pre["price"]),
            "post_price_claimed": str(post["price"]),
            "arithmetical_candidate_gap_percent": str(gap.quantize(Decimal("0.0001"))),
            "provisional_direction_from_two_claimed_prices": (
                "ALTA" if gap > 0 else "BAIXA" if gap < 0 else "NEUTRO"),
            "verified_last_pre_event_trade": False,
            "verified_first_post_event_trade": False,
            "verified_tradable_gap": False,
            "copom_price_forecast_success": None,
        })
    return {
        **_base(SYNTHETIC if fixture else PENDING, None),
        "csv_fields_valid": True, "csv_integrity_matches_claim": True,
        "matched_pairs": len(output), "pair_rows": output,
        "origin_label_unverified": manifest["declared_origin_label"],
        "declared_source_reference_unverified": manifest["declared_source_reference"],
        "fixture_mode": fixture,
        "data_is_not_live": True,
        "why_not_validated_market_reaction": (
            "Boundary time distances are computed from scheduled session "
            "hours, not verified exchange ticks. The two declared samples "
            "cannot prove last/first B3 trades, opening gap, license, source, "
            "actual Copom publication, execution or Copom causality."
        ),
    }


__all__ = ["SCHEMA", "DENIED", "PENDING", "SYNTHETIC", "COLUMNS",
           "inspect_b3_offline_price_export_lab"]
