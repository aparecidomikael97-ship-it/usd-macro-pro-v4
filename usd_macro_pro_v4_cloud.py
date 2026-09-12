#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🦅 USD Macro Pro — V5 PORTUGUÊS
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

# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

APP_VERSION = "5.0 — PORTUGUÊS"
HIST_SCORES = "historico_scores_v5.parquet"
HIST_SINAIS = "historico_sinais_v5.parquet"

st.set_page_config(
    page_title="USD Macro Pro — V5 Português",
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
    "higher for longer", "inflation remains elevated", "rate hike", "hike",
    "tightening", "restrictive", "not ready to cut", "strong economy"
)
PALAVRAS_FLEXIVEIS = (
    "rate cut", "easing", "disinflation", "inflation cooling",
    "weaker labor", "growth slowing", "lower rates"
)
POSITIVAS = ("strong", "growth", "beat", "surge", "rise", "gain", "alta", "avanço")
NEGATIVAS = ("weak", "recession", "drop", "fall", "selloff", "queda", "crise")


def _rss_titulos(consulta: str, idioma="en-US", pais="US", ceid="US:en") -> list[str]:
    q = urllib.parse.quote(consulta)
    url = f"https://news.google.com/rss/search?q={q}&hl={idioma}&gl={pais}&ceid={ceid}"
    resposta = _get(url)
    if resposta is None:
        return []
    try:
        raiz = ET.fromstring(resposta.content)
        return [
            item.findtext("title", "").strip()
            for item in raiz.iter("item")
            if item.findtext("title", "")
        ]
    except Exception:
        return []


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
    titulos = _rss_titulos("Federal Reserve OR FOMC OR Powell when:7d")
    forca = _score_palavras(titulos, PALAVRAS_RESTRITIVAS, PALAVRAS_FLEXIVEIS)
    tom = "Restritivo" if forca > 0.15 else "Flexível" if forca < -0.15 else "Neutro"
    STATUS_FONTE["Fed"] = "✅ Notícias RSS" if titulos else "⚠️ Sem manchetes"
    return {"tom": tom, "forca": forca, "titulos": titulos[:12]}


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


def score_atividade_usd(_: dict) -> float:
    # Neutro até o usuário preencher ISM/PMI na área de surpresa econômica.
    return 50.0


def calcular_ranking(dados: dict, macro_us: dict, fed: dict) -> pd.DataFrame:
    df = pd.DataFrame(dados).T.reset_index().rename(columns={"index": "Código"})
    df["Moeda"] = df["Código"].map(MOEDAS)

    df["n_juros"] = normalizar(df["juros"])
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
    df = df.sort_values("Pontuação_Final", ascending=False).reset_index(drop=True)
    df["Posição"] = df.index + 1

    for coluna in ["juros", "inflacao", "pib", "sentimento", "Pontuação_Macro", "Influência_Fed", "Pontuação_Final"]:
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

st.title("🦅 USD Macro Pro — V5 Português")
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
        "Pontuação_Final", "juros", "inflacao", "pib", "sentimento", "fonte"
    ]].copy()
    tabela.columns = [
        "#", "Código", "Moeda", "Pontuação Macro", "Fed", "Pontuação Final",
        "Juros %", "Inflação anual %", "PIB real anual %",
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
            tabela[["Código", "Juros %", "Inflação anual %", "PIB real anual %", "Fonte"]],
            use_container_width=True,
            hide_index=True,
        )

    if st.button("💾 Salvar registro da classificação"):
        st.toast(salvar_snapshot(ranking))

# =========================================================
# ABA 2 — EUA
# =========================================================
with abas[1]:
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
        st.warning("A confiança é uma pontuação do modelo, não uma probabilidade estatística comprovada. Valide no teste histórico.")

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
    st.subheader("Leitura do Federal Reserve")
    st.metric("Tom do Fed", fed["tom"])
    st.metric("Intensidade da leitura", f"{fed['forca']:+.2f}")

    st.markdown("### Manchetes analisadas")
    if fed["titulos"]:
        for titulo in fed["titulos"]:
            st.write("•", titulo)
    else:
        st.info("Nenhuma manchete encontrada nesta atualização.")

    st.markdown("---")
    st.markdown(
        "**🔴 Restritivo** → inflação/economia fortes → juros altos por mais tempo → tende a favorecer o USD  \n"
        "**🟢 Flexível** → inflação cedendo/economia fraca → maior chance de cortes → tende a pressionar o USD  \n"
        "⚠️ Esta leitura de manchetes é auxiliar. Confirme sempre com comunicado, ata e discursos oficiais do Fed."
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
