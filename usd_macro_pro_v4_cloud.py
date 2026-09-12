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

APP_VERSION = "6.6.2 — EXPECTATIVA INTEGRADA AO PAR"
HIST_SCORES = "historico_scores_v5.parquet"
HIST_SINAIS = "historico_sinais_v5.parquet"

st.set_page_config(
    page_title="USD Macro Pro — V6.6.2 Português",
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


def _mostrar_expectativa_v66():
    st.subheader("🔮 Expectativa do Mercado — V6.6.2")
    st.caption(
        "Antes da divulgação: compara PREVISÃO/CONSENSO com o ANTERIOR. "
        "Depois da divulgação, a seção de Surpresa Econômica compara REAL com PREVISÃO."
    )
    st.info(
        "A previsão continua manual: digite o consenso do seu calendário econômico. "
        "O painel não inventa forecast quando a fonte oficial não fornece consenso."
    )

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
        # Reutiliza exatamente os mesmos campos da seção de surpresa.
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
            tem = st.checkbox("Usar", key=flag_key, help=f"Marque quando tiver o consenso de {nome}.")
        step = 1.0 if nome == "Payroll" else 0.1
        with c1:
            previsao = st.number_input(
                f"{nome} — Consenso",
                step=step, key=prev_key,
                help="Consenso/forecast publicado por uma fonte de calendário econômico."
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
    st.dataframe(tabela, use_container_width=True, hide_index=True)

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
        "Importante: expectativa não altera o score macro realizado. "
        "Ela mostra o que o mercado espera antes do dado; o REAL × CONSENSO é que gera surpresa após o release."
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

st.title("🦅 USD Macro Pro — V6.6.2 Português")
st.caption("Dados econômicos → Calendário → Inflação → Fed → Força das moedas → Pares → Teste histórico")

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
        st.dataframe(auditoria_df, use_container_width=True, hide_index=True)
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
        st.dataframe(cal, use_container_width=True, hide_index=True)
    st.info("ℹ️ A FRED fornece dados realizados e datas de releases, mas não fornece o consenso/forecast do mercado. Por segurança, a previsão continua manual.")

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
    st.dataframe(pd.DataFrame(auto_rows), use_container_width=True, hide_index=True)

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
    st.dataframe(df_surpresa, use_container_width=True, hide_index=True)

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
    st.markdown("### 📅 Calendário + Risco e Timing — V6.6.2")
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
                use_container_width=True, hide_index=True
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
        "Consenso/forecast continua separado porque essas fontes não fornecem consenso de mercado."
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
            "Nenhum evento foi informado nesta avaliação. O timing não recebeu penalidade de calendário."
        )

    st.markdown(
        "**Fluxo recomendado pelo painel:** Macro → risco de notícia → estrutura/preço → gestão de risco."
    )
    st.caption(
        "Timing macro não significa 'entrar agora'. O sistema não observa aqui spread da corretora, "
        "liquidez instantânea, slippage ou estrutura técnica do gráfico."
    )



def _mostrar_expectativa_no_par_v662(base: str, cotada: str):
    """
    Exibe no painel do par a expectativa pré-release já calculada no Painel EUA.
    Não soma o consenso ao score macro e evita dupla contagem.
    """
    st.markdown("### 🔮 Expectativa do Mercado — Pré-release")

    exp_score = float(st.session_state.get("v66_expectativa_score", 50.0))
    exp_leitura = str(
        st.session_state.get(
            "v66_expectativa_leitura",
            "⚪ Sem consensos preenchidos"
        )
    )

    tem_consenso = any(
        bool(st.session_state.get(f"v66_consenso_{nome}", False))
        for nome in [
            "IPC anual", "IPC Núcleo anual", "PCE anual", "PCE Núcleo anual",
            "Payroll", "Desemprego", "ISM Industrial", "ISM Serviços"
        ]
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Expectativa USD", f"{exp_score:.0f}/100" if tem_consenso else "—")
    c2.metric("Estado", "Preenchida" if tem_consenso else "Sem consenso")
    c3.metric("Uso no score", "Informativo")

    if not tem_consenso:
        st.info(
            "Nenhum consenso pré-release foi preenchido. "
            "Preencha a seção 🔮 Expectativa do Mercado no Painel EUA."
        )
    else:
        if exp_score >= 60:
            st.success(f"**{exp_leitura}**")
        elif exp_score <= 40:
            st.error(f"**{exp_leitura}**")
        else:
            st.info(f"**{exp_leitura}**")

        # Traduz expectativa USD para o sentido do par sem transformá-la em sinal.
        if base == "USD":
            if exp_score >= 60:
                leitura_par = f"Expectativa do USD tende a confirmar **COMPRA {base}/{cotada}**."
            elif exp_score <= 40:
                leitura_par = f"Expectativa do USD tende a contrariar **COMPRA {base}/{cotada}**."
            else:
                leitura_par = "Expectativa pré-release está neutra/mista para o USD."
        elif cotada == "USD":
            if exp_score >= 60:
                leitura_par = f"Expectativa do USD tende a confirmar **VENDA {base}/{cotada}**."
            elif exp_score <= 40:
                leitura_par = f"Expectativa do USD tende a contrariar **VENDA {base}/{cotada}**."
            else:
                leitura_par = "Expectativa pré-release está neutra/mista para o USD."
        else:
            leitura_par = "Este resumo de expectativa é específico para o USD."

        st.write(leitura_par)

    st.caption(
        "Pré-release = consenso × anterior. É contexto, não surpresa realizada. "
        "Por isso NÃO é somado novamente ao score macro nem à confluência."
    )


# =========================================================
# ABA 3 — PARES
# =========================================================
with abas[2]:
    st.subheader("💱 Painel de Decisão — V6.6.2")

    usd_base = float(usd_detalhado["score"])
    usd_ajustado = float(st.session_state.get("usd_score_ajustado_surpresas", usd_base))
    ajuste = float(st.session_state.get("usd_ajuste_surpresas", 0.0))
    confirmacao = st.session_state.get("usd_confirmacao_surpresas", "Sem previsões preenchidas")

    c1, c2, c3 = st.columns(3)
    c1.metric("USD macro base", f"{usd_base:.0f}/100")
    c2.metric("Ajuste das surpresas", f"{ajuste:+.1f}")
    c3.metric("USD usado nos pares", f"{usd_ajustado:.0f}/100")
    st.caption(f"Leitura das surpresas: {confirmacao}")

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
        st.dataframe(pd.DataFrame(detalhes), use_container_width=True, hide_index=True)

        dt = confl["diferencial_taxas"]
        mercado3m = confl["mercado_3m"]
        tend = confl["tendencias"]
        st.markdown("#### 📐 Qualidade macro da V6.6.2")
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
                    "A V6.6.2 reduz automaticamente o peso desse componente até a FRED atualizar."
                )
        else:
            st.warning(
                "⚠️ Spread de mercado 3M indisponível para este par. "
                "A confluência continua usando juros oficiais e os demais componentes."
            )

        st.caption(
            "Na V6.6.2, 'mercado 3M' é uma comparação de taxas de 3 meses/90 dias "
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
            st.dataframe(pd.DataFrame(trend_rows), use_container_width=True, hide_index=True)
            st.caption("A V6.6.2 combina diferencial de juros oficiais, spread de mercado e direção do spread com pesos ajustados pelo frescor dos dados. O Treasury 2Y permanece como tendência dos EUA, sem ser comparado diretamente a uma maturidade estrangeira diferente.")

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

        st.markdown("### 🧭 Decisão V6.6.2")
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

        _mostrar_expectativa_no_par_v662(base, cotada)

        _mostrar_risco_timing_v65(confl, diferenca)

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
    st.markdown("### 🏆 Matriz Inteligente — V6.6.2")
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

    st.dataframe(
        matriz_v61,
        use_container_width=True,
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
