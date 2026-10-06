"""Safe HTML projection for AION Negócios Commercial Golden Path V1."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

from atlasquant_aion_b2b_commercial_golden_path import SCHEMA, STAGE_LABELS


def _text(value: Any, limit: int = 180) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def commercial_golden_path_ready(raw: Mapping[str, Any] | None) -> bool:
    row = dict(raw) if isinstance(raw, Mapping) else {}
    return (
        row.get("schema") == SCHEMA
        and row.get("state") in {"READY", "READY_WITH_GAPS", "EMPTY"}
        and row.get("read_only") is True
        and row.get("grants_authority") is False
        and row.get("executes_action") is False
    )


def commercial_golden_path_html(raw: Mapping[str, Any] | None) -> str:
    row = dict(raw) if isinstance(raw, Mapping) else {}
    if not commercial_golden_path_ready(row):
        return ""

    state = _text(row.get("state"), 40)
    current = _text(row.get("current_stage"), 60)
    current_label = _text(row.get("current_stage_label"), 120) or STAGE_LABELS.get(current, "Lead / oportunidade")
    next_action = _text(row.get("next_human_action"), 120).replace("_", " ").title()
    stages = list(row.get("stages") or [])[:10]

    chips = []
    for item in stages:
        if not isinstance(item, Mapping):
            continue
        key = _text(item.get("key"), 60)
        label = _text(item.get("label"), 120) or STAGE_LABELS.get(key, key)
        status = _text(item.get("status"), 80)
        chips.append(
            '<div class="aq-b2b-journey-stage" '
            f'data-stage="{escape(key)}" data-status="{escape(status)}">'
            f'<small>{escape(label)}</small><strong>{escape(status.replace("_", " "))}</strong></div>'
        )

    gaps = [
        STAGE_LABELS.get(_text(item, 60), _text(item, 60))
        for item in list(row.get("lineage_gaps") or [])[:10]
        if _text(item, 60)
    ]
    gap_html = (
        '<p class="aq-b2b-journey-gap">Lacunas de evidência: ' + escape(", ".join(gaps)) + '</p>'
        if gaps else ""
    )

    return (
        '<section class="aq-b2b-journey" data-read-only="true" '
        f'data-state="{escape(state)}">'
        '<div class="aq-b2b-journey-head"><div>'
        '<small>GOLDEN PATH COMERCIAL · LEITURA</small>'
        '<h3>Jornada comercial unificada</h3>'
        '<p>Diagnóstico → qualificação → proposta → piloto → valor → recorrência.</p>'
        '</div><span>SEM AÇÃO AUTOMÁTICA</span></div>'
        f'<div class="aq-b2b-journey-current"><b>Agora:</b> {escape(current_label)}'
        f'<em>Próxima ação humana: {escape(next_action)}</em></div>'
        f'<div class="aq-b2b-journey-grid">{"".join(chips)}</div>'
        + gap_html
        + '<p class="aq-b2b-journey-foot">Este painel não envia mensagens, não altera CRM, '
        'não fecha preço, não assina contrato, não cobra e não ativa operação.</p>'
        '</section>'
    )


__all__ = ["commercial_golden_path_ready", "commercial_golden_path_html"]
