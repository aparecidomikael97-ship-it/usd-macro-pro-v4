"""AtlasQuant branch-drift classification.

Separates mutable runtime-data drift from code/config drift so release reviews
do not confuse live snapshot churn with source-code divergence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


RUNTIME_MUTABLE_PATHS=frozenset({
    "dados/autopilot_inputs_v107.json",
    "dados/autopilot_status_v107.json",
    "dados/configuracoes_completas_v937.csv",
    "dados/currency_news_current_v107.json",
    "dados/currency_news_validation_v1061.csv",
    "dados/master_market_map_v102.json",
    "dados/scanner_tecnico_v934.json",
    "dados/autopilot_daily_cache_v107.json",
    "dados/sinais_v84.csv",
    "dados/atlasquant_flight_recorder.jsonl",
    "dados/atlasquant_quota_shadow_v1.json",
    "dados/atlasquant_shadow_samples.jsonl",
    "dados/paper_trades_v112.csv",
    "dados/paper_trading_summary_v112.json",
    "dados/paper_setup_audit_v114.csv",
    "dados/paper_setup_performance_v114.csv",
    "dados/paper_setup_summary_v114.json",
})


@dataclass(frozen=True)
class DriftAudit:
    runtime_files: tuple[str,...]
    code_or_config_files: tuple[str,...]
    unknown_data_files: tuple[str,...]
    runtime_only: bool
    requires_code_reconciliation: bool


def classify_path(path: str) -> str:
    p=str(path or "").strip().replace("\\","/")
    while "//" in p:
        p=p.replace("//","/")
    if p.startswith("./"):
        p=p[2:]
    parts=[x for x in p.split("/") if x not in ("",".")]
    if any(x==".." for x in parts) or p.startswith("/"):
        return "CODE_OR_CONFIG"
    p="/".join(parts)
    if p in RUNTIME_MUTABLE_PATHS:
        return "RUNTIME"
    if p.startswith("dados/"):
        return "UNKNOWN_DATA"
    return "CODE_OR_CONFIG"


def audit_branch_drift(paths: Iterable[str]) -> DriftAudit:
    runtime=[]
    code=[]
    unknown=[]
    for raw in paths:
        p=str(raw or "").strip().replace("\\","/")
        if not p:
            continue
        kind=classify_path(p)
        if kind=="RUNTIME":
            runtime.append(p)
        elif kind=="UNKNOWN_DATA":
            unknown.append(p)
        else:
            code.append(p)
    runtime=sorted(set(runtime))
    code=sorted(set(code))
    unknown=sorted(set(unknown))
    runtime_only=bool(runtime) and not code and not unknown
    return DriftAudit(
        runtime_files=tuple(runtime),
        code_or_config_files=tuple(code),
        unknown_data_files=tuple(unknown),
        runtime_only=runtime_only,
        requires_code_reconciliation=bool(code or unknown),
    )


def drift_release_message(audit: DriftAudit) -> str:
    if audit.requires_code_reconciliation:
        return "Branch drift includes code/config or unclassified data; reconcile before promotion."
    if audit.runtime_only:
        return "Branch drift is runtime-data only; source-code reconciliation is not required."
    return "No material branch drift supplied."
