"""AtlasQuant TradingView/Python static parity contracts.

This validator is offline and read-only. It verifies that the research Pine
strategies and Python replay defaults/core formulas have not silently drifted.
It does NOT compile Pine and does NOT claim execution-level equivalence with
TradingView's broker emulator.
"""
from __future__ import annotations

from pathlib import Path
import inspect
import re
from typing import Any

from atlasquant_strategy_replay import generate_bos_choch_ob_signals
from atlasquant_fvg_replay import generate_fvg_signals
from atlasquant_ote_replay import generate_ote_signals
from atlasquant_crt_replay import generate_crt_signals
from atlasquant_amd_replay import generate_amd_signals
import ict_structure_v111


ROOT=Path(__file__).resolve().parent


def _pine(name: str) -> str:
    try:
        return (ROOT/"tradingview"/name).read_text(encoding="utf-8")
    except Exception:
        return ""


def _input_number(text: str, variable: str) -> float | None:
    # Accepts input.int(...) and input.float(...).
    m=re.search(
        rf"(?m)^\s*{re.escape(variable)}\s*=\s*input\.(?:int|float)\(\s*([-+]?\d+(?:\.\d+)?)",
        text,
    )
    return float(m.group(1)) if m else None


def _input_string(text: str, variable: str) -> str | None:
    m=re.search(
        rf'(?m)^\s*{re.escape(variable)}\s*=\s*input\.string\(\s*"([^"]+)"',
        text,
    )
    return m.group(1) if m else None


def _default(fn: Any, name: str) -> Any:
    return inspect.signature(fn).parameters[name].default


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name":name,"ok":bool(ok),"detail":detail}


def validate_tradingview_parity() -> dict[str, Any]:
    bos=_pine("atlasquant_bos_choch_ob_strategy_v1.pine")
    fvg=_pine("atlasquant_fvg_strategy_v1.pine")
    ote=_pine("atlasquant_ote_strategy_v1.pine")
    crt=_pine("atlasquant_crt_strategy_v1.pine")
    amd=_pine("atlasquant_amd_strategy_v1.pine")
    ote_src=inspect.getsource(generate_ote_signals)
    amd_src=inspect.getsource(generate_amd_signals)
    structure_src=inspect.getsource(ict_structure_v111)
    checks=[]

    # Shared execution contract.
    checks += [
        _check("bos_next_bar_processing","process_orders_on_close=false" in bos.replace(" ",""),"Pine BOS/CHOCH+OB must process orders after the signal close."),
        _check("fvg_next_bar_processing","process_orders_on_close=false" in fvg.replace(" ",""),"Pine FVG must process orders after the signal close."),
        _check("bos_no_external_series","request.security" not in bos.lower(),"BOS/CHOCH+OB Pine must stay single-series/offline."),
        _check("fvg_no_external_series","request.security" not in fvg.lower(),"FVG Pine must stay single-series/offline."),
        _check("ote_next_bar_processing","process_orders_on_close=false" in ote.replace(" ",""),"Pine OTE must process orders after the signal close."),
        _check("ote_no_external_series","request.security" not in ote.lower(),"OTE Pine must stay single-series/offline."),
        _check("crt_next_bar_processing","process_orders_on_close=false" in crt.replace(" ",""),"Pine CRT must process orders after the signal close."),
        _check("crt_no_external_series","request.security" not in crt.lower(),"CRT Pine must stay single-series/offline."),
        _check("amd_next_bar_processing","process_orders_on_close=false" in amd.replace(" ",""),"Pine AMD must process orders after the distribution close."),
        _check("amd_no_external_series","request.security" not in amd.lower(),"AMD Pine must stay single-series/offline."),
    ]

    # FVG defaults and core geometry.
    checks += [
        _check("fvg_rr_default",_input_number(fvg,"rrTarget")==float(_default(generate_fvg_signals,"rr_target")),"Pine/Python RR default must match."),
        _check("fvg_stop_buffer_default",_input_number(fvg,"stopBufferAtr")==float(_default(generate_fvg_signals,"stop_buffer_atr")),"Pine/Python stop buffer default must match."),
        _check("fvg_min_gap_default",_input_number(fvg,"minGapAtr")==float(_default(generate_fvg_signals,"min_gap_atr")),"Pine/Python minimum gap default must match."),
        _check("fvg_entry_default",str(_input_string(fvg,"entryMode")).upper()==str(_default(generate_fvg_signals,"entry_mode")).upper(),"Pine/Python entry mode default must match."),
        _check("fvg_wait_default",_input_number(fvg,"maxSetupAge")==8.0,"Pine FVG pending-order life must match AtlasQuant's default max_wait_bars=8."),
        _check("fvg_bull_formula","bullGapSize = low - high[2]" in fvg,"Bull FVG geometry must be third-low minus first-high."),
        _check("fvg_bear_formula","bearGapSize = low[2] - high" in fvg,"Bear FVG geometry must be first-low minus third-high."),
    ]

    # OTE defaults and geometry.
    checks += [
        _check("ote_rr_default",_input_number(ote,"rrTarget")==float(_default(generate_ote_signals,"rr_target")),"Pine/Python OTE RR default must match."),
        _check("ote_stop_buffer_default",_input_number(ote,"stopBufferAtr")==float(_default(generate_ote_signals,"stop_buffer_atr")),"Pine/Python OTE stop buffer must match."),
        _check("ote_min_impulse_default",_input_number(ote,"minImpulseAtr")==float(_default(generate_ote_signals,"min_impulse_atr")),"Pine/Python OTE impulse filter must match."),
        _check("ote_lookback_default",_input_number(ote,"lookback")==float(_default(generate_ote_signals,"lookback")),"Pine/Python OTE lookback must match."),
        _check("ote_recent_default",_input_number(ote,"recentExtreme")==float(_default(generate_ote_signals,"recent_extreme")),"Pine/Python recent extreme window must match."),
        _check("ote_wait_default",_input_number(ote,"maxSetupAge")==8.0,"Pine OTE pending-order life must match backtest default."),
        _check("ote_sweet_formula","0.705" in ote,"OTE Pine must retain 70.5% sweet spot."),
        _check("ote_zone_formula","0.62" in ote and "0.79" in ote,"OTE Pine must retain the 62%-79% zone."),
        _check("ote_warmup","replayReady = bar_index >= lookback - 1 and not na(atr)" in ote and int(_default(generate_ote_signals,"min_bars"))==28,"OTE Pine/Python warmup must align at 28 bars."),
        _check(
            "ote_reanchor_guard",
            "buyLoBar > lastBuyTerminalBar" in ote
            and "sellHiBar > lastSellTerminalBar" in ote
            and "origin_global<=previous_terminal" in ote_src,
            "OTE same-side signals must start after the previous emitted impulse terminal.",
        ),
    ]

    # CRT defaults and three-candle rule contract.
    checks += [
        _check("crt_stop_buffer_default",_input_number(crt,"stopBufferAtr")==float(_default(generate_crt_signals,"stop_buffer_atr")),"Pine/Python CRT stop buffer default must match."),
        _check("crt_min_rr_default",_input_number(crt,"minRR")==float(_default(generate_crt_signals,"min_rr")),"Pine/Python CRT min RR default must match."),
        _check("crt_wait_default",_input_number(crt,"maxSetupAge")==8.0,"Pine CRT pending-order life must match backtest default."),
        _check("crt_warmup","replayReady = bar_index >= 13 and not na(atr)" in crt and int(_default(generate_crt_signals,"min_bars"))==14,"CRT Pine/Python warmup must align at 14 bars."),
        _check("crt_buy_raid","low[1] < anchorLow and close[1] > anchorLow" in crt,"CRT BUY raid/reclaim rule must match."),
        _check("crt_buy_delivery","close > close[1] and close > anchorMid" in crt,"CRT BUY delivery rule must match."),
        _check("crt_sell_raid","high[1] > anchorHigh and close[1] < anchorHigh" in crt,"CRT SELL raid/reclaim rule must match."),
        _check("crt_sell_delivery","close < close[1] and close < anchorMid" in crt,"CRT SELL delivery rule must match."),
        _check("crt_structural_targets","buyTarget = anchorHigh" in crt and "sellTarget = anchorLow" in crt,"CRT targets must remain the opposite anchor boundary."),
        _check("crt_entry_close","buyEntry = close" in crt and "sellEntry = close" in crt,"CRT confirmed delivery close must remain the pending entry reference."),
    ]

    # AMD / Power of Three defaults and strict temporal state contract.
    checks += [
        _check("amd_accumulation_default",_input_number(amd,"accumulationBars")==float(_default(generate_amd_signals,"accumulation_bars")),"Pine/Python accumulation length must match."),
        _check("amd_distribution_window_default",_input_number(amd,"maxDistributionBars")==float(_default(generate_amd_signals,"max_distribution_bars")),"Pine/Python distribution window must match."),
        _check("amd_stop_buffer_default",_input_number(amd,"stopBufferAtr")==float(_default(generate_amd_signals,"stop_buffer_atr")),"Pine/Python AMD stop buffer must match."),
        _check("amd_min_rr_default",_input_number(amd,"minRR")==float(_default(generate_amd_signals,"min_rr")),"Pine/Python AMD min RR must match."),
        _check("amd_wait_default",_input_number(amd,"maxSetupAge")==8.0,"Pine AMD pending-order life must match backtest default."),
        _check("amd_warmup","replayReady = bar_index >= 13 and not na(atr)" in amd and int(_default(generate_amd_signals,"min_bars"))==14,"AMD Pine/Python warmup must align at 14 bars."),
        _check("amd_buy_manip","low < accLow and close > accLow" in amd and 'float(row["low"])<al and float(row["close"])>al' in amd_src,"BUY manipulation must sweep SSL and reclaim the frozen accumulation."),
        _check("amd_sell_manip","high > accHigh and close < accHigh" in amd and 'float(row["high"])>ah and float(row["close"])<ah' in amd_src,"SELL manipulation must sweep BSL and reclaim the frozen accumulation."),
        _check("amd_buy_distribution","close > frozenAccMid and close > manipulationClose" in amd and 'close>mid and close>p.manipulation_close' in amd_src,"BUY distribution must occur later above midpoint and manipulation close."),
        _check("amd_sell_distribution","close < frozenAccMid and close < manipulationClose" in amd and 'close<mid and close<p.manipulation_close' in amd_src,"SELL distribution must occur later below midpoint and manipulation close."),
        _check("amd_phase_order","bar_index > manipulationBar" in amd and 'i>p.manipulation_index' in amd_src,"Distribution cannot confirm on the manipulation candle."),
        _check("amd_two_sided_resolution","buyDepth >= sellDepth ? 1 : -1" in amd and 'selected="BUY" if buy_depth>=sell_depth else "SELL"' in amd_src,"Two-sided sweeps must resolve deterministically by normalized depth."),
        _check("amd_structural_targets","candidateTarget = frozenAccHigh" in amd and "candidateTarget = frozenAccLow" in amd,"AMD targets must remain opposite accumulation boundaries."),
    ]

    # BOS/CHOCH + OB defaults and rule contract.
    checks += [
        _check("bos_rr_default",_input_number(bos,"rrTarget")==float(_default(generate_bos_choch_ob_signals,"rr_target")),"Pine/Python RR default must match."),
        _check("bos_stop_buffer_default",_input_number(bos,"stopBufferAtr")==float(_default(generate_bos_choch_ob_signals,"stop_buffer_atr")),"Pine/Python stop buffer default must match."),
        _check("bos_entry_default",str(_input_string(bos,"entryMode")).upper()==str(_default(generate_bos_choch_ob_signals,"entry_mode")).upper(),"Pine/Python entry mode default must match."),
        _check("bos_min_bars_contract","replayReady = bar_index >= 19 and not na(atr)" in bos and int(_default(generate_bos_choch_ob_signals,"min_bars"))==20,"Pine must wait for the same 20-bar research warmup used by Python."),
        _check("bos_wait_default",_input_number(bos,"maxSetupAge")==8.0,"Pine pending-order life must match AtlasQuant's default max_wait_bars=8."),
        _check("bos_pivot_defaults",_input_number(bos,"leftBars")==2.0 and _input_number(bos,"rightBars")==2.0,"Pine pivots must match Python 2/2 confirmed pivots."),
        _check("bos_atr_default",_input_number(bos,"atrLen")==14.0,"Pine ATR default must remain 14."),
        _check("bos_noise_default",_input_number(bos,"noiseAtr")==0.05 and "atr_ref * 0.05" in structure_src,"Pine/Python structural noise default must remain 0.05 ATR."),
        _check("bos_origin_limit",_input_number(bos,"maxOrigin")==8.0 and "break_idx - 8" in structure_src,"Pine/Python OB origin search must remain capped at eight candles."),
        _check("bos_displacement_body",_input_number(bos,"bodyAtrMin")==0.65 and "body_atr >= 0.65" in structure_src,"Pine/Python displacement body threshold must match."),
        _check("bos_displacement_range",_input_number(bos,"rangeAtrMin")==0.85 and "range_atr >= 0.85" in structure_src,"Pine/Python displacement range threshold must match."),
    ]

    failed=[x for x in checks if not x["ok"]]
    return {
        "status":"OK" if not failed else "DRIFT",
        "checks":checks,
        "passed":len(checks)-len(failed),
        "failed":len(failed),
        "limitations":[
            "Validação estática; não compila Pine.",
            "Não prova equivalência do broker emulator do TradingView com o simulador Python.",
            "Timezone/sessão e arredondamento por tick podem produzir diferenças quando configurados manualmente.",
        ],
    }
