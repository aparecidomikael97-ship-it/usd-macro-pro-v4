"""AtlasQuant Operational Backtest Panel V1.

Offline Streamlit adapter for TradingView/exported OHLC + explicit signal plans.
Opening the panel performs no provider/API calls. It never invents entry, stop
or target; missing/invalid plans are shown as NO_TRADE.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
import csv
import io

import pandas as pd
import streamlit as st

from atlasquant_operational_backtest import (
    backtest_many,
    ledger_frame,
    summarize_by,
    summarize_results,
)


CANDLE_ALIASES = {
    "datetime": ("datetime", "time", "timestamp", "date", "data", "hora"),
    "open": ("open", "abertura"),
    "high": ("high", "max", "máxima", "maxima"),
    "low": ("low", "min", "mínima", "minima"),
    "close": ("close", "fechamento"),
}

SIGNAL_ALIASES = {
    "signal_time": ("signal_time", "time", "timestamp", "datetime", "data_hora", "datahora", "data"),
    "pair": ("pair", "par", "asset", "ativo", "symbol", "ticker"),
    "setup": ("setup", "operacional", "strategy", "estrategia", "estratégia"),
    "session": ("session", "sessao", "sessão"),
    "side": ("side", "direcao", "direção", "direction", "lado"),
    "entry": ("entry", "entrada", "entry_price", "preco_entrada", "preço_entrada"),
    "stop": ("stop", "sl", "stop_loss", "stoploss"),
    "target": ("target", "tp", "take_profit", "takeprofit", "alvo"),
    "source": ("source", "fonte"),
    "notes": ("notes", "observacoes", "observações", "obs"),
}


def _norm_name(value: Any) -> str:
    return str(value or "").strip().lower()


def _rename_aliases(df: pd.DataFrame, aliases: dict[str, tuple[str, ...]]) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = df.copy()
    by_norm = {_norm_name(c): c for c in out.columns}
    rename = {}
    for canonical, names in aliases.items():
        if canonical in out.columns:
            continue
        for alias in names:
            actual = by_norm.get(_norm_name(alias))
            if actual is not None:
                rename[actual] = canonical
                break
    return out.rename(columns=rename)


def read_csv_bytes(raw: bytes | bytearray | memoryview | None) -> pd.DataFrame:
    if raw is None:
        return pd.DataFrame()
    data = bytes(raw)
    if not data:
        return pd.DataFrame()
    errors = []
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(BytesIO(data), encoding=encoding)
        except Exception as exc:
            errors.append(type(exc).__name__)
    raise ValueError("CSV inválido ou não suportado: " + ", ".join(errors))


def normalize_tradingview_candles(df: pd.DataFrame) -> pd.DataFrame:
    out = _rename_aliases(df, CANDLE_ALIASES)
    required = ["datetime", "open", "high", "low", "close"]
    if not all(c in out.columns for c in required):
        return pd.DataFrame(columns=required)
    out = out[required].copy()
    out["datetime"] = pd.to_datetime(out["datetime"], utc=True, errors="coerce")
    for c in ("open", "high", "low", "close"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=required).sort_values("datetime")
    return out.drop_duplicates(subset=["datetime"], keep="last").reset_index(drop=True)


def normalize_signal_sheet(df: pd.DataFrame, default_pair: str = "") -> pd.DataFrame:
    out = _rename_aliases(df, SIGNAL_ALIASES)
    required = ["signal_time", "side", "entry", "stop", "target"]
    if not all(c in out.columns for c in required):
        return pd.DataFrame(columns=required + ["pair", "setup", "session", "source", "notes"])

    if "pair" not in out.columns:
        out["pair"] = str(default_pair or "").strip().upper()
    else:
        out["pair"] = out["pair"].fillna("").astype(str).str.strip().str.upper()
        if default_pair:
            out.loc[out["pair"].eq(""), "pair"] = str(default_pair).strip().upper()

    for c in ("setup", "session", "source", "notes"):
        if c not in out.columns:
            out[c] = ""

    out["signal_time"] = pd.to_datetime(out["signal_time"], utc=True, errors="coerce")
    out["side"] = out["side"].astype(str).str.strip().str.upper()
    side_map = {
        "COMPRA": "BUY",
        "LONG": "BUY",
        "ALTA": "BUY",
        "VENDA": "SELL",
        "SHORT": "SELL",
        "BAIXA": "SELL",
    }
    out["side"] = out["side"].replace(side_map)
    for c in ("entry", "stop", "target"):
        out[c] = pd.to_numeric(out[c], errors="coerce")

    cols = ["signal_time", "pair", "setup", "session", "side", "entry", "stop", "target", "source", "notes"]
    return out.reindex(columns=cols)


def signal_template_csv() -> str:
    fields = ["signal_time", "pair", "setup", "session", "side", "entry", "stop", "target", "source", "notes"]
    buf = io.StringIO()
    csv.writer(buf).writerow(fields)
    return buf.getvalue()


def candles_template_csv() -> str:
    buf = io.StringIO()
    csv.writer(buf).writerow(["datetime", "open", "high", "low", "close"])
    return buf.getvalue()


def load_tradingview_pine_asset() -> str:
    path = Path(__file__).resolve().parent / "tradingview" / "atlasquant_bos_choch_ob_strategy_v1.pine"
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    rows = []
    for raw in df.to_dict("records"):
        row = dict(raw)
        if pd.notna(row.get("signal_time")):
            row["signal_time"] = pd.Timestamp(row["signal_time"]).isoformat()
        rows.append(row)
    return rows


def render_operational_backtest_panel() -> dict[str, Any]:
    st.markdown("### 🧪 Backtest Operacional — TradingView → AtlasQuant")
    st.caption(
        "Importe candles OHLC exportados do TradingView e uma planilha de sinais com "
        "entrada/stop/alvo explícitos. O AtlasQuant mede Gain/Loss/BE, R, drawdown, "
        "sequências, setup e sessão. Não cria níveis que não existam na planilha."
    )

    c1, c2 = st.columns(2)
    with c1:
        candle_file = st.file_uploader(
            "1) Candles do TradingView (CSV)",
            type=["csv"],
            key="atlasquant_bt_candles_csv",
        )
        st.download_button(
            "⬇️ Modelo CSV de candles",
            data=candles_template_csv(),
            file_name="atlasquant_candles_template.csv",
            mime="text/csv",
            key="atlasquant_bt_candles_template",
        )
    with c2:
        signal_file = st.file_uploader(
            "2) Planilha de sinais/operacionais (CSV)",
            type=["csv"],
            key="atlasquant_bt_signals_csv",
        )
        st.download_button(
            "⬇️ Modelo da planilha de operações",
            data=signal_template_csv(),
            file_name="atlasquant_operacionais_template.csv",
            mime="text/csv",
            key="atlasquant_bt_signals_template",
        )

    pine_asset = load_tradingview_pine_asset()
    st.markdown("#### Pine Script — BOS/CHOCH + Order Block")
    st.caption(
        "Estratégia técnica de pesquisa para o Strategy Tester do TradingView. "
        "Não inclui macro/Fed e não altera o Gate do AtlasQuant."
    )
    st.download_button(
        "⬇️ Baixar Pine Strategy BOS/CHOCH + OB",
        data=pine_asset,
        file_name="atlasquant_bos_choch_ob_strategy_v1.pine",
        mime="text/plain",
        disabled=not bool(pine_asset),
        key="atlasquant_bt_pine_bos_choch_ob",
    )

    default_pair = st.text_input(
        "Par/ativo dos candles (usado apenas se a planilha não tiver a coluna par)",
        value="EUR/USD",
        key="atlasquant_bt_default_pair",
    ).strip().upper()

    a, b, c = st.columns(3)
    with a:
        max_wait = st.number_input("Máx. candles para entrada", min_value=1, max_value=100, value=8, step=1)
    with b:
        max_hold = st.number_input("Máx. candles em posição", min_value=1, max_value=1000, value=96, step=1)
    with c:
        cost_r = st.number_input(
            "Custos totais por trade (R)",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.01,
            format="%.2f",
        )

    if candle_file is None or signal_file is None:
        st.info("Envie os dois CSVs para executar o backtest. Abrir esta tela não consome API.")
        return {"status": "WAITING_FILES"}

    try:
        raw_candles = read_csv_bytes(candle_file.getvalue())
        raw_signals = read_csv_bytes(signal_file.getvalue())
    except Exception as exc:
        st.error(f"Não foi possível ler o CSV: {type(exc).__name__}: {exc}")
        return {"status": "INVALID_CSV"}

    candles = normalize_tradingview_candles(raw_candles)
    signals = normalize_signal_sheet(raw_signals, default_pair=default_pair)
    if candles.empty:
        st.error("CSV de candles sem datetime/open/high/low/close válidos.")
        return {"status": "INVALID_CANDLES"}
    if signals.empty:
        st.error("Planilha de sinais sem signal_time/side/entry/stop/target válidos.")
        return {"status": "INVALID_SIGNALS"}

    unique_pairs = sorted({str(x).strip().upper() for x in signals["pair"].tolist() if str(x).strip()})
    if len(unique_pairs) != 1:
        st.error(
            "Nesta etapa, cada arquivo de candles deve corresponder a um único par. "
            "Separe a planilha por par antes de rodar."
        )
        return {"status": "MULTI_PAIR_NOT_SUPPORTED", "pairs": unique_pairs}
    pair = unique_pairs[0]

    st.caption(
        f"Pronto para testar {len(signals)} sinal(is) em {len(candles)} candle(s) de {pair}. "
        "O candle do sinal não é usado para executar a entrada (proteção anti-look-ahead)."
    )

    if not st.button("▶️ Rodar backtest operacional", type="primary", key="atlasquant_bt_run"):
        return {"status": "READY", "pair": pair, "signals": len(signals), "candles": len(candles)}

    results = backtest_many(
        {pair: candles},
        _records(signals),
        max_wait_bars=int(max_wait),
        max_hold_bars=int(max_hold),
        cost_r=float(cost_r),
        start_after_signal_bar=True,
    )
    metrics = summarize_results(results)
    ledger = ledger_frame(results)

    st.markdown("#### Resultado")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Trades", metrics["trades"])
    m2.metric("Gain", metrics["gains"])
    m3.metric("Loss", metrics["losses"])
    m4.metric("BE", metrics["breakeven"])
    win = metrics["win_rate_pct"]
    m5.metric("Win Rate", "—" if win is None else f"{win:.1f}%")

    n1, n2, n3, n4 = st.columns(4)
    n1.metric("Resultado", f"{metrics['net_r']:+.2f}R")
    n2.metric("Expectativa", "—" if metrics["expectancy_r"] is None else f"{metrics['expectancy_r']:+.2f}R")
    n3.metric("Drawdown máx.", f"{metrics['max_drawdown_r']:.2f}R")
    n4.metric("Maior seq. Loss", metrics["max_loss_streak"])

    if metrics["ambiguous_same_bar"]:
        st.warning(
            f"{metrics['ambiguous_same_bar']} trade(s) tocaram stop e alvo no mesmo candle OHLC. "
            "O motor marcou LOSS por segurança porque a ordem intrabar é desconhecida."
        )

    st.markdown("#### Diário completo")
    st.dataframe(ledger, use_container_width=True, hide_index=True)

    csv_data = ledger.to_csv(index=False)
    st.download_button(
        "📥 Baixar planilha completa do backtest (CSV)",
        data=csv_data,
        file_name=f"atlasquant_backtest_{pair.replace('/','_')}.csv",
        mime="text/csv",
        key="atlasquant_bt_export_ledger",
    )

    if "setup" in ledger.columns:
        by_setup = summarize_by(results, "setup")
        st.markdown("#### Por operacional/setup")
        st.dataframe(by_setup, use_container_width=True, hide_index=True)
    if "session" in ledger.columns:
        by_session = summarize_by(results, "session")
        st.markdown("#### Por sessão")
        st.dataframe(by_session, use_container_width=True, hide_index=True)

    st.caption(
        "Backtest histórico não garante resultado futuro. Esta tela mede apenas as regras "
        "e níveis fornecidos, com política conservadora para ambiguidades OHLC."
    )
    return {"status": "DONE", "metrics": metrics, "rows": results}
