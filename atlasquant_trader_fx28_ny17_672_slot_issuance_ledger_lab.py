"""Every frozen FX28 NY17 D1/W1 pair-horizon slot, without hindsight.

This is an OFFLINE, read-only accountability ledger over the established
prospective census. An empty input does NOT prove that GitHub contains no
comment: it means the caller supplied no witness. Missing past slots are
marked NOT_ISSUED_BEFORE_WINDOW for the *supplied evidence set*, with an
explicit independent-absence-verification=False flag.

Synthetic or caller-supplied GithubWitnessClaim objects never become
independently authenticated forecasts. Even a structurally valid claim
produces only CLAIM_ONLY_UNAUTHENTICATED; no prices, direction, hit-rate,
order, publication, scheduler, API access, file writes or deployment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, EXPECTED_PAIR_HORIZON_SLOTS,
    FROZEN_START_UTC, FROZEN_END_UTC, _nominal_windows,
)
from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    WindowForecastWitnessClaim, inspect_prospective_fx28_witness_census_lab,
)

SCHEMA = "ATLASQUANT_FX28_NY17_672_SLOT_ISSUANCE_LEDGER_LAB_V1"
FUTURE = "NOT_YET_DUE"
FUTURE_CLAIM = "FUTURE_CLAIM_ONLY_UNAUTHENTICATED"
MISSING = "NOT_ISSUED_BEFORE_WINDOW"
PAST_CLAIM = "PAST_CLAIM_ONLY_UNAUTHENTICATED"
STATES = frozenset((FUTURE, FUTURE_CLAIM, MISSING, PAST_CLAIM))
HORIZONS = ("D1", "W1")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_672_SLOT_ISSUANCE_LEDGER_BLOCKED_NO_GO",
        "reason": reason,
        "campaign_id": CAMPAIGN_ID,
        "calendar_issue_url": CALENDAR_ISSUE,
        "campaign_start_utc": FROZEN_START_UTC.isoformat(),
        "campaign_end_utc": FROZEN_END_UTC.isoformat(),
        "nominal_windows_expected": 24,
        "nominal_pairs_expected": 28,
        "slots_expected": EXPECTED_PAIR_HORIZON_SLOTS,
        "slots_accounted": 0,
        "not_yet_due_slots": 0,
        "future_unattested_claim_slots": 0,
        "not_issued_before_window_slots": 0,
        "past_unattested_claim_slots": 0,
        "per_horizon": {},
        "slots": [],
        "independently_authenticated_forecasts": 0,
        "independently_authenticated_comment_timestamps": False,
        "absence_of_github_witness_independently_verified": False,
        "caller_claims_are_not_real_api_attestation": True,
        "no_witness_in_input_does_not_prove_absence_on_github": True,
        "github_comments_fetched": False,
        "forecast_direction_published": False,
        "validated_directional_accuracy": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "http_requests": 0,
        "file_writes": 0,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_fx28_ny17_672_slot_issuance_ledger_lab(
    *, window_claims: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Classify all 672 nominal opportunities, never backfill or omit gaps.

    window_claims are UNTRUSTED caller declarations, not downloaded records.
    The existing strict witness census must validate them first; even after
    acceptance they are only a local structural claim, not proof of issue.
    """
    out = _blocked("INVALID_INPUT_OR_FROZEN_CAMPAIGN")
    now = _utc(inspected_at_utc)
    if (now is None or not isinstance(window_claims, (list, tuple))
            or len(window_claims) > 24
            or len(OFFICIAL_PAIRS) != 28
            or len(set(OFFICIAL_PAIRS)) != 28
            or EXPECTED_PAIR_HORIZON_SLOTS != 672):
        return out
    windows = [(horizon, start, end)
               for horizon in HORIZONS
               for start, end in _nominal_windows(horizon)]
    if (len(windows) != 24
            or len([x for x in windows if x[0] == "D1"]) != 20
            or len([x for x in windows if x[0] == "W1"]) != 4
            or windows[0][1] != FROZEN_START_UTC
            or windows[20][1] != FROZEN_START_UTC
            or windows[19][2] != FROZEN_END_UTC
            or windows[23][2] != FROZEN_END_UTC):
        out["reason"] = "FROZEN_WINDOW_ROSTER_DIVERGED"
        return out

    audited = inspect_prospective_fx28_witness_census_lab(
        window_claims=window_claims, inspected_at_utc=now)
    if (type(audited) is not dict
            or audited.get("state") !=
                "LAB_PROSPECTIVE_WITNESS_CENSUS_CLAIM_ONLY_NO_GO"
            or audited.get("all_nominal_opportunities_accounted") is not True
            or audited.get("pair_horizon_slots_expected") != 672
            or audited.get("github_comments_independently_authenticated") is not False
            or audited.get("pre_event_forecasts_independently_witnessed") is not False
            or audited.get("trade_authorized") is not False
            or audited.get("publishable") is not False):
        out["reason"] = "WITNESS_CENSUS_REJECTED_INVALID_OR_RETROACTIVE_CLAIMS"
        return out

    claims: set[tuple[str, datetime]] = set()
    for item in window_claims:
        if not isinstance(item, WindowForecastWitnessClaim):
            out["reason"] = "UNEXPECTED_WITNESS_CLAIM_TYPE"
            return out
        start = _utc(item.start_at)
        key = (item.horizon, start)
        if start is None or key in claims:
            out["reason"] = "DUPLICATE_OR_INVALID_CLAIM"
            return out
        claims.add(key)

    rows: list[dict[str, Any]] = []
    by_horizon: dict[str, dict[str, int]] = {}
    totals = {state: 0 for state in STATES}
    ids = set()
    for horizon in HORIZONS:
        counts = {state: 0 for state in STATES}
        counts["slots_expected"] = 560 if horizon == "D1" else 112
        for h, start, end in windows:
            if h != horizon:
                continue
            has_claim = (horizon, start) in claims
            state = (FUTURE_CLAIM if has_claim else FUTURE) if now < start else (
                PAST_CLAIM if has_claim else MISSING)
            for pair in OFFICIAL_PAIRS:
                slot_id = (
                    f"FX28_NY17_{start.strftime('%Y%m%dT%H%MZ')}_{horizon}_{pair}")
                if slot_id in ids:
                    out["reason"] = "DUPLICATE_FROZEN_SLOT_ID"
                    return out
                ids.add(slot_id)
                rows.append({
                    "slot_id": slot_id,
                    "pair": pair,
                    "horizon": horizon,
                    "window_start_utc": start.isoformat(),
                    "window_end_utc": end.isoformat(),
                    "issuance_accounting_status": state,
                    "claim_is_external_witness": False,
                    "missing_status_proves_github_absence": False,
                    "forecast_issued_independently_verified": False,
                    "broker_price_verified": False,
                    "trade_authorized": False,
                })
                counts[state] += 1
                totals[state] += 1
        by_horizon[horizon] = counts

    if (len(rows) != 672 or len(ids) != 672
            or totals[FUTURE] + totals[FUTURE_CLAIM]
               != audited["not_yet_due_slots"]
            or totals[PAST_CLAIM] != audited["due_witness_claim_only_slots"]
            or totals[MISSING] != audited["due_missing_witness_slots"]
            or totals[FUTURE_CLAIM] != audited["future_witness_claim_only_slots"]
            or by_horizon["D1"]["slots_expected"] != 560
            or by_horizon["W1"]["slots_expected"] != 112):
        out["reason"] = "SOURCE_CENSUS_AND_SLOT_STATES_DIVERGED"
        return out

    out.update(
        state="LAB_FX28_672_SLOTS_ACCOUNTED_UNATTESTED_NO_GO",
        reason="INPUT_ONLY_CENSUS_NOT_GITHUB_WITNESS_OR_FORECAST_PROOF",
        slots_accounted=672,
        not_yet_due_slots=totals[FUTURE],
        future_unattested_claim_slots=totals[FUTURE_CLAIM],
        not_issued_before_window_slots=totals[MISSING],
        past_unattested_claim_slots=totals[PAST_CLAIM],
        per_horizon=by_horizon,
        slots=rows,
    )
    return out


__all__ = (
    "SCHEMA", "STATES", "FUTURE", "FUTURE_CLAIM", "MISSING",
    "PAST_CLAIM", "inspect_fx28_ny17_672_slot_issuance_ledger_lab",
)
