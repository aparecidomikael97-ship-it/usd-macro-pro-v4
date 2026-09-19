"""AtlasQuant 28FX quota shadow telemetry.

Collects read-only evidence about current Twelve Data consumption versus the
planned adaptive 28-pair architecture. It never changes cadence, PAIR_ORDER,
API quotas or live execution behavior.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any, Mapping, Sequence
from datetime import datetime

from atlasquant_adaptive_coverage import adaptive_coverage_plan


SCHEMA_VERSION="atlasquant.quota-shadow.v1"
DEFAULT_MIN_MARKET_RUNS=20


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out=float(value)
        return out if math.isfinite(out) else float(default)
    except Exception:
        return float(default)


def _sample_id(payload: Mapping[str,Any]) -> str:
    raw=json.dumps(dict(payload),sort_keys=True,ensure_ascii=False,separators=(",",":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def build_quota_shadow_sample(
    status: Mapping[str,Any] | None,
    *,
    plan: Mapping[str,Any] | None = None,
) -> dict[str,Any]:
    s=dict(status or {})
    p=dict(plan or adaptive_coverage_plan())
    budget=dict(s.get("twelve_budget",{}) or {})
    base={
        "schema_version":SCHEMA_VERSION,
        "timestamp":str(s.get("last_run","")),
        "market_open":bool(s.get("forex_market_open",False)),
        "actual_http_calls":int(_num(s.get("twelve_calls_this_run",0))),
        "requested_internal_calls":int(_num(s.get("twelve_calls_requested_internal",0))),
        "provider_blocked":bool(s.get("twelve_daily_blocked",False)),
        "block_type":str(s.get("twelve_block_type","") or ""),
        "app_headless_ok":bool(s.get("app_headless_ok",False)),
        "scanner_fresh":int(_num(s.get("scanner_fresh",0))),
        "market_map_fresh":int(_num(s.get("market_map_fresh",0))),
        "budget_used":_num(budget.get("used",budget.get("count",0))),
        "budget_remaining":(
            None if budget.get("remaining") is None
            else _num(budget.get("remaining"))
        ),
        "adaptive_estimated_daily_calls":int(_num(p.get("estimated_daily_calls",0))),
        "adaptive_usable_cap":int(_num(p.get("usable_cap",0))),
        "adaptive_within_usable_cap":bool(p.get("within_usable_cap",False)),
        "adaptive_active_pairs":int(_num(p.get("active_pairs",0))),
        "adaptive_background_pairs":int(_num(p.get("background_pairs",0))),
    }
    base["sample_id"]=_sample_id(base)
    return base


def append_quota_shadow_sample(
    samples: Sequence[Mapping[str,Any]] | None,
    sample: Mapping[str,Any],
    *,
    max_samples: int = 500,
) -> tuple[list[dict[str,Any]],bool]:
    rows=[dict(x) for x in (samples or [])]
    sid=str(sample.get("sample_id","") or "")
    if sid and any(str(x.get("sample_id","") or "")==sid for x in rows):
        return rows,False
    rows.append(dict(sample))
    limit=max(1,int(max_samples))
    if len(rows)>limit:
        rows=rows[-limit:]
    return rows,True


def summarize_quota_shadow(
    samples: Sequence[Mapping[str,Any]] | None,
    *,
    min_market_runs: int = DEFAULT_MIN_MARKET_RUNS,
) -> dict[str,Any]:
    rows=[dict(x) for x in (samples or []) if isinstance(x, Mapping)]
    try:
        minimum=int(min_market_runs)
    except Exception:
        minimum=DEFAULT_MIN_MARKET_RUNS
    if isinstance(min_market_runs,bool) or minimum < 1:
        minimum=DEFAULT_MIN_MARKET_RUNS
    valid_rows=[]
    invalid_timestamp_rows=0
    for row in rows:
        timestamp=str(row.get("timestamp","") or "").strip()
        try:
            parsed=datetime.fromisoformat(timestamp.replace("Z","+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("timezone required")
            valid_rows.append(row)
        except Exception:
            invalid_timestamp_rows+=1
    market=[x for x in valid_rows if bool(x.get("market_open",False))]
    blocked=[x for x in market if bool(x.get("provider_blocked",False))]
    unhealthy=[x for x in market if not bool(x.get("app_headless_ok",False))]
    plan_over=[x for x in valid_rows if not bool(x.get("adaptive_within_usable_cap",False))]
    calls=[_num(x.get("actual_http_calls",0)) for x in market]

    enough=len(market)>=minimum
    no_quota_blocks=len(blocked)==0
    plan_fits=len(plan_over)==0 and bool(valid_rows)
    eligible=bool(enough and no_quota_blocks and not unhealthy and plan_fits)

    return {
        "samples":len(valid_rows),
        "invalid_timestamp_rows":invalid_timestamp_rows,
        "market_open_runs":len(market),
        "min_market_runs":minimum,
        "minimum_met":enough,
        "provider_blocked_runs":len(blocked),
        "provider_block_rate_pct":(
            None if not market else round(len(blocked)/len(market)*100.0,2)
        ),
        "headless_failed_runs":len(unhealthy),
        "avg_actual_http_calls_per_market_run":(
            None if not calls else round(sum(calls)/len(calls),2)
        ),
        "max_actual_http_calls_per_market_run":(
            None if not calls else int(max(calls))
        ),
        "adaptive_plan_fit_all_samples":plan_fits,
        "eligible_for_manual_review":eligible,
        "quota_shadow_validated":eligible,
        "automatic_expansion_allowed":False,
        "manual_review_required":True,
    }
