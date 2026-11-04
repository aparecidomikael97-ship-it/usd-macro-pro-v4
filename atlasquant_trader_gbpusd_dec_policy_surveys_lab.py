"""Documentary December GBP/USD policy-survey pair, not a directional model.

Both surveys are public on the 2026-11-03 research date. The Bank of England
page has an official publication DATE; the New York Fed September PDF does not
prove its precise initial posting time. The research date is not an independent
historical source receipt. Only a conservative next-UTC-day comparison is shown,
without mixing policy-rate midpoint and Bank Rate as directly tradable yields.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_TRADER_GBPUSD_DEC2026_POLICY_SURVEY_PAIR_LAB_V1"
BOE = ("https://www.bankofengland.co.uk/markets/market-intelligence/"
       "survey-results/2026/market-participants-survey-results-september-2026")
NYFED = ("https://www.newyorkfed.org/medialibrary/media/markets/survey/"
         "2026/sep-2026-sme-results.pdf")
BOOK_FIELDS = frozenset((
    "schema", "state", "first_lab_observed_on", "survey_freshness_days",
    "boe", "nyfed", "source_pdf_bytes_archived",
    "publication_timestamps_independently_attested",
    "real_oos_verified", "trade_authorized",
))
ITEM_FIELDS = frozenset((
    "currency", "source_url", "sample_closed_on",
    "published_on", "target_event_on", "survey_measure",
    "median_pct", "p25_pct", "p75_pct", "respondents",
))
EXPECTED = {
    "boe": {
        "currency": "GBP", "source_url": BOE,
        "sample_closed_on": "2026-09-04", "published_on": "2026-09-18",
        "target_event_on": "2026-12-17",
        "survey_measure": "MODE_PER_RESPONDENT_BANK_RATE_AFTER_MPC",
        "median_pct": "3.75", "p25_pct": "3.75", "p75_pct": "4.00",
        "respondents": 92,
    },
    "nyfed": {
        "currency": "USD", "source_url": NYFED,
        "sample_closed_on": "2026-09-08", "published_on": None,
        "target_event_on": "2026-12-09",
        "survey_measure": "MODE_PER_RESPONDENT_FED_TARGET_RANGE_MIDPOINT_AFTER_FOMC",
        "median_pct": "3.63", "p25_pct": "3.63", "p75_pct": "4.13",
        "respondents": 62,
    },
}


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_POLICY_PAIR_REFUSED",
        "reason": reason, "snapshot_sha256": None,
        "gbp_survey_median_pct": None, "usd_survey_median_pct": None,
        "nominal_rate_gap_pp": None,
        "implied_rate_path_spread_bp": None,
        "fx_bias": "AGUARDAR", "fx_probability": None,
        "survey_as_live_consensus": False,
        "independent_point_in_time_receipt": False,
        "walk_forward_oos_verified": False, "accuracy_90_proven": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def _date(x: Any) -> date | None:
    if not isinstance(x, str) or len(x) != 10:
        return None
    try:
        value = date.fromisoformat(x)
    except ValueError:
        return None
    return value if value.isoformat() == x else None


def _rate(x: Any) -> Decimal | None:
    if not isinstance(x, str) or len(x) > 10:
        return None
    try:
        v = Decimal(x)
    except InvalidOperation:
        return None
    return v if v.is_finite() and Decimal("-5") <= v <= 30 else None


def compare_gbpusd_dec2026_policy_surveys_lab(
    book: Any, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Report only matched *calendar month* documentary medians; no spread."""
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Explicit timezone-aware evaluation required")
    now = evaluated_at.astimezone(timezone.utc)
    if not isinstance(book, Mapping) or set(book) != BOOK_FIELDS:
        return _refuse("Exact frozen research book required")
    if (book["schema"] != SCHEMA or book["state"] != "LAB_DOCUMENTARY_PAIR_UNATTESTED"
            or book["source_pdf_bytes_archived"] is not False
            or book["publication_timestamps_independently_attested"] is not False
            or book["real_oos_verified"] is not False
            or book["trade_authorized"] is not False
            or type(book["survey_freshness_days"]) is not int
            or book["survey_freshness_days"] != 30):
        return _refuse("False status, rights, custody or freshness claims")
    first_seen = _date(book["first_lab_observed_on"])
    if first_seen != date(2026, 11, 3):
        return _refuse("Research observation date must match frozen lab record")
    for key in ("boe", "nyfed"):
        raw = book[key]
        if not isinstance(raw, Mapping) or set(raw) != ITEM_FIELDS:
            return _refuse(f"Missing or extra {key} survey fields")
        # Fixed values are manual documentary transcription, *not* proof of
        # authentic raw bytes. This contract rejects retrospective relabeling.
        if raw != EXPECTED[key]:
            return _refuse(f"Altered {key} survey provenance or quantiles")
        values = [_rate(raw[x]) for x in ("p25_pct", "median_pct", "p75_pct")]
        if any(x is None for x in values) or not values[0] <= values[1] <= values[2]:
            return _refuse(f"Invalid {key} survey rate quantiles")
        if not (_date(raw["sample_closed_on"]) < _date(raw["target_event_on"])):
            return _refuse(f"Post-event {key} sample cannot predict event")
        if raw["published_on"] is not None and not (
            _date(raw["sample_closed_on"]) <= _date(raw["published_on"])
            < _date(raw["target_event_on"])
        ):
            return _refuse(f"Retrospective {key} survey published after event")
    if now.date() <= first_seen:
        return _refuse("Date-only research visibility requires next UTC day")
    digest = sha256(json.dumps(dict(book), ensure_ascii=True,
                               sort_keys=True, separators=(",", ":")
                               ).encode("utf-8")).hexdigest()
    common = {
        **_refuse(""), "snapshot_sha256": digest,
        "first_lab_observed_on": first_seen.isoformat(),
        "boe_survey_collected_through": "2026-09-04",
        "nyfed_survey_collected_through": "2026-09-08",
        "boe_survey_published_on": "2026-09-18",
        "nyfed_initial_publication_time_attested": False,
        "both_survey_event_months": "2026-12",
        "old_samples_exceed_30_day_policy": (
            (now.date() - date(2026, 9, 4)).days > 30
            and (now.date() - date(2026, 9, 8)).days > 30
        ),
    }
    if now.date() >= date(2026, 12, 9):
        return {
            **common, "state": "LAB_DEC_POLICY_PAIR_TARGET_PASSED",
            "reason": "First FOMC decision day reached; no prospective release claim",
        }
    return {
        **common, "state": "LAB_STALE_DOCUMENTARY_DEC_POLICY_PAIR_ONLY",
        "reason": ("Both September modal surveys are historical; policy target "
                   "definitions, panels and event dates differ, so there is "
                   "no tradeable interest-rate differential or FX forecast"),
        "gbp_survey_median_pct": "3.75",
        "usd_survey_median_pct": "3.63",
        "boe_target_event_on": "2026-12-17",
        "nyfed_target_event_on": "2026-12-09",
    }


__all__ = ["SCHEMA", "compare_gbpusd_dec2026_policy_surveys_lab"]
