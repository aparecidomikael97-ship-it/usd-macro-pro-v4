"""LAB-only ex-ante FX forecast and subsequent outcome chronology audit.

All clocks and hashes are caller supplied: structural acceptance is not
independent point-in-time attestation or historical predictive accuracy.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any
from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_FX_PREMOVE_AUDIT_LAB_V1"
FORECAST = "ATLASQUANT_FX_D1W1_FORECAST_V1"
OUTCOME = "ATLASQUANT_FX_D1W1_OUTCOME_V1"
MAX_BYTES = 32768
FIELDS_FORECAST = frozenset(("schema","pair","horizon","model_version",
    "direction","evidence_sha256","data_cutoff_utc","created_at_utc",
    "target_start_utc","target_end_utc"))
FIELDS_OUTCOME = frozenset(("schema","pair","target_start_utc",
    "target_end_utc","captured_at_utc","source_kind","source_sha256",
    "first_price","last_price"))
HORIZONS = {"D1":timedelta(days=1), "W1":timedelta(days=7)}
SOURCES = frozenset(("ECB_REFERENCE_INDICATIVE","BROKER_M15_UNVERIFIED"))
SHA = re.compile(r"[0-9a-f]{64}\Z")
TAG = re.compile(r"LAB_[A-Z0-9_.-]{3,48}\Z")
PRICE = re.compile(r"(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,10})?\Z")
UTC_TEXT = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")


def _result(reason: str) -> dict[str,Any]:
    return {
        "schema":SCHEMA,"state":"LAB_BLOCKED","reason":reason,
        "pair":None,"horizon":None,"direction":None,"forecast_sha256":None,
        "outcome_sha256":None,"observed_direction":None,
        "arithmetic_direction_match_unverified":None,
        "all_times_caller_claims":True,"forecast_precommit_independently_verified":False,
        "pre_decision_data_availability_verified":False,
        "frozen_model_pre_event_verified":False,
        "outcome_original_source_authenticated":False,
        "broker_m15_execution_verified":False,
        "historical_point_in_time_eligible":False,
        "validated_prediction_count":0,"validated_accuracy":None,
        "fx_bias":None,"operational_bias":"AGUARDAR",
        "trade_authorized":False,"can_feed_live_radar":False,
        "publishable":False,"worker_enabled":False,"scheduler_enabled":False,
        "external_http_requests":0,"new_cost_brl":0,
    }


def _pairs(pairs: list[tuple[str,Any]]) -> dict[str,Any]:
    d={}
    for k,v in pairs:
        if k in d:
            raise ValueError("duplicate")
        d[k]=v
    return d


def _obj(raw: Any) -> dict[str,Any] | None:
    if not isinstance(raw,bytes) or not 30<=len(raw)<=MAX_BYTES:
        return None
    try:
        x=json.loads(raw.decode("utf8","strict"),object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        return x if isinstance(x,dict) else None
    except (TypeError,ValueError,UnicodeDecodeError,RecursionError):
        return None


def _utc(s: Any) -> datetime | None:
    if not isinstance(s,str) or UTC_TEXT.fullmatch(s) is None:
        return None
    try:
        return datetime.fromisoformat(s[:-1]+"+00:00")
    except ValueError:
        return None


def _now(x: Any) -> datetime | None:
    if not isinstance(x,datetime) or x.tzinfo is None or x.utcoffset() is None:
        return None
    return x.astimezone(timezone.utc)


def _price(x: Any) -> Decimal | None:
    if not isinstance(x,str) or PRICE.fullmatch(x) is None:
        return None
    try:
        v=Decimal(x)
        return v if v.is_finite() and Decimal("0.0001")<=v<=999 else None
    except InvalidOperation:
        return None


def audit_fx_premove_lab(forecast_raw: Any,*,as_of_utc: Any,
                         outcome_raw: Any=None) -> dict[str,Any]:
    """Chronology and arithmetic only. NEVER compute proven hit rates."""
    r=_result("FORECAST_INVALID")
    f=_obj(forecast_raw)
    now=_now(as_of_utc)
    if now is None or f is None or set(f)!=FIELDS_FORECAST:
        return r
    if (f["schema"]!=FORECAST or not isinstance(f["pair"],str)
            or f["pair"] not in OFFICIAL_PAIRS
            or not isinstance(f["horizon"],str)
            or f["horizon"] not in HORIZONS
            or f["direction"] not in ("ALTA","BAIXA","NEUTRO")
            or not isinstance(f["model_version"],str)
            or TAG.fullmatch(f["model_version"]) is None
            or not isinstance(f["evidence_sha256"],str)
            or SHA.fullmatch(f["evidence_sha256"]) is None):
        return r
    data,created,start,end=(_utc(f[k]) for k in (
        "data_cutoff_utc","created_at_utc","target_start_utc","target_end_utc"))
    if (None in (data,created,start,end) or not data<=created<start<end
            or created>now or end-start!=HORIZONS[f["horizon"]]
            or start-created>timedelta(days=30)):
        r["reason"]="FORECAST_TIMELINE_OR_HORIZON_INVALID"
        return r
    r.update(state="LAB_FORECAST_STRUCTURALLY_ACCEPTED_UNATTESTED",
        reason="CREATION_AND_EVIDENCE_TIMES_SELF_ASSERTED",
        pair=f["pair"],horizon=f["horizon"],direction=f["direction"],
        forecast_sha256=sha256(forecast_raw).hexdigest())
    if outcome_raw is None:
        return r
    o=_obj(outcome_raw)
    if (o is None or set(o)!=FIELDS_OUTCOME or o["schema"]!=OUTCOME
            or o["pair"]!=f["pair"] or o["target_start_utc"]!=f["target_start_utc"]
            or o["target_end_utc"]!=f["target_end_utc"]
            or not isinstance(o["source_kind"],str)
            or o["source_kind"] not in SOURCES
            or not isinstance(o["source_sha256"],str)
            or SHA.fullmatch(o["source_sha256"]) is None):
        r.update(state="LAB_BLOCKED",reason="OUTCOME_IDENTITY_OR_SCHEMA_INVALID")
        return r
    capture=_utc(o["captured_at_utc"])
    first,last=_price(o["first_price"]),_price(o["last_price"])
    if capture is None or capture<end or capture>now or first is None or last is None:
        r.update(state="LAB_BLOCKED",reason="OUTCOME_BEFORE_CLOSE_OR_BAD_PRICE")
        return r
    observed="ALTA" if last>first else "BAIXA" if last<first else "NEUTRO"
    r.update(state="LAB_RETROSPECTIVE_DIRECTION_MATCH_UNATTESTED",
        reason="CALLER_CLAIMED_TIMESTAMPS_DO_NOT_PROVE_FORECAST_PRECOMMIT",
        outcome_sha256=sha256(outcome_raw).hexdigest(),
        observed_direction=observed,
        arithmetic_direction_match_unverified=(
            f["direction"]==observed if f["direction"]!="NEUTRO" else None))
    return r


__all__=["SCHEMA","FORECAST","OUTCOME","audit_fx_premove_lab"]
