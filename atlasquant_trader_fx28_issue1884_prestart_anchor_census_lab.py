"""Issue #1884 first-seen *claims* against all 672 fixed FX28 opportunities.

Consume an explicit normalized snapshot of GitHub issue comments, including
the (possibly absent) server created_at and updated_at fields. A calendar
issue, a generic audit comment, or a hash-only "forecast commitment" is
not an independently authenticated source of pre-event forecasts.

This PURE LAB auditor verifies only that claim text follows the exact
predefined 28-pair window anchor format and does not contradict supplied
timestamps. Without independently authenticated published roster bytes,
real issuer vintage, pre-event external first-seen and broker NY17 prices,
NO window is scored as an accurate prediction. Every due slot without a
verified pre-event witness stays in the denominator as NOT_ISSUED.

No network, file IO, GitHub posting, backfill, MT5, positions, trading,
commercial alert, scheduler, or recalibration.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, EXPECTED_PAIR_HORIZON_SLOTS,
    _nominal_windows,
)
from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    HEADER as ANCHOR_HEADER, REPO, ISSUE_NUMBER,
)

SCHEMA="ATLASQUANT_FX28_ISSUE1884_PRESTART_ANCHOR_SNAPSHOT_CENSUS_LAB_V1"
MAX_COMMENTS=500
MAX_BODY=20_000
SHA64=re.compile(r"[0-9a-f]{64}\Z")
STAMP=re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
LABELS=("D1","W1")


def _utc(value:Any)->datetime|None:
    if not isinstance(value,datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError,TypeError,OverflowError):
        return None


def _parse_time(raw:Any)->datetime|None:
    if type(raw) is not str or STAMP.fullmatch(raw) is None:
        return None
    try:
        return datetime.strptime(raw,"%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def _anchor(body:str)->tuple[str,datetime,datetime,str]|None:
    """Recognize ONLY the nine exact hash-anchor lines, not random notes."""
    lines=body.split("\n")
    if len(lines)!=9 or lines[0]!=ANCHOR_HEADER:
        return None
    if (lines[1]!="campaign_id="+CAMPAIGN_ID
        or lines[5]!="pairs=28"
        or lines[7]!="research_only=true"
        or lines[8]!="trade_authorized=false"):
        return None
    if not lines[2].startswith("horizon="):
        return None
    horizon=lines[2][len("horizon="):]
    if horizon not in LABELS:
        return None
    if not lines[3].startswith("start_utc=") or not lines[4].startswith("end_utc="):
        return None
    if not lines[6].startswith("roster_sha256="):
        return None
    digest=lines[6][len("roster_sha256="):]
    if SHA64.fullmatch(digest) is None:
        return None
    start=_parse_time(lines[3][len("start_utc="):])
    end=_parse_time(lines[4][len("end_utc="):])
    if start is None or end is None:
        return None
    return (horizon,start,end,digest)


def _base(reason:str)->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":"LAB_ISSUE1884_ANCHOR_CENSUS_BLOCKED",
        "reason":reason,"campaign_id":CAMPAIGN_ID,
        "calendar_issue_url":CALENDAR_ISSUE,
        "expected_windows":24,
        "expected_pairs_per_window":28,
        "expected_pair_horizon_slots":EXPECTED_PAIR_HORIZON_SLOTS,
        "snapshot_comments_examined":0,
        "generic_calendar_or_audit_comments_ignored":0,
        "well_formed_hash_only_anchor_comments":0,
        "future_not_due_pair_slots":0,
        "due_not_issued_with_independent_witness_pair_slots":0,
        "due_hash_anchor_claim_only_pair_slots":0,
        "future_hash_anchor_claim_only_pair_slots":0,
        "anchor_claims_missing_server_timestamps":0,
        "anchor_claims_late_or_edited":0,
        "ambiguous_duplicate_window_anchor_claims":0,
        "first_d1_window_state":None,
        "first_w1_window_state":None,
        "window_states":[],
        "all_672_slots_accounted_for":False,
        "raw_roster_json_independently_preserved":False,
        "github_comment_metadata_independently_authenticated":False,
        "issuer_macro_data_first_seen_authenticated":False,
        "broker_ny17_first_last_m15_authenticated":False,
        "directional_forecasts_independently_witnessed":0,
        "calibrated_probability":None,
        "validated_directional_accuracy":None,
        "operational_bias":"AGUARDAR",
        "trade_authorized":False,
        "publishable":False,
        "live_alert_allowed":False,
        "worker_enabled":False,
        "scheduler_enabled":False,
        "http_requests":0,"files_written":0,"new_cost_brl":0,
        "research_only":True,
    }


def inspect_fx28_issue1884_prestart_anchor_snapshot_lab(
    *, issue_comment_snapshots:Any, inspected_at_utc:Any,
)->dict[str,Any]:
    """Conservative status of 672 slots from caller-provided comment snapshots.

    Even valid-looking earlier timestamps and a SHA are *claims*, never
    independently authenticated server evidence or preserved source bytes.
    """
    out=_base("INVALID_COMMENT_SNAPSHOT_OR_CLOCK")
    now=_utc(inspected_at_utc)
    if (now is None or type(issue_comment_snapshots) not in (list,tuple)
        or len(issue_comment_snapshots)>MAX_COMMENTS
        or len(OFFICIAL_PAIRS)!=28 or len(set(OFFICIAL_PAIRS))!=28):
        return out
    expected={(h,start):end for h in LABELS
              for start,end in _nominal_windows(h)}
    if len(expected)!=24 or EXPECTED_PAIR_HORIZON_SLOTS!=672:
        out["reason"]="FROZEN_CALENDAR_OR_PAIR_UNIVERSE_INVALID"
        return out

    windows:dict[tuple[str,datetime],list[str]]={}
    ids:set[int]=set()
    ignored=0
    for comment in issue_comment_snapshots:
        if type(comment) is not dict or type(comment.get("body")) is not str:
            out["reason"]="COMMENT_SHAPE_OR_BODY_INVALID"
            return out
        body=comment["body"]
        if len(body)>MAX_BODY:
            out["reason"]="COMMENT_BODY_OVERSIZED"
            return out
        parsed=_anchor(body)
        if parsed is None:
            if body.startswith(ANCHOR_HEADER):
                out["reason"]="MALFORMED_COMMITMENT_MARKER_NOT_ACCEPTABLE"
                return out
            ignored+=1
            continue
        h,start,end,_digest=parsed
        if (expected.get((h,start))!=end
            or type(comment.get("id")) is not int
            or comment["id"]<1 or comment["id"] in ids):
            out["reason"]="UNKNOWN_WINDOW_OR_DUPLICATE_OR_INVALID_COMMENT_ID"
            return out
        ident=comment["id"]
        ids.add(ident)
        expected_browser=(f"https://github.com/{REPO}/issues/{ISSUE_NUMBER}"
                          f"#issuecomment-{ident}")
        expected_api=(f"https://api.github.com/repos/{REPO}"
                      f"/issues/comments/{ident}")
        source_url=comment.get("url")
        if source_url not in (expected_browser,expected_api):
            out["reason"]="COMMENT_NOT_FROM_FROZEN_CAMPAIGN_ISSUE"
            return out

        created_raw=comment.get("created_at")
        updated_raw=comment.get("updated_at")
        status="HASH_ANCHOR_SERVER_TIMESTAMPS_UNAVAILABLE"
        if created_raw is None or updated_raw is None:
            out["anchor_claims_missing_server_timestamps"]+=1
        else:
            created=_parse_time(created_raw)
            updated=_parse_time(updated_raw)
            if created is None or updated is None or not created<=updated<=now:
                out["reason"]="COMMENT_TIMESTAMP_CLAIMS_INCOHERENT"
                return out
            if created>=start or updated>=start:
                status="HASH_ANCHOR_LATE_OR_EDITED"
                out["anchor_claims_late_or_edited"]+=1
            else:
                status="HASH_ANCHOR_TIME_CLAIM_PRESTART_UNATTESTED"
        windows.setdefault((h,start),[]).append(status)
    out["snapshot_comments_examined"]=len(issue_comment_snapshots)
    out["generic_calendar_or_audit_comments_ignored"]=ignored
    out["well_formed_hash_only_anchor_comments"]=sum(
        len(v) for v in windows.values())
    out["ambiguous_duplicate_window_anchor_claims"]=sum(
        len(v)>1 for v in windows.values())

    future=due=due_anchor=future_anchor=0
    states=[]
    for h in LABELS:
        for start,end in _nominal_windows(h):
            claims=windows.get((h,start),[])
            is_due=now>=start
            if is_due:
                due+=28
                due_anchor+=28*bool(claims)
            else:
                future+=28
                future_anchor+=28*bool(claims)
            if len(claims)>1:
                state="AMBIGUOUS_ANCHORS_UNVERIFIED"
            elif claims:
                state=("DUE_ANCHOR_CLAIM_ONLY_NO_WITNESS"
                       if is_due else "PRESTART_ANCHOR_CLAIM_ONLY_UNVERIFIED")
            else:
                state=("DUE_NOT_ISSUED_WITH_INDEPENDENT_WITNESS"
                       if is_due else "FUTURE_WINDOW_NOT_DUE")
            states.append({
                "horizon":h,
                "window_start_utc":start.isoformat().replace("+00:00","Z"),
                "window_end_utc":end.isoformat().replace("+00:00","Z"),
                "pair_slots":28,
                "status":state,
                "hash_anchor_comment_claim_count":len(claims),
                "pre_event_forecast_independently_witnessed":False,
            })

    if future+due!=EXPECTED_PAIR_HORIZON_SLOTS:
        out["reason"]="INTERNAL_672_SLOT_CENSUS_MISMATCH"
        return out
    out.update({
        "state":"LAB_ISSUE1884_672_SLOT_ANCHOR_CENSUS_NO_GO",
        "reason":"HASH_ONLY_COMMENTS_NEVER_INDEPENDENT_PRE_EVENT_FORECAST_PROOF",
        "future_not_due_pair_slots":future,
        "due_not_issued_with_independent_witness_pair_slots":due,
        "due_hash_anchor_claim_only_pair_slots":due_anchor,
        "future_hash_anchor_claim_only_pair_slots":future_anchor,
        "first_d1_window_state":states[0]["status"],
        "first_w1_window_state":states[20]["status"],
        "window_states":states,
        "all_672_slots_accounted_for":True,
    })
    return out


__all__=("SCHEMA","inspect_fx28_issue1884_prestart_anchor_snapshot_lab")
