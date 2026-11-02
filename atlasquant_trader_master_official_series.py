"""Read-only official macro series for AtlasQuant Painel Mestre (LAB).

BCB SGS: Selic target 432 (daily % a.a.), IPCA monthly 433 (% m/m),
IPCA 12 months 13522 (% 12m). FRED: CPIAUCSL transformed with pc1
(% y/y), UNRATE (%), DGS2 (% a.a.).

OBSERVATION DATE is NOT a release timestamp. Collection may be daily while
the series is monthly. This service never supplies consensus, trade bias or
economic-calendar actuals. It is opt-in; does not touch AION Core/Worker and
does not create persistent state, cron, orders or extra subscriptions.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from functools import lru_cache
from math import isfinite
import os
from typing import Any, Callable, Mapping

SCHEMA = "ATLASQUANT_MASTER_OFFICIAL_SERIES_V1"
FEATURE_FLAG = "ATLASQUANT_MASTER_OFFICIAL_DATA_ENABLED"
# (label, provider, code, frequency, unit, max observation age in days, API transformation)
SPECS = {
    "BR_SELIC_META": ("Meta Selic", "BCB-SGS", "432", "DIÁRIA", "% ao ano", 14, ""),
    "BR_IPCA_MENSAL": ("IPCA mensal", "BCB-SGS", "433", "MENSAL", "% no mês", 75, ""),
    "BR_IPCA_12M": ("IPCA 12 meses", "BCB-SGS", "13522", "MENSAL", "% em 12 meses", 75, ""),
    "US_CPI_YOY": ("CPI EUA · 12 meses", "FRED", "CPIAUCSL", "MENSAL", "% em 12 meses", 75, "pc1"),
    "US_UNEMPLOYMENT": ("Desemprego EUA", "FRED", "UNRATE", "MENSAL", "% da força de trabalho", 75, ""),
    "US_TREASURY_2Y": ("Treasury EUA 2 anos", "FRED", "DGS2", "DIÁRIA", "% ao ano", 12, ""),
}


def enabled(env: Mapping[str, str] | None = None) -> bool:
    values = env if env is not None else os.environ
    return str(values.get(FEATURE_FLAG) or "").strip().lower() in ("1", "true", "yes", "on")


def _number(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    text = str(raw).strip().replace(",", ".")
    if not text or text == "." or len(text) > 30:
        return None
    try:
        val = float(text)
    except (TypeError, ValueError, OverflowError):
        return None
    return val if isfinite(val) and -1000 <= val <= 100000 else None


def _parse_date(raw: Any, source: str) -> date | None:
    if not isinstance(raw, str):
        return None
    try:
        if source == "BCB-SGS":
            return datetime.strptime(raw, "%d/%m/%Y").date()
        return date.fromisoformat(raw)
    except (ValueError, TypeError, OverflowError):
        return None


def normalize_series(key: str, payload: Any, *, at: datetime | None = None,
                     collected: bool = True) -> dict[str, Any]:
    """Only accept observations from a known provider series and valid period."""
    if key not in SPECS:
        raise ValueError("unknown official series")
    name, source, series_id, frequency, unit, max_days, transform = SPECS[key]
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware instant required")
    today = now.astimezone(timezone.utc).date()
    base = {
        "id": key, "label": name, "source": source, "series": series_id,
        "frequency": frequency, "unit": unit, "observation_date": "",
        "fetched_at": now.astimezone(timezone.utc).isoformat() if collected else "",
        "value": None, "state": "AGUARDANDO", "reason": "",
        "transformation": transform or "lin",
        "provider_verified": False, "trade_authorized": False,
    }
    if not collected:
        return {**base, "reason": "Fonte não consultada."}
    if source == "BCB-SGS":
        items = payload if isinstance(payload, list) else []
    else:
        items = payload.get("observations") if isinstance(payload, Mapping) else []
        if not isinstance(items, list):
            items = []
    observations = []
    for item in items[:20]:
        if not isinstance(item, Mapping):
            continue
        stamp = _parse_date(item.get("data") if source == "BCB-SGS" else item.get("date"), source)
        val = _number(item.get("valor") if source == "BCB-SGS" else item.get("value"))
        if stamp is None or val is None or stamp > today:
            continue
        observations.append((stamp, val))
    if not observations:
        return {**base, "state": "SEM DADOS VÁLIDOS", "reason":
                "Resposta sem observação, data ou unidade compatível."}
    stamp, val = max(observations, key=lambda x: x[0])
    age = (today - stamp).days
    state = "VALIDADO" if age <= max_days else "PERÍODO ANTIGO"
    return {
        **base, "value": val if state == "VALIDADO" else None,
        "observation_date": stamp.isoformat(),
        "state": state, "provider_verified": state == "VALIDADO",
        "reason": (
            "Data do período estatístico, não horário de divulgação nem consenso."
            if state == "VALIDADO" else
            f"A última observação tem {age} dias, acima do limite de {max_days} dias."
        ),
    }


def _get_fred_key(st: Any) -> str:
    key = str(os.environ.get("CHAVE_FRED") or "").strip()
    if key:
        return key
    try:
        return str(st.secrets.get("CHAVE_FRED", "") or "").strip()
    except Exception:
        return ""


def _http_one(key: str, fred_key: str, *, request_get: Callable[..., Any]) -> Any:
    _, source, series_id, _, _, _, transform = SPECS[key]
    if source == "FRED":
        if not fred_key:
            return None
        params = {"series_id": series_id, "api_key": fred_key,
                  "file_type": "json", "sort_order": "desc", "limit": 8}
        if transform:
            params["units"] = transform
        url = "https://api.stlouisfed.org/fred/series/observations"
    else:
        params = {"formato": "json"}
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_id}/dados/ultimos/1"
    try:
        response = request_get(url, params=params, timeout=7)
        if int(response.status_code) != 200:
            return None
        obj = response.json()
        if isinstance(obj, (dict, list)):
            return obj
    except Exception:
        pass
    return None


@lru_cache(maxsize=5)
def _one_day(day_utc: str, fred_key: str) -> dict[str, Any]:
    """At most 6 requests per UTC date per process, with bounded timeouts."""
    import requests
    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks = {
            pool.submit(_http_one, key, fred_key, request_get=requests.get): key
            for key in SPECS
            if SPECS[key][1] != "FRED" or fred_key
        }
        for future in as_completed(tasks):
            key = tasks[future]
            try:
                results[key] = future.result()
            except Exception:
                results[key] = None
    return results


def read_official_series(st: Any, *, at: datetime | None = None) -> dict[str, Any]:
    """Opt-in lazy fetch after Master access gate; does not set any billing."""
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware instant required")
    date_utc = now.astimezone(timezone.utc).date().isoformat()
    if not enabled():
        return {
            "schema": SCHEMA, "state": "DESATIVADO", "read_at": now.isoformat(),
            "rows": [normalize_series(k, None, at=now, collected=False) for k in SPECS],
            "reason": "Coleta oficial não habilitada; nenhuma requisição foi efetuada.",
            "requests_by_this_view": 0, "trade_authorized": False,
        }
    fred_key = _get_fred_key(st)
    raw = _one_day(date_utc, fred_key)
    rows = [normalize_series(key, raw.get(key), at=now, collected=key in raw)
            for key in SPECS]
    return {
        "schema": SCHEMA,
        "state": "PARCIAL" if any(r["state"] != "VALIDADO" for r in rows) else "VALIDADO",
        "read_at": now.isoformat(), "rows": rows,
        "reason": "Períodos de referência e frequência por série. Não são divulgações novas de hoje.",
        "requests_by_this_view": 0, # Cache may have been filled by an earlier view.
        "trade_authorized": False,
    }


__all__ = ["SCHEMA", "SPECS", "FEATURE_FLAG", "enabled",
           "normalize_series", "read_official_series", "_http_one"]
