"""G8 documentary inflation + policy + prospective catalyst dossier, LAB only.

This is an evidence-readiness bridge, NOT a currency strength model.
It never turns observed CPI or policy levels into interest-rate expectations,
market direction, confidence percentages, or authorization to trade.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_policy_documentary_lab import build_g8_policy_documentary_lab
from atlasquant_trader_g8_inflation_documentary_lab import build_g8_inflation_documentary_lab
from atlasquant_trader_macro_event_exposure_lab import (
    HORIZONS, INDICES, build_macro_event_exposure_lab,
)
from atlasquant_trader_policy_survey_asof_lab import audit_official_policy_surveys_lab

SCHEMA = "ATLASQUANT_TRADER_MACRO_JOINT_DOSSIER_LAB_V1"
MISSING = (
    "MARKET_PRICED_FORWARD_RATE_PATH_UNVERIFIED",
    "ECONOMIC_CONSENSUS_VINTAGES_UNVERIFIED",
    "EMPLOYMENT_ACTIVITY_CROSS_COUNTRY_COVERAGE_INCOMPLETE",
    "MICRO_AND_GEOPOLITICAL_EVIDENCE_INCOMPLETE",
    "INDEPENDENT_ORIGINAL_SOURCE_CUSTODY_MISSING",
    "INDEPENDENT_FX_PRICE_OOS_CALIBRATION_MISSING",
)
US_INDICES = frozenset(("SPX500", "NAS100", "US30"))


def _doc_ref(row: Mapping[str, Any] | None, kind: str) -> dict[str, Any] | None:
    if row is None:
        return None
    if kind == "INFLATION":
        return {
            "period": row["reference_period"], "published_on": row["published_on"],
            "headline_yoy_pct": row["yoy_pct"], "periodicity": row["periodicity"],
            "series_id": row["series_id"], "source_url": row["source_url"],
            "freshness_state": row["freshness_state"],
        }
    return {
        "decided_on": row["decided_on"], "measure_type": row["measure_type"],
        "announced_low_pct": row["low_pct"],
        "announced_high_pct": row["high_pct"], "source_url": row["source_url"],
        "availability_state": row["availability_state"],
        "effective_on_local": row["effective_on_local"],
    }


def _survey_status(book: Any, at: datetime) -> dict[str, str]:
    if book is None:
        return {c: "NOT_PROVIDED" for c in CURRENCIES}
    audited = audit_official_policy_surveys_lab(book, evaluated_at=at)
    if audited["state"] != "LAB_DOCUMENTARY_POLICY_AVAILABILITY_ONLY":
        raise ValueError("Invalid policy survey documentary book")
    result = {c: "NOT_DOCUMENTED_IN_PARTIAL_SURVEY_BOOK" for c in CURRENCIES}
    seen = set()
    for row in audited["records"]:
        c = row["currency"]
        if c in seen:
            # A second row might be for another target event. This bridge
            # does not pick one expectation post hoc.
            raise ValueError("Ambiguous multiple survey entries per currency")
        seen.add(c)
        result[c] = row["status"]
    return result


def build_macro_joint_dossier_lab(
    *, at: datetime, policy_survey_book: Any = None,
) -> dict[str, Any]:
    """Read an explicit point-in-time snapshot; refuse directional inference."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("A timezone-aware as-of instant is mandatory")
    now = at.astimezone(timezone.utc)
    policies = build_g8_policy_documentary_lab(at=now)
    inflation = build_g8_inflation_documentary_lab(at=now)
    events = build_macro_event_exposure_lab(at=now)
    status = _survey_status(policy_survey_book, now)

    currencies = {}
    for code in CURRENCIES:
        currencies[code] = {
            "inflation": _doc_ref(inflation["currency_inflation"][code], "INFLATION"),
            "announced_policy": _doc_ref(policies["rates"][code], "POLICY"),
            "forward_policy_survey_state": status[code],
            "independent_survey_receipt_verified": False,
            "market_priced_next_meeting_expectation_pct": None,
            "actual_policy_path_change_prediction": None,
            "currency_bias": "AGUARDAR",
        }

    lookup_fx = {(x["pair"], x["horizon"]): x for x in events["fx_rows"]}
    lookup_index = {(x["instrument"], x["horizon"]): x for x in events["index_rows"]}
    pair_rows = []
    for horizon in HORIZONS:
        for pair in OFFICIAL_PAIRS:
            base, quote = pair.split("/")
            catalyst = lookup_fx[(pair, horizon)]
            pair_rows.append({
                "pair": pair, "horizon": horizon, "base_currency": base,
                "quote_currency": quote,
                "base_documentary": currencies[base],
                "quote_documentary": currencies[quote],
                "curated_upcoming_events": catalyst["event_exposures"],
                "event_coverage_state": catalyst["risk_status"],
                "inflation_difference_pp": None,
                "nominal_policy_gap_pp": None,
                "expected_policy_path_difference_pp": None,
                "fx_strength": None,
                "directional_bias": "AGUARDAR",
                "probability_calibrated": None,
                "blocking_evidence_gaps": MISSING,
                "trade_authorized": False,
            })

    index_rows = []
    for horizon in HORIZONS:
        for instrument in INDICES:
            catalyst = lookup_index[(instrument, horizon)]
            index_rows.append({
                "instrument": instrument, "horizon": horizon,
                "usd_macro_context": currencies["USD"],
                "curated_upcoming_events": catalyst["event_exposures"],
                "event_coverage_state": catalyst["risk_status"],
                "local_market_context_state": (
                    "US_DOMESTIC_MICRO_GEOPOLITICS_MISSING"
                    if instrument in US_INDICES
                    else "BRAZIL_DOMESTIC_MACRO_AND_POLICY_MISSING"
                ),
                "directional_bias": "AGUARDAR",
                "probability_calibrated": None,
                "blocking_evidence_gaps": MISSING,
                "trade_authorized": False,
            })

    if (set(currencies) != set(CURRENCIES) or len(pair_rows) != 84
            or len(index_rows) != 15
            or len(lookup_fx) != 84 or len(lookup_index) != 15):
        raise RuntimeError("Canonical G8/FX/indices research join failed")
    return {
        "schema": SCHEMA, "state": "LAB_MACRO_JOINT_DOCUMENTARY_NO_DIRECTION",
        "as_of_utc": now.isoformat(),
        "currency_readiness": currencies, "fx_by_horizon": pair_rows,
        "indices_by_horizon": index_rows,
        "currency_count": 8, "pair_horizon_count": 84,
        "index_horizon_count": 15,
        "horizons": list(HORIZONS),
        "source_schemas": {
            "policy": policies["schema"],
            "inflation": inflation["schema"],
            "calendar": events["schema"],
        },
        "calendar_partial": True,
        "market_forward_curve_verified": False,
        "economic_consensus_verified": False,
        "micro_geopolitics_verified": False,
        "independent_sources_attested": False,
        "relative_currency_strength_proven": False,
        "accuracy_90_proven": False,
        "real_walk_forward_oos_proven": False,
        "can_feed_live_radar": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "warning": "Documentary headline CPI and announced nominal policy rates "
                   "are historical facts, not a forecast of next rate changes "
                   "or independent D1/W1/MN1 directional odds.",
    }


__all__ = ["SCHEMA", "MISSING", "build_macro_joint_dossier_lab"]
