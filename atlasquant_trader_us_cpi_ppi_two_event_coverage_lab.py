"""Two-event CPI/PPI economic-evidence denominator + optional price study.

Deliberately include BOTH October 2026 US inflation releases even if one
is missing a pre-event consensus or usable price archive. No selection based
on the post-release market outcome. Feed the original source bytes and
receipts through the existing source-bound strict BLS, TD and TE parsers.

When requested, re-read the seven PPI M15 price files via the existing full
one-event source/price study, and only attach it to the SAME PPI release and
exact original HTML bytes. Seven correlated USD FX crosses, H1 and H4 are
NEVER seven (or 21) independent economic forecasts.

No statistically valid forecasts, probabilities, signals, deploy or orders.
This module does not perform HTTP, MT5 calls, file writes or price fetches;
the existing one-event read-only parser may read locally supplied file paths.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from atlasquant_trader_us_cpi_ppi_consensus_body_gate_lab import (
    PpiPreEventOriginalPair, inspect_us_cpi_ppi_source_bound_consensus_lab,
)
from atlasquant_trader_us_cpi_ppi_pit_visibility_cutoff_lab import EventVintageClaim
from atlasquant_trader_ppi_one_event_study_join_lab import (
    PpiStudyPacket, inspect_ppi_one_event_study_lab,
    ROOT_EVENT as PPI_STUDY_ROOT,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    USD_FX, LAST_REQUIRED_CLOSE_UTC,
)
from atlasquant_trader_us_cpi_source_custody_lab import RELEASE as CPI_RELEASE
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import RELEASE_UTC as PPI_RELEASE

SCHEMA = "ATLASQUANT_US_CPI_PPI_OCT2026_TWO_EVENT_DENOMINATOR_LAB_V1"
KIND_ROOTS = (("CPI", "US_CPI_OCT2026", CPI_RELEASE),
              ("PPI", "US_PPI_OCT2026", PPI_RELEASE))
_STUDY_OK = "LAB_PPI_ONE_EVENT_SEVEN_FX_DOCUMENTARY_NO_GO"
# The source-bound gate replaces the official-body schema with its own.
_SOURCE_BOUND_OK = "LAB_CPI_PPI_OFFICIAL_BODY_JOIN_UNATTESTED_NO_GO"


def _utc(t: Any) -> datetime | None:
    if type(t) is not datetime or t.tzinfo is None or t.microsecond:
        return None
    try:
        return t.astimezone(timezone.utc) if t.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def _number(s: Any) -> Decimal | None:
    if type(s) is not str:
        return None
    try:
        v = Decimal(s)
        return v if v.is_finite() else None
    except (ValueError, InvalidOperation):
        return None


def _blocked(reason: str, cutoff: datetime | None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_CPI_PPI_TWO_EVENT_COVERAGE_BLOCKED_NO_GO",
        "reason": reason,
        "research_cutoff_utc": cutoff.isoformat() if cutoff else None,
        "frozen_macro_event_denominator": 2,
        "event_roots": [
            {
                "root_id": root, "kind": kind,
                "scheduled_release_utc": published.isoformat(),
                "consensus_visible_in_original_claimed_time": False,
                "actual_visible_in_original_claimed_time": False,
                "retrospective_surprise_percentage_points": None,
                "study_stage": "SOURCE_UNAVAILABLE_OR_UNVALIDATED",
                "pre_event_directional_prediction_verified": False,
                "independent_validated_forecast_trials": 0,
            }
            for kind, root, published in KIND_ROOTS
        ],
        "documentary_actual_events_available": 0,
        "documentary_pre_event_consensus_events_available": 0,
        "documentary_comparable_macro_surprise_events": 0,
        "events_without_comparable_consensus_or_actual": 2,
        "ppi_fx_price_study_originals_revalidated": False,
        "ppi_price_study_attachment_reason": "NOT_EVALUATED",
        "ppi_correlated_fx_pairs_descriptively_observed": 0,
        "ppi_reaction_economic_event_roots": 0,
        "ppi_m15_to_h4_opposite_spot_sign_pairs_documentary": [],
        "ppi_competing_release_risk_documentary": True,
        "ppi_exclusive_news_causality_established": False,
        "pre_event_directional_fx_forecasts_registered_and_independently_witnessed": 0,
        "independent_tradable_prediction_trials": 0,
        "testable_out_of_sample_macro_event_count": 0,
        "validated_directional_accuracy": None,
        "calibrated_directional_probability": None,
        "market_bias": None,
        "broker_prices_independently_authenticated": False,
        "source_first_seen_independently_authenticated": False,
        "consensus_methods_independently_authenticated": False,
        "cpi_yoy_oct2026_reported_as_available": False,
        "seven_correlated_spot_crosses_not_seven_economic_trials": True,
        "no_lookahead_and_no_hindsight_prediction_fabrication": True,
        "research_only": True,
        "publishable": False, "trade_authorized": False,
        "operational_bias": "AGUARDAR",
        "original_672_campaign_slots_modified": False,
        "mt5_calls": 0, "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0,
    }


def inspect_oct2026_us_cpi_ppi_two_event_coverage_lab(
    *, research_cutoff_utc: Any, event_claims: Any,
    actual_http_receipts: Any, ppi_original_pair: Any,
    ppi_study_packet: Any = None,
) -> dict[str, Any]:
    """Documentary-only cohort, with every missing CPI/PPI event retained."""
    cutoff = _utc(research_cutoff_utc)
    out = _blocked("INVALID_CUTOFF_OR_CPI_PPI_SOURCES", cutoff)
    if cutoff is None:
        return out
    source = inspect_us_cpi_ppi_source_bound_consensus_lab(
        decision_cutoff_utc=cutoff, research_horizon="D1",
        event_claims=event_claims, actual_http_receipts=actual_http_receipts,
        ppi_original_pair=ppi_original_pair,
    )
    if (source.get("state") != _SOURCE_BOUND_OK
            or source.get("economic_events_reconciled") != 2
            or source.get("cpi_pre_event_consensus_admitted") is not False
            or source.get("publisher_first_seen_independently_attested") is not False
            or source.get("trade_authorized") is not False
            or source.get("publishable") is not False
            or type(source.get("feature_rows")) is not list
            or len(source["feature_rows"]) != 2):
        out["reason"] = "SOURCE_BOUND_CPI_PPI_TWO_EVENT_ORIGINAL_REPLAY_NOT_ACCEPTED"
        return out

    rows = source["feature_rows"]
    if [r.get("kind") for r in rows] != ["CPI", "PPI"]:
        out["reason"] = "SOURCE_BOUND_CPI_PPI_RELEASE_ORDER_CHANGED"
        return out
    if (type(event_claims) not in (tuple, list)
            or len(event_claims) != 2 or
            not all(type(c) is EventVintageClaim for c in event_claims)):
        return out
    by_kind = {c.kind: c for c in event_claims}
    if set(by_kind) != {"CPI", "PPI"}:
        return out
    combined = []
    for row, (kind, root, release) in zip(rows, KIND_ROOTS):
        actual = row.get("actual_first_print_percent_local_claim_visible")
        consensus = row.get("consensus_percent_local_claim_visible")
        diff = row.get("actual_minus_consensus_percentage_points_documentary")
        a, c, d = _number(actual), _number(consensus), _number(diff)
        if (row.get("scheduled_release_utc") != release.isoformat()
                or row.get("reference_period") != "2026-10"
                or row.get("metric_transform") != "MOM_SA_PERCENT"
                or (a is None) != (actual is None)
                or (c is None) != (consensus is None)
                or (d is None) != (diff is None)
                or (d is not None and (a is None or c is None or d != a-c))
                or (a is not None and cutoff < release)):
            out["reason"] = "RELEASE_DATE_SERIES_OR_SURPRISE_MISMATCH"
            return out
        if kind == "CPI" and (c is not None or diff is not None):
            out["reason"] = "CPI_PRE_EVENT_CONSENSUS_NOT_EVIDENCED"
            return out
        if a is not None and c is not None:
            stage = "RETROSPECTIVE_DOCUMENTARY_SURPRISE_ONLY"
        elif a is not None:
            stage = "POST_EVENT_ACTUAL_ONLY_NO_COMPARABLE_CONSENSUS"
        elif c is not None:
            stage = "PRE_EVENT_CONSENSUS_ONLY_NO_FUTURE_ACTUAL"
        else:
            stage = "NO_ADMISSIBLE_SOURCE_AT_RESEARCH_CUTOFF"
        combined.append({
            "root_id": root, "kind": kind,
            "scheduled_release_utc": release.isoformat(),
            "consensus_visible_in_original_claimed_time": c is not None,
            "actual_visible_in_original_claimed_time": a is not None,
            "retrospective_surprise_percentage_points": diff if d is not None else None,
            "study_stage": stage,
            "pre_event_directional_prediction_verified": False,
            "independent_validated_forecast_trials": 0,
        })
    actual_count = sum(r["actual_visible_in_original_claimed_time"] for r in combined)
    consensus_count = sum(r["consensus_visible_in_original_claimed_time"] for r in combined)
    surprise_count = sum(r["retrospective_surprise_percentage_points"] is not None
                         for r in combined)
    if (actual_count != source["research_events_with_first_print_visible_at_cutoff_claim_only"]
            or consensus_count != source["research_events_with_pre_release_consensus_visible"]
            or surprise_count != source["documentary_surprises_comparable_after_release_only"]):
        out["reason"] = "TWO_EVENT_COUNT_OR_DENOMINATOR_MISMATCH"
        return out

    out.update({
        "state": "LAB_CPI_PPI_TWO_EVENT_DOCUMENTARY_COVERAGE_NO_GO",
        "reason": "TWO_ORIGINAL_DOCUMENTARY_EVENTS_ZERO_PRECOMMITTED_FX_FORECASTS",
        "event_roots": combined,
        "documentary_actual_events_available": actual_count,
        "documentary_pre_event_consensus_events_available": consensus_count,
        "documentary_comparable_macro_surprise_events": surprise_count,
        "events_without_comparable_consensus_or_actual": 2-surprise_count,
    })

    if ppi_study_packet is None:
        out["ppi_price_study_attachment_reason"] = "PPI_PRICE_ORIGINALS_NOT_SUPPLIED"
        return out
    if (type(ppi_study_packet) is not PpiStudyPacket
            or type(ppi_original_pair) is not PpiPreEventOriginalPair
            or by_kind["PPI"].actual_source_bytes is None
            or ppi_study_packet.td_html != ppi_original_pair.td_original_html
            or ppi_study_packet.te_html != ppi_original_pair.te_original_html
            or ppi_study_packet.bls_html != by_kind["PPI"].actual_source_bytes):
        out["ppi_price_study_attachment_reason"] = "PPI_PRICE_STUDY_ORIGINAL_BYTES_NOT_SAME_EVENT"
        return out
    if cutoff < LAST_REQUIRED_CLOSE_UTC or not combined[1]["actual_visible_in_original_claimed_time"]:
        out["ppi_price_study_attachment_reason"] = "PPI_PRICES_OR_ACTUAL_NOT_VISIBLE_AT_CUTOFF"
        return out

    ppi_study = inspect_ppi_one_event_study_lab(
        packet=ppi_study_packet, as_of_utc=cutoff,
    )
    packet = ppi_study.get("one_event_study")
    if (ppi_study.get("state") != _STUDY_OK
            or type(packet) is not dict
            or packet.get("root_event_id") != PPI_STUDY_ROOT
            or packet.get("economic_event_count_documentary") != 1
            or packet.get("pre_event_research_direction_registered") != "ABSTAIN"
            or packet.get("pre_event_directional_forecasts_registered") != 0
            or packet.get("forex_crosses_observed") != len(USD_FX)
            or packet.get("seven_spot_observations_not_seven_independent_trials") is not True
            or packet.get("descriptive_reaction_cannot_be_exclusively_attributed_to_ppi") is not True
            or packet.get("mt5_server_or_broker_independently_authenticated") is not False
            or packet.get("post_event_price_reactions_count_as_predictive_hits") is not False
            or ppi_study.get("trade_authorized") is not False):
        out["ppi_price_study_attachment_reason"] = "PPI_ONE_EVENT_PRICE_SOURCE_REPLAY_NOT_ACCEPTED"
        return out
    if (_number(packet.get("headline_ppi_surprise_percentage_points")) !=
            _number(combined[1]["retrospective_surprise_percentage_points"])
            or combined[1]["retrospective_surprise_percentage_points"] is None):
        out["ppi_price_study_attachment_reason"] = "PPI_MACRO_SURPRISE_NOT_SAME_DOCUMENTARY_EVENT"
        return out

    conf = packet.get("competing_macro_calendar_context_documentary")
    moves = packet.get("fx_usd_normalized_m15_h1_h4_bps")
    reversals = packet.get("m15_to_h4_opposing_spot_sign_pairs_documentary")
    if (type(conf) is not dict or
            conf.get("ppi_causal_isolation_verified") is not False
            or conf.get("no_competing_events_proven") is not False
            or conf.get("requires_human_calendar_review") is not True
            or type(moves) is not dict or set(moves) != set(USD_FX)
            or type(reversals) is not list or
            any(sym not in USD_FX for sym in reversals)):
        out["ppi_price_study_attachment_reason"] = "PPI_PRICE_COHORT_OR_CONFOUNDER_DOCUMENTARY_INVALID"
        return out

    out.update({
        "ppi_fx_price_study_originals_revalidated": True,
        "ppi_price_study_attachment_reason": "SEVEN_CORRELATED_PRICE_SERIES_ONE_EVENT_NO_FORECAST",
        "ppi_correlated_fx_pairs_descriptively_observed": len(USD_FX),
        "ppi_reaction_economic_event_roots": 1,
        "ppi_m15_to_h4_opposite_spot_sign_pairs_documentary": reversals,
        "ppi_competing_release_risk_documentary": True,
    })
    # Intentional: independent_tradable_prediction_trials remains ZERO.
    return out


__all__ = ("SCHEMA", "inspect_oct2026_us_cpi_ppi_two_event_coverage_lab")
