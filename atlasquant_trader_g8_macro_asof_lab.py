"""LAB-only G8 FX pair macro-release as-of audit: chronology, not bias.

Prevents structural look-ahead: no record may claim publication or collection
AFTER a decision. All timestamps and hashes are caller assertions; independent
publication/vintage attestation remains missing. No source authenticity,
execution data, scores, statistics of directional accuracy or trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from calendar import monthrange
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_G8_MACRO_ASOF_PAIR_LAB_V1"
ENVELOPE = "ATLASQUANT_TRADER_MACRO_RELEASE_RECEIPTS_LAB_V1"
EXPECTED = ("CPI_YOY", "POLICY_RATE")
FRESH_DAYS = {"CPI_YOY": 60, "POLICY_RATE": 120}
# A quarterly CPI is refreshed on a different cadence from a monthly CPI.
# This is a structural freshness allowance, NOT a source/forecast attestation.
QUARTERLY_CPI_FRESH_DAYS = 120
# A newly reissued *old* observation is not new economic information.
# These deliberately conservative LAB ceilings measure time since the end of
# the observation period; they are NOT issuer-confirmed release schedules.
# Fail closed when a period is too old even if a page was updated yesterday.
OBSERVATION_AGE_LIMIT_DAYS = {
    ("CPI_YOY", "MONTHLY"): 95,
    ("CPI_YOY", "QUARTERLY"): 125,
    ("POLICY_RATE", "MONTHLY"): 155,
}
SOURCES = frozenset(("OFFICIAL_STATISTICS_OFFICE", "CENTRAL_BANK"))
ENVELOPE_FIELDS = frozenset(("schema", "pair", "decision_at_utc", "records"))
RECORD_FIELDS = frozenset((
    "currency", "indicator", "observation_period", "value",
    "published_at_utc", "captured_at_utc", "source_type", "source_sha256",
))
UTC = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
MONTH = re.compile(r"20\d\d-(?:0[1-9]|1[0-2])\Z")
QUARTER = re.compile(r"(20\d\d)-Q([1-4])\Z")
NUMBER = re.compile(r"-?(?:0|[1-9]\d{0,2})(?:\.\d{1,4})?\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_BYTES = 48_000
MAX_RECORDS = 32


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "pair": None, "decision_at_utc": None, "input_sha256": None,
        "records_seen": 0, "pair_currencies": [], "selected_observations": {},
        "missing_or_stale": [], "all_metadata_chronological": False,
        "all_required_indicators_present": False,
        "timestamp_source": "CALLER_ASSERTED_NOT_INDEPENDENT",
        "independent_release_time_attested": False,
        "source_origin_authenticated": False,
        "source_raw_bytes_independently_verified": False,
        "point_in_time_vintage_independently_verified": False,
        "macro_values_verified_by_issuer": False,
        "independent_broker_m15_prices_verified": False,
        "validated_prediction_count": 0,
        "validated_directional_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _json_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _parse(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, bytes) or not 32 <= len(raw) <= MAX_BYTES:
        return None
    try:
        value = json.loads(raw.decode("utf-8", "strict"),
                           object_pairs_hook=_json_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        return value if isinstance(value, dict) else None
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
        return None


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or UTC.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _asof(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _value(raw: Any) -> Decimal | None:
    if not isinstance(raw, str) or NUMBER.fullmatch(raw) is None:
        return None
    try:
        val = Decimal(raw)
        return val if val.is_finite() and Decimal("-50") <= val <= Decimal("100") else None
    except InvalidOperation:
        return None


def _observation_period(raw: Any, *, indicator: str, published: datetime) -> tuple[str, int] | None:
    """Normalize a monthly or CPI-only quarterly period without inventing dates.

    Quarterly observations need a completed quarter before their announced
    value can plausibly be known. The publication itself still needs separate
    independent evidence to become eligible for ex-ante use.
    """
    if not isinstance(raw, str):
        return None
    if MONTH.fullmatch(raw):
        return ("MONTHLY", FRESH_DAYS[indicator]) if raw <= published.strftime("%Y-%m") else None
    match = QUARTER.fullmatch(raw)
    if match is None or indicator != "CPI_YOY":
        return None
    year, quarter = int(match.group(1)), int(match.group(2))
    end_month = quarter * 3
    end_day = monthrange(year, end_month)[1]
    if (year, end_month, end_day) > (published.year, published.month, published.day):
        return None
    return "QUARTERLY", QUARTERLY_CPI_FRESH_DAYS


def _period_rank(raw: str) -> tuple[int, int]:
    """Sort economic observation periods, NOT the time a page was reissued.

    The caller may supply a later publication of an older observation.
    Comparing publication timestamps would incorrectly call that older period
    the latest economic observation.
    """
    quarter = QUARTER.fullmatch(raw)
    if quarter is not None:
        return int(quarter.group(1)), int(quarter.group(2)) * 3
    year, month = raw.split("-")
    return int(year), int(month)


def _period_end_date(raw: str):
    year, month = _period_rank(raw)
    return datetime(year, month, monthrange(year, month)[1], tzinfo=timezone.utc).date()


def inspect_g8_pair_macro_asof_lab(raw: Any, *, as_of_utc: Any) -> dict[str, Any]:
    """Check metadata for TWO currency sides; do not infer bias from values.

    All source metadata is supplied by the caller and can be backdated.
    This cannot prove historically available releases. It only rejects
    inconsistent/future timestamps and identifies missing/stale indicators.
    """
    out = _blocked("INVALID_ENVELOPE_OR_AS_OF")
    obj, now = _parse(raw), _asof(as_of_utc)
    if (now is None or obj is None or set(obj) != ENVELOPE_FIELDS
            or obj["schema"] != ENVELOPE
            or not isinstance(obj["pair"], str)
            or obj["pair"] not in OFFICIAL_PAIRS
            or not isinstance(obj["records"], list)
            or not 1 <= len(obj["records"]) <= MAX_RECORDS):
        return out
    decision = _time(obj["decision_at_utc"])
    if decision is None or decision > now:
        out["reason"] = "DECISION_CLOCK_FUTURE_OR_INVALID"
        return out
    base, quote = split_pair(obj["pair"])
    # Keep only pair-specific economic evidence, never a third currency's data.
    accepted: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in obj["records"]:
        if not isinstance(row, dict) or set(row) != RECORD_FIELDS:
            out["reason"] = "RELEASE_SCHEMA_INVALID"
            return out
        cur, indicator = row["currency"], row["indicator"]
        if (not isinstance(cur, str) or cur not in (base, quote)
                or not isinstance(indicator, str) or indicator not in EXPECTED
                or not isinstance(row["source_type"], str)
                or row["source_type"] not in SOURCES
                or not isinstance(row["source_sha256"], str)
                or HEX.fullmatch(row["source_sha256"]) is None
                or _value(row["value"]) is None):
            out["reason"] = "RELEASE_SOURCE_VALUE_OR_PAIR_INVALID"
            return out
        pub, captured = _time(row["published_at_utc"]), _time(row["captured_at_utc"])
        frequency = (_observation_period(row["observation_period"], indicator=indicator,
                                         published=pub) if pub is not None else None)
        if (pub is None or captured is None or frequency is None
                or not pub <= captured <= decision):
            out["reason"] = "RELEASE_LOOKAHEAD_OR_CHRONOLOGY_INVALID"
            return out
        key = (cur, indicator, row["observation_period"])
        if key in accepted:
            # Never select a revised value silently on an existing period.
            out["reason"] = "DUPLICATE_INDICATOR_PERIOD_REVISION_AMBIGUOUS"
            return out
        accepted[key] = row
    selections: dict[str, dict[str, Any]] = {}
    missing = []
    for currency in (base, quote):
        selections[currency] = {}
        for indicator in EXPECTED:
            candidates = [r for (cur, name, _), r in accepted.items()
                          if cur == currency and name == indicator]
            if not candidates:
                missing.append(f"{currency}:{indicator}:MISSING")
                continue
            frequencies = {
                _observation_period(r["observation_period"], indicator=indicator,
                                    published=_time(r["published_at_utc"]))[0]
                for r in candidates
            }
            if len(frequencies) != 1:
                # Monthly and quarterly inflation are not one continuous
                # series. A source-methodology transition needs a new gate.
                out["reason"] = "MIXED_INDICATOR_OBSERVATION_FREQUENCIES"
                return out
            latest = max(candidates, key=lambda r: (
                _period_rank(r["observation_period"]), r["published_at_utc"]))
            published = _time(latest["published_at_utc"])
            frequency, fresh_days = _observation_period(
                latest["observation_period"], indicator=indicator, published=published)
            age_days = (decision - published).total_seconds() / 86400
            period_age_days = (decision.date() - _period_end_date(
                latest["observation_period"])).days
            period_limit = OBSERVATION_AGE_LIMIT_DAYS[(indicator, frequency)]
            if age_days > fresh_days or period_age_days > period_limit:
                missing.append(f"{currency}:{indicator}:STALE")
                continue
            # Never include unverified numeric readings in the output: this
            # gate is not a scored source of economic strength or direction.
            selections[currency][indicator] = {
                "observation_period": latest["observation_period"],
                "observation_frequency": frequency,
                "freshness_limit_days": fresh_days,
                "observation_period_age_days": period_age_days,
                "observation_period_age_limit_days": period_limit,
                "published_at_utc_claim": latest["published_at_utc"],
                "captured_at_utc_claim": latest["captured_at_utc"],
                "source_type_claim": latest["source_type"],
                "source_sha256_claim": latest["source_sha256"],
                "measurement_verified": False,
            }
    complete = not missing
    out.update({
        "state": ("LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED" if complete
                  else "LAB_PAIR_MACRO_METADATA_INCOMPLETE_UNATTESTED"),
        "reason": ("CALLER_SOURCE_TIMESTAMPS_AND_ORIGIN_UNATTESTED" if complete
                   else "MISSING_OR_STALE_PAIR_MACRO_EVIDENCE"),
        "pair": obj["pair"], "decision_at_utc": decision.isoformat(),
        "input_sha256": sha256(raw).hexdigest(),
        "records_seen": len(accepted), "pair_currencies": [base, quote],
        "selected_observations": selections, "missing_or_stale": missing,
        "all_metadata_chronological": True,
        "all_required_indicators_present": complete,
    })
    return out


__all__ = ["SCHEMA", "ENVELOPE", "EXPECTED", "QUARTERLY_CPI_FRESH_DAYS",
           "OBSERVATION_AGE_LIMIT_DAYS",
           "inspect_g8_pair_macro_asof_lab"]
