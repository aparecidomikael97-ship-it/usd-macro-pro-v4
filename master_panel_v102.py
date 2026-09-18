"""Painel Mestre de Oportunidades — USD Macro Pro V10.3.

Combina, sem alterar o motor base:
- Matriz/Decisão Automática (macro, score, qualidade)
- Professional Macro Market Map (W1/D1, liquidez, evento, Gate)
- Scanner técnico persistente H4/H1/M15
- Filtro de volatilidade ADR14 / range diário consumido

O Índice Integrado é apenas um ranking operacional. Não é probabilidade de lucro.
"""
from __future__ import annotations

import base64
import html
import json
import os
import time as _time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Mapping, Callable

import numpy as np
import pandas as pd
import requests
import streamlit as st
from twelve_cache_v1108 import cached_series, clear_shared_cache
from atlasquant_runtime_store import resolve_runtime_branch

from market_map_core_v10 import (
    NY_TZ,
    adr_context,
    aggregate_ohlc,
    completed_daily,
    equal_liquidity_levels,
    intraday_open_context,
    killzone_state,
    macro_regime_summary,
    macro_side,
    nearest_liquidity,
    normalize_ohlc,
    premium_discount,
    prior_period_levels,
    recent_sweeps,
    session_range,
    setup_readiness,
    trend_context,
)

MASTER_PATH = "dados/master_market_map_v102.json"
PAIR_ORDER = ("EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD", "USD/JPY", "USD/CHF", "USD/CAD")
AUTO_SCANNER_INTERVAL_SECONDS = 75


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if np.isfinite(out) else float(default)
    except Exception:
        return float(default)


def _fmt_price(value: Any, pair: str) -> str:
    try:
        n = float(value)
    except Exception:
        return "—"
    return f"{n:.3f}" if "JPY" in pair else f"{n:.5f}"


def _gh_config() -> tuple[str, str, str]:
    try:
        token = st.secrets.get("GITHUB_TOKEN_HISTORICO", os.getenv("GITHUB_TOKEN_HISTORICO", ""))
        repo = st.secrets.get("GITHUB_REPO_HISTORICO", os.getenv("GITHUB_REPO_HISTORICO", ""))
        branch = resolve_runtime_branch(
            st.secrets.get("GITHUB_DATA_BRANCH", os.getenv("GITHUB_DATA_BRANCH", "")),
            st.secrets.get("GITHUB_BRANCH_HISTORICO", os.getenv("GITHUB_BRANCH_HISTORICO", "")),
        )
    except Exception:
        token, repo, branch = "", "", resolve_runtime_branch()
    return str(token), str(repo), str(branch)


def _empty_state() -> dict[str, Any]:
    return {
        "version": "V10.2",
        "cursor": 0,
        "last_batch_ts": 0.0,
        "contexts": {},
    }


def _load_state() -> dict[str, Any]:
    token, repo, branch = _gh_config()
    state = _empty_state()
    if not token or not repo:
        # Modo Windows/local: persiste no próprio computador.
        try:
            if os.path.exists(MASTER_PATH):
                with open(MASTER_PATH, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    state.update(loaded)
            state.setdefault("contexts", {})
            state["_storage"] = "LOCAL"
            return state
        except Exception as exc:
            state["_error"] = f"Persistência local: {type(exc).__name__}: {exc}"
            state["_storage"] = "LOCAL"
            return state
    url = f"https://api.github.com/repos/{repo}/contents/{MASTER_PATH}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        r = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
        if r.status_code == 404:
            return state
        r.raise_for_status()
        j = r.json()
        raw = base64.b64decode(j.get("content", "")).decode("utf-8")
        loaded = json.loads(raw) if raw else {}
        if isinstance(loaded, dict):
            state.update(loaded)
        state["_sha"] = j.get("sha", "")
        state.setdefault("contexts", {})
        return state
    except Exception as exc:
        state["_error"] = f"{type(exc).__name__}: {exc}"
        return state


def _save_state(state: Mapping[str, Any]) -> tuple[bool, str]:
    token, repo, branch = _gh_config()
    if not token or not repo:
        # Modo Windows/local: não exige token GitHub e não publica nada.
        try:
            os.makedirs(os.path.dirname(MASTER_PATH) or ".", exist_ok=True)
            clean = {k: v for k, v in dict(state).items() if not str(k).startswith("_")}
            tmp_path = MASTER_PATH + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(clean, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, MASTER_PATH)
            return True, ""
        except Exception as exc:
            return False, f"Persistência local: {type(exc).__name__}: {exc}"
    url = f"https://api.github.com/repos/{repo}/contents/{MASTER_PATH}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        current = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
        sha = current.json().get("sha", "") if current.status_code == 200 else ""
        clean = {k: v for k, v in dict(state).items() if not str(k).startswith("_")}
        payload = {
            "message": "V10.2: atualiza Painel Mestre de Oportunidades",
            "content": base64.b64encode(json.dumps(clean, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload, timeout=25)
        r.raise_for_status()
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _td_series(symbol: str, interval: str, outputsize: int, _api_key: str):
    return cached_series(symbol,interval,outputsize)
_td_series.clear = clear_shared_cache


def _matrix_row(matrix: pd.DataFrame, pair: str) -> dict[str, Any]:
    if matrix is None or matrix.empty:
        return {}
    found = matrix[matrix["Par"].astype(str) == str(pair)]
    return found.iloc[0].to_dict() if not found.empty else {}


def _build_pair_context(pair: str, row: Mapping[str, Any], api_key: str, macro_context: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    direction = str(row.get("Direção", "⚪ AGUARDAR"))
    macro_score = _safe_float(row.get("Score final", row.get("Score", 0)))
    quality = _safe_float(row.get("Qualidade", 0))
    rank_index = _safe_float(row.get("Índice ranking", row.get("Índice operacional", 0)))

    daily, err_d = _td_series(pair, "1day", 320, api_key)
    m15, err_m = _td_series(pair, "15min", 500, api_key)
    if err_d or err_m or daily.empty or m15.empty:
        return None, " | ".join(x for x in (err_d, err_m) if x) or "Dados insuficientes."

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
    latest_type = str(latest.get("type", "")) if latest else ""

    kz = killzone_state(now_ny)
    active = kz.get("active")
    regime = macro_regime_summary(pair, direction, macro_score, quality, dict(macro_context or {}))
    readiness = setup_readiness(
        direction, macro_score, quality, w1, d1,
        pd_loc.get("zone", "INDEFINIDO"), latest_type, bool(active),
        regime.get("event_risk", {}).get("level", "NORMAL"),
    )
    adr = adr_context(daily, m15, now_ny, length=14)
    opens = intraday_open_context(m15, now_ny)

    return {
        "pair": pair,
        "updated_at": m15.attrs.get('source_fetched_at',pd.Timestamp.utcnow().isoformat()),
        "candle_m15": candle.isoformat(),
        "price": price,
        "macro_direction": direction,
        "macro_score": macro_score,
        "quality": quality,
        "rank_index": rank_index,
        "macro_regime": str(regime.get("weekly_label", "—")),
        "macro_consistency": _safe_float(regime.get("consistency", 0)),
        "event_risk": str(regime.get("event_risk", {}).get("level", "NORMAL")),
        "w1_bias": str(w1.get("bias", "NEUTRO")),
        "w1_regime": str(w1.get("structure", {}).get("regime", "—")),
        "w1_confirmation": str(w1.get("confirmation", "—")),
        "d1_bias": str(d1.get("bias", "NEUTRO")),
        "d1_regime": str(d1.get("structure", {}).get("regime", "—")),
        "d1_confirmation": str(d1.get("confirmation", "—")),
        "location": str(pd_loc.get("zone", "INDEFINIDO")),
        "location_position": pd_loc.get("position"),
        "bsl_name": bsl[0] if bsl else "",
        "bsl_price": bsl[1] if bsl else None,
        "ssl_name": ssl[0] if ssl else "",
        "ssl_price": ssl[1] if ssl else None,
        "latest_sweep": latest_type,
        "latest_sweep_level": str(latest.get("level", "")) if latest else "",
        "latest_sweep_price": latest.get("price") if latest else None,
        "latest_sweep_time": pd.Timestamp(latest["datetime"]).isoformat() if latest else "",
        "latest_sweep_rejection": str(latest.get("rejection", "")) if latest else "",
        "killzone": str(active.get("name", "FORA")) if active else "FORA",
        "readiness_score": _safe_float(readiness.get("score", 0)),
        "readiness_grade": str(readiness.get("grade", "WAIT")),
        "readiness_action": str(readiness.get("action", "")),
        "adr14": adr.get("adr"),
        "adr_used_pct": adr.get("used_pct"),
        "adr_state": str(adr.get("state", "SEM DADOS")),
        "day_open": opens.get("day_open") if opens.get("available") else None,
        "week_open": opens.get("week_open") if opens.get("available") else None,
        "above_day_open": opens.get("above_day_open") if opens.get("available") else None,
        "above_week_open": opens.get("above_week_open") if opens.get("available") else None,
    }, ""


def _status_kind(status: Any) -> str:
    s = str(status or "").upper()
    if "🟢" in s or "CONFIRMA" in s or "PULLBACK OK" in s:
        return "GREEN"
    if "🔴" in s or "CONTRA" in s or "SEM GATILHO" in s:
        return "RED"
    if "🟡" in s or "AGUARDAR" in s or "BASE" in s:
        return "YELLOW"
    return "UNKNOWN"


def _minutes_since(value: Any) -> float | None:
    if value in (None, "", 0, 0.0):
        return None
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '', 1).isdigit()):
            ts = pd.Timestamp(float(value), unit="s", tz="UTC")
        else:
            ts = pd.Timestamp(value)
            ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        return max(0.0, (pd.Timestamp.now(tz="UTC") - ts).total_seconds() / 60.0)
    except Exception:
        return None


def _context_fresh(context: Mapping[str, Any] | None, current_direction: str, max_minutes: float = 45.0) -> tuple[bool, str]:
    if not context:
        return False, "Market Map ainda não processado."
    saved_dir = str(context.get("macro_direction", ""))
    if saved_dir and saved_dir != str(current_direction):
        return False, "O viés macro mudou desde o último Market Map."
    age = _minutes_since(context.get("updated_at"))
    if age is not None and age > max_minutes:
        return False, f"Market Map com {age:.0f} min; atualizar antes de executar."
    return True, ""


def _scanner_for_pair(scanner_state: Mapping[str, Any] | None, pair: str) -> dict[str, Any]:
    """
    V10.7.4 — sincroniza o conceito de "scanner fresco" com o Autopilot.

    Antes, o Painel Mestre usava `processado_em` + limite de 45 min,
    enquanto o Autopilot usa `m15_fetched_at` + limite de 60 min.
    Isso fazia o app mostrar 0/7 mesmo quando o M15 do Autopilot estava fresco.

    Agora:
    - usa m15_fetched_at quando existir;
    - faz fallback para processado_em em registros antigos;
    - usa o mesmo limite de 60 min do Autopilot.
    """
    results = dict((scanner_state or {}).get("resultados", {}) or {})
    raw = results.get(pair, {}) if isinstance(results, dict) else {}
    tec = raw.get("tecnico", {}) if isinstance(raw, dict) else {}

    fresh_ts = raw.get("m15_fetched_at", raw.get("processado_em"))
    age = _minutes_since(fresh_ts)

    # Compatibilidade com registros antigos: o Painel Mestre original tratava
    # timestamp ausente como "não comprovadamente velho". Mantemos isso apenas
    # para legado; quando m15_fetched_at existe, a regra real é <=60 min.
    available = bool(tec.get("disponivel", False))
    fresh = available and (True if age is None else age <= 60.0)

    return {
        "available": available,
        "h4": str((tec.get("h4", {}) or {}).get("status", "—")),
        "h1": str((tec.get("h1", {}) or {}).get("status", "—")),
        "m15": str((tec.get("m15", {}) or {}).get("status", "—")),
        "decision": str(raw.get("decisao", "")),
        "text": str(raw.get("texto", "")),
        "updated_at": str(fresh_ts or ""),
        "age_minutes": age,
        "fresh": fresh,
        "freshness_source": "m15_fetched_at" if raw.get("m15_fetched_at") else "processado_em",
    }


def _technical_score(tech: Mapping[str, Any]) -> float:
    weights = {"h4": 35.0, "h1": 35.0, "m15": 30.0}
    total = 0.0
    for key, weight in weights.items():
        kind = _status_kind(tech.get(key))
        if kind == "GREEN":
            total += weight
        elif kind == "YELLOW":
            total += weight * 0.45
        elif kind == "UNKNOWN":
            total += weight * 0.15
    return float(total)


def _integrated_state(direction: str, context: Mapping[str, Any] | None, tech: Mapping[str, Any]) -> tuple[str, str]:
    if "COMPRA" not in str(direction).upper() and "VENDA" not in str(direction).upper():
        return "⚪ SEM VIÉS", "Motor macro ainda não escolheu compra/venda."
    fresh_ctx, fresh_reason = _context_fresh(context, direction)
    if not fresh_ctx:
        return "⚪ MAPA DESATUALIZADO", fresh_reason
    if not tech.get("available"):
        return "⚪ DADOS PARCIAIS", "Scanner H4/H1/M15 ainda não está completo."
    if tech.get("fresh") is False:
        age = tech.get("age_minutes")
        txt = f"Scanner técnico com {float(age):.0f} min; atualizar M15/scanner." if age is not None else "Scanner técnico desatualizado."
        return "⚪ TÉCNICA DESATUALIZADA", txt

    risk = str(context.get("event_risk", "NORMAL")).upper()
    grade = str(context.get("readiness_grade", "WAIT")).upper()
    adr_used = context.get("adr_used_pct")
    adr_exhausted = False
    try:
        adr_exhausted = float(adr_used) >= 110.0
    except Exception:
        pass

    h4, h1, m15 = (_status_kind(tech.get(x)) for x in ("h4", "h1", "m15"))
    if risk == "ALTO":
        return "🟠 BLOQUEADO EVENTO", "Evento principal muito próximo; preserve o viés, mas não force execução."
    if h4 == "RED" or h1 == "RED":
        return "🔴 CONFLITO", "H4 ou H1 está contra o viés macro."
    if adr_exhausted:
        return "🟡 ESTICADO", "O range diário já consumiu cerca de 110%+ do ADR14; evitar perseguir preço."
    if grade in {"A+", "A"} and h4 == "GREEN" and h1 == "GREEN" and m15 == "GREEN":
        return "🟢 EXECUTÁVEL", "Macro + Market Map + H4/H1 + M15 estão alinhados."
    if grade in {"A+", "A", "B"} and h4 == "GREEN" and h1 == "GREEN" and m15 in {"YELLOW", "UNKNOWN", "RED"}:
        return "🟡 QUASE PRONTO", "Contexto e H4/H1 estão alinhados; falta confirmação M15 limpa."
    return "⚪ AGUARDAR", "Confluência ainda não é suficiente para execução seletiva."


def _state_rank(state: str) -> int:
    if state.startswith("🟢"):
        return 5
    if "QUASE" in state:
        return 4
    if "ESTICADO" in state:
        return 3
    if state.startswith("⚪"):
        return 2
    if state.startswith("🟠"):
        return 1
    return 0


def _age_text(iso: str) -> str:
    if not iso:
        return "—"
    try:
        ts = pd.Timestamp(iso)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        now = pd.Timestamp.now(tz="UTC")
        mins = max(0, int((now - ts).total_seconds() // 60))
        if mins < 60:
            return f"{mins} min"
        return f"{mins/60:.1f} h"
    except Exception:
        return "—"


def build_master_rows(matrix: pd.DataFrame, contexts: Mapping[str, Any], scanner_state: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Pure-ish table assembler, exported for unit tests."""
    rows: list[dict[str, Any]] = []
    if matrix is None or matrix.empty:
        return rows
    for _, mr in matrix.head(7).iterrows():
        pair = str(mr.get("Par", ""))
        direction = str(mr.get("Direção", "⚪ AGUARDAR"))
        macro_score = _safe_float(mr.get("Score final", mr.get("Score", 0)))
        quality = _safe_float(mr.get("Qualidade", 0))
        ctx = dict((contexts or {}).get(pair, {}) or {})
        tech = _scanner_for_pair(scanner_state, pair)
        state, reason = _integrated_state(direction, ctx if ctx else None, tech)
        ready = _safe_float(ctx.get("readiness_score", 0)) if ctx else 0.0
        tech_score = _technical_score(tech) if tech.get("available") else 0.0
        integrated = 0.45 * macro_score + 0.35 * ready + 0.20 * tech_score
        if not ctx:
            integrated *= 0.72
        if not tech.get("available"):
            integrated *= 0.80
        rows.append({
            "Par": pair,
            "Viés": direction.replace("🟢 ", "").replace("🔴 ", "").replace("⚪ ", ""),
            "Score": macro_score,
            "Qualidade": quality,
            "W1": ctx.get("w1_bias", "—") if ctx else "—",
            "D1": ctx.get("d1_bias", "—") if ctx else "—",
            "Gate": ctx.get("readiness_grade", "—") if ctx else "—",
            "Prontidão": ready if ctx else None,
            "ADR usado %": ctx.get("adr_used_pct") if ctx else None,
            "ADR estado": ctx.get("adr_state", "—") if ctx else "—",
            "Liquidez alvo": (
                ctx.get("bsl_name", "") if macro_side(direction) == "ALTISTA" else
                ctx.get("ssl_name", "") if macro_side(direction) == "BAIXISTA" else ""
            ) if ctx else "",
            "H4": tech.get("h4", "—"),
            "H1": tech.get("h1", "—"),
            "M15": tech.get("m15", "—"),
            "Técnica atualizada": "—" if tech.get("age_minutes") is None else f"{float(tech.get('age_minutes')):.0f} min",
            "Estado": state,
            "Motivo": reason,
            "Índice Integrado": round(float(np.clip(integrated, 0, 100)), 1),
            "Market Map atualizado": _age_text(str(ctx.get("updated_at", ""))) if ctx else "—",
            "_rank": _state_rank(state),
        })
    return rows


def render_master_panel(matrix: pd.DataFrame, ranking: pd.DataFrame, api_key: str,
                        macro_context: Mapping[str, Any] | None = None,
                        scanner_state: Mapping[str, Any] | None = None,
                        scanner_refresh_cb: Callable[[], tuple[bool, str]] | None = None,
                        scanner_refresh_remaining: int = 0) -> None:
    st.subheader("🧠 Painel Mestre de Oportunidades — V10.7.5")
    st.caption(
        "Decisão Automática + Macro Market Map + H4/H1/M15 + ADR14 em uma única visão dos 7 pares. "
        "O painel serve para priorização; não transforma índice em probabilidade de lucro."
    )
    st.info(
        "🎯 Novo filtro de volatilidade: ADR14 mede quanto do range diário médio já foi consumido. "
        "Ele ajuda a evitar perseguir movimentos já muito esticados."
    )

    if matrix is None or matrix.empty:
        st.warning("A matriz macro ainda não está disponível nesta execução.")
        return

    state = _load_state()
    contexts = dict(state.get("contexts", {}) or {})
    pairs = [str(x) for x in matrix.head(7)["Par"].tolist()]
    processed = sum(1 for p in pairs if p in contexts)

    top1, top2, top3, top4 = st.columns(4)
    top1.metric("Pares", len(pairs))
    top2.metric("Market Map processado", f"{processed}/{len(pairs)}")
    _scanner_infos_v1022 = {p: _scanner_for_pair(scanner_state, p) for p in pairs}
    _scanner_available_v1022 = sum(bool(v.get("available")) for v in _scanner_infos_v1022.values())
    _scanner_fresh_v1022 = sum(bool(v.get("available")) and bool(v.get("fresh")) for v in _scanner_infos_v1022.values())
    top3.metric(
        "Scanner técnico atual",
        f"{_scanner_fresh_v1022}/{len(pairs)}",
        delta=(f"{_scanner_available_v1022}/{len(pairs)} com dados" if _scanner_available_v1022 != _scanner_fresh_v1022 else None),
    )
    top4.metric("Modo", "SELETIVO")

    now_ts = _time.time()
    last_batch = _safe_float(state.get("last_batch_ts", 0.0))
    remaining = max(0, int(61 - (now_ts - last_batch))) if last_batch else 0
    cursor = int(state.get("cursor", 0) or 0)

    c1, c2, c3 = st.columns([1.35, 1.2, 2.45])
    with c1:
        if st.button("▶️ Atualizar próximo lote (2 pares)", key="v102_master_batch", disabled=(remaining > 0 or not bool(api_key)), width="stretch"):
            # Prioriza pares ausentes ou com Market Map mais antigo.
            def _context_age_minutes_v102(pair_name: str) -> float:
                ctx = dict(contexts.get(pair_name, {}) or {})
                if not ctx:
                    return 10**12
                stamp = ctx.get("updated_at") or ctx.get("candle_m15")
                if not stamp:
                    return 10**12
                try:
                    ts = pd.Timestamp(stamp)
                    if ts.tzinfo is None:
                        ts = ts.tz_localize("UTC")
                    else:
                        ts = ts.tz_convert("UTC")
                    return max(
                        0.0,
                        (pd.Timestamp.now(tz="UTC") - ts).total_seconds() / 60.0,
                    )
                except Exception:
                    return 10**12

            candidates = sorted(
                pairs,
                key=lambda p: (_context_age_minutes_v102(p), -pairs.index(p)),
                reverse=True,
            )[:2]
            errors = []
            for p in candidates:
                row = _matrix_row(matrix, p)
                ctx, err = _build_pair_context(p, row, api_key, dict(macro_context or {}))
                if ctx:
                    contexts[p] = ctx
                else:
                    errors.append(f"{p}: {err}")
            state["contexts"] = contexts
            state["cursor"] = (cursor + len(candidates)) % max(1, len(pairs))
            state["last_batch_ts"] = _time.time()
            ok, save_err = _save_state(state)
            if errors:
                st.warning(" | ".join(errors))
            if not ok:
                st.error("Não foi possível persistir a fila: " + save_err)
            else:
                st.rerun()
    with c2:
        if st.button("🔄 Recarregar painel", key="v102_master_reload", width="stretch"):
            st.rerun()
    with c3:
        if remaining > 0:
            st.warning(f"Aguarde ~{remaining}s antes de outro lote para proteger o limite da Twelve Data.")
        elif not api_key:
            st.warning("CHAVE_TWELVE_DATA ausente: atualização W1/D1/liquidez/ADR indisponível.")
        else:
            st.caption("Cada lote usa até 4 consultas (D1 + M15 para 2 pares), abaixo do limite conservador usado no app.")

    # ---------------------------------------------------------
    # V10.7.5 — Scanner técnico automático + botão manual.
    # O automático verifica periodicamente, mas só consulta a
    # Twelve Data quando o callback encontra par ausente ou
    # técnica vencida. O callback mantém lote de 2 pares e
    # cooldown próprio, preservando o orçamento de API.
    # ---------------------------------------------------------
    st.markdown("#### 🤖 Scanner técnico automático")
    _cooldown_v1022 = max(int(scanner_refresh_remaining or 0), int(remaining or 0))

    _auto_enabled_v1075 = st.toggle(
        "Atualização automática do scanner técnico",
        value=True,
        key="v1075_auto_scanner_enabled",
        help=(
            "Verifica o scanner periodicamente enquanto o AtlasQuant estiver aberto. "
            "Só atualiza pares ausentes ou vencidos e mantém o limite de 2 pares por ciclo."
        ),
    )

    _fragment_factory_v1075 = getattr(st, "fragment", None)
    if (
        _auto_enabled_v1075
        and scanner_refresh_cb is not None
        and bool(api_key)
        and callable(_fragment_factory_v1075)
    ):
        @_fragment_factory_v1075(run_every=AUTO_SCANNER_INTERVAL_SECONDS)
        def _auto_scanner_tick_v1075():
            try:
                _ok_auto_v1075, _msg_auto_v1075 = scanner_refresh_cb()
            except Exception as _exc_auto_v1075:
                _ok_auto_v1075 = False
                _msg_auto_v1075 = f"{type(_exc_auto_v1075).__name__}: {_exc_auto_v1075}"

            st.session_state["v1075_auto_scanner_last"] = (
                bool(_ok_auto_v1075),
                str(_msg_auto_v1075),
                datetime.now().strftime("%H:%M:%S"),
            )

            # Só força um rerun completo quando houve atualização REAL de pares.
            # "Tudo atual" e "aguarde cooldown" não geram loop de reruns.
            if _ok_auto_v1075 and str(_msg_auto_v1075).startswith("Scanner atualizado para:"):
                st.session_state["v1022_scanner_feedback"] = ("success", _msg_auto_v1075)
                st.rerun()

            _kind_auto_v1075 = "🟢" if _ok_auto_v1075 else "🟡"
            st.caption(f"{_kind_auto_v1075} Automático: {_msg_auto_v1075}")

        _auto_scanner_tick_v1075()
    elif _auto_enabled_v1075 and not callable(_fragment_factory_v1075):
        st.caption(
            "Modo automático indisponível nesta versão do Streamlit; o botão manual continua ativo."
        )
    elif _auto_enabled_v1075 and not api_key:
        st.warning("CHAVE_TWELVE_DATA ausente: scanner automático indisponível.")
    elif _auto_enabled_v1075 and scanner_refresh_cb is None:
        st.caption("Atualização automática indisponível nesta execução.")

    _last_auto_v1075 = st.session_state.get("v1075_auto_scanner_last")
    if _last_auto_v1075:
        _ok_last_v1075, _msg_last_v1075, _time_last_v1075 = _last_auto_v1075
        st.caption(
            f"Última checagem automática: {_time_last_v1075} · "
            f"{'OK' if _ok_last_v1075 else 'aguardando'}"
        )

    st.markdown("#### 🔄 Controle manual")
    _s1_v1022, _s2_v1022, _s3_v1022 = st.columns([1.55, 1.25, 2.2])

    with _s1_v1022:
        if st.button(
            "🔄 Atualizar scanner técnico (2 pares)",
            key="v1022_master_refresh_scanner",
            disabled=(scanner_refresh_cb is None or _cooldown_v1022 > 0 or not bool(api_key)),
            width="stretch",
        ):
            try:
                _ok_v1022, _msg_v1022 = scanner_refresh_cb()
            except Exception as _exc_v1022:
                _ok_v1022, _msg_v1022 = False, f"{type(_exc_v1022).__name__}: {_exc_v1022}"

            if _ok_v1022:
                st.session_state["v1022_scanner_feedback"] = ("success", _msg_v1022)
            else:
                st.session_state["v1022_scanner_feedback"] = ("warning", _msg_v1022)
            st.rerun()

    with _s2_v1022:
        if st.button(
            "🔁 Atualizar leitura",
            key="v1022_master_refresh_view",
            width="stretch",
        ):
            st.rerun()

    with _s3_v1022:
        if _cooldown_v1022 > 0:
            st.warning(
                f"Aguarde ~{_cooldown_v1022}s antes de nova consulta para proteger o limite da Twelve Data."
            )
        elif scanner_refresh_cb is None:
            st.caption("Atualização técnica direta indisponível nesta execução.")
        else:
            st.caption(
                f"Automático verifica a cada ~{AUTO_SCANNER_INTERVAL_SECONDS}s. "
                "Só pares ausentes ou com técnica >45 min entram na fila; "
                "cada ciclo consulta no máximo 2 pares (H4 + H1 + M15)."
            )

    _fb_v1022 = st.session_state.pop("v1022_scanner_feedback", None)
    if _fb_v1022:
        _kind_v1022, _txt_v1022 = _fb_v1022
        if _kind_v1022 == "success":
            st.success(_txt_v1022)
        else:
            st.warning(_txt_v1022)

    rows = build_master_rows(matrix, contexts, scanner_state)
    if not rows:
        st.warning("Ainda não há linhas para consolidar.")
        return
    df = pd.DataFrame(rows).sort_values(["_rank", "Índice Integrado", "Score"], ascending=[False, False, False], kind="stable")

    best = df.iloc[0]
    st.markdown("### 🏆 Melhor contexto consolidado agora")
    with st.container(border=True):
        b1, b2, b3 = st.columns(3)
        b1.metric("Par", str(best["Par"]))
        b2.metric("Viés", str(best["Viés"]))
        b3.metric("Estado", str(best["Estado"]))
        b4, b5 = st.columns(2)
        b4.metric("Índice integrado", f"{float(best['Índice Integrado']):.1f}/100")
        b5.metric("Gate", str(best["Gate"]))
        st.caption(
            f"Leitura completa: {best['Par']} · {best['Viés']} · {best['Estado']} · "
            f"Índice {float(best['Índice Integrado']):.1f}/100 · Gate {best['Gate']}"
        )
    best_reason = str(best["Motivo"])
    if str(best["Estado"]).startswith("🟢"):
        st.success(best_reason)
    elif "QUASE" in str(best["Estado"]) or "ESTICADO" in str(best["Estado"]):
        st.warning(best_reason)
    elif str(best["Estado"]).startswith("🔴") or str(best["Estado"]).startswith("🟠"):
        st.error(best_reason)
    else:
        st.info(best_reason)

    with st.expander("ℹ️ Entenda os campos do Painel Mestre", expanded=False):
        h1, h2 = st.columns(2)
        with h1:
            st.markdown(
                "**Score:** força do motor macro.\n\n"
                "**Qualidade:** disponibilidade e confiabilidade das fontes usadas.\n\n"
                "**W1 / D1:** estrutura semanal e diária.\n\n"
                "**Gate:** filtro de seletividade A+ / A / B / WAIT."
            )
        with h2:
            st.markdown(
                "**ADR14:** quanto do range diário médio já foi usado.\n\n"
                "**Liquidez alvo:** BSL/SSL ainda relevante no lado do viés.\n\n"
                "**H4/H1/M15:** confirmação técnica top-down.\n\n"
                "**Índice Integrado:** ranking operacional; NÃO é probabilidade de gain."
            )

    st.markdown("### 🌐 Ranking dos 7 pares")
    show = df[[
        "Par", "Viés", "Score", "Qualidade", "W1", "D1", "Gate",
        "ADR usado %", "Liquidez alvo", "H4", "H1", "M15", "Técnica atualizada", "Estado", "Índice Integrado", "Market Map atualizado"
    ]].copy()
    show["Score"] = pd.to_numeric(show["Score"], errors="coerce").round(0)
    show["Qualidade"] = pd.to_numeric(show["Qualidade"], errors="coerce").round(0)
    show["ADR usado %"] = pd.to_numeric(show["ADR usado %"], errors="coerce").round(1)
    st.dataframe(show, hide_index=True, width="stretch")

    st.caption(
        "Índice Integrado = ranking operacional de Macro + Gate + Técnica. Não é probabilidade de gain. "
        "A ação final continua condicionada a evento, localização, volatilidade e confirmação M15."
    )

    chosen = st.selectbox("🔎 Abrir diagnóstico consolidado do par", df["Par"].tolist(), key="v102_master_pair_detail")
    detail = df[df["Par"] == chosen].iloc[0]
    ctx = dict(contexts.get(chosen, {}) or {})
    tech = _scanner_for_pair(scanner_state, chosen)
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Direção preferencial", str(detail["Viés"]))
    d2.metric("Market Map", f"{ctx.get('readiness_grade','—')} · {_safe_float(ctx.get('readiness_score',0)):.0f}/100" if ctx else "—")
    d3.metric("ADR14 usado", f"{_safe_float(ctx.get('adr_used_pct',0)):.1f}%" if ctx.get("adr_used_pct") is not None else "—")
    d4.metric("Risco de evento", str(ctx.get("event_risk", "—")) if ctx else "—")

    if ctx:
        # Renderiza o diagnóstico dinâmico em um único nó HTML estável.
        # Em reruns rápidos do Streamlit, o bloco Sweep pode aparecer/desaparecer.
        # Manter sempre as mesmas três linhas evita reconciliação React inconsistente
        # (NotFoundError/removeChild) sem alterar nenhum cálculo do Painel Mestre.
        if ctx.get("latest_sweep"):
            try:
                ny_time = pd.Timestamp(ctx.get("latest_sweep_time")).tz_convert(NY_TZ).strftime("%d/%m %H:%M NY")
            except Exception:
                ny_time = "horário indisponível"
            sweep_text = (
                f"{ctx.get('latest_sweep')} em {ctx.get('latest_sweep_level') or 'nível'} "
                f"({_fmt_price(ctx.get('latest_sweep_price'), chosen)}) · {ny_time} · "
                f"{ctx.get('latest_sweep_rejection','')}."
            )
        else:
            sweep_text = "Nenhum sweep recente confirmado para este contexto."

        topdown_text = (
            f"W1 {ctx.get('w1_bias','—')} ({ctx.get('w1_regime','—')}) · "
            f"D1 {ctx.get('d1_bias','—')} ({ctx.get('d1_regime','—')}) · "
            f"Localização {ctx.get('location','—')} · Killzone {ctx.get('killzone','—')}."
        )
        volatility_text = (
            f"{ctx.get('adr_state','—')} · ADR14 consumido "
            f"{_safe_float(ctx.get('adr_used_pct',0)):.1f}%."
        )
        st.markdown(
            (
                '<div class="atlas-master-diagnostic" translate="no">'
                f'<div><strong>Top-down:</strong> {html.escape(topdown_text)}</div>'
                f'<div><strong>Sweep:</strong> {html.escape(sweep_text)}</div>'
                f'<div><strong>Volatilidade:</strong> {html.escape(volatility_text)}</div>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )
    st.markdown(
        f"**Técnica:** H4 {tech.get('h4','—')} · H1 {tech.get('h1','—')} · M15 {tech.get('m15','—')}."
    )

    side = macro_side(str(detail["Viés"]))
    if side == "ALTISTA":
        alt = "Cenário alternativo vendedor só ganha prioridade se W1/D1 perderem a estrutura de alta e o motor macro também deixar de favorecer compra."
    elif side == "BAIXISTA":
        alt = "Cenário alternativo comprador só ganha prioridade se W1/D1 perderem a estrutura de baixa e o motor macro também deixar de favorecer venda."
    else:
        alt = "Sem cenário alternativo operacional enquanto o motor macro não definir um lado."
    st.info("🔁 " + alt)

    with st.expander("ℹ️ Por que ADR/ATR entrou e RSI/MACD não entrou no Gate"):
        st.markdown(
            "O app já usa estrutura, EMAs, macro, liquidez e timing. RSI/MACD acrescentariam sinais muito correlacionados ao preço e poderiam aumentar ruído/overfitting. "
            "O **ADR14** responde a outra pergunta: *o movimento de hoje já gastou grande parte do range que normalmente percorre?* "
            "Por isso ele funciona melhor aqui como filtro contra perseguição de preço, sem mudar o Score Mestre."
        )