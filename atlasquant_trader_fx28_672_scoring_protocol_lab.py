"""PRE-FROZEN FX28 prospective measurement protocol: research-only/no GO.

Defines 672 nominal opportunities = (20 D1 + 4 W1) x 28 FX pairs.
An abstention is *coverage lost*, NEVER a correct directional prediction.
FLAT is not an accurate UP or DOWN call. Unknown evidence stays unknown.

Joins must FIRST pass the existing documentary 28-pair/whole-period join;
this rollup only verifies counts, canonical order, session dates, meanings,
and rejects manipulated/adversarial summaries. It never authenticates the
broker, GitHub's pre-event timestamp, real macro vintages or trading fills.

No percentages or statistical confidence are advertised on unverified
documentary claims. D1/W1 overlap; FX28 pairs share eight currency legs.
A 90% claim from 672 correlated rows would be false precision. Code
defines the future arithmetic, but does not treat outcomes as observed until
EVERY window has ended and every original/independent source is checked.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, EXPECTED_PAIR_HORIZON_SLOTS,
    FROZEN_START_UTC, FROZEN_END_UTC, _nominal_windows,
)
from atlasquant_trader_fx_ny17_forecast_outcome_join_lab import (
    SCHEMA as FORECAST_OUTCOME_SCHEMA,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_672_SCORING_RULES_FROZEN_LAB_V1"
_JOIN_STATE = "LAB_NY17_COMPLETE_FORECAST_PRICE_CLAIMS_ONLY_NO_GO"
_REASON = {
    "SAME_DIRECTION_CLAIM_ONLY": "DIRECTIONAL_AGREEMENT_CLAIM_ONLY",
    "OPPOSITE_DIRECTION_CLAIM_ONLY": "DIRECTIONAL_DISAGREEMENT_CLAIM_ONLY",
    "FLAT_OUTCOME_NOT_A_HIT": "FLAT_IS_A_MISS_NOT_A_HIT",
    "ABSTENTION_NOT_A_HIT": "ABSTAIN_IS_NOT_A_HIT",
}


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _parse_time(value: Any) -> datetime | None:
    if type(value) is not str or len(value) > 45:
        return None
    try:
        return _utc(datetime.fromisoformat(value))
    except (TypeError, ValueError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_672_PRECOMMITTED_SCORING_BLOCKED",
        "reason": reason,
        "campaign_id": CAMPAIGN_ID,
        "campaign_issue_url": CALENDAR_ISSUE,
        "campaign_start_utc": FROZEN_START_UTC.isoformat(),
        "campaign_end_utc": FROZEN_END_UTC.isoformat(),
        "expected_pair_horizon_slots": 672,
        "expected_d1_slots": 560,
        "expected_w1_slots": 112,
        "expected_independent_trials": None,
        "twenty_d1_and_four_w1_sessions_overlap": True,
        "fx28_pairs_share_eight_currency_legs": True,
        "out_of_sample_accuracy_percent": None,
        "validated_hit_rate_percent": None,
        "calibrated_probability": None,
        "confidence_interval_percent": None,
        "trading_profitability_inferred": False,
        "pre_event_publication_independently_authenticated": False,
        "broker_prices_independently_authenticated": False,
        "macro_vintages_independently_authenticated": False,
        "model_configuration_independently_attested": False,
        "transaction_costs_verified": False,
        "scoring_rule_frozen_before_first_nominal_window": True,
        "primary_metric_definition":
            "AUTHENTICATED_CORRECT_UP_DOWN / AUTHENTICATED_NON_ABSTAIN_UP_DOWN",
        "flat_price_if_direction_predicted": "DIRECTIONAL_ERROR",
        "abstention": "NOT_A_HIT_AND_EXCLUDED_FROM_DIRECTIONAL_HIT_RATE",
        "no_forecast_or_missing_witness": "NOT_ISSUED_NOT_BACKFILLED",
        "secondary_coverage_definition":
            "AUTHENTICATED_NON_ABSTAIN_UP_DOWN / 672",
        "d1_w1_primary_rates_must_be_separate": True,
        "cluster_aware_uncertainty_required": True,
        "no_iid_binomial_interval": True,
        "d1_sessions_for_cluster": 20,
        "w1_sessions_for_cluster": 4,
        "per_horizon_documentary_counts": {},
        "total_documentary_reconciled_slots": 0,
        "total_documentary_directional_claims": 0,
        "total_documentary_abstentions": 0,
        "total_documentary_same_direction": 0,
        "total_documentary_wrong_or_flat": 0,
        "composite_accuracy_not_allowed": True,
        "operational_bias": "AGUARDAR",
        "directional_bias": None,
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def precommit_fx28_672_scoring_rules_lab(
    *, as_of_utc: Any, d1_documentary_join: Any = None,
    w1_documentary_join: Any = None,
) -> dict[str, Any]:
    """Read-only measurement rules, optionally roll up ONLY full claim rosters.

    Before campaign finish, show the frozen rules but do not score claims;
    post-campaign, require complete *claimed* paired price/forecasts for
    BOTH horizons. All numeric counts are self-consistency only, NEVER
    statistical evidence of future prediction skill.
    """
    out = _base("INVALID_AS_OF_UTC_OR_CAMPAIGN_CONTRACT")
    now = _utc(as_of_utc)
    d1, w1 = _nominal_windows("D1"), _nominal_windows("W1")
    if (now is None
            or len(OFFICIAL_PAIRS) != 28
            or len(set(OFFICIAL_PAIRS)) != 28
            or len(d1) != 20 or len(w1) != 4
            or EXPECTED_PAIR_HORIZON_SLOTS != 672
            or d1[0][0] != FROZEN_START_UTC
            or w1[0][0] != FROZEN_START_UTC
            or d1[-1][1] != FROZEN_END_UTC
            or w1[-1][1] != FROZEN_END_UTC):
        return out

    if now < FROZEN_END_UTC:
        if d1_documentary_join is not None or w1_documentary_join is not None:
            out["reason"] = "HINDSIGHT_SCORE_REQUESTED_BEFORE_ALL_WINDOWS_FINISH"
            return out
        out["state"] = "LAB_FX28_672_SCORING_PROTOCOL_FROZEN_AWAIT_RESULTS_NO_GO"
        out["reason"] = "NO_FORECAST_OR_PRICE_MEASUREMENT_YET"
        return out
    if d1_documentary_join is None or w1_documentary_join is None:
        out["reason"] = "BOTH_HORIZON_JOINS_MANDATORY_NO_PARTIAL_WIN_RATE"
        return out

    horizon_counts = {}
    for horizon, report, expected_windows in (
        ("D1", d1_documentary_join, d1),
        ("W1", w1_documentary_join, w1),
    ):
        expected = len(expected_windows) * 28
        if (type(report) is not dict
                or report.get("schema") != FORECAST_OUTCOME_SCHEMA
                or report.get("state") != _JOIN_STATE
                or report.get("horizon") != horizon
                or report.get("full_28fx_all_window_manifest_reconciled") is not True
                or report.get("nominal_window_census_recomputed_locally") is not True
                or report.get("trade_authorized") is not False
                or report.get("publishable") is not False
                or report.get("pre_event_forecasts_witnessed") is True
                or report.get("forecast_pre_event_witness_independently_authenticated") is not False
                or report.get("broker_price_source_verified") is True
                or report.get("price_archive_source_independently_authenticated") is not False
                or report.get("declared_window_count") != len(expected_windows)
                or type(report.get("expected_opportunities")) is not int
                or report["expected_opportunities"] != expected
                or type(report.get("received_forecasts")) is not int
                or report["received_forecasts"] != expected):
            out["reason"] = horizon + "_DOCUMENTARY_JOIN_SCHEMA_OR_STATE_INVALID"
            return out

        rows = report.get("rows_documentary")
        if type(rows) is not list or len(rows) != expected:
            out["reason"] = horizon + "_CLAIM_ROWS_MISSING"
            return out
        counts = {"same": 0, "opposite": 0, "flat": 0, "abstain": 0}
        seen_ids: set[str] = set()
        for wi, (start, end) in enumerate(expected_windows):
            for pi, pair in enumerate(OFFICIAL_PAIRS):
                row = rows[wi * 28 + pi]
                if type(row) is not dict:
                    out["reason"] = horizon + "_UNEXPECTED_ROW_TYPE"
                    return out
                compare = row.get("comparison_documentary_only")
                pred, actual = row.get("direction_claim_unattested"), row.get(
                    "observed_price_direction_documentary")
                rid = row.get("opportunity_id")
                if (row.get("pair") != pair
                        or row.get("horizon") != horizon
                        or _parse_time(row.get("window_start_utc")) != start
                        or _parse_time(row.get("window_end_utc")) != end
                        or type(rid) is not str or not rid or rid in seen_ids
                        or row.get("external_precommit_verified") is not False
                        or row.get("broker_price_source_verified") is not False
                        or pred not in ("UP", "DOWN", "ABSTAIN")
                        or actual not in ("UP", "DOWN", "FLAT")
                        or compare not in _REASON):
                    out["reason"] = horizon + "_UNTRUSTED_OR_NONCANONICAL_ROW"
                    return out
                seen_ids.add(rid)
                expected_comparison = (
                    "ABSTENTION_NOT_A_HIT" if pred == "ABSTAIN"
                    else "FLAT_OUTCOME_NOT_A_HIT" if actual == "FLAT"
                    else "SAME_DIRECTION_CLAIM_ONLY" if pred == actual
                    else "OPPOSITE_DIRECTION_CLAIM_ONLY")
                if compare != expected_comparison:
                    out["reason"] = horizon + "_COMPARISON_INCONSISTENT_WITH_DIRECTIONS"
                    return out
                counts[{
                    "SAME_DIRECTION_CLAIM_ONLY": "same",
                    "OPPOSITE_DIRECTION_CLAIM_ONLY": "opposite",
                    "FLAT_OUTCOME_NOT_A_HIT": "flat",
                    "ABSTENTION_NOT_A_HIT": "abstain",
                }[compare]] += 1

        def equals_number(key: str, value: int) -> bool:
            return type(report.get(key)) is int and report[key] == value

        if (not equals_number("declared_abstentions", counts["abstain"])
                or not equals_number(
                    "directional_claims", expected - counts["abstain"])
                or not equals_number(
                    "documentary_same_direction_count", counts["same"])
                or not equals_number(
                    "documentary_opposite_direction_count", counts["opposite"])
                or not equals_number(
                    "documentary_flat_outcomes_count", counts["flat"])
                or sum(counts.values()) != expected):
            out["reason"] = horizon + "_DOCUMENTARY_SUMMARY_COUNTS_TAMPERED"
            return out
        horizon_counts[horizon] = {
            "expected_slots": expected, "claimed_directional": (
                expected - counts["abstain"]),
            "claimed_abstention_not_hit": counts["abstain"],
            "claimed_same_direction_unattested": counts["same"],
            "claimed_wrong_direction_unattested": counts["opposite"],
            "claimed_flat_outcome_not_hit": counts["flat"],
        }

    out.update({
        "state": "LAB_FX28_672_DOCUMENTARY_ROLLUP_ONLY_NO_GO",
        "reason": "CLAIMED_AGREEMENT_COUNTS_NOT_PROVEN_PROSPECTIVE_ACCURACY",
        "per_horizon_documentary_counts": horizon_counts,
        "total_documentary_reconciled_slots": 672,
        "total_documentary_directional_claims": sum(
            h["claimed_directional"] for h in horizon_counts.values()),
        "total_documentary_abstentions": sum(
            h["claimed_abstention_not_hit"] for h in horizon_counts.values()),
        "total_documentary_same_direction": sum(
            h["claimed_same_direction_unattested"]
            for h in horizon_counts.values()),
        "total_documentary_wrong_or_flat": sum(
            h["claimed_wrong_direction_unattested"]
            + h["claimed_flat_outcome_not_hit"]
            for h in horizon_counts.values()),
    })
    return out


# Auxiliary census for unavailable data. This does NOT change the frozen
# score formula above and NEVER upgrades a source or a self-declared status.
COVERAGE_SCHEMA = "ATLASQUANT_FX28_672_COVERAGE_TWO_AXIS_CLAIM_ONLY_LAB_V2"
FORECAST_CLAIMS = frozenset((
    "DIRECTIONAL_CLAIM_ONLY", "ABSTAIN_CLAIM_ONLY",
    "NOT_ISSUED_CLAIM_ONLY",
))
PRICE_CLAIMS = frozenset((
    "COMPLETE_M15_CLAIM_ONLY", "UNLABELABLE_M15_GAP_CLAIM_ONLY",
    "UNAVAILABLE_PRICE_CLAIM_ONLY",
))


def inspect_fx28_672_two_axis_coverage_lab(
    *, as_of_utc: Any, supplied_slot_claims: Any = (),
) -> dict[str, Any]:
    """Reconcile all 672 fixed opportunities even when sources are missing.

    A supplied record is an untrusted *claim*, NEVER authenticated proof
    of pre-window issuance or Pepperstone historical price. DIRECTIONAL and
    ABSTAIN claims must carry a purported issue time in the last 12h before
    the nominal open: it may be forged and is NOT an external witness.
    Omitted records mean UNKNOWN, NOT 'NOT_ISSUED'. Price reports are inadmissible before
    the corresponding nominal window has CLOSED. This is a coverage-only
    diagnostic, not a scorer and not a replacement for real archive joins.
    """
    out = {
        "schema": COVERAGE_SCHEMA,
        "state": "LAB_FX28_672_COVERAGE_BLOCKED_NO_GO",
        "reason": "INVALID_CENSUS_INPUT",
        "frozen_opportunities": 672,
        "per_horizon": {},
        "all_slots_accounted": False,
        "source_claims_not_issuer_or_broker_attestation": True,
        "forecast_issuance_clock_is_untrusted_caller_claim": True,
        "backdated_clock_without_external_witness_is_not_authenticated": True,
        "absence_of_supplied_claim_is_not_proof_of_nonissuance": True,
        "forecast_and_price_availability_are_independent_axes": True,
        "price_gap_cannot_be_a_hit_or_abstention": True,
        "validated_hit_rate_percent": None,
        "calibrated_probability": None,
        "trade_authorized": False,
        "publishable": False,
        "operational_bias": "AGUARDAR",
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }
    now = _utc(as_of_utc)
    if (now is None or type(supplied_slot_claims) not in (tuple, list)
            or len(supplied_slot_claims) > 672):
        return out
    if len(OFFICIAL_PAIRS) != 28 or EXPECTED_PAIR_HORIZON_SLOTS != 672:
        return out
    windows = [
        (horizon, start, end, pair)
        for horizon in ("D1", "W1")
        for start, end in _nominal_windows(horizon)
        for pair in OFFICIAL_PAIRS
    ]
    if (len(windows) != 672 or
            sum(h == "D1" for h, *_ in windows) != 560 or
            sum(h == "W1" for h, *_ in windows) != 112):
        out["reason"] = "FROZEN_CALENDAR_OR_PAIR_UNIVERSE_INVALID"
        return out
    ids = {
        f"FX28_NY17_{start.strftime('%Y%m%dT%H%MZ')}_{h}_{pair}":
            (h, start, end)
        for h, start, end, pair in windows
    }
    if len(ids) != 672:
        out["reason"] = "FROZEN_SLOT_IDENTIFIERS_NOT_UNIQUE"
        return out
    supplied = {}
    for record in supplied_slot_claims:
        if type(record) is not dict or set(record) != {
                "slot_id", "forecast_status_claim", "price_status_claim",
                "forecast_issued_at_utc_claim"}:
            out["reason"] = "INVALID_SLOT_CLAIM_SHAPE"
            return out
        sid = record["slot_id"]
        fc = record["forecast_status_claim"]
        price = record["price_status_claim"]
        issue_raw = record["forecast_issued_at_utc_claim"]
        if (type(sid) is not str or sid not in ids or sid in supplied
                or type(fc) is not str or fc not in FORECAST_CLAIMS
                or price is not None and (
                    type(price) is not str or price not in PRICE_CLAIMS)):
            out["reason"] = "DUPLICATE_UNKNOWN_OR_UNSUPPORTED_SLOT_CLAIM"
            return out
        # A future window can still receive a valid prospective forecast.
        # Even an *untrusted claim* of non-issuance is premature until
        # the nominal opportunity starts; do not pre-label it as missed.
        if fc == "NOT_ISSUED_CLAIM_ONLY":
            if issue_raw is not None:
                out["reason"] = "NOT_ISSUED_MUST_NOT_CLAIM_A_FORECAST_TIME"
                return out
            if now < ids[sid][1]:
                out["reason"] = "FORECAST_NOT_ISSUED_BEFORE_NOMINAL_WINDOW_OPEN"
                return out
        else:
            issued = _parse_time(issue_raw)
            start = ids[sid][1]
            if (issued is None
                    or not start - timedelta(hours=12) <= issued < start
                    or issued > now):
                out["reason"] = "FORECAST_ISSUANCE_CLAIM_NOT_IN_12H_BEFORE_OPEN"
                return out
        if price is not None and now < ids[sid][2]:
            out["reason"] = "PRICE_CLAIM_BEFORE_NOMINAL_WINDOW_CLOSE"
            return out
        supplied[sid] = (fc, price)

    per_horizon = {}
    total = 0
    for horizon in ("D1", "W1"):
        cnt = {
            "slots": 0, "not_started": 0, "window_open": 0,
            "window_closed": 0,
            "forecast_unknown_no_supplied_evidence": 0,
            "forecast_directional_claim_only": 0,
            "forecast_abstain_claim_only": 0,
            "forecast_not_issued_claim_only": 0,
            "price_not_yet_labelable_by_clock": 0,
            "price_unknown_no_supplied_evidence": 0,
            "price_complete_m15_claim_only": 0,
            "price_unlabelable_m15_gap_claim_only": 0,
            "price_unavailable_claim_only": 0,
            "directional_with_price_complete_claim_only": 0,
        }
        for h, start, end, pair in windows:
            if h != horizon:
                continue
            sid = f"FX28_NY17_{start.strftime('%Y%m%dT%H%MZ')}_{h}_{pair}"
            fc, price = supplied.get(sid, (None, None))
            cnt["slots"] += 1
            if now < start:
                cnt["not_started"] += 1
            elif now < end:
                cnt["window_open"] += 1
            else:
                cnt["window_closed"] += 1
            fk = {
                None: "forecast_unknown_no_supplied_evidence",
                "DIRECTIONAL_CLAIM_ONLY": "forecast_directional_claim_only",
                "ABSTAIN_CLAIM_ONLY": "forecast_abstain_claim_only",
                "NOT_ISSUED_CLAIM_ONLY": "forecast_not_issued_claim_only",
            }[fc]
            cnt[fk] += 1
            if now < end:
                cnt["price_not_yet_labelable_by_clock"] += 1
            else:
                pk = {
                    None: "price_unknown_no_supplied_evidence",
                    "COMPLETE_M15_CLAIM_ONLY": "price_complete_m15_claim_only",
                    "UNLABELABLE_M15_GAP_CLAIM_ONLY":
                        "price_unlabelable_m15_gap_claim_only",
                    "UNAVAILABLE_PRICE_CLAIM_ONLY": "price_unavailable_claim_only",
                }[price]
                cnt[pk] += 1
                if fc == "DIRECTIONAL_CLAIM_ONLY" and price == "COMPLETE_M15_CLAIM_ONLY":
                    cnt["directional_with_price_complete_claim_only"] += 1
        per_horizon[horizon] = cnt
        total += cnt["slots"]
    out.update({
        "state": "LAB_FX28_672_TWO_AXIS_COVERAGE_CLAIM_ONLY_NO_GO",
        "reason": "ALL_SLOTS_RECONCILED_SOURCE_AND_LABEL_AVAILABILITY_UNATTESTED",
        "per_horizon": per_horizon,
        "all_slots_accounted": total == 672,
    })
    return out


__all__ = ("SCHEMA", "COVERAGE_SCHEMA", "precommit_fx28_672_scoring_rules_lab",
           "inspect_fx28_672_two_axis_coverage_lab")
