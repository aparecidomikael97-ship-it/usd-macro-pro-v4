"""Painel Mestre: briefing e agenda semanal sem modificar a identidade aprovada."""
from __future__ import annotations

from html import escape
from math import isfinite
from datetime import datetime
from typing import Any, Mapping

from atlasquant_trader_master_briefing_v2 import build_master_briefing
from atlasquant_trader_calendar_ui import calendar_source_status

STYLE = """
<style>
.aqr-master-briefing{margin-top:18px}
.aqr-master-briefing .aqr-macro-row{padding:11px 14px;margin:8px 0;
 background:#0e2436;border:1px solid #2b4b62;border-radius:10px;
 color:#b9d5e6;font-size:12px;line-height:1.65}
.aqr-master-briefing .aqr-macro-row strong{color:#e7f6fb}
.aqr-master-headline{color:#f1faff;font-weight:800;font-size:12px}
.aqr-master-risk{border:1px solid #8b633a;color:#e8c49c;background:#2b251f;
 border-radius:11px;padding:14px;margin-top:14px;font-size:11px;line-height:1.65}
.aqr-master-risk li{padding-top:6px}
.aqr-master-next{display:grid;gap:8px;margin:13px 0}
.aqr-master-week{display:grid;gap:8px}
.aqr-master-week details{border:1px solid #304b60;background:#0d2132;
 padding:11px 14px;border-radius:10px;color:#d1e5f0}
.aqr-master-week summary{cursor:pointer;font-weight:750;font-size:11px;
 display:flex;justify-content:space-between;gap:9px;line-height:1.5}
.aqr-master-week summary:focus-visible{outline:2px solid #7ce8f4;outline-offset:3px}
.aqr-master-week small{font-size:10px;color:#9eb9cb}
.aqr-master-week p{font-size:11px;line-height:1.7;color:#afc9d7}
.aqr-master-week .aqr-week-status{font-size:9px;color:#f2d1a6;
 padding:5px 7px;border:1px solid #67553f;background:#29251e;border-radius:5px;
 white-space:nowrap}
.aqr-master-week .aqr-week-status.hot{color:#88ecce;background:#15382f;
 border-color:#2a7663}
.aqr-master-value{font-size:19px;color:#d4f6fb;margin:18px 0 5px;font-weight:800}
@media(max-width:700px){.aqr-master-week summary{display:block}
.aqr-master-week summary .aqr-week-status{display:inline-block;margin-top:6px}}
</style>
"""


def _number(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return "—"
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return "—"
    if not isfinite(number) or abs(number) > 1e9:
        return "—"
    return f"{number:,.2f}".replace(",", " ").replace(".", ",")


def master_overview_cards(calendar: Any, *, at: datetime | None = None) -> str:
    model = build_master_briefing(calendar, at=at)
    ready = model["state"] == "VALIDADO"
    def card(title: str, value: str, description: str, label: str) -> str:
        return ('<article class="aqr-card aqr-fourth"><h3>' + escape(title) +
                '</h3><div class="aqr-master-value">' + escape(value) +
                '</div><p>' + escape(description) + '</p>'
                '<span class="aqr-tag">' + escape(label) + '</span></article>')
    # No market-direction "green" light: editorial counts are not proof
    # of an actual macroeconomic trend or interest-rate surprise.
    return STYLE + (
        card("Cenário macro", str(model["daily_events"]) if ready else "—",
             "Eventos recebidos hoje · sem inferir viés de mercado",
             "AGENDA VERIFICADA" if ready else "AGUARDANDO FONTE") +
        card("Bancos centrais", str(model["central_bank_events"]) if ready else "—",
             "Eventos identificados hoje na agenda, não decisões interpretadas",
             "CONFERIR COMUNICADO" if ready else "SEM LEITURA") +
        card("Risco geopolítico", "—",
             "Monitoramento geopolítico exige fatos com fonte e horário",
             "SEM FEED VERIFICADO") +
        card("Notícias relevantes", "—",
             "Notícias e eventos econômicos são fontes diferentes",
             "SEM FEED VERIFICADO")
    )


def master_briefing_html(calendar: Any, *, at: datetime | None = None) -> str:
    model = build_master_briefing(calendar, at=at)
    if model["state"] != "VALIDADO":
        status_label, status_detail = calendar_source_status(calendar)
        return (
            '<section class="aqr-section aqr-master-briefing" '
            'aria-label="Briefing macro verificável">'
            '<div class="aqr-heading"><div><h2>Briefing macro do dia</h2>'
            '<p>Leitura baseada em eventos verificados, sem dados fictícios.</p></div>'
            '<span class="aqr-status">AGUARDANDO FONTE</span></div>'
            '<div class="aqr-empty-area"><strong>Briefing indisponível</strong>' +
            escape(str(model["why_not"])) +
            '<p><strong>' + escape(status_label) + ':</strong> ' +
            escape(status_detail) + '</p>'
            ' Nenhuma direção para USD, WIN ou WDO será inventada.</div></section>'
        )
    lines = "".join(
        '<div class="aqr-macro-row">' + escape(str(item)) + '</div>'
        for item in model["briefing"]
    )
    risks = model["risk_window"]
    warning = (
        '<div class="aqr-master-risk"><strong>Janela de atenção econômica</strong>'
        '<p>Proximidade de divulgação não significa direção de preço nem '
        'autorização para operar.</p><ul>' +
        "".join(
            '<li>' + escape(item["time"]) + ' · ' +
            escape(item["currency"]) + ' · ' + escape(item["name"]) +
            ' — ' + escape(item["phase"]) + '</li>' for item in risks
        ) + '</ul></div>'
    ) if risks else (
        '<div class="aqr-guide"><strong>Eventos próximos</strong>'
        'Nenhum evento de prioridade editorial foi localizado na janela '
        'de 60 minutos antes a 30 minutos depois, dentro da fonte recebida.'
        '</div>'
    )
    priority = "".join(
        '<div class="aqr-macro-row"><strong>' + escape(item["time"]) +
        ' · ' + escape(item["currency"]) + '</strong> · ' +
        escape(item["name"]) +
        ' <small>(prioridade editorial, não risco calculado pelo mercado)</small></div>'
        for item in model["priority_events"][:8]
    )
    return (
        '<section class="aqr-section aqr-master-briefing" '
        'aria-label="Briefing macro verificável">'
        '<div class="aqr-heading"><div><h2>Briefing macro do dia</h2>'
        '<p>Agenda e contexto recebidos da fonte, sem previsão de trade.</p></div>'
        '<span class="aqr-status">EVENTOS VERIFICADOS</span></div>'
        '<div class="aqr-card aqr-wide"><h3>Resumo executivo</h3>' +
        lines + warning + '</div>'
        '<div class="aqr-guide"><strong>Fontes e interpretação</strong>Fonte: ' +
        escape(model["source"]) + ' · Carimbo UTC: ' +
        escape(model["fetched_at"]) +
        '. Prioridades são apenas uma triagem editorial; consenso não é '
        'resultado divulgado, e reação do dólar depende do contexto.</div>'
        '<div class="aqr-heading"><div><h2>Divulgações de atenção</h2>'
        '<p>Eventos de hoje identificados por categoria econômica.</p></div></div>'
        + (priority or
           '<div class="aqr-empty-area">Sem eventos de prioridade editorial '
           'nos registros de hoje.</div>')
        + '</section>'
    )


def master_week_html(calendar: Any, *, at: datetime | None = None) -> str:
    """Accessible details for six forthcoming days; source driven, not fabricated."""
    model = build_master_briefing(calendar, at=at)
    heading = ('<section class="aqr-section" aria-label="Agenda econômica da semana">'
               '<div class="aqr-heading"><div><h2>Agenda econômica · próximos 6 dias</h2>'
               '<p>Horário de Brasília · previsão e número anterior quando disponíveis.</p>'
               '</div></div>')
    if model["state"] != "VALIDADO":
        return (heading + '<div class="aqr-empty-area">'
                '<strong>Agenda semanal aguardando fonte válida</strong>'
                'Nenhuma divulgação foi simulada.</div></section>')
    rows = []
    for e in model["week_preview"][:32]:
        status = ('<span class="aqr-week-status hot">ATENÇÃO EDITORIAL</span>'
                  if e["priority"] else
                  '<span class="aqr-week-status">AGENDA</span>')
        rows.append(
            '<details><summary><span>' + escape(e["date"]) + ' · ' +
            escape(e["time"]) + ' · ' + escape(e["country"]) +
            ' · ' + escape(e["name"]) + '</span>' + status + '</summary>'
            '<p><strong>Consenso:</strong> ' + _number(e["consensus"]) +
            ' · <strong>Anterior:</strong> ' + _number(e["previous"]) +
            ' · <strong>Período:</strong> ' + escape(e["period"]) +
            ' · <strong>Base:</strong> ' + escape(e["comparison"] or "nível") +
            '. Sem unidade padronizada: confirmar no anúncio oficial.</p>'
            '<p><strong>O que mede:</strong> ' + escape(e["mechanism"]) +
            '</p><p><strong>O que observar:</strong> ' +
            escape(e["watch"]) + '</p>'
            '<p><strong>Limite:</strong> ' + escape(e["caution"]) + '</p>'
            '<p><strong>Acima do consenso:</strong> ' +
            escape(e["above"]) + '</p><p><strong>Abaixo do consenso:</strong> ' +
            escape(e["below"]) + '</p>'
            '<p>Fonte: ' + escape(e["source"]) +
            ' · Data do anúncio conforme calendário; sujeito a revisão.</p>'
            '</details>'
        )
    hidden = max(0, model["week_events"] - len(rows))
    foot = ('<p class="aqr-cal-caption">Outros ' + str(hidden) +
            ' eventos não exibidos nesta visão compacta.</p>') if hidden else ''
    return (
        heading + '<div class="aqr-guide"><strong>Agenda recebida da fonte</strong>' +
        str(model["week_events"]) +
        ' registros visíveis de ' + str(model["week_received_total"]) +
        ' eventos recebidos. ' +
        ('LISTA PARCIAL: parte da semana não está exibida. '
         if model["week_partial"] else '') +
        'Isto não comprova cobertura de todos os calendários mundiais; '
        'a fonte e sua franquia determinam os resultados.'
        '</div><div class="aqr-master-week">' +
        (''.join(rows) or
         '<div class="aqr-empty-area">Nenhum evento futuro retornado pela fonte '
         'na janela selecionada.</div>') +
        '</div>' + foot + '</section>'
    )


__all__ = ["master_overview_cards", "master_briefing_html", "master_week_html"]
