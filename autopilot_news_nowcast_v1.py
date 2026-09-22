"""Automatic AtlasQuant live economic-nowcast capture.

Runs inside the existing Autopilot schedule. It uses at most one EODHD Economic
Events request when the provider cache is stale, then freezes point-in-time
pre-release snapshots in the runtime data branch.

This module never places orders and its failure never changes trading logic.
"""
from __future__ import annotations

from datetime import timedelta
import json
import os
import re
from typing import Any

import pandas as pd
import requests

import autopilot_v107 as base
from atlasquant_live_nowcast import (
    normalize_live_ledger,
    summarize_live_nowcasts,
    sync_live_nowcasts,
)

VERSION="ATLASQUANT_AUTOPILOT_NEWS_NOWCAST_V1"
LEDGER_PATH="dados/news_nowcast_predictions_v1.csv"
SUMMARY_PATH="dados/news_nowcast_summary_v1.json"
PROVIDER_STATE_PATH="dados/news_nowcast_provider_state_v1.json"

DEFAULT_FETCH_INTERVAL_MIN=360
DEFAULT_AUTH_RETRY_MIN=360
DEFAULT_RATE_LIMIT_RETRY_MIN=60
DEFAULT_PROVIDER_ERROR_RETRY_MIN=60
DEFAULT_LOOKBACK_DAYS=120
DEFAULT_HORIZON_DAYS=7



def _safe_diagnostic(value:Any,*secrets:str)->str:
    """Redact credentials from persisted/logged provider diagnostics."""
    text=str(value or "")
    for secret in secrets:
        secret=str(secret or "")
        if secret:
            text=text.replace(secret,"[REDACTED]")
    text=re.sub(
        r"([?&](?:api_token|apikey|api_key|access_token|token)=)[^&\s\"']+",
        r"\1[REDACTED]",
        text,
        flags=re.IGNORECASE,
    )
    text=re.sub(
        r"((?:api_token|apikey|api_key|access_token|token)\s*[=:]\s*)[A-Za-z0-9._-]{8,}",
        r"\1[REDACTED]",
        text,
        flags=re.IGNORECASE,
    )
    return text

def _age_minutes(value:Any,now:pd.Timestamp)->float|None:
    if value in (None,""):
        return None
    try:
        ts=pd.to_datetime(value,utc=True,errors="coerce")
        if pd.isna(ts):
            return None
        age=(now-ts).total_seconds()/60.0
        return None if age<0 else float(age)
    except Exception:
        return None


def provider_fetch_policy(
    state:dict[str,Any]|None,
    *,
    now:pd.Timestamp,
    interval_minutes:int=DEFAULT_FETCH_INTERVAL_MIN,
)->dict[str,Any]:
    """Return a fail-closed provider retry decision.

    A successful cache obeys the normal refresh interval. Authentication,
    rate-limit and provider failures use their own cooldowns so the Autopilot
    does not hammer an endpoint that already rejected the previous request.
    """
    state=dict(state or {})
    success_age=_age_minutes(state.get("last_success_at"),now)
    normal_interval=max(60,int(interval_minutes))
    if success_age is not None and success_age<normal_interval:
        return {
            "fetch":False,
            "runtime_state":"THROTTLED",
            "reason":"SUCCESS_CACHE_FRESH",
            "retry_after_min":max(0,int(normal_interval-success_age)),
        }

    last_status=dict(state.get("last_provider_status") or {})
    reason=str(last_status.get("reason") or "").upper().strip()
    # Backward-compatible normalization: older runtimes stored every HTTP
    # failure as PROVIDER_ERROR. Use the persisted status code to recover the
    # precise class without issuing a new provider request.
    try:
        persisted_http=int(last_status.get("http_status")) if last_status.get("http_status") is not None else None
    except Exception:
        persisted_http=None
    if reason in {"","PROVIDER_ERROR"}:
        if persisted_http in {401,403}:
            reason="AUTH_ERROR"
        elif persisted_http==429:
            reason="RATE_LIMITED"
        elif persisted_http is not None and persisted_http>=500:
            reason="PROVIDER_UNAVAILABLE"
    attempt_age=_age_minutes(state.get("last_attempt_at"),now)
    retry_min={
        "AUTH_ERROR":DEFAULT_AUTH_RETRY_MIN,
        "RATE_LIMITED":DEFAULT_RATE_LIMIT_RETRY_MIN,
        "PROVIDER_UNAVAILABLE":DEFAULT_PROVIDER_ERROR_RETRY_MIN,
        "NETWORK_ERROR":DEFAULT_PROVIDER_ERROR_RETRY_MIN,
        "PROVIDER_ERROR":DEFAULT_PROVIDER_ERROR_RETRY_MIN,
        "PROVIDER_PAYLOAD_ERROR":DEFAULT_PROVIDER_ERROR_RETRY_MIN,
    }.get(reason)

    if retry_min is not None and attempt_age is not None and attempt_age<retry_min:
        runtime_state={
            "AUTH_ERROR":"AUTH_COOLDOWN",
            "RATE_LIMITED":"RATE_LIMIT_COOLDOWN",
        }.get(reason,"PROVIDER_COOLDOWN")
        return {
            "fetch":False,
            "runtime_state":runtime_state,
            "reason":reason,
            "retry_after_min":max(0,int(retry_min-attempt_age)),
        }

    return {
        "fetch":True,
        "runtime_state":"FETCH_ALLOWED",
        "reason":"DUE",
        "retry_after_min":0,
    }


def should_fetch_provider(
    state:dict[str,Any]|None,
    *,
    now:pd.Timestamp,
    interval_minutes:int=DEFAULT_FETCH_INTERVAL_MIN,
)->bool:
    return bool(provider_fetch_policy(
        state,
        now=now,
        interval_minutes=interval_minutes,
    ).get("fetch"))


def _provider_error_reason(http_status:Any,exc:Exception)->str:
    try:
        status=int(http_status) if http_status is not None else None
    except Exception:
        status=None
    if status in {401,403}:
        return "AUTH_ERROR"
    if status==429:
        return "RATE_LIMITED"
    if status is not None and status>=500:
        return "PROVIDER_UNAVAILABLE"
    if isinstance(exc,(requests.Timeout,requests.ConnectionError)):
        return "NETWORK_ERROR"
    if isinstance(exc,(ValueError,TypeError)):
        return "PROVIDER_PAYLOAD_ERROR"
    return "PROVIDER_ERROR"


def fetch_eodhd_events(
    token:str,
    *,
    start_date:str,
    end_date:str,
    timeout:int=25,
)->tuple[list[dict[str,Any]],dict[str,Any]]:
    """Fetch US events with bounded pagination.

    EODHD allows offset up to 1000. We request 1000 rows first and, only when
    necessary, one second page at offset 1000. If both pages are full we fail
    closed because the provider window may still be truncated.
    """
    token=str(token or "").strip()
    if not token:
        return [],{
            "ok":False,
            "reason":"NOT_CONFIGURED",
            "http_status":None,
            "rows":0,
            "requests":0,
            "error":"CHAVE_EODHD ausente.",
        }

    rows=[]
    statuses=[]
    request_count=0
    try:
        for offset in (0,1000):
            response=requests.get(
                "https://eodhd.com/api/economic-events",
                params={
                    "api_token":token,
                    "from":start_date,
                    "to":end_date,
                    "country":"US",
                    "limit":1000,
                    "offset":offset,
                    "fmt":"json",
                },
                timeout=timeout,
            )
            request_count+=1
            statuses.append(int(response.status_code))
            response.raise_for_status()
            payload=response.json()
            if isinstance(payload,dict):
                message=payload.get("error") or payload.get("message")
                if message:
                    raise ValueError(str(message))
                payload=payload.get("data",[])
            if not isinstance(payload,list):
                raise ValueError("Formato inesperado no Economic Events.")
            page=[dict(x) for x in payload if isinstance(x,dict)]
            rows.extend(page)
            if len(page)<1000:
                break

        if request_count==2 and len(rows)>=2000:
            return [],{
                "ok":False,
                "reason":"TRUNCATED_PROVIDER_DATA",
                "http_status":statuses[-1] if statuses else None,
                "rows":len(rows),
                "requests":request_count,
                "error":"Janela EODHD excedeu a paginação segura; Nowcast não usa dados potencialmente truncados.",
            }

        # Stable de-duplication without depending on provider ordering.
        unique=[]
        seen=set()
        for item in rows:
            key=(
                str(item.get("type") or ""),
                str(item.get("comparison") or ""),
                str(item.get("period") or ""),
                str(item.get("country") or ""),
                str(item.get("date") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique,{
            "ok":True,
            "reason":"LOADED",
            "http_status":statuses[-1] if statuses else None,
            "rows":len(unique),
            "requests":request_count,
            "paginated":request_count>1,
            "limit_reached":False,
            "error":"",
        }
    except Exception as exc:
        http_status=(
            statuses[-1]
            if statuses
            else getattr(locals().get("response",None),"status_code",None)
        )
        return [],{
            "ok":False,
            "reason":_provider_error_reason(http_status,exc),
            "http_status":http_status,
            "rows":0,
            "requests":request_count,
            "error":_safe_diagnostic(f"{type(exc).__name__}: {exc}",token),
        }


def _news_nowcast_cycle()->tuple[bool,dict[str,Any],list[str]]:
    errors=[]
    now=base.utcnow()
    now=now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")

    ledger,err=base.gh_get_csv(LEDGER_PATH)
    if err and "404" not in str(err):
        errors.append("Nowcast ledger: "+str(err))
    ledger=normalize_live_ledger(ledger)

    state,err=base.gh_get_json(PROVIDER_STATE_PATH,{})
    if err and "404" not in str(err):
        errors.append("Nowcast provider state: "+str(err))
    state=state if isinstance(state,dict) else {}

    token=os.getenv("CHAVE_EODHD","").strip()
    if not token:
        summary=summarize_live_nowcasts(ledger)
        summary.update({
            "version":VERSION,
            "runtime_state":"NOT_CONFIGURED",
            "provider":"EODHD Economic Events",
            "last_cycle_at":now.isoformat(),
            "safety":{
                "real_orders":False,
                "market_reaction_predicted":False,
                "automatic_weight_change":False,
                "lookahead_used":False,
            },
        })
        # Missing an optional provider is observable, not a CI/trading failure.
        base.gh_put_json(
            SUMMARY_PATH,summary,
            "AtlasQuant Nowcast: registra provider não configurado",
        )
        _update_status(summary,errors)
        return True,summary,errors

    fetch_policy=provider_fetch_policy(state,now=now)
    if not fetch_policy.get("fetch"):
        summary=summarize_live_nowcasts(ledger)
        summary.update({
            "version":VERSION,
            "runtime_state":fetch_policy.get("runtime_state","THROTTLED"),
            "provider":"EODHD Economic Events",
            "last_cycle_at":now.isoformat(),
            "provider_last_success_at":state.get("last_success_at"),
            "provider_fetch_interval_min":DEFAULT_FETCH_INTERVAL_MIN,
            "provider_retry_reason":fetch_policy.get("reason"),
            "provider_retry_after_min":fetch_policy.get("retry_after_min",0),
            "provider_status":{
                **dict(state.get("last_provider_status") or {}),
                "original_reason":dict(state.get("last_provider_status") or {}).get("reason"),
                "reason":fetch_policy.get("reason")
                or dict(state.get("last_provider_status") or {}).get("reason"),
            },
            "safety":{
                "real_orders":False,
                "trading_news_enabled":False,
                "market_reaction_predicted":False,
                "automatic_weight_change":False,
                "lookahead_used":False,
            },
        })
        _update_status(summary,errors)
        return True,summary,errors

    start=(now.date()-timedelta(days=DEFAULT_LOOKBACK_DAYS)).isoformat()
    end=(now.date()+timedelta(days=DEFAULT_HORIZON_DAYS+7)).isoformat()
    raw_events,provider=fetch_eodhd_events(
        token,start_date=start,end_date=end,
    )

    provider_state={
        **state,
        "version":VERSION,
        "last_attempt_at":now.isoformat(),
        "last_window":{"from":start,"to":end},
        "last_provider_status":provider,
    }

    if not provider.get("ok"):
        provider_state["last_error_at"]=now.isoformat()
        provider_state["last_error"]=provider.get("error","")
        base.gh_put_json(
            PROVIDER_STATE_PATH,provider_state,
            "AtlasQuant Nowcast: registra falha de provider sem afetar trading",
        )
        summary=summarize_live_nowcasts(ledger)
        summary.update({
            "version":VERSION,
            "runtime_state":str(provider.get("reason") or "PROVIDER_ERROR"),
            "provider_status":provider,
            "last_cycle_at":now.isoformat(),
            "provider_retry_after_min":{
                "AUTH_ERROR":DEFAULT_AUTH_RETRY_MIN,
                "RATE_LIMITED":DEFAULT_RATE_LIMIT_RETRY_MIN,
            }.get(str(provider.get("reason") or "").upper(),DEFAULT_PROVIDER_ERROR_RETRY_MIN),
            "safety":{
                "real_orders":False,
                "trading_news_enabled":False,
                "market_reaction_predicted":False,
                "automatic_weight_change":False,
                "lookahead_used":False,
            },
        })
        # Provider outage remains fail-closed and does not invent a forecast.
        _update_status(summary,errors+[str(provider.get("error",""))])
        return True,summary,errors

    try:
        updated,cycle=sync_live_nowcasts(
            raw_events,
            ledger,
            now=now.to_pydatetime(),
            horizon_days=DEFAULT_HORIZON_DAYS,
            min_history=40,
            min_analogs=20,
            bandwidth=0.25,
        )
    except Exception as exc:
        errors.append(_safe_diagnostic(f"Nowcast sync: {type(exc).__name__}: {exc}",token))
        summary=summarize_live_nowcasts(ledger)
        summary.update({
            "version":VERSION,
            "runtime_state":"SYNC_ERROR",
            "provider_status":provider,
            "last_cycle_at":now.isoformat(),
        })
        _update_status(summary,errors)
        return True,summary,errors

    ok_ledger,err_ledger=base.gh_put_csv(
        LEDGER_PATH,
        updated,
        "AtlasQuant Nowcast: congela snapshots pré-release",
    )
    if not ok_ledger:
        errors.append("Salvar Nowcast ledger: "+str(err_ledger))

    summary=summarize_live_nowcasts(updated)
    summary.update({
        "version":VERSION,
        "runtime_state":"CAPTURED",
        "provider_status":provider,
        "last_cycle_at":now.isoformat(),
        "last_cycle":cycle,
        "provider_fetch_interval_min":DEFAULT_FETCH_INTERVAL_MIN,
        "safety":{
            "real_orders":False,
            "broker_connection":False,
            "trading_news_enabled":False,
            "market_reaction_predicted":False,
            "automatic_weight_change":False,
            "lookahead_used":False,
            "same_day_naive_target_capture":False,
        },
    })

    ok_summary,err_summary=base.gh_put_json(
        SUMMARY_PATH,summary,
        "AtlasQuant Nowcast: atualiza resumo prospectivo",
    )
    if not ok_summary:
        errors.append("Salvar Nowcast resumo: "+str(err_summary))

    provider_state.update({
        "last_success_at":now.isoformat(),
        "last_error":"",
        "last_error_at":"",
        "last_rows":int(provider.get("rows",0) or 0),
        "limit_reached":bool(provider.get("limit_reached",False)),
    })
    ok_state,err_state=base.gh_put_json(
        PROVIDER_STATE_PATH,provider_state,
        "AtlasQuant Nowcast: atualiza cache do provider",
    )
    if not ok_state:
        errors.append("Salvar estado provider Nowcast: "+str(err_state))

    _update_status(summary,errors)
    # The nowcast is sidecar research. Return success even for optional
    # persistence diagnostics so the core scanner is never masked by this lab.
    return bool(ok_ledger and ok_summary and ok_state),summary,errors


def _update_status(summary:dict[str,Any],errors:list[str])->None:
    errors=[_safe_diagnostic(x) for x in list(errors or [])]
    status,_=base.gh_get_json(base.STATUS_PATH,{})
    status=status if isinstance(status,dict) else {}
    status["news_nowcast_v1"]={
        "enabled":True,
        "runtime_state":summary.get("runtime_state"),
        "snapshots":summary.get("snapshots",0),
        "events":summary.get("events",0),
        "closed_events":summary.get("closed_events",0),
        "with_signals":summary.get("with_signals",0),
        "with_empirical_distribution":summary.get("with_empirical_distribution",0),
        "by_indicator":summary.get("by_indicator",{}),
        "provider_status":summary.get("provider_status",{}),
        "provider_retry_reason":summary.get("provider_retry_reason"),
        "provider_retry_after_min":summary.get("provider_retry_after_min",0),
        "real_orders":False,
        "trading_news_enabled":False,
        "market_reaction_predicted":False,
        "automatic_weight_change":False,
        "lookahead_used":False,
        "errors":[str(x) for x in errors[:10] if str(x).strip()],
    }
    base.gh_put_json(
        base.STATUS_PATH,status,
        "AtlasQuant Autopilot: status com News Nowcast",
    )


def main()->int:
    ok,summary,errors=_news_nowcast_cycle()
    print(json.dumps({
        "news_nowcast_v1":summary,
        "news_nowcast_ok":ok,
        "news_nowcast_errors":errors,
    },ensure_ascii=False,indent=2,default=str))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
