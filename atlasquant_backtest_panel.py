"""AtlasQuant Operational Backtest Panel V1.1.

Offline Streamlit adapter for TradingView/exported OHLC. It supports explicit
signal plans and an objective BOS/CHOCH + Order Block historical replay.
Opening the panel performs no provider/API calls.
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
from atlasquant_strategy_replay import generate_bos_choch_ob_signals
from atlasquant_fvg_replay import generate_fvg_signals
from atlasquant_ote_replay import generate_ote_signals
from atlasquant_crt_replay import generate_crt_signals
from atlasquant_amd_replay import generate_amd_signals
from atlasquant_strategy_comparator import (
    run_strategy_suite,
    comparison_frame,
    breakdown_frame,
    combined_ledger,
)
from atlasquant_strategy_stability import temporal_stability_report
from atlasquant_strategy_walkforward import walk_forward_report
from atlasquant_strategy_friction import friction_sensitivity_report
from atlasquant_strategy_parameter_robustness import parameter_robustness_report
from atlasquant_backtest_evidence import (
    consolidated_evidence_frame,
    build_evidence_bundle,
    evidence_bundle_json,
    evidence_markdown,
)
from atlasquant_tradingview_parity import validate_tradingview_parity


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


def _load_pine_file(filename: str) -> str:
    path = Path(__file__).resolve().parent / "tradingview" / filename
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def load_tradingview_pine_asset() -> str:
    return _load_pine_file("atlasquant_bos_choch_ob_strategy_v1.pine")


def load_tradingview_fvg_pine_asset() -> str:
    return _load_pine_file("atlasquant_fvg_strategy_v1.pine")


def load_tradingview_ote_pine_asset() -> str:
    return _load_pine_file("atlasquant_ote_strategy_v1.pine")


def load_tradingview_crt_pine_asset() -> str:
    return _load_pine_file("atlasquant_crt_strategy_v1.pine")


def load_tradingview_amd_pine_asset() -> str:
    return _load_pine_file("atlasquant_amd_strategy_v1.pine")


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


def _render_result_block(
    results: list[dict[str, Any]],
    pair: str,
    *,
    key_suffix: str,
    generated_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
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

    st.download_button(
        "📥 Baixar planilha completa do backtest (CSV)",
        data=ledger.to_csv(index=False),
        file_name=f"atlasquant_backtest_{pair.replace('/','_')}.csv",
        mime="text/csv",
        key=f"atlasquant_bt_export_ledger_{key_suffix}",
    )

    if generated_signals:
        signals_df=pd.DataFrame(generated_signals)
        st.download_button(
            "📥 Baixar sinais gerados pelo replay (CSV)",
            data=signals_df.to_csv(index=False),
            file_name=f"atlasquant_sinais_replay_{pair.replace('/','_')}.csv",
            mime="text/csv",
            key=f"atlasquant_bt_export_signals_{key_suffix}",
        )

    if "setup" in ledger.columns:
        by_setup = summarize_by(results, "setup")
        st.markdown("#### Por operacional/setup")
        st.dataframe(by_setup, use_container_width=True, hide_index=True)
    if "session" in ledger.columns:
        by_session = summarize_by(results, "session")
        st.markdown("#### Por sessão")
        st.dataframe(by_session, use_container_width=True, hide_index=True)

    return {"status": "DONE", "metrics": metrics, "rows": results}


def render_operational_backtest_panel() -> dict[str, Any]:
    st.markdown("### 🧪 Backtest Operacional — TradingView → AtlasQuant")
    st.caption(
        "Importe candles OHLC exportados do TradingView. Você pode usar uma planilha "
        "de sinais explícitos ou deixar o AtlasQuant fazer replay automático do "
        "BOS/CHOCH + Order Block, candle a candle, para pesquisa histórica."
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
    p1,p2,p3,p4,p5=st.columns(5)
    with p1:
        st.download_button(
            "⬇️ Pine BOS/CHOCH + OB",
            data=pine_asset,
            file_name="atlasquant_bos_choch_ob_strategy_v1.pine",
            mime="text/plain",
            disabled=not bool(pine_asset),
            key="atlasquant_bt_pine_bos_choch_ob",
        )
    fvg_pine=load_tradingview_fvg_pine_asset()
    with p2:
        st.download_button(
            "⬇️ Pine FVG",
            data=fvg_pine,
            file_name="atlasquant_fvg_strategy_v1.pine",
            mime="text/plain",
            disabled=not bool(fvg_pine),
            key="atlasquant_bt_pine_fvg",
        )
    ote_pine=load_tradingview_ote_pine_asset()
    with p3:
        st.download_button(
            "⬇️ Pine OTE",
            data=ote_pine,
            file_name="atlasquant_ote_strategy_v1.pine",
            mime="text/plain",
            disabled=not bool(ote_pine),
            key="atlasquant_bt_pine_ote",
        )
    crt_pine=load_tradingview_crt_pine_asset()
    with p4:
        st.download_button(
            "⬇️ Pine CRT",
            data=crt_pine,
            file_name="atlasquant_crt_strategy_v1.pine",
            mime="text/plain",
            disabled=not bool(crt_pine),
            key="atlasquant_bt_pine_crt",
        )
    amd_pine=load_tradingview_amd_pine_asset()
    with p5:
        st.download_button(
            "⬇️ Pine AMD",
            data=amd_pine,
            file_name="atlasquant_amd_strategy_v1.pine",
            mime="text/plain",
            disabled=not bool(amd_pine),
            key="atlasquant_bt_pine_amd",
        )

    parity=validate_tradingview_parity()
    with st.expander("🔎 Paridade TradingView ↔ Python", expanded=False):
        if parity["status"]=="OK":
            st.success(f"Contrato estático OK: {parity['passed']} verificações.")
        else:
            st.error(f"DRIFT detectado: {parity['failed']} verificação(ões) falharam.")
        st.dataframe(pd.DataFrame(parity["checks"]),use_container_width=True,hide_index=True)
        st.caption(" ".join(parity["limitations"]))

    default_pair = st.text_input(
        "Par/ativo dos candles (usado apenas se a planilha não tiver a coluna par)",
        value="EUR/USD",
        key="atlasquant_bt_default_pair",
    ).strip().upper()

    a, b, c, d = st.columns(4)
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
    with d:
        slippage_r = st.number_input(
            "Slippage adverso por trade (R)",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.01,
            format="%.2f",
        )

    with st.expander("🤖 Backtest automático — BOS/CHOCH + Order Block", expanded=True):
        st.caption(
            "Usa somente os candles enviados. O replay percorre o histórico sem ver candles futuros, "
            "gera entrada/stop/alvo por regras fixas de pesquisa e bloqueia sobreposição de posição no mesmo par."
        )
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            auto_rr = st.number_input(
                "Alvo automático (R)", min_value=0.25, max_value=10.0,
                value=2.0, step=0.25, key="atlasquant_auto_rr"
            )
        with ac2:
            auto_buffer = st.number_input(
                "Buffer do stop (ATR)", min_value=0.0, max_value=1.0,
                value=0.05, step=0.01, key="atlasquant_auto_buffer"
            )
        with ac3:
            auto_entry_mode = st.selectbox(
                "Entrada", ["MIDPOINT","PROXIMAL"], key="atlasquant_auto_entry_mode"
            )

        af1, af2 = st.columns(2)
        with af1:
            auto_events = st.multiselect(
                "Eventos", ["BOS","CHOCH"], default=["BOS","CHOCH"],
                key="atlasquant_auto_events"
            )
        with af2:
            auto_sides = st.multiselect(
                "Lados", ["BUY","SELL"], default=["BUY","SELL"],
                key="atlasquant_auto_sides"
            )

        if candle_file is None:
            st.info("Envie o CSV de candles para habilitar o replay automático.")
        else:
            try:
                auto_raw=read_csv_bytes(candle_file.getvalue())
                auto_candles=normalize_tradingview_candles(auto_raw)
            except Exception as exc:
                auto_candles=pd.DataFrame()
                st.error(f"CSV de candles inválido: {type(exc).__name__}: {exc}")

            if not auto_candles.empty:
                auto_signals=generate_bos_choch_ob_signals(
                    auto_candles,
                    pair=default_pair,
                    rr_target=float(auto_rr),
                    stop_buffer_atr=float(auto_buffer),
                    entry_mode=str(auto_entry_mode),
                    allow_bos="BOS" in auto_events,
                    allow_choch="CHOCH" in auto_events,
                    allow_buy="BUY" in auto_sides,
                    allow_sell="SELL" in auto_sides,
                )
                st.caption(
                    f"Replay encontrou {len(auto_signals)} setup(s) objetivo(s) em "
                    f"{len(auto_candles)} candle(s)."
                )
                if st.button(
                    "▶️ Rodar backtest automático",
                    type="primary",
                    key="atlasquant_bt_auto_run",
                    disabled=not bool(auto_signals),
                ):
                    auto_results=backtest_many(
                        {default_pair:auto_candles},
                        auto_signals,
                        single_position_per_pair=True,
                        max_wait_bars=int(max_wait),
                        max_hold_bars=int(max_hold),
                        cost_r=float(cost_r),
                        slippage_r=float(slippage_r),
                        start_after_signal_bar=True,
                    )
                    result=_render_result_block(
                        auto_results,
                        default_pair,
                        key_suffix="auto",
                        generated_signals=auto_signals,
                    )
                    st.caption(
                        "Resultado automático = pesquisa técnica histórica. "
                        "Não inclui macro/Fed e não altera o Gate do AtlasQuant."
                    )
                    return {**result, "mode":"AUTO_REPLAY", "signals":auto_signals}

    with st.expander("🤖 Backtest automático — FVG", expanded=False):
        st.caption(
            "Operacional separado do BOS/CHOCH + OB. Detecta FVG novo de três candles "
            "e mede sua estatística de forma independente."
        )
        fc1,fc2,fc3=st.columns(3)
        with fc1:
            fvg_rr=st.number_input(
                "Alvo FVG (R)",min_value=0.25,max_value=10.0,
                value=2.0,step=0.25,key="atlasquant_fvg_rr"
            )
        with fc2:
            fvg_buffer=st.number_input(
                "Buffer FVG stop (ATR)",min_value=0.0,max_value=1.0,
                value=0.0,step=0.01,key="atlasquant_fvg_buffer"
            )
        with fc3:
            fvg_min_gap=st.number_input(
                "Gap mínimo (ATR)",min_value=0.0,max_value=5.0,
                value=0.0,step=0.05,key="atlasquant_fvg_min_gap"
            )
        ff1,ff2=st.columns(2)
        with ff1:
            fvg_entry_mode=st.selectbox(
                "Entrada FVG",["MIDPOINT","PROXIMAL"],key="atlasquant_fvg_entry_mode"
            )
        with ff2:
            fvg_sides=st.multiselect(
                "Lados FVG",["BUY","SELL"],default=["BUY","SELL"],key="atlasquant_fvg_sides"
            )

        if candle_file is None:
            st.info("Envie o CSV de candles para habilitar o replay FVG.")
        else:
            try:
                fvg_raw=read_csv_bytes(candle_file.getvalue())
                fvg_candles=normalize_tradingview_candles(fvg_raw)
            except Exception as exc:
                fvg_candles=pd.DataFrame()
                st.error(f"CSV de candles inválido: {type(exc).__name__}: {exc}")

            if not fvg_candles.empty:
                fvg_signals=generate_fvg_signals(
                    fvg_candles,
                    pair=default_pair,
                    rr_target=float(fvg_rr),
                    stop_buffer_atr=float(fvg_buffer),
                    min_gap_atr=float(fvg_min_gap),
                    entry_mode=str(fvg_entry_mode),
                    allow_buy="BUY" in fvg_sides,
                    allow_sell="SELL" in fvg_sides,
                )
                st.caption(
                    f"Replay FVG encontrou {len(fvg_signals)} setup(s) em "
                    f"{len(fvg_candles)} candle(s)."
                )
                if st.button(
                    "▶️ Rodar backtest FVG",
                    type="primary",
                    key="atlasquant_bt_fvg_run",
                    disabled=not bool(fvg_signals),
                ):
                    fvg_results=backtest_many(
                        {default_pair:fvg_candles},
                        fvg_signals,
                        single_position_per_pair=True,
                        max_wait_bars=int(max_wait),
                        max_hold_bars=int(max_hold),
                        cost_r=float(cost_r),
                        slippage_r=float(slippage_r),
                        start_after_signal_bar=True,
                    )
                    result=_render_result_block(
                        fvg_results,
                        default_pair,
                        key_suffix="fvg",
                        generated_signals=fvg_signals,
                    )
                    st.caption(
                        "FVG é medido separadamente do BOS/CHOCH + Order Block. "
                        "Não inclui macro/Fed e não altera o Gate."
                    )
                    return {**result,"mode":"AUTO_FVG","signals":fvg_signals}

    with st.expander("🤖 Backtest automático — OTE 62–79%", expanded=False):
        st.caption(
            "Terceiro operacional independente. Ancora impulso objetivo, espera a primeira "
            "entrada na zona OTE e mantém sua estatística separada."
        )
        oc1,oc2,oc3=st.columns(3)
        with oc1:
            ote_rr=st.number_input(
                "Alvo OTE (R)",min_value=0.25,max_value=10.0,
                value=2.0,step=0.25,key="atlasquant_ote_rr"
            )
        with oc2:
            ote_buffer=st.number_input(
                "Buffer OTE stop (ATR)",min_value=0.0,max_value=1.0,
                value=0.05,step=0.01,key="atlasquant_ote_buffer"
            )
        with oc3:
            ote_min_impulse=st.number_input(
                "Impulso mínimo (ATR)",min_value=0.0,max_value=20.0,
                value=0.0,step=0.25,key="atlasquant_ote_min_impulse"
            )
        of1,of2=st.columns(2)
        with of1:
            ote_entry_mode=st.selectbox(
                "Entrada OTE",["SWEET_705","ZONE_MIDPOINT"],key="atlasquant_ote_entry_mode"
            )
        with of2:
            ote_sides=st.multiselect(
                "Lados OTE",["BUY","SELL"],default=["BUY","SELL"],key="atlasquant_ote_sides"
            )

        if candle_file is None:
            st.info("Envie o CSV de candles para habilitar o replay OTE.")
        else:
            try:
                ote_raw=read_csv_bytes(candle_file.getvalue())
                ote_candles=normalize_tradingview_candles(ote_raw)
            except Exception as exc:
                ote_candles=pd.DataFrame()
                st.error(f"CSV de candles inválido: {type(exc).__name__}: {exc}")

            if not ote_candles.empty:
                ote_signals=generate_ote_signals(
                    ote_candles,
                    pair=default_pair,
                    rr_target=float(ote_rr),
                    stop_buffer_atr=float(ote_buffer),
                    entry_mode=str(ote_entry_mode),
                    min_impulse_atr=float(ote_min_impulse),
                    allow_buy="BUY" in ote_sides,
                    allow_sell="SELL" in ote_sides,
                )
                st.caption(
                    f"Replay OTE encontrou {len(ote_signals)} setup(s) em "
                    f"{len(ote_candles)} candle(s)."
                )
                if st.button(
                    "▶️ Rodar backtest OTE",
                    type="primary",
                    key="atlasquant_bt_ote_run",
                    disabled=not bool(ote_signals),
                ):
                    ote_results=backtest_many(
                        {default_pair:ote_candles},
                        ote_signals,
                        single_position_per_pair=True,
                        max_wait_bars=int(max_wait),
                        max_hold_bars=int(max_hold),
                        cost_r=float(cost_r),
                        slippage_r=float(slippage_r),
                        start_after_signal_bar=True,
                    )
                    result=_render_result_block(
                        ote_results,
                        default_pair,
                        key_suffix="ote",
                        generated_signals=ote_signals,
                    )
                    st.caption(
                        "OTE é medido separadamente de FVG e BOS/CHOCH + Order Block. "
                        "Não inclui macro/Fed e não altera o Gate."
                    )
                    return {**result,"mode":"AUTO_OTE","signals":ote_signals}

    with st.expander("🤖 Backtest automático — CRT", expanded=False):
        st.caption(
            "Quarto operacional independente. Usa anchor range → raid/reclaim → delivery "
            "e mantém resultado separado dos demais setups."
        )
        cc1,cc2=st.columns(2)
        with cc1:
            crt_buffer=st.number_input(
                "Buffer CRT stop (ATR)",min_value=0.0,max_value=1.0,
                value=0.0,step=0.01,key="atlasquant_crt_buffer"
            )
        with cc2:
            crt_min_rr=st.number_input(
                "RR mínimo CRT",min_value=0.0,max_value=20.0,
                value=0.0,step=0.25,key="atlasquant_crt_min_rr"
            )
        crt_sides=st.multiselect(
            "Lados CRT",["BUY","SELL"],default=["BUY","SELL"],key="atlasquant_crt_sides"
        )

        if candle_file is None:
            st.info("Envie o CSV de candles para habilitar o replay CRT.")
        else:
            try:
                crt_raw=read_csv_bytes(candle_file.getvalue())
                crt_candles=normalize_tradingview_candles(crt_raw)
            except Exception as exc:
                crt_candles=pd.DataFrame()
                st.error(f"CSV de candles inválido: {type(exc).__name__}: {exc}")

            if not crt_candles.empty:
                crt_signals=generate_crt_signals(
                    crt_candles,
                    pair=default_pair,
                    stop_buffer_atr=float(crt_buffer),
                    min_rr=float(crt_min_rr),
                    allow_buy="BUY" in crt_sides,
                    allow_sell="SELL" in crt_sides,
                )
                st.caption(
                    f"Replay CRT encontrou {len(crt_signals)} setup(s) em "
                    f"{len(crt_candles)} candle(s)."
                )
                if st.button(
                    "▶️ Rodar backtest CRT",
                    type="primary",
                    key="atlasquant_bt_crt_run",
                    disabled=not bool(crt_signals),
                ):
                    crt_results=backtest_many(
                        {default_pair:crt_candles},
                        crt_signals,
                        single_position_per_pair=True,
                        max_wait_bars=int(max_wait),
                        max_hold_bars=int(max_hold),
                        cost_r=float(cost_r),
                        slippage_r=float(slippage_r),
                        start_after_signal_bar=True,
                    )
                    result=_render_result_block(
                        crt_results,
                        default_pair,
                        key_suffix="crt",
                        generated_signals=crt_signals,
                    )
                    st.caption(
                        "CRT é medido separadamente de OTE, FVG e BOS/CHOCH + OB. "
                        "Não inclui macro/Fed e não altera o Gate."
                    )
                    return {**result,"mode":"AUTO_CRT","signals":crt_signals}

    with st.expander("🤖 Backtest automático — AMD / Power of Three", expanded=False):
        st.caption(
            "Quinto operacional independente. Usa máquina de estados temporal "
            "Acumulação → Manipulação → Distribuição, sem misturar estatísticas."
        )
        ac1,ac2,ac3=st.columns(3)
        with ac1:
            amd_acc_bars=st.number_input(
                "Candles de acumulação",min_value=4,max_value=50,
                value=8,step=1,key="atlasquant_amd_acc_bars"
            )
        with ac2:
            amd_max_dist=st.number_input(
                "Máx. candles até distribuição",min_value=1,max_value=20,
                value=4,step=1,key="atlasquant_amd_max_dist"
            )
        with ac3:
            amd_buffer=st.number_input(
                "Buffer AMD stop (ATR)",min_value=0.0,max_value=1.0,
                value=0.0,step=0.01,key="atlasquant_amd_buffer"
            )
        ad1,ad2=st.columns(2)
        with ad1:
            amd_min_rr=st.number_input(
                "RR mínimo AMD",min_value=0.0,max_value=20.0,
                value=0.0,step=0.25,key="atlasquant_amd_min_rr"
            )
        with ad2:
            amd_sides=st.multiselect(
                "Lados AMD",["BUY","SELL"],default=["BUY","SELL"],key="atlasquant_amd_sides"
            )

        if candle_file is None:
            st.info("Envie o CSV de candles para habilitar o replay AMD.")
        else:
            try:
                amd_raw=read_csv_bytes(candle_file.getvalue())
                amd_candles=normalize_tradingview_candles(amd_raw)
            except Exception as exc:
                amd_candles=pd.DataFrame()
                st.error(f"CSV de candles inválido: {type(exc).__name__}: {exc}")

            if not amd_candles.empty:
                amd_signals=generate_amd_signals(
                    amd_candles,
                    pair=default_pair,
                    accumulation_bars=int(amd_acc_bars),
                    max_distribution_bars=int(amd_max_dist),
                    stop_buffer_atr=float(amd_buffer),
                    min_rr=float(amd_min_rr),
                    allow_buy="BUY" in amd_sides,
                    allow_sell="SELL" in amd_sides,
                )
                st.caption(
                    f"Replay AMD encontrou {len(amd_signals)} setup(s) em "
                    f"{len(amd_candles)} candle(s)."
                )
                if st.button(
                    "▶️ Rodar backtest AMD",
                    type="primary",
                    key="atlasquant_bt_amd_run",
                    disabled=not bool(amd_signals),
                ):
                    amd_results=backtest_many(
                        {default_pair:amd_candles},
                        amd_signals,
                        single_position_per_pair=True,
                        max_wait_bars=int(max_wait),
                        max_hold_bars=int(max_hold),
                        cost_r=float(cost_r),
                        slippage_r=float(slippage_r),
                        start_after_signal_bar=True,
                    )
                    result=_render_result_block(
                        amd_results,
                        default_pair,
                        key_suffix="amd",
                        generated_signals=amd_signals,
                    )
                    st.caption(
                        "AMD/PO3 é medido separadamente de CRT, OTE, FVG e BOS/CHOCH + OB. "
                        "Não inclui macro/Fed e não altera o Gate."
                    )
                    return {**result,"mode":"AUTO_AMD","signals":amd_signals}

    with st.expander("📊 Comparador dos 5 operacionais", expanded=True):
        st.caption(
            "Roda BOS/CHOCH+OB, FVG, OTE, CRT e AMD separadamente sobre o mesmo CSV "
            "com os defaults de pesquisa. Não mistura sinais e não altera o Gate."
        )
        sc1,sc2,sc3=st.columns(3)
        with sc1:
            min_rank_trades=st.number_input(
                "Mínimo de trades para ranking observado",
                min_value=5,max_value=500,value=20,step=5,
                key="atlasquant_compare_min_rank_trades",
            )
        with sc2:
            stability_folds=st.selectbox(
                "Blocos temporais",
                [3,4,5],
                index=0,
                key="atlasquant_compare_stability_folds",
            )
        with sc3:
            min_fold_trades=st.number_input(
                "Mínimo de trades por bloco",
                min_value=2,max_value=100,value=5,step=1,
                key="atlasquant_compare_min_fold_trades",
            )

        wf1,wf2,wf3,wf4=st.columns(4)
        with wf1:
            wf_train_pct=st.selectbox(
                "Treino inicial walk-forward",
                [50,60,70],
                index=1,
                format_func=lambda x:f"{x}%",
                key="atlasquant_compare_wf_train_pct",
            )
        with wf2:
            wf_windows=st.selectbox(
                "Janelas OOS",
                [2,3,4],
                index=1,
                key="atlasquant_compare_wf_windows",
            )
        with wf3:
            wf_min_train=st.number_input(
                "Mín. trades treino",
                min_value=5,max_value=500,value=20,step=5,
                key="atlasquant_compare_wf_min_train",
            )
        with wf4:
            wf_min_test=st.number_input(
                "Mín. trades teste",
                min_value=2,max_value=100,value=5,step=1,
                key="atlasquant_compare_wf_min_test",
            )

        fr1,fr2=st.columns(2)
        with fr1:
            friction_min_trades=st.number_input(
                "Mínimo de trades para teste de custos",
                min_value=5,max_value=500,value=20,step=5,
                key="atlasquant_compare_friction_min_trades",
            )
        with fr2:
            friction_slippage_levels=st.multiselect(
                "Stress adicional de slippage (R)",
                [0.0,0.01,0.02,0.05,0.10,0.20,0.30],
                default=[0.0,0.02,0.05,0.10],
                key="atlasquant_compare_friction_slippage_levels",
            )

        pr1,pr2=st.columns(2)
        with pr1:
            include_param_robustness=st.checkbox(
                "Incluir robustez de parâmetros pré-definidos",
                value=False,
                key="atlasquant_compare_include_param_robustness",
            )
        with pr2:
            param_min_trades=st.number_input(
                "Mínimo de trades por variante",
                min_value=5,max_value=500,value=20,step=5,
                key="atlasquant_compare_param_min_trades",
                disabled=not include_param_robustness,
            )

        if candle_file is None:
            st.info("Envie o CSV de candles para comparar os cinco operacionais.")
        else:
            try:
                cmp_raw=read_csv_bytes(candle_file.getvalue())
                cmp_candles=normalize_tradingview_candles(cmp_raw)
            except Exception as exc:
                cmp_candles=pd.DataFrame()
                st.error(f"CSV de candles inválido: {type(exc).__name__}: {exc}")

            if not cmp_candles.empty and st.button(
                "📊 Comparar os 5 operacionais",
                type="primary",
                key="atlasquant_compare_five",
            ):
                suite=run_strategy_suite(
                    cmp_candles,
                    pair=default_pair,
                    max_wait_bars=int(max_wait),
                    max_hold_bars=int(max_hold),
                    cost_r=float(cost_r),
                    slippage_r=float(slippage_r),
                )
                comparison=comparison_frame(
                    suite,
                    min_trades_for_rank=int(min_rank_trades),
                )
                st.markdown("#### Comparação geral")
                display_cols=[
                    "operacional","trades","gains","losses","breakeven",
                    "win_rate_pct","expectancy_r","net_r","profit_factor",
                    "max_drawdown_r","max_loss_streak","sample_tier",
                    "observed_expectancy_rank",
                ]
                st.dataframe(
                    comparison.reindex(columns=display_cols),
                    use_container_width=True,
                    hide_index=True,
                )

                eligible=int(comparison["eligible_observed_rank"].sum())
                if eligible == 0:
                    st.warning(
                        "Nenhum operacional atingiu a amostra mínima para ranking observado. "
                        "As métricas continuam visíveis, mas não há ranking."
                    )
                else:
                    st.info(
                        f"{eligible} operacional(is) atingiram a amostra mínima. "
                        "O ranking é apenas da expectativa observada nesta amostra histórica."
                    )

                by_session=breakdown_frame(suite,"session")
                if not by_session.empty:
                    st.markdown("#### Comparação por sessão")
                    st.dataframe(by_session,use_container_width=True,hide_index=True)

                stability=temporal_stability_report(
                    suite,
                    folds=int(stability_folds),
                    min_trades_per_fold=int(min_fold_trades),
                )
                stability_summary=stability["summary"]
                stability_folds_df=stability["folds"]

                st.markdown("#### Estabilidade temporal")
                st.caption(
                    "Cada operacional é dividido em blocos cronológicos de quantidade semelhante de trades. "
                    "O objetivo é detectar quando a expectativa positiva aparece só em uma parte do histórico."
                )
                stability_cols=[
                    "operacional","folds_available","positive_folds","negative_folds","flat_folds",
                    "positive_fold_pct","worst_expectancy_r","best_expectancy_r",
                    "expectancy_spread_r","expectancy_std_r","total_net_r","stability_status",
                ]
                st.dataframe(
                    stability_summary.reindex(columns=stability_cols),
                    use_container_width=True,
                    hide_index=True,
                )
                if not stability_folds_df.empty:
                    with st.expander("Ver blocos temporais detalhados",expanded=False):
                        st.dataframe(
                            stability_folds_df,
                            use_container_width=True,
                            hide_index=True,
                        )

                walkforward=walk_forward_report(
                    suite,
                    initial_train_pct=int(wf_train_pct),
                    test_windows=int(wf_windows),
                    min_train_trades=int(wf_min_train),
                    min_test_trades=int(wf_min_test),
                )
                wf_summary=walkforward["summary"]
                wf_windows_df=walkforward["windows"]

                st.markdown("#### Walk-forward — treino anterior × teste futuro")
                st.caption(
                    "Usa treino expansivo e janelas posteriores de teste, sem otimizar parâmetros. "
                    "Cada janela de teste fica cronologicamente depois do treino correspondente."
                )
                wf_cols=[
                    "operacional","windows_available","positive_test_windows","negative_test_windows",
                    "positive_test_pct","avg_train_expectancy_r","avg_test_expectancy_r",
                    "avg_expectancy_delta_r","worst_test_expectancy_r","best_test_expectancy_r",
                    "total_test_net_r","walk_forward_status",
                ]
                st.dataframe(
                    wf_summary.reindex(columns=wf_cols),
                    use_container_width=True,
                    hide_index=True,
                )
                if not wf_windows_df.empty:
                    with st.expander("Ver janelas walk-forward detalhadas",expanded=False):
                        st.dataframe(
                            wf_windows_df,
                            use_container_width=True,
                            hide_index=True,
                        )

                stress_levels=sorted({
                    float(x) for x in list(friction_slippage_levels)+[float(slippage_r)]
                })
                friction=friction_sensitivity_report(
                    suite,
                    base_cost_r=float(cost_r),
                    slippage_levels_r=stress_levels,
                    min_trades=int(friction_min_trades),
                )
                friction_summary=friction["summary"]
                friction_scenarios=friction["scenarios"]
                friction_breakdown=friction["breakdown"]

                st.markdown("#### Sensibilidade a custos e slippage")
                st.caption(
                    "Reprecifica exatamente os mesmos trades sob diferentes atritos em R. "
                    "Slippage aqui é um drag adverso por trade, não um simulador tick a tick."
                )
                friction_cols=[
                    "operacional","trades","scenarios_tested","positive_scenarios",
                    "positive_scenario_pct","baseline_expectancy_r","worst_expectancy_r",
                    "expectancy_drop_to_worst_r","first_nonpositive_total_friction_r",
                    "first_nonpositive_cost_r","first_nonpositive_slippage_r","sensitivity_status",
                ]
                st.dataframe(
                    friction_summary.reindex(columns=friction_cols),
                    use_container_width=True,
                    hide_index=True,
                )
                if not friction_scenarios.empty:
                    with st.expander("Ver cenários de custos/slippage detalhados",expanded=False):
                        st.dataframe(
                            friction_scenarios,
                            use_container_width=True,
                            hide_index=True,
                        )
                if not friction_breakdown.empty:
                    with st.expander("Ver custos/slippage por sessão e par",expanded=False):
                        st.dataframe(
                            friction_breakdown,
                            use_container_width=True,
                            hide_index=True,
                        )
                        st.download_button(
                            "📥 Baixar stress por sessão/par (CSV)",
                            data=friction_breakdown.to_csv(index=False),
                            file_name=f"atlasquant_friction_segmentos_{default_pair.replace('/','_')}.csv",
                            mime="text/csv",
                            key="atlasquant_compare_export_friction_breakdown",
                        )

                robustness_summary=pd.DataFrame()
                robustness_variants=pd.DataFrame()
                if include_param_robustness:
                    robustness=parameter_robustness_report(
                        cmp_candles,
                        pair=default_pair,
                        max_wait_bars=int(max_wait),
                        max_hold_bars=int(max_hold),
                        cost_r=float(cost_r),
                        slippage_r=float(slippage_r),
                        min_trades_per_variant=int(param_min_trades),
                    )
                    robustness_summary=robustness["summary"]
                    robustness_variants=robustness["variants"]
                    st.markdown("#### Robustez de parâmetros pré-definidos")
                    st.caption(
                        "Executa uma grade pequena e fixa, declarada no código. "
                        "O sistema não procura nem escolhe automaticamente o melhor parâmetro."
                    )
                    robustness_cols=[
                        "operacional","variants_tested","all_variants_sufficient",
                        "positive_variants","positive_variant_pct","base_expectancy_r",
                        "worst_expectancy_r","best_expectancy_r","expectancy_spread_r",
                        "min_variant_trades","max_variant_trades","parameter_robustness_status",
                    ]
                    st.dataframe(
                        robustness_summary.reindex(columns=robustness_cols),
                        use_container_width=True,
                        hide_index=True,
                    )
                    with st.expander("Ver variantes pré-definidas detalhadas",expanded=False):
                        st.dataframe(
                            robustness_variants,
                            use_container_width=True,
                            hide_index=True,
                        )
                        st.download_button(
                            "📥 Baixar robustez de parâmetros (CSV)",
                            data=robustness_variants.to_csv(index=False),
                            file_name=f"atlasquant_param_robustness_{default_pair.replace('/','_')}.csv",
                            mime="text/csv",
                            key="atlasquant_compare_export_param_robustness",
                        )

                evidence=consolidated_evidence_frame(
                    comparison,
                    stability_summary,
                    wf_summary,
                    friction_summary,
                    robustness_summary if include_param_robustness else None,
                )
                st.markdown("#### Relatório consolidado de evidências")
                st.caption(
                    "Reúne Backtest, estabilidade temporal, walk-forward, fricção e robustez "
                    "de parâmetros em uma única leitura. Cobertura indica disponibilidade de "
                    "diagnósticos, não qualidade do setup."
                )
                evidence_cols=[
                    "operacional","trades","win_rate_pct","expectancy_r","net_r",
                    "max_drawdown_r","sample_tier","temporal_status","walk_forward_status",
                    "friction_status","parameter_status","evidence_diagnostics_available",
                    "evidence_diagnostics_total","evidence_coverage",
                ]
                st.dataframe(
                    evidence.reindex(columns=evidence_cols),
                    use_container_width=True,
                    hide_index=True,
                )

                evidence_settings={
                    "pair":default_pair,
                    "max_wait_bars":int(max_wait),
                    "max_hold_bars":int(max_hold),
                    "cost_r":float(cost_r),
                    "slippage_r":float(slippage_r),
                    "stability_folds":int(stability_folds),
                    "min_fold_trades":int(min_fold_trades),
                    "walk_forward_train_pct":int(wf_train_pct),
                    "walk_forward_windows":int(wf_windows),
                    "walk_forward_min_train":int(wf_min_train),
                    "walk_forward_min_test":int(wf_min_test),
                    "friction_min_trades":int(friction_min_trades),
                    "parameter_robustness_ran":bool(include_param_robustness),
                    "parameter_min_trades":int(param_min_trades),
                }
                evidence_bundle=build_evidence_bundle(
                    pair=default_pair,
                    evidence=evidence,
                    comparison=comparison,
                    stability_summary=stability_summary,
                    stability_folds=stability_folds_df,
                    walkforward_summary=wf_summary,
                    walkforward_windows=wf_windows_df,
                    friction_summary=friction_summary,
                    friction_scenarios=friction_scenarios,
                    friction_breakdown=friction_breakdown,
                    parameter_summary=robustness_summary if include_param_robustness else None,
                    parameter_variants=robustness_variants if include_param_robustness else None,
                    settings=evidence_settings,
                )
                evidence_json=evidence_bundle_json(evidence_bundle)
                evidence_md=evidence_markdown(
                    evidence,
                    pair=default_pair,
                    settings=evidence_settings,
                )
                er1,er2=st.columns(2)
                with er1:
                    st.download_button(
                        "📥 Baixar relatório de evidências (JSON)",
                        data=evidence_json,
                        file_name=f"atlasquant_evidencias_{default_pair.replace('/','_')}.json",
                        mime="application/json",
                        key="atlasquant_compare_export_evidence_json",
                    )
                with er2:
                    st.download_button(
                        "📥 Baixar resumo de evidências (MD)",
                        data=evidence_md,
                        file_name=f"atlasquant_evidencias_{default_pair.replace('/','_')}.md",
                        mime="text/markdown",
                        key="atlasquant_compare_export_evidence_md",
                    )

                all_ledger=combined_ledger(suite)
                cexp1,cexp2,cexp3,cexp4,cexp5=st.columns(5)
                with cexp1:
                    st.download_button(
                        "📥 Baixar comparação (CSV)",
                        data=comparison.to_csv(index=False),
                        file_name=f"atlasquant_comparacao_5_{default_pair.replace('/','_')}.csv",
                        mime="text/csv",
                        key="atlasquant_compare_export_table",
                    )
                with cexp2:
                    st.download_button(
                        "📥 Baixar ledger dos 5 (CSV)",
                        data=all_ledger.to_csv(index=False),
                        file_name=f"atlasquant_ledger_5_{default_pair.replace('/','_')}.csv",
                        mime="text/csv",
                        key="atlasquant_compare_export_ledger",
                    )
                with cexp3:
                    stability_export=stability_folds_df.copy()
                    st.download_button(
                        "📥 Baixar estabilidade (CSV)",
                        data=stability_export.to_csv(index=False),
                        file_name=f"atlasquant_estabilidade_5_{default_pair.replace('/','_')}.csv",
                        mime="text/csv",
                        key="atlasquant_compare_export_stability",
                    )
                with cexp4:
                    st.download_button(
                        "📥 Baixar walk-forward (CSV)",
                        data=wf_windows_df.to_csv(index=False),
                        file_name=f"atlasquant_walkforward_5_{default_pair.replace('/','_')}.csv",
                        mime="text/csv",
                        key="atlasquant_compare_export_walkforward",
                    )
                with cexp5:
                    st.download_button(
                        "📥 Baixar custos/slippage (CSV)",
                        data=friction_scenarios.to_csv(index=False),
                        file_name=f"atlasquant_friction_5_{default_pair.replace('/','_')}.csv",
                        mime="text/csv",
                        key="atlasquant_compare_export_friction",
                    )

                st.caption(
                    "Comparação histórica não garante resultado futuro. Estratégias com poucas "
                    "operações ficam fora do ranking observado para reduzir leitura enganosa de amostra pequena."
                )

    if candle_file is None or signal_file is None:
        st.info(
            "Para o backtest manual, envie também a planilha de sinais. "
            "Os replays automáticos acima precisam apenas do CSV de candles."
        )
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
        slippage_r=float(slippage_r),
        start_after_signal_bar=True,
    )
    result=_render_result_block(results,pair,key_suffix="manual")
    st.caption(
        "Backtest histórico não garante resultado futuro. Esta tela mede apenas as regras "
        "e níveis fornecidos, com política conservadora para ambiguidades OHLC."
    )
    return {**result, "mode":"MANUAL"}
