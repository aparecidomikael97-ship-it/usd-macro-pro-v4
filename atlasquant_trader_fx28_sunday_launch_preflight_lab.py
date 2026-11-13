"""FX28 Sunday NY17 prospective campaign opening preflight: pure, NO-GO.

Freeze all 672 planned pair/horizon slots and show exactly what needs real
verification BEFORE the first nominal Sunday opening 2026-11-15 22:00 UTC.
Do not confuse calendar registration, source file consistency, or a claimed
GitHub hash anchor with an authenticated first-seen 28-pair forecast.

No HTTP, local file IO, GitHub posts, MT5, worker, scheduler, signals,
trading, calibrated probability, hindsight backfill, or paid data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_28pair_source_readiness_manual_lab import (
    SCHEMA as READINESS_SCHEMA,
    inspect_28pair_source_readiness_once_lab,
)
from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    inspect_prospective_fx28_witness_census_lab,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, FROZEN_START_UTC, FROZEN_END_UTC,
    EXPECTED_PAIR_HORIZON_SLOTS, _nominal_windows,
)

SCHEMA = "ATLASQUANT_FX28_SUNDAY_NY17_OPENING_PREFLIGHT_LAB_V1"
FIRST_D1_END_UTC = datetime(2026, 11, 16, 22, tzinfo=timezone.utc)
FIRST_W1_END_UTC = datetime(2026, 11, 20, 22, tzinfo=timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_CAMPAIGN_OPENING_PREFLIGHT_BLOCKED",
        "reason": reason,
        "campaign_id": CAMPAIGN_ID,
        "calendar_issue_url": CALENDAR_ISSUE,
        "campaign_begin_utc": _stamp(FROZEN_START_UTC),
        "campaign_end_utc": _stamp(FROZEN_END_UTC),
        "first_d1_end_utc": _stamp(FIRST_D1_END_UTC),
        "first_w1_end_utc": _stamp(FIRST_W1_END_UTC),
        "expected_pair_horizon_opportunities": 672,
        "expected_d1_opportunities": 560,
        "expected_w1_opportunities": 112,
        "expected_distinct_pair_codes": 28,
        "not_independent_bernoulli_trials": True,
        "checked_clock_utc": None,
        "seconds_until_first_nominal_open": None,
        "first_nominal_open_already_due": None,
        "next_nominal_window_starts_utc": None,
        "window_roster_length": 0,
        "future_nominal_pair_horizon_slots": 0,
        "due_nominal_pair_horizon_slots": 0,
        "local_bank_policy_currency_codes_checked": [],
        "local_bank_policy_currency_count": None,
        "local_bank_policy_pair_coverage_count": None,
        "policy_readiness_report_is_authenticated_source": False,
        "witness_snapshot_was_supplied": False,
        "claimed_window_anchors_checked": 0,
        "independently_authenticated_pre_event_forecasts": 0,
        "first_d1_forecast_roster_independently_witnessed": False,
        "first_w1_forecast_roster_independently_witnessed": False,
        "sufficient_verified_macro_to_issue_direction": False,
        "broker_ny17_m15_verified": False,
        "pre_event_roster_can_be_backfilled_after_start": False,
        "required_actions": [],
        "directional_bias": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "live_alert_allowed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_fx28_sunday_opening_preflight_lab(
    *, inspected_at_utc: Any,
    local_policy_readiness: Any = None,
    window_witness_claims: Any = None,
) -> dict[str, Any]:
    """Diagnose 28-pair D1/W1 readiness; NEVER prepare or post a forecast.

    A caller-supplied, well-formed source report or hash witness remains a
    CLAIM, never source origin, PIT vintage, broker price or pre-event proof.
    Omitted witnesses mean 'not checked', NOT 'confirmed absent on GitHub'.
    """
    out = _base("INVALID_CLOCK_OR_FROZEN_CAMPAIGN")
    now = _utc(inspected_at_utc)
    if now is None or len(OFFICIAL_PAIRS) != 28 or len(set(OFFICIAL_PAIRS)) != 28:
        return out
    d1, w1 = _nominal_windows("D1"), _nominal_windows("W1")
    if (FROZEN_START_UTC != datetime(2026, 11, 15, 22, tzinfo=timezone.utc)
            or FROZEN_END_UTC != datetime(2026, 12, 11, 22, tzinfo=timezone.utc)
            or EXPECTED_PAIR_HORIZON_SLOTS != 672
            or len(d1) != 20 or len(w1) != 4
            or d1[0] != (FROZEN_START_UTC, FIRST_D1_END_UTC)
            or w1[0] != (FROZEN_START_UTC, FIRST_W1_END_UTC)):
        out["reason"] = "FROZEN_CAMPAIGN_WINDOWS_DRIFTED"
        return out

    coverage_sources: list[str] = []
    bilateral: int | None = None
    if local_policy_readiness is not None:
        report = local_policy_readiness
        if (type(report) is not dict
                or report.get("schema") != READINESS_SCHEMA
                or report.get("state") != "LAB_FX28_28PAIR_MANUAL_SOURCE_READINESS_NO_GO"
                or report.get("operational_bias") != "AGUARDAR"
                or report.get("trade_authorized") is not False
                or report.get("publishable") is not False
                or report.get("pairs_explained") != 28
                or report.get("pre_event_forecasts_independently_witnessed") is not False
                or report.get("first_seen_pit_authenticated") is not False
                or report.get("bilateral_cpi_yoy_authenticated") is not False):
            out["reason"] = "POLICY_SOURCE_READINESS_REPORT_INADMISSIBLE"
            return out
        coverage_sources = report.get("local_policy_sources_checked_codes")
        bilateral = report.get("pairs_with_two_policy_sources_locally_checked")
        if (type(coverage_sources) is not list
                or len(coverage_sources) > 8
                or len(coverage_sources) != len(set(coverage_sources))
                or any(type(x) is not str or x not in (
                    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"
                ) for x in coverage_sources)
                or type(report.get("local_policy_sources_checked_count")) is not int
                or report["local_policy_sources_checked_count"] != len(coverage_sources)
                or type(bilateral) is not int
                or bilateral != len(coverage_sources) * (len(coverage_sources) - 1) // 2):
            out["reason"] = "POLICY_SOURCE_READINESS_COVERAGE_INCOHERENT"
            return out

    # The census is from supplied local claims, NEVER independently verified
    # Github API/server timestamps. There is no false "posted" label.
    claims_count = 0
    supplied = window_witness_claims is not None
    if supplied:
        census = inspect_prospective_fx28_witness_census_lab(
            window_claims=window_witness_claims,
            inspected_at_utc=now,
        )
        if (census.get("state") != "LAB_PROSPECTIVE_WITNESS_CENSUS_CLAIM_ONLY_NO_GO"
                or census.get("all_nominal_opportunities_accounted") is not True
                or census.get("pre_event_forecasts_independently_witnessed") is not False
                or census.get("trade_authorized") is not False):
            out["reason"] = "WITNESS_SNAPSHOT_INADMISSIBLE_OR_CLOCK_TOO_EARLY"
            return out
        claims_count = sum(
            int(w["witness_claim_only_slots"] > 0)
            for w in census["windows"]
        )

    ordered = sorted(
        [(start, horizon) for horizon, slots in (("D1", d1), ("W1", w1))
         for start, _ in slots],
        key=lambda pair: (pair[0], pair[1])
    )
    future = sum(28 for start, _ in ordered if start > now)
    due = 672 - future
    if future + due != EXPECTED_PAIR_HORIZON_SLOTS:
        out["reason"] = "FROZEN_SLOT_DENOMINATOR_MISMATCH"
        return out

    next_start = next((start for start, _ in ordered if start > now), None)
    if now < FROZEN_START_UTC:
        stage = "PREOPEN_NO_AUTHENTICATED_FORECAST"
        seconds_to_open = int((FROZEN_START_UTC - now).total_seconds())
    elif now < FROZEN_END_UTC:
        stage = "OPENED_NO_RETROACTIVE_FORECAST"
        seconds_to_open = 0
    else:
        stage = "CAMPAIGN_CLOSED_NO_RETROACTIVE_FORECAST"
        seconds_to_open = 0

    required = [
        "VERIFY_REAL_ISSUER_BYTES_RELEASE_TIMES_AND_PIT_MACRO_VINTAGES",
        "VERIFY_BILATERAL_CPI_AND_POLICY_EXPECTATIONS_NOT_ONLY_RATE_LEVELS",
        "CONNECT_AM12_AND_VERIFY_PEPPERSTONE_NY17_M15_PRICE_PROVENANCE",
        "GENERATE_EXACT_28_PAIR_D1_AND_W1_ROSTERS_FROM_VETTED_MODEL_BEFORE_START",
        "RETAIN_CANONICAL_ROSTER_BYTES_MODEL_AND_EVIDENCE_HASHES",
        "PUBLISH_INDEPENDENT_VERIFIABLE_PRE_EVENT_WITNESS_OR_MARK_NOT_ISSUED",
        "DO_NOT_TREAT_GITHUB_CALENDAR_OR_HASH_ONLY_AS_FORECAST_WITNESS",
        "DO_NOT_BACKFILL_AFTER_WINDOW_START_OR_DELETE_ANY_OF_672_SLOTS",
    ]
    out.update({
        "state": "LAB_FX28_CAMPAIGN_OPENING_RESEARCH_ONLY_NO_GO",
        "reason": stage,
        "checked_clock_utc": _stamp(now),
        "seconds_until_first_nominal_open": seconds_to_open,
        "first_nominal_open_already_due": now >= FROZEN_START_UTC,
        "next_nominal_window_starts_utc": (
            _stamp(next_start) if next_start is not None else None
        ),
        "window_roster_length": len(ordered),
        "future_nominal_pair_horizon_slots": future,
        "due_nominal_pair_horizon_slots": due,
        "local_bank_policy_currency_codes_checked": sorted(coverage_sources),
        "local_bank_policy_currency_count": (
            len(coverage_sources) if local_policy_readiness is not None else None
        ),
        "local_bank_policy_pair_coverage_count": bilateral,
        "witness_snapshot_was_supplied": supplied,
        "claimed_window_anchors_checked": claims_count,
        "required_actions": required,
    })
    return out


def main(argv: list[str] | None = None) -> int:
    """Manual zero-network snapshot; no readings from GitHub or Pepperstone."""
    parser = argparse.ArgumentParser(
        description="NY17 FX28 pre-event lab preflight (no forecasts)")
    parser.add_argument("--preflight", action="store_true",
                        help="Read local policy archive only; never post signals")
    flags = parser.parse_args(argv)
    if not flags.preflight:
        print(json.dumps(_base("EXPLICIT_PREFLIGHT_REQUIRED"),
                         ensure_ascii=False, indent=2))
        return 2
    local = inspect_28pair_source_readiness_once_lab(
        mode="audit", local_appdata=os.environ.get("LOCALAPPDATA", ""))
    if local["state"] != "LAB_FX28_28PAIR_MANUAL_SOURCE_READINESS_NO_GO":
        local = None  # unknown/not readable, NOT evidence of 0/8 captures
    report = inspect_fx28_sunday_opening_preflight_lab(
        inspected_at_utc=datetime.now(timezone.utc).replace(microsecond=0),
        local_policy_readiness=local,
        window_witness_claims=None,  # not fetched or independently checked
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    # Always exit 2: this command is observational, NEVER a GO gate.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("SCHEMA", "inspect_fx28_sunday_opening_preflight_lab")
