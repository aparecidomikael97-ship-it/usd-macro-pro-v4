"""AtlasQuant Motor A: PIT-oriented FX28 macro release cohort readiness, LAB.

Treats the simultaneous M15/H1/H4 moves of seven FX crosses, and multiple
metrics within one press release, as ONE economic event candidate. Concurrent
releases and overlapping price-observation windows become ONE conservative
research cluster. A chronological OOS split never divides a cluster or
allows shared observation hours across train and holdout.

Input time/digest/consensus/price values are UNTRUSTED caller claims. This
module NEVER independently authenticates any record. It never calculates a
hit rate, calibrated probability, currency bias or forex signal. This is a
future research database consistency and leakage-control component.

Pure function. No web/API, filesystem, GitHub, MT5, orders, automation or fees.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
import re

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_us_dec2026_frozen_evaluation_protocol_lab import (
    FROZEN_PLAN, PINNED_PLAN_SHA256, canonical_frozen_plan_bytes_lab,
)

SCHEMA="ATLASQUANT_MOTOR_A_MACRO_OOS_EVENT_CLUSTER_LEDGER_LAB_V1"
_HORIZONS=("M15","H1","H4")
_SHA=re.compile(r"[a-f0-9]{64}\Z")
_ROOT=re.compile(r"[A-Z][A-Z0-9_.:-]{5,79}\Z")
_METRIC=re.compile(r"[A-Z][A-Z0-9_]{4,79}\Z")
_STUDY_MAX=timedelta(hours=4)
_BASELINE_PRE=timedelta(minutes=15)
_SPLIT_EMBARGO=timedelta(hours=4)
_PRECOMMIT_LOOKBACK=timedelta(hours=12)
_PRECOMMIT_FREEZE_BEFORE_RELEASE=timedelta(hours=1)
_FROZEN_DEC_ROOTS={
    row["root_id"]:row for row in FROZEN_PLAN["event_roots"]
}

@dataclass(frozen=True)
class MacroEventCohortClaim:
    root_id:str
    issuer_currency:str
    scheduled_release_at_utc:datetime
    consensus_locally_captured_at_utc:datetime
    actual_locally_captured_at_utc:datetime
    price_locally_captured_at_utc:datetime
    metric_ids:tuple[str,...]
    price_pairs:tuple[str,...]
    horizons:tuple[str,...]
    consensus_original_sha256_claim:str
    actual_original_sha256_claim:str
    price_archive_sha256_claim:str
    pre_event_forecast_direction:str
    pre_event_forecast_issued_at_utc:datetime|None
    competing_release_roots:tuple[str,...]=()


def _utc(t:Any)->datetime|None:
    if not isinstance(t,datetime) or t.tzinfo is None:
        return None
    try:
        return t.astimezone(timezone.utc) if t.utcoffset() is not None else None
    except (ValueError,TypeError,OverflowError):
        return None


def _base(reason:str)->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "state":"LAB_MOTOR_A_EVENT_COHORT_LEDGER_BLOCKED_NO_GO",
        "reason":reason,
        "untrusted_event_roots_checked":0,
        "untrusted_abstention_event_roots_checked":0,
        "untrusted_directional_forecast_claims_checked":0,
        "frozen_dec2026_event_roots_seen":[],
        "frozen_dec2026_abstain_rule_verified_claim_only":False,
        "directional_forecast_freeze_before_release_minutes":60,
        "untrusted_metric_rows_checked":0,
        "untrusted_fx_pair_observations_checked":0,
        "untrusted_candidate_cluster_count":0,
        "untrusted_total_cluster_count":0,
        "unresolved_competing_release_root_count":0,
        "quarantined_unresolved_confounder_cluster_count":0,
        "candidate_train_cluster_count":0,
        "candidate_holdout_cluster_count":0,
        "candidate_purged_boundary_cluster_count":0,
        "clusters":[],
        "all_event_times_and_origins_independently_authenticated":False,
        "all_pre_event_consensus_vintages_independently_authenticated":False,
        "historical_broker_prices_independently_authenticated":False,
        "all_release_confounders_discovered":False,
        "cross_pairs_not_independent_economic_samples":True,
        "multiple_metrics_same_release_not_independent_events":True,
        "overlapping_observation_windows_not_independent_trials":True,
        "forecasts_not_retrospectively_fabricated":False,
        "no_hindsight_scoring":True,
        "research_cluster_counts_are_only_claims":True,
        "can_train_calibrated_model":False,
        "out_of_sample_accuracy":None,
        "calibrated_probability":None,
        "predicted_currency_direction":None,
        "trade_authorized":False,
        "publishable":False,
        "operational_bias":"AGUARDAR",
        "no_change_to_frozen_672_slot_campaign":True,
        "http_requests":0,"mt5_calls":0,"file_writes":0,
        "new_cost_brl":0,
    }


def audit_historical_macro_event_cohorts_lab(
    *, event_claims:Any, inspected_at_utc:Any, holdout_begins_at_utc:Any,
)->dict[str,Any]:
    out=_base("INVALID_INPUT_OR_TIME")
    now=_utc(inspected_at_utc)
    split=_utc(holdout_begins_at_utc)
    if (now is None or split is None or split>now
            or type(event_claims) not in (tuple,list)
            or len(event_claims)>512):
        return out
    pinned=canonical_frozen_plan_bytes_lab(FROZEN_PLAN)
    if (pinned is None or sha256(pinned).hexdigest()!=PINNED_PLAN_SHA256
            or len(_FROZEN_DEC_ROOTS)!=2
            or set(_FROZEN_DEC_ROOTS)!={
                "US_CPI_NOV2026","US_PPI_NOV2026"
            }):
        out["reason"]="FROZEN_DEC2026_RESEARCH_PROTOCOL_SHA_OR_ROOTS_CHANGED"
        return out
    if len(event_claims)==0:
        out.update({
            "state":"LAB_MOTOR_A_NO_HISTORICAL_EVENT_CLAIMS_NO_GO",
            "reason":"NO_UNTRUSTED_COHORT_ROWS_NO_PERFORMANCE_EVIDENCE",
        })
        return out
    if any(type(e) is not MacroEventCohortClaim for e in event_claims):
        out["reason"]="EVENT_CLAIM_TYPE_MISMATCH"
        return out

    claims=sorted(event_claims,key=lambda e:(
        _utc(e.scheduled_release_at_utc) or datetime.max.replace(tzinfo=timezone.utc),
        str(e.root_id)))
    seen_roots:set[str]=set()
    actual_sha_roots:dict[str,str]={}
    intervals:list[tuple[datetime,datetime]]=[]
    cohorts:list[MacroEventCohortClaim]=[]
    by_root:dict[str,int]={}
    frozen_roots_seen=[]
    for e in claims:
        rel=_utc(e.scheduled_release_at_utc)
        cons=_utc(e.consensus_locally_captured_at_utc)
        actual=_utc(e.actual_locally_captured_at_utc)
        px=_utc(e.price_locally_captured_at_utc)
        forecast_time=_utc(e.pre_event_forecast_issued_at_utc)
        if (type(e.root_id) is not str or not _ROOT.fullmatch(e.root_id)
                or e.root_id in seen_roots
                or e.issuer_currency not in CURRENCIES
                or None in (rel,cons,actual,px)
                or not rel-timedelta(days=60) <= cons < rel
                or not rel <= actual <= px <= now
                or px < rel+_STUDY_MAX
                or e.horizons != _HORIZONS
                or type(e.metric_ids) is not tuple or not e.metric_ids
                or len(e.metric_ids)>10
                or any(type(k) is not str or not _METRIC.fullmatch(k)
                       for k in e.metric_ids)
                or len(set(e.metric_ids))!=len(e.metric_ids)
                or type(e.competing_release_roots) is not tuple
                or len(e.competing_release_roots)>32
                or any(type(k) is not str or not _ROOT.fullmatch(k)
                       or k==e.root_id for k in e.competing_release_roots)
                or len(set(e.competing_release_roots))!=len(e.competing_release_roots)):
            out["reason"]="EVENT_ID_TIME_METRIC_OR_CONFOUNDER_CONTRADICTION"
            return out
        expected=tuple(p for p in OFFICIAL_PAIRS
                       if e.issuer_currency in split_pair(p))
        if len(expected)!=7 or e.price_pairs!=expected:
            out["reason"]="INCOMPLETE_NONCANONICAL_SEVEN_CROSS_FX_COHORT"
            return out
        sha_values=(
            e.consensus_original_sha256_claim,
            e.actual_original_sha256_claim,
            e.price_archive_sha256_claim,
        )
        if (any(type(v) is not str or not _SHA.fullmatch(v)
                for v in sha_values)
                or len(set(sha_values))!=3):
            out["reason"]="SOURCE_OR_PRICE_SHA_INVALID_OR_REUSED_IN_SAME_EVENT"
            return out
        earlier=actual_sha_roots.get(e.actual_original_sha256_claim)
        if earlier is not None and earlier!=e.root_id:
            out["reason"]="SAME_ACTUAL_BYTES_RELABELED_AS_SECOND_ECONOMIC_EVENT"
            return out
        if e.pre_event_forecast_direction not in ("UP","DOWN","ABSTAIN"):
            out["reason"]="INVALID_FORECAST_ENUM_NO_REAL_SIGNAL"
            return out
        # These exact December research events were pre-registered with
        # ABSTAIN and zero model forecasts in the SHA-pinned plan. No
        # separate historical ledger may replace ABSTAIN with a caller's
        # after-the-fact UP/DOWN claim or rename their release clock.
        frozen=_FROZEN_DEC_ROOTS.get(e.root_id)
        if frozen is not None:
            if (e.issuer_currency!="USD"
                    or rel.isoformat()!=frozen["release_utc"]
                    or frozen["forecast_direction"]!="ABSTAIN"
                    or e.pre_event_forecast_direction!="ABSTAIN"
                    or e.pre_event_forecast_issued_at_utc is not None):
                out["reason"]="FROZEN_DEC2026_EVENT_ABSTAIN_OR_CLOCK_OVERRIDE"
                return out
            frozen_roots_seen.append(e.root_id)
        if ((e.pre_event_forecast_direction=="ABSTAIN" and
             e.pre_event_forecast_issued_at_utc is not None)
                or (e.pre_event_forecast_direction in ("UP","DOWN")
                    and (forecast_time is None
                         or not rel-_PRECOMMIT_LOOKBACK<=forecast_time
                               <= rel-_PRECOMMIT_FREEZE_BEFORE_RELEASE
                         or forecast_time>now
                         or forecast_time<cons))):
            out["reason"]="MISSING_LATE_OR_REWRITTEN_PRE_EVENT_FORECAST"
            return out
        by_root[e.root_id]=len(cohorts)
        cohorts.append(e)
        intervals.append((rel-_BASELINE_PRE,rel+_STUDY_MAX))
        actual_sha_roots[e.actual_original_sha256_claim]=e.root_id
        seen_roots.add(e.root_id)

    # Union-find: overlapping event price windows cannot enter both train
    # and holdout. Confounder labels that are present join the same cluster.
    # Unknown named confounders do NOT prove absence of competing releases.
    parents=list(range(len(cohorts)))
    def find(i:int)->int:
        while parents[i]!=i:
            parents[i]=parents[parents[i]]
            i=parents[i]
        return i
    def union(i:int,j:int)->None:
        ri,rj=find(i),find(j)
        if ri!=rj:parents[max(ri,rj)]=min(ri,rj)
    for i,e in enumerate(cohorts):
        for j in range(i):
            if intervals[i][0]<=intervals[j][1] and intervals[j][0]<=intervals[i][1]:
                union(i,j)
            # Same calendar/consensus snapshot across two root IDs is
            # shared context, never two entirely independent information sets.
            elif (e.consensus_original_sha256_claim==cohorts[j].consensus_original_sha256_claim
                  or e.price_archive_sha256_claim==cohorts[j].price_archive_sha256_claim):
                union(i,j)
        for other in e.competing_release_roots:
            if other in by_root:
                union(i,by_root[other])
    # A later event can point at an earlier or later event; second pass
    # ensures all references count regardless of lexical order.
    for i,e in enumerate(cohorts):
        for other in e.competing_release_roots:
            if other in by_root:union(i,by_root[other])

    # CRITICAL: a competing release outside this input roster is NOT proof
    # that no other release existed. Two events sharing an unresolved
    # external root are also dependent on that same unknown news episode.
    # Union their cohorts BEFORE choosing a chronological holdout. The
    # missing root can never be treated as an independent trial or silently
    # omitted from the group and model evaluation.
    unresolved_by_root:dict[str,int]={}
    for i,e in enumerate(cohorts):
        for other in e.competing_release_roots:
            if other in by_root:
                continue
            previous=unresolved_by_root.get(other)
            if previous is None:
                unresolved_by_root[other]=i
            else:
                union(i,previous)

    groups:dict[int,list[int]]={}
    for i in range(len(cohorts)):
        groups.setdefault(find(i),[]).append(i)
    rendered=[]
    train=holdout=purged=quarantined=0
    for members in sorted(groups.values(),key=lambda a:(
        min(intervals[i][0] for i in a),
        tuple(cohorts[i].root_id for i in a),
    )):
        earliest=min(intervals[i][0] for i in members)
        latest=max(intervals[i][1] for i in members)
        missing_conf=sorted({
            ref for i in members
            for ref in cohorts[i].competing_release_roots
            if ref not in by_root
        })
        # The only defensible statistical classification for missing
        # competing-news provenance is QUARANTINE, not a purported
        # training/holdout sample. Retain it visibly in the denominator.
        if missing_conf:
            partition="QUARANTINED_UNRESOLVED_COMPETING_RELEASE_NO_GO"
            quarantined+=1
        elif latest < split-_SPLIT_EMBARGO:
            partition="CANDIDATE_TRAIN_UNATTESTED"
            train+=1
        elif earliest > split+_SPLIT_EMBARGO:
            partition="CANDIDATE_HOLDOUT_UNATTESTED"
            holdout+=1
        else:
            partition="PURGED_AROUND_HOLDOUT_BOUNDARY"
            purged+=1
        rendered.append({
            "root_ids":[cohorts[i].root_id for i in members],
            "event_roots_count":len(members),
            "metric_rows_count":sum(len(cohorts[i].metric_ids) for i in members),
            "correlated_seven_cross_spot_observations_count":7*len(members),
            "claimed_baseline_utc":earliest.isoformat(),
            "claimed_last_h4_close_utc":latest.isoformat(),
            "partition":partition,
            "other_macro_releases_not_locally_resolved":missing_conf,
            "can_count_as_authenticated_trial":False,
            "forecasts_can_be_scored":False,
        })
    out.update({
        "state":"LAB_MOTOR_A_MACRO_EVENT_CLUSTER_LEDGER_RECONCILED_NO_GO",
        "reason":"ALL_EVENT_ORIGINALS_CONSENSUS_CLOCKS_AND_PRICE_CUSTODY_UNATTESTED",
        "untrusted_event_roots_checked":len(cohorts),
        "untrusted_abstention_event_roots_checked":sum(
            e.pre_event_forecast_direction=="ABSTAIN" for e in cohorts),
        "untrusted_directional_forecast_claims_checked":sum(
            e.pre_event_forecast_direction in ("UP","DOWN") for e in cohorts),
        "frozen_dec2026_event_roots_seen":sorted(frozen_roots_seen),
        "frozen_dec2026_abstain_rule_verified_claim_only":True,
        "untrusted_metric_rows_checked":sum(len(e.metric_ids) for e in cohorts),
        "untrusted_fx_pair_observations_checked":7*len(cohorts),
        "untrusted_candidate_cluster_count":train+holdout+purged,
        "untrusted_total_cluster_count":len(rendered),
        "unresolved_competing_release_root_count":len(unresolved_by_root),
        "quarantined_unresolved_confounder_cluster_count":quarantined,
        "candidate_train_cluster_count":train,
        "candidate_holdout_cluster_count":holdout,
        "candidate_purged_boundary_cluster_count":purged,
        "clusters":rendered,
    })
    return out

__all__=("SCHEMA","MacroEventCohortClaim","audit_historical_macro_event_cohorts_lab")
