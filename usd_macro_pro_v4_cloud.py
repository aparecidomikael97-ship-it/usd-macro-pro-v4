#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🦅 USD Macro Pro — V4 CLOUD
=====================================
✅ Preparada para Streamlit Cloud e uso local
✅ Ranking + EUA + Actual/Forecast/Previous + Pares + Fed + Histórico + Backtest
✅ Fallback automático se APIs falharem
✅ Sem dependência obrigatória do matplotlib
✅ RSS News + NewsAPI como reserva
"""

import math
import os
from datetime import datetime, timedelta
import urllib.parse
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import requests
import streamlit as st

# =========================================================
# CONFIGURAÇÕES GLOBAIS
# =========================================================

APP_VERSION = "4.0 — CLOUD"
HIST_SCORES = "historico_scores_v3.parquet"
HIST_SINAIS = "historico_sinais_v3.parquet"

st.set_page_config(
    page_title="USD Macro Pro — V4 Cloud",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded",
)

MOEDAS = {
    "USD": "Dólar Americano", "EUR": "Euro", "GBP": "Libra Esterlina",
    "JPY": "Iene Japonês", "CHF": "Franco Suíço", "CAD": "Dólar Canadense",
    "AUD": "Dólar Australiano", "NZD": "Dólar Neozelandês", "BRL": "Real Brasileiro",
}

FED_SENS_PADRAO = {
    "USD": +1.00, "JPY": +0.25, "CHF": +0.20, "EUR": -0.10, "GBP": -0.05,
    "CAD": -0.30, "AUD": -0.45, "NZD": -0.45, "BRL": -0.60,
}

# 🔑 Chaves — funciona no Streamlit Cloud (secrets) E localmente (env ou padrão)
CHAVE_FRED = st.secrets.get("CHAVE_FRED", os.getenv("CHAVE_FRED", ""))
CHAVE_NEWSAPI = st.secrets.get("CHAVE_NEWSAPI", os.getenv("CHAVE_NEWSAPI", ""))

FED_IMPACTO_MAX = 18.0

# =========================================================
# BARRA LATERAL — PARÂMETROS AJUSTÁVEIS
# =========================================================

st.sidebar.title("🦅 USD Macro Pro")
st.sidebar.caption(f"Versão {APP_VERSION}")

ESCALA_PROB = st.sidebar.slider(
    "Escala do modelo", 2.0, 30.0, 10.0, 0.5,
    help="Diferença de pontos para ~73% de probabilidade."
)

PESOS = {
    "juros": st.sidebar.slider("Peso — Juros", 0.0, 0.50, 0.20, 0.05),
    "inflacao": st.sidebar.slider("Peso — Inflação", 0.0, 0.50, 0.15, 0.05),
    "pib": st.sidebar.slider("Peso — PIB", 0.0, 0.50, 0.15, 0.05),
    "emprego": st.sidebar.slider("Peso — Emprego", 0.0, 0.50, 0.20, 0.05),
    "atividade": st.sidebar.slider("Peso — Atividade", 0.0, 0.50, 0.20, 0.05),
    "sentimento": st.sidebar.slider("Peso — Sentimento", 0.0, 0.50, 0.10, 0.05),
}

peso_total = sum(PESOS.values())
st.sidebar.caption(f"Soma dos pesos: {peso_total:.2f}")
if abs(peso_total - 1.0) > 0.01:
    st.sidebar.warning("⚠️ A soma ideal dos pesos é 1,00.")

st.sidebar.subheader("Sensibilidade ao Fed")
FED_SENSIBILIDADE = {
    m: st.sidebar.slider(m, -1.0, 1.0, float(FED_SENS_PADRAO[m]), 0.05)
    for m in MOEDAS
}

st.sidebar.divider()
st.sidebar.caption(f"🕒 Atualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
if not CHAVE_FRED:
    st.sidebar.warning("FRED sem chave: alguns dados usarão fallback. Configure CHAVE_FRED em Secrets.")

STATUS_FONTE = {}

# =========================================================
# FUNÇÕES DE CONEXÃO COM APIs
# =========================================================

def _get(url: str, timeout: int = 15):
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None

def _fred_observacoes(series_id: str, limite: int = 24) -> pd.DataFrame:
    if not CHAVE_FRED:
        return pd.DataFrame(columns=["date", "value"])
    url = (
        f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}"
        f"&api_key={CHAVE_FRED}&file_type=json&sort_order=desc&limit={limite}"
    )
    r = _get(url)
    if r is None:
        return pd.DataFrame(columns=["date", "value"])
    try:
        df = pd.DataFrame(r.json().get("observations", []))
        if df.empty: return df
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().sort_values("date")
    except Exception:
        return pd.DataFrame(columns=["date", "value"])

def _fred_ultimo(series_id: str) -> float | None:
    df = _fred_observacoes(series_id, 6)
    return float(df.iloc[-1]["value"]) if not df.empty else None


def _fred_variacao_ultimo_periodo(series_id: str) -> float | None:
    """Retorna a diferença entre as duas observações mais recentes."""
    df = _fred_observacoes(series_id, 6)
    if len(df) < 2:
        return None
    return float(df.iloc[-1]["value"] - df.iloc[-2]["value"])

def _pct_change_12m(series_id: str) -> float | None:
    df = _fred_observacoes(series_id, 20)
    if len(df) < 13: return None
    return (float(df.iloc[-1]["value"]) / float(df.iloc[-13]["value"]) - 1) * 100

def _bcb_ultimo(codigo_sgs: int) -> float | None:
    r = _get(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_sgs}/dados/ultimos/1?formato=json")
    if r is None: return None
    try:
        return float(r.json()[0]["valor"].replace(",", "."))
    except Exception:
        return None

# =========================================================
# SENTIMENTO E NARRATIVA — RSS + NEWSAPI (FALLBACK)
# =========================================================

HAWKISH = ("higher for longer", "inflation remains elevated", "rate hike",
           "hike", "tightening", "restrictive", "not ready to cut", "strong economy")
DOVISH = ("rate cut", "easing", "disinflation", "inflation cooling",
          "weaker labor", "growth slowing", "lower rates")
POSITIVAS = ("strong", "growth", "beat", "surge", "rise", "gain", "alta", "avanço")
NEGATIVAS = ("weak", "recession", "drop", "fall", "selloff", "queda", "crise")

def _rss_titulos(query: str, idioma="en-US", pais="US", ceid="US:en") -> list[str]:
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl={idioma}&gl={pais}&ceid={ceid}"
    r = _get(url)
    if r is None: return []
    try:
        root = ET.fromstring(r.content)
        return [i.findtext("title", "").strip() for i in root.iter("item") if i.findtext("title", "")]
    except Exception:
        return []

def _score_palavras(titulos: list[str], positivas, negativas) -> float:
    if not titulos: return 0.0
    pos = neg = 0
    for t in [x.lower() for x in titulos]:
        pos += sum(1 for w in positivas if w in t)
        neg += sum(1 for w in negativas if w in t)
    return float(np.clip((pos - neg) / max(pos + neg, 1), -1, 1))

@st.cache_data(ttl=1800, show_spinner="Lendo narrativa do Fed...")
def carregar_narrativa_fed() -> dict:
    titulos = _rss_titulos("Federal Reserve OR FOMC OR Powell when:7d")
    forca = _score_palavras(titulos, HAWKISH, DOVISH)
    tom = "Hawkish" if forca > 0.15 else "Dovish" if forca < -0.15 else "Neutro"
    STATUS_FONTE["FED"] = "✅ RSS" if titulos else "⚠️ Sem manchetes"
    return {"tom": tom, "forca": forca, "titulos": titulos[:12]}

@st.cache_data(ttl=1800, show_spinner="Analisando sentimento...")
def sentimento_noticias(nome_moeda: str) -> float:
    titulos = _rss_titulos(f"{nome_moeda} currency when:7d", "pt-BR", "BR", "BR:pt-419")
    if titulos:
        return float(np.clip(50 + 50 * _score_palavras(titulos, POSITIVAS, NEGATIVAS), 0, 100))
    if CHAVE_NEWSAPI:
        try:
            url = (
                f"https://newsapi.org/v2/everything?q={urllib.parse.quote(nome_moeda)}"
                f"&language=pt&from={(datetime.now()-timedelta(days=7)).strftime('%Y-%m-%d')}"
                f"&sortBy=publishedAt&apiKey={CHAVE_NEWSAPI}"
            )
            r = _get(url)
            if r:
                titulos = [a["title"] for a in r.json().get("articles", []) if a.get("title")]
                return float(np.clip(50 + 50 * _score_palavras(titulos, POSITIVAS, NEGATIVAS), 0, 100))
        except Exception:
            pass
    return 50.0

# =========================================================
# DADOS MACRO — EUA E GLOBAIS
# =========================================================

US_FRED = {
    "Fed Funds": "FEDFUNDS", "CPI": "CPIAUCSL", "Core CPI": "CPILFESL",
    "PCE": "PCEPI", "Core PCE": "PCEPILFE", "Payroll": "PAYEMS",
    "Desemprego": "UNRATE", "PIB": "A191RL1Q225SBEA", "Treasury 2Y": "DGS2",
    "Treasury 10Y": "DGS10", "Broad USD Index": "DTWEXBGS",
}

@st.cache_data(ttl=3600, show_spinner="Carregando macro dos EUA...")
def carregar_macro_eua() -> dict:
    fallback = {
        "Fed Funds": 4.25, "CPI YoY": 2.9, "Core CPI YoY": 3.2, "PCE YoY": 2.6,
        "Core PCE YoY": 2.8, "Payroll var. mil": 150.0, "Desemprego": 4.2,
        "PIB": 2.2, "Treasury 2Y": 4.1, "Treasury 10Y": 4.3, "Broad USD Index": 120.0,
    }
    m = {
        "Fed Funds": _fred_ultimo(US_FRED["Fed Funds"]),
        "CPI YoY": _pct_change_12m(US_FRED["CPI"]),
        "Core CPI YoY": _pct_change_12m(US_FRED["Core CPI"]),
        "PCE YoY": _pct_change_12m(US_FRED["PCE"]),
        "Core PCE YoY": _pct_change_12m(US_FRED["Core PCE"]),
        "Payroll var. mil": _fred_variacao_ultimo_periodo(US_FRED["Payroll"]),
        "Desemprego": _fred_ultimo(US_FRED["Desemprego"]),
        "PIB": _fred_ultimo(US_FRED["PIB"]),
        "Treasury 2Y": _fred_ultimo(US_FRED["Treasury 2Y"]),
        "Treasury 10Y": _fred_ultimo(US_FRED["Treasury 10Y"]),
        "Broad USD Index": _fred_ultimo(US_FRED["Broad USD Index"]),
    }
    for k, v in fallback.items():
        if m.get(k) is None or not np.isfinite(m.get(k)):
            m[k] = v
    STATUS_FONTE["US"] = "✅ FRED" if CHAVE_FRED else "⚠️ Fallback"
    return m

FRED_MAP = {
    "USD": ("FEDFUNDS", "CPIAUCSL", "A191RO1Q156NBEA"),
    "EUR": ("ECBDFR", "CP0000EZ19M086NEST", "CLVMNACSCAB1GQEA19"),
    "GBP": ("BOERUKM", "CPALTT01GBM661S", "CLVMNACSCAB1GQUK"),
    "JPY": ("IR3TIB01JPM156N", "CPALTT01JPM661S", "CLVMNACSCAB1GQJP"),
    "CHF": ("IR3TIB01CHM156N", "CPALTT01CHM661S", "CLVMNACSCAB1GQCH"),
    "CAD": ("IR3TIB01CAM156N", "CPALTT01CAM661S", "CLVMNACSCAB1GQCA"),
    "AUD": ("IR3TIB01AUM156N", "CPALTT01AUM661S", "CLVMNACSCAB1GQAU"),
    "NZD": ("IR3TIB01NZM156N", "CPALTT01NZM661S", "CLVMNACSCAB1GQNZ"),
}

@st.cache_data(ttl=3600, show_spinner="Carregando dados globais...")
def carregar_dados_moedas() -> dict:
    demo = {
        "USD": {"juros": 4.25, "inflacao": 2.9, "pib": 2.1},
        "EUR": {"juros": 2.15, "inflacao": 2.1, "pib": 1.4},
        "GBP": {"juros": 4.00, "inflacao": 3.2, "pib": 1.1},
        "JPY": {"juros": 0.25, "inflacao": 2.8, "pib": 0.8},
        "CHF": {"juros": 0.00, "inflacao": 1.2, "pib": 1.5},
        "CAD": {"juros": 3.75, "inflacao": 2.3, "pib": 1.8},
        "AUD": {"juros": 3.35, "inflacao": 2.7, "pib": 1.9},
        "NZD": {"juros": 3.25, "inflacao": 2.5, "pib": 1.6},
        "BRL": {"juros": 10.75, "inflacao": 4.5, "pib": 2.4},
    }
    res = {}
    for m, base in demo.items():
        j = i = p = None
        if m == "BRL":
            j, i, p = _bcb_ultimo(432), _bcb_ultimo(13522), _bcb_ultimo(4380)
        elif m in FRED_MAP and CHAVE_FRED:
            sj, si, sp = FRED_MAP[m]
            j, i, p = _fred_ultimo(sj), _fred_ultimo(si), _fred_ultimo(sp)
        res[m] = {
            "juros": j if j is not None else base["juros"],
            "inflacao": i if i is not None else base["inflacao"],
            "pib": p if p is not None else base["pib"],
            "sentimento": sentimento_noticias(MOEDAS[m]),
        }
        STATUS_FONTE[m] = "✅" if j else "⚠️ Demo"
    return res

# =========================================================
# MOTOR DE CÁLCULO — SCORE, PROBABILIDADE, SURPRESA
# =========================================================

def normalizar(s: pd.Series, inverter: bool = False) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").fillna(0.0)
    res = pd.Series(50.0, index=s.index) if s.max() == s.min() else (s - s.min()) / (s.max() - s.min()) * 100
    return 100 - res if inverter else res

def score_emprego_usd(m: dict) -> float:
    s_pay = np.clip(50 + (m["Payroll var. mil"] - 100) * 0.15, 0, 100)
    s_des = np.clip(50 - (m["Desemprego"] - 4.2) * 15, 0, 100)
    return float((s_pay + s_des) / 2)

def score_inflacao_usd(m: dict) -> float:
    media = np.mean([m["CPI YoY"], m["Core CPI YoY"], m["PCE YoY"], m["Core PCE YoY"]])
    return float(np.clip(50 + (media - 2.0) * 12, 0, 100))


def score_atividade_usd(m: dict) -> float:
    """Baseline neutro. A atividade é refinada pela seção Actual x Forecast."""
    return 50.0

def calcular_ranking(dados: dict, macro_us: dict, fed: dict) -> pd.DataFrame:
    df = pd.DataFrame(dados).T.reset_index().rename(columns={"index": "Código"})
    df["Moeda"] = df["Código"].map(MOEDAS)
    df["n_juros"] = normalizar(df["juros"])
    df["n_inflacao"] = normalizar(df["inflacao"])
    df["n_pib"] = normalizar(df["pib"])
    df["n_sentimento"] = normalizar(df["sentimento"])
    df["n_emprego"] = df["n_atividade"] = 50.0

    idx_usd = df.index[df["Código"] == "USD"]
    if len(idx_usd):
        i = idx_usd[0]
        df.loc[i, "n_inflacao"] = score_inflacao_usd(macro_us)
        df.loc[i, "n_emprego"] = score_emprego_usd(macro_us)
        df.loc[i, "n_atividade"] = score_atividade_usd(macro_us)

    df["Macro_Score"] = (
        PESOS["juros"] * df["n_juros"] + PESOS["inflacao"] * df["n_inflacao"] +
        PESOS["pib"] * df["n_pib"] + PESOS["emprego"] * df["n_emprego"] +
        PESOS["atividade"] * df["n_atividade"] + PESOS["sentimento"] * df["n_sentimento"]
    )
    df["Influência_Fed"] = df["Código"].map(FED_SENSIBILIDADE).fillna(0.0) * fed["forca"] * FED_IMPACTO_MAX
    df["Score_Final"] = (df["Macro_Score"] + df["Influência_Fed"]).clip(0, 100).round(1)
    df = df.sort_values("Score_Final", ascending=False).reset_index(drop=True)
    df["Posição"] = df.index + 1
    return df.round(1)

def probabilidade_modelo(s_base: float, s_cotada: float):
    diff = s_base - s_cotada
    p = 1 / (1 + math.exp(-diff / (ESCALA_PROB / 2)))
    if p >= 0.65: status = "🟢 Forte vantagem da base"
    elif p >= 0.55: status = "🟡 Leve vantagem da base"
    elif p >= 0.45: status = "⚪ Equilíbrio"
    elif p >= 0.35: status = "🟡 Leve vantagem da cotada"
    else: status = "🔴 Forte vantagem da cotada"
    return p, diff, status

# =========================================================
# SURPRESA ECONÔMICA
# =========================================================

def classificar_surpresa(atual, prev, sentido_pos_alto=True, tol=0.0):
    if prev is None or not np.isfinite(prev):
        return {"Surpresa": np.nan, "Score": 0.0, "Classe": "Sem previsão"}
    surp = atual - prev
    if abs(surp) <= tol:
        classe, score = "Neutro", 0.0
    else:
        pos = surp > 0 if sentido_pos_alto else surp < 0
        classe = "USD Favorável" if pos else "USD Desfavorável"
        score = 1.0 if pos else -1.0
    return {"Surpresa": surp, "Score": score, "Classe": classe}

# =========================================================
# HISTÓRICO E BACKTEST
# =========================================================

def salvar_snapshot(df):
    hoje = pd.Timestamp(datetime.now().date())
    snap = df[["Código", "Macro_Score", "Influência_Fed", "Score_Final"]].copy()
    snap["data"] = hoje
    try:
        hist = pd.read_parquet(HIST_SCORES)
        if (pd.to_datetime(hist["data"]).dt.date == hoje.date()).any():
            return "⚠️ Já existe snapshot de hoje."
        hist = pd.concat([hist, snap], ignore_index=True)
    except:
        hist = snap
    hist.to_parquet(HIST_SCORES, index=False)
    return "✅ Snapshot salvo."

def carregar_snapshots():
    try: return pd.read_parquet(HIST_SCORES)
    except: return pd.DataFrame()

def registrar_sinal(par, prob, s_base, s_cotada, preco, horas):
    linha = pd.DataFrame([{
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "data": pd.Timestamp.now(), "par": par, "prob_base": float(prob),
        "score_base": float(s_base), "score_cotada": float(s_cotada),
        "preco_entrada": float(preco), "horizonte": int(horas),
        "preco_saida": np.nan, "resultado": np.nan,
    }])
    try: hist = pd.concat([pd.read_parquet(HIST_SINAIS), linha], ignore_index=True)
    except: hist = linha
    hist.to_parquet(HIST_SINAIS, index=False)

def carregar_sinais():
    try: return pd.read_parquet(HIST_SINAIS)
    except: return pd.DataFrame()

def atualizar_resultado(id_sinal, saida):
    hist = carregar_sinais()
    if hist.empty or id_sinal not in hist["id"].astype(str).values:
        return "Sinal não encontrado."
    m = hist["id"].astype(str) == id_sinal
    entrada = float(hist.loc[m, "preco_entrada"].iloc[0])
    prob = float(hist.loc[m, "prob_base"].iloc[0])
    previsto_alta = prob >= 0.5
    realizado_alta = saida > entrada
    hist.loc[m, "preco_saida"] = saida
    hist.loc[m, "resultado"] = 1.0 if previsto_alta == realizado_alta else 0.0
    hist.to_parquet(HIST_SINAIS, index=False)
    return "✅ Resultado atualizado."

def metricas_backtest(hist):
    val = hist.dropna(subset=["resultado", "prob_base"])
    if val.empty: return None
    acuracia = float(val["resultado"].astype(float).mean())
    p = np.where(val["prob_base"] >= 0.5, val["prob_base"], 1 - val["prob_base"])
    brier = float(np.mean((p - val["resultado"].astype(float)) ** 2))
    return {"n": len(val), "acuracia": acuracia, "brier": brier}

# =========================================================
# EXECUÇÃO PRINCIPAL
# =========================================================

macro_us = carregar_macro_eua()
fed = carregar_narrativa_fed()
dados_moedas = carregar_dados_moedas()
ranking = calcular_ranking(dados_moedas, macro_us, fed)

st.title("🦅 USD Macro Pro — V4 Cloud")
st.caption("Modelo profissional: Dados Econômicos → Inflação → Fed → Força de Moedas → Pares → Backtest")

tom_icon = {"Hawkish":"🔴", "Dovish":"🟢", "Neutro":"⚪"}.get(fed["tom"], "⚪")
st.info(f"Fed: {tom_icon} **{fed['tom']}** | Força: {fed['forca']:+.2f}")

tabs = st.tabs([
    "🏆 Ranking", "🇺🇸 Painel EUA", "💶 Pares & Probabilidade",
    "🏦 Fed & Notícias", "🧾 Histórico", "📈 Backtest"
])

# ═══════════════════════════════════════════════════════════
# ABA 1 — RANKING
# ═══════════════════════════════════════════════════════════
with tabs[0]:
    st.subheader("Força Macro das Moedas")
    tabela = ranking[[
        "Posição", "Código", "Moeda", "Macro_Score", "Influência_Fed",
        "Score_Final", "juros", "inflacao", "pib", "sentimento"
    ]].copy()
    tabela.columns = [
        "#", "Código", "Moeda", "Macro Score", "Fed", "Score Final",
        "Juros %", "Inflação %", "PIB %", "Sentimento"
    ]
    st.dataframe(tabela, use_container_width=True, hide_index=True)

    top3 = ranking.head(3)["Código"].tolist()
    bot3 = ranking.tail(3)["Código"].tolist()
    st.success(f"🏆 Mais Fortes: {', '.join(top3)}")
    st.error(f"📉 Mais Fracas: {', '.join(bot3)}")

    if st.button("💾 Salvar Snapshot"):
        st.toast(salvar_snapshot(ranking))

# ═══════════════════════════════════════════════════════════
# ABA 2 — PAINEL EUA + SURPRESA
# ═══════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("Indicadores dos Estados Unidos")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Fed Funds", f"{macro_us['Fed Funds']:.2f}%")
        st.metric("CPI YoY", f"{macro_us['CPI YoY']:.2f}%")
        st.metric("Core CPI YoY", f"{macro_us['Core CPI YoY']:.2f}%")
    with c2:
        st.metric("PCE YoY", f"{macro_us['PCE YoY']:.2f}%")
        st.metric("Core PCE YoY", f"{macro_us['Core PCE YoY']:.2f}%")
        st.metric("Payroll Δ mensal", f"{macro_us['Payroll var. mil']:.0f} mil")
    with c3:
        st.metric("Desemprego", f"{macro_us['Desemprego']:.2f}%")
        st.metric("PIB", f"{macro_us['PIB']:.2f}%")
        st.metric("Treasury 2Y", f"{macro_us['Treasury 2Y']:.2f}%")
    with c4:
        st.metric("Treasury 10Y", f"{macro_us['Treasury 10Y']:.2f}%")
        st.metric("Broad USD Index", f"{macro_us['Broad USD Index']:.1f}")

    st.markdown("---")
    st.subheader("🎯 Surpresa Econômica — Actual × Previsão")
    st.caption("Digite os valores reais e esperados. O modelo calcula o impacto no USD.")

    indicadores = [
        ("CPI YoY", True), ("Core CPI YoY", True), ("PCE YoY", True),
        ("Core PCE YoY", True), ("Payroll", True), ("Desemprego", False),
        ("ISM Manuf.", True), ("ISM Serviços", True),
    ]
    linhas = []
    for nome, sentido in indicadores:
        cA, cF, cP = st.columns(3)
        with cA:
            actual = st.number_input(f"{nome} — Actual", value=0.0, step=0.1, key=f"act_{nome}")
        with cF:
            forecast = st.number_input(f"{nome} — Forecast", value=0.0, step=0.1, key=f"for_{nome}")
        with cP:
            previous = st.number_input(f"{nome} — Previous", value=0.0, step=0.1, key=f"prev_{nome}")
        r = classificar_surpresa(actual, forecast, sentido)
        linhas.append({
            "Indicador": nome,
            "Actual": actual,
            "Forecast": forecast,
            "Previous": previous,
            "Surpresa vs Forecast": r["Surpresa"],
            "Impacto USD": r["Classe"],
            "Score": r["Score"],
        })

    df_surp = pd.DataFrame(linhas)
    st.dataframe(df_surp, use_container_width=True, hide_index=True)
    total = float(df_surp["Score"].sum())

    if total >= 3: st.success("📈 Fortemente favorável ao USD")
    elif total >= 1: st.success("📈 Levemente favorável ao USD")
    elif total <= -3: st.error("📉 Fortemente desfavorável ao USD")
    elif total <= -1: st.error("📉 Levemente desfavorável ao USD")
    else: st.info("⚪ Surpresas equilibradas")

# ═══════════════════════════════════════════════════════════
# ABA 3 — PARES E PROBABILIDADE
# ═══════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("Análise de Par Cambial")
    moedas = ranking["Código"].tolist()
    c1, c2 = st.columns(2)
    with c1: base = st.selectbox("Moeda Base", moedas, index=moedas.index("EUR") if "EUR" in moedas else 0)
    with c2: cotada = st.selectbox("Moeda Cotada", moedas, index=moedas.index("USD") if "USD" in moedas else 1)

    if base != cotada:
        sb = float(ranking.loc[ranking["Código"]==base, "Score_Final"].iloc[0])
        sc = float(ranking.loc[ranking["Código"]==cotada, "Score_Final"].iloc[0])
        p, diff, status = probabilidade_modelo(sb, sc)

        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col1: st.metric(base, f"{sb:.1f}")
        with col2:
            st.subheader(f"{base}/{cotada}")
            st.markdown(f"### {status}")
            st.progress(float(np.clip(p, 0, 1)))
            st.markdown(f"**{base}**: {p*100:.0f}% · **{cotada}**: {(1-p)*100:.0f}%")
        with col3: st.metric(cotada, f"{sc:.1f}")

        st.caption(f"Diferença: {diff:+.1f} pontos | Escala: {ESCALA_PROB:.1f}")
        st.warning("Probabilidade do modelo ≠ probabilidade estatística comprovada. Use o backtest para calibrar.")

    st.markdown("#### 📝 Registrar Sinal para Backtest")

    preco = st.number_input(
        "Preço de Entrada",
        min_value=0.00001,
        max_value=1000.0,
        value=1.10000,
        step=0.00001,
        format="%.5f",
    )

    h = st.selectbox("Horizonte (horas)", [1, 4, 8, 24, 48, 72], 3)

    if st.button("Registrar Sinal"):
        registrar_sinal(f"{base}/{cotada}", p, sb, sc, preco, h)
        st.success("✅ Sinal registrado!")

# ═══════════════════════════════════════════════════════════
# ABA 4 — FED E NOTÍCIAS
# ═══════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("Narrativa do Federal Reserve")
    st.metric("Tom do Fed", fed["tom"])
    st.metric("Força da Narrativa", f"{fed['forca']:+.2f}")
    st.markdown("### Manchetes Analisadas")
    if fed["titulos"]:
        for t in fed["titulos"]: st.write("•", t)
    else:
        st.info("Nenhuma manchete encontrada nesta atualização.")
    st.markdown("---")
    st.markdown("""
    **🔴 Hawkish** → Inflação alta / economia forte → juros altos por mais tempo → USD sobe
    **🟢 Dovish** → Inflação cedendo / economia fraca → cortes de juros → USD cai
    ⚠️ Leitura auxiliar — confira sempre atas e comunicado oficial do FOMC.
    """)

# ═══════════════════════════════════════════════════════════
# ABA 5 — HISTÓRICO
# ═══════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("Histórico de Rankings")
    st.caption("No Streamlit Community Cloud, arquivos locais podem ser apagados em reinicializações/deploys. Para histórico permanente, use um banco externo.")
    hist = carregar_snapshots()
    if hist.empty:
        st.info("Ainda sem histórico. Salve snapshots na aba 🏆 Ranking.")
    else:
        st.dataframe(hist.sort_values("data", ascending=False), use_container_width=True)

# ═══════════════════════════════════════════════════════════
# ABA 6 — BACKTEST
# ═══════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("📈 Backtest — Validação do Modelo")
    sinais = carregar_sinais()
    if sinais.empty:
        st.info("Nenhum sinal registrado. Registre sinais na aba 💶 Pares.")
    else:
        st.dataframe(sinais.sort_values("data", ascending=False), use_container_width=True)

        abertos = sinais[sinais["resultado"].isna()]
        if not abertos.empty:
            st.markdown("### ✅ Fechar Sinal — Informar Resultado")
            id_sel = st.selectbox("Sinal", abertos["id"].astype(str).tolist())
            saida = st.number_input("Preço de Saída", 0.00001, 1.50000, 1.10000, 0.0001, "%.5f")
            if st.button("Salvar Resultado"):
                st.toast(atualizar_resultado(id_sel, saida))
                st.rerun()

        met = metricas_backtest(sinais)
        if met:
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Trades", met["n"])
            with c2: st.metric("Acurácia", f"{met['acuracia']*100:.1f}%")
            with c3: st.metric("Brier Score", f"{met['brier']:.3f}")
            if met["brier"] < 0.12: st.success("✅ Excelente — Brier < 0.12")
            elif met["brier"] <= 0.20: st.warning("⚠️ Razoável — Brier entre 0.12 e 0.20")
            else: st.error("🔴 Recalibre pesos e escala — Brier alto")

st.divider()
st.caption(f"Fontes: {', '.join(f'{k}:{v}' for k,v in STATUS_FONTE.items())} | Uso educacional. Não é recomendação de investimento.")
