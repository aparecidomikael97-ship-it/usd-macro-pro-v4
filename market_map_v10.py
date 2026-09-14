"""Streamlit UI + data access for USD Macro Pro V10 Market Map.

The module is additive/observational: it reads the existing macro matrix and
adds W1/D1 context, liquidity, Quarterly Theory time scaffolding and ICT-style
killzones.  It does not mutate Score Mestre or the existing signal history.
"""
from __future__ import annotations

import base64
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from market_map_core_v10 import (
    NY_TZ,
    aggregate_ohlc,
    alignment_summary,
    completed_daily,
    equal_liquidity_levels,
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


@st.cache_data(ttl=900, show_spinner=False)
def _td_series(symbol: str, interval: str, outputsize: int, _api_key: str) -> tuple[pd.DataFrame, str]:
    if not _api_key:
        return pd.DataFrame(), "CHAVE_TWELVE_DATA ausente."
    try:
        r = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": symbol,
                "interval": interval,
                "outputsize": int(outputsize),
                "apikey": _api_key,
                "timezone": "UTC",
                "format": "JSON",
                "order": "ASC",
            },
            timeout=20,
        )
        if r.status_code != 200:
            return pd.DataFrame(), f"Twelve Data HTTP {r.status_code}."
        js = r.json()
        if isinstance(js, dict) and js.get("status") == "error":
            return pd.DataFrame(), str(js.get("message") or "Erro da Twelve Data.")
        values = js.get("values", []) if isinstance(js, dict) else []
        df = normalize_ohlc(values)
        if df.empty:
            return df, "A Twelve Data não retornou candles OHLC válidos."
        return df, ""
    except Exception as exc:
        return pd.DataFrame(), f"Falha Twelve Data: {type(exc).__name__}."


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
    token = st.secrets.get("GITHUB_TOKEN_HISTORICO", "")
    repo = st.secrets.get("GITHUB_REPO_HISTORICO", "")
    branch = st.secrets.get("GITHUB_BRANCH_HISTORICO", "main")
    return str(token), str(repo), str(branch or "main")


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


def render_market_map(matrix: pd.DataFrame, ranking: pd.DataFrame, api_key: str) -> None:
    st.subheader("🧭 Macro Market Map — V10")
    st.caption(
        "Camada observacional: Macro → W1 → D1 → Quarterly → Liquidez → Killzones → H4/H1/M15. "
        "Não altera o Score Mestre nem o histórico oficial da V9.3.9.2."
    )
    st.info(
        "🎯 Objetivo: transformar o viés macro em uma narrativa top-down. "
        "O mapa organiza contexto e timing; não é probabilidade de lucro."
    )

    if matrix is None or matrix.empty:
        st.warning("A Matriz Inteligente ainda não está disponível nesta execução.")
        return

    pairs = [str(x) for x in matrix["Par"].tolist()]
    pair = st.selectbox("Par para leitura profissional", pairs, index=0, key="v10_market_map_pair")

    ctrl1, ctrl2, ctrl3 = st.columns([1.1, 1.2, 1.2])
    user_tz = ctrl1.selectbox(
        "Fuso de exibição",
        ["America/Cuiaba", "America/Sao_Paulo", "America/New_York", "UTC"],
        index=0,
        key="v10_market_map_tz",
    )
    anchor_label = ctrl2.selectbox(
        "Âncora Quarterly",
        ["00:00 NY", "18:00 NY"],
        index=0,
        key="v10_quarter_anchor",
        help="Há variações públicas da Quarterly Theory. O app deixa a âncora explícita em vez de escondê-la.",
    )
    anchor_hour = 0 if anchor_label.startswith("00") else 18
    if ctrl3.button("🔄 Atualizar Market Map", use_container_width=True, key="v10_market_map_refresh"):
        _td_series.clear()
        st.rerun()

    row = _matrix_row(matrix, pair)
    macro_direction = str(row.get("Direção", "⚪ AGUARDAR"))
    macro_score = _safe_float(row.get("Score final", row.get("Score", 0)))
    quality = _safe_float(row.get("Qualidade", 0))
    rank_index = _safe_float(row.get("Índice ranking", row.get("Índice operacional", 0)))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Direcional macro", macro_direction.replace("🟢 ", "").replace("🔴 ", "").replace("⚪ ", ""))
    m2.metric("Score macro", f"{macro_score:.0f}/100")
    m3.metric("Qualidade", f"{quality:.0f}%")
    m4.metric("Índice base", f"{rank_index:.1f}/100")

    if not api_key:
        st.warning("CHAVE_TWELVE_DATA ausente: o mapa macro aparece, mas W1/D1/liquidez ficam indisponíveis.")
        return

    with st.spinner(f"Montando leitura W1/D1 e mapa de liquidez de {pair}..."):
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

    st.markdown("### 1️⃣ Direcional semanal e diário")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("W1", f"{_icon_bias(weekly_ctx['bias'])} {weekly_ctx['bias']}", f"Contexto {weekly_ctx['score']:.0f}/100")
    c2.metric("Estrutura W1", f"{weekly_ctx['structure']['high_state']} / {weekly_ctx['structure']['low_state']}")
    c3.metric("D1", f"{_icon_bias(daily_ctx['bias'])} {daily_ctx['bias']}", f"Contexto {daily_ctx['score']:.0f}/100")
    c4.metric("Estrutura D1", f"{daily_ctx['structure']['high_state']} / {daily_ctx['structure']['low_state']}")
    st.caption(f"W1: {weekly_ctx['reason']} · D1: {daily_ctx['reason']}")

    levels = prior_period_levels(daily, today_ny)
    levels.update(equal_liquidity_levels(d_closed))
    asia = session_range(m15, now_ny)
    if asia.get("available"):
        levels["Asia High"] = asia["high"]
        levels["Asia Low"] = asia["low"]
    midnight = ny_midnight_open(m15, now_ny)
    if midnight is not None:
        levels["NY Midnight Open"] = midnight

    st.markdown("### 2️⃣ Mapa de liquidez")
    pwh, pwl = levels.get("PWH"), levels.get("PWL")
    pd_loc = premium_discount(current_price, pwl, pwh)
    above, below = nearest_liquidity(current_price, levels)
    liq = liquidity_rows(current_price, levels, pair)

    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Preço M15", _fmt_price(current_price, pair))
    l2.metric("Localização semanal", pd_loc["zone"], f"{pd_loc['position']:.0f}% do range" if pd_loc["position"] is not None else "Sem PWH/PWL")
    l3.metric("BSL mais próxima", f"{above[0]} · {_fmt_price(above[1], pair)}" if above else "—")
    l4.metric("SSL mais próxima", f"{below[0]} · {_fmt_price(below[1], pair)}" if below else "—")

    if liq:
        df_liq = pd.DataFrame(liq)
        df_liq["Preço"] = df_liq["Preço"].map(lambda x: _fmt_price(x, pair))
        df_liq["Distância (pips)"] = df_liq["Distância (pips)"].map(lambda x: round(float(x), 1))
        st.dataframe(df_liq, hide_index=True, use_container_width=True)

    sweeps = recent_sweeps(m15, levels, bars=16)
    if sweeps:
        latest = sweeps[0]
        st.warning(
            f"💧 Sweep recente: **{latest['type']} em {latest['level']}** · "
            f"nível {_fmt_price(latest['price'], pair)} · candle {pd.Timestamp(latest['datetime']).strftime('%d/%m %H:%M UTC')}"
        )
        latest_sweep = str(latest["type"])
    else:
        st.info("💧 Nenhum sweep simples dos níveis mapeados foi confirmado nos últimos 16 candles M15.")
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
        "Os nomes das fases são uma expectativa heurística; preço não é obrigado a seguir a sequência."
    )

    st.markdown("### 4️⃣ ICT Killzones")
    kz = killzone_state(now_ny)
    active = kz.get("active")
    nxt = kz.get("next")
    if active:
        st.success(
            f"⏰ **ATIVA: {active['name']}** · {active['start'].strftime('%H:%M')}–{active['end'].strftime('%H:%M')} New York"
        )
    elif nxt:
        minutes = max(0, int((nxt["start"] - kz["now_ny"]).total_seconds() // 60))
        st.info(
            f"Próxima janela: **{nxt['name']}** · {nxt['start'].strftime('%H:%M')}–{nxt['end'].strftime('%H:%M')} NY · em ~{minutes} min"
        )

    # Display conversion for the user's selected zone, DST-safe via ZoneInfo.
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
        st.dataframe(pd.DataFrame(kz_rows), hide_index=True, use_container_width=True)

    st.markdown("### 5️⃣ Leitura integrada · narrativa profissional")
    align = alignment_summary(
        macro_direction,
        weekly_ctx["bias"],
        daily_ctx["bias"],
        pd_zone=pd_loc["zone"],
        latest_sweep=latest_sweep,
        killzone_active=bool(active),
    )
    a1, a2, a3 = st.columns(3)
    a1.metric("Alinhamento contextual", align["label"])
    a2.metric("Checklist disponível", f"{align['passed']}/{align['total']}")
    a3.metric("Lado macro", macro_side(macro_direction))
    st.caption("Checklist contextual, não probabilidade estatística e não substitui o Score Mestre.")

    check_rows = []
    for name, ok in align["checks"]:
        status = "🟢 SIM" if ok is True else "🔴 NÃO" if ok is False else "⚪ SEM DADO"
        check_rows.append({"Confluência": name, "Status": status})
    st.dataframe(pd.DataFrame(check_rows), hide_index=True, use_container_width=True)

    macro_bias = macro_side(macro_direction)
    weekly_match = weekly_ctx["bias"] == macro_bias and macro_bias != "NEUTRO"
    daily_match = daily_ctx["bias"] == macro_bias and macro_bias != "NEUTRO"
    target = above if macro_bias == "ALTISTA" else below if macro_bias == "BAIXISTA" else None
    opposing = below if macro_bias == "ALTISTA" else above if macro_bias == "BAIXISTA" else None

    st.markdown("#### 🧠 Narrativa do mercado")
    narrative = []
    narrative.append(f"**Macro:** {macro_direction} · Score {macro_score:.0f}/100 · Qualidade {quality:.0f}%.")
    narrative.append(
        f"**Top-down:** W1 {_icon_bias(weekly_ctx['bias'])} {weekly_ctx['bias']} e D1 {_icon_bias(daily_ctx['bias'])} {daily_ctx['bias']}. "
        + ("Os dois confirmam o lado macro." if weekly_match and daily_match else "Ainda não existe alinhamento completo W1 + D1 com a macro.")
    )
    narrative.append(
        f"**Localização:** preço em {pd_loc['zone']} dentro do range da semana anterior."
        if pd_loc["zone"] != "INDEFINIDO" else "**Localização:** range semanal anterior ainda não disponível."
    )
    if target:
        narrative.append(f"**Draw on liquidity:** referência no lado do viés = {target[0]} em {_fmt_price(target[1], pair)}.")
    if opposing:
        narrative.append(f"**Liquidez oposta:** {opposing[0]} em {_fmt_price(opposing[1], pair)} pode funcionar como zona de sweep/invalidação contextual.")
    narrative.append(
        f"**Tempo:** {quarter['phase']} · micro q{quarter['micro']} · "
        + (f"{active['name']} ativa." if active else "fora de killzone neste momento.")
    )
    for item in narrative:
        st.markdown(f"- {item}")

    if macro_bias == "NEUTRO":
        st.warning("📌 Plano: Macro sem lado definido. Não forçar BUY/SELL; esperar a Matriz escolher direção.")
    elif not weekly_match:
        st.warning("📌 Plano: W1 está contra/neutral. Tratar operações no lado macro como antecipação e exigir confirmação mais forte.")
    elif not daily_match:
        st.warning("📌 Plano: W1 apoia a macro, mas D1 ainda não. Esperar correção/sweep + mudança de estrutura antes do M15.")
    elif not active:
        st.info("📌 Plano: Macro + W1 + D1 alinhados. Não perseguir preço fora da janela; esperar liquidez e a próxima killzone.")
    else:
        st.success("📌 Plano: Macro + W1 + D1 alinhados e janela ativa. Agora H4/H1 localizam o pullback e o M15 continua sendo o gatilho final.")

    st.divider()
    st.markdown("### 🧪 Registro observacional V10")
    st.caption(
        "Salva este contexto em um CSV separado. Isso permite provar depois se W1/D1 + liquidez + timing realmente melhoram os resultados, "
        "sem contaminar o histórico oficial do motor base."
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
        "w1_bias": weekly_ctx["bias"],
        "w1_score": weekly_ctx["score"],
        "d1_bias": daily_ctx["bias"],
        "d1_score": daily_ctx["score"],
        "quarter": f"Q{quarter['quarter']}",
        "micro_quarter": f"q{quarter['micro']}",
        "quarter_anchor_ny": anchor_hour,
        "killzone": active["name"] if active else "FORA",
        "premium_discount": pd_loc["zone"],
        "nearest_bsl": above[0] if above else "",
        "nearest_ssl": below[0] if below else "",
        "latest_sweep": latest_sweep,
        "alinhamento": align["label"],
        "alinhamento_passou": align["passed"],
        "alinhamento_total": align["total"],
        "versao": "V10.0 Market Map observacional",
    }
    if st.button("💾 Registrar leitura atual do Market Map", key="v10_save_snapshot", use_container_width=True):
        ok, msg, created = _save_snapshot(snapshot)
        if ok and created:
            st.success(msg)
        elif ok:
            st.info(msg)
        else:
            st.error(msg)

    with st.expander("ℹ️ Regras e limites desta camada"):
        st.markdown(
            """
- **W1/D1:** contexto por EMA20/EMA50 + swings HH/HL/LH/LL; não é previsão isolada.
- **Liquidez:** PDH/PDL, PWH/PWL, PMH/PML, equal highs/lows, Asian Range e NY Midnight Open quando disponíveis.
- **Sweep:** regra objetiva simples: rompe o nível e fecha de volta do outro lado.
- **Quarterly:** divisão temporal em quatro blocos de 6h + micro-blocos de 90 min, com âncora explícita e editável.
- **Killzones:** ancoradas em **America/New_York**, então o horário de verão é convertido automaticamente.
- **Motor base:** nenhum item desta aba altera pesos, Score Mestre, COMPRA/VENDA ou validação 1H/4H/24H da V9.3.9.2.
            """
        )
