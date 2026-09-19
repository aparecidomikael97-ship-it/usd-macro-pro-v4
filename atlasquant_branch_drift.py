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
    "dados/twelve_budget_v1108.json",
    "dados/twelve_series_v1108.json",
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



def reconciliation_state(
    audit: DriftAudit,
    *,
    ahead_by: object,
    behind_by: object,
) -> dict[str, object]:
    def valid_count(value: object) -> int | None:
        if isinstance(value,bool):
            return None
        try:
            out=int(value)
        except Exception:
            return None
        return out if out>=0 and str(out)==str(value).strip() else None

    ahead=valid_count(ahead_by)
    behind=valid_count(behind_by)
    if ahead is None or behind is None:
        return {
            "status":"REVIEW_REQUIRED",
            "label":"CONTAGENS DE BRANCH INVÁLIDAS",
            "automatic_merge_allowed":False,
            "manual_reconciliation_required":True,
            "runtime_drift_can_be_ignored_for_source_review":False,
        }
    if audit.requires_code_reconciliation:
        return {
            "status":"SOURCE_DIVERGED" if behind>0 else "SOURCE_AHEAD",
            "label":"RECONCILIAÇÃO DE CÓDIGO NECESSÁRIA",
            "automatic_merge_allowed":False,
            "manual_reconciliation_required":True,
            "runtime_drift_can_be_ignored_for_source_review":False,
        }
    if audit.runtime_only:
        return {
            "status":"RUNTIME_ONLY_BEHIND" if behind>0 else "RUNTIME_ONLY",
            "label":"DRIFT APENAS DE RUNTIME" if behind==0 else "RUNTIME ISOLADO, MAIN AVANÇOU",
            "automatic_merge_allowed":False,
            "manual_reconciliation_required":bool(behind>0),
            "runtime_drift_can_be_ignored_for_source_review":True,
        }
    if ahead==0 and behind==0:
        return {
            "status":"ALIGNED",
            "label":"BRANCHES ALINHADOS",
            "automatic_merge_allowed":False,
            "manual_reconciliation_required":False,
            "runtime_drift_can_be_ignored_for_source_review":False,
        }
    return {
        "status":"REVIEW_REQUIRED",
        "label":"DIVERGÊNCIA SEM ARQUIVOS CLASSIFICADOS",
        "automatic_merge_allowed":False,
        "manual_reconciliation_required":True,
        "runtime_drift_can_be_ignored_for_source_review":False,
    }


def build_reconciliation_manifest(
    paths: Iterable[str],
    *,
    ahead_by: object,
    behind_by: object,
) -> dict[str, object]:
    audit=audit_branch_drift(paths)
    state=reconciliation_state(audit,ahead_by=ahead_by,behind_by=behind_by)
    return {
        "schema":"ATLASQUANT_BRANCH_RECONCILIATION_V1",
        "status":state["status"],
        "label":state["label"],
        "ahead_by":ahead_by,
        "behind_by":behind_by,
        "runtime_files":len(audit.runtime_files),
        "code_or_config_files":len(audit.code_or_config_files),
        "unknown_data_files":len(audit.unknown_data_files),
        "runtime_only":audit.runtime_only,
        "requires_code_reconciliation":audit.requires_code_reconciliation,
        "automatic_merge_allowed":False,
        "manual_reconciliation_required":bool(state["manual_reconciliation_required"]),
        "runtime_drift_can_be_ignored_for_source_review":bool(state["runtime_drift_can_be_ignored_for_source_review"]),
        "source_paths":list(audit.code_or_config_files),
        "unknown_data_paths":list(audit.unknown_data_files),
    }



def drift_release_message(audit: DriftAudit) -> str:
    if audit.requires_code_reconciliation:
        return "Branch drift includes code/config or unclassified data; reconcile before promotion."
    if audit.runtime_only:
        return "Branch drift is runtime-data only; source-code reconciliation is not required."
    return "No material branch drift supplied."
