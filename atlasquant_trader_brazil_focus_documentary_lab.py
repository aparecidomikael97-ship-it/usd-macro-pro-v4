"""Focus old official PDF snapshot and WIN/WDO expectation provenance, LAB only.

The 2026-10-23 Focus original PDF was published 2026-10-26; values
are manually transcribed. A newer scheduled 2026-11-03 release is NOT
authenticated here. Never mistake year-end or month-end survey medians
for probabilities of the next Copom meeting or market-implied rate paths.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from atlasquant_trader_win_wdo_brazil_context_lab import build_win_wdo_brazil_context_lab

SCHEMA = "ATLASQUANT_TRADER_BRAZIL_FOCUS_OLD_DOCUMENTARY_LAB_V1"
RESEARCH_ON = date(2026, 11, 3)
FOCUS_SOURCE = "https://www.bcb.gov.br/content/focus/focus/R20261023.pdf"
REFERENCE = "2026-10-23"
PUBLISHED = "2026-10-26"
CONSERVATIVE_ELIGIBLE = "2026-10-27T00:00:00Z"
NEW_RELEASE_REVIEW_DAY = date(2026, 11, 3)
FIELDS = frozenset((
    "indicator", "target_type", "target_period", "median_value",
    "value_unit", "source_reference", "source_published_on",
    "source_url", "note",
))
# "Hoje" column, mediana agregada for 2026/27 from page 1 of official PDF;
# separate November month-end Selic from page 2.
MEDIANS = (
    {"indicator": "IPCA", "target_type": "CALENDAR_YEAR_CHANGE",
     "target_period": "2026", "median_value": "5.19", "value_unit": "PCT",
     "source_reference": REFERENCE, "source_published_on": PUBLISHED,
     "source_url": FOCUS_SOURCE,
     "note": "Year 2026 anticipated inflation, not actual September CPI"},
    {"indicator": "IPCA", "target_type": "CALENDAR_YEAR_CHANGE",
     "target_period": "2027", "median_value": "4.34", "value_unit": "PCT",
     "source_reference": REFERENCE, "source_published_on": PUBLISHED,
     "source_url": FOCUS_SOURCE,
     "note": "Year 2027 anticipated inflation, not 2026 or actual CPI"},
    {"indicator": "SELIC", "target_type": "YEAR_END_POLICY_TARGET",
     "target_period": "2026", "median_value": "13.25", "value_unit": "PCT_AA",
     "source_reference": REFERENCE, "source_published_on": PUBLISHED,
     "source_url": FOCUS_SOURCE,
     "note": "Year-end 2026 market median; NOT next Copom meeting probability"},
    {"indicator": "SELIC", "target_type": "YEAR_END_POLICY_TARGET",
     "target_period": "2027", "median_value": "11.75", "value_unit": "PCT_AA",
     "source_reference": REFERENCE, "source_published_on": PUBLISHED,
     "source_url": FOCUS_SOURCE,
     "note": "Year-end 2027 median; NOT current nominal target"},
    {"indicator": "FX_BRL_PER_USD", "target_type": "DECEMBER_AVERAGE_FX",
     "target_period": "2026", "median_value": "5.05", "value_unit": "BRL_PER_USD",
     "source_reference": REFERENCE, "source_published_on": PUBLISHED,
     "source_url": FOCUS_SOURCE,
     "note": "Survey year-end December exchange-rate reference, not spot price"},
    {"indicator": "FX_BRL_PER_USD", "target_type": "DECEMBER_AVERAGE_FX",
     "target_period": "2027", "median_value": "5.15", "value_unit": "BRL_PER_USD",
     "source_reference": REFERENCE, "source_published_on": PUBLISHED,
     "source_url": FOCUS_SOURCE,
     "note": "Year 2027 December exchange-rate reference, not WDO prediction"},
    {"indicator": "REAL_GDP", "target_type": "CALENDAR_YEAR_CHANGE",
     "target_period": "2026", "median_value": "1.80", "value_unit": "PCT",
     "source_reference": REFERENCE, "source_published_on": PUBLISHED,
     "source_url": FOCUS_SOURCE,
     "note": "Anticipated full-year GDP change; different from Q2 actual"},
    {"indicator": "REAL_GDP", "target_type": "CALENDAR_YEAR_CHANGE",
     "target_period": "2027", "median_value": "1.31", "value_unit": "PCT",
     "source_reference": REFERENCE, "source_published_on": PUBLISHED,
     "source_url": FOCUS_SOURCE,
     "note": "Anticipated full-year 2027 GDP change"},
    {"indicator": "SELIC", "target_type": "MONTH_END_POLICY_TARGET",
     "target_period": "2026-11", "median_value": "13.50", "value_unit": "PCT_AA",
     "source_reference": REFERENCE, "source_published_on": PUBLISHED,
     "source_url": FOCUS_SOURCE,
     "note": "November 2026 month-end median, NOT a meeting outcome or odds"},
)


def _entries(supplied: Sequence[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    raw = MEDIANS if supplied is None else supplied
    if not isinstance(raw, (tuple, list)) or len(raw) != len(MEDIANS):
        raise ValueError("Nine frozen Focus documentary medians required")
    checked = []
    for got, expected in zip(raw, MEDIANS):
        if (not isinstance(got, Mapping) or set(got) != FIELDS
                or dict(got) != expected):
            raise ValueError("Unreviewed, missing, or altered Focus reference")
        try:
            n = Decimal(got["median_value"])
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Malformed Focus document value") from exc
        if not n.is_finite() or not -50 <= n <= 200:
            raise ValueError("Out-of-range Focus documentary value")
        checked.append(dict(got))
    return checked


def build_brazil_focus_documentary_lab(
    *, at: datetime, observations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Read dated survey medians and index context; never issue direction."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Explicit timezone-aware cutoff required")
    now = at.astimezone(timezone.utc)
    if now.date() < RESEARCH_ON:
        raise ValueError("No independent retrospective research receipt")
    values = _entries(observations)
    # The fact a more recent report may exist is NOT proof of its bytes,
    # date/time of publication or numeric expectations.
    state = "NEW_SCHEDULED_FOCUS_RELEASE_REQUIRES_OFFICIAL_PDF_REVIEW"
    brazil = build_win_wdo_brazil_context_lab(at=now)
    rows = []
    for row in brazil["index_horizons"]:
        rows.append({
            "instrument": row["instrument"], "horizon": row["horizon"],
            "brazil_actuals": row["brasil_official_facts"],
            "prior_focus_document": values,
            "focus_state": state,
            "brazil_upcoming_events": row["brasil_upcoming_events"],
            "usd_upcoming_events": row["us_upcoming_events"],
            "next_copom_meeting_decision_consensus_pct": None,
            "next_copom_cut_probability": None,
            "forward_di_curve_verified": False,
            "newer_focus_report_verified": False,
            "directional_bias": "AGUARDAR",
            "probability_calibrated": None,
            "trade_authorized": False,
        })
    if len(rows) != 6:
        raise RuntimeError("WIN WDO 3-horizon coverage must be six")
    return {
        "schema": SCHEMA, "state": "LAB_FOCUS_PRIOR_PDF_NOT_A_FX_FORECAST",
        "as_of_utc": now.isoformat(), "focus_reference_date": REFERENCE,
        "focus_published_on": PUBLISHED,
        "focus_pdf_url": FOCUS_SOURCE, "focus_pdf_content_sha256": None,
        "source_original_pdf_bytes_archived": False,
        "source_original_pdf_signature_verified": False,
        "focus_rows": values, "focus_row_count": len(values),
        "focus_freshness": state,
        "new_focus_release_day": NEW_RELEASE_REVIEW_DAY.isoformat(),
        "new_focus_release_numeric_values_verified": False,
        "last_verified_document_is_most_recent": False,
        "win_wdo_horizons": rows, "index_horizon_count": len(rows),
        "market_priced_brazil_expectations_verified": False,
        "pre_meeting_consensus_verified": False,
        "directional_accuracy_oos_proven": False,
        "accuracy_90_proven": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "warning": "Focus October 23 median has 2026 year-end Selic 13.25 "
                   "and November month-end Selic 13.50, NOT interchangeable. "
                   "Nov 3 release must be independently checked. "
                   "Neither Focus point is a calibrated next-meeting prediction.",
    }


__all__ = ["SCHEMA", "MEDIANS", "build_brazil_focus_documentary_lab"]
