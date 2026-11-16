"""Bridge the ORIGINAL October 2026 US PPI one-event study to generic Motor A.

Replays the full PPI packet through pre-existing byte/manifest validators:
pre-event TD + independent TE source, the actual BLS first-print candidate
and all seven M15 FX bar archives. Afterwards independently re-reads the
economic source bytes and maps TWO indicators into the generic same-metric
contract. The two indicators belong to ONE economic event, never two trials.

No price is invented to satisfy the generic contract: the prior PPI study
already holds descriptive M15/H1/H4 reactions, and the generic contract is
only invoked for metric comparison (price_claims=None). Original post-event
MT5 prices, issuer/publisher timing and consensus source custody are still
only local claims. No causal claim, forecast, risk score or probability.
No networking, write, order, scheduler, current-quote or deployment.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from atlasquant_trader_fx28_macro_event_surprise_reaction_contract_lab import (
    MetricIdentity, PreEventConsensus, OfficialActual,
    inspect_macro_event_surprise_reaction_lab as map_metric,
)
from atlasquant_trader_ppi_one_event_study_join_lab import (
    ROOT_EVENT, PpiStudyPacket, inspect_ppi_one_event_study_lab,
)
from atlasquant_trader_us_ppi_pre_event_preview_lab import (
    URL as TD_URL, inspect_ppi_pre_event_snapshot_lab,
)
from atlasquant_trader_us_ppi_te_second_consensus_lab import (
    inspect_te_ppi_snapshot_lab,
)
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    OFFICIAL_URL, RELEASE_UTC,
    inspect_ppi_oct2026_first_print_lab,
    compare_ppi_actual_to_frozen_consensus_lab,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    TD_PRE_EVENT_HTML_SHA256, TE_PRE_EVENT_HTML_SHA256, USD_FX,
)

SCHEMA = "ATLASQUANT_FX28_PPI_ONE_EVENT_2_METRIC_GENERIC_BRIDGE_LAB_V1"
_COMPLETE = "LAB_PPI_ONE_EVENT_SEVEN_FX_DOCUMENTARY_NO_GO"
_METRIC_COMPLETE = "LAB_FX28_SINGLE_EVENT_SURPRISE_DOCUMENTARY_ONLY_NO_GO"
_FIELDS = (
    ("headline", "US_PPI_FINAL_DEMAND", "headline_consensus_mom_pct",
     "headline_final_demand_sa_mom_pct_body_claim",
     "headline_vs_td_pre_event_diff_pp",
     "headline_ppi_surprise_percentage_points"),
    ("core", "US_PPI_FINAL_DEMAND_EX_FOOD_ENERGY",
     "core_consensus_mom_pct",
     "core_ex_food_energy_sa_mom_pct_body_claim",
     "core_vs_td_pre_event_diff_pp",
     "core_ex_food_energy_surprise_percentage_points"),
)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_PPI_TO_GENERIC_MACRO_EVENT_BRIDGE_BLOCKED_NO_GO",
        "reason": reason,
        "event_root_id": ROOT_EVENT,
        "documentary_metric_count": 0,
        "independent_economic_event_count_documentary": 0,
        "independent_predictive_trial_count": 0,
        "metrics": {},
        "seven_usd_fx_pair_reactions_rechecked": 0,
        "reaction_horizons_rechecked": [],
        "first_print_and_consensus_source_bytes_replayed_locally": False,
        "original_pre_event_consensus_capture_independently_authenticated": False,
        "first_print_publication_time_independently_authenticated": False,
        "ppi_only_isolation_from_other_macro_releases_proven": False,
        "broker_price_source_independently_authenticated": False,
        "joined_prices_not_reconstructed_as_fake_generic_endpoints": True,
        "post_event_price_reactions_are_not_prediction_hits": True,
        "pre_event_registered_forecast": "ABSTAIN",
        "out_of_sample_events_for_calibration": 0,
        "calibrated_directional_probability": None,
        "validated_fx_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_modified": False,
        "file_writes": 0,
        "http_calls": 0,
        "mt5_calls": 0,
    }


def replay_ppi_originals_to_generic_event_lab(*, packet: Any,
                                              as_of_utc: Any) -> dict[str, Any]:
    """A local documentary study; all actual input bytes remain in the packet."""
    out = _blocked("INVALID_PACKET_OR_CLOCK")
    if not isinstance(packet, PpiStudyPacket):
        return out
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None):
        return out

    # Existing end-to-end reader reopens the pinned source bytes and the
    # complete 7-FX archive. Do NOT take a caller-supplied report as proof.
    prior = inspect_ppi_one_event_study_lab(packet=packet, as_of_utc=as_of_utc)
    study = prior.get("one_event_study")
    if (prior.get("state") != _COMPLETE or type(study) is not dict
            or prior.get("trade_authorized") is not False
            or prior.get("publishable") is not False
            or prior.get("independent_directional_trials_verified") != 0
            or study.get("root_event_id") != ROOT_EVENT
            or study.get("economic_event_count_documentary") != 1
            or study.get("forex_crosses_observed") != 7
            or study.get("pre_event_research_direction_registered") != "ABSTAIN"
            or study.get("pre_event_directional_forecasts_registered") != 0
            or study.get("descriptive_reaction_cannot_be_exclusively_attributed_to_ppi") is not True
            or study.get("seven_spot_observations_not_seven_independent_trials") is not True
            or study.get("local_mt5_capture_manifest_matched_unattested") is not True
            or study.get("mt5_server_or_broker_independently_authenticated") is not False):
        out["reason"] = "ORIGINAL_8_COMPONENT_PPI_EVENT_STUDY_NOT_VALID"
        return out
    reactions = study.get("fx_usd_normalized_m15_h1_h4_bps")
    if (type(reactions) is not dict or set(reactions) != set(USD_FX)
            or any(type(x) is not dict or set(x) != {"M15", "H1", "H4"}
                   for x in reactions.values())):
        out["reason"] = "SEVEN_FX_REACTION_HORIZONS_INCOMPLETE"
        return out

    # A SECOND source read, not a caller-written "passed" status.
    td = inspect_ppi_pre_event_snapshot_lab(
        raw_html=packet.td_html,receipt=packet.td_capture,as_of_utc=as_of_utc)
    te = inspect_te_ppi_snapshot_lab(
        raw_html=packet.te_html,capture=packet.te_capture,as_of_utc=as_of_utc)
    actual = inspect_ppi_oct2026_first_print_lab(
        raw_html=packet.bls_html,receipt=packet.bls_capture,as_of_utc=as_of_utc)
    surprise = compare_ppi_actual_to_frozen_consensus_lab(
        actual=actual,td_snapshot=td,te_snapshot=te)
    if (td.get("source_body_sha256") != TD_PRE_EVENT_HTML_SHA256
            or te.get("source_sha256") != TE_PRE_EVENT_HTML_SHA256
            or actual.get("source_sha256") != study.get("post_release_bls_sha256_claim")
            or td.get("source_body_sha256") != study.get("pre_event_td_sha256")
            or te.get("source_sha256") != study.get("pre_event_te_sha256")
            or surprise.get("state") != "LAB_PPI_RESEARCH_SURPRISE_ONLY_UNATTESTED"):
        out["reason"] = "SECOND_SOURCE_REPLAY_DIVERGED_FROM_PPI_STUDY"
        return out

    # Publisher Last-Modified is only untrusted HTTP metadata, and using it
    # in the generic publication field does NOT authenticate first-seen.
    try:
        claimed_modified = datetime.fromisoformat(
            td["publisher_last_modified_http_claim"])
    except (KeyError, TypeError, ValueError, OverflowError):
        out["reason"] = "TD_HTTP_LAST_MODIFIED_CLAIM_NOT_AVAILABLE"
        return out

    mapped = {}
    for name, series, expected_field, actual_field, surprise_field, study_field in _FIELDS:
        metric = MetricIdentity(
            currency="USD",series_id=series,reference_period="2026-10",
            transformation="MOM",seasonal_adjustment="SA",unit="PERCENT")
        consensus = PreEventConsensus(
            metric=metric,numeric_value=td[expected_field],
            source_url=TD_URL,
            original_sha256_claim=td["source_body_sha256"],
            published_at_utc=claimed_modified,
            locally_captured_at_utc=packet.td_capture.finished_at_utc)
        first_print = OfficialActual(
            metric=metric,numeric_value=actual[actual_field],
            official_source_url=OFFICIAL_URL,
            original_sha256_claim=actual["source_sha256"],
            scheduled_release_at_utc=RELEASE_UTC,
            # Request start is a lower-bound observation, NOT a verified
            # issuer publication timestamp; the generic tool marks it CLAIM.
            published_at_utc=packet.bls_capture.started_utc,
            locally_captured_at_utc=packet.bls_capture.finished_utc,
            first_print_vintage_claim="FIRST_PRINT_CLAIM_ONLY")
        mapped_report = map_metric(
            event_root_id=ROOT_EVENT,consensus=consensus,actual=first_print,
            inspected_at_utc=as_of_utc,price_claims=None)
        if (mapped_report.get("state") != _METRIC_COMPLETE
                or mapped_report.get("actual_minus_consensus_metric_units") !=
                    surprise.get(surprise_field)
                or mapped_report.get("actual_minus_consensus_metric_units") !=
                    study.get(study_field)
                or mapped_report.get("single_independent_economic_event_count") != 1
                or mapped_report.get("trade_authorized") is not False
                or mapped_report.get("calibrated_probability") is not None):
            out["reason"] = "PPI_AND_GENERIC_METRIC_SURPRISE_DISAGREE_" + name.upper()
            return out
        mapped[name] = {
            "series_id":series,
            "reference_period":"2026-10",
            "transformation":"MOM",
            "seasonal_adjustment":"SA",
            "consensus_source_original_sha256":td["source_body_sha256"],
            "actual_source_original_sha256":actual["source_sha256"],
            "consensus_value_documentary":td[expected_field],
            "actual_value_documentary":actual[actual_field],
            "actual_minus_consensus_percentage_points_documentary":
                surprise[surprise_field],
            "impact_on_usd_calibrated":False,
            "forecast":None,
        }

    out.update({
        "state":"LAB_PPI_TWO_REAL_SOURCE_METRICS_MAPPED_GENERIC_DOCUMENTARY_NO_GO",
        "reason":"ONE_PPI_EVENT_TWO_METRICS_SEVEN_REACTIONS_NOT_PREDICTIVE",
        "documentary_metric_count":2,
        "independent_economic_event_count_documentary":1,
        "metrics":mapped,
        "seven_usd_fx_pair_reactions_rechecked":7,
        "reaction_horizons_rechecked":["M15","H1","H4"],
        "first_print_and_consensus_source_bytes_replayed_locally":True,
    })
    return out

__all__=("SCHEMA","replay_ppi_originals_to_generic_event_lab")
