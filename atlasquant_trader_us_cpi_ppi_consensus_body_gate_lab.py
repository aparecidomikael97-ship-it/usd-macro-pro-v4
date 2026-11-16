"""PPI TD/TE original-byte consensus admission at CPI/PPI PIT cutoffs, LAB.

The lower PIT engine accepts a caller's arbitrary consensus value and SHA
as a local CLAIM. This higher source-bound bridge refuses to accept those
claimed fields as witnessed consensus unless TWO *frozen* pre-release PPI
source digests match and their exact HTML parsers independently extract the
same correctly named SA-MoM values. TD previous != consensus. Trading
Economics *own forecast* != analyst consensus.

A retrospectively discovered CPI preview is NEVER admitted as a pre-event
vintage; this module requires a future distinct CPI pre-event original-bytes
validator before any CPI consensus becomes a PIT feature.

No network, filesystem, scheduler, MT5, broker I/O, trading or FX forecasts.
Even two replayed local source bytes and HTTP-date CLAIMS are not an
independent proof of a first-seen time or pre-registered model prediction.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any

from atlasquant_trader_fx28_macro_event_surprise_reaction_contract_lab import (
    MetricIdentity, PreEventConsensus,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    TD_PRE_EVENT_HTML_SHA256, TE_PRE_EVENT_HTML_SHA256,
    PRE_EVENT_HEADLINE_CONSENSUS_MOM, PRE_EVENT_CORE_CONSENSUS_MOM,
)
from atlasquant_trader_us_cpi_ppi_pit_visibility_cutoff_lab import EventVintageClaim
from atlasquant_trader_us_cpi_ppi_official_body_join_lab import (
    inspect_us_cpi_ppi_official_body_join_lab,
)
from atlasquant_trader_us_ppi_pre_event_preview_lab import (
    LocalCaptureClaim, EVENT_RELEASE_UTC, URL as TD_URL,
    inspect_ppi_pre_event_snapshot_lab,
)
from atlasquant_trader_us_ppi_te_second_consensus_lab import (
    Capture as TeCapture, SOURCE as TE_URL, EVENT as TE_RELEASE,
    inspect_te_ppi_snapshot_lab,
)

SCHEMA = "ATLASQUANT_CPI_PPI_PRE_EVENT_CONSENSUS_SOURCE_BOUND_PIT_LAB_V1"
_EXPECTED = (PRE_EVENT_HEADLINE_CONSENSUS_MOM, PRE_EVENT_CORE_CONSENSUS_MOM)
_PPI_METRIC = MetricIdentity(
    currency="USD", series_id="US_PPI_FINAL_DEMAND",
    reference_period="2026-10", transformation="MOM",
    seasonal_adjustment="SA", unit="PERCENT",
)


@dataclass(frozen=True)
class PpiPreEventOriginalPair:
    td_original_html: bytes | None
    td_http_capture: LocalCaptureClaim | None
    te_original_html: bytes | None
    te_http_capture: TeCapture | None


def _utc(t: Any) -> datetime | None:
    if type(t) is not datetime or t.tzinfo is None or t.microsecond:
        return None
    try:
        return t.astimezone(timezone.utc) if t.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _num(t: Any) -> Decimal | None:
    if type(t) is not str:
        return None
    try:
        d = Decimal(t)
        return d if d.is_finite() else None
    except (ValueError, InvalidOperation):
        return None


def _no_pair(reason: str) -> dict[str, Any]:
    return {
        "state": "LAB_PPI_PRE_EVENT_SOURCE_PAIR_NOT_ADMISSIBLE_NO_GO",
        "reason": reason,
        "headline_consensus_from_two_original_bodies_pct": None,
        "core_consensus_from_two_original_bodies_pct": None,
        "td_original_source_reconciled": False,
        "te_original_source_reconciled": False,
        "both_source_local_capture_claims_pre_event": False,
        "publisher_first_seen_independently_authenticated": False,
        "analyst_poll_methodology_independently_authenticated": False,
        "te_own_forecast_counted_as_consensus": False,
        "research_only": True,
    }


def _inspect_original_pair(
    *, sources: Any, cutoff: Any,
    # The two pinned digests below are passed only by the public wrapper.
    # Unit tests can exercise the parser composition on SYNTHETIC fixtures,
    # without replacing the production lock.
    expected_td_digest: str, expected_te_digest: str,
) -> dict[str, Any]:
    out = _no_pair("ORIGINAL_PRE_EVENT_TD_TE_SOURCE_BYTES_UNAVAILABLE")
    if type(sources) is not PpiPreEventOriginalPair:
        return out
    if (type(sources.td_original_html) is not bytes
            or type(sources.te_original_html) is not bytes
            or type(sources.td_http_capture) is not LocalCaptureClaim
            or type(sources.te_http_capture) is not TeCapture):
        return out
    d = _utc(cutoff)
    td_end = _utc(sources.td_http_capture.finished_at_utc)
    te_end = _utc(sources.te_http_capture.finished_utc)
    if d is None or td_end is None or te_end is None:
        out["reason"] = "INVALID_CUTOFF_OR_PRE_EVENT_CAPTURE_CLOCK"
        return out
    # Enforce visibility BEFORE reading/parsing either potentially FUTURE body.
    if td_end > d or te_end > d:
        out["reason"] = "SOURCE_CAPTURE_AFTER_RESEARCH_CUTOFF_NOT_VISIBLE"
        return out
    if not (td_end < EVENT_RELEASE_UTC == TE_RELEASE and te_end < TE_RELEASE):
        out["reason"] = "SOURCE_CAPTURE_NOT_PRE_RELEASE"
        return out
    if (sha256(sources.td_original_html).hexdigest() != expected_td_digest
            or sha256(sources.te_original_html).hexdigest() != expected_te_digest
            or expected_td_digest == expected_te_digest):
        out["reason"] = "PRECOMMITTED_TD_TE_ORIGINAL_DIGEST_MISMATCH"
        return out

    td = inspect_ppi_pre_event_snapshot_lab(
        raw_html=sources.td_original_html,
        receipt=sources.td_http_capture, as_of_utc=d)
    te = inspect_te_ppi_snapshot_lab(
        raw_html=sources.te_original_html,
        capture=sources.te_http_capture, as_of_utc=d)
    if (td.get("state") != "LAB_PRE_EVENT_PPI_CONSENSUS_ARCHIVED_LOCAL_NO_TRADE"
            or te.get("state") != "LAB_TE_PRE_EVENT_CONSENSUS_AND_OWN_FORECAST_DISTINGUISHED"
            or td.get("source_body_sha256") != expected_td_digest
            or te.get("source_sha256") != expected_te_digest
            or td.get("capture_finished_utc_claim") != td_end.isoformat()
            or te.get("both_consensus_and_forecast_separate") is not True):
        out["reason"] = "TD_TE_ORIGINAL_HTML_PARSER_OR_CAPTURE_VALIDATION_FAILED"
        return out
    if (td.get("headline_consensus_mom_pct") != te.get("headline_consensus_mom_pct")
            or td.get("core_consensus_mom_pct") != te.get("core_consensus_mom_pct")
            or _num(td.get("headline_consensus_mom_pct")) != _num(_EXPECTED[0])
            or _num(td.get("core_consensus_mom_pct")) != _num(_EXPECTED[1])):
        out["reason"] = "TD_TE_CONSENSUS_DISAGREEMENT_OR_PRE_EVENT_VALUES_CHANGED"
        return out
    try:
        published = _utc(parsedate_to_datetime(
            sources.td_http_capture.last_modified_http))
    except (ValueError, TypeError, OverflowError, IndexError):
        published = None
    if published is None or published > td_end or published >= EVENT_RELEASE_UTC:
        out["reason"] = "INVALID_TD_LAST_MODIFIED_PUBLICATION_CLAIM"
        return out
    out.update({
        "state": "LAB_PPI_PRE_EVENT_TD_TE_BYTES_AND_METRICS_LOCALLY_RECONCILED_NO_GO",
        "reason": "TWO_PRE_RELEASE_SOURCE_CLAIMS_REPLAYED_BUT_FIRST_SEEN_UNATTESTED",
        "headline_consensus_from_two_original_bodies_pct":
            td["headline_consensus_mom_pct"],
        "core_consensus_from_two_original_bodies_pct":
            td["core_consensus_mom_pct"],
        "td_original_source_reconciled": True,
        "te_original_source_reconciled": True,
        "both_source_local_capture_claims_pre_event": True,
        "td_capture_utc_local_claim": td_end.isoformat(),
        "te_capture_utc_local_claim": te_end.isoformat(),
        "td_last_modified_utc_claim": published.isoformat(),
        "source_replay_eligible_at_cutoff_locally_claimed_only": True,
    })
    return out


def inspect_us_cpi_ppi_source_bound_consensus_lab(
    *, decision_cutoff_utc: Any, research_horizon: Any,
    event_claims: Any, actual_http_receipts: Any,
    ppi_original_pair: Any,
) -> dict[str, Any]:
    """Admit only source-parsed and temporally visible *local* PPI consensus.

    Unknown CPI consensus, third-party own forecast, backfilled or missing
    pre-event source is never passed to the older PIT engine as an input.
    Even when two sources match, the result remains research-only/unattested.
    """
    cutoff = _utc(decision_cutoff_utc)
    by_kind: dict[str, EventVintageClaim] = {}
    if (cutoff is not None and type(event_claims) in (tuple, list)
            and len(event_claims) == 2):
        for item in event_claims:
            if (type(item) is not EventVintageClaim
                    or item.kind not in ("CPI", "PPI")
                    or item.kind in by_kind):
                by_kind = {}
                break
            by_kind[item.kind] = item

    probe = _inspect_original_pair(
        sources=ppi_original_pair, cutoff=cutoff,
        expected_td_digest=TD_PRE_EVENT_HTML_SHA256,
        expected_te_digest=TE_PRE_EVENT_HTML_SHA256)
    eligible = (probe["state"] ==
        "LAB_PPI_PRE_EVENT_TD_TE_BYTES_AND_METRICS_LOCALLY_RECONCILED_NO_GO")
    source_claim_rejected = False
    if set(by_kind) == {"CPI", "PPI"}:
        # The CPI preview published before release was discovered later, and
        # no original pre-release CPI consensus bytes are supplied here.
        # Never promote its published_at claim to a captured_at timestamp.
        cpi = replace(by_kind["CPI"], consensus=None,
                      consensus_source_bytes=None)
        ppi = replace(by_kind["PPI"], consensus=None,
                      consensus_source_bytes=None)
        if eligible:
            receipt = ppi_original_pair.td_http_capture
            published = _utc(parsedate_to_datetime(receipt.last_modified_http))
            end = _utc(receipt.finished_at_utc)
            generated = PreEventConsensus(
                metric=_PPI_METRIC,
                numeric_value=probe["headline_consensus_from_two_original_bodies_pct"],
                source_url=TD_URL, original_sha256_claim=TD_PRE_EVENT_HTML_SHA256,
                published_at_utc=published, locally_captured_at_utc=end,
            )
            supplied = by_kind["PPI"].consensus
            if supplied is not None and supplied != generated:
                source_claim_rejected = True
                eligible = False
                probe["reason"] = "DECLARED_PPI_CONSENSUS_DIFFERS_FROM_PARSER_SOURCE"
            elif (by_kind["PPI"].consensus_source_bytes is not None
                  and by_kind["PPI"].consensus_source_bytes !=
                      ppi_original_pair.td_original_html):
                source_claim_rejected = True
                eligible = False
                probe["reason"] = "DECLARED_PPI_CONSENSUS_BYTES_DIFFER_FROM_TD_ORIGINAL"
            if eligible:
                ppi = replace(ppi, consensus=generated,
                              consensus_source_bytes=ppi_original_pair.td_original_html)
        forwarded = (cpi, ppi)
    else:
        forwarded = ()

    base = inspect_us_cpi_ppi_official_body_join_lab(
        decision_cutoff_utc=cutoff,
        research_horizon=research_horizon,
        event_claims=forwarded,
        actual_http_receipts=actual_http_receipts,
    )
    base["schema"] = SCHEMA
    base["ppi_pre_event_original_pair"] = probe
    base["ppi_consensus_admitted_from_two_pinned_pre_event_html"] = eligible and (
        base.get("economic_events_reconciled") == 2)
    base["cpi_pre_event_consensus_admitted"] = False
    base["cpi_retrospectively_found_preview_blocked_from_historical_forecast"] = True
    base["supplied_ppi_consensus_not_from_original_source_rejected"] = source_claim_rejected
    base["ppi_td_and_te_are_one_event_not_two_independent_economic_trials"] = True
    base["publisher_first_seen_independently_attested"] = False
    base["market_effect_calibrated"] = False
    base["trade_authorized"] = False
    base["publishable"] = False
    base["operational_bias"] = "AGUARDAR"
    base["validated_fx_accuracy"] = None
    base["directional_bias"] = None
    # Headline/Core are separate measures of ONE PPI event; no synthetic
    # inflation YoY for the missing October-2025 CPI comparison base.
    return base


__all__ = (
    "SCHEMA", "PpiPreEventOriginalPair",
    "inspect_us_cpi_ppi_source_bound_consensus_lab",
)
