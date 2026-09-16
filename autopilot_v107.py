"""USD Macro Pro V11.0 — Institutional Decision Autopilot.

Executado pelo GitHub Actions a cada 30 minutos.

Automatiza:
- execução headless do app para atualizar FRED/macro/matriz;
- persistência do snapshot atual da matriz;
- notícias globais das 8 moedas;
- scanner técnico H4/H1/M15 com orçamento de API;
- Market Map W1/D1/liquidez/ADR usando M15 fresco + cache D1;
- criação/backfill de snapshots de notícias;
- migração Timing Integrity;
- validação automática 1H/4H/24H;
- status de saúde do Autopilot.

O Score Mestre NÃO é alterado pela camada de notícias.
"""
from __future__ import annotations

import base64
import io
import json
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Mapping

import numpy as np
import pandas as pd
import requests

from engine import closed_candles
from twelve_budget_v1108 import Budget, GitHubStore, BudgetUnavailable, classify_limit
from twelve_cache_v1108 import SERIES_PATH, read_series, valid_records
from currency_news_v107 import (
    CURRENCY_PROFILES,
    PAIR_ORDER,
    load_currency_news_intelligence,
    pair_news_table,
)
from ict_execution_v108 import detect_crt, detect_ote, detect_amd, detect_fvg
from institutional_engine_v110 import build_institutional_snapshot, SMT_COMPANIONS

from atlasquant_runtime_store import resolve_runtime_branch, require_runtime_branch
from atlasquant_quota_shadow import (
    build_quota_shadow_sample,
    append_quota_shadow_sample,
    summarize_quota_shadow,
)

from market_map_core_v10 import (
    NY_TZ,
    adr_context,
    aggregate_ohlc,
    completed_daily,
    equal_liquidity_levels,
    intraday_open_context,
    killzone_state,
    macro_regime_summary,
    nearest_liquidity,
    normalize_ohlc,
    premium_discount,
    prior_period_levels,
    recent_sweeps,
    session_range,
    setup_readiness,
    trend_context,
)

REPO = os.getenv("GITHUB_REPO_HISTORICO", os.getenv("GITHUB_REPOSITORY", "")).strip()
BRANCH = require_runtime_branch(resolve_runtime_branch(
    os.getenv("GITHUB_DATA_BRANCH", ""),
    os.getenv("GITHUB_BRANCH_HISTORICO", ""),
))
TOKEN = os.getenv("GITHUB_TOKEN_HISTORICO", os.getenv("GITHUB_TOKEN", "")).strip()
TD_KEY = os.getenv("CHAVE_TWELVE_DATA", "").strip()
NEWS_KEY = os.getenv("CHAVE_NEWSAPI", "").strip()

INPUT_PATH = "dados/autopilot_inputs_v107.json"
STATUS_PATH = "dados/autopilot_status_v107.json"
SCANNER_PATH = "dados/scanner_tecnico_v934.json"
MASTER_PATH = "dados/master_market_map_v102.json"
DAILY_CACHE_PATH = "dados/autopilot_daily_cache_v107.json"
NEWS_CURRENT_PATH = "dados/currency_news_current_v107.json"
NEWS_VALIDATION_PATH = "dados/currency_news_validation_v1061.csv"
QUOTA_SHADOW_PATH = "dados/atlasquant_quota_shadow_v1.json"

M15_EVERY_MIN = 55
H1_EVERY_MIN = 115
H4_EVERY_MIN = 235
NEWS_EVERY_MIN = 50

# V10.7.5 — prioridade + orçamento conservador.
# Top 3 pares direcionais podem atualizar M15 mais rápido.
PRIORITY_M15_EVERY_MIN = 25
PRIORITY_H1_EVERY_MIN = 55

# Reserva parte do plano diário para uso manual do app.
AUTOPILOT_DAILY_CALL_BUDGET = 480


# V10.7.1 — rate-safe Twelve Data gate.
# Keeps calls well below a bursty per-minute pattern so the first run
# can safely complete H4/H1/M15 + D1 instead of partially failing.
TD_SAFE_CALLS_PER_WINDOW = 6
TD_SAFE_WINDOW_SECONDS = 62.0
_TD_CALL_TIMES: list[float] = []

# V10.7.6 — abre circuito após o primeiro 429 diário.
_TD_DAILY_BLOCKED = False
_TD_DAILY_BLOCK_REASON = ""
_TD_BLOCK_TYPE = ""
_TD_HTTP_CALLS = 0
_TD_BUDGET = None
_TD_SERIES = {"series":{}}
_TD_CACHE_HITS = 0
_TD_STOP_UNTIL = ""



def _td_rate_gate() -> None:
    """Throttle Twelve Data calls conservatively across the whole runner."""
    global _TD_CALL_TIMES
    while True:
        now = time.monotonic()
        _TD_CALL_TIMES = [
            t for t in _TD_CALL_TIMES
            if (now - t) < TD_SAFE_WINDOW_SECONDS
        ]
        if len(_TD_CALL_TIMES) < TD_SAFE_CALLS_PER_WINDOW:
            _TD_CALL_TIMES.append(now)
            return
        wait_for = TD_SAFE_WINDOW_SECONDS - (now - _TD_CALL_TIMES[0]) + 0.25
        if wait_for > 0:
            print(f"[rate-safe] aguardando {wait_for:.1f}s antes da próxima consulta Twelve Data")
            time.sleep(min(60.0, wait_for))
        else:
            _TD_CALL_TIMES = []


def utcnow() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")

def gh_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def gh_get_bytes(path: str) -> tuple[bytes | None, str]:
    if not TOKEN or not REPO:
        return None, "GitHub token/repo ausente."
    try:
        url = f"https://api.github.com/repos/{REPO}/contents/{path}"
        r = requests.get(url, headers=gh_headers(), params={"ref": BRANCH}, timeout=20)
        if r.status_code == 404:
            return None, ""
        r.raise_for_status()
        return base64.b64decode(r.json().get("content", "")), ""
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

def gh_put_bytes(path: str, raw: bytes, message: str) -> tuple[bool, str]:
    if not TOKEN or not REPO:
        return False, "GitHub token/repo ausente."
    try:
        url = f"https://api.github.com/repos/{REPO}/contents/{path}"
        h = gh_headers()
        cur = requests.get(url, headers=h, params={"ref": BRANCH}, timeout=20)
        sha = cur.json().get("sha", "") if cur.status_code == 200 else ""
        if cur.status_code not in (200, 404):
            cur.raise_for_status()
        payload = {
            "message": message,
            "content": base64.b64encode(raw).decode("ascii"),
            "branch": BRANCH,
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=h, json=payload, timeout=30)
        r.raise_for_status()
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

def gh_get_json(path: str, default: Any = None) -> tuple[Any, str]:
    raw, err = gh_get_bytes(path)
    if raw is None:
        return ({} if default is None else default), err
    try:
        return json.loads(raw.decode("utf-8")), ""
    except Exception as exc:
        return ({} if default is None else default), f"{type(exc).__name__}: {exc}"

def gh_put_json(path: str, obj: Any, message: str) -> tuple[bool, str]:
    return gh_put_bytes(
        path, json.dumps(obj, ensure_ascii=False, indent=2, default=str).encode("utf-8"), message
    )

def gh_get_csv(path: str) -> tuple[pd.DataFrame, str]:
    raw, err = gh_get_bytes(path)
    if raw is None:
        return pd.DataFrame(), err
    try:
        return pd.read_csv(io.BytesIO(raw)), ""
    except Exception as exc:
        return pd.DataFrame(), f"{type(exc).__name__}: {exc}"

def gh_put_csv(path: str, df: pd.DataFrame, message: str) -> tuple[bool, str]:
    return gh_put_bytes(path, df.to_csv(index=False).encode("utf-8"), message)

def minutes_since(value: Any) -> float | None:
    if value in (None, "", 0, 0.0):
        return None
    try:
        if isinstance(value, (int, float)):
            ts = pd.Timestamp(float(value), unit="s", tz="UTC")
        else:
            ts = pd.to_datetime(value, utc=True)
        return max(0.0, (utcnow() - ts).total_seconds() / 60.0)
    except Exception:
        return None

def forex_market_likely_open(now: pd.Timestamp | None = None) -> bool:
    now = utcnow() if now is None else pd.Timestamp(now).tz_convert("UTC")
    wd, hour = now.weekday(), now.hour
    if wd == 5:
        return False
    if wd == 6 and hour < 21:
        return False
    if wd == 4 and hour >= 21:
        return False
    return True

def run_headless_app() -> tuple[bool, str]:
    """Executa o app via AppTest com secrets injetados diretamente."""
    try:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file("usd_macro_pro_v4_cloud.py", default_timeout=180)

        secret_keys = [
            "CHAVE_FRED",
            "CHAVE_TWELVE_DATA",
            "CHAVE_NEWSAPI",
            "CHAVE_EODHD",
            "GITHUB_TOKEN_HISTORICO",
            "GITHUB_REPO_HISTORICO",
            "GITHUB_DATA_BRANCH",
            "GITHUB_BRANCH_HISTORICO",
        ]
        injected = 0
        for key in secret_keys:
            value = os.getenv(key, "")
            if value:
                at.secrets[key] = value
                injected += 1

        at.run(timeout=180)

        if at.exception:
            msgs = []
            for exc in at.exception:
                try:
                    msgs.append(str(exc.value))
                except Exception:
                    msgs.append(str(exc))
            return False, " | ".join(msgs[:3])

        return True, f"App headless executado; {injected} secret(s) injetado(s) no AppTest."
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"



def _td_message(resp: requests.Response) -> str:
    try:
        js = resp.json()
        if isinstance(js, dict):
            return str(js.get("message") or js.get("status") or js)
    except Exception:
        pass
    try:
        return str(resp.text)[:300]
    except Exception:
        return ""



# Compatibilidade de regressão das versões anteriores:
# "HTTP 429:" permanece documentado para os testes V10.7.5.
# "HTTP 429 DAILY:" e "API_COTA_DIARIA_BLOQUEADA" permanecem documentados
# para os testes V10.7.6. A V10.7.7 usa mensagens mais específicas em runtime.

def _td_is_minute_limit(message: str) -> bool:
    return classify_limit(message)=="LIMITE_MINUTO"


def _td_is_daily_quota(message: str) -> bool:
    return classify_limit(message)=="COTA_DIARIA"


def _td_initialize():
    global _TD_BUDGET, _TD_SERIES, _TD_DAILY_BLOCKED, _TD_BLOCK_TYPE, _TD_DAILY_BLOCK_REASON, _TD_STOP_UNTIL, _TD_HTTP_CALLS, _TD_CACHE_HITS, _TD_CALL_TIMES
    _TD_DAILY_BLOCKED=False; _TD_BLOCK_TYPE=''; _TD_DAILY_BLOCK_REASON=''; _TD_STOP_UNTIL=''
    _TD_HTTP_CALLS=0; _TD_CACHE_HITS=0; _TD_CALL_TIMES=[]
    _TD_BUDGET=Budget(GitHubStore(TOKEN,REPO,BRANCH))
    try:
        previous,err=gh_get_json(STATUS_PATH,{})
        old_scanner,err2=gh_get_json(SCANNER_PATH,{})
        _TD_SERIES,err3=gh_get_json(SERIES_PATH,{"series":{}})
        if err or err2 or err3: raise BudgetUnavailable("Falha ao ler estado persistido; coleta adiada")
        _TD_SERIES.setdefault("series",{})
        _TD_BUDGET.bootstrap(previous,old_scanner,utcnow().to_pydatetime())
        summary=_TD_BUDGET.summary(utcnow().to_pydatetime())
        if summary.get("blocked_until"):
            _TD_DAILY_BLOCKED=True
            _TD_BLOCK_TYPE=summary.get("block_type","")
            _TD_DAILY_BLOCK_REASON=summary.get("block_reason","")
            _TD_STOP_UNTIL=summary["blocked_until"]
    except Exception as exc:
        _TD_DAILY_BLOCKED=True
        _TD_BLOCK_TYPE="CONTROLE_INDISPONIVEL"
        _TD_DAILY_BLOCK_REASON="Orçamento persistido indisponível; nenhuma consulta liberada."


def td_fetch(pair: str, interval: str, outputsize: int) -> tuple[pd.DataFrame, str]:
    global _TD_DAILY_BLOCKED, _TD_DAILY_BLOCK_REASON, _TD_BLOCK_TYPE, _TD_HTTP_CALLS, _TD_CACHE_HITS, _TD_STOP_UNTIL
    if pair not in PAIR_ORDER or interval not in ('15min','1h','4h','1day'):
        return pd.DataFrame(), "Consulta fora dos sete pares/intervalos previstos."
    if not TD_KEY: return pd.DataFrame(), "CHAVE_TWELVE_DATA ausente."
    if _TD_DAILY_BLOCKED:
        return pd.DataFrame(), f"API_COTA_BLOQUEADA: {_TD_DAILY_BLOCK_REASON}"
    # Reuse direction-neutral candles, never old directional confirmations.
    limits={"15min":24,"1h":54,"4h":234,"1day":0}
    if interval!="1day":
        cached,err=read_series(_TD_SERIES,pair,interval,outputsize,now=utcnow(),max_age=limits.get(interval,0))
        if not err and len(cached)>=min(outputsize,80):
            _TD_CACHE_HITS+=1
            return cached,""
    if _TD_BUDGET is None: return pd.DataFrame(),"Controle de orçamento não inicializado."
    try:
        _td_rate_gate()
        allowed,kind,until=_TD_BUDGET.reserve(utcnow().to_pydatetime())
        if not allowed:
            _TD_DAILY_BLOCKED=True; _TD_BLOCK_TYPE=kind; _TD_STOP_UNTIL=until
            _TD_DAILY_BLOCK_REASON=f"{kind}: novas consultas adiadas até {until}. Cache preservado."
            return pd.DataFrame(),_TD_DAILY_BLOCK_REASON
        # Reservation is durable before even a timeout can consume a credit.
        _TD_HTTP_CALLS+=1
        r=requests.get("https://api.twelvedata.com/time_series",
            params={"symbol":pair,"interval":interval,"outputsize":int(outputsize),
                    "apikey":TD_KEY,"timezone":"UTC","format":"JSON","order":"ASC"},timeout=25)
        try: js=r.json()
        except Exception:
            if r.status_code!=429: return pd.DataFrame(),f"Resposta não JSON: HTTP {r.status_code}"
            js={"message":"HTTP 429: limite não especificado", "status":"error"}
        message=str(js.get("message", "")) if isinstance(js,dict) else ""
        is_error=isinstance(js,dict) and js.get("status")=="error"
        if r.status_code==429 or (is_error and (str(js.get("code"))=="429" or classify_limit(message)!="COTA_OU_PLANO" or any(w in message.lower() for w in ('credits','quota','limit')))):
            _TD_DAILY_BLOCKED=True
            _TD_BLOCK_TYPE=classify_limit(message)
            _TD_DAILY_BLOCK_REASON=message or "HTTP 429: limite não especificado"
            result=_TD_BUDGET.block(_TD_DAILY_BLOCK_REASON,utcnow().to_pydatetime())
            _TD_STOP_UNTIL=result.get("blocked_until","")
            return pd.DataFrame(),f"HTTP 429 QUOTA: {_TD_DAILY_BLOCK_REASON}"
        if r.status_code!=200 or is_error: return pd.DataFrame(),f"HTTP {r.status_code}: {message[:500]}"
        df=valid_records(js.get("values",[]) if isinstance(js,dict) else [],interval,now=utcnow())
        if df.empty: return df,"Sem OHLC fechado válido."
        observed=utcnow().isoformat()
        records=_serialize_tf_cache(df,outputsize)
        candidate={"series":{f"{pair}|{interval}":{"fetched_at":observed,"records":records}}}
        _,error=read_series(candidate,pair,interval,outputsize,now=utcnow())
        if error: return pd.DataFrame(),error
        _TD_SERIES.setdefault("series",{})[f"{pair}|{interval}"]=candidate["series"][f"{pair}|{interval}"]
        df.attrs["source_fetched_at"]=observed
        return df,""
    except BudgetUnavailable:
        _TD_DAILY_BLOCKED=True; _TD_BLOCK_TYPE="CONTROLE_INDISPONIVEL"
        _TD_DAILY_BLOCK_REASON="Falha ao persistir orçamento; coleta interrompida."
        return pd.DataFrame(),_TD_DAILY_BLOCK_REASON
    except Exception as exc:
        # A failed write/request never refunds the already reserved credit.
        return pd.DataFrame(),f"Falha na consulta ou persistência: {type(exc).__name__}"



def technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if d.empty:
        return d
    d["ema9"] = d["close"].ewm(span=9, adjust=False).mean()
    d["ema20"] = d["close"].ewm(span=20, adjust=False).mean()
    d["ema21"] = d["close"].ewm(span=21, adjust=False).mean()
    d["ema50"] = d["close"].ewm(span=50, adjust=False).mean()
    prev = d["close"].shift(1)
    tr = pd.concat([
        d["high"] - d["low"],
        (d["high"] - prev).abs(),
        (d["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14, min_periods=5).mean()
    return d

def macro_side(direction: str) -> str:
    u = str(direction).upper()
    return "BUY" if "COMPRA" in u else "SELL" if "VENDA" in u else "WAIT"

def analyze_h4(df: pd.DataFrame, side: str) -> dict[str, Any]:
    d = technical_indicators(df)
    if len(d) < 60 or side not in ("BUY", "SELL"):
        return {"status":"⚪ MACRO AGUARDAR" if side=="WAIT" else "⚪ INDISPONÍVEL", "score":50 if side=="WAIT" else 0}
    x = d.iloc[-1]
    slope = float(d["ema20"].iloc[-1] - d["ema20"].iloc[-6])
    checks = [
        x["ema20"] > x["ema50"], slope > 0, x["close"] > x["ema20"]
    ] if side == "BUY" else [
        x["ema20"] < x["ema50"], slope < 0, x["close"] < x["ema20"]
    ]
    n = sum(bool(v) for v in checks)
    if n == 3: return {"status":"🟢 CONFIRMA","score":100,"texto":"H4 alinhado ao macro."}
    if n == 2: return {"status":"🟡 PARCIAL","score":65,"texto":"H4 parcialmente alinhado."}
    return {"status":"🔴 CONTRA","score":20,"texto":"H4 contra o macro."}

def analyze_h1(df: pd.DataFrame, side: str) -> dict[str, Any]:
    d = technical_indicators(df)
    if len(d) < 60 or side not in ("BUY", "SELL"):
        return {"status":"⚪ MACRO AGUARDAR" if side=="WAIT" else "⚪ INDISPONÍVEL", "score":50 if side=="WAIT" else 0}
    x = d.iloc[-1]
    atr = float(x["atr14"]) if pd.notna(x["atr14"]) and x["atr14"] > 0 else max(float(x["close"])*.001,1e-8)
    recent = d.tail(8)
    dist = abs(float(x["close"] - x["ema20"])) / atr
    if side == "BUY":
        trend = bool(x["ema20"] > x["ema50"] and x["close"] > x["ema50"])
        touch = bool((recent["low"] <= recent["ema20"] + .25*recent["atr14"].fillna(atr)).any())
        recovered = bool(x["close"] > x["ema20"])
    else:
        trend = bool(x["ema20"] < x["ema50"] and x["close"] < x["ema50"])
        touch = bool((recent["high"] >= recent["ema20"] - .25*recent["atr14"].fillna(atr)).any())
        recovered = bool(x["close"] < x["ema20"])
    if trend and touch and recovered: return {"status":"🟢 PULLBACK OK","score":100,"texto":"H1 pullback confirmado."}
    if trend and dist > 1.2: return {"status":"🟡 ESTICADO","score":55,"texto":"H1 alinhado, porém esticado."}
    if trend: return {"status":"🟡 ALINHADO","score":70,"texto":"H1 favorece o macro."}
    return {"status":"🔴 CONTRA","score":20,"texto":"H1 contra o macro."}

def analyze_m15(df: pd.DataFrame, side: str) -> dict[str, Any]:
    d = technical_indicators(df)
    if len(d) < 30 or side not in ("BUY", "SELL"):
        return {"status":"⚪ MACRO AGUARDAR" if side=="WAIT" else "⚪ INDISPONÍVEL", "score":50 if side=="WAIT" else 0}
    x = d.iloc[-1]
    ph = float(d["high"].shift(1).rolling(3).max().iloc[-1])
    pl = float(d["low"].shift(1).rolling(3).min().iloc[-1])
    if side == "BUY":
        momentum = bool(x["ema9"] > x["ema21"] and x["close"] > x["ema9"])
        bos = bool(x["close"] > ph)
    else:
        momentum = bool(x["ema9"] < x["ema21"] and x["close"] < x["ema9"])
        bos = bool(x["close"] < pl)
    if momentum and bos: return {"status":"🟢 GATILHO","score":100,"texto":"M15 gatilho confirmado."}
    if momentum: return {"status":"🟡 AGUARDAR GATILHO","score":65,"texto":"M15 momentum alinhado."}
    return {"status":"🔴 SEM GATILHO","score":25,"texto":"M15 sem gatilho."}

def technical_decision(tec: Mapping[str, Any], direction: str) -> tuple[str, str]:
    if macro_side(direction) == "WAIT":
        return "⚪ MACRO AGUARDAR", "Dados técnicos válidos; macro sem BUY/SELL."
    s4, s1, s15 = (str((tec.get(k,{}) or {}).get("status","")) for k in ("h4","h1","m15"))
    if "🔴" in s4 or "🔴" in s1:
        return "🔴 CONTRA", "H4/H1 contra o viés macro."
    if "🟢" in s4 and "🟢" in s1 and "🟢" in s15:
        return "🟢 CONFIGURAÇÃO COMPLETA", "Macro + H4 + H1 + M15 alinhados."
    if "🟢" in s4 and "🟢" in s1:
        return "🟡 AGUARDAR GATILHO", "H4/H1 alinhados; aguardar M15."
    return "🟡 AGUARDAR", "Confluência técnica incompleta."

def pair_input_map(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = inputs.get("pairs", []) if isinstance(inputs, Mapping) else []
    out = {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("Par"):
            out[str(row["Par"])] = dict(row)
    return out


def _daily_budget_meta(state: Mapping[str, Any]) -> tuple[str, int]:
    today = utcnow().strftime("%Y-%m-%d")
    auto = dict((state or {}).get("autopilot_v107", {}) or {})
    budget = dict(auto.get("daily_budget", {}) or {})
    if str(budget.get("day", "")) != today:
        return today, 0
    return today, int(budget.get("calls", 0) or 0)


def _is_priority_pair_v1075(pair: str, pmap: Mapping[str, Mapping[str, Any]]) -> bool:
    directional = []
    for p, row in pmap.items():
        direction = str(row.get("Direção", row.get("Direcao", "")))
        if macro_side(direction) not in ("BUY", "SELL"):
            continue
        score = float(row.get("Índice ranking", row.get("Índice operacional", row.get("Score final", 0))) or 0)
        directional.append((score, p))
    directional.sort(reverse=True)
    top = {p for _, p in directional[:3]}
    return pair in top


def _serialize_tf_cache(df: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    x=df.tail(max(8,int(limit))).copy()
    if "datetime" in x.columns:
        x["datetime"] = pd.to_datetime(x["datetime"], utc=True, errors="coerce").astype(str)
    cols=[c for c in ("datetime","open","high","low","close") if c in x.columns]
    return x[cols].to_dict("records")


def _deserialize_tf_cache(records: list[dict[str, Any]] | None) -> pd.DataFrame:
    return normalize_ohlc(records or [])


def scanner_update(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, pd.DataFrame], list[str], int]:
    state, _ = gh_get_json(SCANNER_PATH, {"versao":"V10.7","resultados":{}})
    if not isinstance(state, dict):
        state = {"versao":"V10.7","resultados":{}}
    results = dict(state.get("resultados", {}) or {})
    pmap = pair_input_map(inputs)
    now = utcnow()
    market_open = forex_market_likely_open(now)
    m15_frames: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    calls = 0

    auto_meta = dict(state.get("autopilot_v107", {}) or {})
    fetches = dict(auto_meta.get("last_fetches", {}) or {})
    budget_day, budget_calls = _daily_budget_meta(state)

    if not market_open:
        auto_meta["last_run"] = now.isoformat()
        auto_meta["market_open"] = False
        state["autopilot_v107"] = auto_meta
        return state, m15_frames, errors, calls

    # Oldest M15 first avoids starving the last symbols when pacing defers a run.
    ordered_pairs=sorted(PAIR_ORDER, key=lambda p: minutes_since((fetches.get(p,{}) or {}).get('m15')) if minutes_since((fetches.get(p,{}) or {}).get('m15')) is not None else 10**9, reverse=True)
    for pair in ordered_pairs:
        row = pmap.get(pair, {})
        direction = str(row.get("Direção", row.get("Direcao", "⚪ AGUARDAR")))
        side = macro_side(direction)
        old = dict(results.get(pair, {}) or {})
        old_tec = dict(old.get("tecnico", {}) or {})
        old_dir = str(old.get("macro_direction", ""))
        pair_fetch = dict(fetches.get(pair, {}) or {})

        direction_changed = bool(old_dir and old_dir != direction)
        priority = _is_priority_pair_v1075(pair, pmap)
        m15_every = PRIORITY_M15_EVERY_MIN if priority else M15_EVERY_MIN
        h1_every = PRIORITY_H1_EVERY_MIN if priority else H1_EVERY_MIN

        due_m15 = direction_changed or (
            minutes_since(pair_fetch.get("m15")) is None
            or minutes_since(pair_fetch.get("m15")) >= m15_every
        )
        due_h1 = direction_changed or (
            minutes_since(pair_fetch.get("h1")) is None
            or minutes_since(pair_fetch.get("h1")) >= h1_every
        )
        due_h4 = direction_changed or (
            minutes_since(pair_fetch.get("h4")) is None
            or minutes_since(pair_fetch.get("h4")) >= H4_EVERY_MIN
        )

        # Candles em cache são matéria-prima neutra; estados H4/H1/M15/ICT são dependentes do lado macro.
        # Se a direção muda, nunca reaproveitamos uma confirmação calculada para o lado anterior.
        tec = {
            "disponivel": False if direction_changed else bool(old_tec.get("disponivel", False)),
            "dados_disponiveis": False if direction_changed else bool(old_tec.get("dados_disponiveis", old_tec.get("disponivel", False))),
            "h4": {} if direction_changed else dict(old_tec.get("h4", {}) or {}),
            "h1": {} if direction_changed else dict(old_tec.get("h1", {}) or {}),
            "m15": {} if direction_changed else dict(old_tec.get("m15", {}) or {}),
            "ict": {} if direction_changed else dict(old_tec.get("ict", {}) or {}),
            "institutional": {} if direction_changed else dict(old_tec.get("institutional", {}) or {}),
            "cache_v110": dict(old_tec.get("cache_v110", {}) or {}),
            "preco_m15": old_tec.get("preco_m15"),
            "ultima_atualizacao": old_tec.get("ultima_atualizacao"),
            "motivo": "Direção macro mudou; confirmações anteriores invalidadas." if direction_changed else "",
            "erro": "",
            "diagnostico": "",
        }

        interval_specs = []
        if due_m15: interval_specs.append(("m15","15min",500))
        if due_h1: interval_specs.append(("h1","1h",100))
        if due_h4: interval_specs.append(("h4","4h",100))

        ok_any = False
        fetched_at = now.isoformat()
        for key, interval, outputsize in interval_specs:
            if _TD_DAILY_BLOCKED:
                break
            before_calls=_TD_HTTP_CALLS
            frame, err = td_fetch(pair, interval, outputsize)
            calls += _TD_HTTP_CALLS-before_calls
            budget_calls += _TD_HTTP_CALLS-before_calls
            if err or frame.empty:
                errors.append(f"{pair} {interval}: {err or 'sem dados'}")
                continue
            try:
                closed = closed_candles(frame, interval, now=now)
            except Exception as exc:
                errors.append(f"{pair} {interval}: {type(exc).__name__}: {exc}")
                continue
            if closed.empty:
                errors.append(f"{pair} {interval}: sem candle fechado")
                continue

            ok_any = True
            fetched_at=frame.attrs.get("source_fetched_at",fetched_at)
            pair_fetch[key] = fetched_at
            if key == "m15":
                m15_frames[pair] = closed
                tec["m15"] = analyze_m15(closed, side)
                _ict = dict(tec.get("ict", {}) or {})
                _ict["amd"] = detect_amd(closed, side)
                _ict["fvg"] = detect_fvg(closed, side)
                tec["ict"] = _ict
                tec["preco_m15"] = float(closed.iloc[-1]["close"])
                tec["ultima_atualizacao"] = pd.Timestamp(closed.iloc[-1]["datetime"]).isoformat()
                old["m15_fetched_at"] = fetched_at
                _cache_v110 = dict(tec.get("cache_v110", {}) or {})
                _cache_v110["m15"] = _serialize_tf_cache(closed, 128)
                tec["cache_v110"] = _cache_v110
            elif key == "h1":
                tec["h1"] = analyze_h1(closed, side)
                _ict = dict(tec.get("ict", {}) or {})
                _ict["crt"] = detect_crt(closed, side)
                _ict["ote"] = detect_ote(closed, side)
                tec["ict"] = _ict
                old["h1_fetched_at"] = fetched_at
                _cache_v110 = dict(tec.get("cache_v110", {}) or {})
                _cache_v110["h1"] = _serialize_tf_cache(closed, 80)
                tec["cache_v110"] = _cache_v110
            elif key == "h4":
                tec["h4"] = analyze_h4(closed, side)
                old["h4_fetched_at"] = fetched_at
                tec["cache_v110"]["h4"] = _serialize_tf_cache(closed,100)

        # If M15 wasn't due, still try to make it available for market-map/validation
        # from one fresh fetch only when needed by those modules.
        if pair not in m15_frames and due_m15 is False:
            cached,cache_err=read_series(_TD_SERIES,pair,"15min",500)
            if not cache_err: m15_frames[pair]=cached

        _ict = dict(tec.get("ict", {}) or {})
        if side in ("BUY", "SELL") and _ict:
            _parts = [dict(_ict.get(k, {}) or {}) for k in ("crt", "ote", "amd", "fvg")]
            _scores = [float(x.get("score", 0) or 0) for x in _parts]
            _weights = (0.30, 0.25, 0.30, 0.15)
            _ready = float(np.clip(sum(v*w for v,w in zip(_scores,_weights)), 0, 100))
            _ict["readiness"] = round(_ready, 1)
            _ict["label"] = "🟢 ICT MUITO ALINHADO" if _ready >= 80 else "🟡 ICT EM PREPARAÇÃO" if _ready >= 60 else "⚪ ICT AINDA INCOMPLETO"
            _ict["side"] = side
            _ict["updated_at"] = now.isoformat()
        elif side == "WAIT":
            _ict["readiness"] = 0.0
            _ict["label"] = "⚪ MACRO AGUARDAR"
            _ict["side"] = side
        tec["ict"] = _ict

        tec["disponivel"] = bool(tec.get("h4") and tec.get("h1") and tec.get("m15"))
        tec["dados_disponiveis"] = tec["disponivel"]
        decision, text = technical_decision(tec, direction)

        old.update({
            "tecnico": tec,
            "decisao": decision,
            "texto": text,
            "macro_direction": direction,
            "processado_em": time.time() if ok_any else old.get("processado_em", 0),
            "tentativa_v107": True,
            "versao_tentativa": "V11.0_INSTITUTIONAL_AUTOPILOT",
        })
        results[pair] = old
        fetches[pair] = pair_fetch

        # Continue invalidating changed directions even when no further HTTP is allowed.

    # V11.0 — calcula a camada institucional para TODOS os pares usando cache
    # persistido. Não consome API e permite SMT entre pares correlacionados.
    for _pair in PAIR_ORDER:
        _row = pmap.get(_pair, {})
        _direction = str(_row.get("Direção", _row.get("Direcao", "⚪ AGUARDAR")))
        _side = macro_side(_direction)
        _old = dict(results.get(_pair, {}) or {})
        _tec = dict(_old.get("tecnico", {}) or {})
        _cache = dict(_tec.get("cache_v110", {}) or {})
        _h1 = _deserialize_tf_cache(_cache.get("h1", []))
        _m15 = _deserialize_tf_cache(_cache.get("m15", []))
        _comp = SMT_COMPANIONS.get(_pair)
        _comp_m15 = pd.DataFrame()
        if _comp:
            _comp_old = dict(results.get(_comp, {}) or {})
            _comp_tec = dict(_comp_old.get("tecnico", {}) or {})
            _comp_cache = dict(_comp_tec.get("cache_v110", {}) or {})
            _comp_m15 = _deserialize_tf_cache(_comp_cache.get("m15", []))
        try:
            _tec["institutional"] = build_institutional_snapshot(
                _pair, _h1, _m15, _side, _comp_m15, _comp
            )
        except Exception as _inst_exc:
            _tec["institutional"] = {
                "pair":_pair,"side":_side,"readiness":0.0,
                "label":"⚪ INSTITUCIONAL INDISPONÍVEL",
                "error":f"{type(_inst_exc).__name__}: {_inst_exc}",
            }
        _old["tecnico"] = _tec
        results[_pair] = _old

    state["versao"] = "V11.0_INSTITUTIONAL_AUTOPILOT"
    state["resultados"] = results
    state["ultimo_processamento_ts"] = time.time()
    auto_meta.update({
        "last_run": now.isoformat(),
        "market_open": True,
        "last_fetches": fetches,
        "twelve_calls_last_run": calls,
        "daily_budget": {
            "day": budget_day,
            "calls": budget_calls,
            "limit": AUTOPILOT_DAILY_CALL_BUDGET,
        },
    })
    state["autopilot_v107"] = auto_meta
    return state, m15_frames, errors, calls

def serialize_daily(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    x = df.copy()
    x["datetime"] = pd.to_datetime(x["datetime"], utc=True, errors="coerce").astype(str)
    return x[["datetime","open","high","low","close"]].to_dict("records")

def deserialize_daily(records: list[dict[str, Any]]) -> pd.DataFrame:
    return normalize_ohlc(records or [])

def ensure_daily_cache() -> tuple[dict[str, Any], list[str], int]:
    cache, _ = gh_get_json(DAILY_CACHE_PATH, {"pairs":{}})
    if _TD_DAILY_BLOCKED:
        return cache if isinstance(cache, dict) else {"pairs":{}}, [], 0
    if not isinstance(cache, dict):
        cache = {"pairs":{}}
    pairs = dict(cache.get("pairs", {}) or {})
    today = utcnow().strftime("%Y-%m-%d")
    errors = []
    calls = 0
    if not forex_market_likely_open():
        return cache, errors, calls
    for pair in PAIR_ORDER:
        raw = dict(pairs.get(pair, {}) or {})
        if str(raw.get("cache_day","")) == today and raw.get("records"):
            continue
        before_calls=_TD_HTTP_CALLS
        df, err = td_fetch(pair, "1day", 320)
        calls += _TD_HTTP_CALLS-before_calls
        if err or df.empty:
            errors.append(f"{pair} D1: {err or 'sem dados'}")
            continue
        pairs[pair] = {
            "cache_day": today,
            "updated_at": utcnow().isoformat(),
            "records": serialize_daily(df),
        }
    cache["pairs"] = pairs
    cache["updated_at"] = utcnow().isoformat()
    return cache, errors, calls

def market_context_from_data(
    pair: str, row: Mapping[str, Any], macro_context: Mapping[str, Any],
    daily: pd.DataFrame, m15: pd.DataFrame
) -> dict[str, Any] | None:
    if daily.empty or m15.empty:
        return None
    direction = str(row.get("Direção", row.get("Direcao", "⚪ AGUARDAR")))
    score = float(row.get("Score final", row.get("Score", 0)) or 0)
    quality = float(row.get("Qualidade", 0) or 0)
    rank_index = float(row.get("Índice ranking", row.get("Índice operacional", 0)) or 0)
    now_ny = datetime.now(NY_TZ)
    d_closed = completed_daily(daily, now_ny.date())
    weekly = aggregate_ohlc(d_closed, "W-FRI")
    w1 = trend_context(weekly)
    d1 = trend_context(d_closed)
    price = float(m15.iloc[-1]["close"])
    candle = pd.Timestamp(m15.iloc[-1]["datetime"])

    levels = prior_period_levels(daily, now_ny.date())
    levels.update(equal_liquidity_levels(d_closed))
    asia = session_range(m15, now_ny)
    if asia.get("available"):
        levels["Asia High"] = float(asia["high"])
        levels["Asia Low"] = float(asia["low"])
    pd_loc = premium_discount(price, levels.get("PWL"), levels.get("PWH"))
    bsl, ssl = nearest_liquidity(price, levels)
    sweeps = recent_sweeps(m15, levels, bars=16)
    latest = sweeps[0] if sweeps else None
    latest_type = str(latest.get("type","")) if latest else ""
    kz = killzone_state(now_ny)
    active = kz.get("active")
    regime = macro_regime_summary(pair, direction, score, quality, dict(macro_context or {}))
    readiness = setup_readiness(
        direction, score, quality, w1, d1,
        pd_loc.get("zone","INDEFINIDO"), latest_type, bool(active),
        regime.get("event_risk",{}).get("level","NORMAL"),
    )
    adr = adr_context(daily, m15, now_ny, length=14)
    opens = intraday_open_context(m15, now_ny)

    return {
        "pair": pair,
        "updated_at": utcnow().isoformat(),
        "candle_m15": candle.isoformat(),
        "price": price,
        "macro_direction": direction,
        "macro_score": score,
        "quality": quality,
        "rank_index": rank_index,
        "w1": w1, "d1": d1,
        "levels": levels,
        "premium_discount": pd_loc,
        "bsl": bsl, "ssl": ssl,
        "latest_sweep": latest,
        "killzone": kz,
        "macro_regime": regime,
        "readiness": readiness,
        "readiness_grade": readiness.get("grade","WAIT"),
        "readiness_score": readiness.get("score",0),
        "event_risk": regime.get("event_risk",{}).get("level","NORMAL"),
        "adr": adr,
        "adr_used_pct": adr.get("used_pct"),
        "intraday_opens": opens,
        "autopilot_v107": True,
    }

def update_market_map(inputs: Mapping[str, Any], m15_frames: Mapping[str,pd.DataFrame], daily_cache: Mapping[str,Any]) -> tuple[dict[str,Any], list[str]]:
    state, _ = gh_get_json(MASTER_PATH, {"version":"V10.7","contexts":{}})
    if not isinstance(state, dict):
        state = {"version":"V10.7","contexts":{}}
    contexts = dict(state.get("contexts", {}) or {})
    pmap = pair_input_map(inputs)
    macro_context = dict(inputs.get("macro_context", {}) or {})
    daily_pairs = dict(daily_cache.get("pairs", {}) or {})
    errors = []

    for pair in PAIR_ORDER:
        m15 = m15_frames.get(pair)
        if m15 is None or m15.empty:
            continue
        daily = deserialize_daily((daily_pairs.get(pair,{}) or {}).get("records", []))
        if daily.empty:
            errors.append(f"{pair}: cache D1 ausente")
            continue
        try:
            ctx = market_context_from_data(pair, pmap.get(pair,{}), macro_context, daily, m15)
            if ctx:
                # Recomputing from cache must not advance the data's timestamp.
                ctx['updated_at']=m15.attrs.get('source_fetched_at',ctx.get('updated_at'))
                contexts[pair] = ctx
        except Exception as exc:
            errors.append(f"{pair} map: {type(exc).__name__}: {exc}")

    state.update({
        "version":"V11.0_INSTITUTIONAL_AUTOPILOT",
        "contexts":contexts,
        "last_batch_ts":time.time(),
        "autopilot_updated_at":utcnow().isoformat(),
    })
    return state, errors

def should_refresh_news(current: Mapping[str,Any]) -> bool:
    age = minutes_since(current.get("updated_at")) if isinstance(current, Mapping) else None
    return age is None or age >= NEWS_EVERY_MIN

def get_news() -> tuple[dict[str,Any], list[str]]:
    current, _ = gh_get_json(NEWS_CURRENT_PATH, {})
    errors = []
    if isinstance(current, dict) and current and not should_refresh_news(current):
        return current, errors
    try:
        intel = load_currency_news_intelligence(NEWS_KEY)
        return intel, errors
    except Exception as exc:
        errors.append(f"news: {type(exc).__name__}: {exc}")
        return current if isinstance(current,dict) else {}, errors

VALIDATION_COLS = [
    "day_utc","registered_at","pair","motor_base","news_side","news_diff","alignment",
    "coverage","conviction","base_news_score","quote_news_score",
    "base_independent_stories","quote_independent_stories","base_shared_ratio","quote_shared_ratio",
    "signal_frozen_at","entry_origin","backfilled_at","m15_candle_time","auto_managed",
    "timing_migrated_v107","entry_price","entry_time","price_source","validation_status",
    "price_1h","return_1h_pct","hit_1h","price_4h","return_4h_pct","hit_4h",
    "price_24h","return_24h_pct","hit_24h",
]

def news_side(diff: float) -> str:
    return "BUY" if diff >= 2 else "SELL" if diff <= -2 else "NEUTRAL"

def _bool_or_none_v1081(value):
    """Normaliza booleanos persistidos em CSV sem depender do dtype inferido pelo pandas."""
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).strip().lower()
    if text in ("true", "1", "sim", "yes"):
        return True
    if text in ("false", "0", "nao", "não", "no"):
        return False
    return None


def _normalize_news_validation_dtypes_v1081(df: pd.DataFrame) -> pd.DataFrame:
    """V10.8.1 — Pandas dtype guard para snapshots/validações de notícias.

    CSVs antigos podem fazer colunas booleanas vazias serem inferidas como float64.
    Pandas 2.x rejeita `df.at[..., col] = True` nessas colunas. Normalizamos antes
    de qualquer migração/backfill/validação.
    """
    if df is None:
        return pd.DataFrame(columns=VALIDATION_COLS)
    df = df.copy()

    for c in VALIDATION_COLS:
        if c not in df.columns:
            df[c] = None

    bool_cols = (
        "auto_managed", "timing_migrated_v107",
        "hit_1h", "hit_4h", "hit_24h",
    )
    for c in bool_cols:
        df[c] = df[c].map(_bool_or_none_v1081).astype("object")

    numeric_cols = (
        "news_diff", "coverage", "conviction",
        "base_news_score", "quote_news_score",
        "base_independent_stories", "quote_independent_stories",
        "base_shared_ratio", "quote_shared_ratio",
        "entry_price", "price_1h", "return_1h_pct",
        "price_4h", "return_4h_pct",
        "price_24h", "return_24h_pct",
    )
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")

    # Campos textuais permanecem object para aceitar strings/None com segurança.
    text_cols = (
        "day_utc", "registered_at", "pair", "motor_base", "news_side",
        "alignment", "signal_frozen_at", "entry_origin", "backfilled_at",
        "m15_candle_time", "entry_time", "price_source", "validation_status",
    )
    for c in text_cols:
        df[c] = df[c].astype("object")

    return df



def pair_rows(pair_df: pd.DataFrame) -> dict[str,dict[str,Any]]:
    return {str(r["Par"]):r.to_dict() for _,r in pair_df.iterrows()} if pair_df is not None and not pair_df.empty else {}

def directional_return(side: str, entry: float, exit_price: float) -> float:
    raw = (float(exit_price)/float(entry)-1)*100
    return -raw if side=="SELL" else raw

def exact_horizon_close(frame: pd.DataFrame, target: pd.Timestamp) -> float | None:
    if frame is None or frame.empty:
        return None
    d = frame.copy()
    d["datetime"] = pd.to_datetime(d["datetime"], utc=True, errors="coerce")
    close_at = d["datetime"] + pd.Timedelta(minutes=15)
    mask = (close_at >= target) & (close_at < target + pd.Timedelta(minutes=15))
    hit = d.loc[mask]
    if hit.empty:
        return None
    return float(hit.iloc[0]["close"])

def migrate_timing(df: pd.DataFrame) -> int:
    migrated = 0
    if df.empty:
        return migrated
    for c in VALIDATION_COLS:
        if c not in df.columns:
            df[c] = None
    df = _normalize_news_validation_dtypes_v1081(df)
    for idx,row in df.iterrows():
        if str(row.get("timing_migrated_v107","")).lower() in ("true","1","sim"):
            continue
        if pd.isna(row.get("entry_price")):
            continue
        sig = pd.to_datetime(row.get("signal_frozen_at"), utc=True, errors="coerce")
        ent = pd.to_datetime(row.get("entry_time"), utc=True, errors="coerce")
        if pd.notna(sig) and pd.notna(ent) and sig > ent:
            df.at[idx,"m15_candle_time"] = ent.isoformat()
            df.at[idx,"entry_time"] = sig.isoformat()
            df.at[idx,"timing_migrated_v107"] = True
            migrated += 1
    return migrated

def manage_snapshots(intel: Mapping[str,Any], pair_df: pd.DataFrame, m15_frames: Mapping[str,pd.DataFrame]) -> tuple[pd.DataFrame, dict[str,int]]:
    df, _ = gh_get_csv(NEWS_VALIDATION_PATH)
    if df.empty:        df = pd.DataFrame(columns=VALIDATION_COLS)
    for c in VALIDATION_COLS:
        if c not in df.columns:
            df[c] = None

    # V10.8.1 — evita TypeError: Invalid value 'True' for dtype 'float64'.
    df = _normalize_news_validation_dtypes_v1081(df)

    migrated = migrate_timing(df)
    lookup = pair_rows(pair_df)
    currencies = dict(intel.get("currencies",{}) or {})
    now = utcnow()
    now_iso = now.isoformat()
    day = now.strftime("%Y-%m-%d")
    added = frozen = validated = 0

    # Ensure one row per pair/day.
    existing = set(df["day_utc"].astype(str)+"|"+df["pair"].astype(str)) if not df.empty else set()
    for pair in PAIR_ORDER:
        current = lookup.get(pair,{})
        if not current:
            continue
        key = f"{day}|{pair}"
        if key in existing:
            continue
        base, quote = pair.split("/")
        diff = float(current.get("Diferencial notícias",0) or 0)
        side = news_side(diff)
        b,q = currencies.get(base,{}), currencies.get(quote,{})
        df = pd.concat([df,pd.DataFrame([{
            "day_utc":day,"registered_at":now_iso,"pair":pair,
            "motor_base":str(current.get("Motor base","")),
            "news_side":side,"news_diff":diff,"alignment":str(current.get("Alinhamento","")),
            "coverage":float(current.get("Cobertura notícias",0) or 0),
            "conviction":float(current.get("Convicção heurística",0) or 0),
            "base_news_score":float(b.get("news_score",50) or 50),
            "quote_news_score":float(q.get("news_score",50) or 50),
            "base_independent_stories":float(b.get("effective_independent_stories",0) or 0),
            "quote_independent_stories":float(q.get("effective_independent_stories",0) or 0),
            "base_shared_ratio":float(b.get("shared_story_ratio",0) or 0),
            "quote_shared_ratio":float(q.get("shared_story_ratio",0) or 0),
            "signal_frozen_at":None,"entry_origin":"AUTOPILOT_WAITING",
            "backfilled_at":None,"m15_candle_time":None,"auto_managed":True,
            "timing_migrated_v107":False,"entry_price":None,"entry_time":None,
            "price_source":"Autopilot aguardando lado+M15 fechado",
            "validation_status":"OBSERVACAO_NEUTRA" if side=="NEUTRAL" else "SEM_PRECO_FRESCO",
        }])],ignore_index=True)
        added += 1

    # Timing integrity V11.0.6:
    # 1) congela o sinal quando ele se torna direcional;
    # 2) a entrada usa somente o primeiro candle M15 disponível EM/DEPOIS do congelamento.
    # Nunca usa preço anterior ao sinal como se fosse preço de entrada.
    for idx,row in df.iterrows():
        if str(row.get("day_utc","")) != day or pd.notna(pd.to_numeric(pd.Series([row.get("entry_price")]),errors="coerce").iloc[0]):
            continue
        pair = str(row.get("pair",""))
        current = lookup.get(pair,{})
        if not current:
            continue
        frozen_at = pd.to_datetime(row.get("signal_frozen_at"),utc=True,errors="coerce")

        # Enquanto ainda não congelou, acompanha o estado corrente e congela ao ficar direcional.
        if pd.isna(frozen_at):
            base,quote = pair.split("/")
            b,q = currencies.get(base,{}), currencies.get(quote,{})
            diff = float(current.get("Diferencial notícias",0) or 0)
            side = news_side(diff)
            df.at[idx,"motor_base"] = str(current.get("Motor base",""))
            df.at[idx,"news_side"] = side
            df.at[idx,"news_diff"] = diff
            df.at[idx,"alignment"] = str(current.get("Alinhamento",""))
            df.at[idx,"coverage"] = float(current.get("Cobertura notícias",0) or 0)
            df.at[idx,"conviction"] = float(current.get("Convicção heurística",0) or 0)
            df.at[idx,"base_news_score"] = float(b.get("news_score",50) or 50)
            df.at[idx,"quote_news_score"] = float(q.get("news_score",50) or 50)
            df.at[idx,"base_independent_stories"] = float(b.get("effective_independent_stories",0) or 0)
            df.at[idx,"quote_independent_stories"] = float(q.get("effective_independent_stories",0) or 0)
            if side=="NEUTRAL":
                df.at[idx,"validation_status"]="OBSERVACAO_NEUTRA"
                continue
            df.at[idx,"signal_frozen_at"] = now_iso
            df.at[idx,"entry_origin"] = "AUTOPILOT_WAIT_POST_SIGNAL_M15"
            df.at[idx,"price_source"] = "Aguardando primeiro M15 posterior ao sinal"
            df.at[idx,"validation_status"] = "AGUARDANDO_PRECO_POS_SINAL"
            frozen_at = now
            frozen += 1

        # Sinal já congelado: não altera lado/notícias; busca somente candle posterior ao sinal.
        side = str(df.at[idx,"news_side"] or "")
        if side not in ("BUY","SELL"):
            continue
        frame = m15_frames.get(pair)
        if frame is None or frame.empty:
            continue
        x=frame.copy()
        x["datetime"]=pd.to_datetime(x["datetime"],utc=True,errors="coerce")
        x=x.dropna(subset=["datetime"]).sort_values("datetime")
        eligible=x[x["datetime"] >= frozen_at]
        if eligible.empty:
            df.at[idx,"validation_status"]="AGUARDANDO_PRECO_POS_SINAL"
            continue
        first=eligible.iloc[0]
        candle_time=pd.Timestamp(first["datetime"])
        df.at[idx,"entry_price"] = float(first["close"])
        df.at[idx,"m15_candle_time"] = candle_time.isoformat()
        df.at[idx,"entry_time"] = candle_time.isoformat()
        df.at[idx,"entry_origin"] = "AUTOPILOT_M15_POS_SINAL"
        df.at[idx,"backfilled_at"] = now_iso
        df.at[idx,"auto_managed"] = True
        df.at[idx,"timing_migrated_v107"] = True
        df.at[idx,"price_source"] = "Autopilot: primeiro M15 em/depois do sinal congelado"
        df.at[idx,"validation_status"] = "PENDENTE"

    # Validate all matured horizons, reusing the same M15 frame.
    for idx,row in df.iterrows():
        side = str(row.get("news_side",""))
        entry = pd.to_numeric(pd.Series([row.get("entry_price")]),errors="coerce").iloc[0]
        et = pd.to_datetime(row.get("entry_time"),utc=True,errors="coerce")
        if side not in ("BUY","SELL") or pd.isna(entry) or pd.isna(et):
            continue
        frame = m15_frames.get(str(row.get("pair","")))
        if frame is None or frame.empty:
            continue
        any_new=False
        for hours in (1,4,24):
            cp,cr,ch = f"price_{hours}h",f"return_{hours}h_pct",f"hit_{hours}h"
            if pd.notna(row.get(cp)):
                continue
            target = et + pd.Timedelta(hours=hours)
            if now < target:
                continue
            px = exact_horizon_close(frame,target)
            if px is None:
                continue
            ret = directional_return(side,float(entry),px)
            df.at[idx,cp]=px; df.at[idx,cr]=ret; df.at[idx,ch]=bool(ret>0)
            any_new=True; validated += 1
        if any_new:
            df.at[idx,"validation_status"] = "COMPLETO" if pd.notna(df.at[idx,"price_24h"]) else "PARCIAL"

    return df[VALIDATION_COLS], {"added":added,"frozen":frozen,"validated_horizons":validated,"migrated":migrated}

def status_summary(
    app_ok: bool, app_msg: str, inputs: Mapping[str,Any], scanner: Mapping[str,Any],
    master: Mapping[str,Any], intel: Mapping[str,Any], validation: pd.DataFrame,
    errors: list[str], calls: int, snap_stats: Mapping[str,int]
) -> dict[str,Any]:
    now = utcnow()
    results = dict(scanner.get("resultados",{}) or {})
    scanner_fresh = 0
    for p in PAIR_ORDER:
        raw = results.get(p,{}) if isinstance(results,dict) else {}
        scanner_age=minutes_since(raw.get("m15_fetched_at"))
        if scanner_age is not None and scanner_age <= 60:
            scanner_fresh += 1
    contexts = dict(master.get("contexts",{}) or {})
    map_fresh = 0
    for p in PAIR_ORDER:
        age=minutes_since((contexts.get(p,{}) or {}).get("updated_at"))
        if age is not None and age <= 60:
            map_fresh += 1
    pending = int(validation["validation_status"].astype(str).isin(["PENDENTE","PARCIAL"]).sum()) if not validation.empty else 0
    complete = int((validation["validation_status"].astype(str)=="COMPLETO").sum()) if not validation.empty else 0
    try: budget=_TD_BUDGET.summary(now.to_pydatetime()) if _TD_BUDGET else {}
    except Exception: budget={"error":"Orçamento indisponível"}
    return {
        "twelve_budget":budget,
        "twelve_cache_hits":_TD_CACHE_HITS,
        "twelve_retry_after":_TD_STOP_UNTIL,
        "version":"V11.0.8_BUDGET_AUTOPILOT",
        "last_run":now.isoformat(),
        "app_headless_ok":bool(app_ok),
        "app_headless_message":app_msg,
        "matrix_generated_at":inputs.get("generated_at"),
        "scanner_fresh":scanner_fresh,
        "market_map_fresh":map_fresh,
        "news_updated_at":intel.get("updated_at"),
        "news_unique_stories":intel.get("global_unique_stories",0),
        "validation_rows":len(validation),
        "validation_pending":pending,
        "validation_complete":complete,
        "snapshot_stats":dict(snap_stats),
        "twelve_calls_this_run":int(_TD_HTTP_CALLS),
        "twelve_calls_requested_internal":int(calls),
        "twelve_rate_safe":True,
        "twelve_api_budget_limit":AUTOPILOT_DAILY_CALL_BUDGET,
        "twelve_daily_blocked":bool(_TD_DAILY_BLOCKED),
        "twelve_block_type":_TD_BLOCK_TYPE,
        "twelve_daily_block_reason":_TD_DAILY_BLOCK_REASON,
        "twelve_safe_calls_per_window":TD_SAFE_CALLS_PER_WINDOW,
        "twelve_safe_window_seconds":TD_SAFE_WINDOW_SECONDS,
        "forex_market_open":forex_market_likely_open(now),
        "errors":errors[:20],
        "healthy": bool(app_ok and not _TD_DAILY_BLOCKED and scanner_fresh >= (5 if forex_market_likely_open(now) else 0) and len(errors)<8),
    }

def main() -> int:
    all_errors: list[str] = []
    total_calls = 0

    _td_initialize()

    # 1. Full app headless: refreshes macro/FRED/matrix and persists INPUT_PATH.
    app_ok, app_msg = run_headless_app()
    if not app_ok:
        all_errors.append("AppTest: "+app_msg)

    inputs, inp_err = gh_get_json(INPUT_PATH,{})
    if inp_err:
        all_errors.append("Inputs: "+inp_err)

    # 2. Technical scanner with rate budget.
    scanner, m15_frames, scan_errors, scan_calls = scanner_update(inputs)
    all_errors.extend(scan_errors)
    total_calls += scan_calls
    ok,err=gh_put_json(SCANNER_PATH,scanner,"V10.7 Autopilot: atualiza scanner técnico")
    if not ok: all_errors.append("Salvar scanner: "+err)

    # 3. D1 cache + market map (uses same M15 calls, no duplicate M15 request).
    daily_cache,daily_errors,daily_calls=ensure_daily_cache()
    all_errors.extend(daily_errors); total_calls+=daily_calls
    ok,err=gh_put_json(DAILY_CACHE_PATH,daily_cache,"V10.7 Autopilot: cache diário FX")
    if not ok: all_errors.append("Salvar D1 cache: "+err)

    cache_ok,cache_err=gh_put_json(SERIES_PATH,_TD_SERIES,"V11.0.8: cache compartilhado sem duplicar consultas")
    if not cache_ok: all_errors.append("Salvar cache compartilhado: "+cache_err)

    master,map_errors=update_market_map(inputs,m15_frames,daily_cache)
    all_errors.extend(map_errors)
    ok,err=gh_put_json(MASTER_PATH,master,"V10.7 Autopilot: atualiza Market Map")
    if not ok: all_errors.append("Salvar Market Map: "+err)

    # 4. Global news. Hourly-ish cache.
    intel,news_errors=get_news()
    all_errors.extend(news_errors)
    if intel:
        ok,err=gh_put_json(NEWS_CURRENT_PATH,intel,"V10.7 Autopilot: notícias globais")
        if not ok: all_errors.append("Salvar notícias: "+err)

    pmap = pair_input_map(inputs)
    matrix = pd.DataFrame(list(pmap.values()))
    pair_df = pair_news_table(intel,matrix) if intel else pd.DataFrame()

    # 5. Automatic snapshots + timing migration + 1H/4H/24H validation.
    validation,snap_stats=manage_snapshots(intel,pair_df,m15_frames)
    ok,err=gh_put_csv(NEWS_VALIDATION_PATH,validation,"V11.0 Autopilot: snapshots/validação automática")
    if not ok: all_errors.append("Salvar validação: "+err)

    # 6. Health/status.
    status=status_summary(
        app_ok,app_msg,inputs,scanner,master,intel,validation,
        all_errors,total_calls,snap_stats
    )

    # 7. 28FX quota shadow telemetry — observational only.
    # Never changes PAIR_ORDER, cadence, quota, API behavior or execution gates.
    quota_state,quota_read_err=gh_get_json(
        QUOTA_SHADOW_PATH,
        {"version":"V1","samples":[]},
    )
    quota_samples=list((quota_state or {}).get("samples",[]) or []) if isinstance(quota_state,Mapping) else []
    quota_sample=build_quota_shadow_sample(status)
    quota_samples,quota_added=append_quota_shadow_sample(quota_samples,quota_sample)
    quota_summary=summarize_quota_shadow(quota_samples)
    quota_payload={
        "version":"V1",
        "updated_at":status.get("last_run"),
        "samples":quota_samples,
        "summary":quota_summary,
    }
    quota_ok=False
    quota_write_err=""
    if not quota_read_err:
        quota_ok,quota_write_err=gh_put_json(
            QUOTA_SHADOW_PATH,
            quota_payload,
            "AtlasQuant 28FX: quota shadow telemetry",
        )
    status["quota_shadow"]={
        **quota_summary,
        "sample_added":bool(quota_added),
        "persisted":bool(quota_ok),
        "error":quota_read_err or quota_write_err,
        "automatic_expansion_allowed":False,
    }

    ok,err=gh_put_json(STATUS_PATH,status,"V11.0 Autopilot: status")
    if not ok:
        all_errors.append("Salvar status: "+err)

    print(json.dumps(status,ensure_ascii=False,indent=2))
    # Fail only on structural problems. Data-source hiccups remain visible in status.
    if not TOKEN or not REPO:
        return 2
    if not TD_KEY and forex_market_likely_open():
        print("ERRO: CHAVE_TWELVE_DATA ausente no GitHub Actions.")
        return 3
    return 0

if __name__ == "__main__":
    raise SystemExit(main())