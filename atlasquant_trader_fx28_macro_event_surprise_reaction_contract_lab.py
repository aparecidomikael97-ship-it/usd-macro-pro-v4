"""FX28 generic economic-event surprise -> price association contract (LAB).

First reusable 8-currency schema for a single macro event. Separates:
  1. same-series, same-period pre-event consensus vs claimed first-print actual;
  2. optional complete 7-cross locally claimed post-event price movements;
  3. the ABSENT out-of-sample response model and calibrated probabilities.

It does NOT capture publisher data, trust caller timestamps, authenticate first
prints/broker prices, calculate signed FX impact, estimate causality, forecast,
or activate trades. PPI/M15, CPI, labor and activity must share precise
metric IDs; mixing SA MoM, NSA YoY, indexes and percentage points blocks.
Seven related FX crosses are one economic-event cohort, not seven trials.

All hashes, hostnames and clocks are input CLAIMS pending independent custody.
No network, storage, MT5, GitHub changes, schedules or paid services.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import urlsplit

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_FX28_GENERIC_MACRO_EVENT_SURPRISE_REACTION_LAB_V1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_METRIC = re.compile(r"[A-Z][A-Z0-9_]{4,63}\Z")
_PERIOD = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])\Z")
_ROOT = re.compile(r"[A-Z][A-Z0-9_.:-]{5,79}\Z")
_NUM = re.compile(r"-?(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,6})?\Z")
_PRICE = re.compile(r"(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,8})?\Z")
_HORIZONS = {"M15": 15, "H1": 60, "H4": 240}
# Same conservative maximum consensus lookback as the independent
# OOS event-cluster ledger. An ancient forecast is not a contemporaneous
# pre-release consensus, even if its original bytes can still be replayed.
_CONSENSUS_LOOKBACK = timedelta(days=60)
_HOSTS = {
    "USD": ("bls.gov", "bea.gov", "federalreserve.gov"),
    "EUR": ("ecb.europa.eu", "europa.eu"),
    "GBP": ("ons.gov.uk", "bankofengland.co.uk"),
    "JPY": ("boj.or.jp", "stat.go.jp"),
    "CHF": ("snb.ch", "bfs.admin.ch"),
    "CAD": ("statcan.gc.ca", "bankofcanada.ca"),
    "AUD": ("abs.gov.au", "rba.gov.au"),
    "NZD": ("stats.govt.nz", "rbnz.govt.nz"),
}
# For recognized US economic series, a genuine-looking federal domain
# must still be the agency that publishes THIS series. E.g. BEA does not
# issue BLS PPI, and the Federal Reserve statement is not the CPI release.
# Unknown series remain documentary-only and cannot turn into FX signals.
_US_ISSUER_BY_SERIES_PREFIX = {
    "US_PPI_": "bls.gov",
    "US_CPI_": "bls.gov",
    "US_NFP_": "bls.gov",
    "US_PCE_": "bea.gov",
    "US_GDP_": "bea.gov",
    "US_FED_": "federalreserve.gov",
    "US_FOMC_": "federalreserve.gov",
}

@dataclass(frozen=True)
class MetricIdentity:
    currency: str
    series_id: str
    reference_period: str
    transformation: str
    seasonal_adjustment: str
    unit: str

@dataclass(frozen=True)
class PreEventConsensus:
    metric: MetricIdentity
    numeric_value: str
    source_url: str
    original_sha256_claim: str
    published_at_utc: datetime
    locally_captured_at_utc: datetime

@dataclass(frozen=True)
class OfficialActual:
    metric: MetricIdentity
    numeric_value: str
    official_source_url: str
    original_sha256_claim: str
    scheduled_release_at_utc: datetime
    published_at_utc: datetime
    locally_captured_at_utc: datetime
    first_print_vintage_claim: str

@dataclass(frozen=True)
class LocalPriceReaction:
    pair: str
    horizon: str
    baseline_price: str
    endpoint_price: str
    baseline_at_utc: datetime
    endpoint_at_utc: datetime
    local_price_original_sha256_claim: str


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _number(value: Any, *, price: bool = False) -> Decimal | None:
    if type(value) is not str or len(value) > 24:
        return None
    if not (_PRICE if price else _NUM).fullmatch(value):
        return None
    try:
        x = Decimal(value)
    except InvalidOperation:
        return None
    return x if x.is_finite() and (not price or x > 0) else None


def _https_host(value: Any) -> str | None:
    if type(value) is not str or not 12 <= len(value) <= 500:
        return None
    try:
        u = urlsplit(value)
        if (u.scheme != "https" or not u.hostname or u.username is not None
                or u.password is not None or u.fragment or not u.path
                or (u.port is not None and u.port != 443)
                or u.netloc.lower() not in
                (u.hostname.lower(), u.hostname.lower() + ":443")
                or u.query):
            return None
        return u.hostname.lower()
    except (TypeError, ValueError):
        return None


def _metric_valid(m: Any) -> bool:
    return (type(m) is MetricIdentity
            and m.currency in CURRENCIES
            and type(m.series_id) is str and _METRIC.fullmatch(m.series_id) is not None
            and type(m.reference_period) is str and _PERIOD.fullmatch(m.reference_period) is not None
            and m.transformation in ("MOM", "YOY", "LEVEL", "CHANGE")
            and m.seasonal_adjustment in ("SA", "NSA", "NA")
            and m.unit in ("PERCENT", "THOUSANDS", "INDEX_POINTS", "COUNT")
            and not (m.transformation in ("MOM", "YOY") and m.unit != "PERCENT")
            and not (m.transformation == "CHANGE" and m.unit == "INDEX_POINTS"))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_MACRO_EVENT_STUDY_BLOCKED_NO_GO",
        "reason": reason,
        "event_root_id": None,
        "metric_identity": None,
        "single_independent_economic_event_count": 0,
        "consensus_minus_actual_is_not_directional_effect": True,
        "pre_event_consensus_independently_authenticated": False,
        "consensus_publication_within_60_day_pre_event_window_claim": False,
        "first_print_actual_independently_authenticated": False,
        "issuer_first_seen_independently_authenticated": False,
        "source_digest_authenticates_only_claimed_local_bytes": True,
        "broker_price_and_bid_ask_independently_authenticated": False,
        "actual_minus_consensus_metric_units": None,
        "economic_surprise_label_documentary_only": None,
        "full_seven_pair_cohort_documentary": False,
        "fx_pair_outcome_claim_count": 0,
        "seven_pair_outcomes_are_not_independent_events": True,
        "fx_reaction_claims": [],
        "observed_correlation_not_causing_currency_direction": True,
        "historical_out_of_sample_accuracy": None,
        "calibrated_probability": None,
        "predicted_currency_direction": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "scheduler_enabled": False,
        "http_calls": 0, "mt5_calls": 0, "file_writes": 0,
        "new_cost_brl": 0,
    }


def inspect_macro_event_surprise_reaction_lab(
    *, event_root_id: Any, consensus: Any, actual: Any,
    price_claims: Any = None, inspected_at_utc: Any,
) -> dict[str, Any]:
    result = _blocked("INVALID_CLAIM_TYPE_METRIC_IDENTITY_OR_CLOCK")
    now = _utc(inspected_at_utc)
    if (type(event_root_id) is not str or _ROOT.fullmatch(event_root_id) is None
            or type(consensus) is not PreEventConsensus
            or type(actual) is not OfficialActual
            or now is None
            or not _metric_valid(consensus.metric)
            or consensus.metric != actual.metric):
        return result
    metric = consensus.metric
    consensus_host = _https_host(consensus.source_url)
    official_host = _https_host(actual.official_source_url)
    # Different host strings do not prove independent source organizations:
    # api.bls.gov, www.bls.gov and bls.gov all belong to the same issuer.
    issuer_domains = _HOSTS[metric.currency]
    def issuer_owned_host(host: str) -> bool:
        return any(host == root or host.endswith("." + root)
                   for root in issuer_domains)
    if (consensus_host is None or official_host is None
            or not issuer_owned_host(official_host)
            or issuer_owned_host(consensus_host)):
        result["reason"] = "UNTRUSTED_OR_ISSUER_COLLIDING_CONSENSUS_OR_OFFICIAL_URL"
        return result
    if metric.currency == "USD":
        authority = next((
            host for prefix, host in _US_ISSUER_BY_SERIES_PREFIX.items()
            if metric.series_id.startswith(prefix)
        ), None)
        if (authority is not None
                and official_host != authority
                and not official_host.endswith("." + authority)):
            result["reason"] = "OFFICIAL_PUBLISHER_DOES_NOT_MATCH_US_METRIC"
            return result
    if any(type(h) is not str or _SHA.fullmatch(h) is None for h in (
            consensus.original_sha256_claim, actual.original_sha256_claim)):
        result["reason"] = "MISSING_SOURCE_ORIGINAL_SHA_CLAIMS"
        return result
    if consensus.original_sha256_claim == actual.original_sha256_claim:
        result["reason"] = "PRE_EVENT_CONSENSUS_AND_POST_EVENT_ACTUAL_SAME_BYTES"
        return result
    cpub = _utc(consensus.published_at_utc)
    ccap = _utc(consensus.locally_captured_at_utc)
    rel = _utc(actual.scheduled_release_at_utc)
    apub = _utc(actual.published_at_utc)
    acap = _utc(actual.locally_captured_at_utc)
    if (None in (cpub, ccap, rel, apub, acap)
            or not cpub <= ccap < rel <= apub <= acap <= now):
        result["reason"] = "CONSENSUS_NOT_PRE_EVENT_OR_ACTUAL_NOT_POST_RELEASE"
        return result
    if cpub < rel - _CONSENSUS_LOOKBACK:
        result["reason"] = "STALE_PRE_EVENT_CONSENSUS_PUBLISHED_OVER_60_DAYS_EARLY"
        return result
    if (actual.first_print_vintage_claim != "FIRST_PRINT_CLAIM_ONLY"
            or acap - apub > timedelta(days=90)):
        result["reason"] = "ACTUAL_VINTAGE_NOT_FIRST_PRINT_CLAIM_OR_AGE_INVALID"
        return result
    cvalue = _number(consensus.numeric_value)
    avalue = _number(actual.numeric_value)
    if cvalue is None or avalue is None:
        result["reason"] = "INVALID_OR_NONFINITE_METRIC_VALUE"
        return result
    # Values are in the same named unit and transformation; a percentage
    # minus a percentage is a percentage-POINT difference, not a percent
    # change in price, model edge, or FX-direction probability.
    difference = avalue - cvalue
    label = "ABOVE_CONSENSUS" if difference > 0 else (
        "BELOW_CONSENSUS" if difference < 0 else "IN_LINE_WITH_CONSENSUS")
    result.update({
        "state": "LAB_FX28_SINGLE_EVENT_SURPRISE_DOCUMENTARY_ONLY_NO_GO",
        "reason": "MATCHED_METRIC_ARITHMETIC_WITH_UNATTESTED_SOURCE_CUSTODY",
        "event_root_id": event_root_id,
        "metric_identity": {
            "currency": metric.currency, "series_id": metric.series_id,
            "reference_period": metric.reference_period,
            "transformation": metric.transformation,
            "seasonal_adjustment": metric.seasonal_adjustment,
            "unit": metric.unit,
        },
        "single_independent_economic_event_count": 1,
        "consensus_publication_within_60_day_pre_event_window_claim": True,
        "actual_minus_consensus_metric_units": format(difference, "f"),
        "economic_surprise_label_documentary_only": label,
    })
    if price_claims is None:
        return result
    expected = tuple(p for p in OFFICIAL_PAIRS
                     if metric.currency in split_pair(p))
    if type(price_claims) not in (tuple, list) or len(price_claims) != 7:
        return _blocked("SEVEN_COMPLETE_CROSS_PAIR_PRICE_CLAIMS_REQUIRED")
    if (len(expected) != 7
            or any(type(x) is not LocalPriceReaction for x in price_claims)
            or {x.pair for x in price_claims} != set(expected)):
        return _blocked("FX_REACTION_PAIR_COHORT_INCOMPLETE_OR_DUPLICATED")
    horizon = price_claims[0].horizon
    if horizon not in _HORIZONS or any(p.horizon != horizon for p in price_claims):
        return _blocked("MIXED_OR_UNKNOWN_FX_REACTION_HORIZON")
    # A seven-cross 'M15' reaction must represent ONE synchronized price
    # experiment, not seven separately chosen baselines/endpoints. Keep a
    # bounded end-point tolerance for bar alignment, never hours/days late.
    paired_baseline_utc = None
    paired_endpoint_utc = None
    output = []
    for pair in expected:
        p = next(r for r in price_claims if r.pair == pair)
        baseline = _number(p.baseline_price, price=True)
        endpoint = _number(p.endpoint_price, price=True)
        t0 = _utc(p.baseline_at_utc)
        t1 = _utc(p.endpoint_at_utc)
        if (baseline is None or endpoint is None or t0 is None or t1 is None
                or not rel - timedelta(minutes=15) <= t0 <= rel
                or not rel + timedelta(minutes=_HORIZONS[horizon]) <= t1 <= now
                or t1 > rel + timedelta(minutes=_HORIZONS[horizon] + 15)
                or type(p.local_price_original_sha256_claim) is not str
                or _SHA.fullmatch(p.local_price_original_sha256_claim) is None):
            return _blocked("FX_PRICE_CLAIM_NUMERIC_TIME_OR_SOURCE_HASH_INVALID")
        if paired_baseline_utc is None:
            paired_baseline_utc, paired_endpoint_utc = t0, t1
        elif t0 != paired_baseline_utc or t1 != paired_endpoint_utc:
            return _blocked("SEVEN_FX_REACTIONS_HAVE_DIFFERENT_PRICE_WINDOWS")
        bps = ((endpoint / baseline - 1) * Decimal(10000)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP)
        output.append({
            "pair": pair, "horizon": horizon,
            "locally_claimed_change_bps": format(bps, "f"),
            "local_price_source_sha256_claim": p.local_price_original_sha256_claim,
            "change_is_not_fx_currency_strength_causal_estimate": True,
            "broker_price_source_independently_verified": False,
        })
    result.update({
        "state": "LAB_FX28_SINGLE_EVENT_AND_7FX_REACTIONS_DOCUMENTARY_ONLY_NO_GO",
        "reason": "ONE_EVENT_SEVEN_CORRELATED_PRICE_MOVEMENT_CLAIMS_NOT_FX_FORECAST",
        "fx_pair_outcome_claim_count": 7,
        "full_seven_pair_cohort_documentary": True,
        "all_seven_pairs_share_identical_baseline_and_endpoint_clocks": True,
        "shared_price_baseline_utc_claim": paired_baseline_utc.isoformat(),
        "shared_price_endpoint_utc_claim": paired_endpoint_utc.isoformat(),
        "fx_reaction_claims": output,
    })
    return result


__all__ = (
    "SCHEMA", "MetricIdentity", "PreEventConsensus", "OfficialActual",
    "LocalPriceReaction", "inspect_macro_event_surprise_reaction_lab",
)
