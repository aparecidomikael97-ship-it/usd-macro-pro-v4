"""Offline read-only FULL NY17 D1/W1 window roster for AM12 historical quality.

Important: testing only a convenient "good" day would bias any subsequent
research denominator. This module enumerates EVERY nominal NY17 D1/W1 session
between caller-declared exact 17:00 New York endpoints, records failed windows
rather than skipping them, and calls the existing 28-FX archive reader for
each session. A nominal session is not an independently verified trading day
or broker holiday calendar. No signal, probability, or market accuracy here.

Use from the connected AM12 terminal (no write, no MT5/API access):
  python -B atlasquant_trader_mt5_28fx_full_roster_lab.py \\
    --root "<AM12 folder>" --horizon D1 \\
    --start-utc "2026-11-01T21:00:00+00:00" \\
    --end-utc "2026-11-06T22:00:00+00:00" \\
    --as-of-utc "2026-11-12T13:00:00+00:00"

The selected range must be frozen/documented by the study design; even a
complete archive does NOT retroactively prove prediction precommit or edge.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from atlasquant_trader_mt5_28fx_archive_reader_lab import (
    _iso_utc, inspect_local_am12_28fx_lab,
)

SCHEMA = "ATLASQUANT_TRADER_MT5_FULL_NY17_WINDOW_ROSTER_LAB_V1"
NY = ZoneInfo("America/New_York")
MAX_WINDOWS = 40
MAX_SPAN_DAYS = 60
PASS = "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO"


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_AM12_NY17_FULL_ROSTER_BLOCKED",
        "reason": reason,
        "horizon": None,
        "range_start_utc": None, "range_end_utc": None,
        "nominal_window_count": 0,
        "complete_local_window_count": 0,
        "blocked_or_incomplete_window_count": 0,
        "total_expected_pair_window_checks": 0,
        "local_pair_window_checks_complete": 0,
        "blocked_or_unverifiable_pair_window_checks": 0,
        "all_nominal_windows_locally_checked_complete": False,
        "windows": [],
        "weekend_and_holiday_calendar_independently_attested": False,
        "historical_broker_price_provenance_verified": False,
        "source_capture_clock_independently_verified": False,
        "pair_outcomes_independently_verified": False,
        "precommitted_forecast_evidence_verified": False,
        "statistical_out_of_sample_validation_completed": False,
        "directional_accuracy_validated": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "can_feed_live_radar": False, "live_alert_allowed": False,
        "mt5_connections": 0, "http_requests": 0,
        "output_files_written": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _ny_boundary(value: datetime) -> bool:
    local = value.astimezone(NY)
    return (local.hour == 17 and local.minute == 0 and local.second == 0
            and local.microsecond == 0)


def _local_17(day: date) -> datetime:
    return datetime.combine(day, time(17), tzinfo=NY).astimezone(timezone.utc)


def inspect_am12_ny17_full_roster_lab(
    *, root: Any, horizon: Any,
    range_start_at_utc: Any, range_end_at_utc: Any, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Audit all nominal sessions in one bounded window, never choose winners.

    D1 nominal sessions start Sun–Thu at 17 NY and end next day at 17 NY.
    W1 nominal sessions start Sun 17 NY and end Fri 17 NY. Pauses and
    DST/broker holidays can invalidate candidate sessions; they are not
    imputed, removed or treated as missed directional predictions.
    """
    out = _base("INVALID_RANGE_OR_HORIZON")
    start, end, evaluated = (_utc(t) for t in
                             (range_start_at_utc, range_end_at_utc,
                              evaluated_at_utc))
    if (horizon not in ("D1", "W1") or not isinstance(root, (str, Path))
            or any(t is None for t in (start, end, evaluated))
            or not start < end <= evaluated
            or not _ny_boundary(start) or not _ny_boundary(end)
            or end - start > timedelta(days=MAX_SPAN_DAYS)):
        return out
    start_local = start.astimezone(NY)
    end_local = end.astimezone(NY)
    if (horizon == "W1"
            and (start_local.weekday() != 6 or end_local.weekday() != 4)):
        out["reason"] = "W1_RANGE_MUST_START_SUNDAY_AND_END_FRIDAY_NY17"
        return out
    if (horizon == "D1"
            and (start_local.weekday() not in (6, 0, 1, 2, 3)
                 or end_local.weekday() not in (0, 1, 2, 3, 4))):
        out["reason"] = "D1_RANGE_MUST_USE_NOMINAL_WEEKDAY_CLOSE"
        return out

    candidates: list[tuple[datetime, datetime]] = []
    d = start_local.date()
    while d <= end_local.date():
        weekday = d.weekday()
        if (weekday == 6 if horizon == "W1"
                else weekday in (6, 0, 1, 2, 3)):
            first = _local_17(d)
            last = _local_17(d + timedelta(days=5 if horizon == "W1" else 1))
            if first >= start and last <= end:
                candidates.append((first, last))
                if len(candidates) > MAX_WINDOWS:
                    out["reason"] = "TOO_MANY_WINDOWS_NO_SAMPLING_OR_TRUNCATION"
                    return out
        d += timedelta(days=1)

    if not candidates:
        out["reason"] = "NO_COMPLETE_NOMINAL_WINDOWS_WITHIN_RANGE"
        return out
    out.update(
        horizon=horizon, range_start_utc=start.isoformat(),
        range_end_utc=end.isoformat(),
        nominal_window_count=len(candidates),
        total_expected_pair_window_checks=28 * len(candidates),
    )

    summaries = []
    local_complete = 0
    local_pair_complete = 0
    for n, (first, last) in enumerate(candidates, 1):
        result = inspect_local_am12_28fx_lab(
            root=root, horizon=horizon,
            start_at_utc=first, end_at_utc=last,
            evaluated_at_utc=evaluated,
        )
        complete = result["state"] == PASS
        local_complete += int(complete)
        batch = result.get("batch_result")
        count = (batch.get("coverage_claim_complete_pairs", 0)
                 if isinstance(batch, dict) else 0)
        # Never count unverified files as checked when inventory fails.
        if not isinstance(count, int) or not 0 <= count <= 28:
            out["reason"] = "INCONSISTENT_BATCH_COUNTS"
            return out
        local_pair_complete += count
        blocked_pairs = ([
            pair for pair, info in batch["pair_results"].items()
            if info["state"] != "LAB_MT5_M15_ARCHIVE_NY17_LOCAL_JOIN_NO_GO"
        ] if isinstance(batch, dict) else [])
        summaries.append({
            "window_number": n,
            "start_utc": first.isoformat(),
            "end_utc": last.isoformat(),
            "local_archive_check_state": result["state"],
            "local_archive_check_reason": result["reason"],
            "pair_checks_complete_claim_only": count,
            "pair_checks_blocked_or_unverifiable": 28 - count,
            "blocked_pairs": blocked_pairs,
            "broker_provenance_attested": False,
            "directional_outcome": None,
        })

    total = out["total_expected_pair_window_checks"]
    out.update(
        state=("LAB_AM12_NY17_FULL_ROSTER_LOCAL_CLAIMS_ONLY_NO_GO"
               if local_complete == len(candidates)
               else "LAB_AM12_NY17_FULL_ROSTER_HAS_GAPS_NO_GO"),
        reason=("ALL_NOMINAL_WINDOWS_LOCALLY_SELF_CONSISTENT_NOT_BROKER_PROOF"
                if local_complete == len(candidates)
                else "ONE_OR_MORE_NOMINAL_WINDOWS_BLOCKED_NO_EXCLUSION"),
        complete_local_window_count=local_complete,
        blocked_or_incomplete_window_count=len(candidates) - local_complete,
        local_pair_window_checks_complete=local_pair_complete,
        blocked_or_unverifiable_pair_window_checks=total - local_pair_complete,
        all_nominal_windows_locally_checked_complete=(
            local_complete == len(candidates)),
        windows=summaries,
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--horizon", choices=("D1", "W1"), required=True)
    parser.add_argument("--start-utc", required=True)
    parser.add_argument("--end-utc", required=True)
    parser.add_argument("--as-of-utc", required=True)
    args = parser.parse_args(argv)
    result = inspect_am12_ny17_full_roster_lab(
        root=args.root, horizon=args.horizon,
        range_start_at_utc=_iso_utc(args.start_utc),
        range_end_at_utc=_iso_utc(args.end_utc),
        evaluated_at_utc=_iso_utc(args.as_of_utc),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return (0 if result["state"] ==
            "LAB_AM12_NY17_FULL_ROSTER_LOCAL_CLAIMS_ONLY_NO_GO" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
