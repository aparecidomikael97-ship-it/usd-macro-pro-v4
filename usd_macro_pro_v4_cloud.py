# ============================================================
# USD MACRO PRO V10.2.1 — ESTABILIDADE VISUAL · PAINEL MESTRE V10.2 · MOTOR BASE V9.3.9.2
# Exibe o motivo persistido de falhas por par/timeframe sem
# gastar novas chamadas. Persistência e validação preservadas.
# ============================================================

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🦅 USD Macro Pro — V6.6 EXPECTATIVA DO MERCADO
================================
- Interface em português
- Corrige unidades de inflação e PIB no ranking global
- Corrige Payroll para variação mensal
- Valida dados absurdos e usa fallback quando necessário
- Corrige limites de preço para pares como USD/JPY
- Mantém painel EUA, surpresa econômica, pares, Fed, histórico e teste histórico
"""

import base64
import json
import math
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
import urllib.parse
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import requests
import streamlit as st
from twelve_cache_v1108 import cached_series, clear_shared_cache
from atlasquant_runtime_store import resolve_runtime_branch
import re

# V10 — camada observacional profissional. O try/except evita derrubar
# o motor base caso o arquivo adicional ainda não tenha sido enviado.
try:
    from pair_intelligence_v110 import render_pair_intelligence_v110
    _PAIR_INTEL_V110_IMPORT_ERROR = ""
except Exception as _pair_intel_exc:
    render_pair_intelligence_v110 = None
    _PAIR_INTEL_V110_IMPORT_ERROR = f"{type(_pair_intel_exc).__name__}: {_pair_intel_exc}"

try:
    from market_map_v10 import render_market_map
    _MARKET_MAP_V10_IMPORT_ERROR = ""
except Exception as _mm_exc:
    render_market_map = None
    _MARKET_MAP_V10_IMPORT_ERROR = f"{type(_mm_exc).__name__}: {_mm_exc}"

try:
    from master_panel_v102 import render_master_panel
    _MASTER_V102_IMPORT_ERROR = ""
except Exception as _master_exc:
    render_master_panel = None
    _MASTER_V102_IMPORT_ERROR = f"{type(_master_exc).__name__}: {_master_exc}"


try:
    from experience_v103 import render_experience_controls, render_experience_hub
    _UX_V103_IMPORT_ERROR = ""
except Exception as _ux_exc:
    render_experience_controls = None
    render_experience_hub = None
    _UX_V103_IMPORT_ERROR = f"{type(_ux_exc).__name__}: {_ux_exc}"


try:
    from product_v104 import render_v104_hub
    _PRODUCT_V104_IMPORT_ERROR = ""
except Exception as _product_exc:
    render_v104_hub = None
    _PRODUCT_V104_IMPORT_ERROR = f"{type(_product_exc).__name__}: {_product_exc}"


try:
    from evolution_v105 import render_v105_center
    _EVOLUTION_V105_IMPORT_ERROR = ""
except Exception as _evolution_exc:
    render_v105_center = None
    _EVOLUTION_V105_IMPORT_ERROR = f"{type(_evolution_exc).__name__}: {_evolution_exc}"


try:
    from atlasquant_shadow_mode import render_shadow_mode_panel
    from atlasquant_shadow_capture import ensure_shadow_hydrated
    _ATLASQUANT_SHADOW_IMPORT_ERROR = ""
except Exception as _shadow_exc:
    render_shadow_mode_panel = None
    ensure_shadow_hydrated = None
    _ATLASQUANT_SHADOW_IMPORT_ERROR = f"{type(_shadow_exc).__name__}: {_shadow_exc}"


try:
    from atlasquant_calibration_lab import render_calibration_lab
    _ATLASQUANT_CALIBRATION_IMPORT_ERROR = ""
except Exception as _calib_exc:
    render_calibration_lab = None
    _ATLASQUANT_CALIBRATION_IMPORT_ERROR = f"{type(_calib_exc).__name__}: {_calib_exc}"


try:
    from atlasquant_performance_lab import render_performance_lab
    _ATLASQUANT_PERFORMANCE_IMPORT_ERROR = ""
except Exception as _perf_exc:
    render_performance_lab = None
    _ATLASQUANT_PERFORMANCE_IMPORT_ERROR = f"{type(_perf_exc).__name__}: {_perf_exc}"


try:
    from atlasquant_backtest_panel import render_operational_backtest_panel
    _ATLASQUANT_BACKTEST_IMPORT_ERROR = ""
except Exception as _backtest_exc:
    render_operational_backtest_panel = None
    _ATLASQUANT_BACKTEST_IMPORT_ERROR = f"{type(_backtest_exc).__name__}: {_backtest_exc}"


try:
    from atlasquant_stability_lab import render_stability_lab
    _ATLASQUANT_STABILITY_IMPORT_ERROR = ""
except Exception as _stability_exc:
    render_stability_lab = None
    _ATLASQUANT_STABILITY_IMPORT_ERROR = f"{type(_stability_exc).__name__}: {_stability_exc}"


try:
    from atlasquant_expansion_budget import render_expansion_budget_planner
    _ATLASQUANT_EXPANSION_BUDGET_IMPORT_ERROR = ""
except Exception as _exp_budget_exc:
    render_expansion_budget_planner = None
    _ATLASQUANT_EXPANSION_BUDGET_IMPORT_ERROR = f"{type(_exp_budget_exc).__name__}: {_exp_budget_exc}"


try:
    from atlasquant_adaptive_coverage import render_adaptive_coverage_plan
    _ATLASQUANT_ADAPTIVE_COVERAGE_IMPORT_ERROR = ""
except Exception as _adaptive_coverage_exc:
    render_adaptive_coverage_plan = None
    _ATLASQUANT_ADAPTIVE_COVERAGE_IMPORT_ERROR = f"{type(_adaptive_coverage_exc).__name__}: {_adaptive_coverage_exc}"


try:
    from atlasquant_validation_readiness import render_validation_readiness
    _ATLASQUANT_VALIDATION_IMPORT_ERROR = ""
except Exception as _validation_exc:
    render_validation_readiness = None
    _ATLASQUANT_VALIDATION_IMPORT_ERROR = f"{type(_validation_exc).__name__}: {_validation_exc}"


try:
    from atlasquant_evidence_bundle import render_validation_evidence
    _ATLASQUANT_EVIDENCE_IMPORT_ERROR = ""
except Exception as _evidence_exc:
    render_validation_evidence = None
    _ATLASQUANT_EVIDENCE_IMPORT_ERROR = f"{type(_evidence_exc).__name__}: {_evidence_exc}"


try:
    from currency_news_v107 import render_currency_news_panel
    _CURRENCY_NEWS_V106_IMPORT_ERROR = ""
except Exception as _currency_news_exc:
    render_currency_news_panel = None
    _CURRENCY_NEWS_V106_IMPORT_ERROR = f"{type(_currency_news_exc).__name__}: {_currency_news_exc}"


try:
    from autopilot_panel_v107 import render_autopilot_v107
    _AUTOPILOT_V107_IMPORT_ERROR = ""
except Exception as _autopilot_exc:
    render_autopilot_v107 = None
    _AUTOPILOT_V107_IMPORT_ERROR = f"{type(_autopilot_exc).__name__}: {_autopilot_exc}"

# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

APP_VERSION = "11.0.8 — STRENGTH ATTRIBUTION + AUDIT INTEGRITY · MOTOR BASE V9.3.9.2"
HIST_SCORES = "historico_scores_v5.parquet"
HIST_SINAIS = "historico_sinais_v5.parquet"

st.set_page_config(
    page_title="AtlasQuant — Market Intelligence Platform · DEV",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from compact_ui_v1107 import apply_compact_theme
apply_compact_theme()

try:
    from atlasquant_ui_v1 import (
        apply_atlasquant_theme,
        render_atlasquant_header,
        navigation_labels,
    )
    _ATLASQUANT_UI_IMPORT_ERROR = ""
    apply_atlasquant_theme()
except Exception as _atlasquant_ui_exc:
    render_atlasquant_header = None
    navigation_labels = None
    _ATLASQUANT_UI_IMPORT_ERROR = f"{type(_atlasquant_ui_exc).__name__}: {_atlasquant_ui_exc}"


try:
    from atlasquant_dashboard_v1 import render_g8_radar
    _ATLASQUANT_DASHBOARD_IMPORT_ERROR = ""
except Exception as _atlasquant_dashboard_exc:
    render_g8_radar = None
    _ATLASQUANT_DASHBOARD_IMPORT_ERROR = (
        f"{type(_atlasquant_dashboard_exc).__name__}: {_atlasquant_dashboard_exc}"
    )


try:
    from atlasquant_coverage_funnel import render_coverage_funnel
    _ATLASQUANT_COVERAGE_IMPORT_ERROR = ""
except Exception as _coverage_exc:
    render_coverage_funnel = None
    _ATLASQUANT_COVERAGE_IMPORT_ERROR = f"{type(_coverage_exc).__name__}: {_coverage_exc}"

MOEDAS = {
    "USD": "Dólar Americano",
    "EUR": "Euro",
    "GBP": "Libra Esterlina",
    "JPY": "Iene Japonês",
    "CHF": "Franco Suíço",
    "CAD": "Dólar Canadense",
    "AUD": "Dólar Australiano",
    "NZD": "Dólar Neozelandês",
    "BRL": "Real Brasileiro",
}

SENSIBILIDADE_FED_PADRAO = {
    "USD": +1.00, "JPY": +0.25, "CHF": +0.20, "EUR": -0.10,
    "GBP": -0.05, "CAD": -0.30, "AUD": -0.45, "NZD": -0.45,
    "BRL": -0.60,
}

CHAVE_FRED = st.secrets.get("CHAVE_FRED", os.getenv("CHAVE_FRED", ""))
CHAVE_NEWSAPI = st.secrets.get("CHAVE_NEWSAPI", os.getenv("CHAVE_NEWSAPI", ""))
CHAVE_EODHD = st.secrets.get("CHAVE_EODHD", os.getenv("CHAVE_EODHD", ""))
CHAVE_TWELVE_DATA = st.secrets.get("CHAVE_TWELVE_DATA", os.getenv("CHAVE_TWELVE_DATA", ""))

IMPACTO_MAX_FED = 18.0
STATUS_FONTE = {}

# =========================================================
# BARRA LATERAL
# =========================================================

if render_experience_controls is not None:
    try:
        _UX_PREFS_V103 = render_experience_controls()
    except Exception as _ux_ctrl_exc:
        _UX_PREFS_V103 = {}
        st.caption(f"UX V10.3 em modo compatível: {type(_ux_ctrl_exc).__name__}")
else:
    _UX_PREFS_V103 = {}

st.sidebar.title("🧭 AtlasQuant")
st.sidebar.caption("Market Intelligence Platform · DEV")
st.sidebar.caption(f"Engine base {APP_VERSION}")

ESCALA_CONFIANCA = st.sidebar.slider(
    "Sensibilidade da comparação", 2.0, 30.0, 10.0, 0.5,
    help="Quanto a diferença de força entre duas moedas altera a confiança relativa do modelo."
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
    st.sidebar.warning("⚠️ O ideal é a soma dos pesos ficar em 1,00.")

st.sidebar.subheader("Sensibilidade ao Federal Reserve")
SENSIBILIDADE_FED = {
    moeda: st.sidebar.slider(
        moeda, -1.0, 1.0, float(SENSIBILIDADE_FED_PADRAO[moeda]), 0.05
    )
    for moeda in MOEDAS
}

st.sidebar.divider()
st.sidebar.caption("Modelo FX: prioriza juros reais, Treasury 2Y e Fed para o USD.")
st.sidebar.caption(f"🕒 Atualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
if not CHAVE_FRED:
    st.sidebar.warning("FRED sem chave: alguns dados usarão valores de segurança.")
if CHAVE_EODHD:
    st.sidebar.success("EODHD configurado: consenso automático tentará usar Economic Events.")
else:
    st.sidebar.info("EODHD sem token: consenso permanece manual.")

if CHAVE_TWELVE_DATA:
    st.sidebar.success("Twelve Data configurado: coleta exclusiva do Autopilot; telas usam cache.")
else:
    st.sidebar.info("Twelve Data sem chave: análise técnica automática ficará aguardando configuração.")

# =========================================================
# CONEXÃO E FRED
# =========================================================

def _get(url: str, timeout: int = 15):
    try:
        resposta = requests.get(url, timeout=timeout)
        resposta.raise_for_status()
        return resposta
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def _fred_observacoes(series_id: str, limite: int = 24, unidades: str | None = None) -> pd.DataFrame:
    if not CHAVE_FRED:
        return pd.DataFrame(columns=["date", "value"])

    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={CHAVE_FRED}&file_type=json"
        f"&sort_order=desc&limit={limite}"
    )
    if unidades:
        url += f"&units={unidades}"

    resposta = _get(url)
    if resposta is None:
        return pd.DataFrame(columns=["date", "value"])

    try:
        df = pd.DataFrame(resposta.json().get("observations", []))
        if df.empty:
            return pd.DataFrame(columns=["date", "value"])
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["date", "value"]).sort_values("date")
    except Exception:
        return pd.DataFrame(columns=["date", "value"])


def _fred_ultimo(series_id: str, idade_max_dias: int | None = None) -> float | None:
    df = _fred_observacoes(series_id, 12)
    if df.empty:
        return None
    ultima = df.iloc[-1]
    if idade_max_dias is not None:
        idade = (pd.Timestamp.now(tz=None).normalize() - ultima["date"].normalize()).days
        if idade > idade_max_dias:
            return None
    return float(ultima["value"])


def _fred_ultimo_com_meta(series_id: str, limite: int = 24, unidades: str | None = None) -> dict:
    """Retorna valor, data e idade da observação mais recente válida da FRED."""
    df = _fred_observacoes(series_id, limite, unidades=unidades)
    if df.empty:
        return {"valor": None, "data": None, "idade_dias": None, "serie": series_id}
    ultima = df.iloc[-1]
    data = pd.Timestamp(ultima["date"]).normalize()
    hoje = pd.Timestamp.now(tz=None).normalize()
    idade = int((hoje - data).days)
    return {
        "valor": float(ultima["value"]),
        "data": data.strftime("%d/%m/%Y"),
        "idade_dias": idade,
        "serie": series_id,
    }


def _fred_variacao_mensal_com_meta(series_id: str) -> dict:
    df = _fred_observacoes(series_id, 8)
    if len(df) < 2:
        return {"valor": None, "data": None, "idade_dias": None, "serie": series_id}
    ultima = df.iloc[-1]
    anterior = df.iloc[-2]
    data = pd.Timestamp(ultima["date"]).normalize()
    hoje = pd.Timestamp.now(tz=None).normalize()
    return {
        "valor": float(ultima["value"] - anterior["value"]),
        "data": data.strftime("%d/%m/%Y"),
        "idade_dias": int((hoje - data).days),
        "serie": series_id,
    }


def _fred_variacao_anual_com_meta(series_id: str) -> dict:
    """Variação percentual anual calculada pela própria FRED (units=pc1) + data."""
    return _fred_ultimo_com_meta(series_id, limite=12, unidades="pc1")


def _status_frescura(idade_dias: int | None, limite_dias: int) -> tuple[str, str]:
    if idade_dias is None:
        return "⚠️", "Sem data"
    if idade_dias <= limite_dias:
        return "🟢", "Atual"
    if idade_dias <= limite_dias * 2:
        return "🟡", "Atenção"
    return "🔴", "Desatualizado"


def _fred_variacao_mensal_nivel(series_id: str) -> float | None:
    df = _fred_observacoes(series_id, 6)
    if len(df) < 2:
        return None
    return float(df.iloc[-1]["value"] - df.iloc[-2]["value"])


def _fred_variacao_anual_percentual(series_id: str, idade_max_dias: int = 180) -> float | None:
    """Pede ao próprio FRED a variação % em relação ao mesmo período do ano anterior."""
    df = _fred_observacoes(series_id, 8, unidades="pc1")
    if df.empty:
        return None
    ultima = df.iloc[-1]
    idade = (pd.Timestamp.now(tz=None).normalize() - ultima["date"].normalize()).days
    if idade > idade_max_dias:
        return None
    return float(ultima["value"])


def _bcb_ultimo(codigo_sgs: int) -> float | None:
    resposta = _get(
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_sgs}/dados/ultimos/1?formato=json"
    )
    if resposta is None:
        return None
    try:
        return float(resposta.json()[0]["valor"].replace(",", "."))
    except Exception:
        return None


def _valor_valido(valor, minimo, maximo) -> bool:
    return valor is not None and np.isfinite(valor) and minimo <= float(valor) <= maximo


def _usar_ou_fallback(valor, fallback, minimo, maximo):
    return float(valor) if _valor_valido(valor, minimo, maximo) else float(fallback)

# =========================================================
# NOTÍCIAS E FED
# =========================================================

PALAVRAS_RESTRITIVAS = (
    "higher for longer", "inflation remains elevated", "rate hike", "rate hikes",
    "hike rates", "hiking rates", "tightening", "restrictive", "hawkish",
    "not ready to cut", "strong economy", "inflation heats up", "inflation hot",
    "sticky inflation", "stubborn inflation", "rates stay high", "rates higher"
)
PALAVRAS_FLEXIVEIS = (
    "rate cut", "rate cuts", "cut rates", "cutting rates", "easing", "dovish",
    "disinflation", "inflation cooling", "inflation cools", "weaker labor",
    "labor market weakens", "growth slowing", "lower rates", "recession risk"
)
POSITIVAS = ("strong", "growth", "beat", "surge", "rise", "gain", "alta", "avanço")
NEGATIVAS = ("weak", "recession", "drop", "fall", "selloff", "queda", "crise")

# Termos usados para separar notícias realmente úteis para política monetária/Forex.
TERMOS_ALTA_RELEVANCIA = (
    "fomc", "federal reserve", "fed rate", "interest rate", "rate hike", "rate cut",
    "inflation", "cpi", "pce", "payroll", "nonfarm", "unemployment", "jobs report",
    "treasury yields", "dot plot", "monetary policy", "fed decision", "fed meeting"
)
TERMOS_MEDIA_RELEVANCIA = (
    "powell", "warsh", "bowman", "fed chair", "fed governor", "fed official",
    "labor market", "economic growth", "gdp", "wages", "employment"
)
TERMOS_IRRELEVANTES = (
    "mansion", "real estate", "realtor", "house sale", "sells home", "sells mansion",
    "meet the directors", "biography", "personal life", "wedding", "sports", "celebrity"
)


def _rss_titulos(consulta: str, idioma="en-US", pais="US", ceid="US:en") -> list[str]:
    q = urllib.parse.quote(consulta)
    url = f"https://news.google.com/rss/search?q={q}&hl={idioma}&gl={pais}&ceid={ceid}"
    resposta = _get(url)
    if resposta is None:
        return []
    try:
        raiz = ET.fromstring(resposta.content)
        titulos = []
        vistos = set()
        for item in raiz.iter("item"):
            titulo = (item.findtext("title", "") or "").strip()
            chave = titulo.lower()
            if titulo and chave not in vistos:
                vistos.add(chave)
                titulos.append(titulo)
        return titulos
    except Exception:
        return []


def _separar_fonte(titulo: str) -> tuple[str, str]:
    """Separa 'manchete - Fonte' sem quebrar hífens internos."""
    if " - " in titulo:
        corpo, fonte = titulo.rsplit(" - ", 1)
        return corpo.strip(), fonte.strip()
    return titulo.strip(), "Fonte não identificada"


def _relevancia_manchete(titulo: str) -> tuple[int, str]:
    t = titulo.lower()
    if any(x in t for x in TERMOS_IRRELEVANTES):
        return 0, "Baixa"
    alta = sum(1 for x in TERMOS_ALTA_RELEVANCIA if x in t)
    media = sum(1 for x in TERMOS_MEDIA_RELEVANCIA if x in t)
    pontos = alta * 3 + media
    if pontos >= 4:
        return pontos, "Alta"
    if pontos >= 2:
        return pontos, "Média"
    return pontos, "Baixa"


def _impacto_usd_manchete(titulo: str) -> tuple[float, str, str]:
    """Retorna score [-1,+1], direção e explicação curta."""
    t = titulo.lower()
    hawk = sum(1 for x in PALAVRAS_RESTRITIVAS if x in t)
    dove = sum(1 for x in PALAVRAS_FLEXIVEIS if x in t)
    if hawk > dove:
        score = min(1.0, 0.35 + 0.2 * (hawk - dove))
        return score, "🟢 Favorável ao USD", "Sinal mais restritivo: juros altos por mais tempo tendem a apoiar o dólar."
    if dove > hawk:
        score = -min(1.0, 0.35 + 0.2 * (dove - hawk))
        return score, "🔴 Desfavorável ao USD", "Sinal mais flexível: maior chance de cortes tende a pressionar o dólar."
    return 0.0, "⚪ Neutro/indefinido", "A manchete não traz sinal claro de alta ou corte de juros."


# Fallback local: não tenta "inventar" tradução completa; converte termos macro essenciais.
TRADUCOES_MANCHETES = {
    "rate hikes": "altas de juros", "rate hike": "alta de juros",
    "rate cuts": "cortes de juros", "rate cut": "corte de juros",
    "interest rates": "taxas de juros", "inflation": "inflação",
    "Federal Reserve": "Federal Reserve", "economy": "economia",
    "markets": "mercados", "market": "mercado", "growth": "crescimento",
    "jobs": "empregos", "labor": "trabalho", "dollar": "dólar",
    "bonds": "títulos", "decision": "decisão", "September": "setembro",
    "higher": "mais altos", "lower": "mais baixos",
    "hold rates steady": "manter os juros estáveis",
    "all eyes on": "todas as atenções voltadas para",
    "stubborn": "persistente", "cool": "esfriar", "heats up": "acelera",
    "week ahead": "semana à frente", "economists say": "dizem economistas",
    "pressure": "pressão", "raises prospect": "aumenta a possibilidade de",
    "faces new pressure": "enfrenta nova pressão", "to hike rates": "para elevar os juros",
}


def _traduzir_fallback_local(titulo: str) -> str:
    texto = titulo
    for origem, destino in sorted(TRADUCOES_MANCHETES.items(), key=lambda x: len(x[0]), reverse=True):
        texto = re.sub(re.escape(origem), destino, texto, flags=re.IGNORECASE)
    return texto


def _traducao_parece_erro(texto: str) -> bool:
    t = (texto or "").lower()
    marcadores = ("error 500", "server error", "that's an error", "that’s an error", "please try again later", "<!doctype html", "<html")
    return not texto or any(m in t for m in marcadores)


@st.cache_data(ttl=86400, show_spinner=False)
def _traduzir_google_endpoint(texto: str) -> str | None:
    """Tentativa 1: endpoint público de tradução do Google, com timeout curto."""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "en", "tl": "pt", "dt": "t", "q": texto}
        r = requests.get(url, params=params, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.ok:
            data = r.json()
            trad = "".join(parte[0] for parte in data[0] if parte and parte[0])
            if not _traducao_parece_erro(trad):
                return trad.strip()
    except Exception:
        pass
    return None


@st.cache_data(ttl=86400, show_spinner=False)
def _traduzir_mymemory(texto: str) -> str | None:
    """Tentativa 2: MyMemory. É fallback e pode ter limite de uso."""
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": texto, "langpair": "en|pt-BR"},
            timeout=8,
            headers={"User-Agent": "USD-Macro-Pro/5.1"},
        )
        if r.ok:
            data = r.json()
            trad = (data.get("responseData") or {}).get("translatedText", "")
            if not _traducao_parece_erro(trad):
                return trad.strip()
    except Exception:
        pass
    return None


@st.cache_data(ttl=86400, show_spinner=False)
def _traduzir_manchete(titulo: str) -> tuple[str, str]:
    """Tradução robusta com dois provedores + fallback local. Nunca exibe HTML/erro técnico."""
    if not titulo or not titulo.strip():
        return titulo, "sem tradução"
    corpo, _ = _separar_fonte(titulo)
    trad = _traduzir_google_endpoint(corpo)
    if trad:
        return trad, "Google"
    trad = _traduzir_mymemory(corpo)
    if trad:
        return trad, "MyMemory"
    local = _traduzir_fallback_local(corpo)
    return local, "modo local"


def _score_palavras(titulos: list[str], positivas, negativas) -> float:
    if not titulos:
        return 0.0
    pos = neg = 0
    for titulo in [x.lower() for x in titulos]:
        pos += sum(1 for palavra in positivas if palavra in titulo)
        neg += sum(1 for palavra in negativas if palavra in titulo)
    return float(np.clip((pos - neg) / max(pos + neg, 1), -1, 1))


@st.cache_data(ttl=1800, show_spinner="Lendo a narrativa do Fed...")
def carregar_narrativa_fed() -> dict:
    # Consulta focada em política monetária para evitar manchetes pessoais/irrelevantes.
    brutas = _rss_titulos('(Federal Reserve OR FOMC OR "Fed rate" OR "Fed Chair") when:7d')
    analisadas = []
    for titulo in brutas:
        pontos, nivel = _relevancia_manchete(titulo)
        if nivel == "Baixa":
            continue
        impacto, direcao, explicacao = _impacto_usd_manchete(titulo)
        corpo, fonte = _separar_fonte(titulo)
        analisadas.append({
            "titulo": titulo,
            "corpo": corpo,
            "fonte": fonte,
            "relevancia_pontos": pontos,
            "relevancia": nivel,
            "impacto": impacto,
            "direcao": direcao,
            "explicacao": explicacao,
        })

    analisadas.sort(key=lambda x: (x["relevancia_pontos"], abs(x["impacto"])), reverse=True)
    analisadas = analisadas[:12]

    if analisadas:
        pesos = np.array([max(1, x["relevancia_pontos"]) for x in analisadas], dtype=float)
        impactos = np.array([x["impacto"] for x in analisadas], dtype=float)
        forca = float(np.clip(np.average(impactos, weights=pesos), -1, 1))
    else:
        forca = 0.0

    tom = "Restritivo" if forca > 0.15 else "Flexível" if forca < -0.15 else "Neutro"
    STATUS_FONTE["Fed"] = f"✅ {len(analisadas)} manchetes relevantes" if analisadas else "⚠️ Sem manchetes relevantes"
    return {"tom": tom, "forca": forca, "titulos": [x["titulo"] for x in analisadas], "analisadas": analisadas}


@st.cache_data(ttl=1800, show_spinner="Analisando sentimento das notícias...")
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
            resposta = _get(url)
            if resposta:
                titulos = [a["title"] for a in resposta.json().get("articles", []) if a.get("title")]
                return float(np.clip(50 + 50 * _score_palavras(titulos, POSITIVAS, NEGATIVAS), 0, 100))
        except Exception:
            pass
    return 50.0

# =========================================================
# PAINEL EUA
# =========================================================

SERIES_EUA = {
    "Juros do Fed": "FEDFUNDS",
    "IPC": "CPIAUCSL",
    "IPC Núcleo": "CPILFESL",
    "PCE": "PCEPI",
    "PCE Núcleo": "PCEPILFE",
    "Payroll": "PAYEMS",
    "Desemprego": "UNRATE",
    "PIB": "A191RL1Q225SBEA",
    "Treasury 2 anos": "DGS2",
    "Treasury 10 anos": "DGS10",
    "Índice amplo do dólar": "DTWEXBGS",
}


@st.cache_data(ttl=900, show_spinner="Carregando e validando dados macroeconômicos dos EUA...")
def carregar_macro_eua() -> dict:
    fallback = {
        "Juros do Fed": 4.25,
        "IPC anual": 2.9,
        "IPC Núcleo anual": 3.2,
        "PCE anual": 2.6,
        "PCE Núcleo anual": 2.8,
        "Payroll variação mensal (mil)": 150.0,
        "Desemprego": 4.2,
        "PIB": 2.2,
        "Treasury 2 anos": 4.1,
        "Treasury 10 anos": 4.3,
        "Índice amplo do dólar": 120.0,
    }

    metas = {
        "Juros do Fed": _fred_ultimo_com_meta(SERIES_EUA["Juros do Fed"], 12),
        "IPC anual": _fred_variacao_anual_com_meta(SERIES_EUA["IPC"]),
        "IPC Núcleo anual": _fred_variacao_anual_com_meta(SERIES_EUA["IPC Núcleo"]),
        "PCE anual": _fred_variacao_anual_com_meta(SERIES_EUA["PCE"]),
        "PCE Núcleo anual": _fred_variacao_anual_com_meta(SERIES_EUA["PCE Núcleo"]),
        "Payroll variação mensal (mil)": _fred_variacao_mensal_com_meta(SERIES_EUA["Payroll"]),
        "Desemprego": _fred_ultimo_com_meta(SERIES_EUA["Desemprego"], 12),
        "PIB": _fred_ultimo_com_meta(SERIES_EUA["PIB"], 12),
        "Treasury 2 anos": _fred_ultimo_com_meta(SERIES_EUA["Treasury 2 anos"], 20),
        "Treasury 10 anos": _fred_ultimo_com_meta(SERIES_EUA["Treasury 10 anos"], 20),
        "Índice amplo do dólar": _fred_ultimo_com_meta(SERIES_EUA["Índice amplo do dólar"], 20),
    }

    limites = {
        "Juros do Fed": (-1, 25), "IPC anual": (-5, 25), "IPC Núcleo anual": (-5, 25),
        "PCE anual": (-5, 25), "PCE Núcleo anual": (-5, 25),
        "Payroll variação mensal (mil)": (-3000, 3000), "Desemprego": (0, 30),
        "PIB": (-20, 20), "Treasury 2 anos": (-2, 20), "Treasury 10 anos": (-2, 20),
        "Índice amplo do dólar": (50, 200),
    }

    frescura = {
        "Juros do Fed": 45, "IPC anual": 50, "IPC Núcleo anual": 50,
        "PCE anual": 50, "PCE Núcleo anual": 50, "Payroll variação mensal (mil)": 50,
        "Desemprego": 50, "PIB": 130, "Treasury 2 anos": 5,
        "Treasury 10 anos": 5, "Índice amplo do dólar": 10,
    }

    dados, auditoria = {}, []
    for chave, fallback_val in fallback.items():
        meta = metas[chave]
        bruto = meta.get("valor")
        valido = _valor_valido(bruto, *limites[chave])
        valor_final = float(bruto) if valido else float(fallback_val)
        fonte = f"FRED · {meta.get('serie')}" if valido else "Valor de segurança"
        idade = meta.get("idade_dias") if valido else None
        icone, status = _status_frescura(idade, frescura[chave])
        dados[chave] = valor_final
        auditoria.append({
            "Indicador": chave.replace("Payroll variação mensal (mil)", "Payroll — variação mensal"),
            "Valor": round(valor_final, 3),
            "Última observação": meta.get("data") if valido else "—",
            "Idade (dias)": idade if idade is not None else "—",
            "Status": f"{icone} {status}" if valido else "⚠️ Fallback",
            "Fonte": fonte,
        })

    dados["_auditoria"] = auditoria
    dados["_metadados"] = metas
    dados["_fallbacks"] = sum(1 for x in auditoria if x["Fonte"] == "Valor de segurança")
    STATUS_FONTE["EUA"] = "✅ FRED + validação + datas" if CHAVE_FRED else "⚠️ Valores de segurança"
    return dados


# =========================================================
# CALENDÁRIO MACRO AUTOMÁTICO — FRED
# =========================================================
RELEASES_FRED = {
    "IPC / CPI": 10,
    "Emprego / Payroll": 50,
    "PIB / GDP": 53,
    "PCE / Renda e Gastos": 54,
}

def _fred_get(endpoint: str, params: dict) -> dict:
    if not CHAVE_FRED:
        return {}
    p = dict(params)
    p["api_key"] = CHAVE_FRED
    p["file_type"] = "json"
    try:
        r = requests.get(f"https://api.stlouisfed.org/fred/{endpoint}", params=p, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

@st.cache_data(ttl=1800, show_spinner=False)
def _fred_datas_release(release_id: int) -> list[str]:
    hoje = pd.Timestamp.now(tz=None).normalize()
    inicio = (hoje - pd.Timedelta(days=120)).strftime("%Y-%m-%d")
    fim = (hoje + pd.Timedelta(days=120)).strftime("%Y-%m-%d")
    js = _fred_get("release/dates", {
        "release_id": release_id,
        "realtime_start": inicio,
        "realtime_end": fim,
        "include_release_dates_with_no_data": "true",
        "sort_order": "asc",
        "limit": 1000,
    })
    return [x.get("date") for x in js.get("release_dates", []) if x.get("date")]

def _data_release(datas: list[str], futura: bool) -> str | None:
    hoje = pd.Timestamp.now(tz=None).normalize()
    validas = []
    for d in datas:
        try:
            dt = pd.Timestamp(d).normalize()
            if (futura and dt >= hoje) or ((not futura) and dt <= hoje):
                validas.append(dt)
        except Exception:
            pass
    if not validas:
        return None
    dt = min(validas) if futura else max(validas)
    return dt.strftime("%d/%m/%Y")

@st.cache_data(ttl=1800, show_spinner="Carregando calendário econômico...")
def carregar_calendario_fred() -> pd.DataFrame:
    linhas = []
    for nome, rid in RELEASES_FRED.items():
        datas = _fred_datas_release(rid)
        linhas.append({
            "Evento": nome,
            "Última data de release": _data_release(datas, False) or "—",
            "Próxima data de release": _data_release(datas, True) or "—",
            "Fonte": f"FRED release {rid}",
        })
    return pd.DataFrame(linhas)

def _obs_ultimas(series_id: str, unidades: str | None = None, limite: int = 3) -> list[float]:
    df = _fred_observacoes(series_id, max(limite + 2, 6), unidades=unidades)
    if df.empty:
        return []
    vals = pd.to_numeric(df["value"], errors="coerce").dropna().tolist()
    return [float(x) for x in vals[-limite:]]

def _automatico_real_anterior(indicador: str) -> tuple[float | None, float | None]:
    mapa = {
        "IPC anual": ("CPIAUCSL", "pc1"),
        "IPC Núcleo anual": ("CPILFESL", "pc1"),
        "PCE anual": ("PCEPI", "pc1"),
        "PCE Núcleo anual": ("PCEPILFE", "pc1"),
        "Desemprego": ("UNRATE", None),
    }
    if indicador == "Payroll":
        vals = _obs_ultimas("PAYEMS", None, 3)
        return (vals[-1] - vals[-2], vals[-2] - vals[-3]) if len(vals) >= 3 else (None, None)
    cfg = mapa.get(indicador)
    if not cfg:
        return None, None
    vals = _obs_ultimas(cfg[0], cfg[1], 2)
    return (vals[-1], vals[-2]) if len(vals) >= 2 else (None, None)


# =========================================================
# RANKING GLOBAL — SÉRIES E TRANSFORMAÇÕES CORRETAS
# =========================================================

# inflação e PIB são séries em NÍVEL; por isso são convertidas para variação % anual.
# Isso evita mostrar, por exemplo, 103 como "inflação 103%" ou 2.900.000 como "PIB %".
SERIES_GLOBAIS = {
    "USD": {"juros": "FEDFUNDS", "inflacao": "CPIAUCSL", "pib": "GDPC1"},
    "EUR": {"juros": "ECBDFR", "inflacao": "CP0000EZ19M086NEST", "pib": "CLVMNACSCAB1GQEA"},
    "GBP": {"juros": "BOERUKM", "inflacao": "CPALTT01GBM661S", "pib": "CLVMNACSCAB1GQUK"},
    "JPY": {"juros": "IR3TIB01JPM156N", "inflacao": "CPALTT01JPM661S", "pib": "JPNRGDPEXP"},
    "CHF": {"juros": "IR3TIB01CHM156N", "inflacao": "CPALTT01CHM661S", "pib": "CLVMNACSAB1GQCH"},
    "CAD": {"juros": "IR3TIB01CAM156N", "inflacao": "CPALTT01CAM661S", "pib": "NGDPRSAXDCCAQ"},
    "AUD": {"juros": "IR3TIB01AUM156N", "inflacao": "CPALTT01AUM661S", "pib": "NGDPRSAXDCAUQ"},
    "NZD": {"juros": "IR3TIB01NZM156N", "inflacao": "CPALTT01NZM661S", "pib": "CLVMNACSCAB1GQNZ"},
}

VALORES_SEGURANCA = {
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


@st.cache_data(ttl=3600, show_spinner="Carregando dados macroeconômicos globais...")
def carregar_dados_moedas() -> dict:
    resultado = {}

    for moeda, fallback in VALORES_SEGURANCA.items():
        juros = inflacao = pib = None
        fonte = "Valores de segurança"

        if moeda == "BRL":
            # BCB/SGS. Qualquer valor fora de faixa é rejeitado para evitar unidade errada.
            juros = _bcb_ultimo(432)
            inflacao = _bcb_ultimo(13522)
            pib = _bcb_ultimo(4380)
            fonte = "BCB + validação"

        elif CHAVE_FRED and moeda in SERIES_GLOBAIS:
            ids = SERIES_GLOBAIS[moeda]
            juros = _fred_ultimo(ids["juros"], 180)
            inflacao = _fred_variacao_anual_percentual(ids["inflacao"], 180)
            pib = _fred_variacao_anual_percentual(ids["pib"], 300)
            fonte = "FRED + transformação anual"

        juros_final = _usar_ou_fallback(juros, fallback["juros"], -2, 30)
        inflacao_final = _usar_ou_fallback(inflacao, fallback["inflacao"], -5, 30)
        pib_final = _usar_ou_fallback(pib, fallback["pib"], -15, 20)

        usou_fallback = (
            not _valor_valido(juros, -2, 30)
            or not _valor_valido(inflacao, -5, 30)
            or not _valor_valido(pib, -15, 20)
        )

        resultado[moeda] = {
            "juros": juros_final,
            "inflacao": inflacao_final,
            "pib": pib_final,
            "sentimento": sentimento_noticias(MOEDAS[moeda]),
            "fonte": f"{fonte}{' + fallback parcial' if usou_fallback else ''}",
        }
        STATUS_FONTE[moeda] = "⚠️ Fallback parcial" if usou_fallback else "✅ Dados válidos"

    return resultado

# =========================================================
# MOTOR DE CÁLCULO
# =========================================================

def normalizar(serie: pd.Series, inverter: bool = False) -> pd.Series:
    serie = pd.to_numeric(serie, errors="coerce").fillna(0.0)
    if serie.max() == serie.min():
        normalizada = pd.Series(50.0, index=serie.index)
    else:
        normalizada = (serie - serie.min()) / (serie.max() - serie.min()) * 100
    return 100 - normalizada if inverter else normalizada


def score_emprego_usd(macro: dict) -> float:
    s_payroll = np.clip(50 + (macro["Payroll variação mensal (mil)"] - 100) * 0.15, 0, 100)
    s_desemprego = np.clip(50 - (macro["Desemprego"] - 4.2) * 15, 0, 100)
    return float((s_payroll + s_desemprego) / 2)


def score_inflacao_usd(macro: dict) -> float:
    media = np.mean([
        macro["IPC anual"], macro["IPC Núcleo anual"],
        macro["PCE anual"], macro["PCE Núcleo anual"]
    ])
    return float(np.clip(50 + (media - 2.0) * 12, 0, 100))


def score_atividade_usd(macro: dict) -> float:
    """Score simples de atividade usando PIB real; ISM/PMI manual entra na leitura de surpresa."""
    pib = float(macro.get("PIB", 0.0))
    return float(np.clip(50 + (pib - 2.0) * 10, 0, 100))


def score_juros_usd(macro: dict) -> float:
    """Juros de curto prazo têm grande peso no câmbio; combina Fed Funds e Treasury 2Y."""
    fed = float(macro.get("Juros do Fed", 0.0))
    y2 = float(macro.get("Treasury 2 anos", 0.0))
    # âncoras deliberadamente moderadas; não representa probabilidade de mercado
    s_fed = np.clip(50 + (fed - 3.0) * 10, 0, 100)
    s_y2 = np.clip(50 + (y2 - 3.0) * 12, 0, 100)
    return float(0.4 * s_fed + 0.6 * s_y2)


def score_dolar_amplo_usd(macro: dict) -> float:
    """Nível do índice amplo FRED usado apenas como confirmação, não como DXY ICE."""
    indice = float(macro.get("Índice amplo do dólar", 120.0))
    return float(np.clip(50 + (indice - 120.0) * 2.0, 0, 100))


def score_fed_usd(fed: dict) -> float:
    return float(np.clip(50 + float(fed.get("forca", 0.0)) * 50, 0, 100))


def score_usd_detalhado(macro: dict, fed: dict) -> dict:
    componentes = {
        "Inflação": score_inflacao_usd(macro),
        "Emprego": score_emprego_usd(macro),
        "Atividade": score_atividade_usd(macro),
        "Juros / Treasury 2Y": score_juros_usd(macro),
        "Federal Reserve": score_fed_usd(fed),
        "Índice amplo USD": score_dolar_amplo_usd(macro),
    }
    pesos = {
        "Inflação": 0.18,
        "Emprego": 0.18,
        "Atividade": 0.12,
        "Juros / Treasury 2Y": 0.24,
        "Federal Reserve": 0.20,
        "Índice amplo USD": 0.08,
    }
    total = float(sum(componentes[k] * pesos[k] for k in componentes))
    return {"score": float(np.clip(total, 0, 100)), "componentes": componentes, "pesos": pesos}


def faixa_forca(score: float) -> tuple[str, str]:
    if score >= 70:
        return "FORTE", "🟢"
    if score >= 58:
        return "MODERADAMENTE FORTE", "🟢"
    if score > 42:
        return "NEUTRO", "⚪"
    if score > 30:
        return "MODERADAMENTE FRACO", "🟠"
    return "FRACO", "🔴"


def qualidade_dados_usd() -> tuple[int, str]:
    # FRED abastece a maior parte do painel; sem chave a qualidade cai porque entram fallbacks.
    pontos = 90 if CHAVE_FRED else 45
    rotulo = "ALTA" if pontos >= 80 else ("MÉDIA" if pontos >= 60 else "BAIXA")
    return pontos, rotulo


def classificar_par(score_base: float, score_cotada: float, base: str, cotada: str) -> dict:
    diff = float(score_base - score_cotada)
    ad = abs(diff)
    if ad >= 25:
        conf = "ALTA"
    elif ad >= 12:
        conf = "MÉDIA"
    else:
        conf = "BAIXA"
    if diff >= 8:
        vies = f"COMPRA {base}/{cotada}"
        direcao = "🟢"
    elif diff <= -8:
        vies = f"VENDA {base}/{cotada}"
        direcao = "🔴"
    else:
        vies = "SEM VANTAGEM MACRO CLARA"
        direcao = "⚪"
    return {"diferenca": diff, "confianca": conf, "vies": vies, "icone": direcao}


def calcular_ranking(dados: dict, macro_us: dict, fed: dict) -> pd.DataFrame:
    df = pd.DataFrame(dados).T.reset_index().rename(columns={"index": "Código"})
    df["Moeda"] = df["Código"].map(MOEDAS)

    # Para câmbio, diferencial de juros REAIS tende a ser mais informativo que juros nominais isolados.
    df["juros_reais"] = pd.to_numeric(df["juros"], errors="coerce") - pd.to_numeric(df["inflacao"], errors="coerce")
    df["n_juros"] = normalizar(df["juros_reais"])
    df["n_inflacao"] = normalizar(df["inflacao"])
    df["n_pib"] = normalizar(df["pib"])
    df["n_sentimento"] = normalizar(df["sentimento"])
    df["n_emprego"] = 50.0
    df["n_atividade"] = 50.0

    idx_usd = df.index[df["Código"] == "USD"]
    if len(idx_usd):
        i = idx_usd[0]
        df.loc[i, "n_inflacao"] = score_inflacao_usd(macro_us)
        df.loc[i, "n_emprego"] = score_emprego_usd(macro_us)
        df.loc[i, "n_atividade"] = score_atividade_usd(macro_us)
        # Treasury 2Y é incorporado no componente de juros do USD.
        df.loc[i, "n_juros"] = score_juros_usd(macro_us)

    df["Pontuação_Macro"] = (
        PESOS["juros"] * df["n_juros"]
        + PESOS["inflacao"] * df["n_inflacao"]
        + PESOS["pib"] * df["n_pib"]
        + PESOS["emprego"] * df["n_emprego"]
        + PESOS["atividade"] * df["n_atividade"]
        + PESOS["sentimento"] * df["n_sentimento"]
    )

    df["Influência_Fed"] = (
        df["Código"].map(SENSIBILIDADE_FED).fillna(0.0)
        * fed["forca"] * IMPACTO_MAX_FED
    )
    df["Pontuação_Final"] = (df["Pontuação_Macro"] + df["Influência_Fed"]).clip(0, 100)

    # O USD usa um score dedicado com inflação, emprego, atividade, juros/Treasury, Fed e índice amplo.
    idx_usd2 = df.index[df["Código"] == "USD"]
    if len(idx_usd2):
        iu = idx_usd2[0]
        usd_det = score_usd_detalhado(macro_us, fed)
        df.loc[iu, "Pontuação_Final"] = usd_det["score"]
        df.loc[iu, "Pontuação_Macro"] = (
            usd_det["componentes"]["Inflação"] * 0.25
            + usd_det["componentes"]["Emprego"] * 0.25
            + usd_det["componentes"]["Atividade"] * 0.15            + usd_det["componentes"]["Juros / Treasury 2Y"] * 0.35
        )
        df.loc[iu, "Influência_Fed"] = usd_det["componentes"]["Federal Reserve"] - 50

    # Attribution metadata only: does not change any ranking score or weight.
    from strength_breakdown_v1104 import make_score_attribution
    df["strength_attribution"] = [
        make_score_attribution(row, PESOS, usd_det if row["Código"] == "USD" else None)
        for _, row in df.iterrows()
    ]

    df = df.sort_values("Pontuação_Final", ascending=False).reset_index(drop=True)
    df["Posição"] = df.index + 1

    for coluna in ["juros", "inflacao", "pib", "juros_reais", "sentimento", "Pontuação_Macro", "Influência_Fed", "Pontuação_Final"]:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").round(1)

    return df


def confianca_modelo(score_base: float, score_cotada: float):
    diferenca = score_base - score_cotada
    p = 1 / (1 + math.exp(-diferenca / (ESCALA_CONFIANCA / 2)))
    if p >= 0.65:
        status = "🟢 Forte vantagem da moeda base"
    elif p >= 0.55:
        status = "🟡 Leve vantagem da moeda base"
    elif p >= 0.45:
        status = "⚪ Equilíbrio"
    elif p >= 0.35:
        status = "🟡 Leve vantagem da moeda cotada"
    else:
        status = "🔴 Forte vantagem da moeda cotada"
    return p, diferenca, status


# =========================================================
# V6.6 — EXPECTATIVA DO MERCADO (PRÉ-RELEASE)
# =========================================================

EXPECTATIVA_ESCALAS = {
    "IPC anual": 0.20,
    "IPC Núcleo anual": 0.20,
    "PCE anual": 0.20,
    "PCE Núcleo anual": 0.20,
    "Payroll": 50.0,
    "Desemprego": 0.10,
    "ISM Industrial": 1.0,
    "ISM Serviços": 1.0,
}

EXPECTATIVA_PESOS = {
    "IPC anual": 1.15,
    "IPC Núcleo anual": 1.35,
    "PCE anual": 1.20,
    "PCE Núcleo anual": 1.45,
    "Payroll": 1.35,
    "Desemprego": 1.25,
    "ISM Industrial": 0.90,
    "ISM Serviços": 1.00,
}

def _expectativa_indicador_v66(nome: str, previsao: float, anterior: float,
                               maior_favorece_usd: bool) -> dict:
    """
    Compara CONSENSO vs ANTERIOR antes do release.
    Isso mede a expectativa embutida no calendário, não a surpresa futura.
    """
    if previsao is None or anterior is None:
        return {"delta": np.nan, "pontos": 0.0, "leitura": "Sem consenso", "score": 50.0}

    if not np.isfinite(previsao) or not np.isfinite(anterior):
        return {"delta": np.nan, "pontos": 0.0, "leitura": "Sem consenso", "score": 50.0}

    delta = float(previsao) - float(anterior)
    escala = float(EXPECTATIVA_ESCALAS.get(nome, 1.0))
    peso = float(EXPECTATIVA_PESOS.get(nome, 1.0))

    # Zero pode ser valor válido em alguns indicadores, portanto a existência
    # do consenso é controlada separadamente no painel.
    intensidade = float(np.clip(abs(delta) / max(escala, 1e-9), 0, 2.0))
    if abs(delta) < 1e-12:
        pontos = 0.0
        leitura = "⚪ Consenso estável"
    else:
        favoravel = delta > 0 if maior_favorece_usd else delta < 0
        pontos = (1.0 if favoravel else -1.0) * intensidade * peso
        leitura = "🟢 Expectativa favorece USD" if favoravel else "🔴 Expectativa desfavorece USD"

    return {
        "delta": delta,
        "pontos": float(pontos),
        "leitura": leitura,
        "score": float(np.clip(50 + pontos * 10, 0, 100)),
    }


def _resumo_expectativa_v66(linhas: list[dict]) -> dict:
    validas = [x for x in linhas if x.get("tem_consenso")]
    if not validas:
        return {
            "score": 50.0, "saldo": 0.0, "leitura": "⚪ Sem consensos preenchidos",
            "favoraveis": 0, "desfavoraveis": 0, "neutras": 0
        }

    saldo = float(sum(float(x["Pontos"]) for x in validas))
    # Pré-release deve ter influência informativa, sem alterar o score macro realizado.
    score = float(np.clip(50 + saldo * 7.5, 0, 100))
    fav = sum(float(x["Pontos"]) > 0 for x in validas)
    des = sum(float(x["Pontos"]) < 0 for x in validas)
    neu = sum(abs(float(x["Pontos"])) < 1e-12 for x in validas)

    if score >= 60:
        leitura = "🟢 Consenso agregado favorece o USD"
    elif score <= 40:
        leitura = "🔴 Consenso agregado desfavorece o USD"
    else:
        leitura = "⚪ Consenso agregado neutro/misto"

    return {
        "score": score, "saldo": saldo, "leitura": leitura,
        "favoraveis": int(fav), "desfavoraveis": int(des), "neutras": int(neu)
    }



# =========================================================
# V7.3 — EODHD / CONSENSO AUTOMÁTICO
# =========================================================

EOD_ALIASES_V73 = {
    "IPC anual": {
        "aliases": ["inflation rate", "consumer price index", "cpi"],
        "comparison": "yoy",
        "exclude": ["core"],
    },
    "IPC Núcleo anual": {
        "aliases": ["core inflation rate", "core consumer price index", "core cpi"],
        "comparison": "yoy",
        "exclude": [],
    },
    "PCE anual": {
        "aliases": ["pce price index", "pce prices", "personal consumption expenditures price index"],
        "comparison": "yoy",
        "exclude": ["core"],
    },
    "PCE Núcleo anual": {
        "aliases": ["core pce price index", "core pce prices", "core personal consumption expenditures"],
        "comparison": "yoy",
        "exclude": [],
    },
    "Payroll": {
        "aliases": ["nonfarm payrolls", "non farm payrolls", "nonfarm payroll"],
        "comparison": None,
        "exclude": [],
    },
    "Desemprego": {
        "aliases": ["unemployment rate"],
        "comparison": None,
        "exclude": [],
    },
    "ISM Industrial": {
        "aliases": ["ism manufacturing pmi", "ism manufacturing"],
        "comparison": None,
        "exclude": [],
    },
    "ISM Serviços": {
        "aliases": ["ism services pmi", "ism non manufacturing pmi", "ism non-manufacturing pmi", "ism services"],
        "comparison": None,
        "exclude": [],
    },
}

def _normalizar_texto_v73(s):
    import unicodedata
    s = "" if s is None else str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _numero_eod_v73(valor):
    if valor is None:
        return None
    try:
        return float(valor)
    except Exception:
        try:
            s = str(valor).strip().replace(",", "").replace("%", "")
            return float(s)
        except Exception:
            return None

@st.cache_data(ttl=1800, show_spinner=False)
def _eodhd_eventos_eua_v73(token: str, inicio_txt: str, fim_txt: str):
    """
    Uma única chamada por janela de cache.
    Retorna diagnóstico junto com os dados para o app não esconder falhas da API.
    """
    if not token:
        return {"ok": False, "status": None, "erro": "Token EODHD não configurado.", "dados": []}

    url = "https://eodhd.com/api/economic-events"
    params = {
        "api_token": token,
        "from": inicio_txt,
        "to": fim_txt,
        "country": "US",
        "limit": 1000,
        "offset": 0,
        "fmt": "json",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        status = int(r.status_code)
        if not r.ok:
            detalhe = r.text[:300] if r.text else f"HTTP {status}"
            return {
                "ok": False,
                "status": status,
                "erro": f"EODHD respondeu HTTP {status}: {detalhe}",
                "dados": [],
            }

        payload = r.json()
        if isinstance(payload, dict):
            # Alguns erros de API chegam como JSON mesmo com HTTP 200.
            msg = payload.get("message") or payload.get("error") or payload.get("errors")
            if msg:
                return {"ok": False, "status": status, "erro": str(msg), "dados": []}
            payload = payload.get("data", [])

        if not isinstance(payload, list):
            return {
                "ok": False,
                "status": status,
                "erro": "Formato inesperado retornado pelo EODHD.",
                "dados": [],
            }
        return {"ok": True, "status": status, "erro": "", "dados": payload}
    except Exception as e:
        return {"ok": False, "status": None, "erro": f"Falha de conexão EODHD: {e}", "dados": []}

def _eodhd_janela_v73():
    hoje = datetime.now().date()
    inicio = (hoje - timedelta(days=14)).strftime("%Y-%m-%d")
    fim = (hoje + timedelta(days=45)).strftime("%Y-%m-%d")
    return _eodhd_eventos_eua_v73(CHAVE_EODHD, inicio, fim)

def _eodhd_dado_indicador_v73(nome: str, diagnostico: dict):
    cfg = EOD_ALIASES_V73.get(nome)
    if not cfg or not diagnostico.get("ok"):
        return None

    aliases = [_normalizar_texto_v73(x) for x in cfg["aliases"]]
    excludes = [_normalizar_texto_v73(x) for x in cfg["exclude"]]
    comp_desejada = cfg.get("comparison")

    candidatos = []
    agora = datetime.now()

    for item in diagnostico.get("dados", []):
        tipo = _normalizar_texto_v73(item.get("type", ""))
        if not tipo:
            continue
        if not any(a in tipo for a in aliases):
            continue
        if any(x in tipo for x in excludes):
            continue

        comp = _normalizar_texto_v73(item.get("comparison", ""))
        if comp_desejada and comp != comp_desejada:
            continue

        try:
            dt = pd.Timestamp(item.get("date"))
            if dt.tzinfo is not None:
                dt = dt.tz_convert(None)
        except Exception:
            continue

        estimate = _numero_eod_v73(item.get("estimate"))
        previous = _numero_eod_v73(item.get("previous"))
        actual = _numero_eod_v73(item.get("actual"))

        delta_h = (dt.to_pydatetime() - agora).total_seconds() / 3600.0
        futuro = delta_h >= -4
        tem_consenso = estimate is not None

        # Preferência: próximo release futuro com estimate.
        prioridade = (
            0 if (futuro and tem_consenso) else
            1 if futuro else
            2 if tem_consenso else 3
        )
        candidatos.append((
            prioridade,
            abs(delta_h),
            {
                "nome": nome,
                "evento": item.get("type") or nome,
                "comparison": item.get("comparison"),
                "periodo": item.get("period"),
                "data": dt,
                "consenso": estimate,
                "anterior": previous,
                "real": actual,
                "source": "EODHD Economic Events",
            }
        ))

    if not candidatos:
        return None

    candidatos.sort(key=lambda x: (x[0], x[1]))
    return candidatos[0][2]

def _sincronizar_eodhd_v73():
    """
    Sincroniza antes dos widgets da Aba EUA.
    Não inventa consenso e não faz chamada extra por indicador.
    """
    diagnostico = _eodhd_janela_v73()
    resultado = {}

    if not diagnostico.get("ok"):
        return diagnostico, resultado

    for nome in EOD_ALIASES_V73:
        d = _eodhd_dado_indicador_v73(nome, diagnostico)
        if not d:
            continue
        resultado[nome] = d

        assinatura = (
            f"{d.get('evento')}|{d.get('data')}|{d.get('consenso')}|"
            f"{d.get('anterior')}|{d.get('real')}"
        )
        sig_key = f"v73_eod_sig_{nome}"
        mudou = st.session_state.get(sig_key) != assinatura

        if mudou:
            # Expectativa pré-release
            if d.get("consenso") is not None:
                st.session_state[f"v66_previsao_{nome}"] = float(d["consenso"])
                st.session_state[f"v66_consenso_{nome}"] = True
            if d.get("anterior") is not None:
                st.session_state[f"v66_anterior_{nome}"] = float(d["anterior"])

            # Surprise Engine
            if d.get("consenso") is not None:
                st.session_state[f"previsao_{nome}"] = float(d["consenso"])
            if d.get("anterior") is not None:
                st.session_state[f"anterior_{nome}"] = float(d["anterior"])
            if d.get("real") is not None:
                st.session_state[f"real_{nome}"] = float(d["real"])

            # Painel do par
            if d.get("consenso") is not None:
                st.session_state[f"v67_previsao_{nome}"] = float(d["consenso"])
                st.session_state[f"v67_usar_{nome}"] = True
            if d.get("anterior") is not None:
                st.session_state[f"v67_anterior_{nome}"] = float(d["anterior"])

            st.session_state[sig_key] = assinatura

    return diagnostico, resultado

def _painel_eodhd_v73(diagnostico, dados):
    st.markdown("#### 🌐 Consenso automático — EODHD")

    if not CHAVE_EODHD:
        st.warning(
            "Token EODHD não configurado. O app continua funcionando em modo manual."
        )
        return

    if not diagnostico.get("ok"):
        status = diagnostico.get("status")
        erro = diagnostico.get("erro", "Falha desconhecida.")
        st.warning(
            "O token foi encontrado, mas o endpoint Economic Events não respondeu com dados. "
            "Isso pode acontecer por limite diário, permissão do plano ou indisponibilidade temporária."
        )
        st.code(f"Status: {status if status is not None else '—'}\nDetalhe: {erro}")
        st.info(
            "Nenhum número é inventado: enquanto a API não liberar o evento, "
            "o consenso permanece manual."
        )
        return

    st.success(
        f"✅ EODHD conectado. Eventos recebidos na janela: {len(diagnostico.get('dados', []))}"
    )

    if not dados:
        st.warning(
            "A API respondeu, mas nenhum dos indicadores principais foi localizado "
            "na janela atual. O modo manual continua disponível."
        )
        return

    rows = []
    for nome, d in dados.items():
        rows.append({
            "Indicador": nome,
            "Evento EODHD": d.get("evento", "—"),
            "Comparação": d.get("comparison") or "—",
            "Período": d.get("periodo") or "—",
            "Data": d["data"].strftime("%d/%m/%Y %H:%M") if d.get("data") is not None else "—",
            "Consenso": d.get("consenso") if d.get("consenso") is not None else "—",
            "Anterior": d.get("anterior") if d.get("anterior") is not None else "—",
            "Real": d.get("real") if d.get("real") is not None else "—",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption(
        "EODHD fornece estimate/previous/actual. FRED/BLS/BEA continuam sendo "
        "as fontes principais do histórico oficial do motor."
    )

def _mostrar_expectativa_v66():
    st.subheader("🔮 Expectativa do Mercado — V7.4")
    st.caption(
        "Antes da divulgação: CONSENSO × ANTERIOR. "
        "Com EODHD Economic Events disponível, o consenso é preenchido automaticamente."
    )

    st.info("🤖 V7.4: Anterior e Real são automáticos; Consenso fica manual quando necessário.")

    indicadores = [
        ("IPC anual", True),
        ("IPC Núcleo anual", True),
        ("PCE anual", True),
        ("PCE Núcleo anual", True),
        ("Payroll", True),
        ("Desemprego", False),
        ("ISM Industrial", True),
        ("ISM Serviços", True),
    ]

    linhas = []
    for nome, maior_favorece in indicadores:
        prev_key = f"v66_previsao_{nome}"
        ant_key = f"v66_anterior_{nome}"
        flag_key = f"v66_consenso_{nome}"

        if prev_key not in st.session_state:
            st.session_state[prev_key] = 0.0
        if ant_key not in st.session_state:
            st.session_state[ant_key] = 0.0
        if flag_key not in st.session_state:
            st.session_state[flag_key] = False

        c0, c1, c2 = st.columns([0.9, 1.2, 1.2])
        with c0:
            tem = st.checkbox(
                "Usar", key=flag_key,
                help=f"Automático quando houver consenso disponível; pode ser desmarcado manualmente."
            )
        step = 1.0 if nome == "Payroll" else 0.1
        with c1:
            previsao = st.number_input(
                f"{nome} — Consenso",
                step=step, key=prev_key,
                help="Preenchido automaticamente pelo EODHD quando o endpoint Economic Events estiver disponível."
            )
        with c2:
            anterior = st.number_input(
                f"{nome} — Anterior",
                step=step, key=ant_key
            )

        r = _expectativa_indicador_v66(
            nome, float(previsao), float(anterior), maior_favorece
        ) if tem else {"delta": np.nan, "pontos": 0.0, "leitura": "⚪ Não utilizado", "score": 50.0}

        linhas.append({
            "Indicador": nome,
            "Consenso": float(previsao),
            "Anterior": float(anterior),
            "Δ esperado": round(r["delta"], 3) if np.isfinite(r["delta"]) else "—",
            "Leitura pré-release": r["leitura"],
            "Pontos": round(r["pontos"], 2),
            "tem_consenso": bool(tem),
        })

    resumo = _resumo_expectativa_v66(linhas)
    tabela = pd.DataFrame(linhas).drop(columns=["tem_consenso"])
    st.dataframe(tabela, width="stretch", hide_index=True)

    a,b,c,d = st.columns(4)
    a.metric("Expectativa USD", f"{resumo['score']:.0f}/100")
    b.metric("Favorecem USD", resumo["favoraveis"])
    c.metric("Desfavorecem USD", resumo["desfavoraveis"])
    d.metric("Neutras", resumo["neutras"])

    if resumo["score"] >= 60:
        st.success(f"**{resumo['leitura']}**")
    elif resumo["score"] <= 40:
        st.error(f"**{resumo['leitura']}**")
    else:
        st.info(f"**{resumo['leitura']}**")

    st.session_state["v66_expectativa_score"] = float(resumo["score"])
    st.session_state["v66_expectativa_leitura"] = resumo["leitura"]

    st.caption(
        "Expectativa não altera diretamente o macro realizado. "
        "Após o release, REAL × CONSENSO alimenta o Surprise Engine."
    )


# =========================================================
# SURPRESA ECONÔMICA
# =========================================================

SURPRESA_ESCALAS = {
    # Unidade aproximada usada para transformar a surpresa em intensidade comparável.
    # Não é desvio-padrão estatístico; é uma escala operacional transparente.
    "IPC anual": 0.20,
    "IPC Núcleo anual": 0.20,
    "PCE anual": 0.20,
    "PCE Núcleo anual": 0.20,
    "Payroll": 50.0,
    "Desemprego": 0.10,
    "ISM Industrial": 1.0,
    "ISM Serviços": 1.0,
}

SURPRESA_PESOS = {
    "IPC anual": 1.15,
    "IPC Núcleo anual": 1.35,
    "PCE anual": 1.20,
    "PCE Núcleo anual": 1.45,
    "Payroll": 1.35,
    "Desemprego": 1.25,
    "ISM Industrial": 0.90,
    "ISM Serviços": 1.00,
}

def classificar_surpresa(real, previsao, maior_favorece_usd=True, tolerancia=0.0,
                         nome_indicador=None):
    if previsao is None or not np.isfinite(previsao):
        return {
            "Surpresa": np.nan, "Pontuação": 0.0, "Classe": "Sem previsão",
            "Intensidade": 0.0, "Score impacto": 50.0
        }

    surpresa = float(real) - float(previsao)
    escala = float(SURPRESA_ESCALAS.get(nome_indicador, 1.0))
    peso = float(SURPRESA_PESOS.get(nome_indicador, 1.0))

    if abs(surpresa) <= tolerancia:
        classe, pontos, intensidade = "Neutro", 0.0, 0.0
    else:
        positivo = surpresa > 0 if maior_favorece_usd else surpresa < 0
        # Intensidade limitada evita que um outlier domine todo o modelo.
        intensidade = float(np.clip(abs(surpresa) / max(escala, 1e-9), 0, 3))
        sinal = 1.0 if positivo else -1.0
        pontos = sinal * intensidade * peso
        classe = "Favorável ao USD" if positivo else "Desfavorável ao USD"

    score_impacto = float(np.clip(50 + pontos * 10, 0, 100))
    return {
        "Surpresa": surpresa,
        "Pontuação": float(pontos),
        "Classe": classe,
        "Intensidade": float(intensidade),
        "Score impacto": score_impacto,
    }


def interpretar_conjunto_surpresas(df: pd.DataFrame, score_base_usd: float) -> dict:
    if df.empty:
        return {"ajuste": 0.0, "score_ajustado": score_base_usd, "confirmação": "Sem dados"}

    validos = df[pd.to_numeric(df["Previsão"], errors="coerce").fillna(0).abs() > 0].copy()
    if validos.empty:
        return {"ajuste": 0.0, "score_ajustado": score_base_usd, "confirmação": "Sem previsões preenchidas"}

    total = float(pd.to_numeric(validos["Pontuação"], errors="coerce").fillna(0).sum())
    # Ajuste controlado: no máximo ±15 pontos no score macro principal.
    ajuste = float(np.clip(total * 2.0, -15, 15))
    score_ajustado = float(np.clip(score_base_usd + ajuste, 0, 100))

    positivos = int((pd.to_numeric(validos["Pontuação"], errors="coerce") > 0).sum())
    negativos = int((pd.to_numeric(validos["Pontuação"], errors="coerce") < 0).sum())

    # Conflitos importantes: emprego forte com desemprego pior, ou inflação vs atividade em sentidos opostos.
    mapa = {r["Indicador"]: float(r["Pontuação"]) for _, r in validos.iterrows()}
    conflitos = []
    if mapa.get("Payroll", 0) * mapa.get("Desemprego", 0) < 0:
        conflitos.append("Payroll e desemprego estão em conflito")
    infl = sum(mapa.get(k, 0) for k in ["IPC anual", "IPC Núcleo anual", "PCE anual", "PCE Núcleo anual"])
    ativ = sum(mapa.get(k, 0) for k in ["ISM Industrial", "ISM Serviços"])
    if infl * ativ < 0 and abs(infl) > 0.5 and abs(ativ) > 0.5:
        conflitos.append("Inflação e atividade apontam direções diferentes")

    if conflitos:
        confirmacao = "⚠️ Sinais mistos — " + "; ".join(conflitos)
    elif positivos >= 2 and negativos == 0:
        confirmacao = "✅ Dados confirmam força do USD"
    elif negativos >= 2 and positivos == 0:
        confirmacao = "🔴 Dados confirmam fraqueza do USD"
    else:
        confirmacao = "⚪ Leitura mista / parcial"

    return {
        "ajuste": ajuste,
        "score_ajustado": score_ajustado,
        "confirmação": confirmacao,
        "positivos": positivos,
        "negativos": negativos,
    }

# =========================================================
# HISTÓRICO E TESTE HISTÓRICO
# =========================================================

def salvar_snapshot(df):
    hoje = pd.Timestamp(datetime.now().date())
    snap = df[["Código", "Pontuação_Macro", "Influência_Fed", "Pontuação_Final"]].copy()
    snap["data"] = hoje
    try:
        hist = pd.read_parquet(HIST_SCORES)
        if (pd.to_datetime(hist["data"]).dt.date == hoje.date()).any():
            return "⚠️ Já existe um registro de hoje."
        hist = pd.concat([hist, snap], ignore_index=True)
    except Exception:
        hist = snap
    hist.to_parquet(HIST_SCORES, index=False)
    return "✅ Registro salvo."


def carregar_snapshots():
    try:
        return pd.read_parquet(HIST_SCORES)
    except Exception:
        return pd.DataFrame()


def registrar_sinal(par, confianca, s_base, s_cotada, preco, horas):
    linha = pd.DataFrame([{
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "data": pd.Timestamp.now(),
        "par": par,
        "confianca_base": float(confianca),
        "score_base": float(s_base),
        "score_cotada": float(s_cotada),
        "preco_entrada": float(preco),
        "horizonte": int(horas),
        "preco_saida": np.nan,
        "resultado": np.nan,
    }])
    try:
        hist = pd.concat([pd.read_parquet(HIST_SINAIS), linha], ignore_index=True)
    except Exception:
        hist = linha
    hist.to_parquet(HIST_SINAIS, index=False)


def carregar_sinais():
    try:
        return pd.read_parquet(HIST_SINAIS)
    except Exception:
        return pd.DataFrame()


def atualizar_resultado(id_sinal, saida):
    hist = carregar_sinais()
    if hist.empty or id_sinal not in hist["id"].astype(str).values:
        return "Sinal não encontrado."

    mascara = hist["id"].astype(str) == id_sinal
    entrada = float(hist.loc[mascara, "preco_entrada"].iloc[0])
    confianca = float(hist.loc[mascara, "confianca_base"].iloc[0])
    previsto_alta = confianca >= 0.5
    realizado_alta = saida > entrada
    hist.loc[mascara, "preco_saida"] = saida
    hist.loc[mascara, "resultado"] = 1.0 if previsto_alta == realizado_alta else 0.0
    hist.to_parquet(HIST_SINAIS, index=False)
    return "✅ Resultado atualizado."


def metricas_backtest(hist):
    validos = hist.dropna(subset=["resultado", "confianca_base"])
    if validos.empty:
        return None
    acuracia = float(validos["resultado"].astype(float).mean())
    p = np.where(
        validos["confianca_base"] >= 0.5,
        validos["confianca_base"],
        1 - validos["confianca_base"],
    )
    brier = float(np.mean((p - validos["resultado"].astype(float)) ** 2))
    return {"n": len(validos), "acuracia": acuracia, "brier": brier}

# =========================================================
# EXECUÇÃO PRINCIPAL
# =========================================================

macro_eua = carregar_macro_eua()
fed = carregar_narrativa_fed()
dados_moedas = carregar_dados_moedas()
ranking = calcular_ranking(dados_moedas, macro_eua, fed)
usd_detalhado = score_usd_detalhado(macro_eua, fed)
qualidade_usd, qualidade_rotulo = qualidade_dados_usd()

st.title("USD Macro Pro")
st.caption("V11.0.8 · Força auditável · coleta com orçamento diário")
st.caption("Macro semanal → Macro do dia → W1/D1 → Quarterly → Liquidez → Killzones → H4/H1/M15 → Performance real")

icone_tom = {"Restritivo": "🔴", "Flexível": "🟢", "Neutro": "⚪"}.get(fed["tom"], "⚪")
st.info(
    f"Fed narrativo: {icone_tom} **{fed['tom']}** | "
    f"Intensidade: {fed['forca']:+.2f}"
)

if st.session_state.get("v77_fomc_integrado", False):
    _v77_top_score = float(st.session_state.get("v76_fomc_usd_score", 50.0))
    _v77_top_peso = float(st.session_state.get("v77_peso_fomc", 0.0)) * 100.0
    _v77_top_usd = float(st.session_state.get("v77_usd_pos_fomc", 50.0))
    st.success(
        f"🔗 **FOMC V7.7 integrado ao USD:** "
        f"Score FOMC {_v77_top_score:.0f}/100 | "
        f"Peso {_v77_top_peso:.0f}% | "
        f"USD integrado {_v77_top_usd:.1f}/100"
    )
else:
    st.caption(
        "🔗 V7.7: o FOMC calibrado será conectado automaticamente ao USD "
        "quando o próximo evento relevante for uma reunião do FOMC."
    )

# =========================================================
# V7.4 — MODO HÍBRIDO INTELIGENTE
# =========================================================

def _mapear_evento_para_indicador_v74(evento):
    if not evento:
        return None
    nome = _normalizar_texto_v73(evento.get("evento", "") if isinstance(evento, dict) else str(evento))
    regras = [
        (["core pce", "pce nucleo"], "PCE Núcleo anual"),
        (["pce"], "PCE anual"),
        (["core cpi", "ipc nucleo"], "IPC Núcleo anual"),
        (["cpi", "ipc"], "IPC anual"),
        (["payroll", "employment situation", "nfp"], "Payroll"),
        (["ism manufacturing", "ism industrial"], "ISM Industrial"),
        (["ism services", "ism servicos"], "ISM Serviços"),
    ]
    for termos, indicador in regras:
        if any(t in nome for t in termos):
            return indicador
    return None

def _ultimo_real_oficial_v74(indicador):
    """Valor realizado mais recente/compatível usando FRED quando disponível."""
    sid = AUTO_SERIES_V71.get(indicador)
    obs = _fred_obs_v71(sid, 15) if sid else []
    if not obs:
        return None, None

    if indicador in ("IPC anual","IPC Núcleo anual","PCE anual","PCE Núcleo anual"):
        if len(obs) < 13:
            return None, None
        # observações vêm desc; cálculo YoY do ponto mais recente
        atual = obs[0][1] / obs[12][1] * 100.0 - 100.0
        return float(atual), obs[0][0]

    if indicador == "Payroll":
        if len(obs) < 2:
            return None, None
        return float(obs[0][1] - obs[1][1]), obs[0][0]

    return float(obs[0][1]), obs[0][0]

def _painel_hibrido_v74():
    st.markdown("## 🤖 Modo Híbrido Inteligente — V7.4")
    st.caption(
        "O app busca automaticamente o que existe em fonte oficial. "
        "Você só informa o consenso quando ele não estiver disponível gratuitamente."
    )

    evento = _proximo_evento_macro_v65()
    indicador = _mapear_evento_para_indicador_v74(evento)

    if not evento:
        st.info("Nenhum evento macro principal localizado no calendário atual.")
        return

    nome_evento = evento.get("evento", "Evento macro")
    data_evento = evento.get("data")
    dias = evento.get("dias", None)

    c1,c2,c3 = st.columns(3)
    c1.metric("Próximo evento", nome_evento)
    c2.metric("Data", data_evento.strftime("%d/%m/%Y") if hasattr(data_evento, "strftime") else str(data_evento))
    c3.metric("Faltam", f"{dias} dia(s)" if dias is not None else "—")

    if indicador is None:
        if "fomc" in _normalizar_texto_v73(nome_evento):
            st.info(
                "Próximo evento é FOMC. A expectativa continua no módulo probabilístico "
                "Corte / Manutenção / Alta; o calendário e Fed Funds são automáticos."
            )
        else:
            st.info("Evento identificado, mas ainda não há mapeamento para consenso híbrido.")
        return

    anterior, data_ant = _auto_anterior_v71(indicador)
    real, data_real = _ultimo_real_oficial_v74(indicador)

    key_cons = f"v74_consenso_{indicador}"
    if key_cons not in st.session_state:
        # reaproveita consenso já digitado em outros módulos, se existir
        st.session_state[key_cons] = float(
            st.session_state.get(f"v66_previsao_{indicador}",
            st.session_state.get(f"previsao_{indicador}", 0.0))
        )

    st.markdown(f"### 📌 {indicador}")
    a,b,c = st.columns(3)
    a.metric("Anterior 🤖", f"{anterior:.2f}" if anterior is not None else "—")
    with b:
        consenso = st.number_input(
            "Consenso ✍️",
            key=key_cons,
            step=1.0 if indicador == "Payroll" else 0.1,
            help="Este é o único número que pode precisar ser digitado manualmente."
        )
    c.metric("Último real oficial 🤖", f"{real:.2f}" if real is not None else "—")

    if anterior is not None:
        st.caption(f"Anterior automático — referência FRED: {data_ant.strftime('%d/%m/%Y') if data_ant is not None else '—'}")
    if real is not None:
        st.caption(f"Último valor oficial disponível: {data_real.strftime('%d/%m/%Y') if data_real is not None else '—'}")

    # Sincroniza consenso para os motores existentes, sem mexer em widgets já instanciados.
    st.session_state["v74_indicador_ativo"] = indicador
    st.session_state["v74_consenso_ativo"] = float(consenso)
    st.session_state["v74_tem_consenso"] = abs(float(consenso)) > 1e-12

    if not st.session_state["v74_tem_consenso"]:
        st.warning("Preencha somente o CONSENSO. O restante permanece automático.")
        return

    # Pré-release: consenso x anterior
    maior_favorece = indicador != "Desemprego"
    if anterior is not None:
        pre = _expectativa_indicador_v66(indicador, float(consenso), float(anterior), maior_favorece)
        st.write(f"**Leitura pré-release:** {pre['leitura']}")

    # Detecta automaticamente se o 'real' oficial é posterior ao anterior e permite cálculo.
    if real is not None and data_real is not None and data_ant is not None and data_real > data_ant:
        delta = float(real) - float(consenso)
        if not maior_favorece:
            delta = -delta
        if delta > 0:
            leitura = "🟢 Real acima do consenso → favorece USD"
        elif delta < 0:
            leitura = "🔴 Real abaixo do consenso → desfavorece USD"
        else:
            leitura = "⚪ Real em linha com o consenso"
        st.success(f"**Pós-release automático:** {leitura} · surpresa ajustada = {delta:+.2f}")
    else:
        st.info("Aguardando a próxima divulgação oficial. Após a atualização da FRED, o Real será atualizado automaticamente.")

    st.caption(
        "Regra de segurança: o app nunca cria um consenso. Se não houver API gratuita confiável, "
        "esse único campo permanece manual."
    )



# =========================================================
# V7.8 — EXPLICADOR DO SINAL
# =========================================================

def _classificar_forca_v78(score):
    try:
        s = float(score)
    except Exception:
        return "indisponível"
    if s >= 70:
        return "forte"
    if s >= 58:
        return "moderada"
    if s <= 30:
        return "fraca"
    if s <= 42:
        return "moderadamente fraca"
    return "neutra"

def _direcao_par_v78(par, diferenca):
    """
    diferenca esperada = força base - força cotada.
    >0 favorece BUY do par; <0 favorece SELL.
    """
    try:
        d = float(diferenca)
    except Exception:
        return "WAIT"
    if d >= 8:
        return "BUY"
    if d <= -8:
        return "SELL"
    return "WAIT"

def _explicar_sinal_v78(par, moeda_base, moeda_cotada, score_base, score_cotada,
                        diferenca, confluencia=None, qualidade=None, timing=None,
                        score_mestre=None, risco_calendario=None):
    direcao = _direcao_par_v78(par, diferenca)

    fatores_favor = []
    fatores_contra = []
    observacoes = []

    # Força relativa
    try:
        sb = float(score_base)
        sc = float(score_cotada)
        df = float(diferenca)
        if df >= 8:
            fatores_favor.append(
                f"{moeda_base} está mais forte que {moeda_cotada} ({sb:.1f} vs {sc:.1f})"
            )
        elif df <= -8:
            fatores_favor.append(
                f"{moeda_cotada} está mais forte que {moeda_base} ({sc:.1f} vs {sb:.1f})"
            )
        else:
            observacoes.append(
                f"Força relativa ainda próxima ({sb:.1f} vs {sc:.1f})"
            )
    except Exception:
        pass

    # FOMC integrado
    if st.session_state.get("v77_fomc_integrado", False):
        fomc_score = float(st.session_state.get("v76_fomc_usd_score", 50.0))
        peso = float(st.session_state.get("v77_peso_fomc", 0.0)) * 100.0
        if "USD" in (moeda_base, moeda_cotada):
            if fomc_score >= 55:
                texto = f"FOMC está levemente hawkish para o USD ({fomc_score:.0f}/100, peso {peso:.0f}%)"
                if (direcao == "BUY" and moeda_base == "USD") or (direcao == "SELL" and moeda_cotada == "USD"):
                    fatores_favor.append(texto)
                else:
                    fatores_contra.append(texto)
            elif fomc_score <= 45:
                texto = f"FOMC está levemente dovish para o USD ({fomc_score:.0f}/100, peso {peso:.0f}%)"
                if (direcao == "SELL" and moeda_base == "USD") or (direcao == "BUY" and moeda_cotada == "USD"):
                    fatores_favor.append(texto)
                else:
                    fatores_contra.append(texto)
            else:
                observacoes.append(f"FOMC está neutro para o USD ({fomc_score:.0f}/100)")

    # Qualidade
    try:
        q = float(qualidade)
        if q >= 80:
            fatores_favor.append(f"Qualidade dos dados está alta ({q:.0f}%)")
        elif q < 60:
            fatores_contra.append(f"Qualidade dos dados está baixa ({q:.0f}%)")
        else:
            observacoes.append(f"Qualidade dos dados está moderada ({q:.0f}%)")
    except Exception:
        pass

    # Timing
    try:
        t = float(timing)
        if t >= 70:
            fatores_favor.append(f"Timing está favorável ({t:.0f}/100)")
        elif t < 50:
            fatores_contra.append(f"Timing está fraco ({t:.0f}/100)")
        else:
            observacoes.append(f"Timing ainda está intermediário ({t:.0f}/100)")
    except Exception:
        pass

    # Risco calendário
    if risco_calendario:
        rc = str(risco_calendario).upper()
        if any(x in rc for x in ("MÁXIMO", "MAXIMO", "ALTO", "ATENÇÃO", "ATENCAO")):
            fatores_contra.append(f"Risco de calendário elevado: {risco_calendario}")
        elif "BAIX" in rc:
            fatores_favor.append("Risco de calendário está baixo")

    # Score mestre
    try:
        sm = float(score_mestre)
        if sm >= 80:
            observacoes.append(f"Score Mestre forte ({sm:.0f}/100)")
        elif sm >= 65:
            observacoes.append(f"Score Mestre moderado ({sm:.0f}/100)")
        else:
            fatores_contra.append(f"Score Mestre ainda fraco ({sm:.0f}/100)")
    except Exception:        pass

    # Conclusão textual
    if direcao == "WAIT":
        conclusao = (
            f"⏸️ **WAIT em {par}** — ainda não há diferença suficiente entre as moedas "
            "para justificar uma direção clara."
        )
    elif direcao == "BUY":
        conclusao = (
            f"🟢 **BUY {par}** — o conjunto atual favorece {moeda_base} sobre {moeda_cotada}."
        )
    else:
        conclusao = (
            f"🔴 **SELL {par}** — o conjunto atual favorece {moeda_cotada} sobre {moeda_base}."
        )

    return {
        "direcao": direcao,
        "favor": fatores_favor,
        "contra": fatores_contra,
        "observacoes": observacoes,
        "conclusao": conclusao,
    }

def _painel_explicador_v78(par, moeda_base, moeda_cotada, score_base, score_cotada,
                           diferenca, confluencia=None, qualidade=None, timing=None,
                           score_mestre=None, risco_calendario=None):
    st.markdown("## 🧠 Por que o sistema está dando esse sinal? — V7.8.2")

    exp = _explicar_sinal_v78(
        par=par,
        moeda_base=moeda_base,
        moeda_cotada=moeda_cotada,
        score_base=score_base,
        score_cotada=score_cotada,
        diferenca=diferenca,
        confluencia=confluencia,
        qualidade=qualidade,
        timing=timing,
        score_mestre=score_mestre,
        risco_calendario=risco_calendario,
    )

    st.markdown(exp["conclusao"])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### ✅ O que ajuda o sinal")
        if exp["favor"]:
            for item in exp["favor"]:
                st.write(f"• {item}")
        else:
            st.write("• Nenhum fator forte adicional identificado.")

    with c2:
        st.markdown("### ⚠️ O que atrapalha o sinal")
        if exp["contra"]:
            for item in exp["contra"]:
                st.write(f"• {item}")
        else:
            st.write("• Nenhum fator contrário forte identificado.")

    if exp["observacoes"]:
        st.markdown("### ℹ️ Pontos de atenção")
        for item in exp["observacoes"]:
            st.write(f"• {item}")

    # O que faria o sinal mudar
    st.markdown("### 🔄 O que faria o sinal mudar?")
    if exp["direcao"] == "SELL":
        st.write(
            f"• {moeda_base} precisaria ganhar força ou {moeda_cotada} perder força.\n"
            f"• O FOMC/Fed poderia ficar menos favorável à moeda atualmente dominante.\n"
            f"• O timing e a qualidade precisariam deteriorar para enfraquecer a venda."
        )
    elif exp["direcao"] == "BUY":
        st.write(
            f"• {moeda_base} precisaria perder força ou {moeda_cotada} ganhar força.\n"
            f"• O FOMC/Fed poderia ficar menos favorável à moeda atualmente dominante.\n"
            f"• O timing e a qualidade precisariam deteriorar para enfraquecer a compra."
        )
    else:
        st.write(
            "• Uma das moedas precisa abrir vantagem clara de força.\n"
            "• Confluência, timing e qualidade precisam sair da zona neutra.\n"
            "• Um evento macro importante pode ser o gatilho dessa mudança."
        )

    st.caption(
        "V7.8 explica o sinal usando apenas os dados e scores já existentes no aplicativo. "
        "Ele não cria uma nova probabilidade de lucro e não substitui confirmação técnica."
    )




# =========================================================
# V7.9 — RAIO-X COMPLETO DO SINAL
# =========================================================

def _raiox_v79(par, base, cotada, score_base, score_cotada, diferenca, confl):
    st.markdown("## 🔬 Raio-X completo do sinal — V7.9")

    direcao = "WAIT"
    if diferenca >= 6:
        direcao = "BUY"
    elif diferenca <= -6:
        direcao = "SELL"

    linhas = []
    for nome, estado, peso, fator, peso_eff in confl.get("linhas_dinamicas", []):
        if estado > 0:
            leitura = "🟢 A favor"
        elif estado < 0:
            leitura = "🔴 Contra"
        else:
            leitura = "⚪ Neutro"
        linhas.append({
            "Componente": nome,
            "Leitura": leitura,
            "Peso nominal": f"{peso:.0f}%",
            "Qualidade": f"{fator*100:.0f}%",
            "Peso efetivo": f"{peso_eff:.1f}%"
        })

    if linhas:
        st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)

    # Bloco juros
    dt = confl.get("diferencial_taxas", {})
    m3 = confl.get("mercado_3m", {})
    tend = confl.get("tendencias", {})

    st.markdown("### 🏦 Juros e política monetária")
    a,b,c = st.columns(3)
    if dt.get("base") is not None and dt.get("cotada") is not None:
        a.metric("Diferencial oficial", f"{dt.get('dif',0):+.2f} p.p.")
        a.caption(f"Vantagem: {dt.get('vantagem','—')}")
    else:
        a.metric("Diferencial oficial", "—")

    if m3.get("disponivel"):
        b.metric("Spread mercado 3M", f"{m3.get('spread',0):+.2f} p.p.")
        b.caption(f"{m3.get('vantagem','—')} · {m3.get('movimento','—')}")
    else:
        b.metric("Spread mercado 3M", "—")

    if st.session_state.get("v77_fomc_integrado", False) and "USD" in (base, cotada):
        fs = float(st.session_state.get("v76_fomc_usd_score", 50))
        fp = float(st.session_state.get("v77_peso_fomc", 0))*100
        c.metric("FOMC/USD", f"{fs:.0f}/100")
        c.caption(f"Peso integrado: {fp:.0f}%")
    else:
        c.metric("FOMC/USD", "—")

    # Tendência macro
    st.markdown("### 📊 Tendência macro")
    rows = []
    for nome in ["CPI","Core CPI","Desemprego","Treasury 2Y","Broad USD"]:
        x = tend.get(nome)
        if isinstance(x, dict):
            rows.append({
                "Indicador": nome,
                "Tendência": x.get("texto","—"),
                "Variação média": round(float(x.get("delta",0)),4)
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    score = float(confl.get("score_confluencia", 50))
    qualidade = float(confl.get("qualidade_confluencia", 0))
    nivel = str(confl.get("nivel","BAIXA"))

    # Próximo evento / risco
    evento = _proximo_evento_macro_v65()
    nome_evento = "—"
    dias = None
    impacto = "—"
    if isinstance(evento, dict) and evento.get("disponivel", False):
        nome_evento = str(evento.get("evento","—"))
        dias = evento.get("dias")
        impacto = str(evento.get("impacto","—"))

    st.markdown("### 📅 Risco e timing")
    r1,r2,r3 = st.columns(3)
    r1.metric("Próximo evento", nome_evento)
    r2.metric("Faltam", f"{dias} dia(s)" if dias is not None else "—")
    r3.metric("Impacto", impacto)

    # Conclusão operacional, sem chamar score de probabilidade.
    if direcao == "WAIT" or score < 58 or qualidade < 50:
        acao = "⏸️ AGUARDAR"
        motivo = "a vantagem macro/confluência ainda não é suficiente."
    elif direcao == "BUY":
        acao = f"🟢 BUY {par}"
        motivo = f"{base} possui vantagem macro sobre {cotada}."
    else:
        acao = f"🔴 SELL {par}"
        motivo = f"{cotada} possui vantagem macro sobre {base}."

    if dias is not None and dias <= 2 and impacto.upper() in ("MÁXIMO","MAXIMO","ALTO"):
        timing_txt = "⚠️ Evento de alto impacto muito próximo — aguardar confirmação de preço/estrutura."
    elif dias is not None and dias <= 7 and impacto.upper() in ("MÁXIMO","MAXIMO","ALTO"):
        timing_txt = "🟡 Direção macro válida, mas há evento importante próximo."
    else:
        timing_txt = "🟢 Calendário não bloqueia a leitura macro neste momento."

    st.markdown("### 🎯 Conclusão operacional")
    st.info(
        f"**{acao}** — {motivo}\n\n"
        f"**Confluência:** {nivel} · Score {score:.0f}/100 · Qualidade {qualidade:.0f}%\n\n"
        f"**Timing:** {timing_txt}"
    )

    # Principal motor: maior peso efetivo não-neutro
    ativos = [
        (nome, estado, peso_eff)
        for nome, estado, peso, fator, peso_eff in confl.get("linhas_dinamicas", [])
        if estado != 0
    ]
    if ativos:
        principal = max(ativos, key=lambda x: abs(float(x[2])))
        st.caption(
            f"Principal componente ativo: {principal[0]} "
            f"(peso efetivo {float(principal[2]):.1f}%)."
        )

    st.warning(
        "O Raio-X é uma leitura macro e de confluência. "
        "Não é previsão garantida nem gatilho de entrada. Confirme preço, estrutura, liquidez e gestão de risco."
    )



# =========================================================
# V8.0 — CENTRAL DE DECISÃO FOREX
# Consolida direção, confluência, qualidade, FOMC, risco e ação.
# =========================================================

def _central_decisao_v80(par, base, cotada, score_base, score_cotada, diferenca, confl):
    score = float(confl.get("score_confluencia", 50.0))
    qualidade = float(confl.get("qualidade_confluencia", 0.0))
    nivel = str(confl.get("nivel", "BAIXA"))

    if diferenca >= 6:
        direcao = "BUY"
        dominante = base
    elif diferenca <= -6:
        direcao = "SELL"
        dominante = cotada
    else:
        direcao = "WAIT"
        dominante = "—"

    evento = _proximo_evento_macro_v65()
    evento_nome, dias, impacto = "—", None, "—"
    if isinstance(evento, dict) and evento.get("disponivel", False):
        evento_nome = str(evento.get("evento", "—"))
        dias = evento.get("dias")
        impacto = str(evento.get("impacto", "—"))

    fomc_score = None
    fomc_peso = 0.0
    if st.session_state.get("v77_fomc_integrado", False) and "USD" in (base, cotada):
        fomc_score = float(st.session_state.get("v76_fomc_usd_score", 50.0))
        fomc_peso = float(st.session_state.get("v77_peso_fomc", 0.0)) * 100.0

    # Timing conservador baseado no calendário.
    alto_impacto = impacto.upper() in ("MÁXIMO", "MAXIMO", "ALTO")
    if dias is not None and dias <= 2 and alto_impacto:
        timing = "BLOQUEADO / AGUARDAR"
        timing_score = 35
    elif dias is not None and dias <= 7 and alto_impacto:
        timing = "ATENÇÃO"
        timing_score = 58
    else:
        timing = "NORMAL"
        timing_score = 75

    # Decisão final: direção macro não é entrada.
    if direcao == "WAIT" or score < 58 or qualidade < 50:
        decisao = "AGUARDAR"
        status = "⚪"
    elif timing_score < 50:
        decisao = "DIREÇÃO VÁLIDA — AGUARDAR EVENTO/CONFIRMAÇÃO"
        status = "🟡"
    elif timing_score < 65:
        decisao = "DIREÇÃO VÁLIDA — AGUARDAR CONFIRMAÇÃO TÉCNICA"
        status = "🟡"
    else:
        decisao = "DIREÇÃO MACRO VÁLIDA — BUSCAR GATILHO TÉCNICO"
        status = "🟢"

    # Principal componente ativo pelo peso efetivo.
    ativos = []
    for nome, estado, peso, fator, peso_eff in confl.get("linhas_dinamicas", []):
        if estado != 0:
            ativos.append((nome, estado, float(peso_eff)))
    principal = max(ativos, key=lambda x: abs(x[2])) if ativos else None

    st.markdown("## 🎛️ Central de Decisão Forex — V8.0")

    # Linha principal
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Par", par)
    c2.metric("Direção macro", direcao)
    c3.metric("Score Mestre", f"{score:.0f}/100")
    c4.metric("Qualidade", f"{qualidade:.0f}%")

    # Segunda linha
    d1,d2,d3,d4 = st.columns(4)
    d1.metric(base, f"{score_base:.1f}/100")
    d2.metric(cotada, f"{score_cotada:.1f}/100")
    d3.metric("Diferença", f"{diferenca:+.1f}")
    d4.metric("Confluência", nivel)

    # FOMC / calendário
    st.markdown("### 🏦 Catalisador e risco")
    e1,e2,e3,e4 = st.columns(4)
    e1.metric("FOMC/USD", f"{fomc_score:.0f}/100" if fomc_score is not None else "—")
    e2.metric("Peso FOMC", f"{fomc_peso:.0f}%" if fomc_score is not None else "—")
    e3.metric("Próximo evento", evento_nome)
    e4.metric("Timing", timing)

    if dias is not None:
        st.caption(f"Calendário: {evento_nome} em {dias} dia(s) · impacto {impacto}.")

    # Motivo principal
    if principal:
        nome_p, estado_p, peso_p = principal
        sentido_p = "a favor" if estado_p > 0 else "contra"
        st.info(
            f"🔎 **Principal motor do sinal:** {nome_p} — {sentido_p} "
            f"(peso efetivo {peso_p:.1f}%)."
        )

    # Resumo causal simples
    if direcao == "SELL":
        resumo = f"{cotada} está dominando {base}; o conjunto macro favorece venda de {par}."
    elif direcao == "BUY":
        resumo = f"{base} está dominando {cotada}; o conjunto macro favorece compra de {par}."
    else:
        resumo = f"{base} e {cotada} ainda não apresentam vantagem macro suficiente."

    st.markdown("### 🎯 Decisão")
    if status == "🟢":
        st.success(f"{status} **{decisao}**\n\n{resumo}")
    elif status == "🟡":
        st.warning(f"{status} **{decisao}**\n\n{resumo}")
    else:
        st.info(f"{status} **{decisao}**\n\n{resumo}")

    st.markdown(
        "**Fluxo operacional:** Macro → próximo evento → risco → timing → "
        "preço/estrutura → gestão."
    )
    st.caption(
        "Score Mestre é uma pontuação interna de alinhamento, não probabilidade de lucro. "
        "A Central V8.0 não envia ordem e não substitui confirmação técnica."
    )



# =========================================================
# V8.1 — ACABAMENTO DA CENTRAL DE DECISÃO
# =========================================================

def _central_decisao_v81(par, base, cotada, score_base, score_cotada, diferenca, confl):
    score = float(confl.get("score_confluencia", 50.0))
    qualidade = float(confl.get("qualidade_confluencia", 0.0))

    if diferenca >= 6:
        direcao = "BUY"
        dominante = base
    elif diferenca <= -6:
        direcao = "SELL"
        dominante = cotada
    else:
        direcao = "WAIT"
        dominante = "—"

    # Confluência visual coerente com score + cobertura.
    if score >= 80 and qualidade >= 80:
        alinhamento = "FORTE"
    elif score >= 70 and qualidade >= 60:
        alinhamento = "FORTE / QUALIDADE MODERADA"
    elif score >= 58 and qualidade >= 50:
        alinhamento = "MODERADO"
    else:
        alinhamento = "FRACO"

    evento = _proximo_evento_macro_v65()
    evento_nome, dias, impacto = "—", None, "—"
    if isinstance(evento, dict) and evento.get("disponivel", False):
        evento_nome = str(evento.get("evento", "—"))
        dias = evento.get("dias")
        impacto = str(evento.get("impacto", "—"))

    fomc_score = None
    fomc_peso = 0.0
    if st.session_state.get("v77_fomc_integrado", False) and "USD" in (base, cotada):
        fomc_score = float(st.session_state.get("v76_fomc_usd_score", 50.0))
        fomc_peso = float(st.session_state.get("v77_peso_fomc", 0.0)) * 100.0

    alto = impacto.upper() in ("MÁXIMO", "MAXIMO", "ALTO")
    if dias is not None and dias <= 2 and alto:
        timing = "AGUARDAR"
        timing_score = 35
    elif dias is not None and dias <= 7 and alto:
        timing = "ATENÇÃO"
        timing_score = 58
    else:
        timing = "NORMAL"
        timing_score = 75

    if direcao == "WAIT" or score < 58 or qualidade < 50:
        decisao = "AGUARDAR"
        cor = "info"
    elif timing_score < 50:
        decisao = f"{direcao} MACRO — AGUARDAR EVENTO"
        cor = "warning"
    elif timing_score < 65:
        decisao = f"{direcao} MACRO — AGUARDAR CONFIRMAÇÃO"
        cor = "warning"
    else:
        decisao = f"{direcao} MACRO — BUSCAR GATILHO TÉCNICO"
        cor = "success"

    ativos = [
        (nome, estado, float(peso_eff))
        for nome, estado, peso, fator, peso_eff in confl.get("linhas_dinamicas", [])
        if estado != 0
    ]
    principal = max(ativos, key=lambda x: abs(x[2])) if ativos else None

    st.markdown("## 🎛️ Central de Decisão Forex — V8.1")

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Par", par)
    c2.metric("Direção macro", direcao)
    c3.metric("Score Mestre", f"{score:.0f}/100")
    c4.metric("Qualidade / cobertura", f"{qualidade:.0f}%")

    d1,d2,d3,d4 = st.columns(4)
    d1.metric(base, f"{score_base:.1f}/100")
    d2.metric(cotada, f"{score_cotada:.1f}/100")
    d3.metric("Diferença", f"{diferenca:+.1f}")
    d4.metric("Alinhamento", alinhamento)

    st.markdown("### 🏦 Catalisador e risco")
    e1,e2,e3 = st.columns(3)
    e1.metric("FOMC/USD", f"{fomc_score:.0f}/100" if fomc_score is not None else "—")
    e2.metric("Peso FOMC", f"{fomc_peso:.0f}%" if fomc_score is not None else "—")
    e3.metric("Timing", timing)

    # Evento em linha própria para evitar truncamento.
    if dias is not None:
        st.info(
            f"📅 **Próximo evento:** {evento_nome}  |  "
            f"**Faltam:** {dias} dia(s)  |  **Impacto:** {impacto}"
        )
    else:
        st.info(f"📅 **Próximo evento:** {evento_nome}")

    if principal:
        nome_p, estado_p, peso_p = principal
        sentido = "A FAVOR" if estado_p > 0 else "CONTRA"
        st.caption(
            f"Principal motor: {nome_p} · {sentido} · peso efetivo {peso_p:.1f}%."
        )

    st.markdown("### 🎯 Decisão final")
    resumo = (
        f"{dominante} é a moeda dominante no modelo."
        if dominante != "—" else
        "Nenhuma moeda possui vantagem suficiente."
    )
    mensagem = (
        f"**{decisao}**\n\n"
        f"{resumo}  |  Score {score:.0f}/100  |  "
        f"Qualidade {qualidade:.0f}%  |  Timing {timing}."
    )
    if cor == "success":
        st.success(mensagem)
    elif cor == "warning":
        st.warning(mensagem)
    else:
        st.info(mensagem)

    # Semáforo final bem simples.
    st.markdown("### 🚦 Leitura rápida")
    s1,s2,s3 = st.columns(3)
    s1.metric("DIREÇÃO", direcao)
    s2.metric("TIMING", timing)
    if timing_score >= 65 and direcao != "WAIT":
        acao_curta = "BUSCAR GATILHO"
    else:
        acao_curta = "AGUARDAR"
    s3.metric("AÇÃO", acao_curta)

    st.caption(
        "Score Mestre mede alinhamento interno; Qualidade/cobertura mede a confiança nos dados disponíveis. "
        "Nenhum deles representa probabilidade de lucro."
    )



# =========================================================
# V8.2 — VALIDAÇÃO HISTÓRICA / TESTE DE SINAIS
# Registra sinais no momento em que acontecem e avalia depois
# usando preço diário oficial do FRED (DEXUSEU) para EUR/USD.
# Não reconstrói sinais antigos com dados de hoje.
# =========================================================

ARQ_SINAIS_V82 = "dados/sinais_v82.parquet"

def _dia_coleta_v873():
    """Dia civil da coleta no fuso de Cuiabá."""
    try:
        return pd.Timestamp.now(tz="America/Cuiaba").strftime("%Y-%m-%d")
    except Exception:
        return pd.Timestamp.now().strftime("%Y-%m-%d")

def _garantir_pasta_v82():
    try:
        Path("dados").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _normalizar_tipos_sinais_v1072(df):
    """
    V10.7.2 — compatibilidade robusta com pandas 2.x.

    O CSV histórico pode chegar com colunas vazias inferidas como float64.
    Isso quebra quando o app tenta gravar Timestamp/boolean nessas colunas.
    Aqui os tipos são normalizados antes de qualquer atualização.
    """
    df = df.copy()

    # Datas: sempre UTC, inclusive quando a origem veio como string/float vazia.
    for col in ("timestamp", "data_preco", "data_saida"):
        if col not in df.columns:
            df[col] = pd.NaT
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    # Numéricos: força float seguro.
    for col in (
        "score_mestre", "qualidade", "score_base", "score_cotada",
        "diferenca", "fomc_score", "fomc_peso", "dias_evento",
        "preco_entrada", "preco_saida", "retorno_pct",
        "retorno_direcional_pct"
    ):
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # avaliado: ausência deve significar False, nunca bool(np.nan)==True.
    if "avaliado" not in df.columns:
        df["avaliado"] = False
    _av = df["avaliado"]
    df["avaliado"] = _av.map(
        lambda x: (
            True if str(x).strip().lower() in ("true", "1", "sim", "yes")
            else False
        )
    ).astype(bool)

    # acertou: preserva ausente como None e aceita bases antigas em texto/número.
    if "acertou" not in df.columns:
        df["acertou"] = None

    def _bool_ou_none_v1072(x):
        if pd.isna(x) or str(x).strip().lower() in ("", "none", "nan", "nat"):
            return None
        s = str(x).strip().lower()
        if s in ("true", "1", "sim", "yes"):
            return True
        if s in ("false", "0", "nao", "não", "no"):
            return False
        return None

    df["acertou"] = df["acertou"].map(_bool_ou_none_v1072).astype("object")

    # Texto: evita NaN quebrando comparações e exibição.
    for col in (
        "par", "direcao", "evento", "impacto", "timing",
        "versao_coleta", "dia_coleta", "horizonte_validacao", "serie_saida"
    ):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    return df


def _carregar_sinais_v82():
    """
    V8.7.3 — carrega histórico persistente e separa registros antigos.
    Tudo que não tiver versão explícita passa a ser LEGADO.
    """
    _garantir_pasta_v82()

    def _normalizar_v873(df):
        df = df.copy()
        if "versao_coleta" not in df.columns:
            df["versao_coleta"] = "LEGADO"
        else:
            df["versao_coleta"] = df["versao_coleta"].fillna("LEGADO").replace("", "LEGADO")
        if "dia_coleta" not in df.columns:
            df["dia_coleta"] = ""
        else:
            df["dia_coleta"] = df["dia_coleta"].fillna("").astype(str)
        return _normalizar_tipos_sinais_v1072(df)

    if "_github_ler_csv_v84" in globals():
        remoto = _github_ler_csv_v84()
        if isinstance(remoto, pd.DataFrame) and not remoto.empty:
            return _normalizar_v873(remoto)

    p = Path(ARQ_SINAIS_V82)
    if p.exists():
        try:
            return _normalizar_v873(pd.read_parquet(p))
        except Exception:
            pass

    cols = [
        "timestamp","par","direcao","score_mestre","qualidade",
        "score_base","score_cotada","diferenca","fomc_score",
        "fomc_peso","evento","dias_evento","impacto","timing",
        "preco_entrada","data_preco","avaliado","preco_saida",
        "data_saida","retorno_pct","acertou","versao_coleta","dia_coleta",
        "horizonte_validacao","retorno_direcional_pct","serie_saida"
    ]
    return pd.DataFrame(columns=cols)

def _github_cfg_v84():
    """Configuração opcional para persistência do histórico no GitHub."""
    try:
        token = st.secrets.get("GITHUB_TOKEN_HISTORICO", "")
        repo = st.secrets.get("GITHUB_REPO_HISTORICO", "aparecidomikael97-ship-it/usd-macro-pro-v4")
        branch = resolve_runtime_branch(
            st.secrets.get("GITHUB_DATA_BRANCH", os.getenv("GITHUB_DATA_BRANCH", "")),
            st.secrets.get("GITHUB_BRANCH_HISTORICO", os.getenv("GITHUB_BRANCH_HISTORICO", "")),
        )
    except Exception:
        token, repo, branch = "", "aparecidomikael97-ship-it/usd-macro-pro-v4", resolve_runtime_branch()
    return str(token).strip(), str(repo).strip(), str(branch).strip()

def _github_ler_csv_v84():
    """Lê dados/sinais_v84.csv do GitHub. Retorna None se não configurado/indisponível."""
    token, repo, branch = _github_cfg_v84()
    if not token or not repo:
        return None
    try:
        import base64, io
        url = f"https://api.github.com/repos/{repo}/contents/dados/sinais_v84.csv"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        r = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
        if r.status_code == 404:
            return pd.DataFrame()
        r.raise_for_status()
        payload = r.json()
        raw = base64.b64decode(payload["content"])
        df = pd.read_csv(io.BytesIO(raw))
        return df
    except Exception:
        return None

def _github_salvar_csv_v84(df):
    """Cria/atualiza o CSV persistente no GitHub. Retorna (ok, mensagem)."""
    token, repo, branch = _github_cfg_v84()
    if not token or not repo:
        return False, "GitHub persistente não configurado"
    try:
        import base64
        url = f"https://api.github.com/repos/{repo}/contents/dados/sinais_v84.csv"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # Descobre SHA atual para atualização segura.
        atual = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
        sha = None
        if atual.status_code == 200:
            sha = atual.json().get("sha")
        elif atual.status_code != 404:
            atual.raise_for_status()

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        body = {
            "message": "V8.4: atualizar histórico de validação",
            "content": base64.b64encode(csv_bytes).decode("ascii"),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha

        resp = requests.put(url, headers=headers, json=body, timeout=20)
        resp.raise_for_status()
        return True, "Histórico salvo no GitHub"
    except Exception as e:
        return False, f"Falha ao salvar no GitHub: {type(e).__name__}"

def _salvar_sinais_v82(df):
    """
    V8.7.3 — persistência segura:
    - LEGADO permanece guardado, mas separado;
    - V8.7.3: 1 par + 1 dia de coleta = no máximo 1 fotografia.
    """
    _garantir_pasta_v82()
    df = df.copy()

    if "versao_coleta" not in df.columns:
        df["versao_coleta"] = "LEGADO"
    df["versao_coleta"] = df["versao_coleta"].fillna("LEGADO").replace("", "LEGADO")

    if "dia_coleta" not in df.columns:
        df["dia_coleta"] = ""
    df["dia_coleta"] = df["dia_coleta"].fillna("").astype(str)

    if not df.empty:
        legados = df[df["versao_coleta"].astype(str) != "V8.7.3"].copy()
        novos = df[df["versao_coleta"].astype(str) == "V8.7.3"].copy()

        if not novos.empty:
            novos["par"] = novos["par"].astype(str).str.upper().str.strip()
            novos = novos.drop_duplicates(
                subset=["par", "dia_coleta"], keep="first"
            )

        df = pd.concat([legados, novos], ignore_index=True)

    ok_local = False
    try:
        df.to_parquet(ARQ_SINAIS_V82, index=False)
        ok_local = True
    except Exception:
        pass

    ok_git, _ = _github_salvar_csv_v84(df)
    return bool(ok_local or ok_git)

def _fred_preco_par_v87(par):
    """
    V8.7 — preço diário oficial FRED/H.10 para os 7 pares.
    As séries abaixo já estão na mesma orientação do par exibido.
    """
    series = {
        "EUR/USD": ("DEXUSEU", "USD por 1 EUR"),
        "GBP/USD": ("DEXUSUK", "USD por 1 GBP"),
        "AUD/USD": ("DEXUSAL", "USD por 1 AUD"),
        "NZD/USD": ("DEXUSNZ", "USD por 1 NZD"),
        "USD/JPY": ("DEXJPUS", "JPY por 1 USD"),
        "USD/CHF": ("DEXSZUS", "CHF por 1 USD"),
        "USD/CAD": ("DEXCAUS", "CAD por 1 USD"),
    }
    sid_info = series.get(str(par).upper())
    if not sid_info:
        return None, None, None
    sid, unidade = sid_info
    try:
        obs = _fred_obs_v71(sid, 20)
        if not obs:
            return None, None, sid
        return float(obs[0][1]), obs[0][0], sid
    except Exception:
        return None, None, sid

def _fred_primeira_observacao_posterior_v88(par, data_entrada):
    """
    Retorna a primeira observação diária FRED estritamente posterior à entrada.
    Isso fixa o horizonte da V8.8 como 'próxima observação diária disponível',
    em vez de usar simplesmente o preço mais recente.
    """
    series = {
        "EUR/USD": "DEXUSEU",
        "GBP/USD": "DEXUSUK",
        "AUD/USD": "DEXUSAL",
        "NZD/USD": "DEXUSNZ",
        "USD/JPY": "DEXJPUS",
        "USD/CHF": "DEXSZUS",
        "USD/CAD": "DEXCAUS",
    }
    sid = series.get(str(par).upper().strip())
    if not sid:
        return None, None, None

    try:
        entrada = pd.Timestamp(data_entrada).normalize()
        obs = _fred_obs_v71(sid, 120)
        candidatos = []
        for dt, valor in obs or []:
            try:
                d = pd.Timestamp(dt).normalize()
                v = float(valor)
                if d > entrada:
                    candidatos.append((d, v))
            except Exception:
                continue
        if not candidatos:
            return None, None, sid
        candidatos.sort(key=lambda x: x[0])
        d, v = candidatos[0]
        return float(v), d, sid
    except Exception:
        return None, None, sid

def _fred_preco_eurusd_v82():
    """Compatibilidade com versões anteriores."""
    preco, data, _ = _fred_preco_par_v87("EUR/USD")
    return preco, data

def _registrar_sinal_v82(par, direcao, score_mestre, qualidade,
                         score_base, score_cotada, diferenca):
    preco, dt_preco, serie_fred = _fred_preco_par_v87(par)
    if preco is None:
        return False, f"Preço oficial diário de {par} indisponível na FRED nesta execução."

    evento = _proximo_evento_macro_v65()
    evento_nome, dias, impacto = "—", None, "—"
    if isinstance(evento, dict) and evento.get("disponivel", False):
        evento_nome = str(evento.get("evento","—"))
        dias = evento.get("dias")
        impacto = str(evento.get("impacto","—"))

    fomc_score = None
    fomc_peso = None
    if st.session_state.get("v77_fomc_integrado", False):
        fomc_score = float(st.session_state.get("v76_fomc_usd_score", 50.0))
        fomc_peso = float(st.session_state.get("v77_peso_fomc", 0.0))*100.0

    alto = impacto.upper() in ("MÁXIMO","MAXIMO","ALTO")
    if dias is not None and dias <= 2 and alto:
        timing = "AGUARDAR"
    elif dias is not None and dias <= 7 and alto:
        timing = "ATENÇÃO"
    else:
        timing = "NORMAL"

    df = _carregar_sinais_v82()
    dia_coleta = _dia_coleta_v873()

    if not df.empty:
        dup = (
            (df["par"].astype(str).str.upper().str.strip() == str(par).upper().strip()) &
            (df["versao_coleta"].astype(str) == "V8.7.3") &
            (df["dia_coleta"].astype(str) == dia_coleta)
        )
        if dup.any():
            return False, (
                f"{par} já possui uma fotografia V8.7.3 em {dia_coleta}. "
                "A próxima coleta será liberada no próximo dia."
            )

    linha = {
        "timestamp": pd.Timestamp.now(),
        "par": par,
        "direcao": direcao,
        "score_mestre": float(score_mestre),
        "qualidade": float(qualidade),
        "score_base": float(score_base),
        "score_cotada": float(score_cotada),
        "diferenca": float(diferenca),
        "fomc_score": fomc_score,
        "fomc_peso": fomc_peso,
        "evento": evento_nome,
        "dias_evento": dias,
        "impacto": impacto,
        "timing": timing,
        "preco_entrada": float(preco),
        "data_preco": pd.Timestamp(dt_preco),
        "avaliado": False,
        "preco_saida": None,
        "data_saida": None,
        "retorno_pct": None,
        "acertou": None,
        "versao_coleta": "V8.7.3",
        "dia_coleta": dia_coleta,
    }
    df = pd.concat([df, pd.DataFrame([linha])], ignore_index=True)
    ok = _salvar_sinais_v82(df)
    return ok, f"Sinal registrado em {preco:.5f} (FRED {serie_fred}, {dt_preco})."


def _entrada_legada_segura_v1073(r):
    """
    V10.7.3 — protege a validação histórica contra linhas antigas/incompletas.

    pd.Timestamp(pd.NaT) não lança erro, mas NaT.strftime() lança ValueError.
    Por isso a data precisa ser testada explicitamente antes de qualquer uso.
    """
    par = str(r.get("par", "") or "").upper().strip()

    dt = pd.to_datetime(r.get("data_preco"), errors="coerce", utc=True)
    if pd.isna(dt):
        return None, None, None, "data_preco ausente/inválida"

    entrada = pd.to_numeric(
        pd.Series([r.get("preco_entrada")]), errors="coerce"
    ).iloc[0]
    if pd.isna(entrada) or not np.isfinite(float(entrada)) or float(entrada) <= 0:
        return None, None, None, "preco_entrada ausente/inválido"

    pares_validos = {
        "EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD",
        "USD/JPY", "USD/CHF", "USD/CAD"
    }
    if par not in pares_validos:
        return None, None, None, "par ausente/inválido"

    return par, pd.Timestamp(dt), float(entrada), ""


def _avaliar_sinais_v82():
    """
    V8.8 — Validação Automática Multipares.

    Horizonte oficial desta etapa:
    primeira observação diária FRED estritamente posterior à data_preco de entrada.

    O retorno_pct permanece como movimento bruto do PAR.
    retorno_direcional_pct converte esse movimento para o lado do sinal:
    BUY -> retorno do par; SELL -> retorno invertido.
    """
    df = _carregar_sinais_v82()
    if df.empty:
        return df, 0

    for col, default in [
        ("horizonte_validacao", ""),
        ("retorno_direcional_pct", None),
        ("serie_saida", ""),
    ]:
        if col not in df.columns:
            df[col] = default

    # V10.7.2 — impede incompatibilidade de dtype ao escrever Timestamp/bool/float.
    df = _normalizar_tipos_sinais_v1072(df)

    cache = {}
    atualizados = 0
    _ignorados_legado_v1073 = 0

    for i, r in df.iterrows():
        if bool(r.get("avaliado", False)):
            continue

        par_linha, dt_entrada, entrada, _motivo_v1073 = _entrada_legada_segura_v1073(r)
        if _motivo_v1073:
            _ignorados_legado_v1073 += 1
            continue

        # V10.7.3 — dt_entrada já foi validado como Timestamp real, nunca NaT.
        chave = (par_linha, dt_entrada.strftime("%Y-%m-%d"))
        if chave not in cache:
            cache[chave] = _fred_primeira_observacao_posterior_v88(
                par_linha, dt_entrada
            )

        preco_saida, dt_saida, sid = cache[chave]
        if preco_saida is None or dt_saida is None:
            continue

        try:
            retorno_par = (float(preco_saida) / entrada - 1.0) * 100.0
        except Exception:
            continue

        direcao = str(r.get("direcao", "")).upper().strip()
        if direcao in ("SELL", "VENDA", "VENDER"):
            retorno_dir = -retorno_par
        elif direcao in ("BUY", "COMPRA", "COMPRAR"):
            retorno_dir = retorno_par
        else:
            continue

        # Zero exato não conta como acerto.
        acertou = bool(retorno_dir > 0.0)

        df.at[i, "avaliado"] = True
        df.at[i, "preco_saida"] = float(preco_saida)
        df.at[i, "data_saida"] = pd.to_datetime(dt_saida, utc=True)
        df.at[i, "retorno_pct"] = float(retorno_par)
        df.at[i, "retorno_direcional_pct"] = float(retorno_dir)
        df.at[i, "acertou"] = acertou
        df.at[i, "horizonte_validacao"] = "Próxima observação diária FRED"
        df.at[i, "serie_saida"] = sid or ""
        atualizados += 1

    if atualizados:
        _salvar_sinais_v82(df)

    # Apenas diagnóstico de interface; não altera a classificação histórica.
    st.session_state["v1073_linhas_legadas_ignoradas"] = int(_ignorados_legado_v1073)
    return df, atualizados


def _painel_validacao_v82(par, base, cotada, score_base, score_cotada, diferenca, confl):
    st.markdown("## 🧪 Validação Automática Multipares — V9.3.5")
    st.caption(
        "A V8.8 registra a fotografia do sinal e avalia automaticamente os 7 pares na "
        "primeira observação diária FRED posterior. Não reconstrói sinais passados."
    )

    score = float(confl.get("score_confluencia", 50.0))
    qualidade = float(confl.get("qualidade_confluencia", 0.0))

    if diferenca >= 6:
        direcao = "BUY"
    elif diferenca <= -6:
        direcao = "SELL"
    else:
        direcao = "WAIT"

    p_atual, dt_atual, serie_atual = _fred_preco_par_v87(par)
    a,b,c,d = st.columns(4)
    a.metric("Par", par)
    b.metric("Sinal atual", direcao)
    c.metric("Score", f"{score:.0f}/100")
    d.metric("Preço diário FRED", f"{p_atual:.5f}" if p_atual else "—")

    if serie_atual:
        st.info(
            f"Fonte de preço V9.3.5: FRED {serie_atual}, série diária oficial H.10 para {par}. "
            "A validação mede direção entre observações diárias — não 1h/4h."
        )
    else:
        st.warning(
            "A série diária FRED deste par não está disponível nesta execução."
        )

    # V8.5.2 — Coleta Automática Diária corrigida
    _auto_v852_ativo = st.toggle(
        "🤖 Coleta automática diária",
        value=True,
        key="v852_coleta_auto",
        help="Quando houver uma nova observação diária FRED, registra automaticamente o cenário atual sem duplicar a mesma data."
    )

    if _auto_v852_ativo and par == "EUR/USD" and direcao in ("BUY", "SELL"):
        try:
            _df_auto_v852 = _carregar_sinais_v82()
            _dup_auto_v852 = False

            if isinstance(_df_auto_v852, pd.DataFrame) and not _df_auto_v852.empty and "data_preco" in _df_auto_v852.columns:
                _datas_auto_v852 = pd.to_datetime(
                    _df_auto_v852["data_preco"], errors="coerce", utc=True
                )
                _dirs_auto_v852 = (
                    _df_auto_v852["direcao"].astype(str).str.upper()
                    .replace({"VENDER":"SELL","VENDA":"SELL","COMPRAR":"BUY","COMPRA":"BUY"})
                )
                _dup_auto_v852 = (
                    (_df_auto_v852["par"].astype(str) == str(par)) &
                    (_dirs_auto_v852 == direcao) &
                    (_datas_auto_v852 == pd.to_datetime(dt_atual, utc=True))
                ).any()

            if not _dup_auto_v852:
                _ok_auto_v852, _msg_auto_v852 = _registrar_sinal_v82(
                    par, direcao, score, qualidade,
                    score_base, score_cotada, diferenca
                )
                if _ok_auto_v852:
                    st.success(f"🤖 V8.5.2 registrou automaticamente {par} {direcao}.")
                else:
                    st.caption(f"🤖 Coleta automática: {_msg_auto_v852}")
            else:
                st.caption(
                    "🤖 Coleta automática ativa — esta observação diária FRED "
                    "já está registrada para este cenário."
                )
        except Exception:
            st.warning(
                "A coleta automática não conseguiu registrar neste ciclo. "
                "O registro manual continua disponível."
            )

    if st.button("📌 Registrar sinal atual para validação", key="v82_registrar"):
        ok, msg = _registrar_sinal_v82(
            par, direcao, score, qualidade,
            score_base, score_cotada, diferenca
        )
        if ok:
            st.success(msg)
        else:
            st.warning(msg)

    if st.button("🔄 Avaliar sinais pendentes", key="v82_avaliar"):
        df, n = _avaliar_sinais_v82()
        if n:
            st.success(f"{n} sinal(is) atualizado(s) com preço diário posterior.")
        else:
            st.info("Nenhum sinal pendente tinha um novo preço diário posterior disponível.")

    # V8.3 — tenta avaliar automaticamente toda vez que o painel abre.
    df, _v83_auto_n = _avaliar_sinais_v82()

    _legadas_v1073 = int(st.session_state.get("v1073_linhas_legadas_ignoradas", 0) or 0)
    if _legadas_v1073:
        st.caption(
            f"ℹ️ V10.7.3 ignorou {_legadas_v1073} registro(s) legado(s) com data/preço/par "
            "incompleto. Eles não entram nas estatísticas e não derrubam mais o app."
        )

    if df.empty:
        st.info("Ainda não há sinais registrados na V8.3.")
        return

    pendentes = df[df["avaliado"] != True].copy()
    avaliados_total = df[df["avaliado"] == True].copy()

    st.markdown("### 💾 Persistência do histórico — V9.3.5")
    _v84_token, _v84_repo, _v84_branch = _github_cfg_v84()
    if _v84_token:
        st.success(
            f"✅ Histórico persistente configurado: {_v84_repo} · branch {_v84_branch}. "
            "Os novos registros serão salvos no repositório."
        )

        # V8.4.1 — migra o histórico local que existia antes do token.
        if st.button("☁️ Sincronizar histórico com GitHub", key="v841_sync_github"):
            _hist_local_v841 = None
            try:
                _p_v841 = Path(ARQ_SINAIS_V82)
                if _p_v841.exists():
                    _hist_local_v841 = pd.read_parquet(_p_v841)
            except Exception:
                _hist_local_v841 = None

            if not isinstance(_hist_local_v841, pd.DataFrame) or _hist_local_v841.empty:
                _hist_local_v841 = _carregar_sinais_v82()

            if isinstance(_hist_local_v841, pd.DataFrame) and not _hist_local_v841.empty:
                _ok_v841, _msg_v841 = _github_salvar_csv_v84(_hist_local_v841)
                if _ok_v841:
                    st.success(
                        f"☁️ Sincronização concluída: {len(_hist_local_v841)} "
                        "sinal(is) enviado(s) para dados/sinais_v84.csv."
                    )
                else:
                    st.error(f"Não foi possível sincronizar. {_msg_v841}")
            else:
                st.info("Não há histórico local para sincronizar.")
    else:
        st.warning(
            "⚠️ Histórico ainda está apenas no armazenamento temporário do Streamlit. "
            "Adicione GITHUB_TOKEN_HISTORICO aos Secrets para ativar a persistência."
        )

    st.markdown("### 🧭 Status da validação")
    s1, s2, s3 = st.columns(3)
    s1.metric("Registrados", len(df))
    s2.metric("Pendentes", len(pendentes))
    s3.metric("Avaliados", len(avaliados_total))

    if len(pendentes):
        st.warning(
            f"⏳ {len(pendentes)} sinal(is) pendente(s). "
            "O sistema verificará automaticamente quando a FRED trouxer uma observação diária posterior."
        )
    elif len(df):
        st.success("✅ Todos os sinais registrados já possuem avaliação posterior.")

    st.markdown("### 📚 Histórico registrado")
    if "versao_coleta" in df.columns:
        _n_legado_v873 = int((df["versao_coleta"].astype(str) != "V8.7.3").sum())
        if _n_legado_v873:
            st.info(
                f"ℹ️ {_n_legado_v873} registro(s) anterior(es) estão marcados como LEGADO. "
                "Eles permanecem visíveis, mas não entram nas estatísticas oficiais da V8.8."
            )
    exibir = df.copy()
    for col in ["timestamp","data_preco","data_saida"]:
        if col in exibir.columns:
            exibir[col] = pd.to_datetime(exibir[col], errors="coerce").dt.strftime("%d/%m/%Y")
    st.dataframe(
        exibir.tail(50).sort_values("timestamp", ascending=False),
        width="stretch",
        hide_index=True
    )

    avaliados = df[df["avaliado"] == True].copy()
    if avaliados.empty:
        st.info("Ainda não há sinais avaliados. O sistema precisa de um preço diário posterior.")
        return

    validos = avaliados[avaliados["acertou"].notna()].copy()
    if "versao_coleta" in validos.columns:
        validos = validos[
            validos["versao_coleta"].astype(str).isin(["V8.7.3", "V8.8"])
        ].copy()
    if validos.empty:
        st.info(
            "Ainda não há sinais da base limpa (V8.7.3+) avaliados "
            "para a estatística oficial V8.8."
        )
        return

    taxa = 100.0 * validos["acertou"].astype(bool).mean()
    n = len(validos)
    _ret_col_v88 = (
        "retorno_direcional_pct"
        if "retorno_direcional_pct" in validos.columns
        else "retorno_pct"
    )
    ret_medio = pd.to_numeric(validos[_ret_col_v88], errors="coerce").mean()

    st.markdown("### 📈 Resultado observado")
    r1,r2,r3 = st.columns(3)
    r1.metric("Sinais avaliados", n)
    r2.metric("Acerto direcional", f"{taxa:.1f}%")
    r3.metric("Retorno direcional médio", f"{ret_medio:+.3f}%")

    # Segmentação simples por Score Mestre.
    faixas = []
    for nome, lo, hi in [
        ("Score < 70", -1, 70),
        ("70–79", 70, 80),
        ("80–89", 80, 90),
        ("90+", 90, 101),
    ]:
        sub = validos[
            (pd.to_numeric(validos["score_mestre"], errors="coerce") >= lo) &
            (pd.to_numeric(validos["score_mestre"], errors="coerce") < hi)
        ]
        if len(sub):
            faixas.append({
                "Faixa": nome,
                "N": len(sub),
                "Acerto direcional": f"{100*sub['acertou'].astype(bool).mean():.1f}%",
                "Qualidade média": f"{pd.to_numeric(sub['qualidade'], errors='coerce').mean():.1f}%"
            })
    if faixas:
        st.markdown("### 🎯 Resultado por faixa de Score Mestre")
        st.dataframe(pd.DataFrame(faixas), width="stretch", hide_index=True)

    # V8.8 — desempenho por par.
    st.markdown("### 💱 Resultado por par")
    por_par = []
    for _par88, _sub88 in validos.groupby(validos["par"].astype(str)):
        _retcol88 = (
            "retorno_direcional_pct"
            if "retorno_direcional_pct" in _sub88.columns
            else "retorno_pct"
        )
        por_par.append({
            "Par": _par88,
            "N": len(_sub88),
            "Acertos": int(_sub88["acertou"].astype(bool).sum()),
            "Taxa de acerto": f"{100*_sub88['acertou'].astype(bool).mean():.1f}%",
            "Score médio": f"{pd.to_numeric(_sub88['score_mestre'], errors='coerce').mean():.1f}",
            "Qualidade média": f"{pd.to_numeric(_sub88['qualidade'], errors='coerce').mean():.1f}%",
            "Retorno direcional médio": (
                f"{pd.to_numeric(_sub88[_retcol88], errors='coerce').mean():+.3f}%"
            ),
        })
    if por_par:
        st.dataframe(
            pd.DataFrame(por_par).sort_values(["N", "Par"], ascending=[False, True]),
            width="stretch",
            hide_index=True,
        )

    # V8.8 — desempenho por faixa de qualidade.
    st.markdown("### 🧪 Resultado por qualidade")
    _q88 = pd.to_numeric(validos["qualidade"], errors="coerce")
    faixas_q88 = []
    for _nome88, _lo88, _hi88 in [
        ("Qualidade < 60%", -1, 60),
        ("60–74%", 60, 75),
        ("75%+", 75, 101),
    ]:
        _sub88 = validos[(_q88 >= _lo88) & (_q88 < _hi88)]
        if len(_sub88):
            faixas_q88.append({
                "Faixa": _nome88,
                "N": len(_sub88),
                "Acerto direcional": f"{100*_sub88['acertou'].astype(bool).mean():.1f}%",
                "Score médio": f"{pd.to_numeric(_sub88['score_mestre'], errors='coerce').mean():.1f}",
            })
    if faixas_q88:
        st.dataframe(pd.DataFrame(faixas_q88), width="stretch", hide_index=True)

    # =====================================================
    # V8.9 — PAINEL DE PERFORMANCE
    # Somente leitura/estatística: NÃO altera sinal, pesos ou decisão da Matriz.
    # =====================================================
    st.markdown("## 📊 Painel de Performance — V9.3.5")

    _perf89 = validos.copy()
    _perf89["score_num"] = pd.to_numeric(_perf89["score_mestre"], errors="coerce")
    _perf89["qual_num"] = pd.to_numeric(_perf89["qualidade"], errors="coerce")
    _perf89["acerto_num"] = _perf89["acertou"].astype(bool).astype(int)

    _ret89 = (
        "retorno_direcional_pct"
        if "retorno_direcional_pct" in _perf89.columns
        else "retorno_pct"
    )
    _perf89["ret_dir_num"] = pd.to_numeric(_perf89[_ret89], errors="coerce")

    _n89 = len(_perf89)
    _acertos89 = int(_perf89["acerto_num"].sum())
    _taxa89 = 100.0 * _perf89["acerto_num"].mean() if _n89 else 0.0
    _retmedio89 = _perf89["ret_dir_num"].mean()

    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric("Amostra oficial", f"{_n89}")
    _m2.metric("Acertos", f"{_acertos89}")
    _m3.metric("Taxa de acerto", f"{_taxa89:.1f}%")
    _m4.metric(
        "Retorno direcional médio",
        "—" if pd.isna(_retmedio89) else f"{_retmedio89:+.3f}%"
    )

    if _n89 < 30:
        st.warning(
            f"⚠️ Amostra ainda pequena: {_n89} sinal(is) avaliado(s). "
            "Use este painel para acompanhamento, não para concluir que o modelo está validado. "
            "Uma leitura mais útil começa quando houver dezenas de sinais."
        )

    # Ranking real por par
    _rank89 = (
        _perf89.groupby("par", dropna=False)
        .agg(
            Sinais=("acerto_num", "size"),
            Acertos=("acerto_num", "sum"),
            Taxa_acerto=("acerto_num", "mean"),
            Score_medio=("score_num", "mean"),
            Qualidade_media=("qual_num", "mean"),
            Retorno_direcional_medio=("ret_dir_num", "mean"),
        )
        .reset_index()
    )
    _rank89["Taxa_acerto"] = _rank89["Taxa_acerto"] * 100.0
    _rank89 = _rank89.sort_values(
        ["Taxa_acerto", "Sinais", "Retorno_direcional_medio"],
        ascending=[False, False, False]
    )

    st.markdown("### 🏆 Ranking real dos pares")
    _rank_show89 = _rank89.rename(columns={
        "par": "Par",
        "Taxa_acerto": "Taxa de acerto (%)",
        "Score_medio": "Score médio",
        "Qualidade_media": "Qualidade média (%)",
        "Retorno_direcional_medio": "Retorno direcional médio (%)",
    })
    st.dataframe(
        _rank_show89.round({
            "Taxa de acerto (%)": 1,
            "Score médio": 1,
            "Qualidade média (%)": 1,
            "Retorno direcional médio (%)": 3,
        }),
        width="stretch",
        hide_index=True,
    )

    if not _rank89.empty:
        _chart89 = _rank89.set_index("par")[["Taxa_acerto"]].rename(
            columns={"Taxa_acerto": "Taxa de acerto (%)"}
        )
        st.bar_chart(_chart89)

    # Score Mestre x resultado
    st.markdown("### 🎯 Score Mestre × desempenho")
    _perf89["Faixa Score"] = pd.cut(
        _perf89["score_num"],
        bins=[-float("inf"), 70, 80, 90, float("inf")],
        labels=["<70", "70–79", "80–89", "90+"],
        right=False,
    )
    _score89 = (
        _perf89.dropna(subset=["Faixa Score"])
        .groupby("Faixa Score", observed=False)
        .agg(
            Sinais=("acerto_num", "size"),
            Taxa_acerto=("acerto_num", "mean"),
            Retorno_medio=("ret_dir_num", "mean"),
        )
        .reset_index()
    )
    _score89 = _score89[_score89["Sinais"] > 0]
    if not _score89.empty:
        _score89["Taxa_acerto"] *= 100.0
        _score_show89 = _score89.rename(columns={
            "Taxa_acerto": "Taxa de acerto (%)",
            "Retorno_medio": "Retorno direcional médio (%)",
        })
        st.dataframe(
            _score_show89.round({
                "Taxa de acerto (%)": 1,
                "Retorno direcional médio (%)": 3,
            }),
            width="stretch",
            hide_index=True,
        )

    # Evolução acumulada dos resultados
    st.markdown("### 📈 Evolução da amostra")
    _evo89 = _perf89.copy()
    _evo89["data_resultado"] = pd.to_datetime(
        _evo89.get("data_saida"), errors="coerce"
    )
    _evo89 = _evo89.sort_values(["data_resultado", "timestamp"])
    _evo89["Sinais avaliados"] = range(1, len(_evo89) + 1)
    _evo89["Taxa de acerto acumulada (%)"] = (
        _evo89["acerto_num"].expanding().mean() * 100.0
    )
    _evo89["Retorno direcional acumulado (%)"] = (
        _evo89["ret_dir_num"].fillna(0.0).cumsum()
    )

    if len(_evo89):
        st.line_chart(
            _evo89.set_index("Sinais avaliados")[
                ["Taxa de acerto acumulada (%)"]
            ]
        )
        st.line_chart(
            _evo89.set_index("Sinais avaliados")[
                ["Retorno direcional acumulado (%)"]
            ]
        )

    st.caption(
        "ℹ️ V8.9 é um painel estatístico. Ele não muda pesos, sinais ou decisões. "
        "Taxa de acerto histórica não é garantia de resultado futuro."
    )

    # V8.3 — separa sinais perto/longe de eventos de impacto máximo.
    st.markdown("### 🏦 Resultado por risco de evento")
    regimes = []
    _dias = pd.to_numeric(validos["dias_evento"], errors="coerce")
    _impacto = validos["impacto"].astype(str).str.upper()
    _perto = (_dias <= 7) & _impacto.isin(["MÁXIMO", "MAXIMO", "ALTO"])

    for nome_regime, mascara in [
        ("Evento alto impacto ≤ 7 dias", _perto),
        ("Fora da janela crítica", ~_perto),
    ]:
        sub = validos[mascara]
        if len(sub):
            regimes.append({
                "Regime": nome_regime,
                "N": len(sub),
                "Acerto direcional": f"{100*sub['acertou'].astype(bool).mean():.1f}%",
                "Score médio": f"{pd.to_numeric(sub['score_mestre'], errors='coerce').mean():.1f}",
                "Qualidade média": f"{pd.to_numeric(sub['qualidade'], errors='coerce').mean():.1f}%"
            })
    if regimes:
        st.dataframe(pd.DataFrame(regimes), width="stretch", hide_index=True)
    else:
        st.caption("Ainda não há sinais avaliados suficientes para comparar regimes de evento.")

    st.warning(
        "Amostra pequena não prova vantagem estatística. "
        "Use muitos sinais e diferentes regimes de mercado antes de alterar pesos do modelo."
    )



# ============================================================
# V9.0 — CENTRAL DO OPERADOR
# Somente interface/orientação; não altera o motor do modelo.
# ============================================================
with st.expander("Guia do operador", expanded=False):
    st.markdown("## 🎛️ Central do Operador — Núcleo de Decisão V11.0.8")
    st.caption("O APP define o viés macro; o gráfico confirma a entrada.")

    with st.container(border=True):
        _op1, _op2, _op3 = st.columns(3)
        _op1.markdown("**1️⃣ CENÁRIO**")
        _op1.caption("Força das moedas + Macro EUA + Fed")
        _op2.markdown("**2️⃣ DECISÃO**")
        _op2.caption("Calendário + Matriz + Score + Qualidade")
        _op3.markdown("**3️⃣ EXECUÇÃO**")
        _op3.caption("Raio-X → gráfico → gatilho → risco")
        st.markdown(
            "**Fluxo diário:** FORÇA → MACRO → FED → CALENDÁRIO → MATRIZ "
            "→ SCORE/QUALIDADE → GRÁFICO → ENTRADA → RISCO"
        )

with st.expander("Dados manuais e configurações opcionais", expanded=False):
    st.success(
        "🟢 No uso normal, você NÃO precisa digitar manualmente CPI, PCE, Payroll, "
        "desemprego, Fed Funds, Treasuries ou preços dos pares."
    )
    st.warning(
        "🟡 CONSENSO / FORECAST pode continuar manual quando não houver uma fonte "
        "automática disponível. Preencha somente quando o módulo solicitar."
    )
    st.info(
        "🔵 Controles antigos de simulação, FOMC pós-reunião, preço manual ou timing "
        "são opcionais e não precisam ser preenchidos para consultar a Matriz automática."
    )

with st.expander("🧭 Como tomar a decisão no APP", expanded=False):
    st.markdown("""
**1 — Força:** procure moeda forte contra moeda fraca.  
**2 — Macro/Fed:** confirme se o cenário sustenta a diferença.  
**3 — Calendário:** verifique eventos críticos antes de operar.  
**4 — Matriz:** priorize COMPRA/VENDA com boa confluência e qualidade.  
**5 — Raio-X:** confira os fatores a favor e contra.  
**6 — Gráfico:** espere estrutura e gatilho técnico.  
**7 — Risco:** defina stop e tamanho da posição antes da execução.

**Regra:** APP escolhe o lado → gráfico escolhe a entrada → gestão controla a perda.
""")


# =========================================================
# V10.4 — FEEDBACK PERSISTENTE
# =========================================================
def _github_put_bytes_v104(path_repo: str, raw: bytes, message: str) -> tuple[bool, str]:
    token, repo, branch = _github_cfg_v84()
    if not token or not repo:
        return False, "GitHub persistente não configurado."
    try:
        import base64
        path_repo = str(path_repo).lstrip("/")
        url = f"https://api.github.com/repos/{repo}/contents/{path_repo}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        old = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
        sha = old.json().get("sha") if old.status_code == 200 else None
        if old.status_code not in (200, 404):
            old.raise_for_status()
        body = {"message": message, "content": base64.b64encode(raw).decode("ascii"), "branch": branch}
        if sha: body["sha"] = sha
        r = requests.put(url, headers=headers, json=body, timeout=25)
        r.raise_for_status()
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

def _salvar_feedback_v104(payload: dict, attachment: bytes | None, attachment_name: str | None) -> tuple[bool, str]:
    token, repo, branch = _github_cfg_v84()
    if not token or not repo:
        return False, "Configure GITHUB_TOKEN_HISTORICO para salvar feedback."
    try:
        import base64, io, uuid as _uuid
        path = "dados/feedback_v104.csv"
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        current = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
        sha = None
        if current.status_code == 200:
            body = current.json()
            sha = body.get("sha")
            raw = base64.b64decode(body.get("content", ""))
            df = pd.read_csv(io.BytesIO(raw)) if raw else pd.DataFrame()
        elif current.status_code == 404:
            df = pd.DataFrame()
        else:
            current.raise_for_status()

        row = dict(payload)
        attach_path = ""
        if attachment:
            safe_ext = ".png"
            if attachment_name and "." in attachment_name:
                ext = "." + attachment_name.rsplit(".", 1)[-1].lower()
                if ext in (".png", ".jpg", ".jpeg", ".webp"): safe_ext = ext
            stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%SZ")
            attach_path = f"dados/feedback_anexos/{stamp}_{_uuid.uuid4().hex[:8]}{safe_ext}"
            ok_att, err_att = _github_put_bytes_v104(attach_path, attachment, "V10.4: adicionar print de feedback")
            if not ok_att:
                return False, f"Feedback não salvo: falha no anexo ({err_att})."

        row["attachment_path"] = attach_path
        new_df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        csv_bytes = new_df.to_csv(index=False).encode("utf-8")
        body = {"message": "V10.4: registrar feedback de usuário",
                "content": base64.b64encode(csv_bytes).decode("ascii"), "branch": branch}
        if sha: body["sha"] = sha
        r = requests.put(url, headers=headers, json=body, timeout=25)
        r.raise_for_status()
        return True, "Feedback enviado e salvo com sucesso."
    except Exception as exc:
        return False, f"Falha ao salvar feedback: {type(exc).__name__}"

def _refresh_central_v104() -> tuple[bool, str]:
    try:
        _fred_observacoes.clear()
    except Exception:
        pass
    return True, "Cache histórico liberado; a próxima leitura buscará dados novos."



# =========================================================
# V10.7 — HEADLESS INPUT SNAPSHOT FOR BACKGROUND AUTOPILOT
# =========================================================
def _autopilot_save_inputs_v107():
    if os.getenv("USD_MACRO_AUTOPILOT", "") != "1":
        return True, "Modo interativo: snapshot automático não necessário."
    try:
        if "matriz_v61" not in globals() or matriz_v61 is None or matriz_v61.empty:
            return False, "Matriz V6.1 indisponível no run headless."

        token = st.secrets.get("GITHUB_TOKEN_HISTORICO", os.getenv("GITHUB_TOKEN_HISTORICO", ""))
        repo = st.secrets.get("GITHUB_REPO_HISTORICO", os.getenv("GITHUB_REPO_HISTORICO", ""))
        branch = resolve_runtime_branch(
            st.secrets.get("GITHUB_DATA_BRANCH", os.getenv("GITHUB_DATA_BRANCH", "")),
            st.secrets.get("GITHUB_BRANCH_HISTORICO", os.getenv("GITHUB_BRANCH_HISTORICO", "")),
        )
        if not token or not repo:
            return False, "GitHub persistente ausente."

        cols = [c for c in [
            "Par","Direção","Score final","Qualidade","Confluência","Dif. macro",
            "Índice ranking","Índice operacional"
        ] if c in matriz_v61.columns]
        pairs = matriz_v61[cols].head(7).to_dict("records")

        _macro = {
            "usd_score": float(usd_detalhado.get("score", 50.0)) if "usd_detalhado" in globals() else 50.0,
            "usd_quality": float(qualidade_usd) if "qualidade_usd" in globals() else 0.0,
            "fed_tone": str(fed.get("tom", "Neutro")) if "fed" in globals() else "Neutro",
            "fed_strength": float(fed.get("forca", 0.0)) if "fed" in globals() else 0.0,
        }
        try:
            _macro["trend"] = _score_tendencias_eua()
        except Exception:
            _macro["trend"] = {}
        try:
            _macro["event"] = _proximo_evento_macro_v65()
        except Exception:
            _macro["event"] = {}

        obj = {
            "version": "V10.7",
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "app_version": APP_VERSION,
            "pairs": pairs,
            "macro_context": _macro,
        }

        path = "dados/autopilot_inputs_v107.json"
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        cur = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
        sha = cur.json().get("sha", "") if cur.status_code == 200 else ""
        payload = {
            "message": "V10.7 Autopilot: snapshot da matriz",
            "content": base64.b64encode(
                json.dumps(obj, ensure_ascii=False, indent=2, default=str).encode("utf-8")
            ).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload, timeout=25)
        r.raise_for_status()
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


if render_atlasquant_header is not None:
    render_atlasquant_header(APP_VERSION, environment="DEV")
else:
    st.title("🧭 AtlasQuant")
    st.caption("Market Intelligence Platform · DEV")
    if _ATLASQUANT_UI_IMPORT_ERROR:
        st.caption(f"UI profissional em modo compatível: {_ATLASQUANT_UI_IMPORT_ERROR}")

abas = st.tabs([
    "Central", "Painel mestre", "Moedas", "EUA", "Pares", "Fed",
    "Histórico", "Backtest", "Decisão", "Market Map", "Aprender",
    "Produto", "Melhorias", "Notícias", "Autopilot",
])

# =========================================================
# ABA 2 — CLASSIFICAÇÃO
# =========================================================
with abas[2]:
    st.subheader("Força Macroeconômica das Moedas")
    st.caption("Inflação e PIB são exibidos como variação percentual anual, não como nível do índice.")

    tabela = ranking[[
        "Posição", "Código", "Moeda", "Pontuação_Macro", "Influência_Fed",
        "Pontuação_Final", "juros", "juros_reais", "inflacao", "pib", "sentimento", "fonte"
    ]].copy()
    tabela.columns = [
        "#", "Código", "Moeda", "Pontuação Macro", "Fed", "Pontuação Final",
        "Juros %", "Juros reais aprox. %", "Inflação anual %", "PIB real anual %",
        "Sentimento das notícias", "Fonte"
    ]
    st.dataframe(tabela, width="stretch", hide_index=True)

    top3 = ranking.head(3)["Código"].tolist()
    ultimas3 = ranking.tail(3)["Código"].tolist()
    st.success(f"🏆 Mais fortes: {', '.join(top3)}")
    st.error(f"📉 Mais fracas: {', '.join(ultimas3)}")

    with st.expander("🔎 Verificação da qualidade dos dados"):
        st.write("O sistema rejeita automaticamente valores fora de faixas plausíveis e usa um valor de segurança quando a série está ausente, antiga ou em unidade incompatível.")
        st.dataframe(
            tabela[["Código", "Juros %", "Juros reais aprox. %", "Inflação anual %", "PIB real anual %", "Fonte"]],
            width="stretch",
            hide_index=True,
        )

    if st.button("💾 Salvar registro da classificação"):
        st.toast(salvar_snapshot(ranking))

# =========================================================
# ABA 3 — EUA
# =========================================================
with abas[3]:
    diagnostico_eod_v73, dados_eod_v73 = ({"ok": False, "status": 403, "erro": "Economic Events não incluído no plano gratuito.", "dados": []}, {})
    st.subheader("🇺🇸 Painel de Força Macro do USD")


    rotulo_usd, icone_usd = faixa_forca(usd_detalhado["score"])
    d1, d2, d3 = st.columns(3)
    with d1:
        st.metric("Score macro do USD", f"{usd_detalhado['score']:.0f}/100")
        st.caption(f"{icone_usd} {rotulo_usd}")
    with d2:
        st.metric("Qualidade dos dados", f"{qualidade_usd}%")
        st.caption(f"Confiança dos dados: {qualidade_rotulo}")
    with d3:
        if usd_detalhado["score"] >= 58:
            st.metric("Conclusão macro", "Viés favorável ao USD")
            st.caption("🟢 O conjunto atual favorece o dólar")
        elif usd_detalhado["score"] <= 42:
            st.metric("Conclusão macro", "Viés desfavorável ao USD")
            st.caption("🔴 O conjunto atual pressiona o dólar")
        else:
            st.metric("Conclusão macro", "Neutro")
            st.caption("⚪ Sem vantagem macro clara")

    comp_df = pd.DataFrame([
        {"Componente": nome, "Score 0–100": round(valor, 1), "Peso %": int(usd_detalhado["pesos"][nome] * 100)}
        for nome, valor in usd_detalhado["componentes"].items()
    ])
    st.dataframe(comp_df, width="stretch", hide_index=True)
    st.caption("O score é uma leitura macro relativa, não uma promessa de taxa de acerto nem uma probabilidade estatística.")

    st.markdown("---")
    st.subheader("Indicadores Econômicos dos Estados Unidos")
    col_titulo, col_atualizar = st.columns([4, 1])
    with col_atualizar:
        if st.button("🔄 Atualizar FRED", help="Limpa o cache e busca novamente as observações mais recentes."):
            st.cache_data.clear()
            st.rerun()
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Juros do Fed", f"{macro_eua['Juros do Fed']:.2f}%")
        st.metric("IPC anual", f"{macro_eua['IPC anual']:.2f}%")
        st.metric("IPC Núcleo anual", f"{macro_eua['IPC Núcleo anual']:.2f}%")
    with c2:
        st.metric("PCE anual", f"{macro_eua['PCE anual']:.2f}%")
        st.metric("PCE Núcleo anual", f"{macro_eua['PCE Núcleo anual']:.2f}%")
        st.metric("Payroll — variação mensal", f"{macro_eua['Payroll variação mensal (mil)']:.0f} mil")
    with c3:
        st.metric("Desemprego", f"{macro_eua['Desemprego']:.2f}%")
        st.metric("PIB real", f"{macro_eua['PIB']:.2f}%")
        st.metric("Treasury 2 anos", f"{macro_eua['Treasury 2 anos']:.2f}%")
    with c4:
        st.metric("Treasury 10 anos", f"{macro_eua['Treasury 10 anos']:.2f}%")
        st.metric("Índice amplo do dólar", f"{macro_eua['Índice amplo do dólar']:.1f}")

    st.info("ℹ️ O Índice amplo do dólar da FRED não é o DXY/ICE. Ele serve como medida ampla da força do dólar.")

    st.markdown("#### 🔎 Auditoria dos dados")
    st.caption("Data da última observação, série usada e status de atualização de cada indicador.")
    auditoria_df = pd.DataFrame(macro_eua.get("_auditoria", []))
    if not auditoria_df.empty:
        st.dataframe(auditoria_df, width="stretch", hide_index=True)
        atrasados = auditoria_df[auditoria_df["Status"].astype(str).str.contains("🔴|Fallback", regex=True)]
        atencao = auditoria_df[auditoria_df["Status"].astype(str).str.contains("🟡", regex=True)]
        if len(atrasados):
            st.error(f"⚠️ {len(atrasados)} indicador(es) precisam de atenção: dado muito antigo ou fallback.")
        elif len(atencao):
            st.warning(f"🟡 {len(atencao)} indicador(es) estão mais antigos que o ideal para a frequência da série.")
        else:
            st.success("✅ Todos os indicadores principais passaram na validação de data e faixa.")
    st.caption("Treasuries usam janela curta de frescura. CPI/PCE/Payroll são mensais; PIB é trimestral. A data exibida é a data da observação da FRED.")

    st.markdown("---")
    st.markdown("---")
    st.subheader("📅 Calendário Econômico Automático")
    st.caption("Datas de releases obtidas da FRED. A data do release não garante o horário exato em que o dado ficará disponível na API.")
    cal = carregar_calendario_fred()
    if not cal.empty:
        st.dataframe(cal, width="stretch", hide_index=True)
    st.info("ℹ️ A FRED fornece dados realizados e datas de releases. O consenso/forecast é tentado via EODHD; se indisponível, permanece manual.")

    _mostrar_expectativa_v66()

    st.markdown("---")
    st.subheader("🎯 Surpresa Econômica Automática — Real × Previsão")
    st.caption("A FRED preenche Real e Anterior quando disponível. Você informa apenas a Previsão/consenso. O modelo mede direção e intensidade da surpresa.")

    autom = {}
    for _ind in ["IPC anual", "IPC Núcleo anual", "PCE anual", "PCE Núcleo anual", "Payroll", "Desemprego"]:
        autom[_ind] = _automatico_real_anterior(_ind)

    st.markdown("#### 🤖 Dados automáticos disponíveis")
    auto_rows = []
    for _ind, (_real, _ant) in autom.items():
        auto_rows.append({
            "Indicador": _ind,
            "Real FRED": round(_real, 3) if _real is not None else "—",
            "Anterior FRED": round(_ant, 3) if _ant is not None else "—",
        })
    st.dataframe(pd.DataFrame(auto_rows), width="stretch", hide_index=True)

    if st.button("⚡ Preencher Real e Anterior com FRED", type="primary"):
        for _ind, (_real, _ant) in autom.items():
            if _real is not None:
                st.session_state[f"real_{_ind}"] = float(_real)
            if _ant is not None:
                st.session_state[f"anterior_{_ind}"] = float(_ant)
        st.rerun()

    indicadores = [
        ("IPC anual", True),
        ("IPC Núcleo anual", True),
        ("PCE anual", True),
        ("PCE Núcleo anual", True),
        ("Payroll", True),
        ("Desemprego", False),
        ("ISM Industrial", True),
        ("ISM Serviços", True),
    ]

    linhas = []
    for nome, maior_favorece in indicadores:
        # Inicializa automáticos apenas na primeira carga da sessão.
        auto_real, auto_ant = autom.get(nome, (None, None))
        if f"real_{nome}" not in st.session_state:
            st.session_state[f"real_{nome}"] = float(auto_real) if auto_real is not None else 0.0
        if f"anterior_{nome}" not in st.session_state:
            st.session_state[f"anterior_{nome}"] = float(auto_ant) if auto_ant is not None else 0.0
        if f"previsao_{nome}" not in st.session_state:
            st.session_state[f"previsao_{nome}"] = 0.0

        c_real, c_prev, c_ant = st.columns(3)
        with c_real:
            step = 1.0 if nome == "Payroll" else 0.1
            real = st.number_input(
                f"{nome} — Real",
                step=step,
                key=f"real_{nome}",
            )
        with c_prev:
            previsao = st.number_input(
                f"{nome} — Previsão",
                step=step,
                key=f"previsao_{nome}",
                help="Digite o consenso/forecast publicado pelo seu calendário econômico."
            )
        with c_ant:
            anterior = st.number_input(
                f"{nome} — Anterior",
                step=step,
                key=f"anterior_{nome}",
            )

        tem_previsao = abs(float(previsao)) > 1e-12
        resultado = classificar_surpresa(
            real,
            previsao if tem_previsao else None,
            maior_favorece_usd=maior_favorece,
            nome_indicador=nome,
        )

        classe = resultado["Classe"]
        if classe == "Favorável ao USD":
            impacto = "🟢 Favorável ao USD"
        elif classe == "Desfavorável ao USD":
            impacto = "🔴 Desfavorável ao USD"
        elif classe == "Sem previsão":
            impacto = "⚪ Aguardando previsão"
        else:
            impacto = "⚪ Neutro"

        linhas.append({
            "Indicador": nome,
            "Real": float(real),
            "Previsão": float(previsao),
            "Anterior": float(anterior),
            "Surpresa": round(resultado["Surpresa"], 3) if np.isfinite(resultado["Surpresa"]) else "—",
            "Intensidade": round(resultado["Intensidade"], 2),
            "Impacto no USD": impacto,
            "Pontuação": round(resultado["Pontuação"], 2),
        })

    df_surpresa = pd.DataFrame(linhas)
    st.dataframe(df_surpresa, width="stretch", hide_index=True)

    leitura_surpresa = interpretar_conjunto_surpresas(df_surpresa, usd_detalhado["score"])
    st.session_state["usd_score_ajustado_surpresas"] = float(leitura_surpresa["score_ajustado"])
    st.session_state["usd_ajuste_surpresas"] = float(leitura_surpresa["ajuste"])
    st.session_state["usd_confirmacao_surpresas"] = leitura_surpresa["confirmação"]

    st.markdown("#### 🧭 Efeito das surpresas sobre o score do USD")
    ca, cb, cc = st.columns(3)
    with ca:
        st.metric("USD macro antes", f"{usd_detalhado['score']:.0f}/100")
    with cb:
        delta = leitura_surpresa["ajuste"]
        st.metric("Ajuste das surpresas", f"{delta:+.1f} pontos")
    with cc:
        st.metric("USD ajustado", f"{leitura_surpresa['score_ajustado']:.0f}/100")

    if leitura_surpresa["score_ajustado"] >= 58:
        st.success(f"🟢 Viés ajustado favorável ao USD — {leitura_surpresa['confirmação']}")
    elif leitura_surpresa["score_ajustado"] <= 42:
        st.error(f"🔴 Viés ajustado desfavorável ao USD — {leitura_surpresa['confirmação']}")
    else:
        st.info(f"⚪ USD em zona neutra — {leitura_surpresa['confirmação']}")

    st.caption("O ajuste por surpresa é limitado a ±15 pontos para impedir que uma única divulgação domine todo o modelo. Isso é uma regra operacional, não uma probabilidade estatística.")


def calcular_confluencia_v57(base: str, cotada: str, diferenca: float,
                             usd_score: float, ajuste_surpresas: float,
                             tom_fed: str, intensidade_fed: float,
                             treasury2: float) -> dict:
    """Confluência interna. Não é probabilidade estatística."""
    # direção desejada do USD no par: +1 favorece USD, -1 desfavorece USD
    usd_no_par = 1 if base == "USD" else -1 if cotada == "USD" else 0
    direcao_par = 1 if diferenca > 0 else -1 if diferenca < 0 else 0

    sinais = []

    # 1. Força relativa
    sinais.append(("Força relativa", 1 if diferenca * direcao_par > 0 and abs(diferenca) >= 6 else 0, 30))

    # 2. Score USD
    usd_dir = 1 if usd_score >= 58 else -1 if usd_score <= 42 else 0
    esperado = direcao_par * usd_no_par if usd_no_par else 0
    sinais.append(("Score USD", 1 if esperado != 0 and usd_dir == esperado else -1 if esperado != 0 and usd_dir == -esperado else 0, 20))

    # 3. Surpresa
    surpresa_dir = 1 if ajuste_surpresas > 1 else -1 if ajuste_surpresas < -1 else 0
    sinais.append(("Surpresas", 1 if esperado != 0 and surpresa_dir == esperado else -1 if esperado != 0 and surpresa_dir == -esperado else 0, 20))

    # 4. Fed
    tf = str(tom_fed).lower()
    fed_dir = 1 if ("restritivo" in tf or "hawk" in tf) else -1 if ("dovish" in tf or "expans" in tf) else 0
    sinais.append(("Federal Reserve", 1 if esperado != 0 and fed_dir == esperado else -1 if esperado != 0 and fed_dir == -esperado else 0, 20))

    # 5. Treasury 2Y — confirmação simples de regime, sem fingir previsão
    t_dir = 1 if treasury2 >= 4.0 else -1 if treasury2 <= 3.0 else 0
    sinais.append(("Treasury 2Y", 1 if esperado != 0 and t_dir == esperado else -1 if esperado != 0 and t_dir == -esperado else 0, 10))

    favor = sum(p for _, s, p in sinais if s > 0)
    contra = sum(p for _, s, p in sinais if s < 0)
    neutro = 100 - favor - contra
    saldo = favor - contra

    if favor >= 70 and contra <= 20:
        nivel = "ALTA"
    elif favor >= 50 and favor > contra:
        nivel = "MODERADA"
    else:
        nivel = "BAIXA"

    return {
        "favor": favor, "contra": contra, "neutro": neutro,
        "saldo": saldo, "nivel": nivel, "sinais": sinais
    }



def _tendencia_serie(series_id: str, unidades: str | None = None, n: int = 4) -> dict:
    """Compara média recente com média anterior para reduzir ruído de uma única observação."""
    df = _fred_observacoes(series_id, max(n * 2 + 2, 10), unidades=unidades)
    if len(df) < 4:
        return {"direcao": 0, "delta": 0.0, "texto": "Sem histórico suficiente"}
    vals = pd.to_numeric(df["value"], errors="coerce").dropna().tail(n * 2)
    metade = max(2, len(vals) // 2)
    antiga = vals.iloc[:metade].mean()
    recente = vals.iloc[metade:].mean()
    delta = float(recente - antiga)
    eps = max(abs(float(antiga)) * 0.0025, 0.02)
    direcao = 1 if delta > eps else -1 if delta < -eps else 0
    texto = "Subindo" if direcao > 0 else "Caindo" if direcao < 0 else "Estável"
    return {"direcao": direcao, "delta": delta, "texto": texto}


def _score_tendencias_eua() -> dict:
    """Tendências dos principais blocos dos EUA. Direção positiva = mais suporte relativo ao USD."""
    cpi = _tendencia_serie("CPIAUCSL", "pc1", 3)
    core = _tendencia_serie("CPILFESL", "pc1", 3)
    desemp = _tendencia_serie("UNRATE", None, 3)
    t2 = _tendencia_serie("DGS2", None, 5)
    broad = _tendencia_serie("DTWEXBGS", None, 5)
    # Inflação persistente e yields subindo podem sustentar expectativa de juros;
    # desemprego subindo tende a enfraquecer o bloco de atividade/emprego.
    bruto = (
        cpi["direcao"] * 0.20 +
        core["direcao"] * 0.25 +
        (-desemp["direcao"]) * 0.20 +
        t2["direcao"] * 0.25 +
        broad["direcao"] * 0.10
    )
    return {
        "score": float(np.clip(50 + bruto * 30, 20, 80)),
        "CPI": cpi, "Core CPI": core, "Desemprego": desemp,
        "Treasury 2Y": t2, "Broad USD": broad,
    }


def _diferencial_taxas_macro(base: str, cotada: str, ranking_df: pd.DataFrame) -> dict:
    """
    Diferencial de juros nominais entre moeda base e cotada.
    Procura automaticamente os nomes reais das colunas do ranking.
    Para USD, usa diretamente o Fed Funds carregado no painel EUA quando necessário.
    """
    def achar_coluna(candidatas):
        normalizadas = {str(c).strip().lower(): c for c in ranking_df.columns}
        for nome in candidatas:
            if nome.lower() in normalizadas:
                return normalizadas[nome.lower()]
        # busca parcial
        for c in ranking_df.columns:
            lc = str(c).strip().lower()
            if any(nome.lower() in lc for nome in candidatas):
                return c
        return None

    col_codigo = achar_coluna(["Código", "Codigo", "Moeda", "Currency", "Code"])
    col_juros = achar_coluna(["Juros %", "Juros", "Taxa de Juros", "Taxa", "Policy Rate", "Rate"])

    def taxa_moeda(codigo):
        if codigo == "USD":
            try:
                return float(macro_eua["Juros do Fed"])
            except Exception:
                pass

        if col_codigo is None or col_juros is None:
            return None

        try:
            codigos = ranking_df[col_codigo].astype(str).str.upper().str.strip()
            linha = ranking_df.loc[codigos == str(codigo).upper().strip()]
            if linha.empty:
                return None
            valor = pd.to_numeric(linha.iloc[0][col_juros], errors="coerce")
            return float(valor) if pd.notna(valor) else None
        except Exception:
            return None

    taxa_b = taxa_moeda(base)
    taxa_q = taxa_moeda(cotada)

    if taxa_b is None or taxa_q is None:
        return {
            "base": taxa_b, "cotada": taxa_q, "dif": 0.0, "direcao": 0,
            "vantagem": "Indisponível",
            "col_codigo": str(col_codigo) if col_codigo is not None else "não encontrada",
            "col_juros": str(col_juros) if col_juros is not None else "não encontrada",
        }

    dif = float(taxa_b - taxa_q)
    direcao = 1 if dif > 0.25 else -1 if dif < -0.25 else 0
    vantagem = base if direcao > 0 else cotada if direcao < 0 else "Equilibrado"

    return {
        "base": taxa_b,
        "cotada": taxa_q,
        "dif": dif,
        "direcao": direcao,
        "vantagem": vantagem,
        "col_codigo": str(col_codigo),
        "col_juros": str(col_juros),
    }



# =========================================================
# V5.9 — JUROS DE MERCADO DE CURTO PRAZO (3M/90D)
# =========================================================
# Usamos séries de 3 meses/90 dias da FRED/OECD para comparar
# maturidades semelhantes entre países. Isso é mais consistente
# do que misturar Treasury 2Y dos EUA com séries estrangeiras
# de outra maturidade.
SERIES_MERCADO_3M = {
    "USD": "IR3TIB01USM156N",
    "EUR": "IR3TIB01EZM156N",
    "GBP": "IR3TIB01GBM156N",
    "JPY": "IR3TIB01JPM156N",
    "CAD": "IR3TIB01CAM156N",
    "CHF": "IR3TIB01CHM156N",
    "AUD": "IR3TIB01AUM156N",
    "NZD": "IR3TIB01NZM156N",  # se indisponível, o app faz fallback sem quebrar
}

@st.cache_data(ttl=3600, show_spinner=False)
def _mercado_3m_moeda(codigo: str) -> dict:
    sid = SERIES_MERCADO_3M.get(codigo)
    if not sid:
        return {"valor": None, "anterior": None, "data": None, "idade": None, "serie": None}

    df = _fred_observacoes(sid, 12)
    if df.empty:
        return {"valor": None, "anterior": None, "data": None, "idade": None, "serie": sid}

    df = df.copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    if df.empty:
        return {"valor": None, "anterior": None, "data": None, "idade": None, "serie": sid}

    ult = df.iloc[-1]
    ant = df.iloc[-2] if len(df) >= 2 else None
    data = pd.Timestamp(ult["date"]).normalize()
    hoje = pd.Timestamp.now(tz=None).normalize()

    return {
        "valor": float(ult["value"]),
        "anterior": float(ant["value"]) if ant is not None else None,
        "data": data.strftime("%d/%m/%Y"),
        "idade": int((hoje - data).days),
        "serie": sid,
    }


def _spread_mercado_3m(base: str, cotada: str) -> dict:
    b = _mercado_3m_moeda(base)
    q = _mercado_3m_moeda(cotada)

    if b["valor"] is None or q["valor"] is None:
        return {
            "disponivel": False,
            "base": b, "cotada": q,
            "spread": 0.0, "spread_anterior": None,
            "delta_spread": 0.0, "direcao": 0,
            "vantagem": "Indisponível",
            "movimento": "Sem dados suficientes",
        }

    spread = float(b["valor"] - q["valor"])

    spread_ant = None
    delta = 0.0
    if b["anterior"] is not None and q["anterior"] is not None:
        spread_ant = float(b["anterior"] - q["anterior"])
        delta = float(spread - spread_ant)

    # Direção do nível do spread: positivo favorece moeda base, negativo favorece cotada.
    direcao = 1 if spread > 0.20 else -1 if spread < -0.20 else 0
    vantagem = base if direcao > 0 else cotada if direcao < 0 else "Equilibrado"

    # Movimento do spread: abertura/fechamento.
    if delta > 0.05:
        movimento = f"Abrindo a favor de {base}"
    elif delta < -0.05:
        movimento = f"Abrindo a favor de {cotada}"
    else:
        movimento = "Estável"

    return {
        "disponivel": True,
        "base": b, "cotada": q,
        "spread": spread,
        "spread_anterior": spread_ant,
        "delta_spread": delta,
        "direcao": direcao,
        "vantagem": vantagem,
        "movimento": movimento,
    }


def _sinal_spread_direcao(spread_info: dict, direcao_par: int) -> int:
    """Confirma se a mudança do spread está alinhada com compra/venda do par."""
    if not spread_info.get("disponivel"):
        return 0
    delta = float(spread_info.get("delta_spread", 0.0))
    if abs(delta) <= 0.05:
        return 0
    mov_dir = 1 if delta > 0 else -1
    return 1 if mov_dir == direcao_par else -1


def _fator_frescor_dias(idade: int | None, tipo: str = "mensal") -> float:
    """Peso por frescor. 1.0 = atual; cai gradualmente conforme o dado envelhece."""
    if idade is None:
        return 0.0
    idade = max(int(idade), 0)
    limites = {
        "diario": [(7,1.0),(21,0.85),(45,0.60),(90,0.35)],
        "mensal": [(45,1.0),(75,0.85),(120,0.60),(180,0.35)],
        "trimestral": [(120,1.0),(180,0.80),(270,0.55),(365,0.30)],
    }
    for limite, fator in limites.get(tipo, limites["mensal"]):
        if idade <= limite:
            return fator
    return 0.15


def _frescor_spread_3m(info: dict) -> float:
    if not info.get("disponivel"):
        return 0.0
    ib = info.get("base", {}).get("idade")
    iq = info.get("cotada", {}).get("idade")
    # O componente só é tão atual quanto o lado mais antigo da comparação.
    fb = _fator_frescor_dias(ib, "mensal")
    fq = _fator_frescor_dias(iq, "mensal")
    return min(fb, fq)


def _confluencia_dinamica(sinais_base: list, fatores: dict) -> dict:
    """
    Rebaixa pesos por frescor/qualidade e redistribui apenas a parcela confiável.
    Não transforma o resultado em probabilidade de lucro.
    """
    linhas = []
    peso_efetivo_total = 0.0
    favor_bruto = 0.0
    contra_bruto = 0.0

    for nome, estado, peso in sinais_base:
        fator = float(np.clip(fatores.get(nome, 1.0), 0.0, 1.0))
        peso_eff = float(peso) * fator
        peso_efetivo_total += peso_eff
        if estado > 0:
            favor_bruto += peso_eff
        elif estado < 0:
            contra_bruto += peso_eff
        linhas.append((nome, estado, peso, fator, peso_eff))

    if peso_efetivo_total <= 0:
        return {
            "favor": 0.0, "contra": 0.0, "neutro": 100.0,
            "qualidade": 0.0, "score": 50.0, "nivel": "BAIXA",
            "linhas": linhas,
        }

    favor = 100.0 * favor_bruto / peso_efetivo_total
    contra = 100.0 * contra_bruto / peso_efetivo_total
    neutro = max(0.0, 100.0 - favor - contra)
    qualidade = float(np.clip(peso_efetivo_total, 0, 100))

    # Score direcional centralizado em 50.
    score = float(np.clip(50 + (favor - contra) / 2, 0, 100))

    # Confiança exige confluência E cobertura de dados.
    if qualidade >= 75 and favor >= 70 and contra <= 15:
        nivel = "ALTA"
    elif qualidade >= 55 and favor >= 55 and favor >= contra + 20:
        nivel = "MODERADA"
    else:
        nivel = "BAIXA"

    return {
        "favor": favor, "contra": contra, "neutro": neutro,
        "qualidade": qualidade, "score": score, "nivel": nivel,
        "linhas": linhas,
    }


def calcular_confluencia_v60(base: str, cotada: str, diferenca: float,
                             usd_score: float, ajuste_surpresas: float,
                             tom_fed: str, ranking_df: pd.DataFrame) -> dict:
    """
    V5.9:
    - força relativa
    - diferencial de taxa oficial
    - spread de mercado 3M/90D
    - direção do spread
    - score USD
    - surpresas
    - Fed
    - tendência macro EUA
    """
    direcao_par = 1 if diferenca > 0 else -1 if diferenca < 0 else 0
    usd_no_par = 1 if base == "USD" else -1 if cotada == "USD" else 0
    esperado_usd = direcao_par * usd_no_par if usd_no_par else 0

    sinais = []

    # 1) Força relativa
    s_forca = 1 if abs(diferenca) >= 6 else 0
    sinais.append(("Força relativa", s_forca, 20))

    # 2) Diferencial de política monetária
    dif_oficial = _diferencial_taxas_macro(base, cotada, ranking_df)
    s_oficial = (
        1 if dif_oficial["direcao"] == direcao_par
        else -1 if dif_oficial["direcao"] == -direcao_par
        else 0
    )
    sinais.append(("Juros oficiais", s_oficial, 15))

    # 3) Mercado 3M
    mercado = _spread_mercado_3m(base, cotada)
    s_mercado = (
        1 if mercado.get("direcao", 0) == direcao_par
        else -1 if mercado.get("direcao", 0) == -direcao_par
        else 0
    )
    sinais.append(("Spread mercado 3M", s_mercado, 20))

    # 4) Direção do spread
    s_mov = _sinal_spread_direcao(mercado, direcao_par)
    sinais.append(("Direção do spread", s_mov, 10))

    # 5) Score USD
    usd_dir = 1 if usd_score >= 58 else -1 if usd_score <= 42 else 0
    s_usd = (
        1 if esperado_usd and usd_dir == esperado_usd
        else -1 if esperado_usd and usd_dir == -esperado_usd
        else 0
    )
    sinais.append(("Score USD", s_usd, 10))

    # 6) Surpresas
    sp_dir = 1 if ajuste_surpresas > 1 else -1 if ajuste_surpresas < -1 else 0
    s_sp = (
        1 if esperado_usd and sp_dir == esperado_usd
        else -1 if esperado_usd and sp_dir == -esperado_usd
        else 0
    )
    sinais.append(("Surpresas", s_sp, 10))

    # 7) Fed
    tf = str(tom_fed).lower()
    fed_dir = 1 if ("restritivo" in tf or "hawk" in tf) else -1 if ("dovish" in tf or "expans" in tf) else 0
    s_fed = (
        1 if esperado_usd and fed_dir == esperado_usd
        else -1 if esperado_usd and fed_dir == -esperado_usd
        else 0
    )
    sinais.append(("Federal Reserve", s_fed, 10))

    # 8) Tendência macro EUA
    tendencias = _score_tendencias_eua()
    trend_dir = 1 if tendencias["score"] >= 57 else -1 if tendencias["score"] <= 43 else 0
    s_trend = (
        1 if esperado_usd and trend_dir == esperado_usd
        else -1 if esperado_usd and trend_dir == -esperado_usd
        else 0
    )
    sinais.append(("Tendência macro EUA", s_trend, 5))

    # V6.0 — pesos dinâmicos conforme frescor/qualidade.
    frescor_mercado = _frescor_spread_3m(mercado)

    fatores = {
        "Força relativa": 1.00,
        "Juros oficiais": 0.95 if dif_oficial.get("base") is not None and dif_oficial.get("cotada") is not None else 0.0,
        "Spread mercado 3M": frescor_mercado,
        "Direção do spread": frescor_mercado,
        "Score USD": 1.00,
        "Surpresas": 1.00 if abs(ajuste_surpresas) > 0.01 else 0.70,
        "Federal Reserve": 1.00 if str(tom_fed).lower() not in ("", "neutro", "neutral") else 0.70,
        "Tendência macro EUA": 0.90,
    }

    dinamica = _confluencia_dinamica(sinais, fatores)

    return {
        "favor": dinamica["favor"],
        "contra": dinamica["contra"],
        "neutro": dinamica["neutro"],
        "nivel": dinamica["nivel"],
        "score_confluencia": dinamica["score"],
        "qualidade_confluencia": dinamica["qualidade"],
        "sinais": sinais,
        "linhas_dinamicas": dinamica["linhas"],
        "fatores_qualidade": fatores,
        "diferencial_taxas": dif_oficial,
        "mercado_3m": mercado,
        "tendencias": tendencias,
    }



def _explicar_confluencia_v62(par: str, base: str, cotada: str, diferenca: float,
                              confl: dict, score_base: float, score_cotada: float) -> dict:
    """Gera explicação determinística a partir dos componentes reais da confluência."""
    linhas = confl.get("linhas_dinamicas", [])
    mapa = {nome: {"estado": estado, "peso": peso, "fator": fator, "efetivo": efetivo}
            for nome, estado, peso, fator, efetivo in linhas}

    favoraveis, contrarios, neutros = [], [], []
    rotulos = {
        "Força relativa": "força macro relativa",
        "Juros oficiais": "diferencial de juros oficiais",
        "Spread mercado 3M": "spread de juros de mercado 3M",
        "Direção do spread": "movimento recente do spread",
        "Score USD": "score macro do USD",
        "Surpresas": "surpresas econômicas",
        "Federal Reserve": "tom do Federal Reserve",
        "Tendência macro EUA": "tendência macro dos EUA",
    }

    for nome, d in mapa.items():
        item = f"{rotulos.get(nome, nome)} ({d['efetivo']:.1f}% efetivo)"
        if d["estado"] > 0:
            favoraveis.append((d["efetivo"], item))
        elif d["estado"] < 0:
            contrarios.append((d["efetivo"], item))
        else:
            neutros.append((d["efetivo"], item))

    favoraveis.sort(reverse=True)
    contrarios.sort(reverse=True)

    direcao = "COMPRA" if diferenca > 0 else "VENDA" if diferenca < 0 else "NEUTRO"
    forte = base if diferenca > 0 else cotada if diferenca < 0 else "—"
    fraca = cotada if diferenca > 0 else base if diferenca < 0 else "—"

    motivos = [x[1] for x in favoraveis[:4]]
    riscos = [x[1] for x in contrarios[:3]]

    # Invalidações são condicionais e derivadas do que hoje sustenta o sinal.
    invalidacoes = []
    nomes_favor = {nome for nome, d in mapa.items() if d["estado"] > 0}
    if "Juros oficiais" in nomes_favor:
        invalidacoes.append("redução ou reversão do diferencial de juros que hoje favorece a direção do par")
    if "Spread mercado 3M" in nomes_favor or "Direção do spread" in nomes_favor:
        invalidacoes.append("fechamento/reversão do spread de juros de mercado")
    if "Federal Reserve" in nomes_favor:
        invalidacoes.append("mudança relevante no tom do Fed contra a leitura atual")
    if "Score USD" in nomes_favor or "Tendência macro EUA" in nomes_favor:
        invalidacoes.append("deterioração dos dados dos EUA suficiente para inverter o score macro")
    if "Surpresas" in nomes_favor:
        invalidacoes.append("novas surpresas econômicas relevantes em sentido contrário")
    if not invalidacoes:
        invalidacoes.append("inversão da força relativa e surgimento de componentes contrários relevantes")

    return {
        "direcao": direcao,
        "forte": forte,
        "fraca": fraca,
        "motivos": motivos,
        "riscos": riscos,
        "neutros": [x[1] for x in neutros[:3]],
        "invalidacoes": invalidacoes[:4],
        "score": float(confl.get("score_confluencia", 50)),
        "qualidade": float(confl.get("qualidade_confluencia", 0)),
        "nivel": str(confl.get("nivel", "BAIXA")),
        "score_base": score_base,
        "score_cotada": score_cotada,
    }


def _mostrar_explicador_v62(par: str, base: str, cotada: str, diferenca: float,
                            confl: dict, score_base: float, score_cotada: float):
    exp = _explicar_confluencia_v62(
        par, base, cotada, diferenca, confl, score_base, score_cotada
    )

    st.markdown("### 🧠 Por que o modelo chegou a essa conclusão?")
    if exp["direcao"] == "NEUTRO":
        st.info(
            f"⚪ **{par}: sem vantagem macro clara** — "
            f"Score {exp['score']:.0f}/100 | Qualidade {exp['qualidade']:.0f}%"
        )
    else:
        icone = "🟢" if exp["direcao"] == "COMPRA" else "🔴"
        st.markdown(
            f"{icone} **{exp['direcao']} {par}** — Score **{exp['score']:.0f}/100** | "
            f"Qualidade **{exp['qualidade']:.0f}%** | Confluência **{exp['nivel']}**"
        )
        st.write(
            f"**Força relativa:** {base} {exp['score_base']:.1f}/100 × "
            f"{cotada} {exp['score_cotada']:.1f}/100. "
            f"No cenário atual, **{exp['forte']}** está mais forte e **{exp['fraca']}** mais fraca."
        )

    if exp["motivos"]:
        st.markdown("**Principais confirmações do sinal:**")
        for m in exp["motivos"]:
            st.write(f"• 🟢 {m}")

    if exp["riscos"]:
        st.markdown("**Componentes que estão contra o sinal:**")
        for r in exp["riscos"]:
            st.write(f"• 🔴 {r}")
    elif exp["neutros"]:
        st.markdown("**Componentes que ainda não confirmam:**")
        for n in exp["neutros"]:
            st.write(f"• ⚪ {n}")

    st.markdown("**O que pode enfraquecer ou invalidar essa leitura macro:**")
    for inv in exp["invalidacoes"]:
        st.write(f"• ⚠️ {inv}")

    if exp["qualidade"] < 75:
        st.warning(
            "A qualidade/cobertura ainda não é máxima. Dados antigos ou ausentes reduzem "
            "automaticamente o peso dos componentes afetados."
        )

    st.caption(
        "Este explicador descreve os componentes que o próprio motor utilizou. "
        "Não é gatilho de entrada nem previsão garantida de movimento do preço."
    )





# =========================================================
# V6.5 — CALENDÁRIO MACRO COMPLETO
# FRED + FOMC oficial + ISM oficial
# =========================================================

# Datas de decisão (segundo dia da reunião) publicadas pelo Federal Reserve.
FOMC_DECISOES = {
    2026: [
        "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
        "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    ],
    2027: [
        "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
        "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
    ],
}

# Calendário 2026 publicado pelo Institute for Supply Management.
ISM_2026 = {
    "ISM Industrial": [
        "2026-01-05","2026-02-02","2026-03-02","2026-04-01",
        "2026-05-01","2026-06-01","2026-07-01","2026-08-03",
        "2026-09-01","2026-10-01","2026-11-02","2026-12-01",
    ],
    "ISM Serviços": [
        "2026-01-07","2026-02-04","2026-03-04","2026-04-06",
        "2026-05-05","2026-06-03","2026-07-06","2026-08-05",
        "2026-09-03","2026-10-05","2026-11-04","2026-12-03",
    ],
}

def _eventos_macro_v65() -> pd.DataFrame:
    """Une releases FRED, decisões FOMC e calendário ISM."""
    hoje = pd.Timestamp.now(tz=None).normalize()
    eventos = []

    # 1) FRED: CPI, Payroll, GDP, PCE.
    cal = carregar_calendario_fred()
    if cal is not None and not cal.empty:
        for _, row in cal.iterrows():
            data_txt = str(row.get("Próxima data de release", "—"))
            if data_txt == "—":
                continue
            try:
                dt = pd.to_datetime(data_txt, dayfirst=True).normalize()
            except Exception:
                continue
            if dt >= hoje:
                eventos.append({
                    "Evento": str(row.get("Evento", "Evento FRED")),
                    "Data": dt,
                    "Impacto": "ALTO",
                    "Fonte": str(row.get("Fonte", "FRED")),
                    "Tipo": "Dados",
                })

    # 2) FOMC: prioridade máxima.
    for ano, datas in FOMC_DECISOES.items():
        for d in datas:
            dt = pd.Timestamp(d).normalize()
            if dt >= hoje:
                eventos.append({
                    "Evento": "FOMC — Decisão de juros",
                    "Data": dt,
                    "Impacto": "MÁXIMO",
                    "Fonte": "Federal Reserve",
                    "Tipo": "Banco Central",
                })

    # 3) ISM.
    for nome, datas in ISM_2026.items():
        for d in datas:
            dt = pd.Timestamp(d).normalize()
            if dt >= hoje:
                eventos.append({
                    "Evento": nome,
                    "Data": dt,
                    "Impacto": "ALTO",
                    "Fonte": "ISM",
                    "Tipo": "Atividade",
                })

    if not eventos:
        return pd.DataFrame(columns=["Evento","Data","Impacto","Fonte","Tipo","Dias"])

    df = pd.DataFrame(eventos).drop_duplicates(subset=["Evento","Data"])
    df["Dias"] = (df["Data"] - hoje).dt.days.astype(int)
    prioridade = {"MÁXIMO": 0, "ALTO": 1, "MÉDIO": 2}
    df["_prioridade"] = df["Impacto"].map(prioridade).fillna(9)
    return df.sort_values(["Data","_prioridade","Evento"]).drop(columns="_prioridade").reset_index(drop=True)


def _proximo_evento_macro_v65() -> dict:
    df = _eventos_macro_v65()
    if df.empty:
        return {"disponivel": False}
    r = df.iloc[0]
    return {
        "disponivel": True,
        "evento": str(r["Evento"]),
        "data": r["Data"],
        "data_txt": r["Data"].strftime("%d/%m/%Y"),
        "dias": int(r["Dias"]),
        "impacto": str(r["Impacto"]),
        "fonte": str(r["Fonte"]),
        "tipo": str(r["Tipo"]),
    }


def _avaliar_risco_calendario_v65(confl: dict, diferenca: float, evento: dict) -> dict:
    score = float(confl.get("score_confluencia", 50))
    qualidade = float(confl.get("qualidade_confluencia", 0))
    nivel = str(confl.get("nivel", "BAIXA"))

    timing = 50.0 + (score - 50.0) * 0.35 + (qualidade - 50.0) * 0.20
    if nivel == "ALTA":
        timing += 8
    elif nivel == "BAIXA":
        timing -= 8

    risco, penalidade = "NORMAL", 0.0
    dias = None

    if evento.get("disponivel"):
        dias = int(evento["dias"])
        maximo = evento.get("impacto") == "MÁXIMO"

        if dias == 0:
            risco, penalidade = ("MUITO ALTO", 40 if maximo else 35)
        elif dias == 1:
            risco, penalidade = ("ALTO", 30 if maximo else 25)
        elif dias <= 3:
            risco, penalidade = ("ELEVADO", 20 if maximo else 15)
        elif dias <= 7:
            risco, penalidade = ("ATENÇÃO", 10 if maximo else 7)

    timing = float(np.clip(timing - penalidade, 0, 100))

    if abs(diferenca) < 6 or qualidade < 50:
        status = "⚪ AGUARDAR"
    elif risco in ("MUITO ALTO", "ALTO"):
        status = "🔴 RISCO DE EVENTO — AGUARDAR / CONFIRMAR HORÁRIO"
    elif risco == "ELEVADO":
        status = "🟡 EVENTO PRÓXIMO — REDUZIR CONFIANÇA NO TIMING"
    elif timing >= 72:
        status = "🟢 CENÁRIO FAVORÁVEL — PROCURAR CONFIRMAÇÃO NO PREÇO"
    elif timing >= 58:
        status = "🟡 CENÁRIO ACEITÁVEL — AGUARDAR CONFIRMAÇÃO"
    else:
        status = "⚪ AGUARDAR"

    return {"timing": timing, "risco": risco, "penalidade": penalidade,
            "status": status, "dias": dias}


def _mostrar_risco_timing_v65(confl: dict, diferenca: float):
    st.markdown("### 📅 Calendário + Risco e Timing — V7.4")
    st.caption(
        "Calendário combinado: FRED (CPI, Payroll, PIB e PCE) + Federal Reserve (FOMC) "
        "+ ISM (Industrial e Serviços)."
    )

    prox = _proximo_evento_macro_v65()
    rt = _avaliar_risco_calendario_v65(confl, diferenca, prox)

    if prox.get("disponivel"):
        a,b,c,d = st.columns(4)
        a.metric("Próximo evento", prox["evento"])
        b.metric("Data", prox["data_txt"])
        c.metric("Faltam", "Hoje" if prox["dias"] == 0 else f"{prox['dias']} dia(s)")
        d.metric("Impacto", prox["impacto"])
        st.caption(f"Fonte do calendário: {prox['fonte']} · Categoria: {prox['tipo']}")
    else:
        st.warning("Nenhum próximo evento macro foi localizado.")

    r1,r2,r3 = st.columns(3)
    r1.metric("Timing macro", f"{rt['timing']:.0f}/100")
    r2.metric("Risco de calendário", rt["risco"])
    r3.metric("Penalidade", f"-{rt['penalidade']:.0f} pts")

    if rt["status"].startswith("🟢"):
        st.success(f"**{rt['status']}**")
    elif rt["status"].startswith("🔴"):
        st.error(f"**{rt['status']}**")
    elif rt["status"].startswith("🟡"):
        st.warning(f"**{rt['status']}**")
    else:
        st.info(f"**{rt['status']}**")

    with st.expander("📆 Ver próximos eventos macro"):
        agenda = _eventos_macro_v65().head(12).copy()
        if not agenda.empty:
            agenda["Data"] = agenda["Data"].dt.strftime("%d/%m/%Y")
            st.dataframe(
                agenda[["Data","Evento","Impacto","Fonte","Dias"]],
                width="stretch", hide_index=True
            )

    with st.expander("⏱️ Ajuste manual opcional do horário"):
        st.caption("Use se você já conferiu o horário exato da divulgação.")
        usar = st.checkbox("Informar horas até o próximo evento", key="v65_usar_horas")
        if usar:
            horas = st.number_input(
                "Horas até o evento", min_value=0.0, max_value=168.0,
                value=4.0, step=0.5, key="v65_horas"
            )
            manual = _avaliar_risco_timing_v63(
                confl, diferenca, float(horas), "Alto impacto"
            )
            st.metric("Timing com horário informado", f"{manual['timing']:.0f}/100")
            if manual["status"].startswith("🔴"):
                st.error(f"**{manual['status']}**")
            elif manual["status"].startswith("🟡"):
                st.warning(f"**{manual['status']}**")
            else:
                st.info(f"**{manual['status']}**")

    st.caption(
        "A FRED fornece datas de release; o FOMC e o ISM usam calendários oficiais. "
        "Consenso/forecast é automático quando EODHD está conectado; sem a chave, permanece manual."
    )
    st.markdown("**Fluxo:** Macro → próximo evento → risco → timing → preço/estrutura → gestão.")


def _proximo_evento_fred_v64() -> dict:
    """
    Obtém o próximo release do calendário FRED já usado pelo app.
    A FRED informa a DATA, não o horário exato. Por isso a V6.4 usa risco por dia.
    """
    cal = carregar_calendario_fred()
    hoje = pd.Timestamp.now(tz=None).normalize()
    candidatos = []

    if cal is None or cal.empty:
        return {"disponivel": False}

    for _, row in cal.iterrows():
        nome = str(row.get("Evento", "Evento"))
        data_txt = str(row.get("Próxima data de release", "—"))
        if data_txt == "—":
            continue
        try:
            dt = pd.to_datetime(data_txt, dayfirst=True).normalize()
        except Exception:
            continue
        dias = int((dt - hoje).days)
        if dias < 0:
            continue

        # Os releases atualmente cadastrados (CPI, Payroll, PIB, PCE) são tratados
        # como alto impacto para o USD no controle de risco.
        candidatos.append({
            "evento": nome,
            "data": dt,
            "data_txt": dt.strftime("%d/%m/%Y"),
            "dias": dias,
            "impacto": "Alto impacto",
        })

    if not candidatos:
        return {"disponivel": False}

    candidatos.sort(key=lambda x: (x["dias"], x["evento"]))
    prox = candidatos[0]
    prox["disponivel"] = True
    return prox


def _avaliar_risco_calendario_v64(confl: dict, diferenca: float, evento_auto: dict) -> dict:
    """
    Timing automático por proximidade em DIAS.
    Como a FRED não fornece horário exato, não fingimos precisão intradiária.
    """
    score = float(confl.get("score_confluencia", 50))
    qualidade = float(confl.get("qualidade_confluencia", 0))
    nivel = str(confl.get("nivel", "BAIXA"))

    timing = 50.0 + (score - 50.0) * 0.35 + (qualidade - 50.0) * 0.20
    if nivel == "ALTA":
        timing += 8
    elif nivel == "BAIXA":
        timing -= 8

    risco = "NORMAL"
    penalidade = 0.0
    dias = None

    if evento_auto.get("disponivel"):
        dias = int(evento_auto["dias"])
        if dias == 0:
            risco, penalidade = "MUITO ALTO", 35
        elif dias == 1:
            risco, penalidade = "ALTO", 25
        elif dias <= 3:
            risco, penalidade = "ELEVADO", 15
        elif dias <= 7:
            risco, penalidade = "ATENÇÃO", 7

    timing = float(np.clip(timing - penalidade, 0, 100))

    if abs(diferenca) < 6 or qualidade < 50:
        status = "⚪ AGUARDAR"
    elif risco in ("MUITO ALTO", "ALTO"):
        status = "🔴 EVITAR ENTRADA SEM SABER O HORÁRIO EXATO DA NOTÍCIA"
    elif timing >= 72:
        status = "🟢 CENÁRIO FAVORÁVEL — PROCURAR CONFIRMAÇÃO NO PREÇO"
    elif timing >= 58:
        status = "🟡 CENÁRIO ACEITÁVEL — AGUARDAR CONFIRMAÇÃO"
    else:
        status = "⚪ AGUARDAR"

    return {
        "timing": timing, "risco": risco, "penalidade": penalidade,
        "status": status, "dias": dias,
    }


def _mostrar_risco_timing_v64(confl: dict, diferenca: float):
    st.markdown("### 📅 Risco e Timing Automático — V6.4")
    st.caption(
        "O app lê automaticamente a próxima DATA de release cadastrada na FRED. "
        "Como a FRED não fornece aqui o horário exato, o controle é conservador."
    )

    prox = _proximo_evento_fred_v64()
    rt = _avaliar_risco_calendario_v64(confl, diferenca, prox)

    if prox.get("disponivel"):
        e1, e2, e3 = st.columns(3)
        e1.metric("Próximo evento", prox["evento"])
        e2.metric("Data", prox["data_txt"])
        e3.metric("Faltam", "Hoje" if prox["dias"] == 0 else f"{prox['dias']} dia(s)")
    else:
        st.warning("Não foi possível obter uma próxima data de release da FRED.")

    r1, r2, r3 = st.columns(3)
    r1.metric("Timing macro", f"{rt['timing']:.0f}/100")
    r2.metric("Risco de calendário", rt["risco"])
    r3.metric("Penalidade", f"-{rt['penalidade']:.0f} pts")

    if rt["status"].startswith("🟢"):
        st.success(f"**{rt['status']}**")
    elif rt["status"].startswith("🔴"):
        st.error(f"**{rt['status']}**")
    elif rt["status"].startswith("🟡"):
        st.warning(f"**{rt['status']}**")
    else:
        st.info(f"**{rt['status']}**")

    if prox.get("disponivel") and prox["dias"] <= 1:
        st.warning(
            "⚠️ A data está muito próxima. Consulte um calendário econômico com horário "
            "e consenso antes de operar; a FRED usada aqui não garante o horário exato."
        )

    with st.expander("Ajuste manual opcional do horário"):
        st.caption(
            "Use somente se você já conferiu o horário em um calendário econômico confiável."
        )
        usar_manual = st.checkbox("Informar horas até o evento", key="v64_usar_horas")
        if usar_manual:
            horas = st.number_input(
                "Horas até o evento",
                min_value=0.0, max_value=168.0, value=4.0, step=0.5,
                key="v64_horas"
            )
            manual = _avaliar_risco_timing_v63(
                confl, diferenca, float(horas), "Alto impacto"
            )
            st.metric("Timing com horário informado", f"{manual['timing']:.0f}/100")
            if manual["status"].startswith("🔴"):
                st.error(f"**{manual['status']}**")
            elif manual["status"].startswith("🟡"):
                st.warning(f"**{manual['status']}**")
            else:
                st.info(f"**{manual['status']}**")

    st.markdown(
        "**Fluxo:** Macro → calendário automático → risco → confirmação no preço → gestão."
    )
    st.caption(
        "O timing não é probabilidade de ganho e não é gatilho automático de entrada."
    )

def _avaliar_risco_timing_v63(confl: dict, diferenca: float,
                              horas_ate_evento: float | None,
                              impacto_evento: str = "Sem evento informado") -> dict:
    """
    Separa direção macro de timing. Não cria gatilho técnico.
    Risco aumenta perto de evento de alto impacto.
    """
    score = float(confl.get("score_confluencia", 50))
    qualidade = float(confl.get("qualidade_confluencia", 0))
    nivel = str(confl.get("nivel", "BAIXA"))

    # Base do timing vem da robustez macro, não do preço.
    timing = 50.0
    timing += (score - 50.0) * 0.35
    timing += (qualidade - 50.0) * 0.20
    if nivel == "ALTA":
        timing += 8
    elif nivel == "BAIXA":
        timing -= 8

    risco = "NORMAL"
    penalidade = 0.0
    if horas_ate_evento is not None:
        h = max(float(horas_ate_evento), 0.0)
        alto = impacto_evento == "Alto impacto"
        medio = impacto_evento == "Médio impacto"

        if alto and h <= 1:
            risco, penalidade = "MUITO ALTO", 35
        elif alto and h <= 4:
            risco, penalidade = "ALTO", 25
        elif alto and h <= 12:
            risco, penalidade = "ELEVADO", 15
        elif medio and h <= 2:
            risco, penalidade = "ALTO", 18
        elif medio and h <= 8:
            risco, penalidade = "ELEVADO", 10

    timing = float(np.clip(timing - penalidade, 0, 100))

    if abs(diferenca) < 6 or qualidade < 50:
        status = "⚪ AGUARDAR"
    elif risco in ("MUITO ALTO", "ALTO"):
        status = "🔴 EVITAR ENTRADA PRÓXIMA À NOTÍCIA"
    elif timing >= 72:
        status = "🟢 CENÁRIO FAVORÁVEL — PROCURAR CONFIRMAÇÃO NO PREÇO"
    elif timing >= 58:
        status = "🟡 CENÁRIO ACEITÁVEL — AGUARDAR CONFIRMAÇÃO"
    else:
        status = "⚪ AGUARDAR"

    return {
        "timing": timing,
        "risco": risco,
        "status": status,
        "penalidade": penalidade,
    }


def _mostrar_risco_timing_v63(confl: dict, diferenca: float):
    st.markdown("### ⏱️ Risco e Timing Macro — V6.3")
    st.caption(
        "Direção macro escolhe o lado; esta área controla o risco de timing. "
        "Ela não substitui confirmação técnica no preço."
    )

    c1, c2 = st.columns(2)
    with c1:
        evento = st.selectbox(
            "Próximo evento relevante",
            ["Sem evento informado", "Alto impacto", "Médio impacto"],
            key="v63_evento_impacto"
        )
    with c2:
        horas = st.number_input(
            "Horas até o evento",
            min_value=0.0, max_value=168.0, value=24.0, step=0.5,
            disabled=(evento == "Sem evento informado"),
            key="v63_horas_evento"
        )

    horas_usadas = None if evento == "Sem evento informado" else float(horas)
    rt = _avaliar_risco_timing_v63(confl, diferenca, horas_usadas, evento)

    r1, r2, r3 = st.columns(3)
    r1.metric("Timing macro", f"{rt['timing']:.0f}/100")
    r2.metric("Risco de notícia", rt["risco"])
    r3.metric("Penalidade de timing", f"-{rt['penalidade']:.0f} pts")

    if rt["status"].startswith("🟢"):
        st.success(f"**{rt['status']}**")
    elif rt["status"].startswith("🔴"):
        st.error(f"**{rt['status']}**")
    elif rt["status"].startswith("🟡"):
        st.warning(f"**{rt['status']}**")
    else:
        st.info(f"**{rt['status']}**")

    if evento != "Sem evento informado":
        st.write(
            f"Evento informado: **{evento}**, faltando aproximadamente **{horas:.1f} h**. "
            "Quanto mais perto de uma divulgação importante, menor o timing do modelo."
        )
    else:
        st.info(
            "Nenhum evento foi informado nesta avaliação. O timing não recebeu penalidade de calendário."        )

    st.markdown(
        "**Fluxo recomendado pelo painel:** Macro → risco de notícia → estrutura/preço → gestão de risco."
    )
    st.caption(
        "Timing macro não significa 'entrar agora'. O sistema não observa aqui spread da corretora, "
        "liquidez instantânea, slippage ou estrutura técnica do gráfico."
    )



def _mostrar_expectativa_no_par_v68(base: str, cotada: str):
    """
    V6.7: permite preencher o consenso diretamente no painel do par.
    Reutiliza as mesmas session_state keys do Painel EUA, mas NÃO cria widgets
    com aquelas keys aqui; usa keys v67 exclusivas e sincroniza os valores.
    """
    st.markdown("### 🔮 Expectativa do Mercado — V7.4")
    st.caption(
        "Preencha o consenso diretamente aqui. O painel compara CONSENSO × ANTERIOR "
        "antes do release. Isso continua informativo e não é contado duas vezes no score."
    )

    prox = _proximo_evento_macro_v65()
    evento = prox.get("evento", "") if prox.get("disponivel") else ""

    # Mapeia o próximo evento para o indicador econômico compatível.
    nome_ind = None
    maior_favorece = True
    if "PCE" in evento and ("Núcleo" in evento or "Core" in evento):
        nome_ind = "PCE Núcleo anual"
    elif "PCE" in evento:
        nome_ind = "PCE anual"
    elif "CPI" in evento and ("Core" in evento or "Núcleo" in evento):
        nome_ind = "IPC Núcleo anual"
    elif "CPI" in evento or "IPC" in evento:
        nome_ind = "IPC anual"
    elif "Payroll" in evento or "Emprego" in evento:
        nome_ind = "Payroll"
    elif "ISM Industrial" in evento:
        nome_ind = "ISM Industrial"
    elif "ISM Serviços" in evento:
        nome_ind = "ISM Serviços"

    # FOMC precisa de lógica própria: taxa atual × taxa esperada.
    if "FOMC" in evento:
        st.info(
            f"Próximo evento: **{evento}** em **{prox.get('data_txt','—')}**. "
            "A V6.8 separa Fed Funds efetivo de cenários esperados para a decisão."
        )

        # Fed Funds efetivo é referência observada; não é tratado como a faixa-alvo.
        _effr_auto, _effr_dt = _auto_anterior_v71("Fed Funds efetivo")
        effr_default = float(st.session_state.get(
            "v68_effr", _effr_auto if _effr_auto is not None else 3.63
        ))
        st.number_input(
            "Fed Funds efetivo — referência (%)",
            min_value=0.0, max_value=20.0, value=effr_default,
            step=0.01, key="v68_effr",
            help="Referência observada. Não representa, por si só, a faixa-alvo anunciada pelo FOMC."
        )

        st.markdown("#### 🎲 Cenários esperados para o FOMC")
        st.caption(
            "Informe probabilidades de mercado para CORTE, MANUTENÇÃO e ALTA. "
            "A soma deve ser 100%. Estes valores são manuais nesta versão."
        )

        p1, p2, p3 = st.columns(3)
        with p1:
            p_corte = st.number_input(
                "Corte de 25 pb (%)", min_value=0.0, max_value=100.0,
                value=float(st.session_state.get("v68_p_corte", 0.0)),
                step=1.0, key="v68_p_corte"
            )
        with p2:
            p_manut = st.number_input(
                "Manutenção (%)", min_value=0.0, max_value=100.0,
                value=float(st.session_state.get("v68_p_manut", 100.0)),
                step=1.0, key="v68_p_manut"
            )
        with p3:
            p_alta = st.number_input(
                "Alta de 25 pb (%)", min_value=0.0, max_value=100.0,
                value=float(st.session_state.get("v68_p_alta", 0.0)),
                step=1.0, key="v68_p_alta"
            )

        soma = float(p_corte + p_manut + p_alta)
        if abs(soma - 100.0) > 0.01:
            st.error(
                f"As probabilidades somam **{soma:.1f}%**. "
                "Ajuste os três cenários para totalizar **100%**."
            )
            st.session_state["v66_expectativa_score"] = 50.0
            st.session_state["v66_expectativa_leitura"] = "⚪ Probabilidades FOMC inválidas"
            st.session_state["v67_expectativa_tem_dado"] = False
            return

        # Valor esperado da mudança em pontos-base.
        # Corte = -25 pb; manutenção = 0; alta = +25 pb.
        mudanca_esperada_pb = (-25.0 * p_corte + 25.0 * p_alta) / 100.0

        # Score interno pré-release: 50 é neutro; ±25 pb de valor esperado
        # corresponde a uma faixa de 25–75. Não é probabilidade de lucro.
        score = float(np.clip(50.0 + mudanca_esperada_pb, 0.0, 100.0))

        cenarios = {
            "CORTE 25 pb": float(p_corte),
            "MANUTENÇÃO": float(p_manut),
            "ALTA 25 pb": float(p_alta),
        }
        dominante = max(cenarios, key=cenarios.get)
        prob_dom = cenarios[dominante]

        if mudanca_esperada_pb >= 5:
            leitura = "🟢 Distribuição de cenários tende a favorecer o USD"
        elif mudanca_esperada_pb <= -5:
            leitura = "🔴 Distribuição de cenários tende a desfavorecer o USD"
        else:
            leitura = "⚪ Distribuição de cenários está próxima do neutro"

        m1, m2, m3 = st.columns(3)
        m1.metric("Cenário dominante", dominante)
        m2.metric("Prob. dominante", f"{prob_dom:.0f}%")
        m3.metric("Mudança esperada", f"{mudanca_esperada_pb:+.1f} pb")

        st.metric("Expectativa FOMC / USD", f"{score:.0f}/100")

        if score >= 60:
            st.success(f"**{leitura}**")
        elif score <= 40:
            st.error(f"**{leitura}**")
        else:
            st.info(f"**{leitura}**")

        # Traduz para o par, sem transformar em gatilho.
        if base == "USD":
            if score >= 60:
                st.write(f"Pré-FOMC tende a apoiar **COMPRA {base}/{cotada}**.")
            elif score <= 40:
                st.write(f"Pré-FOMC tende a contrariar **COMPRA {base}/{cotada}**.")
            else:
                st.write(f"Pré-FOMC está **neutro/misto** para {base}/{cotada}.")
        elif cotada == "USD":
            if score >= 60:
                st.write(f"Pré-FOMC tende a apoiar **VENDA {base}/{cotada}**.")
            elif score <= 40:
                st.write(f"Pré-FOMC tende a contrariar **VENDA {base}/{cotada}**.")
            else:
                st.write(f"Pré-FOMC está **neutro/misto** para {base}/{cotada}.")

        st.session_state["v66_expectativa_score"] = score
        st.session_state["v66_expectativa_leitura"] = leitura
        st.session_state["v67_expectativa_tem_dado"] = True

        st.warning(
            "Probabilidade do cenário FOMC ≠ probabilidade de lucro no Forex. "
            "Mesmo com manutenção esperada, comunicado, projeções e Powell podem provocar forte reação."
        )
        st.caption(
            "V6.8 usa probabilidades inseridas manualmente. Não rotula esses números como CME FedWatch "
            "nem como dados ao vivo sem uma fonte de mercado conectada."
        )
        return

    if nome_ind is None:
        st.info(
            "O próximo evento do calendário não possui um campo direto de consenso neste módulo. "
            "Use o Painel EUA para os indicadores disponíveis."
        )
        return

    if nome_ind == "Desemprego":
        maior_favorece = False

    st.info(
        f"Próximo indicador compatível: **{nome_ind}** · "
        f"Evento: **{evento}** · Data: **{prox.get('data_txt','—')}**"
    )

    # Defaults vindos do painel EUA, mas widgets usam keys EXCLUSIVAS V6.7.
    pkey = f"previsao_{nome_ind}"
    akey = f"anterior_{nome_ind}"
    prev_default = float(st.session_state.get(pkey, 0.0))
    ant_default = float(st.session_state.get(akey, 0.0))
    step = 1.0 if nome_ind == "Payroll" else 0.1

    c0, c1, c2 = st.columns([0.7, 1.2, 1.2])
    with c0:
        usar = st.checkbox("Usar", value=False, key=f"v67_usar_{nome_ind}")
    with c1:
        previsao = st.number_input(
            f"{nome_ind} — Consenso",
            value=prev_default, step=step, key=f"v67_previsao_{nome_ind}"
        )
    with c2:
        anterior = st.number_input(
            f"{nome_ind} — Anterior",
            value=ant_default, step=step, key=f"v67_anterior_{nome_ind}"
        )

    if not usar:
        st.info("Marque **Usar** quando tiver preenchido o consenso.")
        return

    # Sincroniza valores para o motor pós-release, sem duplicar widget keys.
    st.session_state[pkey] = float(previsao)
    st.session_state[akey] = float(anterior)
    st.session_state[f"v66_consenso_{nome_ind}"] = True

    r = _expectativa_indicador_v66(
        nome_ind, float(previsao), float(anterior), maior_favorece
    )
    score = float(r["score"])
    st.metric("Expectativa USD", f"{score:.0f}/100")
    if score >= 60:
        st.success(f"**{r['leitura']}**")
    elif score <= 40:
        st.error(f"**{r['leitura']}**")
    else:
        st.info(f"**{r['leitura']}**")

    if base == "USD":
        if score >= 60:
            st.write(f"Pré-release tende a apoiar **COMPRA {base}/{cotada}**.")
        elif score <= 40:
            st.write(f"Pré-release tende a contrariar **COMPRA {base}/{cotada}**.")
    elif cotada == "USD":
        if score >= 60:
            st.write(f"Pré-release tende a apoiar **VENDA {base}/{cotada}**.")
        elif score <= 40:
            st.write(f"Pré-release tende a contrariar **VENDA {base}/{cotada}**.")

    st.session_state["v66_expectativa_score"] = score
    st.session_state["v66_expectativa_leitura"] = r["leitura"]
    st.session_state["v67_expectativa_tem_dado"] = True
    st.caption(
        "Consenso × anterior = expectativa pré-release. "
        "Real × consenso continua sendo a surpresa econômica após a divulgação."
    )



def _fomc_surprise_engine_v69(p_corte: float, p_manut: float, p_alta: float,
                              decisao_real: str, tom: str) -> dict:
    """
    Compara a decisão REAL com a distribuição pré-FOMC.
    O score mede surpresa direcional para o USD; não é probabilidade de lucro.
    """
    probs = {
        "Corte 25 pb": float(p_corte),
        "Manutenção": float(p_manut),
        "Alta 25 pb": float(p_alta),
    }
    soma = sum(probs.values())
    if abs(soma - 100.0) > 0.01:
        return {"valido": False, "erro": f"Probabilidades somam {soma:.1f}%."}

    movimentos = {"Corte 25 pb": -25.0, "Manutenção": 0.0, "Alta 25 pb": 25.0}
    esperado_pb = sum(probs[k] * movimentos[k] for k in probs) / 100.0
    real_pb = movimentos[decisao_real]
    surpresa_pb = real_pb - esperado_pb

    # Surpresa da decisão: +/-25 pb inesperados levam o score até aprox. 25/75.
    score_decisao = float(np.clip(50.0 + surpresa_pb, 0.0, 100.0))

    # Tom comunicado/Powell funciona como camada separada e limitada.
    ajuste_tom = {
        "Muito dovish": -15.0,
        "Dovish": -8.0,
        "Neutro": 0.0,
        "Hawkish": 8.0,
        "Muito hawkish": 15.0,
    }[tom]

    score_final = float(np.clip(score_decisao + ajuste_tom, 0.0, 100.0))

    if score_final >= 62:
        leitura = "🟢 Surpresa FOMC favorece o USD"
    elif score_final <= 38:
        leitura = "🔴 Surpresa FOMC desfavorece o USD"
    else:
        leitura = "⚪ Resultado FOMC neutro/misto para o USD"

    prob_real = probs[decisao_real]
    if prob_real >= 70:
        grau = "BAIXA surpresa"
    elif prob_real >= 40:
        grau = "SURPRESA MODERADA"
    else:
        grau = "ALTA surpresa"

    return {
        "valido": True,
        "esperado_pb": esperado_pb,
        "real_pb": real_pb,
        "surpresa_pb": surpresa_pb,
        "prob_real": prob_real,
        "grau": grau,
        "score_decisao": score_decisao,
        "ajuste_tom": ajuste_tom,
        "score_final": score_final,
        "leitura": leitura,
    }


def _mostrar_fomc_surprise_v69(base: str, cotada: str):
    prox = _proximo_evento_macro_v65()
    evento = prox.get("evento", "") if prox.get("disponivel") else ""

    st.markdown("### ⚡ FOMC Surprise Engine — V7.4")
    st.caption(
        "Use esta área APÓS a decisão. Ela compara o que o mercado precificava "
        "com o que o Fed realmente fez e adiciona uma leitura separada do comunicado/Powell."
    )

    # Recupera as probabilidades pré-FOMC da V6.8.
    p_corte = float(st.session_state.get("v68_p_corte", 0.0))
    p_manut = float(st.session_state.get("v68_p_manut", 100.0))
    p_alta = float(st.session_state.get("v68_p_alta", 0.0))
    soma = p_corte + p_manut + p_alta

    st.write(
        f"**Precificação salva:** Corte {p_corte:.0f}% · "
        f"Manutenção {p_manut:.0f}% · Alta {p_alta:.0f}%"
    )

    ativar = st.checkbox(
        "A decisão do FOMC já saiu — ativar análise pós-release",
        key="v69_fomc_pos_release"
    )
    if not ativar:
        st.session_state["v69_fomc_surprise_ativo"] = False
        st.info(
            "Enquanto a decisão não sair, mantenha esta área desativada. "
            "A análise pré-FOMC continua sendo a referência."
        )
        return

    if abs(soma - 100.0) > 0.01:
        st.error(
            f"As probabilidades pré-FOMC somam {soma:.1f}%. "
            "Corrija os cenários na seção de expectativa antes de calcular a surpresa."
        )
        return

    c1, c2 = st.columns(2)
    with c1:
        decisao = st.selectbox(
            "Decisão real do Fed",
            ["Corte 25 pb", "Manutenção", "Alta 25 pb"],
            key="v69_decisao_real"
        )
    with c2:
        tom = st.selectbox(
            "Tom do comunicado / Powell",
            ["Muito dovish", "Dovish", "Neutro", "Hawkish", "Muito hawkish"],
            index=2, key="v69_tom_fomc"
        )

    r = _fomc_surprise_engine_v69(p_corte, p_manut, p_alta, decisao, tom)
    if not r["valido"]:
        st.error(r["erro"])
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Movimento esperado", f"{r['esperado_pb']:+.1f} pb")
    m2.metric("Decisão real", f"{r['real_pb']:+.0f} pb")
    m3.metric("Surpresa", f"{r['surpresa_pb']:+.1f} pb")
    m4.metric("Prob. do resultado", f"{r['prob_real']:.0f}%")

    q1, q2, q3 = st.columns(3)
    q1.metric("Grau", r["grau"])
    q2.metric("Ajuste comunicado", f"{r['ajuste_tom']:+.0f} pts")
    q3.metric("FOMC / USD", f"{r['score_final']:.0f}/100")

    if r["score_final"] >= 62:
        st.success(f"**{r['leitura']}**")
    elif r["score_final"] <= 38:
        st.error(f"**{r['leitura']}**")
    else:
        st.info(f"**{r['leitura']}**")

    if base == "USD":
        if r["score_final"] >= 62:
            st.write(f"Pós-FOMC tende a apoiar **COMPRA {base}/{cotada}**.")
        elif r["score_final"] <= 38:
            st.write(f"Pós-FOMC tende a pressionar **{base}/{cotada} para baixo**.")
        else:
            st.write(f"Pós-FOMC está misto para **{base}/{cotada}**.")
    elif cotada == "USD":
        if r["score_final"] >= 62:
            st.write(f"Pós-FOMC tende a apoiar **VENDA {base}/{cotada}**.")
        elif r["score_final"] <= 38:
            st.write(f"Pós-FOMC tende a apoiar **COMPRA {base}/{cotada}**.")
        else:
            st.write(f"Pós-FOMC está misto para **{base}/{cotada}**.")

    # Mantém separado do score macro principal para não contar o FOMC duas vezes.
    st.session_state["v69_fomc_surprise_score"] = float(r["score_final"])
    st.session_state["v69_fomc_surprise_ativo"] = True

    st.warning(
        "Este score mede surpresa direcional interna do FOMC, não probabilidade de lucro. "
        "O tom do comunicado/Powell é informado manualmente e deve ser confirmado pela fonte oficial."
    )
    st.caption(
        "A V6.9 NÃO soma automaticamente este resultado ao score macro principal, "
        "evitando dupla contagem com o componente Fed já existente."
    )



def _score_mestre_v70(base: str, cotada: str, diferenca: float, confl: dict) -> dict:
    """
    V7.0 — consolida o estado do sistema sem transformar score em probabilidade.
    Mantém Direção, Qualidade e Timing separados.

    Importante:
    - confluência já contém macro/Fed/juros; não repetimos esses componentes;
    - expectativa pré-release é contexto e recebe peso pequeno;
    - surpresa FOMC só entra se o módulo pós-release estiver explicitamente ativado;
    - calendário afeta TIMING, não a direção estrutural.
    """
    conf_score = float(confl.get("score_confluencia", 50.0))
    qualidade = float(confl.get("qualidade_confluencia", 0.0))

    # Direção do par: diferença macro já está no sentido base - cotada.
    if diferenca >= 0:
        direcao = f"COMPRA {base}/{cotada}"
        sinal = 1.0
    else:
        direcao = f"VENDA {base}/{cotada}"
        sinal = -1.0

    # Núcleo direcional = motor de confluência já deduplicado.
    componentes = [{
        "Componente": "Confluência macro",
        "Score": conf_score,
        "Peso": 0.80,
        "Ativo": True,
        "Observação": "Macro + juros + Fed + frescor já consolidados"
    }]

    # Expectativa pré-release: só entra se houve dado explícito.
    exp_ativo = bool(st.session_state.get("v67_expectativa_tem_dado", False))
    exp_usd = float(st.session_state.get("v66_expectativa_score", 50.0))
    if "USD" in (base, cotada) and exp_ativo:
        # Converte USD-score para o sentido da direção atual do par.
        usd_favorece_compra = base == "USD"
        exp_par = exp_usd if usd_favorece_compra else 100.0 - exp_usd
        # Se a direção estrutural é venda, inverter novamente para medir confirmação.
        exp_confirm = exp_par if sinal > 0 else 100.0 - exp_par
        componentes.append({
            "Componente": "Expectativa pré-release",
            "Score": exp_confirm,
            "Peso": 0.08,
            "Ativo": True,
            "Observação": "Consenso × anterior / cenários FOMC"
        })

    # Surpresa FOMC pós-release: entra somente quando ativada.
    fomc_ativo = bool(st.session_state.get("v69_fomc_surprise_ativo", False))
    fomc_usd = float(st.session_state.get("v69_fomc_surprise_score", 50.0))
    if "USD" in (base, cotada) and fomc_ativo:
        usd_favorece_compra = base == "USD"
        fomc_par = fomc_usd if usd_favorece_compra else 100.0 - fomc_usd
        fomc_confirm = fomc_par if sinal > 0 else 100.0 - fomc_par
        componentes.append({
            "Componente": "Surpresa FOMC pós-release",
            "Score": fomc_confirm,
            "Peso": 0.12,
            "Ativo": True,
            "Observação": "Decisão real × precificação + comunicação"
        })

    # Normaliza apenas pesos ativos para não punir ausência de módulos opcionais.
    peso_total = sum(c["Peso"] for c in componentes if c["Ativo"])
    score_mestre = sum(c["Score"] * c["Peso"] for c in componentes if c["Ativo"]) / max(peso_total, 1e-9)

    # Timing vem do calendário, separado da direção.
    prox = _proximo_evento_macro_v65()
    rt = _avaliar_risco_calendario_v65(confl, diferenca, prox)
    timing = float(rt["timing"])
    risco = str(rt["risco"])

    # Classificação do alinhamento direcional.
    if score_mestre >= 78:
        nivel = "FORTE"
    elif score_mestre >= 62:
        nivel = "MODERADO"
    else:
        nivel = "FRACO / MISTO"

    # Estado operacional: não é ordem de entrada.
    if qualidade < 55 or score_mestre < 58:
        estado = "⚪ AGUARDAR — vantagem insuficiente"
    elif risco in ("MUITO ALTO", "ALTO"):
        estado = "🔴 DIREÇÃO EXISTE, MAS RISCO DE EVENTO É ALTO"
    elif timing >= 72 and score_mestre >= 70:
        estado = "🟢 CENÁRIO MACRO ALINHADO — PROCURAR CONFIRMAÇÃO NO PREÇO"
    elif timing >= 58:
        estado = "🟡 DIREÇÃO VÁLIDA — AGUARDAR CONFIRMAÇÃO"
    else:
        estado = "⚪ AGUARDAR MELHOR TIMING"

    return {
        "direcao": direcao,
        "score": float(np.clip(score_mestre, 0, 100)),
        "qualidade": qualidade,
        "timing": timing,
        "risco": risco,
        "nivel": nivel,
        "estado": estado,
        "componentes": componentes,
    }


def _mostrar_score_mestre_v70(base: str, cotada: str, diferenca: float, confl: dict):
    st.markdown("## 🦅 Score Mestre — V7.8")
    st.caption(
        "Resumo final do motor. Direção, qualidade dos dados e timing ficam separados "
        "para não confundir score interno com probabilidade de lucro."
    )

    m = _score_mestre_v70(base, cotada, diferenca, confl)

    a,b,c,d = st.columns(4)
    a.metric("Direção", m["direcao"])
    b.metric("Score Mestre", f"{m['score']:.0f}/100")
    c.metric("Qualidade", f"{m['qualidade']:.0f}%")
    d.metric("Timing", f"{m['timing']:.0f}/100")

    st.write(f"**Alinhamento:** {m['nivel']} · **Risco de calendário:** {m['risco']}")

    if m["estado"].startswith("🟢"):
        st.success(f"**{m['estado']}**")
    elif m["estado"].startswith("🔴"):
        st.error(f"**{m['estado']}**")
    elif m["estado"].startswith("🟡"):
        st.warning(f"**{m['estado']}**")
    else:
        st.info(f"**{m['estado']}**")

    with st.expander("🔎 Como o Score Mestre foi formado"):
        rows = []
        peso_ativo = sum(x["Peso"] for x in m["componentes"] if x["Ativo"])
        for x in m["componentes"]:
            rows.append({
                "Componente": x["Componente"],
                "Score de confirmação": round(float(x["Score"]), 1),
                "Peso nominal": f"{x['Peso']*100:.0f}%",
                "Peso normalizado": f"{(x['Peso']/peso_ativo)*100:.1f}%" if peso_ativo else "—",
                "Observação": x["Observação"],
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.warning(
        "Score Mestre 80/100 NÃO significa 80% de chance de lucro. "
        "É uma medida interna de alinhamento dos componentes macro disponíveis."
    )
    st.caption(
        "Calendário e timing não invertem automaticamente a direção macro; eles controlam "
        "quando vale procurar confirmação técnica. Spread, liquidez, slippage e estrutura "
        "do gráfico continuam fora deste score."
    )



# =========================================================
# V7.1 — AUTOMAÇÃO MÁXIMA
# =========================================================
AUTO_SERIES_V71 = {
    "IPC anual": "CPIAUCSL",
    "IPC Núcleo anual": "CPILFESL",
    "PCE anual": "PCEPI",
    "PCE Núcleo anual": "PCEPILFE",
    "Payroll": "PAYEMS",
    "Desemprego": "UNRATE",
    "Fed Funds efetivo": "FEDFUNDS",
    "Treasury 2Y": "DGS2",
    "Treasury 10Y": "DGS10",
    "USD amplo": "DTWEXBGS",
}

def _fred_obs_v71(series_id: str, limit: int = 6):
    """Busca observações recentes usando a mesma CHAVE_FRED do app."""
    if not CHAVE_FRED:
        return []
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id, "api_key": CHAVE_FRED, "file_type": "json",
        "sort_order": "desc", "limit": max(limit, 3)
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        out = []
        for x in obs:
            try:
                if x.get("value") not in (None, ".", ""):
                    out.append((pd.Timestamp(x["date"]), float(x["value"])))
            except Exception:
                pass
        return out
    except Exception:
        return []

def _auto_anterior_v71(nome: str):
    """Retorna valor anterior compatível com a forma usada pelo painel."""
    sid = AUTO_SERIES_V71.get(nome)
    obs = _fred_obs_v71(sid, 15) if sid else []
    if len(obs) < 2:
        return None, None

    # Inflação: converte índice para variação anual (%).
    if nome in ("IPC anual", "IPC Núcleo anual", "PCE anual", "PCE Núcleo anual"):
        if len(obs) < 13:
            return None, None
        vals = list(reversed(obs[:13]))
        prev = vals[-2][1] / vals[-13][1] * 100.0 - 100.0
        return float(prev), vals[-2][0]

    # Payroll: diferença mensal em milhares.
    if nome == "Payroll":
        return float(obs[1][1] - obs[2][1]), obs[1][0]

    # Taxas/níveis.
    return float(obs[1][1]), obs[1][0]

def _status_automacao_v71():
    st.markdown("### 🤖 Automação dos Dados — V7.6")
    st.caption(
        "O app preenche automaticamente tudo que possui fonte oficial disponível. "
        "Consenso de mercado e probabilidades FOMC não são inventados."
    )

    rows = []
    for nome in ["IPC anual","IPC Núcleo anual","PCE anual","PCE Núcleo anual",
                 "Payroll","Desemprego","Fed Funds efetivo","Treasury 2Y",
                 "Treasury 10Y","USD amplo"]:
        val, dt = _auto_anterior_v71(nome)
        rows.append({
            "Dado": nome,
            "Automático": "✅" if val is not None else "⚠️",
            "Último/Anterior": round(val, 3) if val is not None else "—",
            "Data": dt.strftime("%d/%m/%Y") if dt is not None else "—",
            "Fonte": "FRED",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.info(
        "Você NÃO precisa digitar CPI, PCE, Payroll, desemprego, Fed Funds, "
        "Treasuries ou índice amplo do USD quando a FRED estiver disponível."
    )
    st.info(
        "CONSENSO/FORECAST: modo híbrido. A fonte oficial preenche Anterior/Real; "
        "você informa somente o consenso quando não houver fonte gratuita confiável."
    )

def _sincronizar_anteriores_v711():
    """
    V7.1.1 — prepara somente as keys do painel de consenso que AINDA não
    foram instanciadas. As keys anterior_* pertencem a number_inputs já
    criados no Painel EUA e não podem ser alteradas depois da criação.
    """
    for nome in ["IPC anual","IPC Núcleo anual","PCE anual","PCE Núcleo anual",
                 "Payroll","Desemprego"]:
        val, _ = _auto_anterior_v71(nome)
        if val is not None:
            k = f"v67_anterior_{nome}"
            if k not in st.session_state:
                st.session_state[k] = float(val)


_sincronizar_anteriores_v711()


# =========================================================
# ABA 3 — PARES
# =========================================================
with abas[4]:
    _status_automacao_v71()

    st.subheader("💱 Painel de Decisão — V7.8")

    usd_base = float(usd_detalhado["score"])
    usd_ajustado = float(st.session_state.get("usd_score_ajustado_surpresas", usd_base))
    ajuste = float(st.session_state.get("usd_ajuste_surpresas", 0.0))
    confirmacao = st.session_state.get("usd_confirmacao_surpresas", "Sem previsões preenchidas")

    # =====================================================
    # V7.7 — CONECTOR FOMC -> USD -> PARES
    # O FOMC pré-release NÃO substitui o macro principal.
    # Ele faz um blend conservador e crescente conforme a reunião se aproxima.
    # Se o FOMC pós-release V6.9 estiver ativo, o pré-release é desligado
    # para evitar dupla contagem.
    # =====================================================
    usd_antes_fomc_v77 = float(usd_ajustado)
    fomc_score_v77 = float(st.session_state.get("v76_fomc_usd_score", 50.0))
    fomc_ativo_v77 = bool(st.session_state.get("v76_fomc_auto_ativo", False))
    fomc_pos_release_v77 = bool(st.session_state.get("v69_fomc_surprise_ativo", False))
    peso_fomc_v77 = 0.0
    evento_v77 = _proximo_evento_macro_v65()

    if (
        fomc_ativo_v77
        and not fomc_pos_release_v77
        and isinstance(evento_v77, dict)
        and evento_v77.get("disponivel", False)
        and "fomc" in _normalizar_texto_v73(evento_v77.get("evento", ""))
    ):
        dias_v77 = int(evento_v77.get("dias", 999))
        if dias_v77 <= 2:
            peso_fomc_v77 = 0.25
        elif dias_v77 <= 7:
            peso_fomc_v77 = 0.20
        elif dias_v77 <= 14:
            peso_fomc_v77 = 0.12
        else:
            peso_fomc_v77 = 0.06

        usd_ajustado = (
            (1.0 - peso_fomc_v77) * usd_ajustado
            + peso_fomc_v77 * fomc_score_v77
        )

    st.session_state["v77_usd_antes_fomc"] = float(usd_antes_fomc_v77)
    st.session_state["v77_usd_pos_fomc"] = float(usd_ajustado)
    st.session_state["v77_peso_fomc"] = float(peso_fomc_v77)
    st.session_state["v77_fomc_integrado"] = bool(peso_fomc_v77 > 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("USD macro base", f"{usd_base:.0f}/100")
    c2.metric("Ajuste das surpresas", f"{ajuste:+.1f}")
    c3.metric("FOMC/USD", f"{fomc_score_v77:.0f}/100" if fomc_ativo_v77 else "—")
    c4.metric("USD usado nos pares", f"{usd_ajustado:.1f}/100")
    st.caption(f"Leitura das surpresas: {confirmacao}")

    if peso_fomc_v77 > 0:
        st.info(
            f"🔗 **V7.7 integrado:** FOMC {fomc_score_v77:.0f}/100 recebeu peso de "
            f"{peso_fomc_v77*100:.0f}% por proximidade da reunião. "
            f"USD: {usd_antes_fomc_v77:.1f} → {usd_ajustado:.1f}. "
            "Esse USD atualizado alimenta automaticamente todos os pares, a matriz e o Score Mestre."
        )
    elif fomc_pos_release_v77:
        st.info(
            "🔗 O FOMC pré-release foi desligado porque o módulo pós-release está ativo. "
            "Isso evita contar o mesmo evento duas vezes."
        )

    # Mantém o seletor original e integra o USD ajustado.
    pares_convencionais = ["EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD", "USD/JPY", "USD/CHF", "USD/CAD"]
    par_escolhido = st.selectbox("Par Forex", pares_convencionais, index=0)
    base, cotada = par_escolhido.split("/")

    if base != cotada:
        score_base = usd_ajustado if base == "USD" else float(ranking.loc[ranking["Código"] == base, "Pontuação_Final"].iloc[0])
        score_cotada = usd_ajustado if cotada == "USD" else float(ranking.loc[ranking["Código"] == cotada, "Pontuação_Final"].iloc[0])
        diferenca = score_base - score_cotada
        ad = abs(diferenca)

        if ad < 6:
            acao, nivel, icone = f"SEM VANTAGEM MACRO CLARA EM {base}/{cotada}", "BAIXA", "⚪"
        elif diferenca > 0:
            acao, icone = f"COMPRA {base}/{cotada}", "🟢"
            nivel = "ALTA" if ad >= 20 else "MODERADA"
        else:
            acao, icone = f"VENDA {base}/{cotada}", "🔴"
            nivel = "ALTA" if ad >= 20 else "MODERADA"

        st.markdown("### 🎯 Conclusão integrada")
        msg = f"{icone} **{acao}** | Força relativa inicial: **{nivel}**"
        if icone == "🟢": st.success(msg)
        elif icone == "🔴": st.error(msg)
        else: st.info(msg)

        x1,x2,x3=st.columns(3)
        x1.metric(base, f"{score_base:.1f}/100")
        x2.metric("Diferença macro", f"{diferenca:+.1f}")
        x3.metric(cotada, f"{score_cotada:.1f}/100")

        # V5.7: confiança passa a exigir confluência, não apenas distância entre scores.
        confl = calcular_confluencia_v60(
            base, cotada, diferenca, usd_ajustado, ajuste,
            fed.get("tom", "Neutro"), ranking
        )

        st.markdown("### 🧩 Confluência do sinal")
        cf1, cf2, cf3, cf4 = st.columns(4)
        cf1.metric("A favor", f"{confl['favor']:.0f}%")
        cf2.metric("Contra", f"{confl['contra']:.0f}%")
        cf3.metric("Score final", f"{confl['score_confluencia']:.0f}/100")
        cf4.metric("Qualidade", f"{confl['qualidade_confluencia']:.0f}%")

        detalhes = []
        for nome_sinal, estado, peso, fator, peso_eff in confl["linhas_dinamicas"]:
            icon = "🟢" if estado > 0 else "🔴" if estado < 0 else "⚪"
            detalhes.append({
                "Componente": nome_sinal,
                "Leitura": icon,
                "Peso nominal": f"{peso:.0f}%",
                "Qualidade/frescor": f"{fator*100:.0f}%",
                "Peso efetivo": f"{peso_eff:.1f}%",
            })
        st.dataframe(pd.DataFrame(detalhes), width="stretch", hide_index=True)

        dt = confl["diferencial_taxas"]
        mercado3m = confl["mercado_3m"]
        tend = confl["tendencias"]
        st.markdown("#### 📐 Qualidade macro da V7.1")
        q1, q2, q3 = st.columns(3)
        with q1:
            if dt["base"] is not None and dt["cotada"] is not None:
                st.metric("Diferencial de juros", f"{dt['dif']:+.2f} p.p.")
                st.caption(f"{base}: {dt['base']:.2f}% | {cotada}: {dt['cotada']:.2f}%")
                if dt["vantagem"] == "Equilibrado":
                    st.caption("⚪ Vantagem de juros: equilibrada")
                else:
                    st.caption(f"🟢 Vantagem de juros: {dt['vantagem']}")
            else:
                st.metric("Diferencial de juros", "—")
                st.caption(f"Diagnóstico: moeda={dt.get('col_codigo')} | juros={dt.get('col_juros')}")
        with q2:
            st.metric("Tendência macro EUA", f"{tend['score']:.0f}/100")
        with q3:
            st.metric("Treasury 2Y — tendência", tend["Treasury 2Y"]["texto"])
            st.caption(f"Δ médio: {tend['Treasury 2Y']['delta']:+.3f}")

        st.markdown("#### 💹 Spread de juros de mercado — 3 meses")
        if mercado3m["disponivel"]:
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric(
                    f"{base} mercado 3M",
                    f"{mercado3m['base']['valor']:.2f}%"
                )
                st.caption(
                    f"FRED {mercado3m['base']['serie']} · {mercado3m['base']['data']}"
                )
            with m2:
                st.metric(
                    f"{cotada} mercado 3M",
                    f"{mercado3m['cotada']['valor']:.2f}%"
                )
                st.caption(
                    f"FRED {mercado3m['cotada']['serie']} · {mercado3m['cotada']['data']}"
                )
            with m3:
                st.metric(
                    "Spread de mercado",
                    f"{mercado3m['spread']:+.2f} p.p.",
                    delta=f"{mercado3m['delta_spread']:+.2f} p.p. vs período anterior"
                )
                st.caption(f"Vantagem: {mercado3m['vantagem']} · {mercado3m['movimento']}")

            idade_max = max(
                mercado3m["base"]["idade"] or 9999,
                mercado3m["cotada"]["idade"] or 9999
            )
            if idade_max > 120:
                st.warning(
                    "🟡 O spread de mercado usa pelo menos uma série antiga. "
                    "A V7.1.1 reduz automaticamente o peso desse componente até a FRED atualizar."
                )
        else:
            st.warning(
                "⚠️ Spread de mercado 3M indisponível para este par. "
                "A confluência continua usando juros oficiais e os demais componentes."
            )

        st.caption(
            "Na V7.1.1, 'mercado 3M' é uma comparação de taxas de 3 meses/90 dias "
            "da FRED/OECD. Mantivemos o Treasury 2Y como tendência dos EUA, mas não "
            "misturamos 2Y americano com uma maturidade estrangeira diferente."
        )

        with st.expander("Ver tendências usadas no modelo"):
            trend_rows = []
            for nome_t in ["CPI", "Core CPI", "Desemprego", "Treasury 2Y", "Broad USD"]:
                x = tend[nome_t]
                trend_rows.append({
                    "Indicador": nome_t,
                    "Tendência": x["texto"],
                    "Variação média": round(x["delta"], 4),
                })
            st.dataframe(pd.DataFrame(trend_rows), width="stretch", hide_index=True)
            st.caption("A V7.1.1 combina diferencial de juros oficiais, spread de mercado e direção do spread com pesos ajustados pelo frescor dos dados. O Treasury 2Y permanece como tendência dos EUA, sem ser comparado diretamente a uma maturidade estrangeira diferente.")

        # Substitui a confiança antiga pela confiança de confluência.
        if "SEM VANTAGEM" in acao:
            nivel_final = "BAIXA"
        else:
            nivel_final = confl["nivel"]

        if nivel_final == "ALTA":
            st.success(f"✅ Sinal macro confirmado por confluência: {nivel_final}")
        elif nivel_final == "MODERADA":
            st.warning(f"🟡 Sinal macro com confluência: {nivel_final}")
        else:
            st.info("⚪ Confluência baixa — evitar tratar a diferença de scores como sinal forte.")

        score_final = confl["score_confluencia"]
        qualidade_final = confl["qualidade_confluencia"]

        st.markdown("### 🧭 Decisão V7.1")
        if "SEM VANTAGEM" in acao or score_final < 58 or qualidade_final < 50:
            st.info(
                f"⚪ **NEUTRO / AGUARDAR** — Score {score_final:.0f}/100 | "
                f"Qualidade {qualidade_final:.0f}%"
            )
        elif nivel_final == "ALTA":
            st.success(
                f"✅ **{acao}** — Confluência ALTA | Score {score_final:.0f}/100 | "
                f"Qualidade {qualidade_final:.0f}%"
            )
        elif nivel_final == "MODERADA":
            st.warning(
                f"🟡 **{acao}** — Confluência MODERADA | Score {score_final:.0f}/100 | "
                f"Qualidade {qualidade_final:.0f}%"
            )
        else:
            st.info(
                f"⚪ **AGUARDAR CONFIRMAÇÃO** — direção macro: {acao} | "
                f"Score {score_final:.0f}/100 | Qualidade {qualidade_final:.0f}%"
            )

        st.caption(
            "Score final = confluência direcional ajustada pela qualidade/frescor dos dados. "
            "Não representa probabilidade de lucro ou taxa de acerto."
        )

        _mostrar_explicador_v62(
            par_escolhido, base, cotada, diferenca, confl,
            float(score_base), float(score_cotada)
        )

        _mostrar_expectativa_no_par_v68(base, cotada)

        _mostrar_fomc_surprise_v69(base, cotada)

        _mostrar_score_mestre_v70(base, cotada, diferenca, confl)

        _mostrar_risco_timing_v65(confl, diferenca)

        # V8.0 — Central Mestre, usando os mesmos dados reais do par.
        _central_decisao_v81(
            par=par_escolhido,
            base=base,
            cotada=cotada,
            score_base=float(score_base),
            score_cotada=float(score_cotada),
            diferenca=float(diferenca),
            confl=confl,
        )

        _painel_validacao_v82(
            par=par_escolhido,
            base=base,
            cotada=cotada,
            score_base=float(score_base),
            score_cotada=float(score_cotada),
            diferenca=float(diferenca),
            confl=confl,
        )

        # V7.8.1 — explicador executado no mesmo escopo do par,
        # usando diretamente as variáveis reais já calculadas.
        _painel_explicador_v78(
            par=par_escolhido,
            moeda_base=base,
            moeda_cotada=cotada,
            score_base=float(score_base),
            score_cotada=float(score_cotada),
            diferenca=float(diferenca),
            confluencia=float(confl["score_confluencia"]),
            qualidade=float(confl["qualidade_confluencia"]),
            timing=None,
            score_mestre=float(confl["score_confluencia"]),
            risco_calendario=None,
        )

        _raiox_v79(
            par=par_escolhido,
            base=base,
            cotada=cotada,
            score_base=float(score_base),
            score_cotada=float(score_cotada),
            diferenca=float(diferenca),
            confl=confl,
        )

        st.write(f"Motivo: {base} está em **{score_base:.1f}** e {cotada} em **{score_cotada:.1f}**. O USD, quando presente, já inclui o ajuste das surpresas econômicas.")
        st.warning("⚠️ O viés macro não é gatilho de entrada nem probabilidade de lucro. Confirme preço, estrutura, liquidez, sessão e risco.")
        st.markdown("#### 📝 Registrar sinal para teste histórico")
        preco = st.number_input("Preço de entrada", min_value=0.00001, max_value=1000.0, value=1.10000, step=0.00001, format="%.5f")
        horizonte = st.selectbox("Tempo para avaliar (horas)", [1,4,8,24,48,72], 3)
        if st.button("Registrar sinal"):
            conf_reg = float(np.clip(0.5 + diferenca/100, 0.01, 0.99))
            registrar_sinal(f"{base}/{cotada}", conf_reg, score_base, score_cotada, preco, horizonte)
            st.success("✅ Sinal registrado!")

    st.markdown("---")
    st.markdown("### 🏆 Matriz Inteligente — V9.3.5")
    st.caption(
        "Todos os pares abaixo passam pelo mesmo motor de confluência, qualidade e frescor "
        "usado na análise individual."
    )

    pares_matriz = ["EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CHF","USD/CAD"]
    scores_ranking = dict(zip(ranking["Código"], ranking["Pontuação_Final"]))
    linhas_matriz = []

    for par_m in pares_matriz:
        b, q = par_m.split("/")
        sb = usd_ajustado if b == "USD" else float(scores_ranking.get(b, 50.0))
        sq = usd_ajustado if q == "USD" else float(scores_ranking.get(q, 50.0))
        dif_m = float(sb - sq)

        if abs(dif_m) < 6:
            direcao_m = "⚪ NEUTRO"
        elif dif_m > 0:
            direcao_m = f"🟢 COMPRA {par_m}"
        else:
            direcao_m = f"🔴 VENDA {par_m}"

        conf_m = calcular_confluencia_v60(
            b, q, dif_m, usd_ajustado, ajuste,
            fed.get("tom", "Neutro"), ranking
        )

        score_m = float(conf_m["score_confluencia"])
        qualidade_m = float(conf_m["qualidade_confluencia"])
        nivel_m = str(conf_m["nivel"])

        # Regra operacional conservadora: sem direção ou baixa cobertura => aguardar.
        if abs(dif_m) < 6 or score_m < 58 or qualidade_m < 50:
            decisao_m = "⚪ AGUARDAR"
            nivel_exibido = "BAIXA"
        elif nivel_m == "ALTA":
            decisao_m = direcao_m
            nivel_exibido = "ALTA"
        elif nivel_m == "MODERADA":
            decisao_m = direcao_m
            nivel_exibido = "MODERADA"
        else:
            decisao_m = "⚪ AGUARDAR CONFIRMAÇÃO"
            nivel_exibido = "BAIXA"

        # Ranking composto: premia confluência + qualidade, sem chamar de probabilidade.
        indice_rank = float(np.clip(
            score_m * 0.60 + qualidade_m * 0.40, 0, 100
        ))

        linhas_matriz.append({
            "Par": par_m,
            "Direção": decisao_m,
            "Dif. macro": round(dif_m, 1),
            "Score final": round(score_m, 0),
            "Qualidade": round(qualidade_m, 0),
            "Confluência": nivel_exibido,
            "Índice ranking": round(indice_rank, 1),
        })

    matriz_v61 = pd.DataFrame(linhas_matriz).sort_values(
        ["Índice ranking", "Qualidade", "Score final"],
        ascending=False
    ).reset_index(drop=True)

    matriz_v61.insert(0, "Ranking", range(1, len(matriz_v61) + 1))

    # =====================================================
    # V8.7.3 — COLETA HISTÓRICA MULTIPARES ATÔMICA
    # Regra: 1 par + 1 DIA DE COLETA = no máximo 1 fotografia.
    # Registros anteriores ficam como LEGADO e não contaminam a estatística nova.
    # =====================================================
    _df_v873 = _carregar_sinais_v82()
    _novas_v873 = []
    _dia_lote_v873 = _dia_coleta_v873()

    _evento_v873 = _proximo_evento_macro_v65()
    _evento_nome_v873, _dias_v873, _impacto_v873 = "—", None, "—"
    if isinstance(_evento_v873, dict) and _evento_v873.get("disponivel", False):
        _evento_nome_v873 = str(_evento_v873.get("evento", "—"))
        _dias_v873 = _evento_v873.get("dias")
        _impacto_v873 = str(_evento_v873.get("impacto", "—"))

    _fomc_score_v873 = None
    _fomc_peso_v873 = None
    if st.session_state.get("v77_fomc_integrado", False):
        _fomc_score_v873 = float(st.session_state.get("v76_fomc_usd_score", 50.0))
        _fomc_peso_v873 = float(st.session_state.get("v77_peso_fomc", 0.0)) * 100.0

    _alto_v873 = str(_impacto_v873).upper() in ("MÁXIMO", "MAXIMO", "ALTO")
    if _dias_v873 is not None and _dias_v873 <= 2 and _alto_v873:
        _timing_v873 = "AGUARDAR"
    elif _dias_v873 is not None and _dias_v873 <= 7 and _alto_v873:
        _timing_v873 = "ATENÇÃO"
    else:
        _timing_v873 = "NORMAL"

    _matriz_por_par_v873 = {str(r["Par"]): r for r in linhas_matriz}

    for _par_v873 in pares_matriz:
        _r873 = _matriz_por_par_v873[_par_v873]
        _dec873 = str(_r873["Direção"]).upper()

        # A decisão final da Matriz manda.
        if "AGUARDAR" in _dec873 or "NEUTRO" in _dec873:
            continue
        if "COMPRA" in _dec873:
            _dir873 = "BUY"
        elif "VENDA" in _dec873:
            _dir873 = "SELL"
        else:
            continue

        # Já existe fotografia NOVA deste par hoje?
        _ja873 = False
        if isinstance(_df_v873, pd.DataFrame) and not _df_v873.empty:
            _ja873 = (
                (_df_v873["par"].astype(str).str.upper().str.strip() == _par_v873) &
                (_df_v873["versao_coleta"].astype(str) == "V8.7.3") &
                (_df_v873["dia_coleta"].astype(str) == _dia_lote_v873)
            ).any()

        if not _ja873 and _novas_v873:
            _ja873 = any(
                x["par"] == _par_v873 and x["dia_coleta"] == _dia_lote_v873
                for x in _novas_v873
            )

        if _ja873:
            continue

        _preco873, _dt873, _serie873 = _fred_preco_par_v87(_par_v873)
        if _preco873 is None or _dt873 is None:
            continue

        _b873, _q873 = _par_v873.split("/")
        _sb873 = usd_ajustado if _b873 == "USD" else float(scores_ranking.get(_b873, 50.0))
        _sq873 = usd_ajustado if _q873 == "USD" else float(scores_ranking.get(_q873, 50.0))
        _dif873 = float(_sb873 - _sq873)

        _conf873 = calcular_confluencia_v60(
            _b873, _q873, _dif873, usd_ajustado, ajuste,
            fed.get("tom", "Neutro"), ranking
        )

        _novas_v873.append({
            "timestamp": pd.Timestamp.now(),
            "par": _par_v873,
            "direcao": _dir873,
            "score_mestre": float(_conf873["score_confluencia"]),
            "qualidade": float(_conf873["qualidade_confluencia"]),
            "score_base": float(_sb873),
            "score_cotada": float(_sq873),
            "diferenca": float(_dif873),
            "fomc_score": _fomc_score_v873,
            "fomc_peso": _fomc_peso_v873,
            "evento": _evento_nome_v873,
            "dias_evento": _dias_v873,
            "impacto": _impacto_v873,
            "timing": _timing_v873,
            "preco_entrada": float(_preco873),
            "data_preco": pd.Timestamp(_dt873),
            "avaliado": False,
            "preco_saida": None,
            "data_saida": None,
            "retorno_pct": None,
            "acertou": None,
            "versao_coleta": "V8.7.3",
            "dia_coleta": _dia_lote_v873,
        })

    if _novas_v873:
        _df_v873 = pd.concat([_df_v873, pd.DataFrame(_novas_v873)], ignore_index=True)
        _salvar_sinais_v82(_df_v873)

    st.caption(
        "🤖 V8.7.3 multipares: usa exatamente a decisão final da Matriz. "
        "Regra anti-duplicata: 1 par + 1 dia de coleta = no máximo 1 registro. "
        "Registros anteriores ficam como LEGADO."
    )

    st.dataframe(
        matriz_v61,
        width="stretch",
        hide_index=True,
        column_config={
            "Score final": st.column_config.NumberColumn(format="%.0f/100"),
            "Qualidade": st.column_config.NumberColumn(format="%.0f%%"),
            "Índice ranking": st.column_config.NumberColumn(format="%.1f"),
        }
    )

    st.markdown("#### ⭐ Melhores oportunidades macro")
    oportunidades = matriz_v61[
        ~matriz_v61["Direção"].str.contains("AGUARDAR|NEUTRO", regex=True)
    ].head(3)

    if oportunidades.empty:
        st.info("⚪ Nenhum dos 7 pares tem confluência e qualidade suficientes neste momento.")
    else:
        for _, r in oportunidades.iterrows():
            if "COMPRA" in r["Direção"]:
                st.success(
                    f"#{int(r['Ranking'])} **{r['Direção']}** — "
                    f"Score {r['Score final']:.0f}/100 | Qualidade {r['Qualidade']:.0f}% | "
                    f"Confluência {r['Confluência']}"
                )
            else:
                st.error(
                    f"#{int(r['Ranking'])} **{r['Direção']}** — "
                    f"Score {r['Score final']:.0f}/100 | Qualidade {r['Qualidade']:.0f}% | "
                    f"Confluência {r['Confluência']}"
                )

    st.caption(
        "Índice ranking = 60% do score de confluência + 40% da qualidade/cobertura. "
        "É uma pontuação interna para ordenar pares, não uma probabilidade de ganho."
    )

# =========================================================
# ABA 4 — FED E NOTÍCIAS
# =========================================================
with abas[5]:
    st.subheader("🏦 Federal Reserve e impacto no USD")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Tom do Fed", fed["tom"])
    with c2:
        st.metric("Intensidade da leitura", f"{fed['forca']:+.2f}")
    with c3:
        impacto_geral = "🟢 Favorável ao USD" if fed["forca"] > 0.15 else "🔴 Desfavorável ao USD" if fed["forca"] < -0.15 else "⚪ Neutro"
        st.metric("Impacto provável", impacto_geral)

    st.caption(
        "O sistema filtra manchetes de baixa relevância e dá mais peso a juros, inflação, FOMC, emprego e comunicação do Fed. "
        "Isso reduz ruído de notícias pessoais ou sem impacto macroeconômico."
    )

    st.markdown("### 📰 Notícias relevantes — português + original")
    analisadas = fed.get("analisadas", [])
    if analisadas:
        for item in analisadas:
            traducao, provedor = _traduzir_manchete(item["titulo"])
            selo_rel = "🔥 Alta" if item["relevancia"] == "Alta" else "🟡 Média"
            st.markdown(f"#### 🇧🇷 {traducao}")
            st.markdown(
                f"**Impacto no USD:** {item['direcao']}  \n"
                f"**Relevância:** {selo_rel}  \n"
                f"**Fonte:** {item['fonte']}"
            )
            st.caption(item["explicacao"])
            with st.expander("🌐 Ver manchete original"):
                st.write(item["corpo"])
                st.caption(f"Tradução: {provedor}")
            st.markdown("---")
    else:
        st.info("Nenhuma manchete macroeconômica relevante encontrada nesta atualização.")

    st.markdown("### 🧭 Como interpretar")
    st.markdown(
        "**🔴 Fed restritivo (hawkish)** → maior chance de juros altos/alta de juros → normalmente favorece o USD.  \n"
        "**🟢 Fed flexível (dovish)** → maior chance de cortes de juros → normalmente pressiona o USD.  \n"
        "**⚪ Neutro** → sinal misto ou insuficiente; dê mais peso aos dados macro e aos rendimentos dos Treasuries."
    )
    st.warning(
        "A análise de manchetes é auxiliar e não substitui o comunicado oficial do FOMC, a coletiva, a ata, o Dot Plot e os dados econômicos."
    )

# =========================================================
# ABA 5 — HISTÓRICO
# =========================================================
with abas[6]:
    st.subheader("Histórico das classificações")
    st.caption("No Streamlit Community Cloud, arquivos locais podem desaparecer após reinicialização ou novo deploy. Para histórico permanente, use um banco externo.")
    historico = carregar_snapshots()
    if historico.empty:
        st.info("Ainda não há histórico. Salve um registro na aba 🏆 Classificação.")
    else:
        st.dataframe(historico.sort_values("data", ascending=False), width="stretch")

# =========================================================
# ABA 6 — TESTE HISTÓRICO
# =========================================================
with abas[7]:
    st.subheader("📈 Teste Histórico — Validação do Modelo")

    if render_operational_backtest_panel is not None:
        render_operational_backtest_panel()
        st.divider()
    else:
        st.warning("Backtest operacional avançado indisponível neste carregamento.")
        if _ATLASQUANT_BACKTEST_IMPORT_ERROR:
            st.caption(_ATLASQUANT_BACKTEST_IMPORT_ERROR)

    st.markdown("### Histórico legado de sinais")
    st.caption("Mantido por compatibilidade; o painel acima é o backtest operacional auditável.")
    sinais = carregar_sinais()

    if sinais.empty:
        st.info("Nenhum sinal registrado. Registre sinais na aba 💱 Pares e Confiança.")
    else:
        st.dataframe(sinais.sort_values("data", ascending=False), width="stretch")

        abertos = sinais[sinais["resultado"].isna()]
        if not abertos.empty:
            st.markdown("### ✅ Fechar sinal e informar o resultado")
            id_selecionado = st.selectbox("Sinal", abertos["id"].astype(str).tolist())
            saida = st.number_input(
                "Preço de saída",
                min_value=0.00001,
                max_value=1000.0,
                value=1.10000,
                step=0.00001,
                format="%.5f",
            )
            if st.button("Salvar resultado"):
                st.toast(atualizar_resultado(id_selecionado, saida))
                st.rerun()

        metricas = metricas_backtest(sinais)
        if metricas:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Operações", metricas["n"])
            with c2:
                st.metric("Acurácia", f"{metricas['acuracia']*100:.1f}%")
            with c3:
                st.metric("Índice de Brier", f"{metricas['brier']:.3f}")

            if metricas["brier"] < 0.12:
                st.success("✅ Excelente — Índice de Brier abaixo de 0,12")
            elif metricas["brier"] <= 0.20:
                st.warning("⚠️ Razoável — Índice de Brier entre 0,12 e 0,20")
            else:
                st.error("🔴 Índice de Brier alto — recalibre pesos e sensibilidade")

st.divider()
st.caption(
    f"Fontes/estado: {', '.join(f'{k}: {v}' for k, v in STATUS_FONTE.items())} | "
    "Uso educacional. Não constitui recomendação de investimento."
)


# =========================================================
# V7.5 — MODELO FOMC AUTOMÁTICO (ESTIMATIVA PRÓPRIA)
# NÃO É CME FEDWATCH
# =========================================================

def _fred_ultimos_v75(series_id, n=30):
    try:
        obs = _fred_obs_v71(series_id, n)
        return obs if obs else []
    except Exception:
        return []

def _ultimo_valor_v75(series_id):
    obs = _fred_ultimos_v75(series_id, 10)
    return (float(obs[0][1]), obs[0][0]) if obs else (None, None)

def _tendencia_v75(series_id, janela=5):
    obs = _fred_ultimos_v75(series_id, max(10, janela + 2))
    vals = [float(x[1]) for x in obs[:janela] if x[1] is not None]
    if len(vals) < 2:
        return 0.0
    # obs desc: mais recente - mais antigo da janela
    return vals[0] - vals[-1]

def _modelo_fomc_v75():
    """
    Heurística transparente:
    - EFFR mostra a taxa overnight efetiva atual.
    - Treasury 2Y incorpora expectativas de juros/crescimento/inflação, mas NÃO é Fed Funds futures.
    - Score macro USD já existente adiciona contexto.
    Resultado = probabilidades INTERNAS do modelo, não probabilidades negociadas no CME.
    """
    effr, dt_effr = _ultimo_valor_v75("DFF")
    y2, dt_y2 = _ultimo_valor_v75("DGS2")
    y2_trend = _tendencia_v75("DGS2", 5)

    # Usa o score macro já calculado pelo app quando disponível.
    usd_score = None
    for k in ("score_usd_final", "usd_score_final", "score_usd", "forca_usd"):
        try:
            v = st.session_state.get(k)
            if isinstance(v, (int, float)):
                usd_score = float(v)
                break
        except Exception:
            pass
    if usd_score is None:
        usd_score = 50.0

    if effr is None or y2 is None:
        return {
            "ok": False, "effr": effr, "y2": y2, "dt_effr": dt_effr, "dt_y2": dt_y2,
            "motivo": "Faltam dados oficiais de juros para calcular a estimativa."
        }

    spread = y2 - effr

    # Índice hawkish/dovish. Positivo = mais hawkish; negativo = mais dovish.
    # O spread 2Y-EFFR recebe maior peso; tendência recente do 2Y e macro são confirmação.
    hawk = 0.0
    hawk += max(-35.0, min(35.0, spread * 28.0))
    hawk += max(-15.0, min(15.0, y2_trend * 35.0))
    hawk += max(-15.0, min(15.0, (usd_score - 50.0) * 0.55))
    hawk = max(-50.0, min(50.0, hawk))

    # Converte índice em distribuição suave de 3 cenários.
    # Manutenção domina perto de zero; extremos deslocam massa para corte/alta.
    manut = max(15.0, 70.0 - abs(hawk) * 1.05)
    restante = 100.0 - manut
    viés = max(-1.0, min(1.0, hawk / 45.0))
    alta = restante * (0.5 + 0.5 * viés)
    corte = restante - alta

    corte = max(0.0, corte)
    alta = max(0.0, alta)
    total = corte + manut + alta
    corte, manut, alta = [100.0*x/total for x in (corte, manut, alta)]

    esperado_pb = (-25.0*corte + 25.0*alta) / 100.0
    score_usd_fomc = max(0.0, min(100.0, 50.0 + esperado_pb))

    return {
        "ok": True,
        "effr": effr, "dt_effr": dt_effr,
        "y2": y2, "dt_y2": dt_y2,
        "spread": spread, "trend2y": y2_trend, "usd_score": usd_score,
        "hawk": hawk,
        "corte": corte, "manut": manut, "alta": alta,
        "esperado_pb": esperado_pb,
        "score_usd_fomc": score_usd_fomc,
    }

def _painel_fomc_auto_v75():
    evento = _proximo_evento_macro_v65()
    if not evento or not evento.get("disponivel", True):
        return
    nome = _normalizar_texto_v73(evento.get("evento", ""))
    if "fomc" not in nome:
        return

    st.markdown("## 🏦 FOMC Automático — V7.5")
    st.warning(
        "⚠️ ESTIMATIVA DO MODELO — NÃO É CME FEDWATCH. "
        "As probabilidades abaixo são calculadas pelo próprio app e não representam "
        "probabilidades negociadas nos futuros de Fed Funds."
    )

    r = _modelo_fomc_v75()
    if not r["ok"]:
        st.error(r["motivo"])
        return

    c1,c2,c3 = st.columns(3)
    c1.metric("✂️ Corte 25 pb", f"{r['corte']:.1f}%")
    c2.metric("⏸️ Manutenção", f"{r['manut']:.1f}%")
    c3.metric("⬆️ Alta 25 pb", f"{r['alta']:.1f}%")

    d1,d2,d3,d4 = st.columns(4)
    d1.metric("Fed Funds efetivo", f"{r['effr']:.2f}%")
    d2.metric("Treasury 2Y", f"{r['y2']:.2f}%")
    d3.metric("2Y − Fed Funds", f"{r['spread']:+.2f} p.p.")
    d4.metric("Movimento esperado", f"{r['esperado_pb']:+.1f} pb")

    if r["hawk"] >= 12:
        leitura = "🟢 HAWKISH — modelo favorece juros mais altos / USD"
    elif r["hawk"] <= -12:
        leitura = "🔴 DOVISH — modelo favorece juros mais baixos / pressão no USD"
    else:
        leitura = "🟡 NEUTRO / MISTO — manutenção continua relevante"

    st.info(f"**Leitura automática:** {leitura}")
    st.progress(int(round(r["score_usd_fomc"])))
    st.caption(f"Score FOMC/USD do modelo: {r['score_usd_fomc']:.0f}/100")

    # Fonte única para outros módulos futuros, sem sobrescrever widgets existentes.
    st.session_state["v75_fomc_auto_ativo"] = True
    st.session_state["v75_prob_corte"] = float(r["corte"])
    st.session_state["v75_prob_manut"] = float(r["manut"])
    st.session_state["v75_prob_alta"] = float(r["alta"])
    st.session_state["v75_esperado_pb"] = float(r["esperado_pb"])
    st.session_state["v75_fomc_usd_score"] = float(r["score_usd_fomc"])

    st.caption(
        "Entradas automáticas: Effective Federal Funds Rate (DFF), Treasury 2Y (DGS2) "
        "e contexto do score macro já existente. O Treasury 2Y é um proxy de expectativas, "
        "não substitui contratos Fed Funds Futures."
    )


# =========================================================
# V7.6 — FOMC PROBABILÍSTICO CALIBRADO
# Separa PRESSÃO monetária de PROBABILIDADE da próxima decisão.
# NÃO É CME FEDWATCH.
# =========================================================

def _sigmoid_v76(x):
    try:
        return 1.0 / (1.0 + math.exp(-float(x)))
    except Exception:
        return 0.5

def _score_macro_fomc_v76():
    """
    Contexto macro 0-100 para o FOMC.
    50 = neutro; >50 = mais hawkish; <50 = mais dovish.
    Reaproveita o score USD existente apenas como contexto e comprime sua influência.
    """
    score = 50.0
    for k in ("score_usd_final", "usd_score_final", "score_usd", "forca_usd"):
        v = st.session_state.get(k)
        if isinstance(v, (int, float)):
            score = float(v)
            break
    return max(25.0, min(75.0, score))

def _modelo_fomc_calibrado_v76():
    effr, dt_effr = _ultimo_valor_v75("DFF")
    y3m, dt_3m = _ultimo_valor_v75("DGS3MO")
    y2, dt_y2 = _ultimo_valor_v75("DGS2")

    tr3m = _tendencia_v75("DGS3MO", 5)
    tr2y = _tendencia_v75("DGS2", 5)
    macro = _score_macro_fomc_v76()

    if effr is None or y2 is None:
        return {"ok": False, "motivo": "Faltam Fed Funds efetivo (DFF) ou Treasury 2Y (DGS2) na FRED."}

    # 1) PRESSÃO HAWKISH/DOVISH (0-100)
    # Treasury 3M melhora o modelo, mas NÃO é obrigatório.
    # Se DGS3MO estiver indisponível, usa DFF + DGS2 + tendência 2Y + macro.
    spread2y = y2 - effr
    tem_3m = y3m is not None

    if tem_3m:
        spread3m = y3m - effr
        pressao_raw = (
            50.0
            + max(-18.0, min(18.0, spread3m * 24.0))
            + max(-8.0, min(8.0, spread2y * 7.0))
            + max(-7.0, min(7.0, tr3m * 28.0))
            + max(-5.0, min(5.0, tr2y * 12.0))
            + max(-7.0, min(7.0, (macro - 50.0) * 0.28))
        )
    else:
        spread3m = None
        # Fallback conservador: reduz a força do proxy 2Y para não exagerar.
        pressao_raw = (
            50.0
            + max(-15.0, min(15.0, spread2y * 12.0))
            + max(-7.0, min(7.0, tr2y * 14.0))
            + max(-8.0, min(8.0, (macro - 50.0) * 0.32))
        )
    pressao = max(0.0, min(100.0, pressao_raw))

    # 2) PROBABILIDADES CALIBRADAS
    # A curva Treasury é proxy, não Fed Funds Futures.
    # Portanto impomos forte prior de manutenção e limitamos extremos.
    z = (pressao - 50.0) / 12.0
    p_hike_signal = _sigmoid_v76(z)
    p_cut_signal = _sigmoid_v76(-z)

    intensidade = min(1.0, abs(pressao - 50.0) / 35.0)

    # massa máxima fora de "manutenção": 55%.
    # perto do neutro fica muito menor, evitando falsa precisão.
    massa_decisao = 0.18 + 0.37 * intensidade
    direcional = 0.50 + 0.42 * (2.0 * p_hike_signal - 1.0)
    direcional = max(0.08, min(0.92, direcional))

    alta = 100.0 * massa_decisao * direcional
    corte = 100.0 * massa_decisao * (1.0 - direcional)
    manut = 100.0 - alta - corte

    # arredondamento só na apresentação; cálculos continuam contínuos.
    esperado_pb = (-25.0*corte + 25.0*alta) / 100.0

    # Score FOMC/USD mais conservador: ±25 pb esperado -> aproximadamente 25/75.
    score_fomc = max(25.0, min(75.0, 50.0 + esperado_pb))

    if pressao >= 62:
        regime = "HAWKISH"
    elif pressao <= 38:
        regime = "DOVISH"
    else:
        regime = "NEUTRO / MISTO"

    confianca = min(85.0, 45.0 + abs(pressao - 50.0) * 0.9)

    return {
        "ok": True,
        "effr": effr, "dt_effr": dt_effr,
        "y3m": y3m, "dt_3m": dt_3m,
        "y2": y2, "dt_y2": dt_y2,
        "spread3m": spread3m, "spread2y": spread2y,
        "tr3m": tr3m, "tr2y": tr2y, "macro": macro, "tem_3m": tem_3m,
        "pressao": pressao, "regime": regime, "confianca": confianca,
        "corte": corte, "manut": manut, "alta": alta,
        "esperado_pb": esperado_pb, "score_fomc": score_fomc,
    }

def _painel_fomc_calibrado_v76():
    evento = _proximo_evento_macro_v65()
    if not evento or not evento.get("disponivel", True):
        return
    if "fomc" not in _normalizar_texto_v73(evento.get("evento", "")):
        return

    st.markdown("## 🏦 FOMC Probabilístico Calibrado — V7.6.1")
    st.warning(
        "⚠️ MODELO PRÓPRIO — NÃO É CME FEDWATCH. "
        "A curva Treasury é usada como proxy. As porcentagens são estimativas internas, "
        "não probabilidades negociadas em Fed Funds Futures."
    )

    r = _modelo_fomc_calibrado_v76()
    if not r["ok"]:
        st.error(r["motivo"])
        return

    if not r.get("tem_3m", False):
        st.warning(
            "Treasury 3M não veio da FRED nesta execução. "
            "O V7.6.1 ativou o fallback conservador usando Fed Funds + Treasury 2Y + contexto macro. "
            "O cálculo continua funcionando sem inventar o dado de 3 meses."
        )

    st.markdown("### 1️⃣ Pressão monetária")
    a,b,c = st.columns(3)
    a.metric("Pressão Hawkish", f"{r['pressao']:.0f}/100")
    b.metric("Regime", r["regime"])
    c.metric("Confiança do modelo", f"{r['confianca']:.0f}%")
    st.progress(int(round(r["pressao"])))

    st.markdown("### 2️⃣ Estimativa da próxima decisão")
    c1,c2,c3 = st.columns(3)
    c1.metric("✂️ Corte 25 pb", f"{r['corte']:.1f}%")
    c2.metric("⏸️ Manutenção", f"{r['manut']:.1f}%")
    c3.metric("⬆️ Alta 25 pb", f"{r['alta']:.1f}%")

    st.markdown("### 3️⃣ O que está puxando o modelo")
    d1,d2,d3,d4 = st.columns(4)
    d1.metric("Fed Funds efetivo", f"{r['effr']:.2f}%")
    d2.metric("Treasury 3M", f"{r['y3m']:.2f}%" if r["y3m"] is not None else "Indisponível")
    d3.metric("Treasury 2Y", f"{r['y2']:.2f}%")
    d4.metric("Mov. esperado", f"{r['esperado_pb']:+.1f} pb")

    e1,e2,e3 = st.columns(3)
    e1.metric("3M − Fed Funds", f"{r['spread3m']:+.2f} p.p." if r["spread3m"] is not None else "Fallback ativo")
    e2.metric("2Y − Fed Funds", f"{r['spread2y']:+.2f} p.p.")
    e3.metric("Score FOMC/USD", f"{r['score_fomc']:.0f}/100")

    if r["regime"] == "HAWKISH":
        st.info("🟢 **Pressão hawkish:** juros de mercado e contexto macro estão inclinados para política mais restritiva. Isso pode favorecer o USD.")
    elif r["regime"] == "DOVISH":
        st.info("🔴 **Pressão dovish:** juros de mercado e contexto macro estão inclinados para política menos restritiva. Isso pode pressionar o USD.")
    else:
        st.info("🟡 **Cenário misto:** não há pressão suficientemente forte para transformar o sinal em uma decisão extrema.")

    st.caption(
        "Calibração V7.6.1: Treasury 3M tem peso maior quando disponível. "
        "Se ele faltar, entra um fallback conservador com DFF + DGS2. "
        "A manutenção recebe um prior forte porque Treasuries não são contratos Fed Funds Futures."
    )

    # Nova fonte interna. Não sobrescreve widgets antigos.
    st.session_state["v76_fomc_auto_ativo"] = True
    st.session_state["v76_pressao_hawkish"] = float(r["pressao"])
    st.session_state["v76_prob_corte"] = float(r["corte"])
    st.session_state["v76_prob_manut"] = float(r["manut"])
    st.session_state["v76_prob_alta"] = float(r["alta"])
    st.session_state["v76_esperado_pb"] = float(r["esperado_pb"])
    st.session_state["v76_fomc_usd_score"] = float(r["score_fomc"])

    # V7.7 — sincroniza o novo valor com a aba de pares.
    # Só reinicia quando o score realmente mudou, evitando loop.
    _v77_anterior = st.session_state.get("v77_ultimo_fomc_sincronizado")
    _v77_atual = float(r["score_fomc"])
    if _v77_anterior is None or abs(float(_v77_anterior) - _v77_atual) > 0.05:
        st.session_state["v77_ultimo_fomc_sincronizado"] = _v77_atual
        st.rerun()


# =========================================================
# V7.6.1 — RENDERIZAÇÃO SEGURA
# =========================================================
with abas[3]:
    _painel_hibrido_v74()
    _painel_fomc_calibrado_v76()




# =========================================================
# V9.2 — DADOS E LEITURA TÉCNICA AUTOMÁTICA
# Fonte: Twelve Data (quando CHAVE_TWELVE_DATA estiver configurada).
# O motor técnico usa regras explícitas e reproduzíveis.
# =========================================================

def _td_time_series_v92(par: str, interval: str, outputsize: int = 140) -> pd.DataFrame:
    df,err=cached_series(par,interval,outputsize)
    df.attrs["erro_td"]=err
    df.attrs["td_diag"]={"symbol":par,"interval":interval,"api_message":err,
                         "source":"CACHE_AUTOPILOT","candles_validos":len(df)}
    return df
_td_time_series_v92.clear = clear_shared_cache

def _indicadores_tecnicos_v92(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if d.empty:
        return d

    d["ema9"] = d["close"].ewm(span=9, adjust=False).mean()
    d["ema20"] = d["close"].ewm(span=20, adjust=False).mean()
    d["ema21"] = d["close"].ewm(span=21, adjust=False).mean()
    d["ema50"] = d["close"].ewm(span=50, adjust=False).mean()

    prev_close = d["close"].shift(1)
    tr = pd.concat([
        d["high"] - d["low"],
        (d["high"] - prev_close).abs(),
        (d["low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14, min_periods=5).mean()
    return d


def _lado_macro_v92(direcao: str) -> str:
    u = str(direcao).upper()
    if "COMPRA" in u:
        return "BUY"
    if "VENDA" in u:
        return "SELL"
    return "WAIT"


def _analise_h4_v92(df: pd.DataFrame, lado: str) -> dict:
    d = _indicadores_tecnicos_v92(df)
    if len(d) < 60 or lado not in ("BUY", "SELL"):
        return {"status": "⚪ INDISPONÍVEL", "score": 0, "texto": "Dados insuficientes."}

    x = d.iloc[-1]
    slope = float(d["ema20"].iloc[-1] - d["ema20"].iloc[-6])
    if lado == "BUY":
        checks = [
            x["ema20"] > x["ema50"],
            slope > 0,
            x["close"] > x["ema20"],
        ]
    else:
        checks = [
            x["ema20"] < x["ema50"],
            slope < 0,
            x["close"] < x["ema20"],
        ]
    n = int(sum(bool(v) for v in checks))
    if n == 3:
        return {"status": "🟢 CONFIRMA", "score": 100, "texto": "Tendência/estrutura H4 alinhada ao macro."}
    if n == 2:
        return {"status": "🟡 PARCIAL", "score": 65, "texto": "H4 parcialmente alinhado; exigir confirmação."}
    return {"status": "🔴 CONTRA", "score": 20, "texto": "H4 não confirma a direção macro."}


def _analise_h1_v92(df: pd.DataFrame, lado: str) -> dict:
    d = _indicadores_tecnicos_v92(df)
    if len(d) < 60 or lado not in ("BUY", "SELL"):
        return {"status": "⚪ INDISPONÍVEL", "score": 0, "texto": "Dados insuficientes."}

    x = d.iloc[-1]
    atr = float(x["atr14"]) if pd.notna(x["atr14"]) and x["atr14"] > 0 else max(float(x["close"]) * 0.001, 1e-8)
    recent = d.tail(8)
    dist = abs(float(x["close"] - x["ema20"])) / atr

    if lado == "BUY":
        trend = bool(x["ema20"] > x["ema50"] and x["close"] > x["ema50"])
        touch = bool((recent["low"] <= recent["ema20"] + 0.25 * recent["atr14"].fillna(atr)).any())
        recovered = bool(x["close"] > x["ema20"])
    else:
        trend = bool(x["ema20"] < x["ema50"] and x["close"] < x["ema50"])
        touch = bool((recent["high"] >= recent["ema20"] - 0.25 * recent["atr14"].fillna(atr)).any())
        recovered = bool(x["close"] < x["ema20"])

    if trend and touch and recovered:
        return {"status": "🟢 PULLBACK OK", "score": 100, "texto": "H1 alinhado e com retorno/reação perto da EMA20."}
    if trend and dist > 1.20:
        return {"status": "🟡 ESTICADO", "score": 55, "texto": "H1 segue alinhado, mas o preço está distante da média; esperar pullback."}
    if trend:
        return {"status": "🟡 ALINHADO", "score": 70, "texto": "H1 favorece o macro, porém o pullback ainda não está confirmado."}
    return {"status": "🔴 CONTRA", "score": 20, "texto": "H1 não confirma a direção macro."}


def _analise_m15_v92(df: pd.DataFrame, lado: str) -> dict:
    d = _indicadores_tecnicos_v92(df)
    if len(d) < 30 or lado not in ("BUY", "SELL"):
        return {"status": "⚪ INDISPONÍVEL", "score": 0, "texto": "Dados insuficientes."}

    x = d.iloc[-1]
    prev_high = float(d["high"].shift(1).rolling(3).max().iloc[-1])
    prev_low = float(d["low"].shift(1).rolling(3).min().iloc[-1])

    if lado == "BUY":
        momentum = bool(x["ema9"] > x["ema21"] and x["close"] > x["ema9"])
        bos = bool(x["close"] > prev_high)
    else:
        momentum = bool(x["ema9"] < x["ema21"] and x["close"] < x["ema9"])
        bos = bool(x["close"] < prev_low)

    if momentum and bos:
        return {"status": "🟢 GATILHO", "score": 100, "texto": "Momentum + rompimento curto no M15 confirmam o lado macro."}
    if momentum:
        return {"status": "🟡 AGUARDAR GATILHO", "score": 65, "texto": "Momentum está alinhado, mas falta rompimento/confirmacão curta."}
    return {"status": "🔴 SEM GATILHO", "score": 25, "texto": "M15 ainda não confirma a execução."}


def _pacote_tecnico_v92(par: str, direcao: str) -> dict:
    """
    V9.3.6.4:
    - separa disponibilidade de dados de alinhamento macro/técnico;
    - se o macro estiver AGUARDAR, candles válidos NÃO viram 'dados insuficientes';
    - preserva diagnóstico seguro da Twelve Data.
    """
    lado=_lado_macro_v92(direcao)
    if not CHAVE_TWELVE_DATA:
        motivo="CHAVE_TWELVE_DATA não configurada."
        base={"status":"⚪ INDISPONÍVEL","score":0,"texto":motivo,"motivo":motivo}
        return {"disponivel":False,"dados_disponiveis":False,"motivo":motivo,"erro":motivo,
                "diagnostico":motivo,"h4":dict(base),"h1":dict(base),"m15":dict(base)}

    h4=_td_time_series_v92(par,"4h",100)
    h1=_td_time_series_v92(par,"1h",100)
    m15=_td_time_series_v92(par,"15min",100)
    dfs={"H4":h4,"H1":h1,"M15":m15}
    diags={tf:dict(df.attrs.get("td_diag",{}) or {}) for tf,df in dfs.items()}
    erros={tf:str(df.attrs.get("erro_td","") or "Resposta sem candles.")
           for tf,df in dfs.items() if df.empty}

    # Falha REAL de dados/API.
    if erros:
        def bloco_erro(tf):
            err=erros.get(tf,"")
            if err:
                return {"status":"⚪ INDISPONÍVEL","score":0,"texto":err,"motivo":err,
                        "erro":err,"td_diag":diags.get(tf,{})}
            return {"status":"⚪ NÃO AVALIADO","score":0,
                    "texto":"Outro timeframe falhou; pacote não concluído.",
                    "motivo":"","erro":"","td_diag":diags.get(tf,{})}
        motivo=" | ".join(f"{tf}: {err}" for tf,err in erros.items())
        return {"disponivel":False,"dados_disponiveis":False,"motivo":motivo,"erro":motivo,
                "diagnostico":motivo,"h4":bloco_erro("H4"),"h1":bloco_erro("H1"),
                "m15":bloco_erro("M15")}

    # Candles existem, mas a Matriz não escolheu BUY/SELL.
    # Isso é estado macro neutro/aguardar — NÃO indisponibilidade técnica.
    if lado == "WAIT":
        def bloco_wait(tf, texto):
            return {"status":"⚪ MACRO AGUARDAR","score":50,"texto":texto,
                    "motivo":"Dados disponíveis; direção macro ainda não definida.",
                    "td_diag":diags.get(tf,{})}
        ultima=max(h4["datetime"].iloc[-1],h1["datetime"].iloc[-1],m15["datetime"].iloc[-1])
        return {
            "disponivel":True,
            "dados_disponiveis":True,
            "macro_definido":False,
            "motivo":"Candles válidos. A Matriz está em AGUARDAR CONFIRMAÇÃO; não existe lado BUY/SELL para comparar a técnica.",
            "erro":"",
            "diagnostico":"Dados técnicos completos; aguardando definição do viés macro.",
            "h4":bloco_wait("H4","H4 disponível; aguardando direção macro."),
            "h1":bloco_wait("H1","H1 disponível; aguardando direção macro."),
            "m15":bloco_wait("M15","M15 disponível; aguardando direção macro."),
            "ultima_atualizacao":ultima,
            "preco_m15":float(m15["close"].iloc[-1]),
        }

    # BUY/SELL definido: análise normal.
    a4=_analise_h4_v92(h4,lado); a4["td_diag"]=diags["H4"]
    a1=_analise_h1_v92(h1,lado); a1["td_diag"]=diags["H1"]
    a15=_analise_m15_v92(m15,lado); a15["td_diag"]=diags["M15"]
    ultima=max(h4["datetime"].iloc[-1],h1["datetime"].iloc[-1],m15["datetime"].iloc[-1])
    return {"disponivel":True,"dados_disponiveis":True,"macro_definido":True,
            "motivo":"","erro":"","diagnostico":"",
            "h4":a4,"h1":a1,"m15":a15,"ultima_atualizacao":ultima,
            "preco_m15":float(m15["close"].iloc[-1])}

def _decisao_tecnica_final_v92(tecnico: dict, timing: str, direcao: str) -> tuple[str, str]:
    if not tecnico.get("disponivel", False):
        return "⚪ TÉCNICA INDISPONÍVEL", tecnico.get("motivo", "Sem dados técnicos.")

    h4 = tecnico["h4"]["status"]
    h1 = tecnico["h1"]["status"]
    m15 = tecnico["m15"]["status"]

    if h4.startswith("🔴") or h1.startswith("🔴"):
        return "🔴 EVITAR ENTRADA AGORA", "H4/H1 não confirmam o viés macro."
    if str(timing).startswith("🔴"):
        return "🔴 AGUARDAR EVENTO", "O calendário bloqueia uma entrada agressiva."
    if "ESTICADO" in h1:
        return "🟡 ESPERAR PULLBACK", "Macro e tendência podem estar alinhados, mas o H1 está esticado."
    if h4.startswith("🟢") and h1.startswith("🟢") and m15.startswith("🟢"):
        if str(timing).startswith("🟡"):
            return "🟡 TÉCNICA CONFIRMADA, EVENTO PRÓXIMO", f"{direcao} tecnicamente alinhada, mas com risco de calendário."
        return "🟢 CENÁRIO COMPLETO CONFIRMADO", f"{direcao} com H4 + H1 + M15 alinhados."
    if h4.startswith(("🟢", "🟡")) and h1.startswith(("🟢", "🟡")) and "AGUARDAR GATILHO" in m15:
        return "🟡 AGUARDAR GATILHO M15", "Direção e contexto estão alinhados; falta o gatilho curto."
    return "🟡 AGUARDAR CONFIRMAÇÃO", "A técnica ainda não está totalmente alinhada."




# =========================================================
# V9.3.8 — VALIDAÇÃO AUTOMÁTICA 1H / 4H / 24H
# Macro + H4 + H1 + M15 alinhados.
# Anti-duplicação: par + direção + candle M15.
# Base pronta para validação futura em 1h / 4h / 24h.
# =========================================================
_CONFIG_GH_PATH_V937 = "dados/configuracoes_completas_v937.csv"

def _config_cols_v937():
    return [
        "id_config", "registrado_em", "par", "direcao", "score_mestre",
        "qualidade", "indice_operacional", "h4", "h1", "m15",
        "candle_m15", "preco_entrada", "fonte_preco", "versao",
        "status_validacao",
        "preco_1h", "retorno_1h_pct", "acertou_1h",
        "preco_4h", "retorno_4h_pct", "acertou_4h",
        "preco_24h", "retorno_24h_pct", "acertou_24h",
    ]

def _config_ler_v937():
    token, repo, branch = _gh_cfg_v934()
    cols = _config_cols_v937()
    if not token or not repo:
        return pd.DataFrame(columns=cols), "GitHub persistente não configurado."
    url = f"https://api.github.com/repos/{repo}/contents/{_CONFIG_GH_PATH_V937}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        r = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
        if r.status_code == 404:
            return pd.DataFrame(columns=cols), ""
        r.raise_for_status()
        import io
        raw = base64.b64decode(r.json()["content"])
        df = pd.read_csv(io.BytesIO(raw))
        for c in cols:
            if c not in df.columns:
                df[c] = None

        # Pandas 2.x pode inferir as colunas "acertou_*" como float64
        # quando o CSV ainda contém apenas valores vazios/NaN. Depois, ao
        # gravar True/False, isso gera TypeError. Mantemos essas colunas como
        # object para aceitar bool + valores vazios sem conflito de dtype.
        for c in ("acertou_1h", "acertou_4h", "acertou_24h"):
            if c in df.columns:
                df[c] = df[c].astype("object")

        return df[cols], ""
    except Exception as e:
        return pd.DataFrame(columns=cols), f"{type(e).__name__}: {e}"

def _config_salvar_v937(df):
    token, repo, branch = _gh_cfg_v934()
    if not token or not repo:
        return False, "GitHub persistente não configurado."
    url = f"https://api.github.com/repos/{repo}/contents/{_CONFIG_GH_PATH_V937}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        atual = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
        sha = atual.json().get("sha", "") if atual.status_code == 200 else ""
        if atual.status_code not in (200, 404):
            atual.raise_for_status()
        payload = {
            "message": "V9.3.7: registra configuração completa",
            "content": base64.b64encode(df.to_csv(index=False).encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload, timeout=25)
        r.raise_for_status()
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def _registrar_config_completa_v937(
    par, direcao, score, qualidade, indice, h4, h1, m15,
    candle_m15="", preco_entrada=None
):
    par, direcao = str(par), str(direcao)
    candle = str(candle_m15 or "")
    chave = f"{par}|{direcao}|{candle}"
    df, erro = _config_ler_v937()
    if erro and df.empty:
        return False, erro, False
    if not df.empty:
        chaves = (
            df["par"].astype(str) + "|" +
            df["direcao"].astype(str) + "|" +
            df["candle_m15"].fillna("").astype(str)
        )
        if chave in set(chaves):
            return True, "Configuração já registrada para este candle M15.", False

    novo = {c: None for c in _config_cols_v937()}
    novo.update({
        "id_config": f"{par.replace('/','')}_{pd.Timestamp.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}",
        "registrado_em": pd.Timestamp.utcnow().isoformat(),
        "par": par,
        "direcao": direcao,
        "score_mestre": float(score),
        "qualidade": str(qualidade),
        "indice_operacional": float(indice),
        "h4": str(h4), "h1": str(h1), "m15": str(m15),
        "candle_m15": candle,
        "preco_entrada": float(preco_entrada) if preco_entrada is not None else None,
        "fonte_preco": "Twelve Data M15",
        "versao": "V9.3.7",
        "status_validacao": "PENDENTE",
    })
    df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
    ok, msg = _config_salvar_v937(df)
    return ok, msg or ("Configuração registrada." if ok else "Falha ao registrar."), bool(ok)


def _retorno_direcional_v938(direcao, entrada, saida):
    entrada, saida = float(entrada), float(saida)
    if entrada == 0:
        return None
    bruto = (saida / entrada - 1.0) * 100.0
    return -bruto if "VENDA" in str(direcao).upper() else bruto

def _td_preco_historico_v938(par, alvo_utc):
    df,err=cached_series(par,"15min",500,history=True)
    if err or df.empty: return None,None,err or "Histórico fora do cache; aguarde coleta."
    try:
        target=pd.to_datetime(alvo_utc,utc=True)
        eligible=df[(df["datetime"]>=target)&(df["datetime"]<target+pd.Timedelta(minutes=15))]
        if eligible.empty: return None,None,"Horizonte sem candle no cache; permanece pendente."
        row=eligible.iloc[0]
        return float(row["close"]),row["datetime"].isoformat(),""
    except Exception:
        return None,None,"Horário histórico inválido."

def _validar_configuracoes_v938():
    """
    Preenche 1h/4h/24h somente quando cada horizonte já venceu.
    Usa o primeiro fechamento M15 disponível em/apos o horário-alvo.
    """
    df, erro = _config_ler_v937()
    if erro and df.empty:
        return df, False, erro
    if df.empty:
        return df, False, ""

    agora = pd.Timestamp.now(tz="UTC")
    mudou = False
    horizontes = [(1, "1h"), (4, "4h"), (24, "24h")]

    for i, row in df.iterrows():
        try:
            entrada = float(row.get("preco_entrada"))
            base_txt = row.get("candle_m15") or row.get("registrado_em")
            base = pd.to_datetime(base_txt, utc=True)
            direcao = str(row.get("direcao", ""))
            par = str(row.get("par", ""))
        except Exception:
            continue

        for horas, suf in horizontes:
            col_preco = f"preco_{suf}"
            col_ret = f"retorno_{suf}_pct"
            col_hit = f"acertou_{suf}"
            ja = row.get(col_preco)
            if pd.notna(ja) and str(ja).strip() not in ("", "None", "nan"):
                continue

            alvo = base + pd.Timedelta(hours=horas)
            if agora < alvo:
                continue

            preco, dt_saida, err = _td_preco_historico_v938(par, alvo)
            if preco is None:
                continue

            ret = _retorno_direcional_v938(direcao, entrada, preco)
            df.at[i, col_preco] = float(preco)
            df.at[i, col_ret] = float(ret) if ret is not None else None
            df.at[i, col_hit] = bool(ret > 0) if ret is not None else None
            # Colunas auxiliares são adicionadas sem quebrar arquivos antigos.
            col_dt = f"data_{suf}"
            if col_dt not in df.columns:
                df[col_dt] = None
            df.at[i, col_dt] = dt_saida
            mudou = True

        feitos = []
        for _, suf in horizontes:
            v = df.at[i, f"preco_{suf}"] if f"preco_{suf}" in df.columns else None
            if pd.notna(v) and str(v).strip() not in ("", "None", "nan"):
                feitos.append(suf)
        if len(feitos) == 3:
            df.at[i, "status_validacao"] = "VALIDADO 1H/4H/24H"
        elif feitos:
            df.at[i, "status_validacao"] = "PARCIAL " + "/".join(x.upper() for x in feitos)
        else:
            df.at[i, "status_validacao"] = "PENDENTE"

    if mudou:
        ok, msg = _config_salvar_v937(df)
        if not ok:
            return df, False, msg
    return df, mudou, ""

def _fmt_resultado_v938(ret, hit):
    if pd.isna(ret):
        return "⏳ PENDENTE"
    try:
        return f"{'✅' if bool(hit) else '❌'} {float(ret):+.3f}%"
    except Exception:
        return "—"



def _faixa_score_v939(v):
    try:
        x = float(v)
    except Exception:
        return "Sem score"
    if x >= 90:
        return "90+"
    if x >= 80:
        return "80–89"
    if x >= 70:
        return "70–79"
    return "<70"

def _faixa_qualidade_v939(v):
    try:
        s = str(v).replace("%", "").replace(",", ".").strip()
        x = float(s)
    except Exception:
        return "Sem qualidade"
    if x >= 75:
        return "75%+"
    if x >= 60:
        return "60–74%"
    return "<60%"

def _estat_horizonte_v939(df, suf):
    ret = pd.to_numeric(df.get(f"retorno_{suf}_pct"), errors="coerce")
    mask = ret.notna()
    n = int(mask.sum())
    if n == 0:
        return {"n": 0, "acertos": 0, "taxa": None, "ret_medio": None}
    acertos = int((ret[mask] > 0).sum())
    return {
        "n": n,
        "acertos": acertos,
        "taxa": 100.0 * acertos / n,
        "ret_medio": float(ret[mask].mean()),
    }

def _tabela_grupo_v939(df, coluna, suf):
    retcol = f"retorno_{suf}_pct"
    tmp = df.copy()
    tmp[retcol] = pd.to_numeric(tmp.get(retcol), errors="coerce")
    tmp = tmp[tmp[retcol].notna()].copy()
    if tmp.empty:
        return pd.DataFrame()
    linhas = []
    for grupo, g in tmp.groupby(coluna, dropna=False):
        n = len(g)
        acertos = int((g[retcol] > 0).sum())
        linhas.append({
            coluna: grupo,
            "Amostra": n,
            "Acertos": acertos,
            "Taxa de acerto": f"{100.0 * acertos / n:.1f}%",
            "Retorno direcional médio": f"{g[retcol].mean():+.3f}%",
        })
    return pd.DataFrame(linhas)

def _painel_performance_v939(df):
    st.markdown("### 📈 Painel de Performance Real — V9.3.9")
    st.caption(
        "Este painel usa somente configurações realmente registradas e os resultados "
        "1H/4H/24H já disponíveis. O Score Mestre e o índice operacional não são "
        "probabilidades de lucro."
    )

    if df is None or df.empty:
        st.info("Ainda não há configurações registradas para medir performance.")
        return

    stats = {s: _estat_horizonte_v939(df, s) for s in ("1h", "4h", "24h")}
    total_avaliacoes = sum(v["n"] for v in stats.values())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Configurações registradas", len(df))
    c2.metric("Avaliações disponíveis", total_avaliacoes)
    c3.metric("Com 24H concluído", stats["24h"]["n"])
    completos = 0
    if "status_validacao" in df.columns:
        completos = int(
            (df["status_validacao"].astype(str) == "VALIDADO 1H/4H/24H").sum()
        )
    c4.metric("Totalmente validadas", completos)

    st.markdown("#### 🎯 Resultado por horizonte")
    cols = st.columns(3)
    for j, suf in enumerate(("1h", "4h", "24h")):
        s = stats[suf]
        if s["n"]:
            cols[j].metric(
                f"{suf.upper()} · taxa de acerto",
                f'{s["taxa"]:.1f}%',
                f'{s["n"]} avaliação(ões)'
            )
            cols[j].caption(
                f'Retorno direcional médio: {s["ret_medio"]:+.3f}%'
            )
        else:
            cols[j].metric(f"{suf.upper()} · taxa de acerto", "—")
            cols[j].caption("Aguardando amostra.")

    if total_avaliacoes == 0:
        st.warning(
            "Ainda não existe resultado vencido para calcular performance. "
            "O painel começará a preencher automaticamente quando 1H, 4H e 24H forem validados."
        )
        return

    horizonte = st.selectbox(
        "Horizonte para análise detalhada",
        ["1H", "4H", "24H"],
        key="v939_horizonte_performance"
    )
    suf = horizonte.lower()

    base = df.copy()
    base["Faixa Score"] = base["score_mestre"].apply(_faixa_score_v939)
    base["Faixa Qualidade"] = base["qualidade"].apply(_faixa_qualidade_v939)

    st.markdown(f"#### 💱 Performance por par — {horizonte}")
    tab_par = _tabela_grupo_v939(base, "par", suf)
    if tab_par.empty:
        st.info(f"Ainda não há avaliações {horizonte}.")
    else:
        st.dataframe(tab_par, width="stretch", hide_index=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"#### 🧠 Por Score Mestre — {horizonte}")
        tab_score = _tabela_grupo_v939(base, "Faixa Score", suf)
        if not tab_score.empty:
            st.dataframe(tab_score, width="stretch", hide_index=True)
        else:
            st.info("Sem amostra.")

    with col_b:
        st.markdown(f"#### 🛡️ Por qualidade — {horizonte}")
        tab_q = _tabela_grupo_v939(base, "Faixa Qualidade", suf)
        if not tab_q.empty:
            st.dataframe(tab_q, width="stretch", hide_index=True)
        else:
            st.info("Sem amostra.")

    # Evolução acumulada simples do retorno direcional.
    retcol = f"retorno_{suf}_pct"
    evo = base.copy()
    evo[retcol] = pd.to_numeric(evo.get(retcol), errors="coerce")
    evo = evo[evo[retcol].notna()].copy()
    if not evo.empty:
        evo["registrado_em_dt"] = pd.to_datetime(
            evo["registrado_em"], errors="coerce", utc=True
        )
        evo = evo.sort_values("registrado_em_dt")
        evo["Retorno direcional acumulado (%)"] = evo[retcol].cumsum()
        st.markdown(f"#### 📊 Evolução acumulada — {horizonte}")
        st.line_chart(
            evo.set_index("registrado_em_dt")[["Retorno direcional acumulado (%)"]]
        )

    menor_n = min([v["n"] for v in stats.values() if v["n"] > 0], default=0)
    if menor_n < 30:
        st.warning(
            "⚠️ AMOSTRA PEQUENA: estes números ainda não validam o modelo. "
            "Não altere pesos ou regras com base em poucos sinais. "
            "Primeiro acumule dezenas de configurações independentes."
        )
    else:
        st.info(
            "A amostra já começou a ficar mais útil, mas ainda deve ser analisada "
            "junto com período de mercado, eventos macro e estabilidade ao longo do tempo."
        )


def _painel_configuracoes_v937():
    st.markdown("#### 🧪 Validação automática das configurações — V9.3.8")
    df, mudou, erro = _validar_configuracoes_v938()
    if erro and df.empty:
        st.info(f"Histórico ainda indisponível: {erro}")
        return
    if df.empty:
        st.info("Ainda não há configuração completa registrada.")
        return

    if mudou:
        st.success("🔄 V9.3.8 atualizou automaticamente os horizontes que já estavam disponíveis.")

    total = len(df)
    completos = int((df["status_validacao"].astype(str) == "VALIDADO 1H/4H/24H").sum())
    pend = total - completos
    c1, c2, c3 = st.columns(3)
    c1.metric("Configurações", total)
    c2.metric("Totalmente validadas", completos)
    c3.metric("Em acompanhamento", pend)

    vis = df.copy()
    for suf in ("1h", "4h", "24h"):
        vis[f"Resultado {suf.upper()}"] = [
            _fmt_resultado_v938(r, h)
            for r, h in zip(vis[f"retorno_{suf}_pct"], vis[f"acertou_{suf}"])
        ]

    cols_show = [
        "registrado_em", "par", "direcao", "score_mestre", "qualidade",
        "indice_operacional", "preco_entrada",
        "Resultado 1H", "Resultado 4H", "Resultado 24H", "status_validacao"
    ]
    st.dataframe(vis[cols_show].tail(30).iloc[::-1], width="stretch", hide_index=True)

    avaliados = {}
    for suf in ("1h", "4h", "24h"):
        mask = pd.to_numeric(df[f"retorno_{suf}_pct"], errors="coerce").notna()
        n = int(mask.sum())
        if n:
            hits = df.loc[mask, f"acertou_{suf}"].astype(str).str.lower().isin(["true", "1"]).sum()
            avaliados[suf] = (n, 100.0 * hits / n)

    if avaliados:
        st.markdown("##### 📊 Desempenho observado")
        cols = st.columns(3)
        for j, suf in enumerate(("1h", "4h", "24h")):
            if suf in avaliados:
                n, taxa = avaliados[suf]
                cols[j].metric(f"Acerto {suf.upper()}", f"{taxa:.1f}%", f"{n} sinal(is)")
            else:
                cols[j].metric(f"Acerto {suf.upper()}", "—", "sem amostra")

    st.caption(
        "Retorno direcional: COMPRA é positiva quando o preço sobe; VENDA é positiva quando o preço cai. "
        "A avaliação usa o primeiro fechamento M15 disponível em/apos 1h, 4h e 24h do candle de entrada. "
        "Amostras pequenas não validam o modelo."
    )

    st.divider()
    _painel_performance_v939(df)


# =========================================================
# V9.3.4 — PERSISTÊNCIA DO SCANNER NO GITHUB
# Arquivo: dados/scanner_tecnico_v934.json
# Não salva API keys; apenas resultados técnicos/estado da fila.
# =========================================================
import base64
import json

_SCANNER_GH_PATH_V934 = "dados/scanner_tecnico_v934.json"

def _gh_cfg_v934():
    token = st.secrets.get("GITHUB_TOKEN_HISTORICO", os.getenv("GITHUB_TOKEN_HISTORICO", ""))
    repo = st.secrets.get("GITHUB_REPO_HISTORICO", os.getenv("GITHUB_REPO_HISTORICO", ""))
    branch = resolve_runtime_branch(
        st.secrets.get("GITHUB_DATA_BRANCH", os.getenv("GITHUB_DATA_BRANCH", "")),
        st.secrets.get("GITHUB_BRANCH_HISTORICO", os.getenv("GITHUB_BRANCH_HISTORICO", "")),
    )
    return str(token), str(repo), str(branch)

def _scanner_load_v934():
    token, repo, branch = _gh_cfg_v934()
    vazio = {"versao": "V9.3.5", "lote": 0, "ultimo_processamento_ts": 0.0, "resultados": {}}
    if not token or not repo:
        vazio["_erro"] = "Persistência GitHub não configurada."
        return vazio
    url = f"https://api.github.com/repos/{repo}/contents/{_SCANNER_GH_PATH_V934}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        r = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
        if r.status_code == 404:
            return vazio
        r.raise_for_status()
        j = r.json()
        raw = base64.b64decode(j["content"]).decode("utf-8")
        data = json.loads(raw)
        data["_sha"] = j.get("sha", "")
        return data
    except Exception as e:
        vazio["_erro"] = f"{type(e).__name__}: {e}"
        return vazio

def _scanner_save_v934(data):
    return False, "Scanner gerenciado pelo Autopilot. Releia o cache; novas coletas e gravações ocorrem no workflow Autopilot."

def _tec_to_json_v934(tec):
    """Converte somente o resumo técnico necessário; DataFrames nunca são persistidos."""
    return {
        "disponivel": bool(tec.get("disponivel", False)),
        "motivo": str(tec.get("motivo", "")),
        "h4": dict(tec.get("h4", {})),
        "h1": dict(tec.get("h1", {})),
        "m15": dict(tec.get("m15", {})),
        "preco_m15": float(tec.get("preco_m15", 0.0) or 0.0),
        "ultima_atualizacao": str(tec.get("ultima_atualizacao", "")),
        "erro": str(tec.get("erro", "")),
        "diagnostico": str(tec.get("diagnostico", "")),
    }


# =========================================================
# V9.1 — CENTRAL DE DECISÃO AUTOMÁTICA
# Consolida os dados já calculados pelo APP.
# NÃO cria sinal técnico H4/H1/M15 porque esses candles
# ainda não são alimentados automaticamente pelo sistema.
# =========================================================
with abas[8]:
    st.subheader("🎯 Central de Decisão Automática — V9.3.5")
    st.caption(
        "Resumo automático dos dados que já existem no APP. "
        "O resultado abaixo é um viés macro/operacional educacional, não uma ordem de mercado."
    )

    if "matriz_v61" not in globals() or matriz_v61 is None or matriz_v61.empty:
        st.warning("A Matriz ainda não está disponível nesta execução.")
    else:
        # -----------------------------
        # Melhor par atual da matriz
        # -----------------------------
        _top91 = matriz_v61.iloc[0]
        _par91 = str(_top91["Par"])
        _dir91 = str(_top91["Direção"])
        _score91 = float(_top91["Score final"])
        _qual91 = float(_top91["Qualidade"])
        _conf91 = str(_top91["Confluência"])
        _dif91 = float(_top91["Dif. macro"])
        _base91, _cot91 = _par91.split("/")

        # Scores individuais das moedas
        _sb91 = usd_ajustado if _base91 == "USD" else float(scores_ranking.get(_base91, 50.0))
        _sc91 = usd_ajustado if _cot91 == "USD" else float(scores_ranking.get(_cot91, 50.0))

        # Evento e timing
        _evt91 = _proximo_evento_macro_v65()
        _evt_nome91, _dias91, _impacto91 = "Nenhum evento crítico identificado", None, "—"
        if isinstance(_evt91, dict) and _evt91.get("disponivel", False):
            _evt_nome91 = str(_evt91.get("evento", "—"))
            _dias91 = _evt91.get("dias")
            _impacto91 = str(_evt91.get("impacto", "—"))

        _alto91 = str(_impacto91).upper() in ("MÁXIMO", "MAXIMO", "ALTO")
        if _dias91 is not None and _dias91 <= 2 and _alto91:
            _timing91 = "🔴 AGUARDAR"
            _timing_text91 = "Evento de alto impacto muito próximo."
        elif _dias91 is not None and _dias91 <= 7 and _alto91:
            _timing91 = "🟡 ATENÇÃO"
            _timing_text91 = "Evento de alto impacto próximo; reduzir agressividade e exigir confirmação."
        else:
            _timing91 = "🟢 NORMAL"
            _timing_text91 = "Sem bloqueio forte do calendário neste momento."

        # Recalcula Raio-X para o melhor par usando o mesmo motor da matriz
        _conf_obj91 = calcular_confluencia_v60(
            _base91, _cot91, _dif91, usd_ajustado, ajuste,
            fed.get("tom", "Neutro"), ranking
        )

        _fav91, _neu91, _contra91 = 0, 0, 0
        _xrows91 = []
        for _nome91, _estado91, _peso91, _fator91, _peff91 in _conf_obj91.get("linhas_dinamicas", []):
            if _estado91 > 0:
                _leit91 = "🟢 A favor"
                _fav91 += 1
            elif _estado91 < 0:
                _leit91 = "🔴 Contra"
                _contra91 += 1
            else:
                _leit91 = "⚪ Neutro"
                _neu91 += 1
            _xrows91.append({
                "Componente": _nome91,
                "Leitura": _leit91,
                "Qualidade": f"{_fator91*100:.0f}%",
                "Peso efetivo": f"{_peff91:.1f}%"
            })

        # -----------------------------
        # Resultado automático
        # -----------------------------
        _tem_direcao91 = ("COMPRA" in _dir91.upper()) or ("VENDA" in _dir91.upper())
        if not _tem_direcao91:
            _resultado91 = "⚪ SEM OPERAÇÃO MACRO CLARA"
            _acao91 = "Aguardar melhora da confluência."
        elif _timing91.startswith("🔴"):
            _resultado91 = "🔴 AGUARDAR"
            _acao91 = (
                f"O viés continua {_dir91}, mas o calendário bloqueia uma entrada agressiva agora."
            )
        elif _score91 >= 85 and _qual91 >= 75 and _contra91 == 0:
            if _timing91.startswith("🟡"):
                _resultado91 = "🟡 VIÉS FORTE, MAS COM RISCO DE EVENTO"
                _acao91 = (
                    f"Prioridade macro: {_dir91}. "
                    "Esperar confirmação no H4/H1 e gatilho no M15 antes de considerar execução."
                )
            else:
                _resultado91 = "🟢 CENÁRIO MACRO FORTE"
                _acao91 = (
                    f"Prioridade macro: {_dir91}. "
                    "Confirmar estrutura H4/H1 e usar M15 apenas para o gatilho."
                )
        elif _score91 >= 70 and _qual91 >= 60:
            _resultado91 = "🟡 CENÁRIO MODERADO"
            _acao91 = (
                f"Viés: {_dir91}. Exigir confirmação técnica mais forte antes de considerar entrada."
            )
        else:
            _resultado91 = "⚪ AGUARDAR MELHOR CENÁRIO"
            _acao91 = "Confluência/qualidade insuficientes para priorizar o par."

        # -----------------------------
        # Cartão principal
        # -----------------------------
        st.markdown("### 🧭 Resultado automático")
        _c1, _c2, _c3, _c4 = st.columns(4)
        _c1.metric("Melhor par", _par91)
        _c2.metric("Direção macro", _dir91.replace("🟢 ","").replace("🔴 ",""))
        _c3.metric("Score Mestre", f"{_score91:.0f}/100")
        _c4.metric("Qualidade", f"{_qual91:.0f}%")

        if _resultado91.startswith("🟢"):
            st.success(f"**{_resultado91}** — {_acao91}")
        elif _resultado91.startswith("🔴"):
            st.error(f"**{_resultado91}** — {_acao91}")
        elif _resultado91.startswith("🟡"):
            st.warning(f"**{_resultado91}** — {_acao91}")
        else:
            st.info(f"**{_resultado91}** — {_acao91}")

        # -----------------------------
        # 1. Força das moedas
        # -----------------------------
        st.markdown("### 1️⃣ Força relativa")
        _f1, _f2, _f3 = st.columns(3)
        _f1.metric(_base91, f"{_sb91:.1f}/100")
        _f2.metric(_cot91, f"{_sc91:.1f}/100")
        _f3.metric("Diferença macro", f"{_dif91:+.1f}")
        st.caption(
            f"O melhor par atual coloca {_base91} contra {_cot91}. "
            f"A diferença de força é {_dif91:+.1f} pontos."
        )

        # -----------------------------
        # 2. Macro USD
        # -----------------------------
        st.markdown("### 2️⃣ Macro dos Estados Unidos")
        _u1, _u2, _u3 = st.columns(3)
        _u1.metric("Score macro USD", f"{usd_detalhado['score']:.0f}/100")
        _u2.metric("Qualidade macro USD", f"{qualidade_usd}%")
        _u3.metric(
            "Fed narrativo",
            str(fed.get("tom", "Neutro"))
        )

        _macro_show91 = pd.DataFrame([
            {"Indicador": "Fed Funds", "Valor": f"{macro_eua['Juros do Fed']:.2f}%"},
            {"Indicador": "CPI/IPC anual", "Valor": f"{macro_eua['IPC anual']:.2f}%"},
            {"Indicador": "Core CPI", "Valor": f"{macro_eua['IPC Núcleo anual']:.2f}%"},
            {"Indicador": "PCE anual", "Valor": f"{macro_eua['PCE anual']:.2f}%"},
            {"Indicador": "Core PCE", "Valor": f"{macro_eua['PCE Núcleo anual']:.2f}%"},
            {"Indicador": "Desemprego", "Valor": f"{macro_eua['Desemprego']:.2f}%"},
            {"Indicador": "Payroll", "Valor": f"{macro_eua['Payroll variação mensal (mil)']:.0f} mil"},
            {"Indicador": "PIB real", "Valor": f"{macro_eua['PIB']:.2f}%"},
            {"Indicador": "Treasury 2Y", "Valor": f"{macro_eua['Treasury 2 anos']:.2f}%"},
            {"Indicador": "Treasury 10Y", "Valor": f"{macro_eua['Treasury 10 anos']:.2f}%"},
            {"Indicador": "Índice amplo USD", "Valor": f"{macro_eua['Índice amplo do dólar']:.1f}"},
        ])
        st.dataframe(_macro_show91, width="stretch", hide_index=True)

        # -----------------------------
        # 3. Calendário
        # -----------------------------
        st.markdown("### 3️⃣ Calendário / risco")
        _e1, _e2, _e3 = st.columns(3)
        _e1.metric("Próximo evento", _evt_nome91)
        _e2.metric("Dias", "—" if _dias91 is None else str(_dias91))
        _e3.metric("Timing", _timing91)
        st.caption(f"Impacto: {_impacto91}. {_timing_text91}")

        # -----------------------------
        # 4. Raio-X consolidado
        # -----------------------------
        st.markdown("### 4️⃣ Raio-X do melhor sinal")
        _r1, _r2, _r3 = st.columns(3)
        _r1.metric("A favor", _fav91)
        _r2.metric("Neutros", _neu91)
        _r3.metric("Contra", _contra91)
        if _xrows91:
            st.dataframe(pd.DataFrame(_xrows91), width="stretch", hide_index=True)

        # -----------------------------
        # 5. Técnica automática V9.2
        # -----------------------------
        st.markdown("### 5️⃣ Confirmação técnica automática — V9.2")
        st.caption(
            "Fonte técnica: cache do Autopilot. H4 = direção/estrutura; "
            "H1 = alinhamento/pullback; M15 = gatilho curto. "
            "As telas reutilizam candles sem novas consultas. Dados antigos continuam bloqueados."
        )

        if st.button("🔄 Atualizar técnica agora", key="v92_refresh_tecnico"):
            try:
                _td_time_series_v92.clear()
            except Exception:
                pass
            st.rerun()

        _tec92 = _pacote_tecnico_v92(_par91, _dir91)
        _dec_tec92, _dec_tec_txt92 = _decisao_tecnica_final_v92(_tec92, _timing91, _dir91)

        if not _tec92.get("disponivel", False):
            st.warning(
                "⚠️ Técnica automática ainda não disponível. "
                + str(_tec92.get("motivo", ""))
            )
            if not CHAVE_TWELVE_DATA:
                st.info(
                    "Adicione CHAVE_TWELVE_DATA aos Secrets do Streamlit para ativar H4/H1/M15 automáticos."
                )
        else:
            _t1, _t2, _t3, _t4 = st.columns(4)
            _t1.metric("Preço técnico", f"{_tec92['preco_m15']:.5f}")
            _t2.metric("H4", _tec92["h4"]["status"])
            _t3.metric("H1", _tec92["h1"]["status"])
            _t4.metric("M15", _tec92["m15"]["status"])

            _tech92_df = pd.DataFrame([
                {
                    "Timeframe": "H4",
                    "Função": "Direção / estrutura",
                    "Status": _tec92["h4"]["status"],
                    "Leitura": _tec92["h4"]["texto"],
                },
                {
                    "Timeframe": "H1",
                    "Função": "Pullback / localização",
                    "Status": _tec92["h1"]["status"],
                    "Leitura": _tec92["h1"]["texto"],
                },
                {
                    "Timeframe": "M15",
                    "Função": "Gatilho",
                    "Status": _tec92["m15"]["status"],
                    "Leitura": _tec92["m15"]["texto"],
                },
            ])
            st.dataframe(_tech92_df, width="stretch", hide_index=True)
            st.caption(
                f"Último candle recebido: {_tec92['ultima_atualizacao'].strftime('%d/%m/%Y %H:%M UTC')}"
            )

        st.markdown("### 🚦 Semáforo Operacional")
        if _dec_tec92.startswith("🟢"):
            st.success(f"**{_dec_tec92}** — {_dec_tec_txt92}")
        elif _dec_tec92.startswith("🔴"):
            st.error(f"**{_dec_tec92}** — {_dec_tec_txt92}")
        else:
            st.warning(f"**{_dec_tec92}** — {_dec_tec_txt92}")



        # -----------------------------------------------------
        # V9.3 — Scanner técnico automático dos 7 pares
        # -----------------------------------------------------
        st.markdown("### 🌐 Scanner Automático dos 7 Pares — V9.3.6.4")
        st.caption(
            "A Matriz continua escolhendo o viés macro de cada par. "
            "O scanner consulta H4, H1 e M15 e procura qual par está mais perto "
            "de uma confirmação técnica completa."
        )

        st.caption(
            "Modo incremental: cada lote consulta SOMENTE os pares novos e salva o resultado na sessão. "
            "Lotes anteriores não são consultados novamente. Máximo de 2 pares (6 séries) por janela."
        )

        _scanner93 = []
        _mat93 = matriz_v61.copy().head(7).reset_index(drop=True)

        _tok934, _repo934, _branch934 = _gh_cfg_v934()
        if not _tok934 or not _repo934:
            st.error("❌ Persistência do scanner não configurada. Verifique os Secrets GitHub já usados pelo histórico.")
        else:
            st.success(f"💾 Fila persistente ativa: {_repo934} · {_SCANNER_GH_PATH_V934}")

        # V9.3.4: estado vem do GitHub; F5/fechar navegador não apaga progresso.
        _estado934 = _scanner_load_v934()
        _resultados934 = dict(_estado934.get("resultados", {}))

        _lotes933 = [
            list(range(i, min(i + 2, len(_mat93))))
            for i in range(0, len(_mat93), 2)
        ]
        _lote_idx933 = max(
            0,
            min(int(_estado934.get("lote", 0)), len(_lotes933) - 1)
        )

        _agora933 = time.time()
        _ultimo933 = float(_estado934.get("ultimo_processamento_ts", 0.0))
        _restante933 = max(0, int(61 - (_agora933 - _ultimo933))) if _ultimo933 else 0
        _resultados933 = _resultados934

        def _resultado_tecnico_valido_v935(r):
            tec = r.get("tecnico", {}) if isinstance(r, dict) else {}
            if not bool(tec.get("disponivel", False)):
                return False
            for tf in ("h4", "h1", "m15"):
                bloco = tec.get(tf, {})
                status = str(bloco.get("status", "")).upper()
                if (not bloco) or ("INDISPON" in status) or ("NA FILA" in status):
                    return False
            return True

        _a933, _b933, _refresh9352, _c933 = st.columns([1.25, 1.15, 1.35, 2.5])

        with _a933:
            _pode_processar933 = (_restante933 <= 0)
            if st.button(
                "▶️ Processar lote atual",
                key="v933_processar_lote",
                disabled=not _pode_processar933
            ):
                # IMPORTANTE: consulta SOMENTE os pares do lote atual.
                for _idx933 in _lotes933[_lote_idx933]:
                    _row933 = _mat93.iloc[_idx933]
                    _par933 = str(_row933["Par"])
                    _dir933 = str(_row933["Direção"])

                    # Se já existe resultado válido deste par, não gasta API novamente.
                    if _par933 in _resultados933 and _resultado_tecnico_valido_v935(_resultados933[_par933]):
                        continue

                    # V9.3.6.4: o par incompleto precisa de UMA tentativa realmente nova.
                    # Limpa somente o cache da função técnica antes desta tentativa.
                    # Os 6 pares válidos continuam preservados no JSON e não são consultados.
                    try:
                        _td_time_series_v92.clear()
                    except Exception:
                        pass

                    _tentativa_ts9355 = time.time()
                    _tec933 = _pacote_tecnico_v92(_par933, _dir933)
                    _dec933, _txt933 = _decisao_tecnica_final_v92(
                        _tec933, _timing91, _dir933
                    )

                    # Persiste SEMPRE a tentativa, inclusive quando a API falhar.
                    # Isso evita manter silenciosamente o diagnóstico antigo.
                    _resultados933[_par933] = {
                        "tecnico": _tec_to_json_v934(_tec933),
                        "decisao": _dec933,
                        "texto": _txt933,
                        "processado_em": _tentativa_ts9355,
                        "tentativa_v9355": True,
                        "versao_tentativa": "V9.3.6.4",
                    }

                _estado934["resultados"] = _resultados933
                _estado934["ultimo_processamento_ts"] = time.time()
                _ok934, _err934 = _scanner_save_v934(_estado934)
                if not _ok934:
                    st.error(f"Falha ao salvar progresso do scanner no GitHub: {_err934}")
                else:
                    st.rerun()

        with _refresh9352:
            if st.button("🔄 Verificar liberação", key="v9352_verificar_timer"):
                # Apenas rerun: não chama Twelve Data, não muda o timestamp
                # e não gasta créditos da API.
                st.rerun()

        with _b933:
            # Só permite avançar quando TODOS os pares do lote atual estão completos.
            _pares_lote933 = [
                str(_mat93.iloc[i]["Par"]) for i in _lotes933[_lote_idx933]
            ]
            _lote_completo933 = all(
                p in _resultados933 and _resultado_tecnico_valido_v935(_resultados933[p])
                for p in _pares_lote933
            )
            if st.button(
                "⏭️ Próximo lote",
                key="v933_proximo_lote",
                disabled=(
                    (not _lote_completo933) or
                    (_restante933 > 0) or
                    (_lote_idx933 >= len(_lotes933) - 1)
                )
            ):
                _estado934["lote"] = min(_lote_idx933 + 1, len(_lotes933) - 1)
                _ok934, _err934 = _scanner_save_v934(_estado934)
                if not _ok934:
                    st.error(f"Falha ao salvar avanço da fila no GitHub: {_err934}")
                else:
                    st.rerun()

        with _c933:
            _pares_txt933 = " + ".join(_pares_lote933)
            if _lote_completo933:
                if _lote_idx933 < len(_lotes933) - 1:
                    if _restante933 > 0:
                        st.caption(
                            f"Lote {_lote_idx933+1}/{len(_lotes933)} completo ({_pares_txt933}). "
                            f"Aguarde ~{_restante933}s e clique em 🔄 Verificar liberação."
                        )
                    else:
                        st.caption(
                            f"Lote {_lote_idx933+1}/{len(_lotes933)} completo ({_pares_txt933}). "
                            "Próximo lote liberado."
                        )
                else:
                    st.caption("Último lote completo.")
            else:
                st.caption(
                    f"Lote {_lote_idx933+1}/{len(_lotes933)}: {_pares_txt933}. "
                    + (
                        f"Aguarde ~{_restante933}s. Depois clique em 🔄 Verificar liberação."
                        if _restante933 > 0
                        else "Pronto para processar."
                    )
                )

        _n_salvos933 = sum(
            1 for p, r in _resultados933.items()
            if _resultado_tecnico_valido_v935(r)
        )
        st.progress(
            min(1.0, _n_salvos933 / max(1, len(_mat93))),
            text=f"Resultados técnicos persistentes: {_n_salvos933}/{len(_mat93)} pares"
        )

        # Monta a tabela SEM fazer novas chamadas.
        for _rank93, _row_idx93 in enumerate(range(len(_mat93)), start=1):
            _row93 = _mat93.iloc[_row_idx93]
            _p93 = str(_row93["Par"])
            _d93 = str(_row93["Direção"])
            _s93 = float(_row93["Score final"])
            _q93 = float(_row93["Qualidade"])
            _c93 = str(_row93["Confluência"])

            _saved933 = _resultados933.get(_p93)

            if not _saved933:
                _scanner93.append({
                    "Ranking macro": _rank93,
                    "Par": _p93,
                    "Direção": _d93.replace("🟢 ", "").replace("🔴 ", ""),
                    "Score": round(_s93),
                    "Qualidade": f"{_q93:.0f}%",
                    "Confluência": _c93,
                    "H4": "⏳ NA FILA",
                    "H1": "⏳ NA FILA",
                    "M15": "⏳ NA FILA",
                    "Semáforo": "⏳ AGUARDANDO LOTE",
                    "Índice operacional": 0.0,
                    "_disponivel": False,
                    "_texto": "Ainda não processado pela fila V9.3.3.",
                })
                continue

            _tec93 = _saved933["tecnico"]
            _dec93 = str(_saved933["decisao"])
            _txt93 = str(_saved933["texto"])
            if not _resultado_tecnico_valido_v935(_saved933):
                _mot_saved9353 = str(
                    _tec93.get("motivo", "")
                    or _tec93.get("erro", "")
                    or _tec93.get("diagnostico", "")
                ).strip()
                _txt93 = (
                    f"Resultado persistido incompleto: {_mot_saved9353}"
                    if _mot_saved9353
                    else "Resultado persistido incompleto. Consulte o diagnóstico abaixo."
                )

            _tech_score93 = (
                float(_tec93["h4"].get("score", 0)) * 0.35 +
                float(_tec93["h1"].get("score", 0)) * 0.35 +
                float(_tec93["m15"].get("score", 0)) * 0.30
            )
            _op93 = 0.40 * _s93 + 0.20 * _q93 + 0.40 * _tech_score93
            if str(_timing91).startswith("🔴"):
                _op93 -= 25
            elif str(_timing91).startswith("🟡"):
                _op93 -= 10

            _scanner93.append({
                "Ranking macro": _rank93,
                "Par": _p93,
                "Direção": _d93.replace("🟢 ", "").replace("🔴 ", ""),
                "Score": round(_s93),
                "Qualidade": f"{_q93:.0f}%",
                "Confluência": _c93,
                "H4": _tec93["h4"]["status"],
                "H1": _tec93["h1"]["status"],
                "M15": _tec93["m15"]["status"],
                "Semáforo": _dec93,
                "Índice operacional": round(max(0, min(100, _op93)), 1),
                "_disponivel": _resultado_tecnico_valido_v935(_saved933),
                "_texto": _txt93,
            })

        _scan_df93 = pd.DataFrame(_scanner93)

        if _scan_df93.empty:
            st.warning("Scanner sem resultados nesta execução.")
        elif not bool(_scan_df93["_disponivel"].any()):
            st.warning(
                "A fonte técnica não retornou dados suficientes para os pares. "
                "Verifique a CHAVE_TWELVE_DATA e o limite de chamadas da conta."
            )
        else:
            _n_ok93 = int(_scan_df93["_disponivel"].sum())
            _n_total93 = int(len(_scan_df93))
            if _n_ok93 < _n_total93:
                st.warning(
                    f"⚠️ Scanner PARCIAL: {_n_ok93}/{_n_total93} pares estão salvos com H4/H1/M15 completos. "
                    "Os demais continuam NA FILA ou precisam repetir somente o lote atual. "
                    "O ranking é provisório até chegar a 7/7."
                )
            else:
                st.success("✅ Scanner COMPLETO: 7/7 pares realmente têm H4/H1/M15 válidos.")
            _scan_show93 = (
                _scan_df93.drop(columns=["_disponivel", "_texto"])
                          .sort_values(
                              ["Índice operacional", "Score", "Ranking macro"],
                              ascending=[False, False, True],
                              kind="stable"
                          )
                          .reset_index(drop=True)
            )
            _scan_show93.insert(0, "Prioridade", range(1, len(_scan_show93) + 1))
            st.dataframe(_scan_show93, width="stretch", hide_index=True)

            # =========================================================
            # V9.3.6.4 — MELHOR OPORTUNIDADE AGORA
            # Apenas resume o scanner existente; NÃO altera sinais/pesos.
            # =========================================================
            st.markdown("### 🏆 Melhor oportunidade agora")

            _cand958 = _scan_df93.copy()
            _cand958 = _cand958[
                (_cand958["_disponivel"] == True)
                & (~_cand958["Direção"].astype(str).str.contains("AGUARDAR", case=False, na=False))
            ].copy()

            if _cand958.empty:
                st.info(
                    "⚪ Nenhum dos 7 pares possui direção macro definida com técnica utilizável neste momento."
                )
            else:
                _cand958 = _cand958.sort_values(
                    ["Índice operacional", "Score", "Ranking macro"],
                    ascending=[False, False, True],
                    kind="stable"
                )
                _best958 = _cand958.iloc[0]

                _par958 = str(_best958["Par"])
                _dir958 = str(_best958["Direção"])
                _score958 = int(round(float(_best958["Score"])))
                _qual958 = str(_best958["Qualidade"])
                _h4958 = str(_best958["H4"])
                _h1958 = str(_best958["H1"])
                _m15958 = str(_best958["M15"])
                _sem958 = str(_best958["Semáforo"])
                _idx958 = float(_best958["Índice operacional"])

                _c1, _c2, _c3, _c4 = st.columns(4)
                _c1.metric("Par prioritário", _par958)
                _c2.metric("Direção macro", _dir958)
                _c3.metric("Score Mestre", f"{_score958}/100")
                _c4.metric("Qualidade", _qual958)

                st.caption(                    f"Índice operacional: {_idx958:.1f}/100 · "
                    "Ranking automático entre os pares com dados técnicos disponíveis."
                )

                _t1, _t2, _t3 = st.columns(3)
                _t1.metric("H4 · Direção/estrutura", _h4958)
                _t2.metric("H1 · Pullback/localização", _h1958)
                _t3.metric("M15 · Gatilho", _m15958)

                if _sem958.startswith("🟢"):
                    st.success(
                        f"🟢 CONFIGURAÇÃO COMPLETA — {_par958}: {_dir958}. "
                        "H4 + H1 + M15 estão alinhados. Confira calendário/risco e gestão antes de qualquer execução."
                    )

                    _tec_best937 = _scan_results934.get(_par958, {}) if "_scan_results934" in locals() else {}
                    _m15_best937 = (_tec_best937.get("m15") or {})
                    _candle_best937 = str(
                        _m15_best937.get("datetime", "")
                        or _m15_best937.get("candle", "")
                        or _m15_best937.get("data", "")
                    )
                    _px_best937 = _tec_best937.get("preco_m15")
                    _okb937, _msgb937, _novob937 = _registrar_config_completa_v937(
                        _par958, _dir958, _score958, _qual958, _idx958,
                        _h4958, _h1958, _m15958,
                        candle_m15=_candle_best937,
                        preco_entrada=_px_best937,
                    )
                    if _okb937 and _novob937:
                        st.success("💾 V9.3.7: configuração completa registrada automaticamente no histórico.")
                elif "AGUARDAR GATILHO M15" in _sem958:
                    st.warning(
                        f"🟡 {_par958} é a prioridade atual, mas ainda NÃO há configuração completa. "
                        "H4 e H1 estão alinhados; falta o gatilho do M15."
                    )
                elif _sem958.startswith("🔴"):
                    st.error(
                        f"🔴 {_par958} tem força macro, porém a técnica/calendário bloqueia a configuração agora: {_sem958}."
                    )
                else:
                    st.warning(
                        f"🟡 {_par958} é o melhor candidato atual, mas ainda precisa de confirmação: {_sem958}."
                    )

                st.caption(
                    "Uso educacional: este painel resume o modelo macro+técnico do APP; "
                    "não é garantia de resultado nem ordem automática de mercado."
                )

                # =========================================================
                # V9.3.6.4 — MONITOR DO GATILHO M15
                # Reconsulta SOMENTE o par prioritário e SOMENTE o M15.
                # Não altera macro, pesos, Score Mestre ou ranking.
                # =========================================================
                st.markdown("#### 🔔 Monitor do gatilho M15")
                st.caption(
                    "A consulta usa somente o M15 do par prioritário. "
                    "Toda tentativa fica registrada na tela, inclusive erro, mesmo candle ou primeira leitura."
                )

                _m15_wait962 = (
                    "AGUARDAR GATILHO" in _m15958.upper()
                    or "SEM GATILHO" in _m15958.upper()
                )

                if _m15_wait962:
                    # =====================================================
                    # V9.3.6.4 — AUTO MONITOR M15
                    # Funciona enquanto o app estiver aberto/ativo.
                    # Verifica a cada 5 minutos e só recalcula se o candle
                    # M15 realmente mudou.
                    # =====================================================
                    # =====================================================
                    # V10.2.1 — MONITOR M15 EM MODO ESTÁVEL
                    # Remove o fragmento temporizado do Streamlit, que podia
                    # disputar a árvore visual com um rerun completo e causar
                    # NotFoundError/removeChild no navegador.
                    #
                    # A revalidação automática continua ocorrendo de forma
                    # segura em reruns completos da página, no máximo 1 vez
                    # a cada 5 minutos. O botão manual abaixo continua ativo.
                    # =====================================================
                    _safe_now1021 = pd.Timestamp.utcnow()
                    _safe_last_raw1021 = st.session_state.get("v1021_last_safe_m15_check", "")
                    try:
                        _safe_last1021 = pd.Timestamp(_safe_last_raw1021) if _safe_last_raw1021 else None
                        if _safe_last1021 is not None:
                            if _safe_last1021.tzinfo is None:
                                _safe_last1021 = _safe_last1021.tz_localize("UTC")
                            else:
                                _safe_last1021 = _safe_last1021.tz_convert("UTC")
                    except Exception:
                        _safe_last1021 = None

                    _safe_due1021 = (
                        _safe_last1021 is None
                        or (_safe_now1021 - _safe_last1021) >= pd.Timedelta(minutes=5)
                    )

                    if _safe_due1021:
                        st.session_state["v1021_last_safe_m15_check"] = _safe_now1021.isoformat()
                        _safe_lado1021 = _lado_macro_v92(_dir958)

                        try:
                            _td_time_series_v92.clear()
                        except Exception:
                            pass

                        _safe_df1021 = _td_time_series_v92(_par958, "15min", 100)
                        _safe_prev1021 = st.session_state.get("v9362_m15_monitor", {})
                        _safe_prev_dt1021 = (
                            str(_safe_prev1021.get("datetime_atual", ""))
                            if _safe_prev1021.get("par") == _par958 else ""
                        )

                        _safe_reg1021 = {
                            "par": _par958,
                            "verificacao_realizada": True,
                            "verificado_em": _safe_now1021.isoformat(),
                            "datetime_anterior": _safe_prev_dt1021 or "Primeira verificação",
                            "datetime_atual": "",
                            "preco": None,
                            "novo_candle": False,
                            "status": "",
                            "texto": "",
                            "consulta_status": "SAFE_INICIADA",
                            "erro": "",
                            "http_status": "",
                            "api_message": "",
                            "candles_validos": 0,
                            "modo": "AUTOMÁTICO_SEGURO",
                        }

                        _safe_diag1021 = dict(_safe_df1021.attrs.get("td_diag", {}) or {})
                        _safe_reg1021["http_status"] = _safe_diag1021.get("http_status", "")
                        _safe_reg1021["api_message"] = str(_safe_diag1021.get("api_message", "") or "")
                        _safe_reg1021["candles_validos"] = int(
                            _safe_diag1021.get("candles_validos", len(_safe_df1021)) or 0
                        )

                        if _safe_df1021.empty:
                            _safe_err1021 = str(
                                _safe_df1021.attrs.get("erro_td", "")
                                or _safe_reg1021["api_message"]
                                or "A Twelve Data não retornou candles M15."
                            )
                            _safe_reg1021["consulta_status"] = "SAFE_ERRO"
                            _safe_reg1021["erro"] = _safe_err1021
                            _safe_reg1021["texto"] = _safe_err1021
                        else:
                            _safe_dt1021 = str(_safe_df1021["datetime"].iloc[-1])
                            _safe_px1021 = float(_safe_df1021["close"].iloc[-1])
                            _safe_reg1021["datetime_atual"] = _safe_dt1021
                            _safe_reg1021["preco"] = _safe_px1021

                            if _safe_lado1021 not in ("BUY", "SELL"):
                                _safe_reg1021["consulta_status"] = "SAFE_MACRO_SEM_DIRECAO"
                                _safe_reg1021["status"] = "⚪ MACRO AGUARDAR"
                                _safe_reg1021["texto"] = (
                                    "M15 disponível, mas o macro ainda não definiu BUY/SELL."
                                )
                            elif _safe_prev_dt1021 and _safe_dt1021 == _safe_prev_dt1021:
                                _safe_reg1021["consulta_status"] = "SAFE_MESMO_CANDLE"
                                _safe_reg1021["status"] = str(_safe_prev1021.get("status", ""))
                                _safe_reg1021["texto"] = str(
                                    _safe_prev1021.get("texto", "Decisão anterior mantida.")
                                )
                            else:
                                _safe_analise1021 = _analise_m15_v92(_safe_df1021, _safe_lado1021)
                                _safe_reg1021["consulta_status"] = (
                                    "SAFE_PRIMEIRA_LEITURA"
                                    if not _safe_prev_dt1021 else "SAFE_NOVO_CANDLE"
                                )
                                _safe_reg1021["novo_candle"] = bool(_safe_prev_dt1021)
                                _safe_reg1021["status"] = str(_safe_analise1021.get("status", ""))
                                _safe_reg1021["texto"] = str(_safe_analise1021.get("texto", ""))

                        st.session_state["v9362_m15_monitor"] = _safe_reg1021

                    _safe_mon1021 = st.session_state.get("v9362_m15_monitor", {})
                    _safe_last_text1021 = str(_safe_mon1021.get("datetime_atual", "") or "—")
                    st.caption(
                        "🛡️ Monitor M15 em modo estável V10.2.1 · "
                        "revalida em reruns completos a cada ≥5 min, sem fragmento temporizado. "
                        f"Último candle: {_safe_last_text1021}. "
                        "O botão manual abaixo força uma consulta quando necessário."
                    )

                    _mon962 = st.session_state.get("v9362_m15_monitor", {})

                    if st.button(
                        f"🔎 Verificar novo M15 de {_par958}",
                        key=f"v9362_recheck_m15_{_par958.replace('/','_')}",
                        width="content",
                    ):
                        _lado962 = _lado_macro_v92(_dir958)
                        _anterior962 = st.session_state.get("v9362_m15_monitor", {})
                        _dt_anterior962 = (
                            str(_anterior962.get("datetime_atual", ""))
                            if _anterior962.get("par") == _par958 else ""
                        )

                        # Registra a tentativa ANTES de qualquer caminho de retorno.
                        _registro962 = {
                            "par": _par958,
                            "verificacao_realizada": True,
                            "verificado_em": pd.Timestamp.utcnow().isoformat(),
                            "datetime_anterior": _dt_anterior962 or "Primeira verificação",
                            "datetime_atual": "",
                            "preco": None,
                            "novo_candle": False,
                            "status": "",
                            "texto": "",
                            "consulta_status": "INICIADA",
                            "erro": "",
                            "http_status": "",
                            "api_message": "",
                            "candles_validos": 0,
                            "modo": "MANUAL",
                        }

                        _df15962 = _td_time_series_v92(_par958, "15min", 100)
                        _diag962 = dict(_df15962.attrs.get("td_diag", {}) or {})

                        _registro962["http_status"] = _diag962.get("http_status", "")
                        _registro962["api_message"] = str(_diag962.get("api_message", "") or "")
                        _registro962["candles_validos"] = int(
                            _diag962.get("candles_validos", len(_df15962)) or 0
                        )

                        if _df15962.empty:
                            _erro962 = str(
                                _df15962.attrs.get("erro_td", "")
                                or _registro962["api_message"]
                                or "A Twelve Data não retornou candles M15."
                            )
                            _registro962["consulta_status"] = "ERRO"
                            _registro962["erro"] = _erro962
                            _registro962["texto"] = _erro962

                        else:
                            _novo_dt962 = str(_df15962["datetime"].iloc[-1])
                            _preco962 = float(_df15962["close"].iloc[-1])
                            _registro962["datetime_atual"] = _novo_dt962
                            _registro962["preco"] = _preco962

                            if _lado962 not in ("BUY", "SELL"):
                                _registro962["consulta_status"] = "MACRO_SEM_DIRECAO"
                                _registro962["status"] = "⚪ MACRO AGUARDAR"
                                _registro962["texto"] = (
                                    "M15 recebido, mas o viés macro ainda não definiu BUY/SELL."
                                )
                            elif _dt_anterior962 and _novo_dt962 == _dt_anterior962:
                                _registro962["consulta_status"] = "MESMO_CANDLE"
                                _registro962["novo_candle"] = False
                                _registro962["status"] = str(_anterior962.get("status", ""))
                                _registro962["texto"] = str(
                                    _anterior962.get("texto", "Decisão anterior mantida.")
                                )
                            else:
                                _analise962 = _analise_m15_v92(_df15962, _lado962)
                                _registro962["consulta_status"] = (
                                    "PRIMEIRA_LEITURA" if not _dt_anterior962 else "NOVO_CANDLE"
                                )
                                _registro962["novo_candle"] = bool(_dt_anterior962)
                                _registro962["status"] = str(_analise962.get("status", ""))
                                _registro962["texto"] = str(_analise962.get("texto", ""))

                        st.session_state["v9362_m15_monitor"] = _registro962
                        st.rerun()

                    _mon962 = st.session_state.get("v9362_m15_monitor", {})

                    # V9.3.6.4 — destaque final quando Macro + H4 + H1 + M15 estão alinhados.
                    if (
                        _mon962.get("par") == _par958
                        and _mon962.get("verificacao_realizada")
                        and str(_mon962.get("status", "")).startswith("🟢")
                    ):
                        _px_final964 = _mon962.get("preco")
                        _dt_final964 = str(_mon962.get("datetime_atual", "") or "—")
                        _px_txt964 = (
                            f"{float(_px_final964):.5f}"
                            if _px_final964 is not None else "—"
                        )
                        st.success(
                            f"🟢 CONFIGURAÇÃO COMPLETA — {_par958} — {_dir958}\n\n"
                            f"Macro + H4 + H1 + M15 estão alinhados. "
                            f"Confirmação M15: {_dt_final964} · preço consultado: {_px_txt964}."
                        )
                        st.caption(
                            "Este aviso indica confluência completa do modelo do APP; "
                            "não é garantia de lucro nem ordem automática de mercado."
                        )

                        _ok937, _msg937, _novo937 = _registrar_config_completa_v937(
                            _par958, _dir958, _score958, _qual958, _idx958,
                            _h4958, _h1958, str(_mon962.get("status", _m15958)),
                            candle_m15=_dt_final964,
                            preco_entrada=_px_final964,
                        )
                        if _ok937 and _novo937:
                            st.success("💾 V9.3.7: configuração completa registrada automaticamente no histórico.")
                        elif not _ok937:
                            st.warning(f"⚠️ Registro V9.3.7 não foi salvo: {_msg937}")

                    if _mon962.get("par") == _par958 and _mon962.get("verificacao_realizada"):
                        st.markdown("##### 🧾 Resultado da última verificação M15")

                        _a962, _b962, _c962, _d962 = st.columns(4)
                        _a962.metric("Candle anterior", str(_mon962.get("datetime_anterior", "—")))
                        _b962.metric("Candle atual", str(_mon962.get("datetime_atual", "—")) or "—")
                        _px962 = _mon962.get("preco")
                        _c962.metric("Preço M15", f"{float(_px962):.5f}" if _px962 is not None else "—")

                        _cs962 = str(_mon962.get("consulta_status", ""))
                        if _cs962 in ("NOVO_CANDLE", "AUTO_NOVO_CANDLE"):
                            _novo_txt962 = "SIM ✅"
                        elif _cs962 in ("MESMO_CANDLE", "AUTO_MESMO_CANDLE"):
                            _novo_txt962 = "NÃO ⏸️"
                        elif _cs962 in ("PRIMEIRA_LEITURA", "AUTO_PRIMEIRA_LEITURA"):
                            _novo_txt962 = "BASE 📌"
                        else:
                            _novo_txt962 = "—"
                        _d962.metric("Novo candle?", _novo_txt962)

                        st.caption(
                            f"Modo: {_mon962.get('modo', 'MANUAL')} · "
                            f"Consulta: {_cs962 or '—'} · "
                            f"HTTP: {_mon962.get('http_status', '—')} · "
                            f"Candles válidos: {_mon962.get('candles_validos', 0)} · "
                            f"Verificado em: {_mon962.get('verificado_em', '—')}"
                        )

                        _erro962 = str(_mon962.get("erro", ""))
                        _st962 = str(_mon962.get("status", ""))
                        _tx962 = str(_mon962.get("texto", ""))

                        if _erro962:
                            st.error(f"🔴 Falha na consulta M15: {_erro962}")
                        elif _cs962 in ("MESMO_CANDLE", "AUTO_MESMO_CANDLE"):
                            st.info(
                                "⏸️ A fonte retornou o mesmo candle. "
                                "A decisão técnica anterior foi mantida."
                            )
                        elif _st962.startswith("🟢"):
                            st.success(
                                f"🟢 GATILHO M15 CONFIRMADO — {_par958}. {_tx962}"
                            )
                        elif _st962.startswith("🔴"):
                            st.error(
                                f"🔴 M15 ainda não confirma {_par958}: {_st962}. {_tx962}"
                            )
                        elif _st962:
                            st.warning(
                                f"🟡 Estado M15 de {_par958}: {_st962}. {_tx962}"
                            )
                        else:
                            st.info("Consulta registrada; ainda não há classificação técnica.")
                else:
                    st.success(
                        f"🟢 O M15 de {_par958} já não está em estado de espera no scanner atual: {_m15958}."
                    )

            # V9.3.5.3 — diagnóstico persistente, sem nova chamada à Twelve Data.
            _diag_rows9353 = []
            for _par_diag9353, _res_diag9353 in _resultados933.items():
                if _resultado_tecnico_valido_v935(_res_diag9353):
                    continue
                _tec_diag9353 = _res_diag9353.get("tecnico", {}) if isinstance(_res_diag9353, dict) else {}
                _det9353 = []
                for _tf9353 in ("h4", "h1", "m15"):
                    _bl9353 = _tec_diag9353.get(_tf9353, {}) or {}
                    _st9353 = str(_bl9353.get("status", "INDISPONÍVEL"))
                    _why9353 = str(
                        _bl9353.get("motivo", "")
                        or _bl9353.get("erro", "")
                        or _bl9353.get("message", "")
                        or _bl9353.get("texto", "")
                    ).strip()
                    _det9353.append(
                        f"{_tf9353.upper()}: {_st9353}" +
                        (f" — {_why9353}" if _why9353 else "")
                    )
                _geral9353 = str(
                    _tec_diag9353.get("motivo", "")
                    or _tec_diag9353.get("erro", "")
                    or _tec_diag9353.get("diagnostico", "")
                    or _res_diag9353.get("texto", "")
                    or "A fonte não informou um motivo detalhado."
                ).strip()
                _diag_rows9353.append({
                    "Par": _par_diag9353,
                    "Tentativa": str(_res_diag9353.get("versao_tentativa", "REGISTRO ANTIGO")),
                    "Motivo da última tentativa": _geral9353,
                    "H4 / H1 / M15": " | ".join(_det9353),
                })

            if _diag_rows9353:
                with st.expander("🔎 Diagnóstico real da Twelve Data", expanded=True):
                    st.warning(
                        "Registros antigos podem mostrar apenas a mensagem genérica. "
                        "A V9.3.6.4 salva HTTP, código/mensagem da API e quantidade de candles por timeframe, sem expor a chave."
                    )
                    st.dataframe(pd.DataFrame(_diag_rows9353), width="stretch", hide_index=True)
                    _deep9356=[]
                    for _p9356,_r9356 in _resultados933.items():
                        if _resultado_tecnico_valido_v935(_r9356):
                            continue
                        _t9356=_r9356.get("tecnico",{}) if isinstance(_r9356,dict) else {}
                        for _k9356,_n9356 in [("h4","H4"),("h1","H1"),("m15","M15")]:
                            _d9356=(_t9356.get(_k9356,{}) or {}).get("td_diag",{}) or {}
                            if _d9356:
                                _deep9356.append({
                                    "Par":_p9356,"TF":_n9356,
                                    "Símbolo":_d9356.get("symbol",""),
                                    "Intervalo":_d9356.get("interval",""),
                                    "HTTP":_d9356.get("http_status",""),
                                    "Status API":_d9356.get("api_status",""),
                                    "Código":_d9356.get("api_code",""),
                                    "Mensagem API":_d9356.get("api_message",""),
                                    "Valores":_d9356.get("values_count",0),
                                    "Candles válidos":_d9356.get("candles_validos",0),
                                })
                    if _deep9356:
                        st.markdown("**🧪 Diagnóstico profundo V9.3.6.4**")
                        st.dataframe(pd.DataFrame(_deep9356),width="stretch",hide_index=True)
                        st.caption("A chave da Twelve Data não é exibida nem persistida.")
                    st.caption(
                        "Este painel lê o diagnóstico já persistido e não consome créditos da Twelve Data."
                    )

            _valid93 = _scan_df93[_scan_df93["_disponivel"]].copy()
            _valid93 = _valid93.sort_values(
                ["Índice operacional", "Score", "Ranking macro"],
                ascending=[False, False, True],
                kind="stable"
            )
            _best93 = _valid93.iloc[0]

            _painel_configuracoes_v937()

            st.markdown("#### 🏆 Melhor oportunidade técnica do scanner")
            _b1, _b2, _b3, _b4 = st.columns(4)
            _b1.metric("Par", str(_best93["Par"]))
            _b2.metric("Direção", str(_best93["Direção"]))
            _b3.metric("Score macro", f'{float(_best93["Score"]):.0f}/100')
            _b4.metric("Índice operacional", f'{float(_best93["Índice operacional"]):.1f}/100')

            _sem93 = str(_best93["Semáforo"])
            _msg93 = str(_best93["_texto"])
            if _sem93.startswith("🟢"):
                st.success(f"**{_sem93}** — {_msg93}")
            elif _sem93.startswith("🔴"):
                st.error(f"**{_sem93}** — {_msg93}")
            else:
                st.warning(f"**{_sem93}** — {_msg93}")

            st.info(
                "O scanner NÃO transforma o índice operacional em probabilidade de lucro. "
                "Ele serve apenas para ordenar os 7 pares pela combinação Macro + Qualidade + Técnica."
            )

            _falt93 = _scan_df93[
                (~_scan_df93["_disponivel"]) &
                (~_scan_df93["_texto"].astype(str).str.contains("Ainda não processado pela fila", na=False))
            ][["Par", "_texto"]].copy()
            if not _falt93.empty:
                _falt93.columns = ["Par", "Motivo técnico"]
                with st.expander("🔎 Diagnóstico dos pares indisponíveis", expanded=False):
                    st.dataframe(_falt93, width="stretch", hide_index=True)
                    st.caption(
                        "Se aparecer limite/crédito/quota, aguarde a renovação da cota da API. "
                        "Não é sinal contra o par."
                    )


        st.markdown("### ✅ Checklist final")
        st.markdown(
            f"""
- **Melhor par:** {_par91}
- **Viés macro:** {_dir91}
- **Score Mestre:** {_score91:.0f}/100
- **Qualidade:** {_qual91:.0f}%
- **Confluência:** {_conf91}
- **Raio-X:** {_fav91} a favor / {_neu91} neutro(s) / {_contra91} contra
- **Calendário:** {_timing91}
- **H4:** {_tec92["h4"]["status"]}
- **H1:** {_tec92["h1"]["status"]}
- **M15:** {_tec92["m15"]["status"]}
- **Semáforo técnico:** {_dec_tec92}
- **Próxima ação macro:** {_acao91}
            """
        )

        st.caption(
            "A Central de Decisão V10.2 mantém a persistência no GitHub e só considera um par completo quando H4, H1 e M15 estão realmente válidos. "
            "Ela não transforma Score Mestre em probabilidade de lucro e não substitui gestão de risco."
        )

# =========================================================
# ABA 9 — V10.2 PROFESSIONAL MACRO MARKET MAP (CAMADA OBSERVACIONAL)
# Não altera o motor base, Score Mestre ou histórico oficial.
# =========================================================
with abas[9]:
    if render_market_map is None:
        st.error(
            "A camada Professional Market Map V10.2 não pôde ser carregada. "
            "Confirme que market_map_v10.py e market_map_core_v10.py estão na raiz do repositório."
        )
        if _MARKET_MAP_V10_IMPORT_ERROR:
            st.caption(f"Diagnóstico: {_MARKET_MAP_V10_IMPORT_ERROR}")
    else:
        try:
            _macro_context_v102 = {
                "usd_score": float(usd_detalhado.get("score", 50.0)),
                "usd_components": dict(usd_detalhado.get("componentes", {})),
                "usd_quality": float(qualidade_usd),
                "fed_tone": str(fed.get("tom", "Neutro")),
                "fed_strength": float(fed.get("forca", 0.0)),
                "trend": _score_tendencias_eua(),
                "surprise_adjustment": float(st.session_state.get("usd_ajuste_surpresas", 0.0)),
                "event": _proximo_evento_macro_v65(),
                "fomc_score": (
                    float(st.session_state.get("v76_fomc_usd_score", 50.0))
                    if st.session_state.get("v77_fomc_integrado", False) else None
                ),
                "fomc_weight": float(st.session_state.get("v77_peso_fomc", 0.0)) * 100.0,
            }
            render_market_map(matriz_v61, ranking, CHAVE_TWELVE_DATA, _macro_context_v102)
        except Exception as _mm_render_exc:
            st.error(
                "O Market Map encontrou um erro, mas o motor base continua preservado. "
                "Envie esta mensagem para diagnóstico."
            )
            st.code(f"{type(_mm_render_exc).__name__}: {_mm_render_exc}")



# =========================================================
# ABA 1 — V10.2.2 PAINEL MESTRE DE OPORTUNIDADES
# Consolida Macro + Market Map + Scanner técnico + ADR.
# Não altera Score Mestre nem históricos oficiais.
# =========================================================
with abas[1]:
    if render_master_panel is None:
        st.error(
            "O Painel Mestre V10.2 não pôde ser carregado. "
            "Confirme que master_panel_v102.py está na raiz do repositório."
        )
        if _MASTER_V102_IMPORT_ERROR:
            st.caption(f"Diagnóstico: {_MASTER_V102_IMPORT_ERROR}")
    else:
        try:
            _macro_context_master_v102 = {
                "usd_score": float(usd_detalhado.get("score", 50.0)),
                "usd_components": dict(usd_detalhado.get("componentes", {})),
                "usd_quality": float(qualidade_usd),
                "fed_tone": str(fed.get("tom", "Neutro")),
                "fed_strength": float(fed.get("forca", 0.0)),
                "trend": _score_tendencias_eua(),
                "surprise_adjustment": float(st.session_state.get("usd_ajuste_surpresas", 0.0)),
                "event": _proximo_evento_macro_v65(),
                "fomc_score": (
                    float(st.session_state.get("v76_fomc_usd_score", 50.0))
                    if st.session_state.get("v77_fomc_integrado", False) else None
                ),
                "fomc_weight": float(st.session_state.get("v77_peso_fomc", 0.0)) * 100.0,
            }
            _scanner_state_master_v102 = _scanner_load_v934()

            # -------------------------------------------------
            # V10.2.2 — Atualização técnica direta pelo Painel
            # Mestre. Atualiza no máximo 2 pares por clique.
            # -------------------------------------------------
            def _master_refresh_scanner_batch_v1022():
                if not CHAVE_TWELVE_DATA:
                    return False, "CHAVE_TWELVE_DATA ausente."

                _state1022 = _scanner_load_v934()
                _results1022 = dict(_state1022.get("resultados", {}) or {})
                _last1022 = float(_state1022.get("ultimo_processamento_ts", 0.0) or 0.0)
                _wait1022 = max(0, int(61 - (time.time() - _last1022))) if _last1022 else 0
                if _wait1022 > 0:
                    return False, f"Aguarde ~{_wait1022}s antes de nova atualização técnica."

                def _age_result1022(_raw):
                    try:
                        _stamp = _raw.get("processado_em")
                        if _stamp in (None, ""):
                            return 10**9
                        if isinstance(_stamp, (int, float)):
                            return max(0.0, (time.time() - float(_stamp)) / 60.0)
                        _ts = pd.Timestamp(_stamp)
                        if _ts.tzinfo is None:
                            _ts = _ts.tz_localize("UTC")
                        else:
                            _ts = _ts.tz_convert("UTC")
                        return max(0.0, (pd.Timestamp.now(tz="UTC") - _ts).total_seconds() / 60.0)
                    except Exception:
                        return 10**9

                _candidates1022 = []
                for _, _row1022 in matriz_v61.head(7).iterrows():
                    _pair1022 = str(_row1022["Par"])
                    _raw1022 = _results1022.get(_pair1022, {})
                    _tec1022 = _raw1022.get("tecnico", {}) if isinstance(_raw1022, dict) else {}
                    _available1022 = bool(_tec1022.get("disponivel", False))
                    _age1022 = _age_result1022(_raw1022 if isinstance(_raw1022, dict) else {})
                    if (not _available1022) or _age1022 > 45.0:
                        _candidates1022.append((_age1022, _pair1022, str(_row1022["Direção"])))

                if not _candidates1022:
                    return True, "Os 7 pares já possuem técnica atual (≤45 min)."

                # Mais antigos/ausentes primeiro.
                _candidates1022.sort(key=lambda x: x[0], reverse=True)
                _batch1022 = _candidates1022[:2]
                _updated1022 = []
                _errors1022 = []

                for _, _pair1022, _dir1022 in _batch1022:
                    try:
                        _td_time_series_v92.clear()
                    except Exception:
                        pass

                    try:
                        _tec1022 = _pacote_tecnico_v92(_pair1022, _dir1022)
                        _timing1022 = globals().get("_timing91", "🟡 ATENÇÃO")
                        _dec1022, _txt1022 = _decisao_tecnica_final_v92(
                            _tec1022, _timing1022, _dir1022
                        )
                        _results1022[_pair1022] = {
                            "tecnico": _tec_to_json_v934(_tec1022),
                            "decisao": _dec1022,
                            "texto": _txt1022,
                            "processado_em": time.time(),
                            "tentativa_v1022": True,
                            "versao_tentativa": "V10.2.2",
                        }
                        _updated1022.append(_pair1022)
                    except Exception as _exc1022:
                        _errors1022.append(f"{_pair1022}: {type(_exc1022).__name__}")

                _state1022["resultados"] = _results1022
                _state1022["ultimo_processamento_ts"] = time.time()
                _ok1022, _err1022 = _scanner_save_v934(_state1022)
                if not _ok1022:
                    return False, f"Falha ao salvar scanner: {_err1022}"

                _msg1022 = (
                    "Scanner atualizado para: " + ", ".join(_updated1022)
                    if _updated1022 else
                    "Nenhum par pôde ser atualizado."
                )
                if _errors1022:
                    _msg1022 += " | Falhas: " + " ; ".join(_errors1022)
                return bool(_updated1022), _msg1022

            _last_scan_ts_master_v1022 = float(
                _scanner_state_master_v102.get("ultimo_processamento_ts", 0.0) or 0.0
            )
            _scan_wait_master_v1022 = (
                max(0, int(61 - (time.time() - _last_scan_ts_master_v1022)))
                if _last_scan_ts_master_v1022 else 0
            )

            render_master_panel(
                matriz_v61, ranking, CHAVE_TWELVE_DATA,
                _macro_context_master_v102, _scanner_state_master_v102,
                scanner_refresh_cb=_master_refresh_scanner_batch_v1022,
                scanner_refresh_remaining=_scan_wait_master_v1022,
            )
        except Exception as _master_render_exc:
            st.error(
                "O Painel Mestre encontrou um erro, mas o motor base continua preservado."
            )
            st.code(f"{type(_master_render_exc).__name__}: {_master_render_exc}")

# =========================================================
# ABA 10 — V10.3 EXPERIÊNCIA, EDUCAÇÃO E PERSONALIZAÇÃO
# Não altera o motor de decisão.
# =========================================================
with abas[10]:
    if render_experience_hub is None:
        st.error("A camada de experiência V10.3 não pôde ser carregada.")
        if _UX_V103_IMPORT_ERROR:
            st.caption(f"Diagnóstico: {_UX_V103_IMPORT_ERROR}")
    else:
        try:
            _macro_context_ux_v103 = {
                "usd_score": float(usd_detalhado.get("score", 50.0)),
                "usd_quality": float(qualidade_usd),
                "fed_tone": str(fed.get("tom", "Neutro")),
                "fed_strength": float(fed.get("forca", 0.0)),
                "surprise_adjustment": float(st.session_state.get("usd_ajuste_surpresas", 0.0)),
                "event": _proximo_evento_macro_v65(),
                "fomc_score": (
                    float(st.session_state.get("v76_fomc_usd_score", 50.0))
                    if st.session_state.get("v77_fomc_integrado", False) else None
                ),
            }
            render_experience_hub(
                ranking,
                matriz_v61,
                macro_context=_macro_context_ux_v103,
                source_status=STATUS_FONTE,
                app_version=APP_VERSION,
            )
        except Exception as _ux_render_exc:
            st.error("A aba de experiência encontrou um erro, mas o motor operacional continua preservado.")
            st.code(f"{type(_ux_render_exc).__name__}: {_ux_render_exc}")

# =========================================================
# ABA 11 — V10.4 PRODUTO, NAVEGAÇÃO, GRÁFICOS E FEEDBACK
# =========================================================
with abas[11]:
    if render_v104_hub is None:
        st.error("A camada de produto V10.4 não pôde ser carregada.")
        if _PRODUCT_V104_IMPORT_ERROR:
            st.caption(f"Diagnóstico: {_PRODUCT_V104_IMPORT_ERROR}")
    else:
        try:
            render_v104_hub(
                history_fetcher=_fred_observacoes,
                feedback_saver=_salvar_feedback_v104,
                refresh_callback=_refresh_central_v104,
                app_version=APP_VERSION,
            )
        except Exception as _prod_render_exc:
            st.error("A aba Produto V10.4 encontrou um erro, mas o motor operacional continua preservado.")
            st.code(f"{type(_prod_render_exc).__name__}: {_prod_render_exc}")

# =========================================================
# ABA 12 — V10.5 CENTRO DE MELHORIAS
# =========================================================
with abas[12]:
    if render_v105_center is None:
        st.error("O Centro de Melhorias V10.5 não pôde ser carregado.")
        if _EVOLUTION_V105_IMPORT_ERROR:
            st.caption(f"Diagnóstico: {_EVOLUTION_V105_IMPORT_ERROR}")
    else:
        try:
            render_v105_center(
                history_fetcher=_fred_observacoes,
                refresh_callback=_refresh_central_v104,
                app_version=APP_VERSION,
            )
        except Exception as _v105_render_exc:
            st.error("A aba Melhorias V10.5 encontrou um erro, mas o motor operacional continua preservado.")
            st.code(f"{type(_v105_render_exc).__name__}: {_v105_render_exc}")

    st.divider()
    if render_shadow_mode_panel is None:
        st.warning("Shadow Mode AtlasQuant indisponível; produção permanece inalterada.")
        if _ATLASQUANT_SHADOW_IMPORT_ERROR:
            st.caption(f"Diagnóstico Shadow Mode: {_ATLASQUANT_SHADOW_IMPORT_ERROR}")
    else:
        try:
            if ensure_shadow_hydrated is not None:
                _aq_shadow_rows, _aq_shadow_load = ensure_shadow_hydrated()
            else:
                _aq_shadow_rows, _aq_shadow_load = (
                    st.session_state.get("atlasquant_shadow_samples", []),
                    {"ok":False,"reason":"HYDRATOR_UNAVAILABLE"},
                )
            render_shadow_mode_panel(
                _aq_shadow_rows,
                min_samples=100,
            )
            if bool(_aq_shadow_load.get("ok",False)) and _aq_shadow_load.get("reason")=="LOADED":
                st.caption(
                    f"Shadow persistente carregado: {int(_aq_shadow_load.get('samples',0))} amostra(s)."
                )
        except Exception as _aq_shadow_load_exc:
            st.warning("Shadow Mode persistente em modo seguro; produção permanece inalterada.")
            st.caption(f"Diagnóstico: {type(_aq_shadow_load_exc).__name__}: {_aq_shadow_load_exc}")

    # AtlasQuant research history snapshot — one persistent read per rerun.
    # Calibration, Performance, Stability and Validation consume the same
    # immutable snapshot so opening Improvements does not repeat GitHub reads.
    _aq_research_df = pd.DataFrame(columns=_config_cols_v937())
    _aq_research_err = ""
    try:
        _aq_research_df, _aq_research_err = _config_ler_v937()
    except Exception as _aq_research_load_exc:
        _aq_research_err = (
            f"{type(_aq_research_load_exc).__name__}: {_aq_research_load_exc}"
        )

    st.divider()
    if render_calibration_lab is None:
        st.warning("Conviction Calibration Lab indisponível; pesos e score permanecem inalterados.")
        if _ATLASQUANT_CALIBRATION_IMPORT_ERROR:
            st.caption(f"Diagnóstico Calibration Lab: {_ATLASQUANT_CALIBRATION_IMPORT_ERROR}")
    else:
        try:
            if _aq_research_err and (_aq_research_df is None or _aq_research_df.empty):
                st.info(f"Calibration Lab aguardando histórico persistente: {_aq_research_err}")
            else:
                render_calibration_lab(
                    _aq_research_df.copy(),
                    min_band_samples=30,
                    min_total_samples=100,
                )
        except Exception as _aq_calib_render_exc:
            st.warning("Calibration Lab em modo seguro; nenhuma regra/ponderação foi alterada.")
            st.caption(f"Diagnóstico: {type(_aq_calib_render_exc).__name__}: {_aq_calib_render_exc}")

    st.divider()
    if render_performance_lab is None:
        st.warning("Performance Lab indisponível; nenhuma regra operacional foi alterada.")
        if _ATLASQUANT_PERFORMANCE_IMPORT_ERROR:
            st.caption(f"Diagnóstico Performance Lab: {_ATLASQUANT_PERFORMANCE_IMPORT_ERROR}")
    else:
        try:
            if _aq_research_err and (_aq_research_df is None or _aq_research_df.empty):
                st.info(f"Performance Lab aguardando histórico persistente: {_aq_research_err}")
            else:
                render_performance_lab(
                    _aq_research_df.copy(),
                    min_total_samples=100,
                    min_group_samples=30,
                )
        except Exception as _aq_perf_render_exc:
            st.warning("Performance Lab em modo seguro; pesos, thresholds e gates permanecem inalterados.")
            st.caption(f"Diagnóstico: {type(_aq_perf_render_exc).__name__}: {_aq_perf_render_exc}")

    st.divider()
    if render_stability_lab is None:
        st.warning("Stability Lab indisponível; nenhuma decisão operacional foi alterada.")
        if _ATLASQUANT_STABILITY_IMPORT_ERROR:
            st.caption(f"Diagnóstico Stability Lab: {_ATLASQUANT_STABILITY_IMPORT_ERROR}")
    else:
        try:
            if _aq_research_err and (_aq_research_df is None or _aq_research_df.empty):
                st.info(f"Stability Lab aguardando histórico persistente: {_aq_research_err}")
            else:
                render_stability_lab(
                    _aq_research_df.copy(),
                    min_fold_samples=30,
                    session_min_samples=10,
                )
        except Exception as _aq_stability_render_exc:
            st.warning("Stability Lab em modo seguro; auto-otimização continua desativada.")
            st.caption(f"Diagnóstico: {type(_aq_stability_render_exc).__name__}: {_aq_stability_render_exc}")

    st.divider()
    if render_expansion_budget_planner is None:
        st.warning("Planejador de expansão técnica indisponível; cobertura atual permanece inalterada.")
        if _ATLASQUANT_EXPANSION_BUDGET_IMPORT_ERROR:
            st.caption(f"Diagnóstico Budget Planner: {_ATLASQUANT_EXPANSION_BUDGET_IMPORT_ERROR}")
    else:
        render_expansion_budget_planner(
            current_pairs=7,
            target_pairs=28,
            daily_cap=480,
        )

    st.divider()
    if render_adaptive_coverage_plan is None:
        st.warning("Plano adaptativo de cobertura indisponível; pipeline atual permanece inalterado.")
        if _ATLASQUANT_ADAPTIVE_COVERAGE_IMPORT_ERROR:
            st.caption(f"Diagnóstico Adaptive Coverage: {_ATLASQUANT_ADAPTIVE_COVERAGE_IMPORT_ERROR}")
    else:
        render_adaptive_coverage_plan()

    st.divider()
    if render_validation_readiness is None:
        st.warning("Validation Readiness Center indisponível; nenhuma promoção é permitida.")
        if _ATLASQUANT_VALIDATION_IMPORT_ERROR:
            st.caption(f"Diagnóstico Validation Center: {_ATLASQUANT_VALIDATION_IMPORT_ERROR}")
    else:
        try:
            if _aq_research_err and (_aq_research_df is None or _aq_research_df.empty):
                st.info(f"Validation Center aguardando histórico persistente: {_aq_research_err}")
            else:
                _aq_validation_result = render_validation_readiness(
                    _aq_research_df.copy(),
                    st.session_state.get("atlasquant_shadow_samples", []),
                    horizon="24h",
                )
                if render_validation_evidence is not None:
                    render_validation_evidence(
                        _aq_validation_result,
                        engine_version=APP_VERSION,
                    )
                elif _ATLASQUANT_EVIDENCE_IMPORT_ERROR:
                    st.caption(
                        f"Evidence Bundle indisponível: {_ATLASQUANT_EVIDENCE_IMPORT_ERROR}"
                    )
        except Exception as _aq_validation_exc:
            st.warning("Validation Center em modo seguro; merge/promoção continuam bloqueados.")
            st.caption(f"Diagnóstico: {type(_aq_validation_exc).__name__}: {_aq_validation_exc}")

# =========================================================
# ABA 13 — V10.6.2 FRESH-PRICE SNAPSHOT RECOVERY
# =========================================================
with abas[13]:
    if render_currency_news_panel is None:
        st.error("A inteligência global de notícias V10.6 não pôde ser carregada.")
        if _CURRENCY_NEWS_V106_IMPORT_ERROR:
            st.caption(f"Diagnóstico: {_CURRENCY_NEWS_V106_IMPORT_ERROR}")
    else:
        try:
            render_currency_news_panel(
                matrix=matriz_v61,
                ranking=ranking,
                newsapi_key=CHAVE_NEWSAPI,
            )
        except Exception as _v106_render_exc:
            st.error(
                "A aba Notícias Globais V10.6 encontrou um erro, "
                "mas o motor operacional continua preservado."
            )
            st.code(f"{type(_v106_render_exc).__name__}: {_v106_render_exc}")

# =========================================================
# ABA 14 — V10.7 FULL BACKGROUND AUTOPILOT
# =========================================================
with abas[14]:
    if render_autopilot_v107 is None:
        st.error("O painel Autopilot V10.7 não pôde ser carregado.")
        if _AUTOPILOT_V107_IMPORT_ERROR:
            st.caption(f"Diagnóstico: {_AUTOPILOT_V107_IMPORT_ERROR}")
    else:
        render_autopilot_v107()

# No modo GitHub Actions/AppTest, persiste a Matriz atual para o runner background.
if os.getenv("USD_MACRO_AUTOPILOT", "") == "1":
    _ok_auto107, _msg_auto107 = _autopilot_save_inputs_v107()
    if not _ok_auto107:
        print("AUTOPILOT_INPUT_WARNING:", _msg_auto107)

# =========================================================
# ABA 1 — CENTRAL INSTITUCIONAL DOS 7 PARES V11.0.1
# Renderizada ao final para reutilizar a Matriz oficial já calculada.
# =========================================================
with abas[0]:
    if render_g8_radar is not None:
        try:
            render_g8_radar(ranking, neutral_band=5.0, top_n=8)
        except Exception as _aq_radar_exc:
            st.warning("Radar G8 temporariamente indisponível; motor operacional preservado.")
            st.caption(f"Diagnóstico Radar G8: {type(_aq_radar_exc).__name__}")
    elif _ATLASQUANT_DASHBOARD_IMPORT_ERROR:
        st.caption(f"Radar G8 em modo compatível: {_ATLASQUANT_DASHBOARD_IMPORT_ERROR}")

    if render_coverage_funnel is not None:
        try:
            render_coverage_funnel(ranking, neutral_band=5.0)
        except Exception as _aq_coverage_exc:
            st.warning("Mapa de cobertura temporariamente indisponível; nenhuma permissão operacional foi ampliada.")
            st.caption(f"Diagnóstico Coverage Funnel: {type(_aq_coverage_exc).__name__}")
    elif _ATLASQUANT_COVERAGE_IMPORT_ERROR:
        st.caption(f"Coverage Funnel em modo compatível: {_ATLASQUANT_COVERAGE_IMPORT_ERROR}")

    if render_pair_intelligence_v110 is None:
        st.error("A Central Institucional V11.0.8 não pôde ser carregada.")
        if _PAIR_INTEL_V110_IMPORT_ERROR:
            st.caption(f"Diagnóstico: {_PAIR_INTEL_V110_IMPORT_ERROR}")
    elif "matriz_v61" not in globals() or matriz_v61 is None or matriz_v61.empty:
        st.warning("A Matriz dos 7 pares ainda não ficou disponível nesta execução.")
    else:
        _macro_v108 = {
            "usd_score": float(usd_detalhado.get("score", 50.0)) if "usd_detalhado" in globals() else 50.0,
            "usd_quality": float(qualidade_usd) if "qualidade_usd" in globals() else 0.0,
        }
        try:
            _macro_v108["event"] = _proximo_evento_macro_v65()
        except Exception:
            _macro_v108["event"] = {}
        render_pair_intelligence_v110(matriz_v61, ranking, fed=fed, macro_context=_macro_v108, weights=PESOS)
