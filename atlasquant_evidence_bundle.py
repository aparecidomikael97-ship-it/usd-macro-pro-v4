"""AtlasQuant validation evidence bundle.

Creates a portable, read-only manifest from Validation Readiness. The bundle
is evidence for human review only; it cannot merge, promote, reweight or alter
live trading gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any, Mapping

import streamlit as st

from atlasquant_validation_readiness import balanced_pair_coverage


SCHEMA_VERSION="atlasquant.validation-evidence.v1"


def _safe(value: Any) -> Any:
    if value is None or isinstance(value,(str,bool,int)):
        return value
    if isinstance(value,float):
        return value if math.isfinite(value) else None
    if isinstance(value,Mapping):
        return {str(k):_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,set)):
        return [_safe(v) for v in value]
    try:
        if hasattr(value,"item"):
            return _safe(value.item())
    except Exception:
        pass
    try:
        if hasattr(value,"isoformat"):
            return value.isoformat()
    except Exception:
        pass
    return str(value)


def _digest(payload: Mapping[str,Any]) -> str:
    raw=json.dumps(_safe(payload),sort_keys=True,ensure_ascii=False,separators=(",",":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def build_validation_evidence(
    readiness: Mapping[str,Any] | None,
    *,
    engine_version: str,
    generated_at: str | None = None,
    paper_summary: Mapping[str,Any] | None = None,
    setup_summary: Mapping[str,Any] | None = None,
) -> dict[str,Any]:
    r=dict(readiness or {})
    perf=dict(r.get("performance",{}) or {})
    calib=dict(r.get("calibration",{}) or {})
    stability=dict(r.get("stability",{}) or {})
    shadow=dict(r.get("shadow",{}) or {})
    pair_coverage=balanced_pair_coverage(
        shadow.get("expected_pairs") or [],
        shadow.get("pair_breakdown") or [],
        shadow.get("min_pair_samples") or 0,
    )
    pair_required_total=pair_coverage["required"]
    pair_covered_total=pair_coverage["covered"]
    quota_shadow=dict(r.get("quota_shadow",{}) or {})
    expansion=dict(r.get("expansion",{}) or {})
    paper=dict(paper_summary or {})
    setup=dict(setup_summary or {})

    generated=generated_at or datetime.now(timezone.utc).isoformat()
    engine=str(engine_version or "").strip()
    try:
        generated_dt=datetime.fromisoformat(str(generated).replace("Z","+00:00"))
        generated_valid=generated_dt.tzinfo is not None
    except Exception:
        generated_valid=False
    source_valid=bool(engine and generated_valid)
    body={
        "schema_version":SCHEMA_VERSION,
        "generated_at":str(generated),
        "engine_version":engine,
        "source_metadata_valid":source_valid,
        "validation":{
            "status":str(r.get("status","UNKNOWN")),
            "label":str(r.get("label","—")),
            "checks":dict(r.get("checks",{}) or {}),
            "passed_checks":int(r.get("passed_checks",0) or 0),
            "total_checks":int(r.get("total_checks",0) or 0),
            "blockers":list(r.get("blockers",[]) or []),
            "pending":list(r.get("pending",[]) or []),
        },
        "evidence":{
            "performance":{
                "status":perf.get("status"),
                "label":perf.get("label"),
                "samples":perf.get("samples",perf.get("total_samples")),
            },
            "calibration":{
                "status":calib.get("status"),
                "label":calib.get("label"),
                "samples":calib.get("total_samples",calib.get("samples")),
            },
            "stability":{
                "status":stability.get("status"),
                "label":stability.get("label"),
                "folds":stability.get("folds"),
            },
            "shadow":{
                "samples":shadow.get("samples"),
                "min_samples":shadow.get("min_samples"),
                "critical_mismatches":shadow.get("critical_mismatches"),
                "balanced_pair_covered":pair_covered_total,
                "balanced_pair_required":pair_required_total,
                "balanced_pair_complete":bool(pair_required_total and pair_covered_total>=pair_required_total),
                "coverage_balanced":shadow.get("coverage_balanced"),
                "pairs_meeting_minimum":shadow.get("pairs_meeting_minimum"),
                "expected_pair_count":shadow.get("expected_pair_count"),
                "missing_pairs":shadow.get("missing_pairs",[]),
                "under_sampled_pairs":shadow.get("under_sampled_pairs",[]),
                "eligible_for_manual_review":shadow.get("eligible_for_manual_review"),
            },
            "quota_shadow":{
                "samples":quota_shadow.get("samples"),
                "market_open_runs":quota_shadow.get("market_open_runs"),
                "min_market_runs":quota_shadow.get("min_market_runs"),
                "provider_blocked_runs":quota_shadow.get("provider_blocked_runs"),
                "headless_failed_runs":quota_shadow.get("headless_failed_runs"),
                "adaptive_plan_fit_all_samples":quota_shadow.get("adaptive_plan_fit_all_samples"),
                "eligible_for_manual_review":quota_shadow.get("eligible_for_manual_review"),
            },
            "paper_forward_test":{
                "trades_total":paper.get("trades_total"),
                "pending_entries":paper.get("pending_entries"),
                "open_positions":paper.get("open_positions"),
                "closed_trades":paper.get("closed_trades"),
                "net_r_after_friction":paper.get("net_r_after_friction"),
                "real_orders":dict(paper.get("safety",{}) or {}).get("real_orders",False),
            },
            "setup_audit":{
                "audited_trades":setup.get("audited_trades"),
                "closed_trades":setup.get("closed_trades"),
                "component_state_rows":setup.get("component_state_rows"),
                "sample_state":setup.get("sample_state"),
                "real_orders":dict(setup.get("safety",{}) or {}).get("real_orders",False),
            },
            "technical_expansion":{
                "target_requires_change":expansion.get("target_requires_change"),
                "max_pairs_same_cadence":expansion.get("max_pairs_same_cadence"),
            },
        },
        "controls":{
            "manual_review_required":True,
            "automatic_promotion_allowed":False,
            "automatic_weight_change_allowed":False,
            "automatic_merge_allowed":False,
        },
    }
    safe=_safe(body)
    safe["integrity_sha256"]=_digest(safe)
    return safe


def verify_validation_evidence(bundle: Mapping[str,Any] | None) -> bool:
    b=dict(bundle or {})
    expected=str(b.pop("integrity_sha256","") or "")
    return bool(expected) and _digest(_safe(b))==expected


def serialize_validation_evidence(bundle: Mapping[str,Any]) -> str:
    return json.dumps(_safe(bundle),ensure_ascii=False,sort_keys=True,indent=2)



def evidence_visual_state(bundle: Mapping[str,Any] | None)->dict[str,str]:
    b=dict(bundle or {})
    if not bool(b.get("source_metadata_valid",False)):
        return {"label":"PROVENIÊNCIA A REVISAR","detail":"Integridade pode estar válida, mas versão/timestamp da origem não são confiáveis"}
    if not verify_validation_evidence(b):
        return {"label":"INTEGRIDADE INVÁLIDA","detail":"O manifesto foi alterado ou está incompleto"}
    status=str((b.get("validation") or {}).get("status","UNKNOWN")).upper() if isinstance(b.get("validation"),Mapping) else "UNKNOWN"
    if status=="REVIEWABLE":
        return {"label":"EVIDÊNCIA ÍNTEGRA","detail":"Pacote pronto apenas para revisão humana"}
    if status=="BLOCKED":
        return {"label":"EVIDÊNCIA BLOQUEADA","detail":"Pacote íntegro, mas a validação contém bloqueios"}
    return {"label":"EVIDÊNCIA PARCIAL","detail":"Pacote íntegro; maturidade ainda não atingiu revisão completa"}


def render_validation_evidence(
    readiness: Mapping[str,Any],
    *,
    engine_version: str,
    paper_summary: Mapping[str,Any] | None = None,
    setup_summary: Mapping[str,Any] | None = None,
) -> dict[str,Any]:
    bundle=build_validation_evidence(
        readiness,
        engine_version=engine_version,
        paper_summary=paper_summary,
        setup_summary=setup_summary,
    )
    validation=bundle["validation"]
    shadow=bundle["evidence"]["shadow"]
    quota=bundle["evidence"]["quota_shadow"]

    st.markdown("### 📦 Validation Evidence Bundle")
    visual=evidence_visual_state(bundle)
    st.markdown(
        f"""<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:11px 13px;
        border:1px solid rgba(137,170,210,.18);border-radius:12px;margin:4px 0 13px;background:rgba(11,27,47,.52)">
        <strong>{visual['label']}</strong><span style="opacity:.74;font-size:.78rem">{visual['detail']}</span>
        <span style="margin-left:auto;opacity:.68;font-size:.72rem">SHA-256 · somente leitura</span></div>""",
        unsafe_allow_html=True,
    )
    st.caption(
        "Manifesto somente leitura para auditoria/revisão humana. "
        "Não promove versão, não muda pesos e não executa merge."
    )
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Estado",validation["status"])
    c2.metric("Checks",f"{validation['passed_checks']}/{validation['total_checks']}")
    c3.metric(
        "Shadow por par",
        f"{shadow.get('pairs_meeting_minimum') or 0}/{shadow.get('expected_pair_count') or 0}",
    )
    c4.metric(
        "Quota mercado",
        f"{quota.get('market_open_runs') or 0}/{quota.get('min_market_runs') or 0}",
    )
    balanced_required=int(shadow.get("balanced_pair_required") or 0)
    balanced_covered=int(shadow.get("balanced_pair_covered") or 0)
    if balanced_required:
        balanced_state="COMPLETA" if shadow.get("balanced_pair_complete") else "EM CONSTRUÇÃO"
        st.caption(
            f"Cobertura balanceada protegida no manifesto: "
            f"{balanced_covered}/{balanced_required} · {balanced_state}."
        )
    paper=bundle["evidence"].get("paper_forward_test",{})
    setup=bundle["evidence"].get("setup_audit",{})
    st.markdown("#### Evidência prospectiva")
    p1,p2,p3,p4=st.columns(4)
    p1.metric("Paper total",paper.get("trades_total") or 0)
    p2.metric("Paper fechados",paper.get("closed_trades") or 0)
    p3.metric("Setups auditados",setup.get("audited_trades") or 0)
    p4.metric("Maturidade setup",setup.get("sample_state") or "AGUARDANDO AMOSTRA")
    st.caption(
        "Forward test e Setup Audit são evidência prospectiva descritiva; "
        "não liberam operação real nem selecionam estratégia automaticamente."
    )
    st.caption(f"Integridade SHA-256: {bundle['integrity_sha256'][:16]}…")
    st.download_button(
        "📥 Exportar evidência de validação (JSON)",
        data=serialize_validation_evidence(bundle),
        file_name="atlasquant_validation_evidence.json",
        mime="application/json",
    )
    return bundle
