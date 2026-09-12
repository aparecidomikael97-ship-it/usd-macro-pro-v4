#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🦅 USD Macro Pro — V5.2 PAINEL MACRO
================================
- Interface em português
- Corrige unidades de inflação e PIB no ranking global
- Corrige Payroll para variação mensal
- Valida dados absurdos e usa fallback quando necessário
- Corrige limites de preço para pares como USD/JPY
- Mantém painel EUA, surpresa econômica, pares, Fed, histórico e teste histórico
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
import re

# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

APP_VERSION = "5.2 — SCORE MACRO FOREX"
HIST_SCORES = "historico_scores_v5.parquet"
HIST_SINAIS = "historico_sinais_v5.parquet"

st.set_page_config(
    page_title="USD Macro Pro — V5.2 Português",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

IMPACTO_MAX_FED = 18.0
STATUS_FONTE = {}

# =========================================================
# BARRA LATERAL
# =========================================================

st.sidebar.title("🦅 USD Macro Pro")
st.sidebar.caption(f"Versão {APP_VERSION}")

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


@st.cache_data(ttl=3600, show_spinner="Carregando dados macroeconômicos dos EUA...")
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

    bruto = {
        "Juros do Fed": _fred_ultimo(SERIES_EUA["Juros do Fed"], 120),
        "IPC anual": _fred_variacao_anual_percentual(SERIES_EUA["IPC"], 120),
        "IPC Núcleo anual": _fred_variacao_anual_percentual(SERIES_EUA["IPC Núcleo"], 120),
        "PCE anual": _fred_variacao_anual_percentual(SERIES_EUA["PCE"], 120),
        "PCE Núcleo anual": _fred_variacao_anual_percentual(SERIES_EUA["PCE Núcleo"], 120),
        "Payroll variação mensal (mil)": _fred_variacao_mensal_nivel(SERIES_EUA["Payroll"]),
        "Desemprego": _fred_ultimo(SERIES_EUA["Desemprego"], 120),
        "PIB": _fred_ultimo(SERIES_EUA["PIB"], 240),
        "Treasury 2 anos": _fred_ultimo(SERIES_EUA["Treasury 2 anos"], 14),
        "Treasury 10 anos": _fred_ultimo(SERIES_EUA["Treasury 10 anos"], 14),
        "Índice amplo do dólar": _fred_ultimo(SERIES_EUA["Índice amplo do dólar"], 14),
    }

    limites = {
        "Juros do Fed": (-1, 25),
        "IPC anual": (-5, 25),
        "IPC Núcleo anual": (-5, 25),
        "PCE anual": (-5, 25),
        "PCE Núcleo anual": (-5, 25),
        "Payroll variação mensal (mil)": (-3000, 3000),
        "Desemprego": (0, 30),
        "PIB": (-20, 20),
        "Treasury 2 anos": (-2, 20),
        "Treasury 10 anos": (-2, 20),
        "Índice amplo do dólar": (50, 200),
    }

    dados = {
        chave: _usar_ou_fallback(bruto[chave], fallback[chave], *limites[chave])
        for chave in fallback
    }

    STATUS_FONTE["EUA"] = "✅ FRED + validação" if CHAVE_FRED else "⚠️ Valores de segurança"
    return dados

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
            + usd_det["componentes"]["Atividade"] * 0.15
            + usd_det["componentes"]["Juros / Treasury 2Y"] * 0.35
        )
        df.loc[iu, "Influência_Fed"] = usd_det["componentes"]["Federal Reserve"] - 50

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
# SURPRESA ECONÔMICA
# =========================================================

def classificar_surpresa(real, previsao, maior_favorece_usd=True, tolerancia=0.0):
    if previsao is None or not np.isfinite(previsao):
        return {"Surpresa": np.nan, "Pontuação": 0.0, "Classe": "Sem previsão"}

    surpresa = real - previsao
    if abs(surpresa) <= tolerancia:
        classe, pontos = "Neutro", 0.0
    else:
        positivo = surpresa > 0 if maior_favorece_usd else surpresa < 0
        classe = "Favorável ao USD" if positivo else "Desfavorável ao USD"
        pontos = 1.0 if positivo else -1.0

    return {"Surpresa": surpresa, "Pontuação": pontos, "Classe": classe}

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

st.title("🦅 USD Macro Pro — V5.2 Português")
st.caption("Dados econômicos → Inflação → Fed → Força das moedas → Pares → Teste histórico")

icone_tom = {"Restritivo": "🔴", "Flexível": "🟢", "Neutro": "⚪"}.get(fed["tom"], "⚪")
st.info(f"Fed: {icone_tom} **{fed['tom']}** | Intensidade: {fed['forca']:+.2f}")

abas = st.tabs([
    "🏆 Classificação",
    "🇺🇸 Painel EUA",
    "💱 Pares e Confiança",
    "🏦 Fed e Notícias",
    "🧾 Histórico",
    "📈 Teste Histórico",
])

# =========================================================
# ABA 1 — CLASSIFICAÇÃO
# =========================================================
with abas[0]:
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
    st.dataframe(tabela, use_container_width=True, hide_index=True)

    top3 = ranking.head(3)["Código"].tolist()
    ultimas3 = ranking.tail(3)["Código"].tolist()
    st.success(f"🏆 Mais fortes: {', '.join(top3)}")
    st.error(f"📉 Mais fracas: {', '.join(ultimas3)}")

    with st.expander("🔎 Verificação da qualidade dos dados"):
        st.write("O sistema rejeita automaticamente valores fora de faixas plausíveis e usa um valor de segurança quando a série está ausente, antiga ou em unidade incompatível.")
        st.dataframe(
            tabela[["Código", "Juros %", "Juros reais aprox. %", "Inflação anual %", "PIB real anual %", "Fonte"]],
            use_container_width=True,
            hide_index=True,
        )

    if st.button("💾 Salvar registro da classificação"):
        st.toast(salvar_snapshot(ranking))

# =========================================================
# ABA 2 — EUA
# =========================================================
with abas[1]:
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
    st.dataframe(comp_df, use_container_width=True, hide_index=True)
    st.caption("O score é uma leitura macro relativa, não uma promessa de taxa de acerto nem uma probabilidade estatística.")

    st.markdown("---")
    st.subheader("Indicadores Econômicos dos Estados Unidos")
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

    st.markdown("---")
    st.subheader("🎯 Surpresa Econômica — Real × Previsão")
    st.caption("Digite o valor divulgado, a previsão do mercado e o valor anterior. O modelo estima a direção do impacto no USD.")

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
        c_real, c_prev, c_ant = st.columns(3)
        with c_real:
            real = st.number_input(f"{nome} — Real", value=0.0, step=0.1, key=f"real_{nome}")
        with c_prev:
            previsao = st.number_input(f"{nome} — Previsão", value=0.0, step=0.1, key=f"previsao_{nome}")
        with c_ant:
            anterior = st.number_input(f"{nome} — Anterior", value=0.0, step=0.1, key=f"anterior_{nome}")

        resultado = classificar_surpresa(real, previsao, maior_favorece)
        linhas.append({
            "Indicador": nome,
            "Real": real,
            "Previsão": previsao,
            "Anterior": anterior,
            "Surpresa vs Previsão": resultado["Surpresa"],
            "Impacto no USD": resultado["Classe"],
            "Pontuação": resultado["Pontuação"],
        })

    df_surpresa = pd.DataFrame(linhas)
    st.dataframe(df_surpresa, use_container_width=True, hide_index=True)
    total = float(df_surpresa["Pontuação"].sum())

    if total >= 3:
        st.success("📈 Conjunto de dados fortemente favorável ao USD")
    elif total >= 1:
        st.success("📈 Conjunto de dados levemente favorável ao USD")
    elif total <= -3:
        st.error("📉 Conjunto de dados fortemente desfavorável ao USD")
    elif total <= -1:
        st.error("📉 Conjunto de dados levemente desfavorável ao USD")
    else:
        st.info("⚪ Surpresas equilibradas")

# =========================================================
# ABA 3 — PARES
# =========================================================
with abas[2]:
    st.subheader("Análise de Par de Moedas")
    moedas = ranking["Código"].tolist()
    c1, c2 = st.columns(2)
    with c1:
        base = st.selectbox("Moeda base", moedas, index=moedas.index("EUR") if "EUR" in moedas else 0)
    with c2:
        cotada = st.selectbox("Moeda cotada", moedas, index=moedas.index("USD") if "USD" in moedas else 1)

    if base == cotada:
        st.warning("Escolha duas moedas diferentes.")
    else:
        score_base = float(ranking.loc[ranking["Código"] == base, "Pontuação_Final"].iloc[0])
        score_cotada = float(ranking.loc[ranking["Código"] == cotada, "Pontuação_Final"].iloc[0])
        confianca, diferenca, status = confianca_modelo(score_base, score_cotada)

        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col1:
            st.metric(base, f"{score_base:.1f}")
        with col2:
            st.subheader(f"{base}/{cotada}")
            st.markdown(f"### {status}")
            st.progress(float(np.clip(confianca, 0, 1)))
            st.markdown(
                f"**Confiança relativa** — {base}: {confianca*100:.0f}% · "
                f"{cotada}: {(1-confianca)*100:.0f}%"
            )
        with col3:
            st.metric(cotada, f"{score_cotada:.1f}")

        st.caption(f"Diferença de força: {diferenca:+.1f} pontos | Sensibilidade: {ESCALA_CONFIANCA:.1f}")

        leitura_par = classificar_par(score_base, score_cotada, base, cotada)
        st.markdown("### 🎯 Conclusão do par")
        if leitura_par["icone"] == "🟢":
            st.success(f"{leitura_par['icone']} **{leitura_par['vies']}** | Confiança macro: **{leitura_par['confianca']}**")
        elif leitura_par["icone"] == "🔴":
            st.error(f"{leitura_par['icone']} **{leitura_par['vies']}** | Confiança macro: **{leitura_par['confianca']}**")
        else:
            st.info(f"{leitura_par['icone']} **{leitura_par['vies']}** | Confiança macro: **{leitura_par['confianca']}**")
        st.write(
            f"Motivo: {base} está com score **{score_base:.1f}** e {cotada} com **{score_cotada:.1f}**, "
            f"uma diferença de **{leitura_par['diferenca']:+.1f} pontos**."
        )
        st.warning("A confiança é uma classificação do modelo, não uma probabilidade estatística comprovada. Valide no teste histórico.")

        st.markdown("#### 📝 Registrar sinal para teste histórico")
        preco = st.number_input(
            "Preço de entrada",
            min_value=0.00001,
            max_value=1000.0,
            value=1.10000,
            step=0.00001,
            format="%.5f",
        )
        horizonte = st.selectbox("Tempo para avaliar (horas)", [1, 4, 8, 24, 48, 72], 3)

        if st.button("Registrar sinal"):
            registrar_sinal(f"{base}/{cotada}", confianca, score_base, score_cotada, preco, horizonte)
            st.success("✅ Sinal registrado!")

# =========================================================
# ABA 4 — FED E NOTÍCIAS
# =========================================================
with abas[3]:
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
with abas[4]:
    st.subheader("Histórico das classificações")
    st.caption("No Streamlit Community Cloud, arquivos locais podem desaparecer após reinicialização ou novo deploy. Para histórico permanente, use um banco externo.")
    historico = carregar_snapshots()
    if historico.empty:
        st.info("Ainda não há histórico. Salve um registro na aba 🏆 Classificação.")
    else:
        st.dataframe(historico.sort_values("data", ascending=False), use_container_width=True)

# =========================================================
# ABA 6 — TESTE HISTÓRICO
# =========================================================
with abas[5]:
    st.subheader("📈 Teste Histórico — Validação do Modelo")
    sinais = carregar_sinais()

    if sinais.empty:
        st.info("Nenhum sinal registrado. Registre sinais na aba 💱 Pares e Confiança.")
    else:
        st.dataframe(sinais.sort_values("data", ascending=False), use_container_width=True)

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
