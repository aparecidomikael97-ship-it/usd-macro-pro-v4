"""G8 policy decision documentary levels, LAB only, with strict as-of gates.

Does not claim intraday independent source custody or convert nominal policy
rates into relative currency strength. AUD Nov-3 announcement is withheld from
earlier as-of calls; effective date is a local calendar date, not a timestamp.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_G8_POLICY_LEVELS_DOCUMENTARY_LAB_V1"
RESEARCH_ON = "2026-11-03"
FIELDS = frozenset((
    "currency", "instrument_id", "low_pct", "high_pct", "measure_type",
    "decided_on", "conservative_available_from_utc", "source_url",
    "effective_on_local", "availability_policy",
))
# Conservative next-day eligibility for date-only documentary publications.
# It does not claim the source's original hourly publication or receipt.
DECISIONS = (
    {"currency": "USD", "instrument_id": "FOMC_TARGET_FED_FUNDS_RANGE",
     "low_pct": "3.75", "high_pct": "4.00", "measure_type": "TARGET_RANGE",
     "decided_on": "2026-10-28", "conservative_available_from_utc": "2026-10-29T00:00:00Z",
     "source_url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm",
     "effective_on_local": None, "availability_policy": "NEXT_UTC_DAY"},
    {"currency": "EUR", "instrument_id": "ECB_DEPOSIT_FACILITY_RATE",
     "low_pct": "2.50", "high_pct": "2.50", "measure_type": "POINT_TARGET",
     "decided_on": "2026-10-29", "conservative_available_from_utc": "2026-10-30T00:00:00Z",
     "source_url": "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html",
     "effective_on_local": None, "availability_policy": "NEXT_UTC_DAY"},
    {"currency": "GBP", "instrument_id": "BOE_BANK_RATE",
     "low_pct": "3.75", "high_pct": "3.75", "measure_type": "POINT_TARGET",
     "decided_on": "2026-09-17", "conservative_available_from_utc": "2026-09-18T00:00:00Z",
     "source_url": "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/september-2026",
     "effective_on_local": None, "availability_policy": "NEXT_UTC_DAY"},
    {"currency": "JPY", "instrument_id": "BOJ_OVERNIGHT_CALL_RATE_GUIDELINE",
     "low_pct": "1.25", "high_pct": "1.25", "measure_type": "APPROXIMATE_GUIDELINE",
     "decided_on": "2026-10-30", "conservative_available_from_utc": "2026-10-31T00:00:00Z",
     "source_url": "https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf",
     "effective_on_local": None, "availability_policy": "NEXT_UTC_DAY"},
    {"currency": "CHF", "instrument_id": "SNB_POLICY_RATE",
     "low_pct": "0.00", "high_pct": "0.00", "measure_type": "POINT_TARGET",
     "decided_on": "2026-09-24", "conservative_available_from_utc": "2026-09-25T00:00:00Z",
     "source_url": "https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924",
     "effective_on_local": None, "availability_policy": "NEXT_UTC_DAY"},
    {"currency": "CAD", "instrument_id": "BOC_OVERNIGHT_RATE_TARGET",
     "low_pct": "2.50", "high_pct": "2.50", "measure_type": "POINT_TARGET",
     "decided_on": "2026-10-28", "conservative_available_from_utc": "2026-10-29T00:00:00Z",
     "source_url": "https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/",
     "effective_on_local": None, "availability_policy": "NEXT_UTC_DAY"},
    {"currency": "AUD", "instrument_id": "RBA_CASH_RATE_TARGET",
     "low_pct": "4.60", "high_pct": "4.60", "measure_type": "POINT_TARGET",
     "decided_on": "2026-09-29", "conservative_available_from_utc": "2026-09-30T00:00:00Z",
     "source_url": "https://www.rba.gov.au/media-releases/2026/mr-26-27.html",
     "effective_on_local": "2026-09-30", "availability_policy": "NEXT_UTC_DAY"},
    {"currency": "AUD", "instrument_id": "RBA_CASH_RATE_TARGET",
     "low_pct": "4.85", "high_pct": "4.85", "measure_type": "POINT_TARGET",
     "decided_on": "2026-11-03", "conservative_available_from_utc": "2026-11-03T03:31:00Z",
     "source_url": "https://www.rba.gov.au/media-releases/2026/mr-26-30.html",
     "effective_on_local": "2026-11-04",
     "availability_policy": "ANNOUNCEMENT_PLUS_ONE_MINUTE_NOT_CUSTODY"},
    {"currency": "NZD", "instrument_id": "RBNZ_OFFICIAL_CASH_RATE",
     "low_pct": "2.75", "high_pct": "2.75", "measure_type": "POINT_TARGET",
     "decided_on": "2026-10-28", "conservative_available_from_utc": "2026-10-29T00:00:00Z",
     "source_url": "https://www.rbnz.govt.nz/news-and-events/news/2026/10/ocr-held-at-2-75-percent",
     "effective_on_local": None, "availability_policy": "NEXT_UTC_DAY"},
)
# Known pending BoE decision makes Sep policy context stale on its event date.
BLOCK_PRIOR_FROM_DATE = {"GBP": date(2026, 11, 5)}


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Canonical explicit UTC instant required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid UTC instant") from exc
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("Nonzero UTC offset")
    return parsed.astimezone(timezone.utc)


def _documents(observations: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    rows = DECISIONS if observations is None else observations
    if not isinstance(rows, (list, tuple)) or len(rows) != len(DECISIONS):
        raise ValueError("Nine documentary G8 policy decision vintages required")
    verified = []
    for incoming, canonical in zip(rows, DECISIONS):
        if (not isinstance(incoming, Mapping) or set(incoming) != FIELDS
                or dict(incoming) != canonical):
            raise ValueError("Forged, altered or incomplete policy document")
        try:
            low, high = Decimal(incoming["low_pct"]), Decimal(incoming["high_pct"])
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Malformed policy level") from exc
        if not (low.is_finite() and high.is_finite() and -10 <= low <= high <= 40):
            raise ValueError("Nonfinite or contradictory policy range")
        verified.append(dict(incoming))
    return verified


def build_g8_policy_documentary_lab(
    *, at: datetime, observations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Expose only documentary rates eligible by cutoff; no FX direction."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Evaluation clock must include timezone")
    now = at.astimezone(timezone.utc)
    if now.date().isoformat() < RESEARCH_ON:
        raise ValueError("This unproven research snapshot cannot be retroactively attested")
    rows = _documents(observations)
    available = {}
    for currency in CURRENCIES:
        candidates = [r for r in rows
                      if r["currency"] == currency
                      and _utc(r["conservative_available_from_utc"]) <= now]
        candidates.sort(key=lambda r: _utc(r["conservative_available_from_utc"]))
        if not candidates:
            available[currency] = None
            continue
        selected = candidates[-1]
        state = "HISTORICAL_POLICY_DOCUMENT_AVAILABLE"
        if currency == "AUD" and selected["decided_on"] == "2026-11-03":
            # Date-only effective-from record, not a claim about bank operations
            # precisely at local midnight. Fixed AEDT offset needs no tzdata.
            sydney_date = now.astimezone(timezone(timedelta(hours=11))).date()
            if sydney_date < date(2026, 11, 4):
                state = "NEW_RATE_ANNOUNCED_EFFECTIVE_NEXT_LOCAL_DATE"
            else:
                state = "NEW_RATE_LOCAL_EFFECTIVE_DATE_REACHED"
        if (currency in BLOCK_PRIOR_FROM_DATE
                and now.date() >= BLOCK_PRIOR_FROM_DATE[currency]):
            state = "KNOWN_NEW_DECISION_DATE_REQUIRES_REFRESH"
        available[currency] = {
            **selected, "availability_state": state,
            "historical_source_original_bytes_attested": False,
            "currency_strength_inferred": False,
        }
    pair_rows = []
    for pair in OFFICIAL_PAIRS:
        base, quote = pair.split("/")
        pair_rows.append({
            "pair": pair, "base_policy": base if available[base] else None,
            "quote_policy": quote if available[quote] else None,
            "nominal_policy_rate_gap_pp": None,
            "future_policy_expectation_gap_pp": None,
            "bias": "AGUARDAR", "probability_calibrated": None,
            "trade_authorized": False,
        })
    if len(available) != 8 or len(pair_rows) != 28:
        raise RuntimeError("Canonical policy documentary universe broken")
    return {
        "schema": SCHEMA, "state": "LAB_G8_POLICY_FACTS_NO_DIRECTION",
        "as_of_utc": now.isoformat(),
        "rates": available, "pair_rows": pair_rows,
        "currency_count": len(available), "pair_count": len(pair_rows),
        "visible_document_count": len([r for r in available.values() if r]),
        "source_bytes_archived": False,
        "source_receipts_independently_attested": False,
        "full_forward_policy_curve_available": False,
        "market_priced_expectations_verified": False,
        "cross_bank_policy_rate_comparability_proven": False,
        "fx_direction_proven": False, "accuracy_90_proven": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "note": "Different policy instruments (including Fed range and BOJ guideline) "
                "are not a direct nominal FX strength ranking.",
    }


__all__ = ["SCHEMA", "DECISIONS", "build_g8_policy_documentary_lab"]
