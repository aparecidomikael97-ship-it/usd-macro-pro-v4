"""AtlasQuant Trader economic calendar: accessible, read-only HTML presentation."""
from __future__ import annotations

from html import escape
from math import isfinite
from typing import Any, Mapping

from atlasquant_trader_economic_calendar import explanation

STYLE = """
<style>
.aqr-cal-list{display:grid;gap:11px;margin-top:12px}
.aqr-cal-item{background:linear-gradient(150deg,#102538,#0c1c2d);border:1px solid #315267;
border-radius:12px;padding:13px 17px;color:#dceef9}
.aqr-cal-item summary{cursor:pointer;display:flex;justify-content:space-between;
align-items:center;gap:12px;min-height:48px;list-style:none}
.aqr-cal-item summary::-webkit-details-marker{display:none}
.aqr-cal-item summary:focus-visible{outline:2px solid #63e7ef;outline-offset:3px}
.aqr-cal-item summary strong{font-size:13px;display:block;color:#eaf8ff}
.aqr-cal-item summary small{font-size:10px;display:block;margin-top:5px;color:#95b5c9}
.aqr-cal-badge{border:1px solid #6b5941;background:#312c24;color:#eac78f;
font-size:10px;border-radius:6px;padding:6px;flex-shrink:0}
.aqr-cal-values{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;
padding:12px;margin-top:12px;background:#112f3c;border-radius:8px}
.aqr-cal-values div{display:grid;gap:5px}
.aqr-cal-values small{font-size:10px;color:#a6c1cf}
.aqr-cal-values strong{font-size:16px;color:#ebf9ff}
.aqr-cal-item h4{font-size:13px;margin:15px 0 6px;color:#e8f5fe}
.aqr-cal-item p{font-size:11px;color:#b1c9d9;line-height:1.7}
.aqr-cal-caption{font-size:11px;color:#9ebace;line-height:1.6}
.aqr-cal-guide{padding:12px;border-left:3px solid #54e3e9;background:#103445;
border-radius:8px;margin:10px 0;line-height:1.7;font-size:11px;color:#d5edf7}
.aqr-cal-empty{border:1px solid #365067;border-radius:12px;background:#10243a;
text-align:center;padding:23px;color:#a9bfd3;font-size:12px}
.aqr-cal-empty strong{display:block;margin-bottom:9px;color:#eaf8ff}
@media(max-width:700px){
.aqr-cal-item summary{align-items:start}
.aqr-cal-values{padding:8px;gap:4px}
.aqr-cal-values strong{font-size:13px}
.aqr-cal-badge{font-size:9px}
}
</style>
"""


def _value(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return "—"
    try:
        n = float(value)
        if not isfinite(n) or abs(n) > 1e9:
            return "—"
    except (ValueError, TypeError, OverflowError):
        return "—"
    return f"{n:,.2f}".replace(",", " ").replace(".", ",")


def calendar_html(data: Any) -> str:
    """No invented events/consensus: only normalized daily evidence is rendered."""
    if not isinstance(data, Mapping) or data.get("state") != "READY":
        return STYLE + (
            '<div class="aqr-cal-empty"><strong>Calendário diário aguardando fonte</strong>'
            'Consulta automática preparada para a fonte existente autorizada. '
            'Sem feed disponível, não mostramos datas, expectativas ou surpresas fictícias.'
            '</div>'
        )
    label = escape(str(data.get("date") or "—"))
    source = escape(str(data.get("source") or "—"))
    header = ('<div class="aqr-cal-guide"><strong>Calendário do dia · ' + label +
              '</strong> · Horário de Brasília · Fonte: ' + source +
              '. O consenso automático é preferido; valores manuais são identificados.'
              '</div>')
    rows = data.get("events")
    if not isinstance(rows, list) or not rows:
        return STYLE + header + (
            '<div class="aqr-cal-empty"><strong>Nenhum evento recebido para hoje</strong>'
            'O calendário foi consultado, mas a fonte não retornou eventos desta data.</div>'
        )
    cards = []
    for event in rows[:120]:
        if not isinstance(event, Mapping):
            continue
        expl = explanation(event)
        title = escape(str(event.get("title") or "—"))
        country = escape(str(event.get("country") or "—"))
        clock = escape(str(event.get("time_brt") or "—"))
        currency = escape(str(event.get("currency") or "—"))
        comparison = escape(str(event.get("comparison") or "nível"))
        period = escape(str(event.get("period") or "—"))
        status = "Divulgado" if event.get("actual") is not None else "Aguardando"
        consensus_source = escape(str(event.get("consensus_source") or "Não disponível"))
        event_id = escape(str(event.get("id") or ""))
        cards.append(
            '<details class="aqr-cal-item" data-event-id="' + event_id + '">'
            '<summary><span><strong>' + clock + ' · ' + country + ' · ' +
            title + '</strong><small>' + currency + ' · ' + comparison +
            ' · ' + period + '</small></span><span class="aqr-cal-badge">' +
            escape(status) + '</span></summary>'
            '<div class="aqr-cal-values"><div><small>Consenso</small><strong>' +
            _value(event.get("consensus")) + '</strong></div>'
            '<div><small>Anterior</small><strong>' +
            _value(event.get("previous")) + '</strong></div>'
            '<div><small>Divulgado</small><strong>' +
            _value(event.get("actual")) + '</strong></div></div>'
            '<p class="aqr-cal-caption">Consenso: ' + consensus_source +
            ' · Evento: EODHD Economic Events'
            ' · Unidade não informada explicitamente pelo feed; confirme a escala na fonte.</p>'
            '<h4>O que o mercado pode esperar?</h4>'
            '<p><strong>Expectativa antes da divulgação:</strong> ' +
            escape(expl["expectation"]) + '</p>'
            '<p><strong>Se vier acima do consenso:</strong> ' +
            escape(expl["above"]) + '</p>'
            '<p><strong>Se vier abaixo do consenso:</strong> ' +
            escape(expl["below"]) + '</p>'
            '<div class="aqr-cal-guide"><strong>Leitura do resultado:</strong> ' +
            escape(expl["result"]) + '</div>'
            '<p class="aqr-cal-caption">' + escape(expl["dollar"]) + '</p>'
            '<p class="aqr-cal-caption">' + escape(expl["risk"]) + '</p>'
            '</details>'
        )
    trunc = (
        '<p class="aqr-cal-caption">Exibindo até 120 eventos de ' +
        str(int(data.get("total") or 0)) + '. O feed foi limitado por proteção de memória.</p>'
        if data.get("truncated") else ""
    )
    return STYLE + header + '<div class="aqr-cal-list">' + "".join(cards) + '</div>' + trunc


__all__ = ["calendar_html"]
