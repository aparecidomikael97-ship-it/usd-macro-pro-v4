"""Read-only preview of future macro refresh windows in the approved Master."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

from atlasquant_trader_master_refresh_plan import planned_refreshes

STYLE = """
<style>
.aqr-refresh-plan{margin-top:10px}
.aqr-refresh-plan .aqr-refresh-row{border:1px solid #294a60;background:#0d2134;
 border-radius:10px;padding:10px 14px;margin-top:8px;color:#c5d8e7;font-size:11px;
 display:flex;gap:12px;justify-content:space-between;align-items:center}
.aqr-refresh-plan .aqr-refresh-hour{font-weight:800;color:#99e7f2;white-space:nowrap}
.aqr-refresh-plan .aqr-refresh-note{font-size:11px;line-height:1.65;color:#bad1de}
.aqr-refresh-plan .aqr-refresh-danger{color:#f0cfab;background:#2d241b;
 border:1px solid #846344;padding:10px 13px;border-radius:10px}
@media(max-width:700px){.aqr-refresh-plan .aqr-refresh-row{align-items:flex-start;flex-direction:column;gap:4px}}
</style>
"""


def master_refresh_plan_html(plan: Any = None) -> str:
    """No action buttons: there is NO scheduler to trigger in LAB."""
    data = plan if isinstance(plan, Mapping) else planned_refreshes(days=1)
    windows = data.get("slots")
    rows = []
    if isinstance(windows, list):
        for item in windows[:4]:
            if not isinstance(item, Mapping):
                continue
            timestamp = str(item.get("at_brt") or "")
            hhmm = timestamp[11:16] if len(timestamp) >= 16 else "—"
            rows.append(
                '<div class="aqr-refresh-row"><span class="aqr-refresh-hour">' +
                escape(hhmm) + ' BRT · ' +
                escape(str(item.get("kind") or "")) +
                '</span><span>' + escape(str(item.get("detail") or "")) +
                '</span></div>'
            )
    return (
        STYLE + '<section class="aqr-section aqr-refresh-plan" '
        'aria-label="Planejamento da atualização diária">'
        '<div class="aqr-heading"><div><h2>Atualização diária · planejamento</h2>'
        '<p>Horários propostos para Brasília, sem serviços agendados.</p></div>'
        '<span class="aqr-status">AINDA NÃO ATIVADO</span></div>'
        '<div class="aqr-refresh-danger"><strong>Somente planejamento LAB.</strong> '
        'O site não executa essas consultas com o aplicativo fechado. '
        'Nenhum agendador ou Worker do AION foi ativado.</div>'
        '<div class="aqr-refresh-note"><p>'
        'A estratégia separa calendário econômico de séries oficiais. '
        'O IPCA mensal continua mensal, mesmo quando consultado diariamente. '
        'Não há garantia de cobertura dos eventos sem autorização de fonte, '
        'cota global confiável e agendador independente.'
        '</p></div>' +
        "".join(rows) +
        '<p class="aqr-refresh-note">Calendário: ' +
        str(int(data.get("calendar_slots_per_day") or 0)) +
        ' janelas/dia · Reserva mínima planejada de ' +
        str(int(data.get("on_demand_reserve") or 0)) +
        ' consulta sob demanda, sujeita a quota GLOBAL auditável. '
        'Dados ausentes continuam indisponíveis, nunca estimados.</p>'
        '</section>'
    )


__all__ = ["master_refresh_plan_html"]
