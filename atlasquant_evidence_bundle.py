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
) -> dict[str,Any]:
    r=dict(readiness or {})
    perf=dict(r.get("performance",{}) or {})
    calib=dict(r.get("calibration",{}) or {})
    stability=dict(r.get("stability",{}) or {})
    shadow=dict(r.get("shadow",{}) or {})
    expansion=dict(r.get("expansion",{}) or {})

    generated=generated_at or datetime.now(timezone.utc).isoformat()
    body={
        "schema_version":SCHEMA_VERSION,
        "generated_at":str(generated),
        "engine_version":str(engine_version),
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
                "coverage_balanced":shadow.get("coverage_balanced"),
                "pairs_meeting_minimum":shadow.get("pairs_meeting_minimum"),
                "expected_pair_count":shadow.get("expected_pair_count"),
                "missing_pairs":shadow.get("missing_pairs",[]),
                "under_sampled_pairs":shadow.get("under_sampled_pairs",[]),
                "eligible_for_manual_review":shadow.get("eligible_for_manual_review"),
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


def render_validation_evidence(
    readiness: Mapping[str,Any],
    *,
    engine_version: str,
) -> dict[str,Any]:
    bundle=build_validation_evidence(readiness,engine_version=engine_version)
    validation=bundle["validation"]
    shadow=bundle["evidence"]["shadow"]

    st.markdown("### 📦 Validation Evidence Bundle")
    st.caption(
        "Manifesto somente leitura para auditoria/revisão humana. "
        "Não promove versão, não muda pesos e não executa merge."
    )
    c1,c2,c3=st.columns(3)
    c1.metric("Estado",validation["status"])
    c2.metric("Checks",f"{validation['passed_checks']}/{validation['total_checks']}")
    c3.metric(
        "Shadow por par",
        f"{shadow.get('pairs_meeting_minimum') or 0}/{shadow.get('expected_pair_count') or 0}",
    )
    st.caption(f"Integridade SHA-256: {bundle['integrity_sha256'][:16]}…")
    st.download_button(
        "📥 Exportar evidência de validação (JSON)",
        data=serialize_validation_evidence(bundle),
        file_name="atlasquant_validation_evidence.json",
        mime="application/json",
    )
    return bundle
