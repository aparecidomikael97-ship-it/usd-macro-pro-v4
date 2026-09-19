"""Streamlit UI + data access for USD Macro Pro V10.2 Professional Macro Market Map.

The module is additive/observational: it reads the existing macro matrix and
adds W1/D1 context, liquidity, Quarterly Theory time scaffolding, ICT-style
killzones and an ADR14 exhaustion filter.  It does not mutate Score Mestre or the existing signal history.
"""
from __future__ import annotations

import base64
import io
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
from twelve_cache_v1108 import cached_series, clear_shared_cache
from atlasquant_runtime_store import resolve_runtime_branch

from market_map_core_v10 import (
    NY_TZ,
    adr_context,
    aggregate_ohlc,
    alignment_summary,
    macro_regime_summary,
    setup_readiness,
    completed_daily,
    equal_liquidity_levels,
    intraday_open_context,
    killzone_state,
    liquidity_rows,
    macro_side,
    nearest_liquidity,
    normalize_ohlc,
    ny_midnight_open,
    premium_discount,
    prior_period_levels,
    quarterly_clock,
    recent_sweeps,
    session_range,
    trend_context,
)

MARKET_MAP_DATA_PATH = "dados/market_map_v10.csv"


def _td_series(symbol: str, interval: str, outputsize: int, _api_key: str):
    return cached_series(symbol,interval,outputsize)
_td_series.clear = clear_shared_cache


def _matrix_row(matrix: pd.DataFrame, pair: str) -> dict:
    if matrix is None or matrix.empty:
        return {}
    found = matrix[matrix["Par"].astype(str) == str(pair)]
    return found.iloc[0].to_dict() if not found.empty else {}


def _fmt_price(value, pair: str) -> str:
    try:
        n = float(value)
    except Exception:
        return "—"
    return f"{n:.3f}" if "JPY" in pair else f"{n:.5f}"


def _icon_bias(bias: str) -> str:
    return "🟢" if bias == "ALTISTA" else "🔴" if bias == "BAIXISTA" else "⚪"


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


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


def _save_snapshot(snapshot: dict) -> tuple[bool, str, bool]:
    """Persist one observational Market Map snapshot, isolated from signal history."""
    token, repo, branch = _gh_config()
    if not token or not repo:
        return False, "GitHub persistente não configurado.", False
    url = f"https://api.github.com/repos/{repo}/contents/{MARKET_MAP_DATA_PATH}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        current = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
        sha = ""
        if current.status_code == 200:
            payload = current.json()
            sha = payload.get("sha", "")
            raw = base64.b64decode(payload.get("content", ""))
            df = pd.read_csv(io.BytesIO(raw)) if raw else pd.DataFrame()
        elif current.status_code == 404:
            df = pd.DataFrame()
        else:
            current.raise_for_status()
            df = pd.DataFrame()

        snap_id = str(snapshot.get("snapshot_id", ""))
        if not df.empty and "snapshot_id" in df.columns and snap_id in set(df["snapshot_id"].astype(str)):
            return True, "Leitura deste candle M15 já registrada.", False

        df = pd.concat([df, pd.DataFrame([snapshot])], ignore_index=True)
        put_payload = {
            "message": "V10: registra snapshot observacional do Market Map",
            "content": base64.b64encode(df.to_csv(index=False).encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            put_payload["sha"] = sha
        saved = requests.put(url, headers=headers, json=put_payload, timeout=25)
        saved.raise_for_status()
        return True, "Snapshot salvo em dados/market_map_v10.csv.", True
    except Exception as exc:
        return False, f"Falha ao salvar snapshot: {type(exc).__name__}: {exc}", False


def render_market_map(matrix: pd.DataFrame, ranking: pd.DataFrame, api_key: str, macro_context: dict | None = None) -> None:
    st.subheader("🧭 Professional Macro Market Map — V10.2")
    st.caption(
        "Macro semanal → Macro do dia → W1 → D1 → Quarterly → Liquidez → Killzones → H4/H1/M15. "
        "Camada de seleção e contexto: não altera o Score Mestre nem o histórico oficial da V9.3.9.2."
    )
    st.info(
        "🎯 A V10.2 ficou mais seletiva: ela procura confluência e também procura motivos para NÃO entrar. "
        "O Índice de Prontidão é um filtro operacional, não uma probabilidade de lucro."
    )

    if matrix is None or matrix.empty:
        st.warning("A Matriz Inteligente ainda não está disponível nesta execução.")
        return

    pairs = [str(x) for x in matrix["Par"].tolist()]
    pair = st.selectbox("Par para leitura profissional", pairs, index=0, key="v102_market_map_pair")

    ctrl1, ctrl2, ctrl3 = st.columns([1.1, 1.2, 1.2])
    user_tz = ctrl1.selectbox(
        "Fuso de exibição",
        ["America/Cuiaba", "America/Sao_Paulo", "America/New_York", "UTC"],
        index=0,
        key="v102_market_map_tz",
    )
    anchor_label = ctrl2.selectbox(
        "Âncora Quarterly",
        ["00:00 NY", "18:00 NY"],
        index=0,
        key="v102_quarter_anchor",
        help="Há variações públicas da Quarterly Theory. A âncora fica explícita para evitar regra escondida.",
    )
    anchor_hour = 0 if anchor_label.startswith("00") else 18
    if ctrl3.button("🔄 Atualizar Market Map", width="stretch", key="v102_market_map_refresh"):
        _td_series.clear()
        st.rerun()

    row = _matrix_row(matrix, pair)
    macro_direction = str(row.get("Direção", "⚪ AGUARDAR"))
    macro_score = _safe_float(row.get("Score final", row.get("Score", 0)))
    quality = _safe_float(row.get("Qualidade", 0))
    rank_index = _safe_float(row.get("Índice ranking", row.get("Índice operacional", 0)))
    macro_context = dict(macro_context or {})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Direcional macro", macro_direction.replace("🟢 ", "").replace("🔴 ", "").replace("⚪ ", ""))
    m2.metric("Score macro", f"{macro_score:.0f}/100")
    m3.metric("Qualidade", f"{quality:.0f}%")
    m4.metric("Índice base", f"{rank_index:.1f}/100")

    # -----------------------------------------------------
    # 0 — MACRO REGIME: usa apenas informações do motor base
    # -----------------------------------------------------
    regime = macro_regime_summary(pair, macro_direction, macro_score, quality, macro_context)
    st.markdown("### 0️⃣ Leitura Macro Semanal & do Dia")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Regime macro semanal", regime["weekly_label"])
    r2.metric("Consistência com o viés", f"{regime['consistency']:.0f}/100")
    r3.metric("Impulso macro recente", regime["recent_label"])
    r4.metric("Risco de evento", regime["event_risk"]["level"])
    st.caption("Consistência mede concordância entre os blocos do próprio sistema; não é taxa de acerto nem probabilidade estatística.")

    if regime["components"]:
        macro_rows = []
        for item in regime["components"]:
            status = "🟢 CONFIRMA" if item["ok"] is True else "🔴 CONTRA" if item["ok"] is False else "⚪ NEUTRO"
            macro_rows.append({
                "Bloco": item["name"],
                "Leitura": item["detail"],
                "Relação com o viés": status,
                "Peso explicativo": f"{item['weight']:.0f}%",
            })
        st.dataframe(pd.DataFrame(macro_rows), hide_index=True, width="stretch")
    risk_level = regime["event_risk"]["level"]
    if risk_level in {"ALTO", "ELEVADO"}:
        st.warning("📅 " + regime["event_risk"]["text"])
    else:
        st.info("📅 " + regime["event_risk"]["text"])

    if not api_key:
        st.warning("CHAVE_TWELVE_DATA ausente: a leitura macro funciona, mas W1/D1/liquidez ficam indisponíveis.")
        return

    with st.spinner(f"Montando W1/D1 e mapa de liquidez de {pair}..."):
        daily, err_d = _td_series(pair, "1day", 320, api_key)
        m15, err_m = _td_series(pair, "15min", 500, api_key)

    if err_d:
        st.error(f"D1: {err_d}")
    if err_m:
        st.error(f"M15: {err_m}")
    if daily.empty or m15.empty:
        st.warning("Não foi possível montar a leitura completa agora. O motor macro original continua funcionando normalmente.")
        return

    now_ny = datetime.now(NY_TZ)
    today_ny = now_ny.date()
    d_closed = completed_daily(daily, today_ny)
    weekly = aggregate_ohlc(d_closed, "W-FRI")
    weekly_ctx = trend_context(weekly)
    daily_ctx = trend_context(d_closed)
    current_price = float(m15.iloc[-1]["close"])
    last_m15 = pd.Timestamp(m15.iloc[-1]["datetime"])
    adr = adr_context(daily, m15, now_ny, length=14)
    opens = intraday_open_context(m15, now_ny)

    st.markdown("### 1️⃣ Direcional semanal e diário")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("W1", f"{_icon_bias(weekly_ctx['bias'])} {weekly_ctx['bias']}", f"Contexto {weekly_ctx['score']:.0f}/100")
    c2.metric("Estrutura W1", f"{weekly_ctx['structure']['high_state']} / {weekly_ctx['structure']['low_state']}", weekly_ctx['structure'].get('regime','—'))
    c3.metric("D1", f"{_icon_bias(daily_ctx['bias'])} {daily_ctx['bias']}", f"Contexto {daily_ctx['score']:.0f}/100")
    c4.metric("Estrutura D1", f"{daily_ctx['structure']['high_state']} / {daily_ctx['structure']['low_state']}", daily_ctx['structure'].get('regime','—'))
    st.caption(
        f"W1: {weekly_ctx['reason']} · confirmação {weekly_ctx.get('confirmation','—')}\n\n"
        f"D1: {daily_ctx['reason']} · confirmação {daily_ctx.get('confirmation','—')}"
    )

    levels = prior_period_levels(daily, today_ny)
    levels.update(equal_liquidity_levels(d_closed))
    asia = session_range(m15, now_ny)
    if asia.get("available"):
        levels["Asia High"] = asia["high"]
        levels["Asia Low"] = asia["low"]
    midnight = ny_midnight_open(m15, now_ny)
    if midnight is not None:
        levels["NY Midnight Open"] = midnight

    st.markdown("### 2️⃣ Mapa de liquidez semântico")
    pwh, pwl = levels.get("PWH"), levels.get("PWL")
    pd_loc = premium_discount(current_price, pwl, pwh)
    bsl, ssl = nearest_liquidity(current_price, levels)
    liq = liquidity_rows(current_price, levels, pair)

    if pd_loc["position"] is None:
        loc_delta = "Sem PWH/PWL"
    elif pd_loc["zone"] == "ACIMA DO RANGE":
        loc_delta = f"Expansão +{pd_loc['expansion_pct']:.1f}%"
    elif pd_loc["zone"] == "ABAIXO DO RANGE":
        loc_delta = f"Expansão -{pd_loc['expansion_pct']:.1f}%"
    else:
        loc_delta = f"{pd_loc['position']:.0f}% do range"

    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Preço M15", _fmt_price(current_price, pair), f"Candle {last_m15.strftime('%d/%m %H:%M UTC')}")
    l2.metric("Localização semanal", pd_loc["zone"], loc_delta)
    l3.metric("BSL disponível", f"{bsl[0]} · {_fmt_price(bsl[1], pair)}" if bsl else "—")
    l4.metric("SSL disponível", f"{ssl[0]} · {_fmt_price(ssl[1], pair)}" if ssl else "—")

    v1, v2, v3, v4 = st.columns(4)
    v1.metric("ADR14", _fmt_price(adr.get("adr"), pair) if adr.get("adr") is not None else "—")
    v2.metric("Range diário consumido", f"{float(adr['used_pct']):.1f}%" if adr.get("used_pct") is not None else "—", adr.get("state", "SEM DADOS"))
    v3.metric("NY Day Open", _fmt_price(opens.get("day_open"), pair) if opens.get("day_open") is not None else "—")
    v4.metric("Week Open", _fmt_price(opens.get("week_open"), pair) if opens.get("week_open") is not None else "—")
    st.caption("ADR14 é um filtro de volatilidade/exaustão. Ele não define direção e não altera o Score Mestre.")

    if liq:
        df_liq = pd.DataFrame(liq)
        df_liq["Preço"] = df_liq["Preço"].map(lambda x: _fmt_price(x, pair))
        df_liq["Distância (pips)"] = df_liq["Distância (pips)"].map(lambda x: round(float(x), 1))
        st.dataframe(df_liq, hide_index=True, width="stretch")

    sweeps = recent_sweeps(m15, levels, bars=16)
    if sweeps:
        latest = sweeps[0]
        _sweep_ts = pd.Timestamp(latest["datetime"])
        _sweep_ny = _sweep_ts.tz_convert(NY_TZ).strftime("%d/%m %H:%M NY")
        _pip = 0.01 if "JPY" in pair else 0.0001
        _excess_pips = float(latest.get("excess_abs", 0.0) or 0.0) / _pip
        st.warning(
            f"💧 Sweep recente: **{latest['type']} em {latest['level']}** · "
            f"nível {_fmt_price(latest['price'], pair)} · {_sweep_ny} · "
            f"excesso {_excess_pips:.1f} pips · {latest.get('rejection','fechamento de volta')}"
        )
        latest_sweep = str(latest["type"])
    else:
        st.info("💧 Nenhum sweep semântico confirmado nos últimos 16 candles M15.")
        latest_sweep = ""

    st.markdown("### 3️⃣ Quarterly Theory · mapa temporal")
    quarter = quarterly_clock(now_ny, anchor_hour=anchor_hour)
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Quarter atual", f"Q{quarter['quarter']}")
    q2.metric("Fase operacional", quarter["phase"].split(" · ", 1)[-1])
    q3.metric("Micro-quarter", f"q{quarter['micro']} · 90 min")
    q4.metric("Hora NY", quarter["now_ny"].strftime("%H:%M"))
    st.caption(
        f"Q{quarter['quarter']}: {quarter['quarter_start'].strftime('%H:%M')}–{quarter['quarter_end'].strftime('%H:%M')} NY · "
        f"q{quarter['micro']}: {quarter['micro_start'].strftime('%H:%M')}–{quarter['micro_end'].strftime('%H:%M')} NY. "
        "Quarterly é uma moldura temporal heurística; não obriga o preço a seguir uma sequência."
    )

    st.markdown("### 4️⃣ ICT Killzones")
    kz = killzone_state(now_ny)
    active = kz.get("active")
    nxt = kz.get("next")
    if active:
        st.success(f"⏰ **ATIVA: {active['name']}** · {active['start'].strftime('%H:%M')}–{active['end'].strftime('%H:%M')} New York")
    elif nxt:
        minutes = max(0, int((nxt["start"] - kz["now_ny"]).total_seconds() // 60))
        st.info(f"Próxima janela: **{nxt['name']}** · {nxt['start'].strftime('%H:%M')}–{nxt['end'].strftime('%H:%M')} NY · em ~{minutes} min")

    zone = ZoneInfo(user_tz)
    kz_rows = []
    for w in kz["windows"]:
        if w["start"].date() != kz["now_ny"].date():
            continue
        kz_rows.append({
            "Janela": w["name"],
            "New York": f"{w['start'].strftime('%H:%M')}–{w['end'].strftime('%H:%M')}",
            user_tz: f"{w['start'].astimezone(zone).strftime('%H:%M')}–{w['end'].astimezone(zone).strftime('%H:%M')}",
            "Status": "🟢 ATIVA" if active and w["name"] == active["name"] else "—",
        })
    if kz_rows:
        st.dataframe(pd.DataFrame(kz_rows), hide_index=True, width="stretch")

    # -----------------------------------------------------
    # 5 — STRICT READINESS GATE
    # -----------------------------------------------------
    st.markdown("### 5️⃣ Gate de Alta Seletividade")
    readiness = setup_readiness(
        macro_direction, macro_score, quality,
        weekly_ctx, daily_ctx,
        pd_loc["zone"], latest_sweep, bool(active),
        regime["event_risk"]["level"],
    )
    g1, g2, g3 = st.columns(3)
    g1.metric("Índice de Prontidão", f"{readiness['score']:.0f}/100")
    g2.metric("Classe", readiness["grade"])
    g3.metric("Ação", readiness["action"])
    st.caption("⚠️ Prontidão = seletividade do checklist atual. Não é probabilidade de gain e não foi calibrada como taxa de acerto.")

    gate_rows = []
    for item in readiness["checks"]:
        status = "🟢 PASSA" if item["ok"] is True else "🔴 FALHA" if item["ok"] is False else "⚪ SEM DADO"
        gate_rows.append({"Filtro": item["name"], "Status": status, "Detalhe": item["detail"], "Peso": f"{item['weight']:.0f}%"})
    st.dataframe(pd.DataFrame(gate_rows), hide_index=True, width="stretch")

    st.markdown("### 6️⃣ Leitura integrada · narrativa profissional")
    align = alignment_summary(
        macro_direction, weekly_ctx["bias"], daily_ctx["bias"],
        pd_zone=pd_loc["zone"], latest_sweep=latest_sweep, killzone_active=bool(active),
    )
    a1, a2, a3 = st.columns(3)
    a1.metric("Alinhamento contextual", align["label"])
    a2.metric("Checklist contextual", f"{align['passed']}/{align['total']}")
    a3.metric("Lado macro", macro_side(macro_direction))

    macro_bias = macro_side(macro_direction)
    weekly_match = weekly_ctx["bias"] == macro_bias and macro_bias != "NEUTRO"
    daily_match = daily_ctx["bias"] == macro_bias and macro_bias != "NEUTRO"
    target = bsl if macro_bias == "ALTISTA" else ssl if macro_bias == "BAIXISTA" else None
    opposing = ssl if macro_bias == "ALTISTA" else bsl if macro_bias == "BAIXISTA" else None

    st.markdown("#### 🧠 Narrativa do mercado")
    narrative = [
        f"**Macro semanal:** {macro_direction} · Score {macro_score:.0f}/100 · Qualidade {quality:.0f}% · regime {regime['weekly_label']} ({regime['consistency']:.0f}/100 de consistência).",
        f"**Macro do dia:** impulso recente {regime['recent_label']} · risco de evento {regime['event_risk']['level']}. {regime['event_risk']['text']}",
        f"**Top-down:** W1 {_icon_bias(weekly_ctx['bias'])} {weekly_ctx['bias']} ({weekly_ctx['structure'].get('regime','—')}) e D1 {_icon_bias(daily_ctx['bias'])} {daily_ctx['bias']} ({daily_ctx['structure'].get('regime','—')}). " + ("Os dois confirmam o lado macro." if weekly_match and daily_match else "Ainda não há confirmação limpa de W1 + D1 com a macro."),
    ]
    if pd_loc["zone"] in {"ACIMA DO RANGE", "ABAIXO DO RANGE"}:
        narrative.append(f"**Localização:** {pd_loc['zone']} da semana anterior · expansão {pd_loc['expansion_pct']:.1f}%. Evitar tratar isso como simples premium/discount.")
    elif pd_loc["zone"] != "INDEFINIDO":
        narrative.append(f"**Localização:** {pd_loc['zone']} · posição {pd_loc['position']:.0f}% dentro do range da semana anterior.")
    else:
        narrative.append("**Localização:** range semanal anterior ainda não disponível.")
    if target:
        narrative.append(f"**Draw on liquidity:** {target[0]} em {_fmt_price(target[1], pair)} é a liquidez disponível no lado do viés.")
    else:
        narrative.append("**Draw on liquidity:** não há pool semântico disponível à frente no lado do viés neste snapshot.")
    if opposing:
        narrative.append(f"**Liquidez oposta:** {opposing[0]} em {_fmt_price(opposing[1], pair)} é referência do lado contrário.")
    if latest_sweep:
        _nys = pd.Timestamp(latest["datetime"]).tz_convert(NY_TZ).strftime("%H:%M NY") if sweeps else "—"
        narrative.append(
            f"**Sweep:** {latest_sweep} em {latest.get('level','—')} ({_fmt_price(latest.get('price'), pair)}) · {_nys} · {latest.get('rejection','rejeição confirmada')}."
        )
    if adr.get("used_pct") is not None:
        narrative.append(f"**Volatilidade:** {adr.get('state','—')} · o dia consumiu {float(adr['used_pct']):.1f}% do ADR14.")
    narrative.append(f"**Tempo:** {quarter['phase']} · micro q{quarter['micro']} · " + (f"{active['name']} ativa." if active else "fora de killzone."))
    narrative.append(f"**Gate:** classe {readiness['grade']} · {readiness['score']:.0f}/100 de prontidão · {readiness['action']}.")
    for item in narrative:
        st.markdown(f"- {item}")

    if readiness["grade"] == "A+":
        st.success("📌 Plano: contexto muito seletivo. Ainda assim, H4/H1 devem localizar o pullback e o M15 precisa confirmar o gatilho final antes da execução.")
    elif readiness["grade"] == "A":
        st.success("📌 Plano: contexto forte, mas não completo. Não antecipar: exigir H4/H1 + confirmação M15.")
    elif readiness["grade"] == "B":
        st.warning("📌 Plano: há confluência parcial. Esperar melhora de localização, sweep, killzone ou estrutura antes de considerar execução.")
    else:
        st.error("📌 Plano: NÃO FORÇAR ENTRADA. O objetivo do Gate é filtrar operações quando o contexto não está suficientemente limpo.")

    st.divider()
    st.markdown("### 🧪 Registro observacional V10.2")
    st.caption(
        "O contexto é salvo em CSV separado para medir depois se Macro Semanal/Dia + W1/D1 + liquidez + timing + Gate realmente melhoram os resultados. "
        "O histórico oficial do motor base continua separado."
    )
    m15_candle = pd.Timestamp(m15.iloc[-1]["datetime"])
    snapshot = {
        "snapshot_id": f"{pair}|{m15_candle.floor('15min').isoformat()}",
        "registrado_em": pd.Timestamp.utcnow().isoformat(),
        "par": pair,
        "candle_m15": m15_candle.isoformat(),
        "preco": current_price,
        "macro_direcao": macro_direction,
        "macro_score": macro_score,
        "qualidade": quality,
        "macro_regime_semanal": regime["weekly_label"],
        "macro_consistencia": regime["consistency"],
        "macro_impulso_recente": regime["recent_label"],
        "risco_evento": regime["event_risk"]["level"],
        "w1_bias": weekly_ctx["bias"],
        "w1_score": weekly_ctx["score"],
        "w1_estrutura": weekly_ctx["structure"].get("regime", ""),
        "d1_bias": daily_ctx["bias"],
        "d1_score": daily_ctx["score"],
        "d1_estrutura": daily_ctx["structure"].get("regime", ""),
        "quarter": f"Q{quarter['quarter']}",
        "micro_quarter": f"q{quarter['micro']}",
        "quarter_anchor_ny": anchor_hour,
        "killzone": active["name"] if active else "FORA",
        "premium_discount": pd_loc["zone"],
        "nearest_bsl": bsl[0] if bsl else "",
        "nearest_ssl": ssl[0] if ssl else "",
        "latest_sweep": latest_sweep,
        "latest_sweep_level": latest.get("level", "") if sweeps else "",
        "latest_sweep_time": pd.Timestamp(latest["datetime"]).isoformat() if sweeps else "",
        "adr14": adr.get("adr"),
        "adr_used_pct": adr.get("used_pct"),
        "adr_state": adr.get("state", ""),
        "day_open": opens.get("day_open") if opens.get("available") else None,
        "week_open": opens.get("week_open") if opens.get("available") else None,
        "alinhamento": align["label"],
        "alinhamento_passou": align["passed"],
        "alinhamento_total": align["total"],
        "readiness_score": readiness["score"],
        "readiness_grade": readiness["grade"],
        "versao": "V10.2 Professional Macro Market Map",
    }
    if st.button("💾 Registrar leitura atual do Market Map", key="v102_save_snapshot", width="stretch"):
        ok, msg, created = _save_snapshot(snapshot)
        if ok and created:
            st.success(msg)
        elif ok:
            st.info(msg)
        else:
            st.error(msg)

    with st.expander("ℹ️ Regras, tecnologia e limites desta camada"):
        st.markdown(
            """
- **Macro semanal/do dia:** reaproveita somente dados já calculados pelo motor base (USD, Fed, tendência macro, surpresas, FOMC e próximo evento). Não cria dado que a fonte não forneceu.
- **W1/D1:** EMA20/EMA50 + inclinação + swings. `HH/LL` é tratado como expansão mista; `LH/HL` como compressão — não como tendência limpa.
- **Liquidez semântica:** máximas (PDH/PWH/PMH/EQH/Asia High) permanecem BSL; mínimas permanecem SSL, mesmo se o preço já tiver cruzado o nível.
- **Liquidez consumida:** um pool que ficou atrás do preço não é reaproveitado como alvo do lado oposto.
- **Premium/Discount:** acima de 100% vira **ACIMA DO RANGE** e abaixo de 0% vira **ABAIXO DO RANGE**, evitando rótulos enganosos.
- **Sweep:** BSL só é varrida por excesso acima + fechamento de volta; SSL só por excesso abaixo + fechamento de volta.
- **Quarterly:** moldura temporal heurística com âncora explícita; não é previsão determinística.
- **Killzones:** ancoradas em `America/New_York`, com horário de verão convertido automaticamente.
- **Gate de Alta Seletividade:** combina qualidade, macro, W1/D1, estrutura, localização, sweep, killzone e risco de evento. É um filtro de prontidão, **não probabilidade de lucro**.
- **Execução:** H4/H1/M15 continuam sendo necessários. A V10.2 não transforma contexto em ordem automática.
- **Motor base:** Score Mestre, direção oficial e histórico 1H/4H/24H permanecem intactos.
            """
        )