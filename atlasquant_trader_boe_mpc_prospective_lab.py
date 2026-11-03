"""Prospective BoE MPC documentary benchmark, lab-only and non-predictive.

The public survey was taken in September and is stale by November. This
module preserves its already-published median BEFORE the November MPC date,
then refuses to infer GBP, FX direction or prediction accuracy from it.
The Git commit can prove the research claim existed before the decision;
it cannot prove the source's original bytes or independent capture time.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Mapping
from urllib.parse import urlsplit

SCHEMA = "ATLASQUANT_TRADER_BOE_NOV2026_POLICY_SURVEY_FREEZE_LAB_V1"
FIELDS = frozenset((
    "schema", "state", "observed_at_utc", "source_url",
    "source_published_on", "collected_through", "target_mpc_on",
    "question", "respondents", "median_policy_rate_pct",
    "p25_policy_rate_pct", "p75_policy_rate_pct", "freshness_policy_days",
    "market_priced_probability", "actual_mpc_rate_pct",
    "source_original_bytes_archived", "source_receipt_independently_attested",
    "real_oos_accuracy_attested", "trade_authorized",
))
ACTUAL_FIELDS = frozenset((
    "state", "source_url", "published_at_utc", "captured_at_utc",
    "official_bank_rate_pct",
))
BOE_SURVEY_URL = (
    "https://www.bankofengland.co.uk/markets/market-intelligence/"
    "survey-results/2026/market-participants-survey-results-september-2026"
)


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, str) or not 20 <= len(v) <= 40:
        return None
    if not (v.endswith("Z") or v.endswith("+00:00")):
        return None
    try:
        stamp = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.utcoffset() != timedelta(0):
        return None
    return stamp.astimezone(timezone.utc)


def _day(v: Any) -> date | None:
    if not isinstance(v, str) or len(v) != 10:
        return None
    try:
        d = date.fromisoformat(v)
    except ValueError:
        return None
    return d if d.isoformat() == v else None


def _rate(v: Any) -> Decimal | None:
    if not isinstance(v, str) or not 1 <= len(v) <= 10:
        return None
    try:
        x = Decimal(v)
    except InvalidOperation:
        return None
    return x if x.is_finite() and Decimal("-5") <= x <= 30 else None


def _refusal(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BOE_SURVEY_FREEZE_REFUSED",
        "reason": reason, "freeze_sha256": None,
        "historical_survey_median_pct": None, "real_actual_rate_pct": None,
        "caller_supplied_absolute_error_pp": None,
        "survey_is_fresh": False, "market_consensus_verified": False,
        "source_receipt_verified": False, "real_oos_verified": False,
        "fx_bias": None, "fx_probability": None, "accuracy_90_proven": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def inspect_boe_mpc_prospective_freeze_lab(
    frozen: Any, *, evaluated_at: datetime, later_actual: Any = None,
) -> dict[str, Any]:
    """Conservative pre-event book with separate hypothetical later observation."""
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Evaluation needs explicit aware datetime")
    now = evaluated_at.astimezone(timezone.utc)
    if not isinstance(frozen, Mapping) or set(frozen) != FIELDS:
        return _refusal("Exact prospective book fields required")
    if (frozen["schema"] != SCHEMA
            or frozen["state"] != "LAB_PRE_EVENT_BOE_SURVEY_HISTORICAL_DOCUMENT"
            or frozen["source_url"] != BOE_SURVEY_URL
            or frozen["question"] != "BOE_MPS_Q1A_MODAL_BANK_RATE_AFTER_NOV5"):
        return _refusal("Incorrect source, survey measure or state")
    if (frozen["source_original_bytes_archived"] is not False
            or frozen["source_receipt_independently_attested"] is not False
            or frozen["real_oos_accuracy_attested"] is not False
            or frozen["trade_authorized"] is not False
            or frozen["market_priced_probability"] is not None
            or frozen["actual_mpc_rate_pct"] is not None):
        return _refusal("Forged provenance, market price or retrospective actual")
    observed = _utc(frozen["observed_at_utc"])
    publication = _day(frozen["source_published_on"])
    collection = _day(frozen["collected_through"])
    meeting = _day(frozen["target_mpc_on"])
    if (observed is None or publication != date(2026, 9, 18)
            or collection != date(2026, 9, 4)
            or meeting != date(2026, 11, 5)
            or not collection < publication < observed.date() < meeting):
        return _refusal("Documentary chronology inconsistent or look-ahead")
    if (type(frozen["respondents"]) is not int or frozen["respondents"] != 92
            or type(frozen["freshness_policy_days"]) is not int
            or frozen["freshness_policy_days"] != 30):
        return _refusal("Response count or declared freshness policy invalid")
    values = tuple(_rate(frozen[k]) for k in (
        "p25_policy_rate_pct", "median_policy_rate_pct", "p75_policy_rate_pct",
    ))
    if any(x is None for x in values) or not values[0] <= values[1] <= values[2]:
        return _refusal("Invalid units/quantiles")
    if values != (Decimal("3.75"), Decimal("3.75"), Decimal("3.81")):
        return _refusal("Documentary values do not match cited BoE question")
    if now < observed:
        return _refusal("Cannot use observation before it was recorded")
    digest = sha256(json.dumps(dict(frozen), sort_keys=True,
                               separators=(",", ":"), ensure_ascii=True
                               ).encode("utf-8")).hexdigest()
    age = (now.date() - publication).days
    common = {
        **_refusal(""), "freeze_sha256": digest,
        "historical_survey_median_pct": "3.75",
        "survey_is_fresh": age <= 30,
        "survey_age_days": age,
        "observed_at_utc": observed.isoformat(),
        "target_mpc_on": meeting.isoformat(),
        "recorded_before_meeting": True,
    }
    if now.date() < meeting:
        if later_actual is not None:
            return _refusal("Actual not allowed before decision day")
        return {
            **common, "state": "LAB_STALE_SURVEY_DOCUMENTED_BEFORE_MPC",
            "reason": (f"September survey is {age} days old; "
                       "not live market consensus or GBP/USD bias"),
        }
    if later_actual is None:
        return {
            **common, "state": "LAB_BOE_MPC_PASSED_NO_VERIFIED_ACTUAL",
            "reason": "Await separately published official BoE outcome",
        }
    if not isinstance(later_actual, Mapping) or set(later_actual) != ACTUAL_FIELDS:
        return _refusal("Later actual record schema invalid")
    if later_actual["state"] != "LAB_CALLER_SUPPLIED_ACTUAL_UNATTESTED":
        return _refusal("Later actual not independently authenticated")
    try:
        parts = urlsplit(later_actual["source_url"])
        official = (parts.scheme == "https"
                    and parts.hostname == "www.bankofengland.co.uk"
                    and parts.path.startswith("/monetary-policy-summary-and-minutes/")
                    and parts.username is None and parts.password is None
                    and parts.port in (None, 443) and not parts.query and not parts.fragment)
    except (TypeError, ValueError):
        official = False
    if not official:
        return _refusal("Later actual must reference official BoE decision page")
    published = _utc(later_actual["published_at_utc"])
    captured = _utc(later_actual["captured_at_utc"])
    if (published is None or captured is None
            or not datetime(2026, 11, 5, tzinfo=timezone.utc) <= published <= captured <= now):
        return _refusal("Future, malformed or unobserved later decision")
    actual = _rate(later_actual["official_bank_rate_pct"])
    if actual is None:
        return _refusal("Official Bank Rate value must be finite decimal string")
    return {
        **common, "state": "LAB_CALLER_SUPPLIED_OUTCOME_COMPARISON_UNVERIFIED",
        "reason": "Not a real scored OOS result until actual has independent custody",
        "real_actual_rate_pct": None,
        "caller_supplied_actual_pct": str(actual),
        "caller_supplied_absolute_error_pp": str(abs(values[1] - actual)),
    }


__all__ = ["SCHEMA", "inspect_boe_mpc_prospective_freeze_lab"]
