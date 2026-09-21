"""Strict alignment contract for AtlasQuant multi-timeframe research.

Execution-grade historical simulations may only count a trade when four
independent conditions were known at signal time:
1) market reading/context aligned;
2) direction aligned;
3) filters aligned;
4) trigger aligned.

Missing evidence fails closed. This module does not infer alignment from future
outcomes and does not enable live orders.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_timeframe_profiles import normalize_execution_timeframe

ALIGNMENT_FIELDS=(
    "reading_aligned",
    "direction_aligned",
    "filters_aligned",
    "trigger_aligned",
)

TIMEFRAME_CONTEXT={
    "M15":("H1","H4"),
    "M30":("H1","H4"),
    "H1":("H4","D1"),
    "H4":("D1","W1"),
    "D1":("W1",),
    "W1":("W1",),
}


def _truth(value:Any)->bool|None:
    if isinstance(value,bool):
        return value
    if value is None:
        return None
    raw=str(value).strip().lower()
    if raw in {"1","true","sim","yes","ok","aligned","alinhado","confirmado"}:
        return True
    if raw in {"0","false","não","nao","no","blocked","desalinhado","divergente"}:
        return False
    return None


def alignment_gate(
    evidence:Mapping[str,Any]|None,
    *,
    timeframe:Any="M15",
    strict:bool=True,
)->dict[str,Any]:
    tf=normalize_execution_timeframe(timeframe)
    src=dict(evidence or {})
    checks={field:_truth(src.get(field)) for field in ALIGNMENT_FIELDS}
    missing=[field for field,value in checks.items() if value is None]
    failed=[field for field,value in checks.items() if value is False]
    passed=not failed and (not strict or not missing)
    reasons=[]
    if failed:
        reasons.extend("DESALINHADO:"+field for field in failed)
    if strict and missing:
        reasons.extend("SEM_EVIDENCIA:"+field for field in missing)
    return {
        "timeframe":tf,
        "context_timeframes":list(TIMEFRAME_CONTEXT[tf]),
        "checks":checks,
        "missing":missing,
        "failed":failed,
        "passed":bool(passed),
        "strict":bool(strict),
        "reason":"ALINHADO" if passed else "|".join(reasons) or "BLOQUEADO",
        "real_orders_enabled":False,
    }


__all__=["ALIGNMENT_FIELDS","TIMEFRAME_CONTEXT","alignment_gate"]
