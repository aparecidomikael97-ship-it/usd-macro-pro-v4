"""G8 headline annual inflation documentary snapshots, LAB and as-of only.

Year-on-year CPI/HICP observations are transcribed from official public releases
but are NOT cross-country currency-strength scores, consensus, independently
signed releases, or complete equivalent measurement methodologies.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_G8_INFLATION_DOCUMENTARY_LAB_V1"
RESEARCH_ON = date(2026, 11, 3)
FIELDS = frozenset((
    "currency", "series_id", "yoy_pct", "reference_period",
    "periodicity", "published_on", "conservative_available_from_utc",
    "source_url", "measurement_note",
))
# Date-only publications enter after the next UTC midnight; this is a
# conservative RESEARCH POLICY, not an attested original release hour.
VINTAGES = (
    {"currency": "USD", "series_id": "US_CPIU_ALL_ITEMS_NSA_YOY",
     "yoy_pct": "3.7", "reference_period": "2026-09", "periodicity": "MONTHLY",
     "published_on": "2026-10-14", "conservative_available_from_utc": "2026-10-15T00:00:00Z",
     "source_url": "https://www.bls.gov/news.release/archives/cpi_10142026.htm",
     "measurement_note": "CPI-U headline NSA annual change"},
    {"currency": "EUR", "series_id": "EURO_AREA_HICP_ALL_ITEMS_YOY_FINAL",
     "yoy_pct": "3.8", "reference_period": "2026-09", "periodicity": "MONTHLY",
     "published_on": "2026-10-16", "conservative_available_from_utc": "2026-10-17T00:00:00Z",
     "source_url": "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap",
     "measurement_note": "Euro area HICP, not national CPI; October flash due Nov 4"},
    {"currency": "GBP", "series_id": "UK_CPI_ALL_ITEMS_YOY",
     "yoy_pct": "3.5", "reference_period": "2026-09", "periodicity": "MONTHLY",
     "published_on": "2026-10-21", "conservative_available_from_utc": "2026-10-22T00:00:00Z",
     "source_url": "https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/september2026",
     "measurement_note": "UK CPI; not CPIH (3.6)"},
    {"currency": "JPY", "series_id": "JAPAN_CPI_2025_BASE_ALL_ITEMS_YOY",
     "yoy_pct": "2.1", "reference_period": "2026-09", "periodicity": "MONTHLY",
     "published_on": "2026-10-23", "conservative_available_from_utc": "2026-10-24T00:00:00Z",
     "source_url": "https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.html",
     "measurement_note": "National all-items CPI, 2025-base; source latest-page URL mutable"},
    {"currency": "CHF", "series_id": "SWISS_CPI_ALL_ITEMS_YOY",
     "yoy_pct": "1.0", "reference_period": "2026-09", "periodicity": "MONTHLY",
     "published_on": "2026-10-01", "conservative_available_from_utc": "2026-10-02T00:00:00Z",
     "source_url": "https://www.bfs.admin.ch/en/newnsb/wNfni1DvzKuQ",
     "measurement_note": "Previous Swiss CPI annual change"},
    {"currency": "CHF", "series_id": "SWISS_CPI_ALL_ITEMS_YOY",
     "yoy_pct": "1.5", "reference_period": "2026-10", "periodicity": "MONTHLY",
     "published_on": "2026-11-03", "conservative_available_from_utc": "2026-11-04T00:00:00Z",
     "source_url": "https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i",
     "measurement_note": "Nov 3 date-only publication; withheld until next UTC day"},
    {"currency": "CAD", "series_id": "CANADA_CPI_ALL_ITEMS_YOY",
     "yoy_pct": "3.1", "reference_period": "2026-09", "periodicity": "MONTHLY",
     "published_on": "2026-10-19", "conservative_available_from_utc": "2026-10-20T00:00:00Z",
     "source_url": "https://www150.statcan.gc.ca/n1/daily-quotidien/261019/dq261019a-eng.htm",
     "measurement_note": "Canada headline CPI annual change"},
    {"currency": "AUD", "series_id": "AUSTRALIA_MONTHLY_CPI_ALL_ITEMS_YOY",
     "yoy_pct": "4.3", "reference_period": "2026-09", "periodicity": "MONTHLY",
     "published_on": "2026-10-28", "conservative_available_from_utc": "2026-10-29T00:00:00Z",
     "source_url": "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/sep-2026",
     "measurement_note": "Australia monthly CPI introduced Oct 2025; all-items annual change"},
    {"currency": "NZD", "series_id": "NEW_ZEALAND_QUARTERLY_CPI_ALL_ITEMS_YOY",
     "yoy_pct": "3.7", "reference_period": "2026-Q3", "periodicity": "QUARTERLY",
     "published_on": "2026-10-22", "conservative_available_from_utc": "2026-10-23T00:00:00Z",
     "source_url": "https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/",
     "measurement_note": "Quarterly CPI 12-month change, not monthly CPI"},
)
# A flash HICP for October is due Nov 4; do not continue to advertise
# September's final figure as a fresh current EUR observation on that day.
REVIEW_FROM = {"EUR": date(2026, 11, 4)}


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z") or len(value) > 40:
        raise ValueError("Documentary as-of clock must be canonical UTC")
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid documentary UTC date") from exc
    if dt.utcoffset() != timedelta(0):
        raise ValueError("Unexpected offset")
    return dt.astimezone(timezone.utc)


def _documents(observations: Sequence[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    raw = VINTAGES if observations is None else observations
    if not isinstance(raw, (list, tuple)) or len(raw) != len(VINTAGES):
        raise ValueError("Nine canonical inflation documentary vintages required")
    out = []
    for row, expected in zip(raw, VINTAGES):
        if (not isinstance(row, Mapping) or set(row) != FIELDS
                or dict(row) != expected):
            raise ValueError("Altered or forged official inflation documentary row")
        try:
            n = Decimal(row["yoy_pct"])
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Invalid annual inflation amount") from exc
        if not n.is_finite() or not -50 <= n <= 200:
            raise ValueError("Nonfinite or unbounded CPI number")
        out.append(dict(row))
    return out


def build_g8_inflation_documentary_lab(
    *, at: datetime, observations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Show only facts known by conservative cutoff; never forecast FX."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Explicit aware evaluation time required")
    now = at.astimezone(timezone.utc)
    if now.date() < RESEARCH_ON:
        raise ValueError("Cannot backdate this independently unverified research")
    rows = _documents(observations)
    known = {}
    for currency in CURRENCIES:
        eligible = [x for x in rows if x["currency"] == currency
                    and _utc(x["conservative_available_from_utc"]) <= now]
        eligible.sort(key=lambda x: _utc(x["conservative_available_from_utc"]))
        if not eligible:
            known[currency] = None
            continue
        current = eligible[-1]
        freshness = ("NEW_RELEASE_DAY_REVIEW_REQUIRED"
                     if currency in REVIEW_FROM and now.date() >= REVIEW_FROM[currency]
                     else "LAST_ELIGIBLE_DOCUMENTARY_RELEASE")
        known[currency] = {
            **current, "freshness_state": freshness,
            "original_source_bytes_attested": False,
            "economic_surprise_verified": False,
        }
    pairs = []
    for pair in OFFICIAL_PAIRS:
        base, quote = pair.split("/")
        pairs.append({
            "pair": pair,
            "base_inflation_reference": base if known[base] else None,
            "quote_inflation_reference": quote if known[quote] else None,
            "numeric_inflation_gap_pp": None,
            "currency_strength_gap": None,
            "bias": "AGUARDAR", "probability_calibrated": None,
            "trade_authorized": False,
        })
    if len(known) != 8 or len(pairs) != 28:
        raise RuntimeError("Incomplete canonical G8 inflation research universe")
    return {
        "schema": SCHEMA, "state": "LAB_G8_HISTORICAL_INFLATION_NO_DIRECTION",
        "as_of_utc": now.isoformat(), "currency_inflation": known,
        "pair_rows": pairs, "documentary_measure_count": len(rows),
        "visible_currency_count": sum(x is not None for x in known.values()),
        "currency_count": len(known), "pair_count": len(pairs),
        "same_cpi_methodology_verified": False,
        "calendar_real_time_refreshed": False,
        "source_original_bytes_archived": False,
        "independent_receipt_verified": False,
        "consensus_pre_event_verified": False,
        "forward_policy_path_verified": False,
        "relative_fx_inflation_edge_proven": False,
        "real_oos_accuracy_proven": False, "accuracy_90_proven": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "warning": "Annual CPI/HICP releases use different methods/cadences; "
                   "nominal inflation cannot rank currencies or prove future FX bias.",
    }


__all__ = ["SCHEMA", "VINTAGES", "build_g8_inflation_documentary_lab"]
