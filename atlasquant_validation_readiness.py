"""AtlasQuant Validation Readiness Center V1.

Combines diagnostic evidence from Performance, Calibration, Stability and
Shadow Mode into a single research-readiness view. It never promotes code,
changes weights, alters live gates or merges branches.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import pandas as pd
import streamlit as st

from atlasquant_performance_lab import performance_readiness
from atlasquant_calibration_lab import calibration_table, calibration_summary
from atlasquant_stability_lab import temporal_folds, stability_summary
from atlasquant_shadow_mode import summarize_shadow, DEFAULT_SHADOW_PAIRS
from atlasquant_expansion_budget import expansion_plan


def build_validation_readiness(
    history: pd.DataFrame,
    shadow_samples: Sequence[Mapping[str, Any]] | None = None,
    *,
    horizon: str = "24h",
    min_total_samples: int = 100,
    min_group_samples: int = 30,
    min_band_samples: int = 30,
    min_fold_samples: int = 30,
    min_shadow_samples: int = 100,
    min_shadow_pair_samples: int = 10,
    expected_shadow_pairs: Sequence[str] | None = DEFAULT_SHADOW_PAIRS,
    current_pairs: int = 7,
    target_pairs: int = 28,
    daily_cap: int = 480,
) -> dict[str, Any]:
    perf=performance_readiness(
        history,
        horizon,
        min_total_samples=min_total_samples,
        min_group_samples=min_group_samples,
    )
    calib_table=calibration_table(
        history,
        horizon,
        min_band_samples=min_band_samples,
    )
    calib=calibration_summary(
        calib_table,
        min_total_samples=min_total_samples,
    )
    folds=temporal_folds(history,horizon,folds=3)
    stability=stability_summary(
        folds,
        min_fold_samples=min_fold_samples,
    )
    shadow=summarize_shadow(
        shadow_samples or [],
        min_samples=min_shadow_samples,
        expected_pairs=expected_shadow_pairs,
        min_pair_samples=min_shadow_pair_samples,
    )
    expansion=expansion_plan(
        current_pairs=current_pairs,
        target_pairs=target_pairs,
        daily_cap=daily_cap,
    )

    checks={
        "performance_reviewable": perf["status"]=="REVIEWABLE",
        "calibration_consistent": calib["status"]=="CONSISTENT",
        "stability_consistent": stability["status"]=="STABLE",
        "shadow_reviewable": bool(shadow["eligible_for_manual_review"]),
    }
    passed=sum(1 for ok in checks.values() if ok)

    blockers=[]
    pending=[]
    if perf["status"]!="REVIEWABLE":
        pending.append(f"Performance: {perf['label']}")
    if calib["status"]!="CONSISTENT":
        pending.append(f"Calibração: {calib['label']}")
    if stability["status"]!="STABLE":
        pending.append(f"Estabilidade: {stability['label']}")
    if shadow["critical_mismatches"]:
        blockers.append(
            f"Shadow Mode com {shadow['critical_mismatches']} divergência(s) crítica(s)"
        )
    elif not shadow["minimum_met"]:
        pending.append(
            f"Shadow Mode: {shadow['samples']}/{shadow['min_samples']} amostras"
        )
    elif not shadow["coverage_balanced"]:
        gaps=list(shadow.get("missing_pairs",[])) + list(shadow.get("under_sampled_pairs",[]))
        suffix=", ".join(gaps[:7]) if gaps else "cobertura concentrada"
        pending.append(
            "Shadow Mode: cobertura por par insuficiente "
            f"({shadow['pairs_meeting_minimum']}/{shadow['expected_pair_count']}) · {suffix}"
        )

    if blockers:
        status="BLOCKED"
        label="VALIDAÇÃO BLOQUEADA"
    elif passed==len(checks):
        status="REVIEWABLE"
        label="EVIDÊNCIA PRONTA PARA REVISÃO HUMANA"
    elif passed:
        status="PARTIAL"
        label="VALIDAÇÃO PARCIAL"
    else:
        status="BUILDING"
        label="EVIDÊNCIA EM FORMAÇÃO"

    return {
        "status":status,
        "label":label,
        "checks":checks,
        "passed_checks":passed,
        "total_checks":len(checks),
        "blockers":blockers,
        "pending":pending,
        "performance":perf,
        "calibration":calib,
        "stability":stability,
        "shadow":shadow,
        "expansion":expansion,
        "manual_review_required":True,
        "automatic_promotion_allowed":False,
        "automatic_weight_change_allowed":False,
        "automatic_merge_allowed":False,
    }


def render_validation_readiness(
    history: pd.DataFrame,
    shadow_samples: Sequence[Mapping[str, Any]] | None = None,
    *,
    horizon: str = "24h",
) -> dict[str, Any]:
    result=build_validation_readiness(
        history,
        shadow_samples,
        horizon=horizon,
    )
    icon={
        "REVIEWABLE":"🟢",
        "PARTIAL":"🟡",
        "BUILDING":"🟠",
        "BLOCKED":"🔴",
    }.get(result["status"],"⚪")

    st.markdown("### ✅ Validation Readiness Center")
    st.caption(
        "Resume a maturidade da evidência. Não promove versão, não altera pesos "
        "e não faz merge automático."
    )
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Estado",f"{icon} {result['label']}")
    c2.metric("Checks aprovados",f"{result['passed_checks']}/{result['total_checks']}")
    c3.metric("Shadow samples",result["shadow"]["samples"])
    c4.metric("Auto-promoção","DESATIVADA")

    rows=[
        {"Camada":"Performance","OK":result["checks"]["performance_reviewable"],"Estado":result["performance"]["label"]},
        {"Camada":"Calibração","OK":result["checks"]["calibration_consistent"],"Estado":result["calibration"]["label"]},
        {"Camada":"Estabilidade","OK":result["checks"]["stability_consistent"],"Estado":result["stability"]["label"]},
        {
            "Camada":"Shadow Mode",
            "OK":result["checks"]["shadow_reviewable"],
            "Estado":(
                "ELEGÍVEL PARA REVISÃO"
                if result["shadow"]["eligible_for_manual_review"]
                else (
                    f"{result['shadow']['samples']}/{result['shadow']['min_samples']} amostras · "
                    f"{result['shadow']['pairs_meeting_minimum']}/{result['shadow']['expected_pair_count']} pares"
                )
            ),
        },
    ]
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

    if result["blockers"]:
        st.error(" · ".join(result["blockers"]))
    elif result["pending"]:
        with st.expander("Pendências antes de revisão"):
            for item in result["pending"]:
                st.write("•",item)
    else:
        st.success("Os quatro blocos atingiram os critérios mínimos para revisão humana.")

    exp=result["expansion"]
    if exp["target_requires_change"]:
        st.caption(
            "Expansão 7→28 no pipeline técnico ainda exige ajuste de cadência/fonte/cache/orçamento; "
            "isso não bloqueia a validação do pipeline atual de 7 pares."
        )

    st.caption(
        "Merge para main, promoção de produção e mudanças de peso continuam exclusivamente manuais."
    )
    return result
