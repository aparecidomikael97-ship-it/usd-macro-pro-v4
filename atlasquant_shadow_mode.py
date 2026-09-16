"""AtlasQuant Shadow Mode V1.

Infrastructure for Champion × Challenger observation. It is deliberately
non-promotional: comparisons can qualify a challenger for human review, never
for automatic production promotion.
"""
from __future__ import annotations

from hashlib import sha256
from statistics import mean
from typing import Any, Mapping, Sequence
import json
import math
import streamlit as st


VALID_SIDES={"BUY","SELL","NEUTRAL","NO_TRADE"}
DEFAULT_SHADOW_PAIRS=("EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CHF","USD/CAD")


def _num(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def normalize_snapshot(payload: Mapping[str, Any] | None, *, role: str) -> dict[str, Any]:
    p=dict(payload or {})
    side=str(p.get("side","NEUTRAL") or "NEUTRAL").upper()
    if side not in VALID_SIDES:
        side="NEUTRAL"
    return {
        "role":str(role).upper(),
        "pair":str(p.get("pair","—")),
        "side":side,
        "state":str(p.get("state","—")),
        "score":_num(p.get("score")),
        "data_quality":_num(p.get("data_quality",p.get("quality"))),
        "executable":bool(p.get("executable",False)),
        "version":str(p.get("version","—")),
        "timestamp":str(p.get("timestamp","")),
    }


def _sample_id(champion: Mapping[str, Any], challenger: Mapping[str, Any]) -> str:
    payload={
        "pair":champion.get("pair"),
        "timestamp":champion.get("timestamp") or challenger.get("timestamp"),
        "champion_version":champion.get("version"),
        "challenger_version":challenger.get("version"),
        "champion_side":champion.get("side"),
        "challenger_side":challenger.get("side"),
        "champion_state":champion.get("state"),
        "challenger_state":challenger.get("state"),
    }
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def compare_shadow_sample(
    champion_payload: Mapping[str, Any] | None,
    challenger_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    champion=normalize_snapshot(champion_payload,role="CHAMPION")
    challenger=normalize_snapshot(challenger_payload,role="CHALLENGER")
    pair_match=champion["pair"]==challenger["pair"]
    side_match=champion["side"]==challenger["side"]
    execution_match=champion["executable"]==challenger["executable"]
    state_match=champion["state"]==challenger["state"]
    opposite=(
        champion["side"] in ("BUY","SELL")
        and challenger["side"] in ("BUY","SELL")
        and champion["side"]!=challenger["side"]
    )
    score_delta=None
    if champion["score"] is not None and challenger["score"] is not None:
        score_delta=round(float(challenger["score"])-float(champion["score"]),4)
    quality_delta=None
    if champion["data_quality"] is not None and challenger["data_quality"] is not None:
        quality_delta=round(float(challenger["data_quality"])-float(champion["data_quality"]),4)

    critical=bool(not pair_match or opposite or not execution_match)
    return {
        "sample_id":_sample_id(champion,challenger),
        "champion":champion,
        "challenger":challenger,
        "pair_match":pair_match,
        "side_match":side_match,
        "execution_match":execution_match,
        "state_match":state_match,
        "opposite_direction":opposite,
        "critical_mismatch":critical,
        "score_delta":score_delta,
        "quality_delta":quality_delta,
    }


def append_shadow_sample(
    samples: Sequence[Mapping[str, Any]] | None,
    sample: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    rows=[dict(x) for x in (samples or [])]
    sid=str(sample.get("sample_id",""))
    if sid and any(str(x.get("sample_id",""))==sid for x in rows):
        return rows,False
    rows.append(dict(sample))
    return rows,True


def shadow_pair_breakdown(
    samples: Sequence[Mapping[str, Any]] | None,
    *,
    expected_pairs: Sequence[str] | None = None,
    min_pair_samples: int = 10,
) -> list[dict[str, Any]]:
    rows=[dict(x) for x in (samples or [])]
    observed={
        str((x.get("champion",{}) or {}).get("pair", "—"))
        for x in rows
        if str((x.get("champion",{}) or {}).get("pair", "")).strip()
    }
    pairs=(
        [str(x) for x in expected_pairs]
        if expected_pairs is not None
        else sorted(observed)
    )
    out=[]
    for pair in pairs:
        subset=[
            x for x in rows
            if str((x.get("champion",{}) or {}).get("pair","—"))==pair
        ]
        total=len(subset)
        side=sum(1 for x in subset if bool(x.get("side_match")))
        execution=sum(1 for x in subset if bool(x.get("execution_match")))
        critical=sum(1 for x in subset if bool(x.get("critical_mismatch")))
        score_deltas=[
            abs(float(x["score_delta"]))
            for x in subset
            if _num(x.get("score_delta")) is not None
        ]
        out.append({
            "pair":pair,
            "samples":total,
            "minimum_met":total>=int(min_pair_samples),
            "side_agreement_pct":None if total==0 else round(side/total*100.0,2),
            "execution_agreement_pct":None if total==0 else round(execution/total*100.0,2),
            "critical_mismatches":critical,
            "mean_abs_score_delta":None if not score_deltas else round(mean(score_deltas),4),
        })
    return out


def summarize_shadow(
    samples: Sequence[Mapping[str, Any]] | None,
    *,
    min_samples: int = 100,
    expected_pairs: Sequence[str] | None = None,
    min_pair_samples: int = 10,
) -> dict[str, Any]:
    rows=[dict(x) for x in (samples or [])]
    total=len(rows)
    def pct(key: str) -> float | None:
        return None if total==0 else round(sum(1 for x in rows if bool(x.get(key)))/total*100.0,2)
    score_deltas=[abs(float(x["score_delta"])) for x in rows if _num(x.get("score_delta")) is not None]
    quality_deltas=[abs(float(x["quality_delta"])) for x in rows if _num(x.get("quality_delta")) is not None]
    critical=sum(1 for x in rows if bool(x.get("critical_mismatch",False)))
    enough=total>=int(min_samples)

    pair_rows=shadow_pair_breakdown(
        rows,
        expected_pairs=expected_pairs,
        min_pair_samples=min_pair_samples,
    )
    coverage_gate_enabled=expected_pairs is not None
    balanced=(
        all(bool(x["minimum_met"]) for x in pair_rows)
        if coverage_gate_enabled
        else True
    )
    missing=[x["pair"] for x in pair_rows if int(x["samples"])==0]
    under=[x["pair"] for x in pair_rows if 0<int(x["samples"])<int(min_pair_samples)]

    return {
        "samples":total,
        "min_samples":int(min_samples),
        "minimum_met":enough,
        "side_agreement_pct":pct("side_match"),
        "execution_agreement_pct":pct("execution_match"),
        "state_agreement_pct":pct("state_match"),
        "critical_mismatches":critical,
        "opposite_direction_count":sum(1 for x in rows if bool(x.get("opposite_direction",False))),
        "mean_abs_score_delta":None if not score_deltas else round(mean(score_deltas),4),
        "mean_abs_quality_delta":None if not quality_deltas else round(mean(quality_deltas),4),
        "pair_breakdown":pair_rows,
        "expected_pair_count":len(pair_rows),
        "pairs_meeting_minimum":sum(1 for x in pair_rows if bool(x["minimum_met"])),
        "coverage_gate_enabled":coverage_gate_enabled,
        "coverage_balanced":balanced,
        "missing_pairs":missing,
        "under_sampled_pairs":under,
        "min_pair_samples":int(min_pair_samples),
        "eligible_for_manual_review":bool(enough and critical==0 and balanced),
        "auto_promotion_allowed":False,
    }


def render_shadow_mode_panel(
    samples: Sequence[Mapping[str, Any]] | None = None,
    *,
    min_samples: int = 100,
    expected_pairs: Sequence[str] | None = DEFAULT_SHADOW_PAIRS,
    min_pair_samples: int = 10,
) -> dict[str, Any]:
    summary=summarize_shadow(
        samples,
        min_samples=min_samples,
        expected_pairs=expected_pairs,
        min_pair_samples=min_pair_samples,
    )
    st.markdown("### 🌓 Shadow Mode — Champion × Challenger")
    st.caption(
        "O Challenger roda em observação e não altera decisões de produção. "
        "Mesmo com boa concordância, promoção automática permanece proibida."
    )
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Amostras",f"{summary['samples']}/{summary['min_samples']}")
    c2.metric("Concordância direcional","—" if summary["side_agreement_pct"] is None else f"{summary['side_agreement_pct']:.1f}%")
    c3.metric("Concordância execução","—" if summary["execution_agreement_pct"] is None else f"{summary['execution_agreement_pct']:.1f}%")
    c4.metric("Divergências críticas",summary["critical_mismatches"])

    if summary["samples"]==0:
        st.info("Infraestrutura pronta. Ainda não há pares Champion/Challenger registrados para comparação.")
    elif summary["eligible_for_manual_review"]:
        st.success("Amostra mínima e cobertura por par atingidas sem divergência crítica: elegível apenas para revisão manual.")
    elif not summary["minimum_met"]:
        st.warning("Shadow Mode ainda precisa de mais amostras antes de qualquer revisão de promoção.")
    elif summary["critical_mismatches"]:
        st.error("Há divergências críticas; Challenger não deve ser promovido.")
    else:
        st.warning("A amostra total existe, mas a cobertura por par ainda está concentrada ou incompleta.")

    if summary["pair_breakdown"]:
        table=[]
        for row in summary["pair_breakdown"]:
            table.append({
                "Par":row["pair"],
                "Amostras":row["samples"],
                "Mínimo por par":row["minimum_met"],
                "Concordância direção":(
                    "—" if row["side_agreement_pct"] is None
                    else f"{row['side_agreement_pct']:.1f}%"
                ),
                "Concordância execução":(
                    "—" if row["execution_agreement_pct"] is None
                    else f"{row['execution_agreement_pct']:.1f}%"
                ),
                "Divergências críticas":row["critical_mismatches"],
            })
        with st.expander("Cobertura Shadow por par"):
            st.dataframe(table,width="stretch",hide_index=True)

    st.caption(
        f"Cobertura mínima por par: {summary['pairs_meeting_minimum']}/"
        f"{summary['expected_pair_count']} · Auto-promoção: DESATIVADA por design."
    )
    return summary
