"""Fail-closed NY17 D1/W1 full-cohort forecast-claim vs M15 outcome join.

For each predeclared session, require ALL 28 Forex forecasts, including
explicit abstentions, and matching complete local M15 price-window labels.
A caller can backdate the entire set of claimed forecast timestamps and
fabricate both the roster and its prices. Even a perfect documentary join
therefore does NOT validate pre-event publication, accuracy, independence,
risk-adjusted profitability or calibration. No I/O, broker or live signals.

No backfilled/retrospectively selected missed predictions are counted as
genuine trials. External evidence of a forecast witnessed before its target
period must be verified independently in a later separate process.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any
from zoneinfo import ZoneInfo

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_ny_rollover_lab import inspect_fx_ny_close_window_lab

SCHEMA = "ATLASQUANT_TRADER_FX_NY17_FULL_FORECAST_OUTCOME_JOIN_LAB_V1"
ROSTER_SCHEMA = "ATLASQUANT_TRADER_MT5_FULL_NY17_WINDOW_ROSTER_LAB_V1"
ROSTER_COMPLETE = "LAB_AM12_NY17_FULL_ROSTER_LOCAL_CLAIMS_ONLY_NO_GO"
WINDOW_COMPLETE = "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO"
NY17_COMPLETE = "LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID"
DIRECTIONS = frozenset(("UP", "DOWN", "ABSTAIN"))
ABSTAIN_REASONS = frozenset((
    "MISSING_MACRO", "CONFLICTING_EVIDENCE", "LOW_CONFIDENCE",
    "STALE_DATA", "EVENT_BLACKOUT", "UNVERIFIED_SOURCE", "OTHER",
))
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
ID = re.compile(r"[A-Z0-9][A-Z0-9_-]{3,79}\Z")
MAX_WINDOWS = 40
MAX_SPAN_DAYS = 60
NY = ZoneInfo("America/New_York")
MAX_SLOTS = 28 * MAX_WINDOWS


@dataclass(frozen=True)
class Ny17ForecastClaim:
    opportunity_id: str
    pair: str
    horizon: str
    outcome_start_at: datetime
    outcome_end_at: datetime
    direction_claim: str
    features_cutoff_at: datetime
    forecast_issued_at: datetime
    model_sha256_claim: str
    evidence_sha256_claim: str
    abstain_reason: str | None = None


def _clock(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _price(value: Any) -> Decimal | None:
    if (not isinstance(value, str) or not 1 <= len(value) <= 40
            or not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,12})?", value)):
        return None
    try:
        v = Decimal(value)
    except InvalidOperation:
        return None
    return v if v.is_finite() and Decimal(0) < v < Decimal("1000000000") else None


def _complete_nominal_ny17_windows(
    *, roster: dict[str, Any], horizon: str, planned: datetime, now: datetime,
) -> list[tuple[datetime, datetime]] | None:
    """Rebuild every nominal session from declared bounds, not caller's rows.

    This verifies coverage ONLY within the locally claimed range. It cannot
    prove the range was externally frozen before the market or that a broker
    was actually open for every nominal session.
    """
    try:
        raw_start, raw_end = roster["range_start_utc"], roster["range_end_utc"]
        if (not isinstance(raw_start, str) or not isinstance(raw_end, str)
                or max(len(raw_start), len(raw_end)) > 40):
            return None
        start = _clock(datetime.fromisoformat(raw_start))
        end = _clock(datetime.fromisoformat(raw_end))
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if (start is None or end is None or not planned < start < end <= now
            or end - start > timedelta(days=MAX_SPAN_DAYS)):
        return None
    first_ny, last_ny = start.astimezone(NY), end.astimezone(NY)
    if any((d.hour, d.minute, d.second, d.microsecond) != (17, 0, 0, 0)
           for d in (first_ny, last_ny)):
        return None
    if horizon == "W1":
        if first_ny.weekday() != 6 or last_ny.weekday() != 4:
            return None
    elif horizon == "D1":
        if (first_ny.weekday() not in (6, 0, 1, 2, 3)
                or last_ny.weekday() not in (0, 1, 2, 3, 4)):
            return None
    else:
        return None

    expected: list[tuple[datetime, datetime]] = []
    current_day = first_ny.date()
    while current_day <= last_ny.date():
        weekday = current_day.weekday()
        if weekday == 6 if horizon == "W1" else weekday in (6, 0, 1, 2, 3):
            begin = datetime.combine(current_day, time(17), tzinfo=NY).astimezone(timezone.utc)
            finish = datetime.combine(
                current_day + timedelta(days=5 if horizon == "W1" else 1),
                time(17), tzinfo=NY,
            ).astimezone(timezone.utc)
            if begin >= start and finish <= end:
                expected.append((begin, finish))
                if len(expected) > MAX_WINDOWS:
                    return None
        current_day += timedelta(days=1)
    return expected if expected else None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_NY17_FORECAST_OUTCOME_JOIN_BLOCKED",
        "reason": reason, "horizon": None,
        "declared_window_count": 0, "expected_opportunities": 0,
        "received_forecasts": 0,
        "declared_abstentions": 0,
        "directional_claims": 0,
        "documentary_same_direction_count": None,
        "documentary_opposite_direction_count": None,
        "documentary_flat_outcomes_count": None,
        "rows_documentary": [],
        "full_28fx_all_window_manifest_reconciled": False,
        "nominal_window_census_recomputed_locally": False,
        "range_precommitted_by_external_witness": False,
        "price_archive_source_independently_authenticated": False,
        "broker_session_calendar_independently_authenticated": False,
        "forecast_pre_event_witness_independently_authenticated": False,
        "model_and_macro_vintages_authenticated": False,
        "prediction_market_ex_ante_available_verified": False,
        "statistical_independence_verified": False,
        "out_of_sample_accuracy_validated": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "transaction_costs_checked": False,
        "operational_bias": "AGUARDAR",
        "publishable": False, "can_feed_live_radar": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_ny17_full_forecast_outcome_join_lab(
    *, price_roster: Any, forecast_claims: Any,
    plan_declared_at_utc: Any, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Reconcile claimed forecasts with EVERY price-window slot.

    The synthetic/caller-provided roster is neither authentic broker data
    nor a proof that a forecast was frozen before price action. No hit-rate
    is returned, including when the two documentary directions agree.
    """
    out = _blocked("INVALID_FORECAST_ROSTER_OR_CLOCK")
    planned, now = _clock(plan_declared_at_utc), _clock(evaluated_at_utc)
    if (not isinstance(price_roster, dict)
            or price_roster.get("schema") != ROSTER_SCHEMA
            or price_roster.get("state") != ROSTER_COMPLETE
            or price_roster.get("all_nominal_windows_locally_checked_complete") is not True
            or not isinstance(forecast_claims, (list, tuple))
            or planned is None or now is None or planned >= now):
        return out
    horizon = price_roster.get("horizon")
    windows = price_roster.get("windows")
    if (horizon not in ("D1", "W1") or not isinstance(windows, list)
            or not 1 <= len(windows) <= MAX_WINDOWS
            or price_roster.get("nominal_window_count") != len(windows)
            or price_roster.get("complete_local_window_count") != len(windows)
            or price_roster.get("total_expected_pair_window_checks") != 28 * len(windows)
            or price_roster.get("local_pair_window_checks_complete") != 28 * len(windows)
            or price_roster.get("blocked_or_unverifiable_pair_window_checks") != 0
            or len(forecast_claims) != 28 * len(windows)
            or len(OFFICIAL_PAIRS) != 28):
        out["reason"] = "FULL_28FX_WINDOW_AND_FORECAST_CENSUS_REQUIRED"
        return out

    expected_windows = _complete_nominal_ny17_windows(
        roster=price_roster, horizon=horizon, planned=planned, now=now)
    if expected_windows is None:
        out["reason"] = "INVALID_OR_UNVERIFIABLE_NY17_DECLARED_RANGE"
        return out
    if len(expected_windows) != len(windows):
        out["reason"] = "OMITTED_OR_EXTRA_NOMINAL_NY17_SESSIONS"
        return out

    sessions: dict[datetime, tuple[datetime, dict[str, Any]]] = {}
    last_end = None
    for index, w in enumerate(windows, 1):
        if not isinstance(w, dict):
            out["reason"] = "INVALID_PRICE_WINDOW_RECORD"
            return out
        try:
            start = _clock(datetime.fromisoformat(w["start_utc"]))
            end = _clock(datetime.fromisoformat(w["end_utc"]))
        except (KeyError, ValueError, TypeError):
            start, end = None, None
        if (start is None or end is None or not start < end <= now
                or not planned < start
                or last_end is not None and start < last_end
                or (start, end) != expected_windows[index - 1]
                or start in sessions or w.get("window_number") != index
                or w.get("local_archive_check_state") != WINDOW_COMPLETE
                or w.get("pair_checks_complete_claim_only") != 28
                or w.get("pair_checks_blocked_or_unverifiable") != 0
                or w.get("blocked_pairs") != []
                or w.get("unverifiable_pair_reasons") != {}):
            out["reason"] = "NONCANONICAL_OR_INCOMPLETE_PRICE_WINDOW"
            return out
        calendar = inspect_fx_ny_close_window_lab(
            horizon=horizon, start_at_utc=start, end_at_utc=end)
        if calendar["state"] != NY17_COMPLETE:
            out["reason"] = "INVALID_NY17_WINDOW_" + calendar["reason"]
            return out
        moves = w.get("price_movements_documentary_by_pair")
        if not isinstance(moves, dict) or set(moves) != set(OFFICIAL_PAIRS):
            out["reason"] = "MISSING_OR_EXTRA_PRICE_MOVEMENT_SLOTS"
            return out
        verified: dict[str, Any] = {}
        for pair in OFFICIAL_PAIRS:
            v = moves[pair]
            if not isinstance(v, dict):
                out["reason"] = "INVALID_DOCUMENTARY_PRICE_ROW"
                return out
            opening = _price(v.get("start_open_documentary"))
            closing = _price(v.get("end_close_documentary"))
            raw_bps = v.get("change_bps_documentary")
            direction = v.get("direction_documentary")
            if (opening is None or closing is None
                    or not isinstance(raw_bps, str)
                    or not re.fullmatch(r"-?[0-9]{1,7}\.[0-9]{4}", raw_bps)):
                out["reason"] = "INVALID_DOCUMENTARY_PRICE_ROW"
                return out
            # A caller can supply a near-zero opening price: reject absurd
            # ratios BEFORE Decimal quantization (which may overflow its
            # working precision). No thrown exception or fabricated result.
            if closing > opening * Decimal("101"):
                out["reason"] = "DOCUMENTARY_PRICE_RATIO_OUTSIDE_RESEARCH_GUARDRAIL"
                return out
            try:
                expected_bps = ((closing / opening - 1) * Decimal("10000")).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP)
            except (InvalidOperation, ZeroDivisionError, OverflowError):
                out["reason"] = "DOCUMENTARY_PRICE_ARITHMETIC_INVALID"
                return out
            expected_direction = ("UP" if closing > opening else
                                  "DOWN" if closing < opening else "FLAT")
            if (abs(expected_bps) > Decimal("1000000")
                    or Decimal(raw_bps) != expected_bps
                    or direction != expected_direction):
                out["reason"] = "DOCUMENTARY_PRICE_DIRECTION_OR_BPS_MISMATCH"
                return out
            verified[pair] = {
                "start_open_documentary": str(opening),
                "end_close_documentary": str(closing),
                "change_bps_documentary": str(expected_bps),
                "direction_documentary": direction,
            }
        sessions[start] = (end, verified)
        last_end = end

    slots: dict[tuple[datetime, str], Ny17ForecastClaim] = {}
    ids = set()
    for claim in forecast_claims:
        if not isinstance(claim, Ny17ForecastClaim):
            out["reason"] = "INVALID_FORECAST_CLAIM_TYPE"
            return out
        start, end, features, issued = (
            _clock(x) for x in (claim.outcome_start_at, claim.outcome_end_at,
                                claim.features_cutoff_at, claim.forecast_issued_at))
        if (not isinstance(claim.opportunity_id, str)
                or ID.fullmatch(claim.opportunity_id) is None
                or claim.opportunity_id in ids
                or claim.pair not in OFFICIAL_PAIRS
                or claim.horizon != horizon
                or claim.direction_claim not in DIRECTIONS
                or start is None or end is None
                or start not in sessions or end != sessions[start][0]
                or features is None or issued is None
                or not planned <= features <= issued < start
                or not isinstance(claim.model_sha256_claim, str)
                or SHA64.fullmatch(claim.model_sha256_claim) is None
                or not isinstance(claim.evidence_sha256_claim, str)
                or SHA64.fullmatch(claim.evidence_sha256_claim) is None
                or (claim.direction_claim == "ABSTAIN"
                    and claim.abstain_reason not in ABSTAIN_REASONS)
                or (claim.direction_claim != "ABSTAIN"
                    and claim.abstain_reason is not None)):
            out["reason"] = "FORECAST_INVALID_DUPLICATE_OR_POST_EVENT_CLAIM"
            return out
        key = (start, claim.pair)
        if key in slots:
            out["reason"] = "DUPLICATE_PAIR_WINDOW_FORECAST_CLAIM"
            return out
        ids.add(claim.opportunity_id)
        slots[key] = claim

    expected = {(start, pair) for start in sessions for pair in OFFICIAL_PAIRS}
    if set(slots) != expected:
        out["reason"] = "FORECAST_CENSUS_HAS_MISSING_OR_EXTRA_PAIR_WINDOWS"
        return out

    rows = []
    abstentions = same = opposite = flat = 0
    for start in sorted(sessions):
        end, prices = sessions[start]
        for pair in OFFICIAL_PAIRS:
            claim = slots[start, pair]
            observed = prices[pair]["direction_documentary"]
            abstain = claim.direction_claim == "ABSTAIN"
            comparison = (
                "ABSTENTION_NOT_A_HIT" if abstain else
                "FLAT_OUTCOME_NOT_A_HIT" if observed == "FLAT" else
                "SAME_DIRECTION_CLAIM_ONLY" if claim.direction_claim == observed
                else "OPPOSITE_DIRECTION_CLAIM_ONLY"
            )
            abstentions += int(abstain)
            same += int(comparison == "SAME_DIRECTION_CLAIM_ONLY")
            opposite += int(comparison == "OPPOSITE_DIRECTION_CLAIM_ONLY")
            flat += int(comparison == "FLAT_OUTCOME_NOT_A_HIT")
            rows.append({
                "opportunity_id": claim.opportunity_id,
                "pair": pair, "horizon": horizon,
                "window_start_utc": start.isoformat(),
                "window_end_utc": end.isoformat(),
                "direction_claim_unattested": claim.direction_claim,
                "abstain_reason": claim.abstain_reason,
                "observed_price_direction_documentary": observed,
                "observed_price_move_bps_documentary":
                    prices[pair]["change_bps_documentary"],
                "comparison_documentary_only": comparison,
                "external_precommit_verified": False,
                "broker_price_source_verified": False,
            })
    out.update({
        "state": "LAB_NY17_COMPLETE_FORECAST_PRICE_CLAIMS_ONLY_NO_GO",
        "reason": "LOCAL_FORECAST_AND_PRICE_ASSERTIONS_NOT_INDEPENDENT_EVIDENCE",
        "horizon": horizon,
        "declared_window_count": len(windows),
        "expected_opportunities": len(expected),
        "received_forecasts": len(forecast_claims),
        "declared_abstentions": abstentions,
        "directional_claims": len(rows) - abstentions,
        "documentary_same_direction_count": same,
        "documentary_opposite_direction_count": opposite,
        "documentary_flat_outcomes_count": flat,
        "rows_documentary": rows,
        "full_28fx_all_window_manifest_reconciled": True,
        "nominal_window_census_recomputed_locally": True,
    })
    return out


__all__ = ("SCHEMA", "Ny17ForecastClaim",
           "inspect_ny17_full_forecast_outcome_join_lab")
