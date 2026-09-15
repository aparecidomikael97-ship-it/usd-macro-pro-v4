"""USD Macro Pro V11.0 — Decision Integrity Engine.

Combina macro, técnico, ICT, fluxo institucional, Gate, ADR e risco de evento.
O resultado é um estado operacional, NÃO uma probabilidade de lucro.
"""
from __future__ import annotations
from typing import Any, Mapping
import math
import numpy as np


def _f(v: Any, default: float = 0.0) -> float:
    try:
        x=float(v)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _status_score(s: str) -> float:
    u=str(s).upper()
    if "🟢" in s or "CONFIRMA" in u or "GATILHO" in u or "PULLBACK OK" in u:
        return 100.0
    if "🟡" in s or "PARCIAL" in u or "ALINHADO" in u or "AGUARDAR" in u or "ESTICADO" in u:
        return 60.0
    if "🔴" in s or "CONTRA" in u or "SEM GATILHO" in u:
        return 20.0
    return 45.0


def _event_level(v: Any) -> str:
    u=str(v or "NORMAL").upper().strip()
    if u in ("MÁXIMO","MAXIMO","MÁXIMA","MAXIMA","CRÍTICO","CRITICO"):
        return "MAXIMO"
    if u in ("ALTO","ELEVADO","HIGH"):
        return "ELEVADO"
    if u in ("MÉDIO","MEDIO","MODERADO","MEDIUM"):
        return "MODERADO"
    return "NORMAL"


def evaluate_decision_integrity(
    *, side: str, score: float, quality: float, rank_index: float,
    h4: str, h1: str, m15: str,
    ict_readiness: float, institutional_readiness: float,
    gate: str, gate_score: float,
    adr_used_pct: float | None,
    event_risk: str,
    technical_age_min: float | None = None,
    news_alignment: str = "",
) -> dict[str, Any]:
    side=str(side).upper()
    score=_f(score); quality=_f(quality); rank_index=_f(rank_index)
    ict=_f(ict_readiness); inst=_f(institutional_readiness)
    gate_score=_f(gate_score)
    adr=None if adr_used_pct in (None,"") else _f(adr_used_pct)
    age=None if technical_age_min in (None,"") else _f(technical_age_min)
    event=_event_level(event_risk)

    tech_scores=[_status_score(h4),_status_score(h1),_status_score(m15)]
    tech_avg=float(np.mean(tech_scores))

    hard=[]; soft=[]; positives=[]
    macro_wait = side not in ("BUY","SELL")
    if quality < 60:
        hard.append(f"Qualidade de dados baixa ({quality:.0f}%)")
    if _status_score(h4) <= 25:
        hard.append("H4 está contra o viés")
    if _status_score(h1) <= 25:
        hard.append("H1 está contra o viés")
    if age is not None and age > 75:
        hard.append(f"Técnica desatualizada ({age:.0f} min)")
    if event == "MAXIMO":
        hard.append("Evento de risco máximo")
    if adr is not None and adr >= 115:
        hard.append(f"ADR14 muito esticado ({adr:.0f}%)")

    gate_u=str(gate).upper()
    if "WAIT" in gate_u or gate_score < 55:
        soft.append("Gate ainda não liberou execução")
    if event == "ELEVADO":
        soft.append("Risco de evento elevado")
    if adr is not None and adr >= 95:
        soft.append(f"ADR14 em {adr:.0f}%: evitar perseguir preço")
    elif adr is not None and adr >= 85:
        soft.append(f"ADR14 em {adr:.0f}%: espaço reduzido")
    if ict < 70:
        soft.append(f"ICT incompleto ({ict:.0f}/100)")
    if inst < 70:
        soft.append(f"Fluxo institucional incompleto ({inst:.0f}/100)")
    if _status_score(m15) < 80:
        soft.append("M15 ainda não confirmou gatilho")

    if score >= 80: positives.append(f"Score Mestre forte ({score:.0f}/100)")
    if quality >= 75: positives.append(f"Qualidade alta ({quality:.0f}%)")
    if tech_avg >= 85: positives.append("H4/H1/M15 fortemente alinhados")
    if ict >= 75: positives.append(f"ICT alinhado ({ict:.0f}/100)")
    if inst >= 75: positives.append(f"Fluxo institucional alinhado ({inst:.0f}/100)")
    if gate_score >= 70 and "WAIT" not in gate_u: positives.append(f"Gate liberado ({gate_score:.0f}/100)")

    # Índice de prioridade operacional, com penalidades. Não é probabilidade.
    raw=(
        rank_index*.25 + score*.16 + quality*.10 + tech_avg*.17 +
        ict*.12 + inst*.14 + max(gate_score,50)*.06
    )
    penalties=0.0
    penalties += 22.0*len(hard)
    penalties += 6.0*len(soft)
    if adr is not None and adr>100:
        penalties += min(12.0,(adr-100)*.6)
    priority=float(np.clip(raw-penalties,0,100))

    executable=(
        side in ("BUY","SELL") and not hard and
        _status_score(h4)>=80 and _status_score(h1)>=80 and _status_score(m15)>=80 and
        ict>=70 and inst>=70 and gate_score>=65 and "WAIT" not in gate_u and
        event not in ("MAXIMO","ELEVADO") and (adr is None or adr<95)
    )

    if macro_wait:
        state="⚪ AGUARDAR DIREÇÃO"
    elif hard:
        state="🔴 BLOQUEADO"
    elif executable:
        state="🟢 EXECUTÁVEL"
    elif _status_score(h4)>=80 and _status_score(h1)>=80 and score>=75:
        state="🟡 DIREÇÃO CONFIRMADA — AGUARDAR EXECUÇÃO"
    elif priority>=62:
        state="🟠 SETUP EM FORMAÇÃO"
    else:
        state="⚪ EM OBSERVAÇÃO"

    if state=="🟢 EXECUTÁVEL":
        next_action="Condições obrigatórias passaram; usar plano de risco/invalidação e não perseguir preço."
    elif macro_wait:
        next_action="Não antecipar. Aguardar o motor macro definir BUY ou SELL."
    elif hard:
        next_action="Não executar enquanto houver bloqueio duro."
    elif soft:
        next_action="Aguardar resolver: " + "; ".join(soft[:3]) + "."
    else:
        next_action="Aguardar nova confirmação de estrutura/localização."

    return {
        "state":state,
        "priority_score":round(priority,1),
        "technical_score":round(tech_avg,1),
        "hard_blocks":hard,
        "soft_blocks":soft,
        "positives":positives,
        "executable":bool(executable),
        "next_action":next_action,
        "event_level":event,
        "note":"Prioridade operacional; não é probabilidade de lucro.",
    }
