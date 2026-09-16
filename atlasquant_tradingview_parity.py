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
